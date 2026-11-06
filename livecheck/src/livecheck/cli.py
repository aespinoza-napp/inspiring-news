"""
    livecheck listen [--app brave]      what this machine is playing, live
    livecheck file talk.mp3 [--realtime]  a recording
    livecheck report sessions/<dir>     the report again, from what was recorded
    livecheck apps                      which applications are playing now
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from livecheck import report as report_module
from livecheck.audio import FileAudio, SystemAudio
from livecheck.judge import ANSWERED, NO_REPLY, NOT_JUDGED, PARTIAL, OllamaChat
from livecheck.segmenter import Segmenter
from livecheck.session import Session, stop_on_interrupt
from livecheck.speakers import SherpaEmbedder, SpeakerTracker
from livecheck.transcriber import Transcriber
from livecheck.verifier import BackendVerifier, FALSE, MIXED, NOT_CHECKED, TRUE

# livecheck/src/livecheck/cli.py -> livecheck/
ROOT = Path(__file__).resolve().parents[2]

GREY, CYAN, GREEN, RED, YELLOW, BOLD, RESET = (
    "\033[90m", "\033[36m", "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m",
)


def _clock(seconds: float) -> str:
    return f"{int(seconds) // 60:02}:{int(seconds) % 60:02}"


def show(kind: str, data: dict) -> None:
    """The live view. Every line stands alone, so the terminal keeps a record."""

    if kind == "sentence":

        sentence = data["sentence"]
        colour = CYAN if data["role"] == "asks" else GREEN
        label = {"asks": "ASKS", "answers": "ANSWERS"}.get(data["role"], "SPEAKS")

        print(f"{GREY}{_clock(sentence.start)}{RESET} {colour}{label:7} v{sentence.speaker + 1}{RESET} {sentence.text}")

    elif kind == "judged":

        judgement = data["judgement"]
        words, colour = {
            ANSWERED: ("ANSWERED", GREEN),
            PARTIAL: ("ANSWERED IN PART", YELLOW),
            NO_REPLY: ("NO REPLY", YELLOW),
            NOT_JUDGED: ("NOT JUDGED", GREY),
        }.get(judgement.status, ("NOT EXPLICITLY ANSWERED", RED))

        print(f"      {colour}{BOLD}{words}{RESET} (question at {_clock(data['at'])}) {GREY}{judgement.reason}{RESET}")

    elif kind == "claim_queued":
        print(f"      {GREY}to check ({data['waiting']} waiting): {data['claim']}{RESET}")

    elif kind == "checked":

        words, colour = {
            TRUE: ("TRUE", GREEN),
            FALSE: ("FALSE", RED),
            MIXED: ("PARTLY TRUE", YELLOW),
            NOT_CHECKED: ("NOT CHECKED", GREY),
        }.get(data["outcome"], ("NO VERDICT", GREY))

        print(f"      {colour}{BOLD}{words}{RESET} (said at {_clock(data['at'])}) {data['claim']}")

    elif kind == "skipped":
        print(f"{YELLOW}Behind the stream: skipped {_clock(data['start'])}-{_clock(data['end'])}.{RESET}")

    elif kind == "silence":
        print(f"{YELLOW}Nothing heard for {data['seconds']:.0f} s. Muted, or another output?{RESET}")

    elif kind == "stage":
        print(f"{GREY}{data['text']}{RESET}")

    sys.stdout.flush()


def _default_model() -> str:
    """The verifier's model, so the two do not push each other out of memory."""

    env = ROOT.parent / "backend" / ".env"

    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("LLM_MODEL="):
                return line.split("=", 1)[1].strip().strip("\"'")

    return "llama3.2:3b"


def _api_key() -> str | None:

    if os.environ.get("STORAGE_API_KEY"):
        return os.environ["STORAGE_API_KEY"]

    env = ROOT.parent / "backend" / ".env"

    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("STORAGE_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'") or None

    return None


def _run(source, args) -> int:

    directory = Path(args.out or ROOT / "sessions" / time.strftime("%Y%m%d-%H%M%S"))

    verify = BackendVerifier(args.backend, _api_key())

    problem = verify.reachable()

    if problem:
        print(
            f"{YELLOW}The fact-checker at {args.backend} cannot check claims ({problem}): "
            f"statements will be listed as not checked. Start it with ./scripts/stack.sh analyse.{RESET}"
        )

    print(f"{GREY}Loading the speech models ({args.whisper})...{RESET}")

    session = Session(
        source=source,
        segmenter=Segmenter(),
        transcribe=Transcriber(args.whisper, args.language, args.threads),
        tracker=SpeakerTracker(SherpaEmbedder(), threshold=args.threshold, max_speakers=args.max_speakers),
        chat=OllamaChat(args.model or _default_model(), args.ollama),
        verify=verify,
        directory=directory,
        show=show,
        max_claims=args.max_claims,
    )

    stop_on_interrupt(session)

    print(f"{GREY}Listening. Ctrl-C to stop.{RESET}")

    session.run()

    path = report_module.write(directory)

    print(f"\n{BOLD}Report:{RESET} {path}")

    return 0


def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(prog="livecheck", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def add_session_options(sub):
        sub.add_argument("--whisper", default="small", help="Whisper model: base is faster, medium hears better")
        sub.add_argument("--language", help="en, es...; detected when left out")
        sub.add_argument("--threads", type=int, default=4, help="CPU threads for the words")
        sub.add_argument("--max-speakers", type=int, default=4)
        sub.add_argument("--threshold", type=float, default=0.72, help="how alike two sounds must be to be one voice")
        sub.add_argument("--model", help="Ollama model that judges answers; default: backend/.env's LLM_MODEL")
        sub.add_argument("--ollama", default="http://localhost:11434")
        sub.add_argument("--backend", default="http://localhost:8000")
        sub.add_argument("--max-claims", type=int, default=30)
        sub.add_argument("--out", help="session directory; default: livecheck/sessions/<now>")

    listen = commands.add_parser("listen", help="what this machine is playing")
    listen.add_argument("--app", help="only this application's sound, as named by `livecheck apps`")
    add_session_options(listen)

    recording = commands.add_parser("file", help="a recording")
    recording.add_argument("path")
    recording.add_argument("--realtime", action="store_true", help="at the speed of speech, as if live")
    add_session_options(recording)

    again = commands.add_parser("report", help="write the report again")
    again.add_argument("directory")

    commands.add_parser("apps", help="what is playing now")

    args = parser.parse_args(argv)

    if args.command == "apps":
        subprocess.run("pactl list sink-inputs | grep -E 'application.(name|process.binary) ='", shell=True)
        return 0

    if args.command == "report":
        print(report_module.write(Path(args.directory)))
        return 0

    if args.command == "listen":
        return _run(SystemAudio(args.app), args)

    source = FileAudio(args.path, realtime=args.realtime)

    # Not live: nothing to fall behind, so nothing may be skipped.
    source.pre_recorded = not args.realtime

    return _run(source, args)


if __name__ == "__main__":
    raise SystemExit(main())

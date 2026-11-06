"""The whole run with every model replaced: its order, its counts, its gaps."""

import numpy as np

from livecheck import report
from livecheck.audio import SAMPLE_RATE
from livecheck.segmenter import Utterance
from livecheck.session import Session
from livecheck.speakers import SpeakerTracker
from livecheck.transcriber import TimedSentence
from livecheck.verifier import NOT_CHECKED

SCRIPT = [
    (0, "How many people live in Spain?"),
    (1, "About forty eight million people live in Spain."),
    (0, "Will you raise taxes?"),
    (1, "Let me talk about something else entirely, because it matters."),
    (0, "Who won the 2010 World Cup?"),
    (1, "Brazil won the 2010 World Cup."),
    (0, "And what about the budget?"),
]


class Scripted:
    """One utterance per second per line; its first sample names the voice."""

    def chunks(self):
        yield np.zeros(SAMPLE_RATE // 4, dtype=np.float32)

    def stop(self):
        pass


class ScriptedSegmenter:

    def feed(self, chunk):
        return []

    def flush(self):

        utterances = []

        for index, (voice, _) in enumerate(SCRIPT):
            audio = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
            audio[:] = voice + 1
            utterances.append(Utterance(index * 3.0, index * 3.0 + 3, audio))

        return utterances


def transcribe(audio, offset):

    text = SCRIPT[int(offset // 3)][1]

    return [TimedSentence(offset, offset + 3, text)]


def embed(audio):
    return np.array([1.0, 0.0]) if audio[0] == 1 else np.array([0.0, 1.0])


def chat(system, user, schema):

    if "parts" in schema["properties"]:

        if "something else" in user:
            return {"parts": [{"asks": "the question", "words": ""}]}

        return {"parts": [{"asks": "the question", "words": user.split("REPLY: ", 1)[1]}]}

    if "forty eight" in user:
        return {"claims": [{"claim": "About forty eight million people live in Spain.", "quote": ""}]}

    if "Brazil" in user:
        return {"claims": [{"claim": "Brazil won the 2010 World Cup.", "quote": "Brazil won the 2010 World Cup."}]}

    return {"claims": []}


def verify(claim):

    outcome = "false" if "Brazil" in claim else "true"

    return {"outcome": outcome, "verdict": outcome.upper(), "confidence": 0.9, "explanation": "x", "note": "", "sources": []}


def run(tmp_path, **options):

    Session(
        source=Scripted(),
        segmenter=ScriptedSegmenter(),
        transcribe=transcribe,
        tracker=SpeakerTracker(embed),
        chat=options.pop("chat", chat),
        verify=options.pop("verify", verify),
        directory=tmp_path,
        **options,
    ).run()

    return report.build(report.load_events(tmp_path))


def test_the_report_counts_what_happened(tmp_path):

    result = run(tmp_path)

    assert result["finished"]
    assert result["words_total"] == sum(len(text.split()) for _, text in SCRIPT)
    assert {s["speaker"]: s["role"] for s in result["speakers"]} == {0: "asks", 1: "answers"}

    questions = result["questions"]

    assert questions["total"] == 4
    assert len(questions["answered"]) == 2
    assert [q["question"] for q in questions["not_answered"]] == ["Will you raise taxes?"]
    assert [q["question"] for q in questions["no_reply"]] == ["And what about the budget?"]

    assert [c["claim"] for c in result["statements"]["true"]] == ["About forty eight million people live in Spain."]
    assert [c["claim"] for c in result["statements"]["false"]] == ["Brazil won the 2010 World Cup."]


def test_the_markdown_carries_every_count_asked_for(tmp_path):

    run(tmp_path)

    text = report.write(tmp_path).read_text(encoding="utf-8")

    for row in [
        "| Words said | ",
        "| Questions answered | 2 |",
        "| Questions not explicitly answered | 2 (0 in part, 1 avoided, 1 with no reply) |",
        "| True statements | 1 |",
        "| False statements | 1 |",
    ]:
        assert row in text

    assert "Brazil won the 2010 World Cup." in text.split("## False statements")[1].split("## True")[0]


def test_past_the_limit_a_claim_is_listed_as_not_checked(tmp_path):

    asked = []

    def counting(claim):
        asked.append(claim)
        return verify(claim)

    result = run(tmp_path, verify=counting, max_claims=1)

    assert len(asked) == 1
    assert len(result["statements"]["not_checked"]) == 1


def test_with_no_model_nothing_is_counted_as_answered(tmp_path):

    def down(system, user, schema):
        raise ConnectionError("refused")

    result = run(tmp_path, chat=down)

    assert result["questions"]["answered"] == []
    assert result["questions"]["not_answered"] == []
    assert len(result["questions"]["not_judged"]) == 3
    assert result["extraction_failures"] == 3

    assert "Questions not judged | 3" in report.to_markdown(result)


def test_an_unfinished_session_still_reports_what_it_heard(tmp_path):

    run(tmp_path)

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()

    (tmp_path / "events.jsonl").write_text("\n".join(lines[:-1]) + '\n{"type": "sent', encoding="utf-8")

    result = report.build(report.load_events(tmp_path))

    assert not result["finished"]
    assert "did not finish normally" in report.to_markdown(result)

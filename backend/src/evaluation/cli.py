"""
The evaluation harness's one command.

    cd backend
    uv run python -m src.evaluation.cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl \
        --model llama3.2:3b [--limit N] [--thresholds f.json] [--corpus snapshot|none] \
        [--retry-unavailable] [--fresh]

The provider is configuration, never a flag: LLM_BASE_URL, LLM_API_KEY
(and LLM_TIMEOUT, LLM_MAX_CONCURRENCY) from the environment or
backend/.env, exactly as the API reads them. Ollama and Groq differ by
those variables alone.

Ctrl-C once stops starting new claims and lets the ones in flight finish
and be written; the same command later resumes. Ctrl-C twice aborts.

docs/decisions/evaluation.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
from pathlib import Path

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds, ThresholdOverrides
from src.evaluation.dataset import load_dataset
from src.evaluation.runner import CORPUS_MODES, SNAPSHOT, RunConfig, build_runner, default_runs_root

logger = logging.getLogger(__name__)


def load_thresholds(path: str | None) -> PipelineThresholds:
    """
    `--thresholds f.json` resolves the way a request's overrides do: the
    fields it names, over the environment defaults. An unknown field is
    an error, not a silently ignored typo.
    """

    if not path:
        return PipelineThresholds()

    overrides = json.loads(Path(path).read_text(encoding="utf-8"))

    return PipelineThresholds.resolve(ThresholdOverrides(**overrides))


def cmd_run(args: argparse.Namespace) -> int:

    dataset = load_dataset(args.dataset)

    config = RunConfig(
        dataset=dataset,
        model=args.model or settings.LLM_MODEL,
        thresholds=load_thresholds(args.thresholds),
        corpus=args.corpus,
        root=Path(args.root) if args.root else default_runs_root(),
    )

    runner, close = build_runner(config)

    _stop_on_first_interrupt(runner.stop)

    try:
        session = runner.run(
            limit=args.limit,
            retry_unavailable=args.retry_unavailable,
            fresh=args.fresh,
        )
    finally:
        close()

    print(json.dumps({"run": str(config.directory), **session}, indent=2))

    return 0 if session["errors"] == 0 else 1


def _stop_on_first_interrupt(stop) -> None:

    def handler(signum, frame):
        print(
            "\nStopping: no new claims; the ones in flight finish and are "
            "written. Ctrl-C again to abort.",
            file=sys.stderr,
        )
        stop()
        signal.signal(signal.SIGINT, signal.default_int_handler)

    signal.signal(signal.SIGINT, handler)


def parser() -> argparse.ArgumentParser:

    root = argparse.ArgumentParser(
        prog="python -m src.evaluation.cli",
        description="Run the pipeline over a labelled set, and report on it.",
    )

    commands = root.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run (or resume) a model over a dataset")
    run.add_argument("--dataset", required=True, help="a JSONL file, or a directory of one-fact JSON files")
    run.add_argument("--model", help=f"the LLM to verify with (default: LLM_MODEL, {settings.LLM_MODEL})")
    run.add_argument("--limit", type=int, help="only the first N rows of the dataset")
    run.add_argument("--thresholds", help="a JSON file of threshold overrides")
    run.add_argument("--corpus", choices=CORPUS_MODES, default=SNAPSHOT)
    run.add_argument(
        "--retry-unavailable",
        action="store_true",
        help="also re-run claims whose search or LLM was never reached",
    )
    run.add_argument("--fresh", action="store_true", help="set the results aside and start over")
    run.add_argument("--root", help=argparse.SUPPRESS)
    run.set_defaults(handler=cmd_run)

    return root


def main(argv: list[str] | None = None) -> int:

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    args = parser().parse_args(argv)

    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

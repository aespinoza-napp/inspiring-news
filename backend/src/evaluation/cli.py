"""
The evaluation harness's one command.

    cd backend
    uv run python -m src.evaluation.cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl \
        --model llama3.2:3b [--limit N] [--thresholds f.json] [--corpus snapshot|none] \
        [--retry-unavailable] [--fresh]

    uv run python -m src.evaluation.cli report --run <run dir> [--compare <run dir>]         [--prices data/evaluation/prices.json] [--seed N] [--resamples N]

    uv run python -m src.evaluation.cli table --run <dir> --run <dir> ... [--prices ...]

    uv run python -m src.evaluation.cli writing run --model llama3.2:3b [--repeats 2] [--texts f.jsonl]
    uv run python -m src.evaluation.cli writing report --run <dir> --run <dir> ... [--prices ...]

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
from src.evaluation.metrics import DEFAULT_RESAMPLES, DEFAULT_SEED
from src.evaluation.report import models_table, write_report
from src.evaluation.runner import CORPUS_MODES, SNAPSHOT, RunConfig, build_runner, default_runs_root
from src.evaluation.usage import load_prices
from src.evaluation.writing import build_writing_runner, load_texts, write_comparison

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


def cmd_report(args: argparse.Namespace) -> int:

    target = write_report(
        args.run,
        compare_with=args.compare,
        prices=load_prices(args.prices) if args.prices else None,
        seed=args.seed,
        resamples=args.resamples,
        root=Path(args.out) if args.out else None,
    )

    print(f"Report written to {target}")
    print((target / "report.md").read_text(encoding="utf-8"))

    return 0


def cmd_table(args: argparse.Namespace) -> int:

    target = models_table(
        args.run,
        prices=load_prices(args.prices) if args.prices else None,
        seed=args.seed,
        resamples=args.resamples,
        root=Path(args.out) if args.out else None,
    )

    print(f"Table written to {target / 'models.md'}")
    print((target / "models.md").read_text(encoding="utf-8"))

    return 0


def cmd_writing_run(args: argparse.Namespace) -> int:

    runner = build_writing_runner(
        load_texts(args.texts),
        args.model or settings.LLM_MODEL,
        root=Path(args.root) if args.root else None,
    )

    _stop_on_first_interrupt(runner.stop)

    session = runner.run(repeats=args.repeats, limit=args.limit, fresh=args.fresh)

    print(json.dumps({"run": str(runner.directory), **session}, indent=2))

    return 0 if session["errors"] == 0 else 1


def cmd_writing_report(args: argparse.Namespace) -> int:

    target = write_comparison(
        args.run,
        prices=load_prices(args.prices) if args.prices else None,
        seed=args.seed,
        resamples=args.resamples,
        root=Path(args.out) if args.out else None,
    )

    print(f"Comparison written to {target / 'comparison.md'}")
    print((target / "comparison.md").read_text(encoding="utf-8"))

    return 0


def _report_options(command: argparse.ArgumentParser) -> None:

    command.add_argument("--prices", help="a prices file (data/evaluation/prices.json) to cost the run")
    command.add_argument("--seed", type=int, default=DEFAULT_SEED, help="bootstrap seed")
    command.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES, help="bootstrap resamples")
    command.add_argument("--out", help=argparse.SUPPRESS)


def _stop_on_first_interrupt(stop) -> None:

    def handler(signum, frame):
        print(
            "\nStopping: nothing new is started; what is in flight finishes "
            "and is written. Ctrl-C again to abort.",
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

    report = commands.add_parser("report", help="metrics.json and report.md for a run")
    report.add_argument("--run", required=True, help="the run directory (runs/<dataset>/<model>/<key>)")
    report.add_argument("--compare", help="a baseline run to compare against, paired over shared claims")
    _report_options(report)
    report.set_defaults(handler=cmd_report)

    table = commands.add_parser("table", help="several runs over one dataset, side by side")
    table.add_argument("--run", required=True, action="append", help="a run directory; repeat per model")
    _report_options(table)
    table.set_defaults(handler=cmd_table)

    writing = commands.add_parser(
        "writing",
        help="the writing-model benchmark: the corrector's five LLM metrics per model",
    ).add_subparsers(dest="writing_command", required=True)

    writing_run = writing.add_parser("run", help="run (or resume) a model over the text set")
    writing_run.add_argument("--model", help=f"the LLM to judge with (default: LLM_MODEL, {settings.LLM_MODEL})")
    writing_run.add_argument("--texts", help="the text set (default: data/evaluation/writing/texts_en_es.jsonl)")
    writing_run.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="times each text is judged; raising it later adds repeats to the same run",
    )
    writing_run.add_argument("--limit", type=int, help="only the first N texts")
    writing_run.add_argument("--fresh", action="store_true", help="set the results aside and start over")
    writing_run.add_argument("--root", help=argparse.SUPPRESS)
    writing_run.set_defaults(handler=cmd_writing_run)

    writing_report = writing.add_parser(
        "report",
        help="the rubric for one run, or several side by side (the first is the baseline)",
    )
    writing_report.add_argument("--run", required=True, action="append", help="a run directory; repeat per model")
    _report_options(writing_report)
    writing_report.set_defaults(handler=cmd_writing_report)

    return root


def main(argv: list[str] | None = None) -> int:

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # A Windows console is cp1252, and the reports carry "·" and "−":
    # printing one raised UnicodeEncodeError after the report had been
    # written. Replace what the console cannot show instead.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    args = parser().parse_args(argv)

    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

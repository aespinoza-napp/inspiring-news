"""
The evaluation harness's one command.

    cd backend
    uv run python -m src.evaluation.cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl \
        --model llama3.2:3b [--limit N] [--thresholds f.json] [--corpus snapshot|none] \
        [--retry-unavailable] [--fresh]

    uv run python -m src.evaluation.cli report --run <run dir> [--compare <run dir>]         [--prices data/evaluation/prices.json] [--seed N] [--resamples N]

    uv run python -m src.evaluation.cli table --run <dir> --run <dir> ... [--prices ...]

    uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split train --loop
    uv run python -m src.evaluation.cli loop --run <dir>
    uv run python -m src.evaluation.cli consistency --run <test run> --run <recheck run>
    uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split train --oracle --model <m>
    uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split test --closed-book --model <m>

    uv run python -m src.evaluation.cli run --dataset <set> --retrieval-only --label <strategy>
    uv run python -m src.evaluation.cli retrieval --run <dir> --run <dir> ...

    uv run python -m src.evaluation.cli pool --run A --run B ... --judgements data/evaluation/judgements/<set>.jsonl
    uv run python -m src.evaluation.cli judge --judgements data/evaluation/judgements/<set>.jsonl
    uv run python -m src.evaluation.cli pooled --run A --run B ... --judgements data/evaluation/judgements/<set>.jsonl

    uv run python -m src.evaluation.cli freshness --dataset data/evaluation/manual [--split test] [--run <dir> ...]

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
from src.evaluation.dataset import SAMPLES, load_dataset, select_rows
from src.evaluation.consistency import write_consistency
from src.evaluation.freshness import freshness, write_freshness
from src.evaluation import pooling
from src.evaluation.loop import write_loop_report
from src.evaluation.metrics import DEFAULT_RESAMPLES, DEFAULT_SEED
from src.evaluation.report import default_reports_root, load_run, models_table, retrieval_table, write_report
from src.evaluation.runner import (
    CORPUS_MODES,
    FULL,
    CLOSED_BOOK,
    ORACLE,
    RETRIEVAL,
    RETRIEVAL_ONLY_MODEL,
    SNAPSHOT,
    RunConfig,
    build_runner,
    default_runs_root,
)
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

    dataset = select_rows(load_dataset(args.dataset), split=args.split, sample=args.sample)

    if args.oracle and (args.retrieval_only or args.loop):
        # The loop already ends on the annotator's pages, and retrieval-only
        # asks no model: neither means anything over evidence given in.
        raise SystemExit("--oracle takes neither --retrieval-only nor --loop")

    if args.closed_book and (args.retrieval_only or args.oracle or args.loop):
        # Three evidence conditions, one per run; the loop needs evidence.
        raise SystemExit("--closed-book takes none of --retrieval-only, --oracle or --loop")

    # backend/.env may make the app fast (FACT_CHECK_PROFILE), and the
    # harness reads the same file: say so, since a thesis run is meant to be
    # the pipeline as the author chose it. The run key records the result.
    if settings.FACT_CHECK_PROFILE != "thorough" and not args.thresholds:
        logger.warning(
            "FACT_CHECK_PROFILE=%s: this run takes that profile's thresholds as its defaults; "
            "--thresholds data/evaluation/thresholds/thorough.json runs the pipeline as before.",
            settings.FACT_CHECK_PROFILE,
        )

    config = RunConfig(
        dataset=dataset,
        # No model is asked in a retrieval-only run; its directory says so.
        model=RETRIEVAL_ONLY_MODEL if args.retrieval_only else (args.model or settings.LLM_MODEL),
        thresholds=load_thresholds(args.thresholds),
        corpus=args.corpus,
        root=Path(args.root) if args.root else default_runs_root(),
        mode=(
            RETRIEVAL if args.retrieval_only
            else ORACLE if args.oracle
            else CLOSED_BOOK if args.closed_book
            else FULL
        ),
        label=args.label,
        loop=args.loop,
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
        minutes_per_fact=args.minutes_per_fact,
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


def cmd_retrieval(args: argparse.Namespace) -> int:

    target = retrieval_table(
        args.run,
        seed=args.seed,
        resamples=args.resamples,
        root=Path(args.out) if args.out else None,
    )

    print(f"Table written to {target / 'retrieval.md'}")
    print((target / "retrieval.md").read_text(encoding="utf-8"))

    return 0


def cmd_pool(args: argparse.Namespace) -> int:

    path = Path(args.judgements)
    entries, added = pooling.pool([load_run(run) for run in args.run], pooling.load_judgements(path), depth=args.depth)
    pooling.save_judgements(path, entries)

    left = sum(1 for entry in entries if entry["relevant"] is None)
    print(f"{added} new page(s) pooled into {path}: {len(entries)} in all, {left} to judge "
          f"(python -m src.evaluation.cli judge --judgements {path}).")

    return 0


def cmd_judge(args: argparse.Namespace) -> int:

    pooling.judge(Path(args.judgements))

    return 0


def cmd_pooled(args: argparse.Namespace) -> int:

    runs = [load_run(run) for run in args.run]
    table = pooling.pooled_table(
        runs, pooling.load_judgements(Path(args.judgements)),
        depth=args.depth, seed=args.seed, resamples=args.resamples,
    )

    root = Path(args.out) if args.out else default_reports_root()
    stem = (runs[0].manifest.get("dataset") or {}).get("stem") or "runs"
    target = root / stem
    target.mkdir(parents=True, exist_ok=True)

    from src.evaluation.store import write_json

    write_json(target / "pooled.json", table)
    (target / "pooled.md").write_text(pooling.render(table), encoding="utf-8")

    print(f"Pooled scores written to {target / 'pooled.md'}")
    print((target / "pooled.md").read_text(encoding="utf-8"))

    return 0


def cmd_freshness(args: argparse.Namespace) -> int:

    dataset = select_rows(load_dataset(args.dataset), split=args.split)

    result = freshness(
        dataset,
        [load_run(directory) for directory in args.run or []],
        seed=args.seed,
        resamples=args.resamples,
    )

    target = write_freshness(result, Path(args.out) if args.out else default_reports_root())

    print(f"Freshness written to {target / 'freshness.md'}")
    print((target / "freshness.md").read_text(encoding="utf-8"))

    return 0


def cmd_loop(args: argparse.Namespace) -> int:

    target = write_loop_report(
        args.run,
        seed=args.seed,
        resamples=args.resamples,
        root=Path(args.out) if args.out else None,
    )

    print(f"Loop report written to {target / 'loop.md'}")
    print((target / "loop.md").read_text(encoding="utf-8"))

    return 0


def cmd_consistency(args: argparse.Namespace) -> int:

    if len(args.run) != 2:
        print("consistency compares exactly two runs: --run A --run B", file=sys.stderr)
        return 2

    target = write_consistency(
        args.run[0],
        args.run[1],
        seed=args.seed,
        resamples=args.resamples,
        root=Path(args.out) if args.out else None,
    )

    print(f"Consistency written to {target}")
    print(target.read_text(encoding="utf-8"))

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
    run.add_argument(
        "--split",
        help="only the rows of this split (the custom set's frozen train / test halves, "
        "x-fact's train / dev / test); its own run directory, <dataset>-<split>",
    )
    run.add_argument(
        "--sample",
        choices=SAMPLES,
        help="only the re-check sample from the labeller's split manifest: the fifth of "
        "the test half labelled again and run again, for consistency",
    )
    run.add_argument("--thresholds", help="a JSON file of threshold overrides")
    run.add_argument("--corpus", choices=CORPUS_MODES, default=SNAPSHOT)
    run.add_argument(
        "--retry-unavailable",
        action="store_true",
        help="also re-run claims whose search or LLM was never reached",
    )
    run.add_argument("--fresh", action="store_true", help="set the results aside and start over")
    run.add_argument(
        "--retrieval-only",
        action="store_true",
        help="stop before the model: measure retrieval for its search and fetch time alone",
    )
    run.add_argument(
        "--oracle",
        action="store_true",
        help="no search: the model judges each claim on the annotator's own reference pages "
        "(RQ2's oracle condition); keyed, so it never resumes a run that searched",
    )
    run.add_argument(
        "--closed-book",
        action="store_true",
        help="no evidence and no pipeline: the model judges each claim from the claim alone "
        "(RQ2's closed-book condition); keyed like --oracle",
    )
    run.add_argument(
        "--label",
        help="a name for the strategy this run measures; part of the run key, so two code "
        "variants with the same settings are two runs",
    )
    run.add_argument(
        "--loop",
        action="store_true",
        help="the tuning loop: a second look on every claim whose verdict disagrees with gold "
        "(or is in doubt), then the annotator's own pages when it still disagrees - "
        "on the train half only",
    )
    run.add_argument("--root", help=argparse.SUPPRESS)
    run.set_defaults(handler=cmd_run)

    report = commands.add_parser("report", help="metrics.json and report.md for a run")
    report.add_argument("--run", required=True, help="the run directory (runs/<dataset>/<model>/<key>)")
    report.add_argument("--compare", help="a baseline run to compare against, paired over shared claims")
    report.add_argument(
        "--minutes-per-fact",
        type=float,
        help="a person's median minutes per fact (python labeller/app.py stats), for the effort estimate",
    )
    _report_options(report)
    report.set_defaults(handler=cmd_report)

    table = commands.add_parser("table", help="several runs over one dataset, side by side")
    table.add_argument("--run", required=True, action="append", help="a run directory; repeat per model")
    _report_options(table)
    table.set_defaults(handler=cmd_table)

    loop = commands.add_parser(
        "loop",
        help="what the tuning loop found in a run made with --loop: fixed, retrieval, adjudicate...",
    )
    loop.add_argument("--run", required=True, help="the run directory")
    _report_options(loop)
    loop.set_defaults(handler=cmd_loop)

    again = commands.add_parser(
        "consistency",
        help="two runs over the same claims: verdict agreement, kappa, and where a change came from",
    )
    again.add_argument("--run", required=True, action="append", help="a run directory; exactly two")
    _report_options(again)
    again.set_defaults(handler=cmd_consistency)

    strategies = commands.add_parser(
        "retrieval",
        help="retrieval strategies over one dataset, side by side, each paired against the first",
    )
    strategies.add_argument("--run", required=True, action="append", help="a run directory; repeat per strategy")
    _report_options(strategies)
    strategies.set_defaults(handler=cmd_retrieval)

    pool_cmd = commands.add_parser(
        "pool",
        help="pool every run's top ranked sources per claim into a judgement file (new pages only)",
    )
    pool_cmd.add_argument("--run", required=True, action="append", help="a run directory; repeat per variant")
    pool_cmd.add_argument("--judgements", required=True, help="the JSONL judgement file, created or extended")
    pool_cmd.add_argument("--depth", type=int, default=pooling.DEPTH, help="how many ranked sources per claim")
    pool_cmd.set_defaults(handler=cmd_pool)

    judge_cmd = commands.add_parser("judge", help="judge the pooled pages, one at a time, in this terminal")
    judge_cmd.add_argument("--judgements", required=True, help="the JSONL judgement file")
    judge_cmd.set_defaults(handler=cmd_judge)

    pooled_cmd = commands.add_parser(
        "pooled",
        help="score runs on the same pooled judgements, each paired against the first",
    )
    pooled_cmd.add_argument("--run", required=True, action="append", help="a run directory; the first is the baseline")
    pooled_cmd.add_argument("--judgements", required=True, help="the JSONL judgement file")
    pooled_cmd.add_argument("--depth", type=int, default=pooling.DEPTH, help="how many ranked sources per claim")
    _report_options(pooled_cmd)
    pooled_cmd.set_defaults(handler=cmd_pooled)

    fresh = commands.add_parser(
        "freshness",
        help="the newest evidence's age at each claim, from the set; with runs, verdicts by that "
        "age and by the claim's age when checked",
    )
    fresh.add_argument("--dataset", required=True, help="a JSONL file, or a directory of one-fact JSON files")
    fresh.add_argument("--split", help="only the rows of this split")
    fresh.add_argument("--run", action="append", help="a run over the set; repeat for several")
    _report_options(fresh)
    fresh.set_defaults(handler=cmd_freshness)

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

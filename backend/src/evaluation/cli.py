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
    uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split train --replay <run dir> \
        --thresholds <verifier.json> --label <strategy>

    uv run python -m src.evaluation.cli run --dataset <set> --retrieval-only --label <strategy>
    uv run python -m src.evaluation.cli retrieval --run <dir> --run <dir> ...

    uv run python -m src.evaluation.cli pool --run A --run B ... --judgements data/evaluation/judgements/<set>.jsonl
    uv run python -m src.evaluation.cli judge --judgements data/evaluation/judgements/<set>.jsonl
    uv run python -m src.evaluation.cli pooled --run A --run B ... --judgements data/evaluation/judgements/<set>.jsonl

    uv run python -m src.evaluation.cli freshness --dataset data/evaluation/manual [--split test] [--run <dir> ...]

    uv run python -m src.evaluation.cli iterate init --name <campaign> --evidence <searched train run> [--goal ...]
    uv run python -m src.evaluation.cli iterate propose --campaign <c> --kind <k> --hypothesis ... --predict ...
    uv run python -m src.evaluation.cli iterate score --campaign <c> --try N --run <dir>
    uv run python -m src.evaluation.cli iterate status --campaign <c>
    uv run python -m src.evaluation.cli iterate close --campaign <c> --reason ...

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
from src.evaluation.dataset import AVERITEC, SAMPLES, load_dataset, only_ids, select_rows
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
    NONE,
    ORACLE,
    REPLAY,
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

    if args.ids:
        dataset = only_ids(dataset, args.ids.split(","))

    is_averitec = all(row.dataset == AVERITEC for row in dataset.rows)

    # The corpus is this project's own articles from 2026: nothing there
    # predates a 2020 claim, and it has no place in a benchmark.
    if is_averitec and args.corpus == SNAPSHOT:
        raise SystemExit("an AVeriTeC run takes no corpus: leave --corpus out, or --corpus none")

    corpus = args.corpus or (NONE if is_averitec else SNAPSHOT)

    if args.knowledge_store:

        if not is_averitec:
            raise SystemExit("--knowledge-store is AVeriTeC's, and this dataset is not")

        if args.oracle or args.closed_book or args.replay or args.loop:
            raise SystemExit("--knowledge-store takes none of --oracle, --closed-book, --replay or --loop")

    if args.oracle and (args.retrieval_only or args.loop):
        # The loop already ends on the annotator's pages, and retrieval-only
        # asks no model: neither means anything over evidence given in.
        raise SystemExit("--oracle takes neither --retrieval-only nor --loop")

    if args.closed_book and (args.retrieval_only or args.oracle or args.loop):
        # Three evidence conditions, one per run; the loop needs evidence.
        raise SystemExit("--closed-book takes none of --retrieval-only, --oracle or --loop")

    if args.replay and (args.retrieval_only or args.oracle or args.closed_book or args.loop):
        # A replay is the searched evidence of another run; the loop's
        # second look would search again.
        raise SystemExit("--replay takes none of --retrieval-only, --oracle, --closed-book or --loop")

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
        corpus=corpus,
        root=Path(args.root) if args.root else default_runs_root(),
        mode=(
            RETRIEVAL if args.retrieval_only
            else ORACLE if args.oracle
            else CLOSED_BOOK if args.closed_book
            else REPLAY if args.replay
            else FULL
        ),
        # The search is part of what a run measures, so the store has its own key.
        label=args.label or ("knowledge-store" if args.knowledge_store else None),
        loop=args.loop,
        replay_of=Path(args.replay) if args.replay else None,
        knowledge_store=Path(args.knowledge_store) if args.knowledge_store else None,
        search_cache=Path(args.search_cache) if args.search_cache else None,
    )

    if config.search_cache is not None and not args.label:
        raise SystemExit("--search-cache needs a --label: a run on recorded answers is not a run on the web")

    if config.knowledge_store is not None and config.thresholds.second_look_enabled:
        raise SystemExit("a second look searches again, and the knowledge store cannot be searched without a claim")

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


def cmd_averitec_import(args: argparse.Namespace) -> int:

    from src.evaluation import averitec

    target = Path(args.out or f"data/evaluation/averitec/averitec_{args.split}.jsonl")

    provenance = averitec.import_split(Path(args.raw), args.split, target)

    print(json.dumps({"written": str(target), **{k: v for k, v in provenance.items() if k != "excluded"},
                      "excluded": len(provenance["excluded"])}, indent=2))

    return 0


def cmd_averitec_audit(args: argparse.Namespace) -> int:

    from src.evaluation.knowledge_store import KnowledgeStore, audit
    from src.evaluation.runner import store_indexes

    dataset = load_dataset(args.dataset)

    claims = [
        {
            "index": int(row.id.rsplit("-", 1)[1]),
            "id": row.id,
            "claimDate": row.claim_date,
            "factCheckUrl": row.fact_check_url,
        }
        for row in dataset.rows
    ]

    result = audit(KnowledgeStore(Path(args.store)), claims)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({key: value for key, value in result.items() if key not in ("late", "factChecks")}, indent=2))

    return 0


def cmd_averitec_qa_score(args: argparse.Namespace) -> int:

    from src.evaluation import averitec_score
    from src.evaluation.report import load_run

    run = load_run(args.run)
    result = averitec_score.evaluate(run.records, averitec_score.load_gold(Path(args.gold)))

    out = Path(args.out) if args.out else run.directory / "averitec_score.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n".join(averitec_score.render(result)))
    print(f"Per claim: {out}")

    return 0


def cmd_averitec_submission(args: argparse.Namespace) -> int:

    from src.evaluation import averitec
    from src.evaluation.report import load_run

    run = load_run(args.run)

    Path(args.out).write_text(
        json.dumps(averitec.submission(run.records), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"{len(run.records)} claims in {args.out}")

    return 0


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


# ----------------------------------------------------------------------
# iterate: the agent's loop over the fact-checker (iterate.py)
# ----------------------------------------------------------------------


def cmd_iterate_init(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.init_campaign(
        args.name, args.evidence, model=args.model, thresholds_path=args.thresholds, tries=args.tries,
        screen=args.screen, target_median=args.target_median, target_p90=args.target_p90, goal=args.goal or "",
        root=Path(args.root) if args.root else None,
    )

    print(f"Campaign {campaign.name} started in {campaign.directory}")
    print(f"Rule: {campaign.directory / iterate.RULE}")
    print("Next: the baseline, try 0 -")
    print(f"  uv run python -m src.evaluation.cli iterate propose --campaign {campaign.name} --kind baseline "
          "--hypothesis 'the defaults, replayed' --predict 'what the campaign is compared with'")

    return 0


def cmd_iterate_propose(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    entry = iterate.propose(
        campaign, kind=args.kind, hypothesis=args.hypothesis, prediction=args.predict,
        thresholds_path=args.thresholds, model=args.model, provider=args.provider, again=args.again,
    )

    print(json.dumps({key: entry[key] for key in ("try", "label", "kind", "mode", "searchSide", "model", "provider", "thresholdsOverridden")}, indent=2))
    print("\nRun, from backend/ (in the background: a claim takes about a minute):\n")
    print("\n\n".join(iterate.commands(campaign, entry)))
    print(f"\nThen: uv run python -m src.evaluation.cli iterate score --campaign {campaign.name} --try {entry['try']} --run <the run directory it printed>")

    return 0


def cmd_iterate_score(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    decision = iterate.score(campaign, args.try_number, args.run)

    print(json.dumps(decision, indent=2, ensure_ascii=False))

    return 0


def cmd_iterate_searched_baseline(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    print(json.dumps(iterate.register_searched_baseline(campaign, args.run), indent=2))

    return 0


def cmd_iterate_status(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    state = iterate.status(campaign)

    print(json.dumps(state, indent=2, ensure_ascii=False) if args.json else iterate.render_status(state))

    return 0


def cmd_iterate_abandon(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    print(json.dumps(iterate.abandon(campaign, args.try_number, args.reason), indent=2))

    return 0


def cmd_iterate_benchmark(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    target = iterate.write_benchmark(campaign, Path(args.prices) if args.prices else None)

    print(target.read_text(encoding="utf-8"))

    return 0


def cmd_iterate_close(args: argparse.Namespace) -> int:

    from src.evaluation import iterate

    campaign = iterate.load_campaign(args.campaign, Path(args.root) if args.root else None)

    target = iterate.close(campaign, args.reason)

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
    run.add_argument("--ids", help="only these comma-separated claim ids, of the split chosen (a troubleshooting batch); their own run directory")
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
    run.add_argument("--corpus", choices=CORPUS_MODES, help="default: snapshot, or none for AVeriTeC")
    run.add_argument(
        "--knowledge-store",
        metavar="ZIP",
        help="AVeriTeC only: search the official knowledge store instead of the live web "
        "(src/evaluation/knowledge_store.py); take data/evaluation/thresholds/averitec_store.json",
    )
    run.add_argument(
        "--search-cache",
        metavar="FILE",
        help="answer a query asked before from FILE, and add new answers to it "
        "(src/evaluation/search_cache.py): to compare two plans on train by what they asked; needs --label",
    )
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
        "--replay",
        metavar="RUN_DIR",
        help="no search: each claim's candidates as RUN_DIR's retrieval found them (its "
        "evidence.jsonl); ranking, the model and the scorer run again, so two verifiers "
        "are compared on the same sources. Keyed by RUN_DIR's key",
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

    benchmark = commands.add_parser("averitec", help="the AVeriTeC benchmark's data")
    benchmark_commands = benchmark.add_subparsers(dest="averitec_command", required=True)

    importing = benchmark_commands.add_parser("import", help="the official JSON as the harness's rows")
    importing.add_argument("--raw", required=True, help="the official file (dev.json, train.json)")
    importing.add_argument("--split", required=True, choices=("dev", "train"))
    importing.add_argument("--out", help="default: data/evaluation/averitec/averitec_<split>.jsonl")
    importing.set_defaults(handler=cmd_averitec_import)

    auditing = benchmark_commands.add_parser(
        "audit-store",
        help="what the knowledge store holds that breaks the temporal rule, per claim",
    )
    auditing.add_argument("--store", required=True, help="the store's zip")
    auditing.add_argument("--dataset", required=True, help="the imported rows")
    auditing.add_argument("--out", help="write the audit here as JSON")
    auditing.set_defaults(handler=cmd_averitec_audit)

    submitting = benchmark_commands.add_parser(
        "submission",
        help="a run's predictions in the shared task's format, for the official scorer",
    )
    submitting.add_argument("--run", required=True, help="the run directory")
    submitting.add_argument("--out", required=True)
    submitting.set_defaults(handler=cmd_averitec_submission)

    scoring = benchmark_commands.add_parser(
        "qa-score",
        help="a run's questions and answers against the annotators': Q-only, Q+A, AVeriTeC score",
    )
    scoring.add_argument("--run", required=True, help="the run directory")
    scoring.add_argument("--gold", default="data/evaluation/averitec/raw/dev.json", help="the official dev.json")
    scoring.add_argument("--out", help="default: <run>/averitec_score.json")
    scoring.set_defaults(handler=cmd_averitec_qa_score)

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

    iterate_ = commands.add_parser(
        "iterate",
        help="an agent's campaign of changes to the fact-checker, each decided by a fixed rule (iterate.py)",
    ).add_subparsers(dest="iterate_command", required=True)

    def campaign_arg(command):
        command.add_argument("--campaign", required=True, help="the campaign's name (or its directory)")
        command.add_argument("--root", help=argparse.SUPPRESS)

    it_init = iterate_.add_parser("init", help="start a campaign over a searched train run's evidence")
    it_init.add_argument("--name", required=True)
    it_init.add_argument("--evidence", required=True, help="a full run over the train half that kept evidence.jsonl")
    it_init.add_argument("--model", help="the verifier every try uses unless it says otherwise (default: the evidence run's)")
    it_init.add_argument("--thresholds", help="the baseline's thresholds file (default: the environment's defaults)")
    it_init.add_argument("--tries", type=int, default=15, help="the budget, the baseline not counted")
    it_init.add_argument("--screen", type=int, default=20, help="claims in the screen; 0 for none")
    it_init.add_argument("--target-median", type=float, default=20.0, help="seconds a claim, median")
    it_init.add_argument("--target-p90", type=float, default=30.0, help="seconds a claim, 90th percentile")
    it_init.add_argument("--goal", help="one line: what the campaign is for")
    it_init.add_argument("--root", help=argparse.SUPPRESS)
    it_init.set_defaults(handler=cmd_iterate_init)

    it_propose = iterate_.add_parser("propose", help="pre-register one try: hypothesis and prediction before the run")
    campaign_arg(it_propose)
    it_propose.add_argument("--kind", required=True, choices=["baseline", "thresholds", "prompt", "model", "code", "search"])
    it_propose.add_argument("--hypothesis", required=True, help="what is wrong and why this change should help")
    it_propose.add_argument("--predict", required=True, help="what it should do to the numbers, and to which claims")
    it_propose.add_argument("--thresholds", help="the try's thresholds file (overrides over the defaults)")
    it_propose.add_argument("--model", help="the verifier for this try (default: the campaign's)")
    it_propose.add_argument(
        "--provider", default="local", choices=["local", "groq"],
        help="where the verifier runs: local (this machine's Ollama) or a hosted endpoint, its key from backend/.env",
    )
    it_propose.add_argument("--again", action="store_true", help="allow a repeat of an earlier try's model, thresholds and commit")
    it_propose.set_defaults(handler=cmd_iterate_propose)

    it_score = iterate_.add_parser("score", help="decide a try by the rule (the screen, or every claim)")
    campaign_arg(it_score)
    it_score.add_argument("--try", dest="try_number", type=int, required=True)
    it_score.add_argument("--run", required=True, help="the try's run directory")
    it_score.set_defaults(handler=cmd_iterate_score)

    it_searched = iterate_.add_parser("searched-baseline", help="register one of the two searched baselines")
    campaign_arg(it_searched)
    it_searched.add_argument("--run", required=True)
    it_searched.set_defaults(handler=cmd_iterate_searched_baseline)

    it_status = iterate_.add_parser("status", help="every try, the best kept, and whether to stop")
    campaign_arg(it_status)
    it_status.add_argument("--json", action="store_true")
    it_status.set_defaults(handler=cmd_iterate_status)

    it_abandon = iterate_.add_parser("abandon", help="give up a pending try (it stays in the ledger)")
    campaign_arg(it_abandon)
    it_abandon.add_argument("--try", dest="try_number", type=int, required=True)
    it_abandon.add_argument("--reason", required=True)
    it_abandon.set_defaults(handler=cmd_iterate_abandon)

    it_bench = iterate_.add_parser("benchmark", help="every try side by side, self-hosted against hosted: benchmark.md")
    campaign_arg(it_bench)
    it_bench.add_argument("--prices", help="a prices file (default: data/evaluation/prices.json)")
    it_bench.set_defaults(handler=cmd_iterate_benchmark)

    it_close = iterate_.add_parser("close", help="end the campaign and write summary.md and benchmark.md")
    campaign_arg(it_close)
    it_close.add_argument("--reason", required=True)
    it_close.set_defaults(handler=cmd_iterate_close)

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

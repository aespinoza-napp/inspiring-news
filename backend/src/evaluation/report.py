"""
A run's results, turned into the numbers the paper quotes.

    uv run python -m src.evaluation.cli report --run <run dir> [--compare <run dir>]

writes `metrics.json`, `report.md` and a copy of `run.json` to
`data/evaluation/reports/<dataset-stem>/<model-slug>/<key>/`, which is
committed: the numbers next to the manifest that produced them. A report
reads only the results file and the manifest, so it can be re-made (and
a metric fixed) long after the model time was paid for.

    uv run python -m src.evaluation.cli table --run <dir> --run <dir> ...

puts several runs over one dataset side by side - the verification-model
comparison - in `reports/<dataset-stem>/models.md`.

docs/decisions/evaluation.md §What is reported apart, §Metrics.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.config.settings import settings
from src.evaluation import metrics
from src.evaluation.metrics import (
    CLASSES,
    DEFAULT_RESAMPLES,
    DEFAULT_SEED,
    LEVEL,
    OUTCOMES,
    SCORED,
)
from src.evaluation import retrieval
from src.evaluation.runner import FULL, MANIFEST, RESULTS, RETRIEVAL, model_slug
from src.evaluation.store import ResultsFile, read_json, write_json
from src.evaluation.usage import cost, price_for, totals

# What a breakdown is by, and which set it applies to. Site is x-fact's
# fact-checker; on the custom set it is just the article's publisher.
BREAKDOWNS = {
    "language": None,
    "topicGroup": "custom",
    "claimType": "custom",
    "sourceTier": "custom",
    "site": "xfact",
}


def default_reports_root() -> Path:

    return Path(settings.STORAGE_PATH) / "evaluation" / "reports"


@dataclass
class Run:

    directory: Path

    manifest: dict

    # The latest record per claim id, sorted by id: the bootstrap
    # resamples by position, so a stable order is what makes the same
    # run give the same interval however its claims finished.
    records: list[dict] = field(default_factory=list)

    @property
    def key(self) -> str:

        return self.manifest.get("key") or self.directory.name

    @property
    def model(self) -> str:

        return self.manifest.get("model") or "unknown"

    @property
    def dataset_stem(self) -> str:

        return (self.manifest.get("dataset") or {}).get("stem") or self.directory.parent.parent.name


def load_run(directory: str | Path) -> Run:

    directory = Path(directory)

    manifest_path = directory / MANIFEST

    if not manifest_path.exists():
        raise FileNotFoundError(f"{directory} has no {MANIFEST}: not a harness run")

    latest = ResultsFile(directory / RESULTS).latest(lambda record: record["id"])

    return Run(
        directory=directory,
        manifest=read_json(manifest_path),
        records=[latest[key] for key in sorted(latest)],
    )


def pairs_of(records: list[dict]) -> list[tuple[str, str]]:

    return [(record["label"], record["verdict"]) for record in records]


def scored_metrics(records: list[dict], *, seed: int, resamples: int) -> dict:

    pairs = pairs_of(records)

    return {
        **metrics.classification(pairs),
        "ci": metrics.bootstrap(pairs, seed=seed, resamples=resamples),
    }


def evaluate(
    run: Run,
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    prices: dict | None = None,
) -> dict:
    """The whole of metrics.json for one run."""

    records = run.records

    by_outcome: dict[str, list[dict]] = {name: [] for name in OUTCOMES}

    for record in records:
        by_outcome[metrics.outcome(record)].append(record)

    scored = by_outcome[SCORED]

    unflagged = [record for record in scored if not metrics.flagged(record)]

    rows = (run.manifest.get("dataset") or {}).get("rows")

    run_totals = totals(records)

    return {
        "run": {
            "key": run.key,
            "model": run.model,
            "provider": run.manifest.get("provider"),
            "dataset": run.manifest.get("dataset"),
            "harnessVersion": run.manifest.get("harnessVersion"),
            "thresholdsHash": run.manifest.get("thresholdsHash"),
            "thresholdsOverridden": run.manifest.get("thresholdsOverridden"),
            "corpus": run.manifest.get("corpus"),
            "mode": run.manifest.get("mode") or FULL,
            "label": run.manifest.get("label"),
            "gitCommits": sorted({record.get("gitCommit") or "unknown" for record in records}),
            "records": len(records),
            "notRun": max(0, rows - len(records)) if isinstance(rows, int) else None,
        },
        "bootstrap": {"seed": seed, "resamples": resamples, "level": LEVEL},
        "outcomes": {
            name: {
                "count": len(group),
                # Ids for everything set apart; the scored list is long
                # and is the rest by definition.
                "ids": [record["id"] for record in group] if name != SCORED else None,
            }
            for name, group in by_outcome.items()
        },
        "flags": _flags(scored),
        "metrics": {
            "scored": scored_metrics(scored, seed=seed, resamples=resamples),
            "scoredUnflagged": scored_metrics(unflagged, seed=seed, resamples=resamples),
        },
        "breakdowns": _breakdowns(scored, seed=seed, resamples=resamples),
        "retrieval": retrieval.retrieval_metrics(records, seed=seed, resamples=resamples),
        "usage": {
            **run_totals,
            "cost": cost(run_totals, price_for(prices, run.model, run.manifest.get("provider"))),
        },
    }


def _flags(scored: list[dict]) -> dict:

    temporal = {record["id"]: metrics.temporal_leak(record) for record in scored}
    verdict = {record["id"]: metrics.verdict_leak(record) for record in scored}

    newer = {record["id"]: metrics.newer_uncited(record) for record in scored}

    return {
        "temporalLeak": {
            "flagged": sorted(key for key, value in temporal.items() if value is True),
            "clear": sum(1 for value in temporal.values() if value is False),
            "undetermined": sum(1 for value in temporal.values() if value is None),
        },
        "verdictLeak": {
            "flagged": sorted(key for key, value in verdict.items() if value is True),
            "clear": sum(1 for value in verdict.values() if value is False),
            "notApplicable": sum(1 for value in verdict.values() if value is None),
        },
        "newerUncitedSources": {
            "sources": sum(newer.values()),
            "claims": sum(1 for value in newer.values() if value),
        },
        # A model failing the output format: scored (as the UNVERIFIED it
        # became), and counted, because it is a property of the model.
        "invalidOutput": sorted(record["id"] for record in scored if record.get("invalidOutput")),
    }


def _breakdowns(scored: list[dict], *, seed: int, resamples: int) -> dict:

    result = {}

    for dimension, only in BREAKDOWNS.items():

        groups: dict[str, list[dict]] = {}

        for record in scored:

            if only and record.get("dataset") != only:
                continue

            value = record.get(dimension)

            if value is None:
                continue

            groups.setdefault(str(value), []).append(record)

        if not groups:
            continue

        result[dimension] = {}

        for value in sorted(groups):

            group = scored_metrics(groups[value], seed=seed, resamples=resamples)

            result[dimension][value] = {
                key: group[key]
                for key in ("n", "accuracy", "macroF1", "coverage", "selectiveAccuracy", "kappa", "goldClasses", "ci")
            }

    return result


def compare(
    baseline: Run,
    candidate: Run,
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
) -> dict:
    """
    Candidate (B) against baseline (A), paired over the claims both scored.
    A claim set apart on either side is left out of both, and counted: a
    search outage on one side is not a model difference.
    """

    a = {record["id"]: record for record in baseline.records}
    b = {record["id"]: record for record in candidate.records}

    shared = sorted(set(a) & set(b))

    both_scored = [
        key for key in shared
        if metrics.outcome(a[key]) == SCORED and metrics.outcome(b[key]) == SCORED
    ]

    gold_differs = [key for key in both_scored if a[key]["label"] != b[key]["label"]]

    paired = [key for key in both_scored if key not in gold_differs]

    pairs_a = pairs_of([a[key] for key in paired])
    pairs_b = pairs_of([b[key] for key in paired])

    dataset_a = (baseline.manifest.get("dataset") or {}).get("sha256")
    dataset_b = (candidate.manifest.get("dataset") or {}).get("sha256")

    return {
        "baseline": {"key": baseline.key, "model": baseline.model,
                     "provider": baseline.manifest.get("provider"), "directory": str(baseline.directory)},
        "candidate": {"key": candidate.key, "model": candidate.model,
                      "provider": candidate.manifest.get("provider")},
        "sameDataset": dataset_a == dataset_b,
        "claims": {
            "paired": len(paired),
            "onlyInBaseline": len(set(a) - set(b)),
            "onlyInCandidate": len(set(b) - set(a)),
            "setApartOnEitherSide": len(shared) - len(both_scored),
            "goldDiffers": gold_differs,
        },
        "discordant": metrics.discordant(pairs_a, pairs_b),
        "difference": metrics.paired_bootstrap(pairs_a, pairs_b, seed=seed, resamples=resamples),
        "retrieval": retrieval.compare_retrieval(
            baseline.records, candidate.records, seed=seed, resamples=resamples,
        ),
    }


def report_directory(run: Run, root: Path | None = None) -> Path:

    return Path(root or default_reports_root()) / run.dataset_stem / model_slug(run.model) / run.key


def write_report(
    run_directory: str | Path,
    *,
    compare_with: str | Path | None = None,
    prices: dict | None = None,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    root: Path | None = None,
) -> Path:

    run = load_run(run_directory)

    result = evaluate(run, seed=seed, resamples=resamples, prices=prices)

    if compare_with:
        result["comparison"] = compare(load_run(compare_with), run, seed=seed, resamples=resamples)

    target = report_directory(run, root)

    target.mkdir(parents=True, exist_ok=True)

    write_json(target / "metrics.json", result)

    (target / "report.md").write_text(render(result), encoding="utf-8", newline="\n")

    shutil.copyfile(run.directory / MANIFEST, target / MANIFEST)

    return target


# ----------------------------------------------------------------------
# Several runs, one table
# ----------------------------------------------------------------------


def models_table(
    run_directories: list[str | Path],
    *,
    prices: dict | None = None,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    root: Path | None = None,
) -> Path:
    """
    One row per run over the same dataset: quality with its interval,
    then what it took. Refuses runs over different datasets - a table
    whose rows answered different questions is not a comparison.
    """

    runs = [load_run(directory) for directory in run_directories]

    datasets = {(run.manifest.get("dataset") or {}).get("sha256") for run in runs}

    if len(datasets) != 1:
        raise ValueError("every run in a table must be over the same dataset (sha256 differs)")

    retrieval_only = [str(run.directory) for run in runs if run.manifest.get("mode") == RETRIEVAL]

    if retrieval_only:
        raise ValueError(
            "retrieval-only runs have no verdicts to compare: use `cli retrieval` for them "
            f"({', '.join(retrieval_only)})"
        )

    rows = []

    for run in runs:

        result = evaluate(run, seed=seed, resamples=resamples, prices=prices)

        scored = result["metrics"]["scored"]

        rows.append({
            "model": run.model,
            "provider": run.manifest.get("provider"),
            "key": run.key,
            "records": result["run"]["records"],
            "outcomes": {name: value["count"] for name, value in result["outcomes"].items()},
            "invalidOutput": len(result["flags"]["invalidOutput"]),
            **{name: scored[name] for name in ("n", "accuracy", "macroF1", "coverage", "selectiveAccuracy", "kappa")},
            "ci": scored["ci"],
            "usage": result["usage"],
        })

    target = Path(root or default_reports_root()) / runs[0].dataset_stem

    target.mkdir(parents=True, exist_ok=True)

    table = {"dataset": runs[0].manifest.get("dataset"), "bootstrap": {"seed": seed, "resamples": resamples}, "runs": rows}

    write_json(target / "models.json", table)

    (target / "models.md").write_text(render_table(table), encoding="utf-8", newline="\n")

    return target


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def pct(value) -> str:

    return "n/a" if value is None else f"{value * 100:.1f}%"


def num(value, digits: int = 3) -> str:

    return "n/a" if value is None else f"{value:.{digits}f}"


# Rates read as percentages; F1 and kappa as the decimals they are
# usually quoted as.
DECIMAL = {"macroF1", "kappa"}


def formatter_for(name: str):

    return num if name in DECIMAL else pct


def with_ci(value, ci: dict | None, formatter=pct) -> str:

    if value is None:
        return "n/a"

    if not ci or ci.get("low") is None:
        return formatter(value)

    return f"{formatter(value)} [{formatter(ci['low'])}, {formatter(ci['high'])}]"


def _table(header: list[str], rows: list[list[str]]) -> str:

    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]

    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]

    return "\n".join(lines)


def _headline(block: dict) -> list[list[str]]:

    ci = block.get("ci") or {}

    return [
        ["Claims", str(block["n"])],
        ["Accuracy", with_ci(block["accuracy"], ci.get("accuracy"))],
        ["Macro-F1 (gold classes)", with_ci(block["macroF1"], ci.get("macroF1"), num)],
        ["Coverage (not UNVERIFIED)", with_ci(block["coverage"], ci.get("coverage"))],
        ["Selective accuracy", with_ci(block["selectiveAccuracy"], ci.get("selectiveAccuracy"))],
        ["Cohen's kappa vs gold", with_ci(block["kappa"], ci.get("kappa"), num)],
    ]


def render(result: dict) -> str:

    run = result["run"]
    boot = result["bootstrap"]
    scored = result["metrics"]["scored"]
    unflagged = result["metrics"]["scoredUnflagged"]
    outcomes = result["outcomes"]
    flags = result["flags"]

    dataset = run.get("dataset") or {}

    if run.get("mode") == RETRIEVAL:
        return _render_retrieval_only(result)

    parts = [
        f"# {dataset.get('stem', 'run')} · {run['model']}" + (f" · {run['label']}" if run.get("label") else ""),
        "",
        f"Run `{run['key']}` · provider `{run.get('provider')}` · harness v{run.get('harnessVersion')} · "
        f"thresholds `{run.get('thresholdsHash')}` · corpus `{(run.get('corpus') or {}).get('mode')}`"
        f" ({(run.get('corpus') or {}).get('points', 'n/a')} points)",
        "",
        f"Dataset sha256 `{(dataset.get('sha256') or '')[:12]}`, {dataset.get('rows')} rows; "
        f"{run['records']} run, {run.get('notRun')} not run. Commits: "
        + ", ".join(f"`{commit[:12]}`" for commit in run.get("gitCommits") or []),
        "",
        f"Intervals: percentile {int(boot['level'] * 100)}% bootstrap over claims, "
        f"{boot['resamples']} resamples, seed {boot['seed']}.",
        "",
        "## Headline",
        "",
        _table(["Scored claims", "All", "Without leak flags"], [
            [left[0], left[1], right[1]] for left, right in zip(_headline(scored), _headline(unflagged))
        ]),
        "",
        "## What was set apart",
        "",
        "Never in the error rate: each would measure an outage, not the pipeline.",
        "",
        _table(["Outcome", "Claims", "Ids"], [
            [name, value["count"], ", ".join(value["ids"]) if value["ids"] else ""]
            for name, value in outcomes.items()
        ]),
        "",
        _table(["Flag", "Flagged", "Clear", "Undetermined / n.a.", "Ids"], [
            ["temporalLeak (cited source newer than the claim)",
             len(flags["temporalLeak"]["flagged"]), flags["temporalLeak"]["clear"],
             flags["temporalLeak"]["undetermined"], ", ".join(flags["temporalLeak"]["flagged"])],
            ["verdictLeak (a ranked source is the fact-checker's own site)",
             len(flags["verdictLeak"]["flagged"]), flags["verdictLeak"]["clear"],
             flags["verdictLeak"]["notApplicable"], ", ".join(flags["verdictLeak"]["flagged"])],
        ]),
        "",
        f"Ranked but uncited sources newer than the claim: {flags['newerUncitedSources']['sources']} "
        f"over {flags['newerUncitedSources']['claims']} claims (counted, not flagged). "
        f"Invalid model output (scored as UNVERIFIED): {len(flags['invalidOutput'])}"
        + (f" ({', '.join(flags['invalidOutput'])})" if flags["invalidOutput"] else "") + ".",
        "",
        "## Per class (all scored claims)",
        "",
        _table(["Class", "Precision", "Recall", "F1", "Support", "Predicted"], [
            [label, pct(s["precision"]), pct(s["recall"]), num(s["f1"]), s["support"], s["predicted"]]
            for label, s in scored["perClass"].items()
        ]),
        "",
        f"Macro-F1 averages over the classes with gold support: {', '.join(scored['goldClasses']) or 'none'}.",
        "",
        "## Confusion matrix (gold rows, predicted columns)",
        "",
        _table(["gold \\ predicted", *CLASSES], [
            [gold, *(scored["confusion"][gold][label] for label in CLASSES)] for gold in CLASSES
        ]),
        "",
    ]

    for dimension, groups in result["breakdowns"].items():
        parts += [
            f"## By {dimension}",
            "",
            _table(["Value", "n", "Accuracy", "Macro-F1", "Coverage", "Selective acc."], [
                [value, g["n"], with_ci(g["accuracy"], (g.get("ci") or {}).get("accuracy")),
                 num(g["macroF1"]), pct(g["coverage"]), pct(g["selectiveAccuracy"])]
                for value, g in groups.items()
            ]),
            "",
        ]

    parts += retrieval.render_section(result["retrieval"])

    parts += _render_usage(result["usage"])

    if result.get("comparison"):
        parts += _render_comparison(result["comparison"])

    return "\n".join(parts).rstrip() + "\n"


def _render_retrieval_only(result: dict) -> str:
    """A retrieval-only run: no model was asked, so no verdict metric."""

    run = result["run"]
    dataset = run.get("dataset") or {}

    parts = [
        f"# {dataset.get('stem', 'run')} · retrieval only" + (f" · {run['label']}" if run.get("label") else ""),
        "",
        f"Run `{run['key']}` · harness v{run.get('harnessVersion')} · thresholds `{run.get('thresholdsHash')}` · "
        f"corpus `{(run.get('corpus') or {}).get('mode')}`. Commits: "
        + ", ".join(f"`{commit[:12]}`" for commit in run.get("gitCommits") or []),
        "",
        "No model was asked: every verdict is a placeholder, so this report has retrieval metrics only.",
        "",
        *retrieval.render_section(result["retrieval"]),
    ]

    if result.get("comparison"):
        parts += retrieval.render_comparison(
            result["comparison"]["retrieval"], result["comparison"]["baseline"]["key"], run["key"],
        )

    return "\n".join(parts).rstrip() + "\n"


def _render_usage(usage: dict) -> list[str]:

    priced = usage.get("cost")

    price = (
        f"{priced['total']:.4f} {priced['currency']} ({priced['per100Units']:.4f} per 100 claims;"
        f" price as of {priced.get('asOf')})"
        if priced else "n/a (no price given, or tokens unknown)"
    )

    return [
        "## Cost, latency and tokens",
        "",
        _table(["", "Value"], [
            ["LLM calls (failed)", f"{usage['llmCalls']} ({usage['failedCalls']})"],
            ["Claims the model was not asked about", usage["unitsWithoutCalls"]],
            ["Prompt / completion tokens", f"{usage['promptTokens']} / {usage['completionTokens']}"],
            ["Tokens per claim asked (prompt / completion)",
             f"{usage['promptTokensPerUnit']} / {usage['completionTokensPerUnit']}"],
            ["Calls with no usage reported", usage["usageMissing"]],
            ["LLM call latency, median / p90 / max (s)",
             f"{num(usage['callLatency']['median'])} / {num(usage['callLatency']['p90'])} / {num(usage['callLatency']['max'])}"],
            ["Claim latency, median / p90 (s)",
             f"{num(usage['unitLatency']['median'])} / {num(usage['unitLatency']['p90'])}"],
            ["Completion tokens per second", num(usage["completionTokensPerSecond"], 1)],
            ["Cost", price],
        ]),
        "",
    ]


def _render_comparison(comparison: dict) -> list[str]:

    claims = comparison["claims"]

    rows = []

    def signed(value, name):
        if name in DECIMAL:
            return f"{value:+.3f}"
        return f"{value * 100:+.1f} pts"

    for name, d in comparison["difference"].items():
        formatter = formatter_for(name)
        rows.append([
            name, formatter(d["a"]), formatter(d["b"]),
            "n/a" if d["difference"] is None else signed(d["difference"], name),
            "n/a" if d["low"] is None else f"[{signed(d['low'], name)}, {signed(d['high'], name)}]",
        ])

    return [
        "## Paired comparison",
        "",
        f"Baseline A: `{comparison['baseline']['model']}` (`{comparison['baseline']['key']}`, "
        f"{comparison['baseline']['provider']}); candidate B: this run. Paired over the "
        f"{claims['paired']} claims both scored; {claims['setApartOnEitherSide']} set apart on either "
        f"side, {claims['onlyInBaseline']} only in A, {claims['onlyInCandidate']} only in B"
        + ("" if comparison["sameDataset"] else "; **the two runs used different dataset files**")
        + ".",
        "",
        _table(["Statistic", "A", "B", "B − A", "95% CI of B − A"], rows),
        "",
        f"Only A right: {comparison['discordant']['onlyA']}; only B right: {comparison['discordant']['onlyB']}. "
        "An interval that excludes 0 is a difference the resampling cannot explain away.",
        "",
        *retrieval.render_comparison(comparison["retrieval"], "A", "B"),
    ]


def render_table(table: dict) -> str:

    dataset = table.get("dataset") or {}

    rows = []

    for row in table["runs"]:

        ci = row.get("ci") or {}
        usage = row["usage"]
        priced = usage.get("cost")

        rows.append([
            f"`{row['model']}`", row.get("provider"), row["n"],
            with_ci(row["accuracy"], ci.get("accuracy")),
            with_ci(row["macroF1"], ci.get("macroF1"), num),
            pct(row["coverage"]), pct(row["selectiveAccuracy"]), num(row["kappa"]),
            row["invalidOutput"],
            row["outcomes"].get("llmUnreachable", 0) + row["outcomes"].get("searchUnavailable", 0)
            + row["outcomes"].get("error", 0),
            num(usage["unitLatency"]["median"], 1),
            usage["completionTokensPerUnit"],
            num(usage["completionTokensPerSecond"], 1),
            f"{priced['per100Units']:.4f}" if priced else "n/a",
        ])

    return "\n".join([
        f"# {dataset.get('stem', 'dataset')}: models compared",
        "",
        f"Dataset sha256 `{(dataset.get('sha256') or '')[:12]}`, {dataset.get('rows')} rows. "
        f"Bootstrap seed {table['bootstrap']['seed']}, {table['bootstrap']['resamples']} resamples. "
        "Pairwise differences: `cli report --run B --compare A`.",
        "",
        _table([
            "Model", "Provider", "Scored", "Accuracy", "Macro-F1", "Coverage", "Selective acc.",
            "Kappa", "Invalid output", "Set apart", "Median s/claim", "Completion tok/claim",
            "Tok/s", "Cost per 100 claims",
        ], rows),
        "",
    ])


# ----------------------------------------------------------------------
# Retrieval strategies, one table
# ----------------------------------------------------------------------


def _strategy(run: Run) -> dict:
    """What a run's retrieval was: everything that can differ between two strategies."""

    manifest = run.manifest

    return {
        "label": manifest.get("label"),
        "mode": manifest.get("mode") or FULL,
        "model": run.model,
        "key": run.key,
        "thresholdsOverridden": manifest.get("thresholdsOverridden") or {},
        "corpus": (manifest.get("corpus") or {}).get("mode"),
        "gitCommit": manifest.get("gitCommit"),
        "duckduckgoFallback": (manifest.get("settings") or {}).get("DUCKDUCKGO_FALLBACK_ENABLED"),
        "directory": str(run.directory),
    }


def retrieval_table(
    run_directories: list[str | Path],
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    root: Path | None = None,
) -> Path:
    """
    Retrieval strategies over one dataset, side by side, and each later
    one paired against the first: `reports/<dataset-stem>/retrieval.md`
    and `.json`. Full and retrieval-only runs mix freely - only what was
    retrieved is compared.
    """

    runs = [load_run(directory) for directory in run_directories]

    datasets = {(run.manifest.get("dataset") or {}).get("sha256") for run in runs}

    if len(datasets) != 1:
        raise ValueError("every run in a table must be over the same dataset (sha256 differs)")

    baseline = runs[0]

    rows = []

    for run in runs:

        row = {
            "strategy": _strategy(run),
            "metrics": retrieval.retrieval_metrics(run.records, seed=seed, resamples=resamples),
        }

        if run is not baseline:
            row["vsBaseline"] = retrieval.compare_retrieval(
                baseline.records, run.records, seed=seed, resamples=resamples,
            )

        rows.append(row)

    table = {
        "dataset": baseline.manifest.get("dataset"),
        "bootstrap": {"seed": seed, "resamples": resamples},
        "runs": rows,
    }

    target = Path(root or default_reports_root()) / baseline.dataset_stem

    target.mkdir(parents=True, exist_ok=True)

    write_json(target / "retrieval.json", table)

    (target / "retrieval.md").write_text(render_retrieval_table(table), encoding="utf-8", newline="\n")

    return target


# The columns of the side-by-side table: the reference metrics first,
# then what any set can say.
RETRIEVAL_COLUMNS = (
    "linkRecall@candidates",
    "linkRecall@ranked",
    "domainRecall@ranked",
    "domainMRR",
    "hasEvidence",
    "ranked",
    "gateCut",
    "uniqueDomains",
    "ratedShare",
    "retrievalSeconds",
)


def _strategy_name(strategy: dict) -> str:

    return strategy["label"] or f"{strategy['model']} {strategy['key']}"


def render_retrieval_table(table: dict) -> str:

    dataset = table.get("dataset") or {}

    rows = []

    for row in table["runs"]:

        metrics_ = row["metrics"]
        blocks = {**metrics_["gold"], **metrics_["goldFree"]}

        rows.append([
            f"`{_strategy_name(row['strategy'])}`",
            metrics_["claims"]["searched"],
            *(retrieval.with_interval(name, blocks[name]) for name in RETRIEVAL_COLUMNS),
        ])

    strategies = []

    for row in table["runs"]:

        s = row["strategy"]

        changed = ", ".join(f"{name}={value}" for name, value in sorted(s["thresholdsOverridden"].items())) or "defaults"

        strategies.append(
            f"- `{_strategy_name(s)}`: {s['mode']} run, thresholds {changed}, corpus {s['corpus']}, "
            f"DuckDuckGo fallback {s['duckduckgoFallback']}, commit `{(s['gitCommit'] or 'unknown')[:12]}`."
        )

    parts = [
        f"# {dataset.get('stem', 'dataset')}: retrieval strategies compared",
        "",
        f"Dataset sha256 `{(dataset.get('sha256') or '')[:12]}`, {dataset.get('rows')} rows. "
        f"Bootstrap seed {table['bootstrap']['seed']}, {table['bootstrap']['resamples']} resamples. "
        "The first run is the baseline. docs/decisions/evaluation.md §Retrieval evaluation.",
        "",
        *strategies,
        "",
        _table(["Strategy", "Searched", *(retrieval.LABELS[name] for name in RETRIEVAL_COLUMNS)], rows),
        "",
    ]

    baseline = _strategy_name(table["runs"][0]["strategy"])

    for row in table["runs"][1:]:
        parts += retrieval.render_comparison(row["vsBaseline"], baseline, _strategy_name(row["strategy"]))

    return "\n".join(parts).rstrip() + "\n"

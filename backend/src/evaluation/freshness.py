"""
How new is too new: the evidence against the age of the claim (roadmap,
Thesis priorities P1.2).

    uv run python -m src.evaluation.cli freshness --dataset data/evaluation/manual \
        [--split train|test] [--run <dir> ...]

writes `reports/<dataset-stem>/freshness.md` and `.json`. Two ages, both
in whole days:

**The newest evidence's age at the claim** (`claimDate - evidenceDate`),
from the set alone. `evidenceDate` is the newest evidence the annotator
used, never after the claim (labeller Rule 3). Zero means the claim
rested on something published that day - often only the organisation's
own release, Rule 1's case - so a search on day 0 has at most one page
to find; a gap of years means the claim restates an old fact, which the
web has had time to cover. The roadmap first called this "the gap to the
earliest evidence"; the field records the newest, and the newest is the
one that says whether the evidence existed yet.

**The claim's age when a run checked it** (the record's `startedAt` -
`claimDate`), from each `--run`: the axis FreshQA (Vu et al. 2024) and
RealTime QA (Kasai et al. 2023) vary. The planned day 0 / 7 / 30
re-runs vary it on purpose; until then, the runs already made spread
over it by themselves, since facts were labelled on different days.

Per age bucket and per run: scored claims, accuracy with its bootstrap
interval, the share with any ranked evidence, and the share answered
UNVERIFIED - the evidence rate against age. A claim set apart
(search unavailable, LLM unreachable, error) is counted and left out,
as everywhere in the harness.

Synthetic FALSE claims (`mutatedFrom`) are left out of the set's
distribution: each copies its source's dates, so it would count one
article twice. They stay in the runs' tables, where the verdict, not the
date, is what is measured.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from src.evaluation import metrics
from src.evaluation.dataset import Dataset, DatasetRow
from src.evaluation.metrics import DEFAULT_RESAMPLES, DEFAULT_SEED, SCORED, outcome
from src.evaluation.stats import median, percentile, rounded

# Upper bounds in days, inclusive, and their names. The last has none.
BUCKETS = (
    (0, "same day"),
    (7, "1-7 days"),
    (30, "8-30 days"),
    (365, "31-365 days"),
    (None, "over a year"),
)

NAMES = tuple(name for _, name in BUCKETS)

MUTATED = "mutated"

# How each dimension of the set's distribution is read off a row.
DIMENSIONS = {
    "language": lambda row: row.language,
    "claimType": lambda row: row.claim_type,
    "sourceTier": lambda row: row.source_tier,
    "label": lambda row: row.label,
}


def _day(value) -> date | None:

    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def days_between(later, earlier) -> int | None:
    """Whole days from `earlier` to `later`, or None when either is missing."""

    a, b = _day(later), _day(earlier)

    return None if a is None or b is None else (a - b).days


def bucket(days: int | None) -> str | None:

    if days is None or days < 0:
        return None

    return next(name for limit, name in BUCKETS if limit is None or days <= limit)


def evidence_age(row: DatasetRow) -> int | None:
    """Days from the newest evidence the annotator used to the claim."""

    return days_between(row.claim_date, row.evidence_date)


# ----------------------------------------------------------------------
# The set
# ----------------------------------------------------------------------


def _distribution(values: list[int]) -> dict:

    counts = Counter(bucket(value) for value in values)

    return {
        "n": len(values),
        "median": rounded(median(values), 1),
        "p25": rounded(percentile(values, 25), 1),
        "p75": rounded(percentile(values, 75), 1),
        "buckets": {
            name: {"count": counts.get(name, 0), "share": rounded(counts.get(name, 0) / len(values)) if values else None}
            for name in NAMES
        },
    }


def set_freshness(rows: tuple[DatasetRow, ...]) -> dict:
    """The newest evidence's age at the claim, over the set's natural claims."""

    natural = [row for row in rows if row.origin != MUTATED]

    dated = [(row, evidence_age(row)) for row in natural]

    usable = [(row, days) for row, days in dated if days is not None and days >= 0]

    return {
        "rows": len(rows),
        "mutatedLeftOut": len(rows) - len(natural),
        "undated": [row.id for row, days in dated if days is None],
        # Rule 3 refuses these in the labeller; a hand-edited file could
        # still hold one, and it is listed rather than counted.
        "evidenceAfterClaim": [row.id for row, days in dated if days is not None and days < 0],
        "all": _distribution([days for _, days in usable]),
        "by": {
            dimension: {
                value: _distribution([days for row, days in usable if read(row) == value])
                for value in sorted({read(row) for row, _ in usable if read(row)})
            }
            for dimension, read in DIMENSIONS.items()
        },
        "sameDayIds": [row.id for row, days in usable if days == 0],
    }


# ----------------------------------------------------------------------
# Runs
# ----------------------------------------------------------------------


def _verdict_block(records: list[dict], *, seed: int, resamples: int) -> dict:

    if not records:
        return {"n": 0}

    pairs = [(record["label"], record["verdict"]) for record in records]

    result = metrics.classification(pairs)
    ci = metrics.bootstrap(pairs, seed=seed, resamples=resamples).get("accuracy") or {}

    return {
        "n": len(records),
        "accuracy": rounded(result["accuracy"]),
        "accuracyLow": rounded(ci.get("low")),
        "accuracyHigh": rounded(ci.get("high")),
        "withEvidence": rounded(sum(1 for record in records if record.get("evidence")) / len(records)),
        "unverified": rounded(sum(1 for record in records if record.get("verdict") == "UNVERIFIED") / len(records)),
    }


def run_freshness(
    records: list[dict],
    rows: tuple[DatasetRow, ...],
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
) -> dict:
    """One run's verdicts by both ages. Rows give the evidence date; records the rest."""

    by_id = {row.id: row for row in rows}

    joined = [record for record in records if record.get("id") in by_id]

    scored = [record for record in joined if outcome(record) == SCORED]

    def by_age(age_of) -> dict:

        groups: dict[str, list[dict]] = {name: [] for name in NAMES}
        undated = 0

        for record in scored:
            name = bucket(age_of(record))
            if name is None:
                undated += 1
            else:
                groups[name].append(record)

        return {
            "undated": undated,
            "buckets": {name: _verdict_block(group, seed=seed, resamples=resamples) for name, group in groups.items()},
        }

    claim_ages = [days_between(record.get("startedAt"), record.get("claimDate")) for record in scored]
    claim_ages = [days for days in claim_ages if days is not None and days >= 0]

    return {
        "records": len(records),
        "notInDataset": len(records) - len(joined),
        "setApart": len(joined) - len(scored),
        "scored": len(scored),
        "claimAgeAtRun": {
            "median": rounded(median(claim_ages), 1),
            "min": min(claim_ages) if claim_ages else None,
            "max": max(claim_ages) if claim_ages else None,
            **by_age(lambda record: days_between(record.get("startedAt"), record.get("claimDate"))),
        },
        "evidenceAge": by_age(lambda record: evidence_age(by_id[record["id"]])),
    }


def freshness(
    dataset: Dataset,
    runs: list | None = None,
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
) -> dict:
    """freshness.json: the set, then each run (report.Run) joined to it."""

    return {
        "dataset": {"path": str(dataset.path), "stem": dataset.stem, "sha256": dataset.sha256},
        "set": set_freshness(dataset.rows),
        "runs": [
            {
                "directory": str(run.directory),
                "key": run.key,
                "model": run.model,
                "label": run.manifest.get("label"),
                "thresholdsOverridden": run.manifest.get("thresholdsOverridden"),
                **run_freshness(run.records, dataset.rows, seed=seed, resamples=resamples),
            }
            for run in runs or []
        ],
        "bootstrap": {"seed": seed, "resamples": resamples},
    }


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def _pct(value) -> str:

    return "n/a" if value is None else f"{value * 100:.1f}%"


def _distribution_row(name: str, block: dict) -> str:

    cells = [f"{b['count']} ({_pct(b['share'])})" for b in block["buckets"].values()]

    return f"| {name} | {block['n']} | {block['median']} | " + " | ".join(cells) + " |"


def _age_table(title: str, block: dict) -> list[str]:

    lines = [
        f"| {title} | Scored | Accuracy [95% CI] | Any evidence | UNVERIFIED |",
        "|---|---|---|---|---|",
    ]

    for name, b in block["buckets"].items():

        if not b["n"]:
            lines.append(f"| {name} | 0 | | | |")
            continue

        lines.append(
            f"| {name} | {b['n']} | {_pct(b['accuracy'])} [{_pct(b['accuracyLow'])}, {_pct(b['accuracyHigh'])}] "
            f"| {_pct(b['withEvidence'])} | {_pct(b['unverified'])} |"
        )

    return lines + ["", f"Undated: {block['undated']}.", ""]


def render(result: dict) -> str:

    data = result["set"]
    everything = data["all"]

    lines = [
        f"# {result['dataset']['stem']} · freshness",
        "",
        "How old the newest evidence the annotator used was when the claim was published "
        "(`claimDate - evidenceDate`, days), and how each run did by that age and by the claim's own age "
        "when it was checked. src/evaluation/freshness.py; roadmap P1.2.",
        "",
        "## The set",
        "",
        f"{everything['n']} natural claims dated on both sides, of {data['rows']} rows: "
        f"{data['mutatedLeftOut']} synthetic FALSE left out (they copy their source's dates), "
        f"{len(data['undated'])} without an evidence date"
        + (f" ({', '.join(data['undated'])})" if data["undated"] else "")
        + (f", {len(data['evidenceAfterClaim'])} with evidence after the claim ({', '.join(data['evidenceAfterClaim'])})"
           if data["evidenceAfterClaim"] else "")
        + f". Median {everything['median']} days (IQR {everything['p25']}-{everything['p75']}).",
        "",
        "| | n | Median days | " + " | ".join(NAMES) + " |",
        "|---|---|---|" + "---|" * len(NAMES),
        _distribution_row("All", everything),
    ]

    for dimension, groups in data["by"].items():
        for value, block in groups.items():
            lines.append(_distribution_row(f"{dimension}: {value}", block))

    lines += [
        "",
        f"Same day ({len(data['sameDayIds'])}): " + (", ".join(data["sameDayIds"]) or "none") + ".",
        "",
    ]

    for run in result["runs"]:

        age = run["claimAgeAtRun"]

        lines += [
            f"## Run `{run['key']}` · {run['model']}" + (f" · {run['label']}" if run.get("label") else ""),
            "",
            f"{run['scored']} scored claims joined to the set ({run['setApart']} set apart, "
            f"{run['notInDataset']} not in it). The claim's age when checked: median {age['median']} days, "
            f"{age['min']}-{age['max']}.",
            "",
            *_age_table("Claim's age when checked", age),
            *_age_table("Newest evidence's age at the claim", run["evidenceAge"]),
        ]

    return "\n".join(lines).rstrip() + "\n"


def write_freshness(result: dict, root: Path) -> Path:

    from src.evaluation.store import write_json

    target = root / result["dataset"]["stem"]
    target.mkdir(parents=True, exist_ok=True)

    write_json(target / "freshness.json", result)
    (target / "freshness.md").write_text(render(result), encoding="utf-8")

    return target

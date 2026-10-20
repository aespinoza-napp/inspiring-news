"""
Journalist effort, the harness's half (RQ4; docs/decisions/evaluation.md
§Journalist effort): what a journalist who trusted the run would gain,
and what it would cost them.

    uv run python -m src.evaluation.cli report --run <dir> [--minutes-per-fact 7.5]

Over the scored claims:

- **usable without re-checking**: the verdict is gold, is not
  UNVERIFIED, cites at least one source that takes a stance (supports or
  contradicts), and carries neither leak flag. A verdict that is right
  but rests on nothing cited still has to be checked by hand.
- **confidently wrong**: a definitive verdict (anything but UNVERIFIED)
  that is not gold - what that journalist would publish.
- **effort estimate**, only when the time a person takes per fact is
  given (`--minutes-per-fact`, the median `python labeller/app.py stats`
  prints): minutes saved per 100 claims, usable share x minutes x 100,
  beside the confidently wrong claims per 100 as its price. An estimate
  with stated assumptions, not a measurement: a usable verdict still
  takes a glance, and a confidently wrong one costs more than the fact
  it replaced once it is published.

The labeller owns the other two numbers (claim selector's precision and
time per fact) because they need no run; the report owns these because
they need the results. Claims set apart are never counted.
"""

from __future__ import annotations

from src.evaluation.metrics import SCORED, flagged, outcome
from src.evaluation.stats import bootstrap_mean, rounded

UNVERIFIED = "UNVERIFIED"

STANCES = ("supports", "contradicts")


def cites_a_stance(record: dict) -> bool:

    return any(item.get("cited") and item.get("stance") in STANCES for item in record.get("evidence") or [])


def usable(record: dict) -> bool:

    return (
        record.get("verdict") == record.get("label")
        and record.get("verdict") != UNVERIFIED
        and cites_a_stance(record)
        and not flagged(record)
    )


def confidently_wrong(record: dict) -> bool:

    return record.get("verdict") != UNVERIFIED and record.get("verdict") != record.get("label")


def _share(records: list[dict], test, *, seed: int, resamples: int) -> dict:

    values = [1.0 if test(record) else 0.0 for record in records]

    interval = bootstrap_mean(values, seed=seed, resamples=resamples)

    return {
        "count": int(sum(values)),
        "share": rounded(sum(values) / len(values)) if values else None,
        "low": rounded(interval["low"]),
        "high": rounded(interval["high"]),
        "ids": [record["id"] for record, value in zip(records, values) if value],
    }


def effort_metrics(
    records: list[dict],
    *,
    seed: int,
    resamples: int,
    minutes_per_fact: float | None = None,
) -> dict:
    """The effort section of a report, for one run's records."""

    scored = [record for record in records if outcome(record) == SCORED]

    result = {
        "scored": len(scored),
        "usable": _share(scored, usable, seed=seed, resamples=resamples),
        "confidentlyWrong": _share(scored, confidently_wrong, seed=seed, resamples=resamples),
        # Right, but nothing cited took a stance: a person must still look.
        "rightButUnsupported": sum(
            1 for record in scored
            if record.get("verdict") == record.get("label") and record.get("verdict") != UNVERIFIED
            and not cites_a_stance(record)
        ),
        "minutesPerFact": minutes_per_fact,
        "estimate": None,
    }

    if minutes_per_fact is not None and scored:

        usable_share = result["usable"]["count"] / len(scored)
        wrong_share = result["confidentlyWrong"]["count"] / len(scored)

        result["estimate"] = {
            "minutesSavedPer100": rounded(usable_share * minutes_per_fact * 100, 1),
            "minutesSavedPer100Low": rounded((result["usable"]["low"] or 0) * minutes_per_fact * 100, 1),
            "minutesSavedPer100High": rounded((result["usable"]["high"] or 0) * minutes_per_fact * 100, 1),
            "confidentlyWrongPer100": rounded(wrong_share * 100, 1),
        }

    return result


def _pct(block: dict) -> str:

    if block["share"] is None:
        return "n/a"

    return f"{block['share'] * 100:.1f}% [{block['low'] * 100:.1f}, {block['high'] * 100:.1f}]"


def render_section(section: dict) -> list[str]:
    """The `## Journalist effort` part of report.md."""

    lines = [
        "## Journalist effort",
        "",
        f"Over {section['scored']} scored claims (docs/decisions/evaluation.md §Journalist effort).",
        "",
        "| | Claims | Share [95% CI] |",
        "|---|---|---|",
        f"| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) "
        f"| {section['usable']['count']} | {_pct(section['usable'])} |",
        f"| Confidently wrong (definitive, not gold) | {section['confidentlyWrong']['count']} "
        f"| {_pct(section['confidentlyWrong'])} |",
        "",
        f"Right and definitive but citing no source with a stance: {section['rightButUnsupported']} "
        "(not usable: a person must still look).",
        "",
    ]

    estimate = section.get("estimate")

    if estimate:
        lines += [
            f"**Estimate**, at {section['minutesPerFact']} minutes a fact by hand: "
            f"{estimate['minutesSavedPer100']} minutes saved per 100 claims "
            f"[{estimate['minutesSavedPer100Low']}, {estimate['minutesSavedPer100High']}], "
            f"against {estimate['confidentlyWrongPer100']} confidently wrong verdicts per 100. "
            "An estimate: a usable verdict still takes a glance, and a wrong one costs more once published.",
            "",
        ]
    else:
        lines += [
            "No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.",
            "",
        ]

    return lines

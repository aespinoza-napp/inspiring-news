"""
Stage attribution: for every wrong verdict, the stage that made it.

    uv run python -m src.evaluation.cli report --run <dir>     # a "Stage attribution" section

Each scored claim whose verdict differs from gold gets one stage, from
fields every harness record already holds (`candidates`, `evidence`,
`rawVerdict`, `referenceEvidenceLinks`) - no new pipeline output. It is
computed twice, because the annotator's references are the better
witness but not every row has them (an `UNVERIFIED` gold label needs
none, and x-fact lost every PolitiFact row's):

    stage        reference-based                         trace only
    aggregation  rawVerdict equals gold; the final verdict does not (same rule)
    retrieval    no reference link or domain among       no candidates at all
                 the candidates
    ranking      a reference among the candidates,       candidates, nothing ranked
                 none ranked
    reasoning    a reference ranked, rawVerdict wrong    something ranked, rawVerdict wrong

Aggregation is tested first, not last as docs/decisions/evaluation.md
§Stage attribution first listed it: when the model's own verdict matched
gold, no stage before it caused the error, however little it was shown -
ConfidenceScorer changed a right answer (evidence floor, nothing cited,
only unrelated sources cited, a contradiction). The pilot's provisional
numbers (scripts/xfact_time_elapsed.py) were computed the same way.

Under the reference rule a wrong verdict resting on sources other than
the annotator's counts as retrieval: the decisive source was never
found. So the two columns can disagree, and both are true - the trace
says the model misread what it was shown, the references that it was
never shown the annotator's sources. The claims they disagree on are
listed.

Claims set apart (`searchUnavailable`, `llmUnreachable`, `error`) are
never attributed: an outage is not a stage. An oracle run (the
annotator's pages given directly, no search) has no reference column:
its candidates are the references by construction.
"""

from __future__ import annotations

from collections import Counter

from src.evaluation.metrics import SCORED, outcome
from src.evaluation.retrieval import RANKED, _domain, _sources, references
from src.services.fact_checker.retrieval.evidence_retriever import _comparable

RETRIEVAL = "retrieval"
RANKING = "ranking"
REASONING = "reasoning"
AGGREGATION = "aggregation"

STAGES = (RETRIEVAL, RANKING, REASONING, AGGREGATION)

# A row with no usable reference link: the reference rule cannot judge it.
NO_REFERENCE = None


# ----------------------------------------------------------------------
# One claim
# ----------------------------------------------------------------------


def wrong(record: dict) -> bool:
    """Scored, and the verdict is not gold."""

    return outcome(record) == SCORED and record.get("verdict") != record.get("label")


def _cut(candidates: list[dict]) -> list[str]:
    """Why each candidate that never reached the ranked list was cut."""

    return [
        f"{item.get('stoppedAt')}: {item.get('reason') or 'no reason given'}"
        for item in candidates
        if item.get("stoppedAt") != RANKED
    ]


def by_trace(record: dict) -> str:
    """The trace-only column: what the claim's own record shows."""

    if record.get("rawVerdict") == record.get("label"):
        return AGGREGATION

    sources = _sources(record)

    if not sources["candidates"]:
        return RETRIEVAL

    if not sources["ranked"]:
        return RANKING

    return REASONING


def by_reference(record: dict) -> str | None:
    """
    The reference-based column, or None when the row has no reference
    link to judge by (placeholders only, or only the fact-checker's own
    verdict page). A link or its domain counts, as in retrieval.py: the
    annotator's source, or another page of the same site.
    """

    links, domains, _ = references(record)

    if not links:
        return NO_REFERENCE

    if record.get("rawVerdict") == record.get("label"):
        return AGGREGATION

    sources = _sources(record)

    def hit(item: dict) -> bool:
        return _comparable(item.get("url") or "") in links or _domain(item) in domains

    if not any(hit(item) for item in sources["candidates"]):
        return RETRIEVAL

    if not any(hit(item) for item in sources["ranked"]):
        return RANKING

    return REASONING


def claim_attribution(record: dict, *, oracle: bool = False) -> dict:
    """Both columns for one wrong verdict, with the cut reasons ranking needs."""

    sources = _sources(record)

    reference = NO_REFERENCE if oracle else by_reference(record)

    links, domains, _ = references(record)

    return {
        "id": record.get("id"),
        "language": record.get("language"),
        "label": record.get("label"),
        "verdict": record.get("verdict"),
        "rawVerdict": record.get("rawVerdict"),
        "trace": by_trace(record),
        "reference": reference,
        # Ranking's evidence: every cut for the trace column, only the
        # references' for the reference column.
        "cutTrace": _cut(sources["candidates"]),
        "cutReference": _cut([
            item for item in sources["candidates"]
            if _comparable(item.get("url") or "") in links or _domain(item) in domains
        ]),
    }


# ----------------------------------------------------------------------
# A run
# ----------------------------------------------------------------------


def _column(claims: list[dict], key: str, cut_key: str) -> dict:

    judged = [claim for claim in claims if claim[key] is not NO_REFERENCE]

    counts = Counter(claim[key] for claim in judged)

    return {
        "judged": len(judged),
        "stages": {
            stage: {
                "count": counts.get(stage, 0),
                "share": (counts.get(stage, 0) / len(judged)) if judged else None,
                "ids": [claim["id"] for claim in judged if claim[key] == stage],
            }
            for stage in STAGES
        },
        "rankingCuts": dict(Counter(
            reason
            for claim in judged if claim[key] == RANKING
            for reason in claim[cut_key]
        ).most_common()),
    }


def attribution_metrics(records: list[dict], *, oracle: bool = False) -> dict:
    """The stage attribution section of a report, for one run's records."""

    claims = [claim_attribution(record, oracle=oracle) for record in records if wrong(record)]

    both = [claim for claim in claims if claim["reference"] is not NO_REFERENCE]

    return {
        "wrong": len(claims),
        "oracle": oracle,
        "trace": _column(claims, "trace", "cutTrace"),
        "reference": _column(claims, "reference", "cutReference"),
        "noReference": [claim["id"] for claim in claims if claim["reference"] is NO_REFERENCE],
        "bothJudged": len(both),
        "disagreements": [
            {"id": claim["id"], "trace": claim["trace"], "reference": claim["reference"]}
            for claim in both if claim["trace"] != claim["reference"]
        ],
        "byLanguage": {
            language: dict(Counter(claim["trace"] for claim in claims if claim["language"] == language))
            for language in sorted({claim["language"] for claim in claims if claim["language"]})
        },
    }


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def _share(value) -> str:

    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_section(section: dict) -> list[str]:
    """The `## Stage attribution` part of report.md."""

    lines = [
        "## Stage attribution",
        "",
        f"{section['wrong']} wrong verdict(s) among the scored claims, each given the stage that made it "
        "(docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was "
        "gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.",
        "",
    ]

    if not section["wrong"]:
        return lines

    trace, reference = section["trace"], section["reference"]

    header = ["Stage", f"Trace only (n={trace['judged']})"]

    if not section["oracle"]:
        header.append(f"By reference (n={reference['judged']})")

    lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]

    for stage in STAGES:

        row = [stage, f"{trace['stages'][stage]['count']} ({_share(trace['stages'][stage]['share'])})"]

        if not section["oracle"]:
            row.append(f"{reference['stages'][stage]['count']} ({_share(reference['stages'][stage]['share'])})")

        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    columns = [("Trace only", trace)] + ([] if section["oracle"] else [("By reference", reference)])

    for name, column in columns:

        named = [
            f"{stage} ({', '.join(column['stages'][stage]['ids'])})"
            for stage in STAGES if column["stages"][stage]["ids"]
        ]

        lines.append(f"{name}: " + "; ".join(named) + ".")
        lines.append("")

        if column["rankingCuts"]:
            lines += [
                f"{name}, why sources were cut on the claims attributed to ranking:",
                "",
                *(f"- {reason}: {count}" for reason, count in column["rankingCuts"].items()),
                "",
            ]

    if section["oracle"]:
        lines += [
            "No reference column: an oracle run's evidence is the annotator's own links, so "
            "\"found the reference\" holds by construction. Retrieval here means none of the "
            "claim's links could be read.",
            "",
        ]
        return lines

    if section["noReference"]:
        lines += [
            f"Without a reference link to judge by ({len(section['noReference'])}): "
            + ", ".join(section["noReference"]) + ".",
            "",
        ]

    disagreements = section["disagreements"]

    lines += [
        f"The two columns disagree on {len(disagreements)} of the {section['bothJudged']} claim(s) both can judge"
        + (":" if disagreements else "."),
        "",
    ]

    if disagreements:
        lines += [
            "| Claim | Trace only | By reference |",
            "|---|---|---|",
            *(f"| {d['id']} | {d['trace']} | {d['reference']} |" for d in disagreements),
            "",
        ]

    return lines

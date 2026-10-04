"""
One line of `results.jsonl`: everything a report needs about one claim.

The record copies the gold row and the pipeline's whole answer, so a
report (metrics.py, retrieval.py, attribution.py) reads nothing but the
results file and its manifest. That is what lets a report be re-run, and
a metric fixed, long after the model time was paid for.

No scraped body is stored: `Evidence.content` is left out, the rule
`progress.source_summary` follows for events. Titles, snippets and quotes
of third-party pages are, which is one of the reasons `runs/` is
gitignored.

docs/decisions/evaluation.md §Record format.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel

from src.evaluation.dataset import DatasetRow
from src.models.fact_checker.evidence import Evidence
from src.models.fact_checker.fact_check import FactCheck
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.fact_checker.retrieval.search_provider import registrable_domain
from src.services.fact_checker.verification.llm_verification import (
    INVALID_OUTPUT_EXPLANATION,
)

# Bump whenever a change to the harness alters what a run produces or how
# a record reads - the same discipline as AnalysisCache.SCHEMA_VERSION. It
# is part of the run key, so a bumped harness starts a new run instead of
# resuming an old one with records of two shapes.
HARNESS_VERSION = 1

OK = "ok"
ERROR = "error"

# The stage a source stopped at when it made the ranked list. A ranked
# source the model did not cite is still `ranked`: `evidence[i].cited`
# says so. FactCheck also lists it among `rejected_sources` (stage
# llm_verification); counting it there too would count it twice.
RANKED = "ranked"

# Every key a record has, in the order it is written. Error records have
# them all too, empty, so a report never has to ask whether a key exists.
RECORD_FIELDS = (
    # The gold row, copied.
    "id", "dataset", "language", "site", "claim", "claimDate", "label",
    "labelRaw", "referenceEvidenceLinks",
    "articleUrl", "topic", "topicGroup", "claimType", "sourceTier",
    # The outcome.
    "status", "error",
    "verdict", "rawVerdict", "confidence", "rawConfidence", "explanation",
    "invalidOutput",
    "reachedStage", "stageNote", "searchUnavailable", "llmUnreachable",
    # The trace.
    "queries", "candidates", "evidence",
    "citedIndices", "evidenceCount", "independentDomains",
    "events", "latency",
    # What it cost: the LLM calls this claim made (usage.py).
    "usage",
    # Provenance.
    "model", "provider", "thresholdsHash", "harnessVersion", "gitCommit",
    "startedAt", "finishedAt",
)


@dataclass(frozen=True)
class Provenance:
    """What produced a record. The same for every record of one session."""

    model: str

    # The LLM endpoint's host (LLM_BASE_URL without scheme, path or
    # credentials): `localhost:11434` for Ollama, `api.groq.com` for
    # Groq. The model name alone does not say who served it.
    provider: str

    thresholds_hash: str

    git_commit: str

    harness_version: int = HARNESS_VERSION


@dataclass(frozen=True)
class Timing:

    started_at: str

    finished_at: str

    # Seconds, wall clock, from before the claim was built to after the
    # check returned.
    total: float

    # Building the claim: the GLiNER pass ClaimService.build_claim makes.
    entities: float | None = None


def build_record(
    row: DatasetRow,
    check: FactCheck,
    *,
    events: list[dict],
    timing: Timing,
    provenance: Provenance,
    usage: dict,
) -> dict:

    cited = set(check.cited_evidence_indices)

    record = _row_fields(row)

    record.update({
        "status": OK,
        "error": None,
        "verdict": _value(check.verdict),
        "rawVerdict": _value(check.raw_verdict),
        "confidence": check.confidence,
        "rawConfidence": check.raw_confidence,
        "explanation": check.explanation,
        # The model answered, but nothing usable came back even after the
        # JSON retry. A format failure is a model-quality result, so it is
        # counted per model rather than lost inside UNVERIFIED.
        "invalidOutput": (
            not check.llm_unreachable
            and check.explanation == INVALID_OUTPUT_EXPLANATION
        ),
        "reachedStage": _value(check.reached_stage),
        "stageNote": check.stage_note,
        "searchUnavailable": check.search_unavailable,
        "llmUnreachable": check.llm_unreachable,
        "queries": queries_from(events),
        "candidates": candidates_from(check),
        "evidence": [
            _evidence(item, index in cited)
            for index, item in enumerate(check.evidence)
        ],
        "citedIndices": list(check.cited_evidence_indices),
        "evidenceCount": check.evidence_count,
        "independentDomains": check.independent_domains,
        "events": events,
        "latency": latency_from(events, timing),
        "usage": usage,
    })

    record.update(_provenance(provenance, timing))

    return _ordered(record)


def error_record(
    row: DatasetRow,
    exc: BaseException,
    *,
    events: list[dict],
    timing: Timing,
    provenance: Provenance,
    usage: dict,
) -> dict:
    """
    The harness or the pipeline crashed on this claim. Retried on the next
    run; any still left at report time are listed by id.
    """

    record = {field: None for field in RECORD_FIELDS}

    record.update(_row_fields(row))

    record.update({
        "status": ERROR,
        "error": f"{type(exc).__name__}: {exc}",
        "invalidOutput": False,
        "searchUnavailable": False,
        "llmUnreachable": False,
        "queries": queries_from(events),
        "candidates": [],
        "evidence": [],
        "citedIndices": [],
        "evidenceCount": 0,
        "independentDomains": 0,
        "events": events,
        "latency": latency_from(events, timing),
        "usage": usage,
    })

    record.update(_provenance(provenance, timing))

    return _ordered(record)


def _row_fields(row: DatasetRow) -> dict:

    return {
        "id": row.id,
        "dataset": row.dataset,
        "language": row.language,
        "site": row.site,
        "claim": row.claim,
        "claimDate": row.claim_date,
        "label": row.label,
        "labelRaw": row.label_raw,
        "referenceEvidenceLinks": list(row.reference_links),
        "articleUrl": row.article_url,
        "topic": row.topic,
        "topicGroup": row.topic_group,
        "claimType": row.claim_type,
        "sourceTier": row.source_tier,
    }


def _provenance(provenance: Provenance, timing: Timing) -> dict:

    return {
        "model": provenance.model,
        "provider": provenance.provider,
        "thresholdsHash": provenance.thresholds_hash,
        "harnessVersion": provenance.harness_version,
        "gitCommit": provenance.git_commit,
        "startedAt": timing.started_at,
        "finishedAt": timing.finished_at,
    }


def _ordered(record: dict) -> dict:

    return {field: record.get(field) for field in RECORD_FIELDS}


def queries_from(events: list[dict]) -> list[dict]:
    """
    What was sent to the search engine, and which question each query
    asks (anchor / proposition / refutation), from `searching_web` - the
    event announced before the search runs.
    """

    for event in events:

        if event["phase"] != "searching_web":
            continue

        data = event["data"]

        texts = data.get("queries") or []
        kinds = data.get("queryKinds") or []

        return [
            {"text": text, "kind": kinds[index] if index < len(kinds) else None}
            for index, text in enumerate(texts)
        ]

    return []


def candidates_from(check: FactCheck) -> list[dict]:
    """
    Every source seen, once: the ranked list, then everything retrieval
    and ranking cut, each with the stage it stopped at and why.
    """

    ranked = [
        {
            "url": item.url,
            "domain": _domain(item),
            "title": item.title,
            "origin": _value(item.origin),
            "stoppedAt": RANKED,
            "reason": None,
            "score": item.relevance_score,
        }
        for item in check.evidence
    ]

    cut = [
        {
            "url": item.url,
            # RejectedEvidence carries no domain; computed the way
            # Evidence.domain is, so the two compare.
            "domain": registrable_domain(item.url),
            "title": item.title,
            "origin": _value(item.origin),
            "stoppedAt": _value(item.stage),
            "reason": item.reason,
            "score": item.score,
        }
        for item in check.rejected_sources
        if item.stage != PipelineStage.LLM_VERIFICATION
    ]

    return ranked + cut


def _evidence(item: Evidence, cited: bool) -> dict:

    return {
        "url": item.url,
        "domain": _domain(item),
        "title": item.title,
        "origin": _value(item.origin),
        "publishedAt": item.published_at.isoformat() if item.published_at else None,
        "relevance": item.relevance_score,
        "semantic": item.semantic_score,
        "lexical": item.lexical_score,
        "recency": item.recency_score,
        "reliability": item.reliability_score,
        "reliabilityKnown": item.reliability_known,
        "pertinence": item.pertinence_score,
        "stance": _value(item.stance),
        "cited": cited,
        "quote": item.quote,
        "engines": list(item.engines),
        "foundBy": list(item.found_by),
    }


def _domain(item: Evidence) -> str:

    return item.domain or registrable_domain(item.url)


# Each stage's span, from the event that opens it to the one that closes
# it. The LLM span is absent when the model was not asked (below the
# evidence floor, no `verifying_claim`).
_SPANS = {
    "retrieval": ("retrieving_evidence", "evidence_retrieved"),
    "ranking": ("evidence_retrieved", "evidence_ranked"),
    "llm": ("verifying_claim", "claim_checked"),
}


def latency_from(events: list[dict], timing: Timing) -> dict:
    """
    Seconds per stage, from the events' own timestamps. `llm` includes
    waiting for the LLM permit; `usage.latency` is the provider's answer
    time alone. The gap between the two is a busy model, not a slow one.
    """

    first: dict[str, float] = {}

    for event in events:
        first.setdefault(event["phase"], event["t"])

    latency = {"total": round(timing.total, 4), "entities": timing.entities}

    for name, (opening, closing) in _SPANS.items():

        if opening in first and closing in first:
            latency[name] = round(first[closing] - first[opening], 4)
        else:
            latency[name] = None

    return latency


def jsonable(value):
    """
    Event data as JSON can hold it. Events carry enums (a verdict),
    datetimes and, from some stages, pydantic models.
    """

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")

    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))

    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]

    return value


def _value(value):

    if value is None:
        return None

    return value.value if isinstance(value, Enum) else value

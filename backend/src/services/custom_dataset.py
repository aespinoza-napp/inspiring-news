import hashlib
import math
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from src.config.topics import TOPICS
from src.models.evaluation.custom_fact import (
    LABEL_RAW,
    ClaimType,
    CustomFact,
    CustomFactInput,
    CustomFactReview,
    SourceTier,
)
from src.models.fact_checker.fact_check import Verdict
from src.repositories.custom_fact_repository import CustomFactRepository


# The five groups topics.py is already laid out in (its section comments).
# 23 topics across 150 facts is six or seven each, too thin to balance
# on; five groups by five verdicts is 25 cells of six. A test holds every
# TOPICS key to exactly one group, so a new topic cannot fall outside the
# balance table unnoticed.
TOPIC_GROUPS = {
    "society": ["education", "community", "employment", "cities"],
    "science": ["space", "technology", "research", "biology"],
    "environment": ["climate", "nature", "energy", "sustainability", "food"],
    "culture": ["arts", "entertainment", "heritage", "literature", "inspiration"],
    "health": ["medicine", "mental_health", "nutrition", "fitness", "public_health"],
}

GROUP_OF = {topic: group for group, topics in TOPIC_GROUPS.items() for topic in topics}

# The goal is 150 facts; 100 is the floor below which a per-cell count
# says nothing. Targets are what the balance table aims at, not a quota
# the form enforces - positive-news articles are mostly true, and a
# FALSE cell that stays short is reported as short, not padded.
TARGET_TOTAL = 150
MINIMUM_TOTAL = 100

# Share of the set labelled a second time, blind, to measure how
# consistently the guide is applied.
REVIEW_SHARE = 0.2

LABEL_DESCRIPTIONS = {
    Verdict.TRUE: "The evidence supports the claim as stated.",
    Verdict.PARTIALLY_TRUE: "The central claim holds; a detail does not.",
    Verdict.MISLEADING: "Evidence conflicts, or the claim is true but cherry-picked.",
    Verdict.FALSE: "The evidence refutes the claim.",
    Verdict.UNVERIFIED: "Not enough independent evidence, either way.",
}


class CustomDatasetService:

    def __init__(self, repository: CustomFactRepository):

        self.repository = repository

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create(self, data: CustomFactInput) -> CustomFact:

        fact = CustomFact.from_input(uuid4().hex[:12], data, _now())

        return self.repository.add(fact)

    def update(self, fact_id: str, data: CustomFactInput) -> CustomFact | None:

        existing = self.repository.get(fact_id)

        if existing is None:
            return None

        fact = CustomFact.from_input(fact_id, data, _now(), created_at=existing.createdAt)
        # A correction made after a review keeps the review: its
        # firstLabel is what self-agreement is measured on, so fixing the
        # label afterwards cannot inflate the agreement figure.
        fact.review = existing.review

        return self.repository.replace(fact)

    def delete(self, fact_id: str) -> bool:

        return self.repository.delete(fact_id)

    def review(self, fact_id: str, data: CustomFactReview) -> CustomFact | None:

        fact = self.repository.get(fact_id)

        if fact is None:
            return None

        first = (fact.review or {}).get("firstLabel", fact.label.value)

        fact.review = {
            "label": data.label.value,
            "firstLabel": first,
            "agrees": data.label.value == first,
            "note": data.note,
            "reviewedAt": _now(),
        }

        return self.repository.replace(fact)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def overview(self) -> dict:

        facts = self.repository.list()

        return {
            "facts": [f.model_dump(mode="json") for f in reversed(facts)],
            "summary": summarise(facts),
            "schema": schema(),
        }

    def review_queue(self) -> dict:

        facts = self.repository.list()
        sample = review_sample(facts)

        return {
            # Blind: whatever gives the first label away is left out.
            "sample": [_blinded(f) for f in sample],
            "sampleSize": len(sample),
            "agreement": agreement(facts),
        }


# ----------------------------------------------------------------------
# Pure functions - tested without a file
# ----------------------------------------------------------------------


def schema() -> dict:

    return {
        "labels": [
            {"label": v.value, "labelRaw": LABEL_RAW[v], "description": LABEL_DESCRIPTIONS[v]}
            for v in Verdict
        ],
        "topics": [
            {"id": key, "name": topic.name, "group": GROUP_OF[key]}
            for key, topic in TOPICS.items()
        ],
        "groups": list(TOPIC_GROUPS),
        "claimTypes": [c.value for c in ClaimType],
        "sourceTiers": [s.value for s in SourceTier],
        "targets": {
            "total": TARGET_TOTAL,
            "minimum": MINIMUM_TOTAL,
            "perLabel": TARGET_TOTAL // len(Verdict),
            "perGroup": TARGET_TOTAL // len(TOPIC_GROUPS),
            "perCell": TARGET_TOTAL // (len(Verdict) * len(TOPIC_GROUPS)),
            "reviewShare": REVIEW_SHARE,
        },
    }


def summarise(facts: list[CustomFact]) -> dict:

    cells: dict[str, dict[str, int]] = {
        v.value: {g: 0 for g in TOPIC_GROUPS} for v in Verdict
    }

    for fact in facts:
        cells[fact.label.value][GROUP_OF[fact.topic]] += 1

    return {
        "total": len(facts),
        "byLabel": _count(facts, lambda f: f.label.value, [v.value for v in Verdict]),
        "byGroup": _count(facts, lambda f: GROUP_OF[f.topic], list(TOPIC_GROUPS)),
        "byTopic": _count(facts, lambda f: f.topic, list(TOPICS)),
        "byLanguage": _count(facts, lambda f: f.language, ["en", "es"]),
        "byClaimType": _count(facts, lambda f: f.claimType.value, [c.value for c in ClaimType]),
        "matrix": cells,
    }


def review_sample(facts: list[CustomFact]) -> list[CustomFact]:
    """
    ceil(20%) of the set: every fact already reviewed, then the rest in
    the order of a hash of their id. Stable - the same fact stays in the
    sample however often the page is reloaded, and adding facts only
    adds to it - and not chosen by the annotator, which is the point.
    """

    if not facts:
        return []

    size = math.ceil(len(facts) * REVIEW_SHARE)
    reviewed = [f for f in facts if f.review]
    rest = sorted(
        (f for f in facts if not f.review),
        key=lambda f: hashlib.sha256(f.id.encode()).hexdigest(),
    )

    return reviewed + rest[: max(0, size - len(reviewed))]


def agreement(facts: list[CustomFact]) -> dict:
    """
    First label against the blind second one: observed agreement and
    Cohen's kappa, which discounts the agreement two labellings would
    reach by chance given how often each used every label.
    """

    pairs = [
        (f.review["firstLabel"], f.review["label"], f)
        for f in facts
        if f.review
    ]

    n = len(pairs)

    if not n:
        return {"reviewed": 0, "observed": None, "kappa": None, "disagreements": []}

    observed = sum(1 for a, b, _ in pairs if a == b) / n

    first = Counter(a for a, _, _ in pairs)
    second = Counter(b for _, b, _ in pairs)
    expected = sum(first[k] * second[k] for k in first) / (n * n)

    # Every pair on one and the same label: chance agreement is 1 and
    # kappa is undefined, not perfect.
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)

    return {
        "reviewed": n,
        "observed": round(observed, 4),
        "kappa": None if kappa is None else round(kappa, 4),
        "disagreements": [
            {"id": f.id, "claim": f.claim, "firstLabel": a, "secondLabel": b}
            for a, b, f in pairs
            if a != b
        ],
    }


def _blinded(fact: CustomFact) -> dict:

    row = fact.model_dump(mode="json")

    for key in ("label", "labelRaw", "annotatorNote", "onlyOwnSource"):
        row.pop(key, None)

    if row.get("review"):
        row["review"] = {"label": row["review"]["label"], "reviewedAt": row["review"]["reviewedAt"]}

    return row


def _count(facts, key, order) -> dict[str, int]:

    counts = Counter(key(f) for f in facts)

    return {k: counts.get(k, 0) for k in order}


def _now() -> str:

    # x-fact's reviewDate format: seconds, no zone.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

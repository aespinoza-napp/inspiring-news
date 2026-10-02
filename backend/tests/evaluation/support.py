"""
What the harness tests share. Not a test module (no `test_` prefix).

The pipeline under test is always the real FactChecker; only the network
clients behind it are the shared fakes from
tests/services/fact_checker/fakes.py. The one stand-in defined here is
the OpenAI SDK object LLMClient wraps - the third-party edge, as in
tests/services/test_llms.py - because usage metering hooks in exactly
there and FakeLLMClient (which replaces LLMClient whole) has nothing to
meter.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.claim_service import ClaimService
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerifier
from src.services.llms import LLMClient

from tests.services.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEntityExtractor,
    FakeEvidenceRetriever,
    FakeEvidenceScraper,
    FakeRanker,
    FakeSearchProvider,
    FakeSourceRepository,
    FakeVectorRetriever,
    FakeVerifier,
)

# ----------------------------------------------------------------------
# Datasets
# ----------------------------------------------------------------------


def xfact_row(claim: str, *, language: str = "en", label: str = "TRUE", **extra) -> dict:
    """An x-fact row: the ten keys, no id."""

    return {
        "language": language,
        "site": extra.pop("site", "politifact.com"),
        "claimant": "Someone",
        "claim": claim,
        "claimDate": extra.pop("claimDate", "none"),
        "reviewDate": "none",
        "labelRaw": extra.pop("labelRaw", "true"),
        "label": label,
        "referenceEvidenceLinks": extra.pop("referenceEvidenceLinks", ["https://ref.example/a"]),
        "split": "test",
        **extra,
    }


def custom_row(fact_id: str, claim: str, *, language: str = "es", label: str = "TRUE", **extra) -> dict:
    """A labeller fact: x-fact's ten keys, then the custom set's own."""

    row = xfact_row(
        claim,
        language=language,
        label=label,
        site=extra.pop("site", "lacarabuenadelmundo.com"),
        claimDate=extra.pop("claimDate", "2026-09-23"),
        labelRaw=extra.pop("labelRaw", "supported"),
    )

    row.update({
        "id": fact_id,
        "topic": extra.pop("topic", "energy"),
        "claimType": extra.pop("claimType", "numerical"),
        "sourceTier": extra.pop("sourceTier", "primary"),
        "onlyOwnSource": False,
        "evidenceDate": "2026-09-01",
        "articleUrl": extra.pop("articleUrl", f"https://lacarabuenadelmundo.com/{fact_id}"),
        "annotatorNote": "",
        "createdAt": "2026-09-29T10:00:00",
        "review": None,
    })

    row.update(extra)

    return row


def write_jsonl(path: Path, rows: list[dict]) -> Path:

    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    return path


# ----------------------------------------------------------------------
# The OpenAI SDK, as LLMClient sees it
# ----------------------------------------------------------------------


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Usage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _Completion:
    def __init__(self, content, usage):
        self.choices = [_Choice(content)]
        self.usage = usage


class _Completions:

    def __init__(self, sdk):
        self._sdk = sdk

    def create(self, **kwargs):
        return self._sdk.answer(kwargs)


class _Chat:
    def __init__(self, sdk):
        self.completions = _Completions(sdk)


class StubOpenAI:
    """
    Answers every chat completion with `content` (a dict is sent as
    JSON), reporting `usage` tokens - or no usage block at all when
    `usage=None`, as some OpenAI-shaped servers do. An Exception in
    `content` is raised instead.
    """

    def __init__(self, content, usage: tuple[int, int] | None = (120, 30)):
        self.content = content
        self.usage = usage
        self.calls: list[dict] = []
        self.chat = _Chat(self)

    def answer(self, kwargs):
        self.calls.append(kwargs)
        if isinstance(self.content, Exception):
            raise self.content
        content = self.content if isinstance(self.content, str) else json.dumps(self.content)
        usage = _Usage(*self.usage) if self.usage else None
        return _Completion(content, usage)


def stub_llm(content, usage: tuple[int, int] | None = (120, 30), model: str = "stub-model") -> LLMClient:

    return LLMClient(model=model, client=StubOpenAI(content, usage))


# ----------------------------------------------------------------------
# Pipelines
# ----------------------------------------------------------------------


def open_gate() -> PipelineThresholds:
    """
    Nothing cut by the pertinence gate: FakeEmbeddingService's vectors are
    hashes, so whether a source "addresses" the claim would be noise. A
    function, not a module constant: built at import, it would read
    `.env` before `pinned_settings` pins the defaults.
    """

    return PipelineThresholds(evidence_min_pertinence=0.0)


def recording_checker(repository, evidence_by_claim: dict | None = None) -> tuple[FactChecker, FakeEvidenceRetriever]:
    """
    A FactChecker whose retrieval records every call (claim, thresholds,
    context, language) - the cheapest witness of what the harness passed.
    """

    retriever = FakeEvidenceRetriever(evidence_by_claim or {})

    checker = FactChecker(
        repository,
        evidence_retriever=retriever,
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    return checker, retriever


def web_evidence() -> list[Evidence]:

    return [
        Evidence(
            url="https://www.ine.es/prensa/ecv2025.htm",
            title="Encuesta de condiciones de vida 2025",
            snippet="La tasa de riesgo de pobreza infantil fue del 28,9%.",
            origin=EvidenceOrigin.WEB,
            domain="ine.es",
            engines=["brave", "bing"],
            found_by=["anchor", "proposition"],
            published_at="2025-06-12T09:00:00",
        ),
        Evidence(
            url="https://www.eapn.es/estadopobreza/informe",
            title="El estado de la pobreza",
            snippet="Uno de cada tres niños vive en riesgo de pobreza o exclusión.",
            origin=EvidenceOrigin.WEB,
            domain="eapn.es",
            engines=["duckduckgo"],
            found_by=["anchor"],
            published_at="2025-10-02T09:00:00",
        ),
    ]


def full_checker(repository, llm: LLMClient) -> FactChecker:
    """
    The real retriever, ranker, verifier and scorer, over the shared
    network fakes and `llm` (a real LLMClient over StubOpenAI).
    """

    embeddings = FakeEmbeddingService()

    retriever = EvidenceRetriever(
        repository=None,
        search_provider=FakeSearchProvider(web_evidence()),
        scraper=FakeEvidenceScraper(),
        vector_retriever=FakeVectorRetriever([]),
        embeddings=embeddings,
    )

    return FactChecker(
        repository,
        evidence_retriever=retriever,
        ranker=EvidenceRanker(embeddings=embeddings, source_repository=FakeSourceRepository()),
        verifier=LLMVerifier(client=llm),
        confidence_scorer=ConfidenceScorer(),
    )


def claim_service(checker: FactChecker) -> ClaimService:

    return ClaimService(checker, entity_extractor=FakeEntityExtractor({"ORG": ["INE"]}))

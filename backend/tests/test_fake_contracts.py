"""
Every shared fake must accept what the real collaborator accepts.

A fake whose signature has drifted does not fail loudly - it fails as a
`TypeError` in whatever unrelated test happens to exercise that path
next, days after the change that caused it. Making thresholds per-call
drifted five fakes at once (`FakeSearchProvider.search`,
`FakeVectorRetriever.retrieve`, `FakeScraper.enrich`,
`FakeQualityAnalyzer.process`, `FakeEnrichmentService.enrich`), and each
was found one failing run at a time.

The check is deliberately one-directional: a fake must accept every
parameter the real method accepts, and may accept more. It says nothing
about return values - that is what the tests using the fake are for.
"""

from __future__ import annotations

import inspect

import pytest

from src.processors.nlp.entities import EntityExtractor
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.fact_checker.retrieval.search_provider import SearchProvider
from src.services.fact_checker.retrieval.vector_retriever import VectorRetriever
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerifier
from src.services.llms import LLMClient
from src.services.scraper.extractor import ExtractorService
from src.services.search import SearxngClient
from src.repositories.source_repository import SourceRepository

from tests.fact_checker import fakes

# (fake class, real class, method name)
CONTRACTS = [
    (fakes.FakeSearchProvider, SearchProvider, "search"),
    (fakes.FakeVectorRetriever, VectorRetriever, "retrieve"),
    (fakes.FakeEvidenceScraper, EvidenceScraper, "enrich"),
    (fakes.FakeEvidenceRetriever, EvidenceRetriever, "retrieve"),
    (fakes.FakeRanker, EvidenceRanker, "rank"),
    (fakes.FakeVerifier, LLMVerifier, "verify"),
    (fakes.FakeConfidenceScorer, ConfidenceScorer, "score"),
    (fakes.FakeExtractorService, ExtractorService, "extract"),
    (fakes.FakeSearxngClient, SearxngClient, "search"),
    (fakes.FakeLLMClient, LLMClient, "complete_json"),
    (fakes.FakeSourceRepository, SourceRepository, "list"),
    (fakes.FakeSourceRepository, SourceRepository, "get"),
    (fakes.FakeQualityAnalyzer, QualityAnalyzer, "process"),
    (fakes.FakeQualityAnalyzer, QualityAnalyzer, "readability"),
    (fakes.FakeSentimentAnalyzer, SentimentAnalyzer, "process"),
    (fakes.FakeEntityExtractor, EntityExtractor, "process"),
]


def parameters(cls, method: str) -> dict[str, inspect.Parameter]:
    """Named parameters of `cls.method`, excluding `self`."""

    signature = inspect.signature(getattr(cls, method))

    return {
        name: parameter
        for name, parameter in signature.parameters.items()
        if name != "self"
        and parameter.kind
        not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    }


@pytest.mark.parametrize(
    "fake, real, method",
    CONTRACTS,
    ids=[f"{f.__name__}.{m}" for f, _, m in CONTRACTS],
)
def test_the_fake_accepts_everything_the_real_method_accepts(fake, real, method):

    real_parameters = parameters(real, method)
    fake_parameters = parameters(fake, method)

    missing = sorted(set(real_parameters) - set(fake_parameters))

    assert missing == [], (
        f"{fake.__name__}.{method}() is missing {missing}, which "
        f"{real.__name__}.{method}() accepts. A caller passing them would "
        "raise TypeError in whatever test touches this path next."
    )


@pytest.mark.parametrize(
    "fake, real, method",
    CONTRACTS,
    ids=[f"{f.__name__}.{m}" for f, _, m in CONTRACTS],
)
def test_the_fake_keeps_the_real_parameter_order(fake, real, method):
    """
    Positional calls are common in this codebase
    (`ranker.rank(claim, evidence, thresholds)`), so matching names is
    not enough - the shared prefix has to line up too.
    """

    real_names = list(parameters(real, method))
    fake_names = list(parameters(fake, method))

    shared = [name for name in real_names if name in fake_names]

    assert [n for n in fake_names if n in shared][: len(shared)] == shared, (
        f"{fake.__name__}.{method}() orders its parameters differently "
        f"from {real.__name__}.{method}(); a positional call would bind "
        "the wrong argument."
    )


# Fakes with no real counterpart to check against, and why.
UNCONTRACTED = {
    # A hand-written stand-in for EmbeddingService whose whole point is
    # being deterministic and 8-dimensional; its contract is asserted by
    # the tests that use it, not by signature.
    "FakeEmbeddingService",
}


def test_every_shared_fake_is_covered_by_a_contract():
    """
    A fake added to fakes.py without an entry in CONTRACTS gets none of
    the protection above - which is exactly how the drifted ones got
    there. Adding it here is a deliberate decision, not an oversight.
    """

    defined = {
        name
        for name in vars(fakes)
        if name.startswith("Fake") and isinstance(getattr(fakes, name), type)
    }

    covered = {fake.__name__ for fake, _, _ in CONTRACTS} | UNCONTRACTED

    uncovered = sorted(defined - covered)

    assert uncovered == [], (
        "Add these to CONTRACTS, or to UNCONTRACTED with a reason: "
        f"{uncovered}"
    )

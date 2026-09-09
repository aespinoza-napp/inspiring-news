"""
Shared fakes for fact-checker tests. Not a test module itself (no
`test_` prefix), so pytest won't try to collect it.
"""

import hashlib

from src.services.fact_checker.ranking.ranking_retrieval import RankingResult
from src.services.fact_checker.retrieval.evidence_retriever import RetrievalResult


class FakeEmbeddingService:
    """
    Deterministic stand-in for EmbeddingService. Mirrors its exact
    contract: encode() returns a vector, similarity() is a raw dot
    product over two vectors (real EmbeddingService.encode() already
    normalizes, so vectors here are pre-normalized too).

    Pass `vectors={"some text": [...]}` to pin specific texts to
    specific vectors (e.g. to control duplicate/relatedness outcomes);
    unmapped text falls back to a deterministic hash-derived vector so
    unrelated strings behave as roughly unrelated.
    """

    DIM = 8

    def __init__(self, vectors: dict[str, list[float]] | None = None):
        self._vectors = vectors or {}

    def encode(self, text: str) -> list[float]:
        if text in self._vectors:
            return list(self._vectors[text])
        return self._hash_vector(text)

    def encode_many(self, texts):
        return [self.encode(text) for text in texts]

    def similarity(self, embedding1, embedding2) -> float:
        return float(sum(a * b for a, b in zip(embedding1, embedding2)))

    def _hash_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        raw = [b / 255.0 for b in digest[: self.DIM]]
        norm = sum(v * v for v in raw) ** 0.5 or 1.0
        return [v / norm for v in raw]


class FakeSearxngClient:

    def __init__(self, results: list[dict] | None = None):
        self.results = results or []
        self.queries: list[str] = []

    def search(self, query: str, max_results: int | None = None) -> list[dict]:
        self.queries.append(query)
        limit = max_results or len(self.results)
        return self.results[:limit]


class FakeExtractorService:
    """
    news_by_url maps a URL to whatever `extract()` should return
    (a News instance, or None to simulate an extraction failure).
    Any URL not in the map also returns None. Passing an Exception
    instance simulates a scraping error.
    """

    def __init__(self, news_by_url: dict | None = None):
        self.news_by_url = news_by_url or {}

    def extract(self, source, url, thresholds=None):
        result = self.news_by_url.get(url)
        if isinstance(result, Exception):
            raise result
        return result


class FakeLLMClient:
    """
    responses is a list of dicts (or None) consumed in order, one per
    complete_json() call - or a single dict/None reused for every call.
    """

    def __init__(self, responses=None):
        if isinstance(responses, list):
            self._responses = list(responses)
            self._single = None
        else:
            self._responses = None
            self._single = responses
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system_prompt: str, user_prompt: str, max_retries: int = 1):
        self.calls.append((system_prompt, user_prompt))
        if self._responses is not None:
            return self._responses.pop(0) if self._responses else None
        return self._single


class FakeSourceRepository:

    def __init__(self, sources: list | None = None):
        self._sources = sources or []

    def list(self):
        return self._sources

    def get(self, source_id: str):
        for source in self._sources:
            if source.id == source_id:
                return source
        return None


class FakeEvidenceRetriever:
    """Maps claim text -> canned evidence list, for orchestrator-level tests."""

    def __init__(self, evidence_by_claim: dict | None = None):
        self.evidence_by_claim = evidence_by_claim or {}

    def retrieve(self, claim, thresholds=None):
        return RetrievalResult(kept=self.evidence_by_claim.get(claim.text, []))


class FakeRanker:
    """Identity pass-through - orchestrator tests don't need real ranking."""

    def rank(self, claim, evidence, thresholds=None):
        return RankingResult(kept=evidence)


class FakeVerifier:
    """Maps claim text -> canned LLMVerificationResult, for orchestrator-level tests."""

    def __init__(self, result_by_claim: dict | None = None):
        self.result_by_claim = result_by_claim or {}

    def verify(self, claim, evidence):
        return self.result_by_claim[claim.text]


# ----------------------------------------------------------------------
# Retrieval collaborators
#
# These lived as private copies inside
# tests/fact_checker/retrieval/test_evidence_retriever.py. Every one of
# them drifted out of signature with the real collaborator when
# thresholds became per-call, and each was found only by a TypeError in
# an unrelated test run. They are shared now, and
# tests/test_fake_contracts.py pins their signatures to the real classes.
# ----------------------------------------------------------------------


class FakeSearchProvider:
    """Canned web evidence, ignoring the query."""

    def __init__(self, evidence=None):
        self.evidence = evidence or []
        self.calls = []

    def search(self, claim, thresholds=None):
        self.calls.append((claim, thresholds))
        return list(self.evidence)


class FakeVectorRetriever:
    """Canned internal-corpus evidence."""

    def __init__(self, evidence=None):
        self.evidence = evidence or []
        self.calls = []

    def retrieve(self, claim, limit: int = 5, thresholds=None):
        self.calls.append((claim, limit, thresholds))
        return list(self.evidence)


class FakeEvidenceScraper:
    """
    Stands in for EvidenceScraper: marks what it was asked to enrich so
    a test can assert *which* candidates were scraped, and stamps the
    content so the enrichment is visible in the result.
    """

    def __init__(self):
        self.enrich_calls = []

    def enrich(self, evidence):
        self.enrich_calls.append(evidence)
        return [
            item.model_copy(update={"content": f"scraped:{item.url}"})
            for item in evidence
        ]


class FakeConfidenceScorer:
    """Returns a canned FactCheck, for tests about orchestration only."""

    def __init__(self, check):
        self.check = check
        self.calls = []

    def score(self, claim, evidence, llm_result, thresholds=None):
        self.calls.append((claim, evidence, llm_result, thresholds))
        return self.check


# ----------------------------------------------------------------------
# Enrichment collaborators
# ----------------------------------------------------------------------


class FakeSentimentAnalyzer:

    def __init__(self, result):
        self.result = result

    def process(self, text: str):
        return self.result


class FakeQualityAnalyzer:

    def __init__(self, readability_score: float, quality_dict: dict):
        self.readability_score = readability_score
        self.quality_dict = quality_dict

    def readability(self, text: str, lexicon=None) -> float:
        return self.readability_score

    def process(
        self,
        text: str,
        *,
        sentiment=None,
        entities=None,
        novelty=None,
        language=None,
    ) -> dict:
        return dict(self.quality_dict)


class FakeEntityExtractor:

    def __init__(self, entities=None):
        self.entities = entities if entities is not None else {}
        self.calls = []

    def process(self, text, threshold=None):
        self.calls.append((text, threshold))
        return dict(self.entities)

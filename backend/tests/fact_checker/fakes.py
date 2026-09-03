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

    def extract(self, source, url):
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

    def retrieve(self, claim):
        return RetrievalResult(kept=self.evidence_by_claim.get(claim.text, []))


class FakeRanker:
    """Identity pass-through - orchestrator tests don't need real ranking."""

    def rank(self, claim, evidence):
        return RankingResult(kept=evidence)


class FakeVerifier:
    """Maps claim text -> canned LLMVerificationResult, for orchestrator-level tests."""

    def __init__(self, result_by_claim: dict | None = None):
        self.result_by_claim = result_by_claim or {}

    def verify(self, claim, evidence):
        return self.result_by_claim[claim.text]

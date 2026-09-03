from datetime import datetime, timedelta, timezone

from src.config.settings import settings
from src.models.core.source import NewsSource, SourceType
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker

from tests.factories import create_claim, create_evidence
from tests.fact_checker.fakes import FakeEmbeddingService, FakeSourceRepository


def test_rank_empty_evidence_returns_empty():

    ranker = EvidenceRanker(
        embeddings=FakeEmbeddingService(),
        source_repository=FakeSourceRepository([]),
    )

    result = ranker.rank(create_claim(), [])

    assert result.kept == []
    assert result.rejected == []


def test_rank_orders_by_semantic_similarity():

    claim = create_claim(text="claim text")

    high = create_evidence(url="https://a.com", content="claim text", published_at=None)
    low = create_evidence(url="https://b.com", content="something else entirely", published_at=None)

    embeddings = FakeEmbeddingService(vectors={
        "claim text": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "something else entirely": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    ranker = EvidenceRanker(embeddings=embeddings, source_repository=FakeSourceRepository([]))

    ranked = ranker.rank(claim, [low, high]).kept

    assert [item.url for item in ranked] == ["https://a.com", "https://b.com"]


def test_rank_prefers_more_recent_evidence():

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=1000)

    newer = create_evidence(url="https://new.com", content="same text", published_at=now)
    older = create_evidence(url="https://old.com", content="same text", published_at=old)

    embeddings = FakeEmbeddingService(vectors={
        "same text": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    ranker = EvidenceRanker(embeddings=embeddings, source_repository=FakeSourceRepository([]))

    ranked = ranker.rank(create_claim(), [older, newer]).kept

    assert [item.url for item in ranked] == ["https://new.com", "https://old.com"]


def test_rank_prefers_known_reliable_domain():

    known_source = NewsSource(
        id="known",
        name="Known",
        base_url="https://known.com",
        source_type=SourceType.NEWS,
        reliability_index=0.95,
    )

    known = create_evidence(url="https://known.com/article", content="same text", published_at=None)
    unknown = create_evidence(url="https://unknown.com/article", content="same text", published_at=None)

    embeddings = FakeEmbeddingService(vectors={
        "same text": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    ranker = EvidenceRanker(
        embeddings=embeddings,
        source_repository=FakeSourceRepository([known_source]),
    )

    ranked = ranker.rank(create_claim(), [unknown, known]).kept

    assert [item.url for item in ranked] == ["https://known.com/article", "https://unknown.com/article"]


def test_rank_truncates_to_max_evidence_per_claim(monkeypatch):

    monkeypatch.setattr(settings, "MAX_EVIDENCE_PER_CLAIM", 2)

    claim = create_claim(text="claim text")

    vectors = {"claim text": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
    evidence = []

    for i in range(4):
        content = f"content {i}"
        vectors[content] = [1.0 - i * 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        evidence.append(create_evidence(url=f"https://{i}.com", content=content, published_at=None))

    embeddings = FakeEmbeddingService(vectors=vectors)

    ranker = EvidenceRanker(embeddings=embeddings, source_repository=FakeSourceRepository([]))

    result = ranker.rank(claim, evidence)

    assert [item.url for item in result.kept] == ["https://0.com", "https://1.com"]
    assert [item.url for item in result.rejected] == ["https://2.com", "https://3.com"]
    assert all(item.stage == "evidence_ranking" for item in result.rejected)
    assert all(item.score is not None for item in result.rejected)

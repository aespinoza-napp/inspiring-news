from datetime import datetime, timedelta, timezone

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.source import NewsSource, SourceType
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker

from tests.factories import create_claim, create_evidence
from tests.services.fact_checker.fakes import FakeEmbeddingService, FakeSourceRepository

# The ordering tests below are about which source outranks which, and
# every one of them uses filler text ("same text", "content 3") that no
# claim's vocabulary appears in. Under the real default that is exactly
# what the pertinence gate exists to throw away, so these open the gate
# explicitly rather than leaving the tests at the mercy of a knob they
# are not about. The gate's own behaviour is tested at the bottom.
#
# A function, not a module constant: PipelineThresholds resolves every
# other field from settings when it is *constructed*, so one built at
# import time would freeze max_evidence_per_claim before a test had a
# chance to monkeypatch it - which is exactly what it did.
def no_gate(**overrides) -> PipelineThresholds:
    return PipelineThresholds(evidence_min_pertinence=0.0, **overrides)


def test_rank_empty_evidence_returns_empty():

    ranker = EvidenceRanker(
        embeddings=FakeEmbeddingService(),
        source_repository=FakeSourceRepository([]),
    )

    result = ranker.rank(create_claim(), [], no_gate())

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

    ranked = ranker.rank(claim, [low, high], no_gate()).kept

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

    ranked = ranker.rank(create_claim(), [older, newer], no_gate()).kept

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

    ranked = ranker.rank(create_claim(), [unknown, known], no_gate()).kept

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

    result = ranker.rank(claim, evidence, no_gate())

    assert [item.url for item in result.kept] == ["https://0.com", "https://1.com"]
    assert [item.url for item in result.rejected] == ["https://2.com", "https://3.com"]
    assert all(item.stage == "evidence_ranking" for item in result.rejected)
    assert all(item.score is not None for item in result.rejected)


def test_rank_says_whether_a_reliability_is_a_real_rating():
    """
    An unrated domain gets the default figure. Shown beside a real 0.95 it
    reads as a judgement on the source that nobody made, so the ranking
    says which is which.
    """

    known_source = NewsSource(
        id="known",
        name="Known",
        base_url="https://known.com",
        source_type=SourceType.NEWS,
        reliability_index=0.95,
    )

    ranker = EvidenceRanker(
        embeddings=FakeEmbeddingService(),
        source_repository=FakeSourceRepository([known_source]),
    )

    ranked = ranker.rank(
        create_claim(),
        [
            create_evidence(url="https://known.com/a", content="text", published_at=None),
            create_evidence(url="https://unknown.com/a", content="text", published_at=None),
        ],
        no_gate(),
    ).kept

    by_url = {item.url: item for item in ranked}

    assert by_url["https://known.com/a"].reliability_known is True
    assert by_url["https://known.com/a"].reliability_score == 0.95

    assert by_url["https://unknown.com/a"].reliability_known is False
    assert by_url["https://unknown.com/a"].reliability_score == settings.RANKING_DEFAULT_RELIABILITY


# ----------------------------------------------------------------------
# Lexical coverage and the pertinence gate
#
# Both exist because of one reproduced failure. A Spanish claim - the
# Coyote's mail-order ACME purchases standing for post-war American
# consumerism - retrieved three pages explaining that "acme" means "peak"
# in Greek. Every name in the claim appeared on them, so their embedding
# similarity was high, so they were the three best-ranked sources, so
# they were the three the model was shown. It returned FALSE at 83%.
#
# Nothing in the pipeline was in a position to notice: ranking can order
# sources but could not refuse one, and min_evidence_for_verdict counted
# them without asking what they were about.
# ----------------------------------------------------------------------


def _orthogonal_to(claim_text: str, evidence_text: str) -> FakeEmbeddingService:
    """
    An embedding service that says the claim and this source have nothing
    in common, so only lexical coverage can decide.

    Needed because FakeEmbeddingService's fallback vectors are derived
    from a hash and are therefore all non-negative - any two of them dot
    to something high, and a "semantically unrelated" source is not a
    thing the default fake can express.
    """

    return FakeEmbeddingService(vectors={
        claim_text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        evidence_text: [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })


def _coyote_claim():

    return create_claim(
        text=(
            "La obsesion del coyote por comprar los productos de ACME se "
            "tradujo en una representacion del consumismo de Estados Unidos."
        ),
        entities={"ORG": ["ACME"], "LOC": ["Estados Unidos"]},
    )


def test_a_source_about_the_subject_but_not_the_claim_is_cut():

    claim = _coyote_claim()

    # Names every entity, addresses nothing the claim asserts.
    etymology = create_evidence(
        url="https://example.com/acme",
        title="Que significa ACME",
        content=(
            "La palabra acme proviene del griego acme y significa el punto "
            "mas alto o culminacion de algo. ACME aparece en Estados Unidos."
        ),
        published_at=None,
    )

    ranker = EvidenceRanker(
        embeddings=_orthogonal_to(claim.text, etymology.content),
        source_repository=FakeSourceRepository([]),
    )

    result = ranker.rank(claim, [etymology])

    assert result.kept == []

    [rejected] = result.rejected
    assert rejected.url == "https://example.com/acme"
    assert rejected.stage == "evidence_ranking"
    assert "does not address the claim" in rejected.reason


def test_a_source_that_addresses_the_claim_survives_the_gate():

    claim = _coyote_claim()

    on_point = create_evidence(
        url="https://example.com/consumismo",
        title="El coyote y ACME",
        content=(
            "La obsesion del coyote por comprar productos de ACME se tradujo "
            "en una representacion del consumismo de Estados Unidos tras la "
            "guerra."
        ),
        published_at=None,
    )

    # Orthogonal embeddings too, so the survival is earned by lexical
    # coverage alone - i.e. by the source actually containing what the
    # claim asserts, which is the property being tested.
    ranker = EvidenceRanker(
        embeddings=_orthogonal_to(claim.text, on_point.content),
        source_repository=FakeSourceRepository([]),
    )

    result = ranker.rank(claim, [on_point])

    assert [item.url for item in result.kept] == ["https://example.com/consumismo"]
    assert result.rejected == []


def test_the_gate_reads_the_runs_threshold_not_the_environment():
    """
    The knob that trades a confident wrong answer for an honest
    UNVERIFIED has to be reachable per run, or tuning it means editing
    .env and restarting.
    """

    claim = _coyote_claim()

    borderline = create_evidence(
        url="https://example.com/partial",
        title="ACME",
        content="ACME y Estados Unidos aparecen aqui.",
        published_at=None,
    )

    ranker = EvidenceRanker(
        embeddings=FakeEmbeddingService(),
        source_repository=FakeSourceRepository([]),
    )

    wide_open = ranker.rank(
        claim, [borderline], PipelineThresholds(evidence_min_pertinence=0.0)
    )
    shut = ranker.rank(
        claim, [borderline], PipelineThresholds(evidence_min_pertinence=1.0)
    )

    assert len(wide_open.kept) == 1
    assert wide_open.rejected == []

    assert shut.kept == []
    assert len(shut.rejected) == 1


def test_the_ranking_keeps_the_four_factors_behind_its_score():

    claim = _coyote_claim()

    evidence = create_evidence(
        url="https://example.com/a",
        title="El coyote y ACME",
        content="El coyote compra productos de ACME en Estados Unidos.",
        published_at=None,
    )

    ranker = EvidenceRanker(
        embeddings=FakeEmbeddingService(),
        source_repository=FakeSourceRepository([]),
    )

    [ranked] = ranker.rank(claim, [evidence], no_gate()).kept

    for factor in (
        ranked.semantic_score,
        ranked.lexical_score,
        ranked.recency_score,
        ranked.reliability_score,
        ranked.pertinence_score,
    ):
        assert factor is not None
        assert 0.0 <= factor <= 1.0


def test_the_claims_embedding_is_reused_rather_than_recomputed():
    """
    EvidenceRetriever has already encoded the claim by the time ranking
    runs. Encoding it again was a second round trip to inference/ per
    claim, on the critical path, for an answer already in memory.
    """

    class CountingEmbeddings(FakeEmbeddingService):

        def __init__(self):
            super().__init__()
            self.singles = 0

        def encode(self, text):
            self.singles += 1
            return super().encode(text)

        def encode_many(self, texts):
            # FakeEmbeddingService batches by looping over encode(), which
            # would count every source as a single encode and hide the
            # very thing this test is about.
            return [FakeEmbeddingService.encode(self, text) for text in texts]

    claim = create_claim(text="claim text")
    embeddings = CountingEmbeddings()

    ranker = EvidenceRanker(
        embeddings=embeddings,
        source_repository=FakeSourceRepository([]),
    )

    ranker.rank(
        claim,
        [create_evidence(url="https://a.com", content="some source text", published_at=None)],
        no_gate(),
        claim_embedding=FakeEmbeddingService.encode(embeddings, claim.text),
    )

    assert embeddings.singles == 0

    # ...and encodes it exactly once when the caller has nothing to hand.
    ranker.rank(
        claim,
        [create_evidence(url="https://a.com", content="some source text", published_at=None)],
        no_gate(),
    )

    assert embeddings.singles == 1


def test_every_source_is_embedded_in_one_batched_call():
    """
    This was `encode()` inside a list comprehension: ranking five sources
    meant five sequential HTTP round trips for work inference/ does in
    one pass.
    """

    class CountingEmbeddings(FakeEmbeddingService):

        def __init__(self):
            super().__init__()
            self.batches = 0

        def encode_many(self, texts):
            self.batches += 1
            return super().encode_many(texts)

    embeddings = CountingEmbeddings()

    ranker = EvidenceRanker(
        embeddings=embeddings,
        source_repository=FakeSourceRepository([]),
    )

    ranker.rank(
        create_claim(),
        [
            create_evidence(url=f"https://{i}.com", content=f"text {i}", published_at=None)
            for i in range(5)
        ],
        no_gate(),
    )

    assert embeddings.batches == 1

from src.models.fact_checker.evidence import EvidenceOrigin
from src.services.fact_checker.retrieval.vector_retriever import VectorRetriever

from tests.factories import create_article, create_claim
from tests.fact_checker.fakes import FakeEmbeddingService


def test_retrieve_returns_related_article_as_internal_evidence(repository):

    article = create_article(
        id="11111111-1111-1111-1111-111111111111",
        url="https://bbc.com/mars-water",
        title="NASA finds water on Mars",
        embedding=[1.0] + [0.0] * 1023,
    )

    repository.save(article)

    claim = create_claim(text="NASA found water on Mars.")

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [1.0] + [0.0] * 1023,
    })

    retriever = VectorRetriever(repository, embeddings=embeddings)

    results = retriever.retrieve(claim)

    assert len(results) == 1
    assert results[0].origin == EvidenceOrigin.INTERNAL
    assert results[0].url == article.url
    assert results[0].relevance_score >= 0.80


def test_retrieve_filters_out_unrelated_articles(repository):

    article = create_article(
        id="11111111-1111-1111-1111-111111111111",
        embedding=[1.0] + [0.0] * 1023,
    )

    repository.save(article)

    claim = create_claim(text="Completely unrelated claim.")

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [0.0, 1.0] + [0.0] * 1022,
    })

    retriever = VectorRetriever(repository, embeddings=embeddings)

    results = retriever.retrieve(claim)

    assert results == []

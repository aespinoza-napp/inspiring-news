from src.config.settings import settings
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever

from tests.factories import create_claim
from tests.fact_checker.fakes import FakeEmbeddingService


class FakeSearchProvider:

    def __init__(self, evidence):
        self.evidence = evidence

    def search(self, claim):
        return self.evidence


class FakeVectorRetriever:

    def __init__(self, evidence):
        self.evidence = evidence

    def retrieve(self, claim, limit=5, thresholds=None):
        return self.evidence


class FakeScraper:

    def __init__(self):
        self.enrich_calls = []

    def enrich(self, evidence):
        self.enrich_calls.append(evidence)
        return [
            item.model_copy(update={"content": f"scraped:{item.url}"})
            for item in evidence
        ]


def test_retrieve_merges_web_and_internal_evidence():

    web = [
        Evidence(url="https://a.com", title="A", snippet="claim keyword here", origin=EvidenceOrigin.WEB),
        Evidence(url="https://b.com", title="B", snippet="unrelated", origin=EvidenceOrigin.WEB),
    ]

    internal = [
        Evidence(
            url="https://internal.com",
            title="Internal",
            snippet="",
            origin=EvidenceOrigin.INTERNAL,
            relevance_score=0.9,
        ),
    ]

    claim = create_claim(text="claim keyword here")

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "A. claim keyword here": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "B. unrelated": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    scraper = FakeScraper()

    retriever = EvidenceRetriever(
        repository=None,
        search_provider=FakeSearchProvider(web),
        scraper=scraper,
        vector_retriever=FakeVectorRetriever(internal),
        embeddings=embeddings,
    )

    result = retriever.retrieve(claim)

    urls = {item.url for item in result.kept}
    assert urls == {"https://a.com", "https://b.com", "https://internal.com"}
    assert result.rejected == []

    assert len(scraper.enrich_calls) == 1
    assert all(item.origin == EvidenceOrigin.WEB for item in scraper.enrich_calls[0])

    internal_result = next(item for item in result.kept if item.origin == EvidenceOrigin.INTERNAL)
    assert internal_result.content is None  # untouched by the scraper


def test_retrieve_returns_empty_when_no_candidates():

    retriever = EvidenceRetriever(
        repository=None,
        search_provider=FakeSearchProvider([]),
        scraper=FakeScraper(),
        vector_retriever=FakeVectorRetriever([]),
        embeddings=FakeEmbeddingService(),
    )

    result = retriever.retrieve(create_claim())

    assert result.kept == []
    assert result.rejected == []


def test_retrieve_only_scrapes_top_web_candidates(monkeypatch):

    monkeypatch.setattr(settings, "MAX_EVIDENCE_PER_CLAIM", 2)

    claim = create_claim(text="target")

    vectors = {claim.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}

    web = []
    for i in range(4):
        text = f"web {i}"
        # Give each candidate a distinct, decreasing similarity to the claim.
        vectors[f"web {i}."] = [1.0 - i * 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        web.append(Evidence(url=f"https://{i}.com", title=text, snippet="", origin=EvidenceOrigin.WEB))

    embeddings = FakeEmbeddingService(vectors=vectors)

    scraper = FakeScraper()

    retriever = EvidenceRetriever(
        repository=None,
        search_provider=FakeSearchProvider(web),
        scraper=scraper,
        vector_retriever=FakeVectorRetriever([]),
        embeddings=embeddings,
    )

    result = retriever.retrieve(claim)

    assert len(scraper.enrich_calls[0]) == 2
    scraped_urls = {item.url for item in scraper.enrich_calls[0]}
    assert scraped_urls == {"https://0.com", "https://1.com"}

    rejected_urls = {item.url for item in result.rejected}
    assert rejected_urls == {"https://2.com", "https://3.com"}
    assert all(item.stage == "evidence_retrieval" for item in result.rejected)

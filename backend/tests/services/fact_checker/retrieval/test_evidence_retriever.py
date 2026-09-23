from src.config.settings import settings
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever

from tests.factories import create_claim
from tests.services.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEvidenceScraper,
    FakeSearchProvider,
    FakeVectorRetriever,
)


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

    scraper = FakeEvidenceScraper()

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
        scraper=FakeEvidenceScraper(),
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

    scraper = FakeEvidenceScraper()

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


def _retriever(web, internal=None):

    provider = FakeSearchProvider(web)
    vectors = FakeVectorRetriever(internal or [])

    retriever = EvidenceRetriever(
        repository=None,
        search_provider=provider,
        scraper=FakeEvidenceScraper(),
        vector_retriever=vectors,
        embeddings=FakeEmbeddingService(),
    )

    return retriever, provider, vectors


def test_retrieve_reports_what_is_searched_and_what_comes_back():

    web = [
        Evidence(url="https://a.com", title="A", snippet="one", origin=EvidenceOrigin.WEB, domain="a.com"),
        Evidence(url="https://b.com", title="B", snippet="two", origin=EvidenceOrigin.WEB, domain="b.com"),
    ]

    retriever, _, _ = _retriever(web)

    claim = create_claim(text="target claim")

    events = []

    result = retriever.retrieve(claim, on_phase=lambda phase, data: events.append((phase, data)))

    assert [phase for phase, _ in events] == [
        "searching_web",
        "web_results",
        "scraping_sources",
        "sources_scraped",
    ]

    by_phase = dict(events)

    assert by_phase["searching_web"]["queries"] == ["query for target claim"]
    assert by_phase["web_results"]["queries"] == ["query for target claim"]
    assert result.queries == ["query for target claim"]

    assert by_phase["web_results"]["webCount"] == 2

    found = by_phase["web_results"]["results"]

    assert {item["url"] for item in found} == {"https://a.com", "https://b.com"}
    assert all("quickScore" in item and "domain" in item for item in found)

    scores = [item["quickScore"] for item in found]
    assert scores == sorted(scores, reverse=True)

    assert all(source["scraped"] for source in by_phase["sources_scraped"]["sources"])


def test_the_search_is_announced_before_it_runs():
    """
    The search is the slow step; the announcement is what lets another
    screen show what is being looked up while the answer is pending.
    """

    retriever, provider, _ = _retriever([
        Evidence(url="https://a.com", title="A", snippet="one", origin=EvidenceOrigin.WEB),
    ])

    searches_done_when_announced = []

    def on_phase(phase, data):
        if phase == "searching_web":
            searches_done_when_announced.append(len(provider.calls))

    retriever.retrieve(create_claim(), on_phase=on_phase)

    assert searches_done_when_announced == [0]
    assert len(provider.calls) == 1


def test_an_empty_search_still_reports_what_was_searched():

    retriever, _, _ = _retriever([])

    events = []

    result = retriever.retrieve(
        create_claim(text="nothing out there"),
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    assert [phase for phase, _ in events] == ["searching_web", "web_results"]
    assert dict(events)["web_results"]["results"] == []
    assert result.queries == ["query for nothing out there"]


def test_the_articles_own_url_is_excluded_from_internal_evidence():

    from src.services.fact_checker.claim_selector import ArticleContext

    retriever, _, vectors = _retriever([])

    retriever.retrieve(
        create_claim(),
        context=ArticleContext(url="https://example.com/the-article"),
    )
    retriever.retrieve(create_claim())

    assert vectors.exclude_urls == ["https://example.com/the-article", None]


def test_the_article_is_excluded_from_its_own_web_results():
    """
    Reproduced live: with the article's subject restored to the queries,
    the search engine's top answer was the article itself, and the model
    cited it as the one source that supported the claim.
    """

    from src.services.fact_checker.claim_selector import ArticleContext

    web = [
        Evidence(
            url="https://www.inspiringnews.ai/cultura/farmear-aura?utm_source=x",
            title="Farmear aura: qué es",
            snippet="one",
            origin=EvidenceOrigin.WEB,
            domain="inspiringnews.ai",
        ),
        Evidence(
            url="https://infobae.com/farmear-aura-cdmx",
            title="Batalla de farmear aura en CDMX",
            snippet="two",
            origin=EvidenceOrigin.WEB,
            domain="infobae.com",
        ),
    ]

    retriever, _, _ = _retriever(web)

    result = retriever.retrieve(
        create_claim(),
        context=ArticleContext(url="https://inspiringnews.ai/cultura/farmear-aura/"),
    )

    assert [item.url for item in result.kept] == ["https://infobae.com/farmear-aura-cdmx"]

    [itself] = [item for item in result.rejected if "itself" in item.reason]
    assert itself.stage == "evidence_retrieval"

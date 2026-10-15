"""
News on the same story, for the writer (src/services/writer/related_news.py):
both routes, what is kept, and what happens when a route fails.
"""

import inspect
from datetime import datetime

from src.config.thresholds import WriterThresholds
from src.models.core.news import News
from src.repositories.vector_repository import VectorRepository
from src.services.writer.analysed_article import AnalysedArticle
from src.services.writer.related_news import (
    MIN_SNIPPET_CHARS,
    RatedDomains,
    RelatedNewsFinder,
    search_query,
)

from tests.services.fact_checker.fakes import FakeExtractorService, FakeSearxngClient
from tests.services.writer.writer_fakes import (
    ExplodingEmbeddings,
    FakeVectorRepository,
    search_hit,
)

ARTICLE = AnalysedArticle(
    id="0123456789abcdef",
    url="https://www.bbc.com/news/valley-trees",
    headline='Volunteers plant 40,000 "native" trees in the valley',
    lead="Volunteers planted forty thousand native trees.",
    language="en",
    topic="Environment",
    published_at="2026-09-01T08:00:00",
    source_name="BBC News",
    domain="bbc.com",
    embedding=(0.1, 0.2, 0.3),
)

PAGE = "The replanting of the valley continued this autumn with schools joining in. " * 10


def news(url: str, published_at: datetime | None = None, content: str = PAGE) -> News:

    return News(source_id="web", url=url, title="", content=content, published_at=published_at)


def finder(search=None, pages=None, repository=None, rated=()) -> RelatedNewsFinder:

    return RelatedNewsFinder(
        search=search or FakeSearxngClient(results=[]),
        extractor=FakeExtractorService(pages or {}),
        repository=lambda: repository or FakeVectorRepository(),
        embeddings=ExplodingEmbeddings(),
        rated=RatedDomains(set(rated)),
    )


def test_the_fake_repository_accepts_what_the_real_search_accepts():
    """The shared-fake contract (CLAUDE.md, invariant 10), for this file's own fake."""

    real = set(inspect.signature(VectorRepository.search).parameters) - {"self"}
    fake = set(inspect.signature(FakeVectorRepository.search).parameters) - {"self"}

    assert real <= fake


def test_the_headline_is_searched_as_news_and_in_general_in_the_articles_language():

    search = FakeSearxngClient(results=[])

    found = finder(search=search).find(ARTICLE, WriterThresholds())

    assert search.queries == [
        "!news Volunteers plant 40,000 native trees in the valley",
        "Volunteers plant 40,000 native trees in the valley",
    ]
    assert search.languages == ["en", "en"]
    assert found.queries == search.queries


def test_a_long_headline_is_cut_to_a_query():

    assert len(search_query(" ".join(["word"] * 40)).split()) == 14


def test_the_analysed_article_and_its_own_outlet_are_never_related_news():

    search = FakeSearxngClient(results=[
        search_hit("https://www.bbc.com/news/valley-trees?utm_source=x"),
        search_hit("https://bbc.com/news/another-bbc-story"),
        search_hit("https://other.example/valley"),
    ])

    found = finder(search=search, pages={"https://other.example/valley": news("https://other.example/valley")}).find(
        ARTICLE, WriterThresholds()
    )

    assert [source.url for source in found.sources] == ["https://other.example/valley"]


def test_one_source_per_domain_rated_first_and_capped():

    search = FakeSearxngClient(results=[
        search_hit("https://unrated.example/one"),
        search_hit("https://unrated.example/two"),
        search_hit("https://second.example/story"),
        search_hit("https://rated.example/story"),
    ])

    pages = {
        url: news(url)
        for url in (
            "https://unrated.example/one",
            "https://unrated.example/two",
            "https://second.example/story",
            "https://rated.example/story",
        )
    }

    found = finder(search=search, pages=pages, rated={"rated.example"}).find(
        ARTICLE, WriterThresholds(related_max_sources=2)
    )

    assert [source.url for source in found.sources] == [
        "https://rated.example/story",
        "https://unrated.example/one",
    ]
    assert [source.reliability_known for source in found.sources] == [True, False]
    assert all(source.origin == "related" for source in found.sources)


def test_a_story_dated_well_before_the_analysed_one_is_left_out():

    search = FakeSearxngClient(results=[
        search_hit("https://old.example/story", published="2025-01-01T00:00:00Z"),
        search_hit("https://follow-up.example/story", published="2026-09-20T00:00:00Z"),
    ])

    pages = {
        "https://old.example/story": news("https://old.example/story"),
        "https://follow-up.example/story": news("https://follow-up.example/story"),
    }

    found = finder(search=search, pages=pages).find(ARTICLE, WriterThresholds(related_max_age_days=30))

    assert [source.url for source in found.sources] == ["https://follow-up.example/story"]


def test_a_page_dated_only_once_read_is_still_held_to_the_window():

    search = FakeSearxngClient(results=[search_hit("https://undated.example/story")])

    pages = {"https://undated.example/story": news("https://undated.example/story", published_at=datetime(2024, 5, 1))}

    found = finder(search=search, pages=pages).find(ARTICLE, WriterThresholds())

    assert found.sources == []


def test_the_writer_sees_a_bounded_excerpt_not_the_page():

    search = FakeSearxngClient(results=[search_hit("https://other.example/valley")])

    found = finder(search=search, pages={"https://other.example/valley": news("https://other.example/valley")}).find(
        ARTICLE, WriterThresholds(related_excerpt_chars=300)
    )

    assert len(found.sources[0].excerpt) <= 301
    assert found.sources[0].excerpt.endswith("…")


def test_a_page_that_will_not_extract_keeps_a_useful_snippet_or_goes():

    useful = "s" * MIN_SNIPPET_CHARS
    search = FakeSearxngClient(results=[
        search_hit("https://snippet.example/story", content=useful),
        search_hit("https://empty.example/story", content="Too short."),
    ])

    found = finder(search=search, pages={
        "https://snippet.example/story": None,
        "https://empty.example/story": RuntimeError("connection reset"),
    }).find(ARTICLE, WriterThresholds())

    assert [(source.url, source.excerpt) for source in found.sources] == [("https://snippet.example/story", useful)]
    assert any("could not be read" in note for note in found.notes)


def test_the_corpus_is_searched_with_the_stored_embedding_and_its_bar():

    repository = FakeVectorRepository(hits=[
        ("https://corpus.example/same-story", 0.91, "Same story", PAGE, datetime(2026, 9, 2)),
        ("https://corpus.example/other-topic", 0.62, "Something else", PAGE, datetime(2026, 9, 2)),
        (ARTICLE.url, 1.0, "Itself", PAGE, datetime(2026, 9, 1)),
    ])

    found = finder(repository=repository).find(ARTICLE, WriterThresholds(related_min_similarity=0.8))

    # ExplodingEmbeddings would have raised had a new vector been made.
    assert repository.vectors == [[0.1, 0.2, 0.3]]
    assert [source.url for source in found.sources] == ["https://corpus.example/same-story"]
    assert found.sources[0].title == "Same story"


def test_web_search_unavailable_still_gives_the_corpus_and_says_so():

    repository = FakeVectorRepository(hits=[
        ("https://corpus.example/same-story", 0.91, "Same story", PAGE, datetime(2026, 9, 2)),
    ])

    found = finder(search=FakeSearxngClient(unavailable=True), repository=repository).find(ARTICLE, WriterThresholds())

    assert found.search_unavailable
    assert [source.url for source in found.sources] == ["https://corpus.example/same-story"]
    assert any("Web search was unavailable" in note for note in found.notes)


def test_both_routes_failing_is_a_note_not_an_exception():

    found = finder(
        search=FakeSearxngClient(unavailable=True),
        repository=FakeVectorRepository(error=RuntimeError("Storage folder is already accessed by another instance")),
    ).find(ARTICLE, WriterThresholds())

    assert found.sources == []
    assert found.search_unavailable and found.corpus_unavailable
    assert any("already accessed" in note for note in found.notes)
    assert any("No related news was found" in note for note in found.notes)


def test_an_empty_answer_is_said_to_be_empty_not_unavailable():

    found = finder(search=FakeSearxngClient(results=[])).find(ARTICLE, WriterThresholds())

    assert not found.search_unavailable
    assert any("found nothing" in note for note in found.notes)


def test_zero_related_sources_searches_nothing():

    search = FakeSearxngClient(results=[search_hit("https://other.example/valley")])

    found = finder(search=search).find(ARTICLE, WriterThresholds(related_max_sources=0))

    assert search.queries == []
    assert found.sources == []


def test_a_rated_domain_matches_its_subdomains_but_not_a_bare_suffix():

    rated = RatedDomains({"bbc.co.uk"})

    assert "news.bbc.co.uk" in rated
    assert "bbc.co.uk" in rated
    assert "co.uk" not in rated
    assert "example.co.uk" not in rated

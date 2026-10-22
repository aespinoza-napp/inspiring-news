from datetime import datetime

from src.models.core.news import News
from src.services.fact_checker.retrieval.scraper import EvidenceScraper

from tests.factories import create_evidence
from tests.services.fact_checker.fakes import FakeExtractorService


def test_enrich_populates_content_from_scraped_news():

    news = News(
        source_id="web",
        url="https://example.com/a",
        title="Scraped title",
        published_at=datetime(2024, 1, 1),
        content="Full scraped article body.",
    )

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": news,
    }))

    evidence = create_evidence(url="https://example.com/a", title="", published_at=None)

    result = scraper.enrich([evidence])

    assert result[0].content == "Full scraped article body."
    assert result[0].title == "Scraped title"
    assert result[0].published_at == datetime(2024, 1, 1)


def test_enrich_keeps_original_title_when_present():

    news = News(
        source_id="web",
        url="https://example.com/a",
        title="Scraped title",
        published_at=datetime(2024, 1, 1),
        content="Full scraped article body.",
    )

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": news,
    }))

    evidence = create_evidence(url="https://example.com/a", title="Original title")

    result = scraper.enrich([evidence])

    assert result[0].title == "Original title"


def test_enrich_keeps_original_evidence_when_extraction_returns_none():

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": None,
    }))

    evidence = create_evidence(url="https://example.com/a")

    result = scraper.enrich([evidence])

    assert result[0] == evidence


def test_enrich_keeps_original_evidence_on_scrape_error():

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": RuntimeError("boom"),
    }))

    evidence = create_evidence(url="https://example.com/a")

    result = scraper.enrich([evidence])

    assert result[0] == evidence


# ----------------------------------------------------------------------
# PageCache: a page fetched once per process and hour, however many
# claims ask for it, and at the same moment.
# ----------------------------------------------------------------------


def _news(url):
    return News(source_id="web", url=url, title="T", content="A body.")


def test_two_claims_asking_for_one_page_at_once_fetch_it_once():

    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from src.services.fact_checker.retrieval.scraper import PageCache

    cache = PageCache()
    fetches = []
    lock = threading.Lock()

    def fetch():
        with lock:
            fetches.append(1)
        time.sleep(0.05)
        return _news("https://example.com/a")

    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _: cache.get_or_fetch("https://example.com/a", fetch), range(6)))

    assert len(fetches) == 1
    assert all(result.content == "A body." for result in results)


def test_a_page_is_served_again_until_it_expires(monkeypatch):

    from src.services.fact_checker.retrieval import scraper as module

    now = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])

    cache = module.PageCache()
    calls = []

    def fetch():
        calls.append(1)
        return _news("https://example.com/a")

    cache.get_or_fetch("https://example.com/a", fetch)
    now[0] += cache.TTL_SECONDS - 1
    cache.get_or_fetch("https://example.com/a", fetch)
    assert len(calls) == 1

    now[0] += 2
    cache.get_or_fetch("https://example.com/a", fetch)
    assert len(calls) == 2


def test_a_failure_is_remembered_for_minutes_not_the_hour(monkeypatch):

    from src.services.fact_checker.retrieval import scraper as module

    now = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])

    cache = module.PageCache()
    calls = []

    def fetch():
        calls.append(1)
        return None

    assert cache.get_or_fetch("https://example.com/a", fetch) is None
    cache.get_or_fetch("https://example.com/a", fetch)
    assert len(calls) == 1

    now[0] += cache.FAILURE_TTL_SECONDS + 1
    cache.get_or_fetch("https://example.com/a", fetch)
    assert len(calls) == 2


def test_a_fetch_that_raises_releases_the_page_for_the_next_claim():

    import pytest

    from src.services.fact_checker.retrieval.scraper import PageCache

    cache = PageCache()

    def broken():
        raise RuntimeError("socket closed")

    with pytest.raises(RuntimeError):
        cache.get_or_fetch("https://example.com/a", broken)

    # Remembered as a failure for minutes, and nothing left pending.
    assert cache.get_or_fetch("https://example.com/a", lambda: _news("x")) is None
    assert cache._pending == {}


def test_scrapers_given_their_own_extractor_do_not_share_pages():

    first = EvidenceScraper(extractor=FakeExtractorService({"https://example.com/a": _news("https://example.com/a")}))
    second = EvidenceScraper(extractor=FakeExtractorService({"https://example.com/a": None}))

    assert first.enrich([create_evidence(url="https://example.com/a")])[0].content == "A body."
    assert second.enrich([create_evidence(url="https://example.com/a")])[0].content is None


# ----------------------------------------------------------------------
# Waiting only so long, and saying how long each page took (2026-10-22)
# ----------------------------------------------------------------------


def test_a_page_still_loading_at_the_wait_keeps_its_snippet_in_its_place():

    import threading

    release = threading.Event()

    class SlowForB(FakeExtractorService):
        def extract(self, source, url, thresholds=None, purpose="article"):
            if url.endswith("/b"):
                release.wait(5)
            return News(source_id="web", url=url, title="T", content=f"body of {url}")

    scraper = EvidenceScraper(extractor=SlowForB())

    timings = []

    try:
        result = scraper.enrich(
            [create_evidence(url="https://x.com/a"), create_evidence(url="https://x.com/b")],
            wait=0.3,
            timings=timings,
        )
    finally:
        release.set()

    assert [item.content for item in result] == ["body of https://x.com/a", None]
    assert [timing["outcome"] for timing in timings] == ["page", "late"]


def test_each_page_says_whether_it_was_fetched_or_already_known():

    news = News(source_id="web", url="https://x.com/a", title="T", content="body")

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://x.com/a": news,
        "https://x.com/missing": None,
    }))

    first, again = [], []

    scraper.enrich([create_evidence(url="https://x.com/a"), create_evidence(url="https://x.com/missing")], timings=first)
    scraper.enrich([create_evidence(url="https://x.com/a")], timings=again)

    assert [timing["outcome"] for timing in first] == ["page", "snippet"]
    assert [timing["outcome"] for timing in again] == ["cached"]
    assert all(timing["seconds"] >= 0 for timing in first + again)

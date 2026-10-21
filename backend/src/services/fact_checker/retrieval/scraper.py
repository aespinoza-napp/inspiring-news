import threading
import time
from concurrent.futures import Future
from logging import getLogger

from src.config.settings import settings
from src.models.core.news import News
from src.models.fact_checker.evidence import Evidence
from src.models.core.source import NewsSource, SourceType
from src.services.concurrency import SCRAPE, bounded_map
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.request_stats import Purpose

logger = getLogger(__name__)


class PageCache:
    """
    Evidence pages this process extracted lately, by URL, and the ones
    being extracted right now.

    Claims of one article are checked at once and often find the same
    pages (2 of 20 fetches in the 2026-10-20 journal's four claims; the
    stories of one discovery round share more); a second look searches
    again near the same claim; an evaluation run reads the same reference
    pages for related claims. Each fetched them again. Now a page fetched
    in the last hour is served from here, and a claim that asks for a page
    another claim is fetching waits for that fetch instead of sending its
    own.

    The wait happens before the waiter takes a SCRAPE permit: only the
    fetching claim holds one, so no permit is held while waiting on work
    that needs another (concurrency.md, the deadlock rule). A failure is
    kept for minutes, not the hour: a 403 now is a 403 for the next
    claim, but a timeout may not be.
    """

    TTL_SECONDS = 3600
    FAILURE_TTL_SECONDS = 300
    MAX_ENTRIES = 1024

    def __init__(self):

        self._lock = threading.Lock()
        self._done: dict[str, tuple[float, News | None]] = {}
        self._pending: dict[str, Future] = {}

    def get_or_fetch(self, url: str, fetch) -> News | None:

        with self._lock:

            cached = self._done.get(url)

            if cached is not None:
                expires, news = cached
                if expires > time.monotonic():
                    return news
                del self._done[url]

            pending = self._pending.get(url)

            if pending is None:
                pending = self._pending[url] = Future()
                owner = True
            else:
                owner = False

        if not owner:
            return pending.result()

        news = None

        try:
            news = fetch()
        finally:
            ttl = self.TTL_SECONDS if news is not None else self.FAILURE_TTL_SECONDS
            with self._lock:
                self._store(url, news, ttl)
                del self._pending[url]
            pending.set_result(news)

        return news

    def _store(self, url: str, news: News | None, ttl: float) -> None:

        if len(self._done) >= self.MAX_ENTRIES:
            # Oldest-inserted first: dicts keep insertion order.
            for key in list(self._done)[: self.MAX_ENTRIES // 4]:
                del self._done[key]

        self._done[url] = (time.monotonic() + ttl, news)


# One per process, like the permits: the claims, articles and runs that
# share pages are in different scraper instances.
PAGES = PageCache()


class EvidenceScraper:
    """
    Fetches full-page text for web evidence by reusing ExtractorService
    rather than duplicating the scraping stack. ExtractorService.extract()
    requires a NewsSource; web-search hits don't have one, so a generic
    placeholder is synthesized purely to satisfy the interface - it is
    never persisted.
    """

    GENERIC_SOURCE = NewsSource(
        id="web",
        name="Web",
        base_url="https://example.com",
        source_type=SourceType.NEWS,
        reliability_index=0.5,
    )

    def __init__(self, extractor: ExtractorService | None = None, pages: PageCache | None = None):

        self.extractor = extractor or ExtractorService()
        # A scraper given its own extractor (a test, a fake) gets its own
        # cache too, so no page leaks between them through PAGES.
        self.pages = pages or (PAGES if extractor is None else PageCache())

    def enrich(self, evidence: list[Evidence]) -> list[Evidence]:
        """
        Fetches every page at once, and returns them **in input order**.

        Order is not cosmetic here: the list that comes back is ranked,
        cut and then handed to the LLM as a numbered list it cites by
        index, so results in completion order would re-point every
        citation at a different source.

        This was the pipeline's longest non-LLM step - five pages fetched
        one after another, each waiting on a stranger's server. One slow
        host held up the other four for no reason.
        """

        return bounded_map(
            self._enrich_one,
            evidence,
            max_workers=settings.SCRAPE_MAX_CONCURRENCY,
            thread_name_prefix="evidence-scrape",
        )

    def _enrich_one(self, item: Evidence) -> Evidence:

        def fetch() -> News | None:
            # Held around the fetch only. SCRAPE_MAX_CONCURRENCY is the
            # process-wide ceiling: bounded_map's fan-out is per claim,
            # and several claims (and several articles) reach here at
            # once - see src/services/concurrency.py.
            with SCRAPE.permit():
                return self.extractor.extract(
                    self.GENERIC_SOURCE,
                    item.url,
                    purpose=Purpose.EVIDENCE,
                )

        try:
            news = self.pages.get_or_fetch(item.url, fetch)
        except Exception as exc:
            logger.warning("Failed to scrape evidence %s: %s", item.url, exc)
            return item

        if news is None:
            return item

        return item.model_copy(update={
            "content": news.content,
            "title": item.title or news.title or "",
            "published_at": item.published_at or news.published_at,
        })

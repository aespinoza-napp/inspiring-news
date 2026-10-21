"""
HtmlStrategy: pages are fetched side by side and parsed one at a time
(concurrency.py, PARSE). Eight extractions of one 2.6 MB page took
239-304 s in parallel threads and 14.3 s in turn (2026-10-21).
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.models.core.source import NewsSource, SourceType
from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.fetcher import FetchedPage
from src.services.scraper.strategies.html import HtmlStrategy


def create_source() -> NewsSource:
    return NewsSource(
        id="web",
        name="Web",
        base_url="https://example.com",
        source_type=SourceType.NEWS,
        reliability_index=0.5,
    )


class Gauge:
    """How many callers are inside at once, at most."""

    def __init__(self):
        self.lock = threading.Lock()
        self.now = 0
        self.peak = 0

    def __enter__(self):
        with self.lock:
            self.now += 1
            self.peak = max(self.peak, self.now)

    def __exit__(self, *exc):
        with self.lock:
            self.now -= 1


class SlowFetcher:

    def __init__(self, gauge: Gauge):
        self.gauge = gauge

    def get(self, url: str) -> FetchedPage:
        with self.gauge:
            time.sleep(0.05)
        return FetchedPage(url=url, status=200, html="<html></html>")


class SlowParser(HtmlStrategy):

    def __init__(self, fetches: Gauge, parses: Gauge):
        super().__init__(fetcher=SlowFetcher(fetches))
        self.parses = parses

    def parse(self, source, page):
        with self.parses:
            time.sleep(0.02)
        return ExtractionResult(source_id=source.id, title="t", body="A body long enough.")


def test_pages_are_fetched_together_and_parsed_in_turn():

    fetches, parses = Gauge(), Gauge()
    strategy = SlowParser(fetches, parses)
    source = create_source()

    with ThreadPoolExecutor(6) as pool:
        attempts = list(pool.map(lambda n: strategy.attempt(source, f"https://example.com/{n}"), range(6)))

    assert all(attempt.result is not None for attempt in attempts)
    assert fetches.peak > 1
    assert parses.peak == 1


def test_a_parse_that_raises_releases_its_turn():

    class Broken(HtmlStrategy):
        def parse(self, source, page):
            raise ValueError("unparseable")

    strategy = Broken(fetcher=SlowFetcher(Gauge()))

    for n in range(3):
        assert strategy.attempt(create_source(), f"https://example.com/{n}").result is None

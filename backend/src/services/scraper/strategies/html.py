"""
The part every plain-HTML parser shares: getting the page, and saying
precisely why it could not be got.
"""

from __future__ import annotations

from abc import abstractmethod
from logging import getLogger

from src.models.core.source import NewsSource
from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.fetcher import FetchedPage, Fetcher, classify
from src.services.scraper.request_stats import Outcome

from .base import ExtractionAttempt, ExtractionStrategy

logger = getLogger(__name__)


class HtmlStrategy(ExtractionStrategy):
    """
    Fetch (unless handed a page), then `parse()`. Subclasses only parse.
    """

    reads_html = True

    def __init__(self, fetcher: Fetcher | None = None):

        self.fetcher = fetcher or Fetcher()

    @abstractmethod
    def parse(self, source: NewsSource, page: FetchedPage) -> ExtractionResult | None:
        """The article in this page, or None if there is none to find."""

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> ExtractionResult | None:

        return self.attempt(source, url).result

    def attempt(
        self,
        source: NewsSource,
        url: str,
        page: FetchedPage | None = None,
    ) -> ExtractionAttempt:

        name = type(self).__name__
        sent = 0

        try:

            if page is None:
                sent = 1
                page = self.fetcher.get(url)

            result = self.parse(source, page)

            if result is None or not result.body.strip():
                return ExtractionAttempt(None, Outcome.NO_CONTENT, page.status, page=page, sent=sent)

            return ExtractionAttempt(result, Outcome.OK, page.status, page=page, sent=sent)

        except Exception as exc:
            outcome, status, message = classify(exc)

            # A guard refusal sends nothing: it refuses before the request.
            if outcome == Outcome.BLOCKED:
                sent = 0

            logger.warning("%s extracting %s with %s: %s", outcome.value, url, name, message)

            return ExtractionAttempt(None, outcome, status, message, page=page, sent=sent)

"""
The part every plain-HTML parser shares: getting the page, and saying
precisely why it could not be got.
"""

from __future__ import annotations

from abc import abstractmethod
from logging import getLogger

import requests

from src.models.core.source import NewsSource
from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.fetcher import FetchedPage, Fetcher
from src.services.scraper.request_stats import Outcome
from src.services.scraper.url_guard import BlockedURL, UnresolvableHost

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

        except UnresolvableHost as exc:
            logger.warning("Could not resolve %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.CONNECTION_ERROR, error=str(exc), sent=sent)

        except BlockedURL as exc:
            # Not an unexpected failure - the guard did its job. Logged at
            # warning so a blocked fetch is visible without a stack trace.
            # Nothing was sent: the guard refuses before the request.
            logger.warning("Refused to fetch %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.BLOCKED, error=str(exc), sent=0)

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.warning("HTTP %s extracting %s", status, url)
            return ExtractionAttempt(None, Outcome.HTTP_ERROR, status, f"HTTP {status}", sent=sent)

        except requests.Timeout as exc:
            logger.warning("Timed out extracting %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.TIMEOUT, error=str(exc), sent=sent)

        except requests.ConnectionError as exc:
            logger.warning("Could not connect extracting %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.CONNECTION_ERROR, error=str(exc), sent=sent)

        except Exception as exc:
            logger.warning("Error extracting %s with %s: %s", url, name, exc)
            return ExtractionAttempt(None, Outcome.ERROR, error=str(exc), page=page, sent=sent)

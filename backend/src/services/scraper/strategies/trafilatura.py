from __future__ import annotations

import json

from logging import getLogger

import requests
import trafilatura

from src.models.scraper.extraction import ExtractionResult
from src.models.core.source import NewsSource
from src.services.scraper.url_guard import BlockedURL, UnresolvableHost, check_url

from src.services.scraper.request_stats import Outcome

from .base import ExtractionAttempt, ExtractionStrategy

logger = getLogger(__name__)

def _parse_date(date_str: str | None) -> str | None:
    """
    Returns the article's published date, or None when trafilatura
    couldn't find one. Never fabricates "today" - a missing date must
    stay missing, not silently become incorrect data.
    """
    if not date_str:
        return None
    try:
        return date_str.split("T")[0]
    except Exception:
        return None
    
class TrafilaturaStrategy(ExtractionStrategy):

    TIMEOUT = 20

    # requests follows redirects itself, which would walk straight past
    # the guard - a public URL can 302 to 127.0.0.1. Hops are followed
    # here instead, one at a time, re-checking each.
    MAX_REDIRECTS = 5

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
    ) -> ExtractionAttempt:

        try:

            response = self._get(url)

            response.raise_for_status()
            extracted = trafilatura.extract(
                response.text,
                output_format="json",
                # trafilatura 2.x leaves title, author, date and
                # description out of the JSON unless asked. Without this
                # every article in the lake came in with `title: None`,
                # no author and no published date - which silently
                # disabled everything downstream that leans on the
                # headline: claim selection's thesis and the fact
                # checker's subject restoration.
                with_metadata=True,
                include_comments=False,
                include_tables=False,
                include_images=False,
            )

            if not extracted:
                return ExtractionAttempt(None, Outcome.NO_CONTENT, response.status_code)

            data = json.loads(extracted)

            body = data.get("text")

            if not body:
                return ExtractionAttempt(None, Outcome.NO_CONTENT, response.status_code)

            return ExtractionAttempt(
                ExtractionResult(
                    source_id=source.id,
                    title=data.get("title") or None,
                    body=body,
                    summary=data.get("description"),
                    author=data.get("author"),
                    published_at=_parse_date(data.get("date")),
                    lead_image=data.get("image"),
                ),
                Outcome.OK,
                response.status_code,
            )

        except UnresolvableHost as exc:
            logger.warning("Could not resolve %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.CONNECTION_ERROR, error=str(exc))

        except BlockedURL as exc:
            # Not an unexpected failure - the guard did its job. Logged at
            # warning so a blocked fetch is visible without a stack trace.
            logger.warning("Refused to fetch %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.BLOCKED, error=str(exc))

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.warning("HTTP %s extracting %s", status, url)
            return ExtractionAttempt(None, Outcome.HTTP_ERROR, status, f"HTTP {status}")

        except requests.Timeout as exc:
            logger.warning("Timed out extracting %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.TIMEOUT, error=str(exc))

        except requests.ConnectionError as exc:
            logger.warning("Could not connect extracting %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.CONNECTION_ERROR, error=str(exc))

        except Exception as exc:
            logger.warning(
                "Error extracting %s with TrafilaturaStrategy: %s", url, exc
            )
            return ExtractionAttempt(None, Outcome.ERROR, error=str(exc))

    def _get(self, url: str) -> requests.Response:
        """
        Fetch, following redirects manually so every hop passes the
        guard. Raises BlockedURL for any hop that does not.
        """

        for _ in range(self.MAX_REDIRECTS + 1):

            response = requests.get(
                check_url(url),
                timeout=self.TIMEOUT,
                allow_redirects=False,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "InspiringNewsBot/1.0"
                    )
                },
            )

            if not response.is_redirect:
                return response

            url = requests.compat.urljoin(url, response.headers["location"])

        raise BlockedURL(f"Too many redirects starting at {url!r}.")
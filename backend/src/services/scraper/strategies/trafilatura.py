from __future__ import annotations

import json

from logging import getLogger

import requests
import trafilatura

from src.models.scraper.extraction import ExtractionResult
from src.models.core.source import NewsSource
from src.services.scraper.url_guard import BlockedURL, check_url

from .base import ExtractionStrategy

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

        try:

            response = self._get(url)

            response.raise_for_status()
            extracted = trafilatura.extract(
                response.text,
                output_format="json",
                include_comments=False,
                include_tables=False,
                include_images=False,
            )

            if not extracted:
                return None

            data = json.loads(extracted)

            body = data.get("text")

            if not body:
                return None

            return ExtractionResult(
                source_id=source.id,
                title=data.get("title") or None,
                body=body,
                summary=data.get("description"),
                author=data.get("author"),
                published_at=_parse_date(data.get("date")),
                lead_image=data.get("image"),
            )

        except BlockedURL as exc:
            # Not an unexpected failure - the guard did its job. Logged at
            # warning so a blocked fetch is visible without a stack trace.
            logger.warning("Refused to fetch %s: %s", url, exc)
            return None

        except Exception as exc:
            logger.warning(
                "Error extracting %s with TrafilaturaStrategy: %s", url, exc
            )
            return None

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
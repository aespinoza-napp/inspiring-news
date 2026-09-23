from __future__ import annotations

import json

import trafilatura

from src.models.scraper.extraction import ExtractionResult
from src.models.core.source import NewsSource
from src.services.scraper.fetcher import FetchedPage

from .html import HtmlStrategy


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


class TrafilaturaStrategy(HtmlStrategy):
    """
    The first and cheapest parser: one request, and trafilatura's own
    boilerplate removal. It handles most news sites; what it cannot find
    goes to BeautifulSoup, which reads the same HTML without fetching it
    again.
    """

    def parse(self, source: NewsSource, page: FetchedPage) -> ExtractionResult | None:

        extracted = trafilatura.extract(
            page.html,
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

from __future__ import annotations

import json

import requests
import trafilatura

from src.models.scraper.extraction import ExtractionResult
from src.models.core.source import NewsSource

from .base import ExtractionStrategy

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

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> ExtractionResult | None:

        try:

            response = requests.get(
                url,
                timeout=self.TIMEOUT,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "InspiringNewsBot/1.0"
                    )
                },
            )

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

        except Exception as exc:
            print(f"Error extracting {url} with TrafilaturaStrategy: {exc}")
            return None
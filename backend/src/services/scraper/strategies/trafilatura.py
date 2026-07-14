from __future__ import annotations

import json

import requests
import trafilatura

from src.models.extraction import ExtractionResult
from src.models.source import NewsSource

from .base import ExtractionStrategy


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
                source_id=source,
                title=data.get("title", ""),
                body=body,
                summary=data.get("description"),
                author=data.get("author"),
                published_at=data.get("date"),
                lead_image=data.get("image"),
            )

        except Exception:

            return None
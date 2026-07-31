from datetime import datetime

from src.config.settings import settings
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.search import SearxngClient


class SearchProvider:

    def __init__(self, client: SearxngClient | None = None):

        self.client = client or SearxngClient()

    def search(self, claim: Claim) -> list[Evidence]:

        raw_results = self.client.search(
            claim.text.strip(),
            max_results=settings.EVIDENCE_FETCH_CANDIDATES,
        )

        evidence = []

        for item in raw_results:

            url = item.get("url")
            title = item.get("title")

            if not url or not title:
                continue

            evidence.append(
                Evidence(
                    url=url,
                    title=title,
                    snippet=item.get("content", ""),
                    published_at=self._parse_date(item.get("publishedDate")),
                    origin=EvidenceOrigin.WEB,
                )
            )

        return evidence

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:

        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

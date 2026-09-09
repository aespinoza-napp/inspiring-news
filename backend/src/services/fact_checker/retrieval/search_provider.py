from datetime import datetime

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.search import SearxngClient


class SearchProvider:

    def __init__(self, client: SearxngClient | None = None):

        self.client = client or SearxngClient()

    def search(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
    ) -> list[Evidence]:

        thresholds = thresholds or PipelineThresholds()

        raw_results = self.client.search(
            claim.text.strip(),
            max_results=thresholds.evidence_fetch_candidates,
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

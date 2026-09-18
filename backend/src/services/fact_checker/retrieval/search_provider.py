from datetime import datetime
from urllib.parse import urlparse

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.search import SearxngClient

from .query_builder import build_query, build_refutation_query


def registrable_domain(url: str) -> str:
    """
    The domain two pieces of evidence would have to share to not be
    independent. Deliberately naive (host minus `www.`): distinguishing
    real registrable suffixes needs a public-suffix list, and for judging
    "is this the same outlet" the host is already the right answer.
    """

    return urlparse(url).netloc.replace("www.", "").lower()


class SearchProvider:

    def __init__(self, client: SearxngClient | None = None):

        self.client = client or SearxngClient()

    def search(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> list[Evidence]:

        thresholds = thresholds or PipelineThresholds()

        candidates = thresholds.evidence_fetch_candidates

        queries = [build_query(claim, context)]

        refutation = build_refutation_query(claim, context, language)

        if refutation:
            queries.append(refutation)

        evidence: list[Evidence] = []

        # Deduped across both queries by URL: the affirmative and
        # refutation passes overlap heavily by design, and the same page
        # arriving twice is not two pieces of evidence.
        seen: set[str] = set()

        for query in queries:

            if not query:
                continue

            for item in self.client.search(
                query,
                max_results=candidates,
                language=language,
            ):

                url = item.get("url")
                title = item.get("title")

                if not url or not title or url in seen:
                    continue

                seen.add(url)

                evidence.append(
                    Evidence(
                        url=url,
                        title=title,
                        snippet=item.get("content", ""),
                        published_at=self._parse_date(item.get("publishedDate")),
                        origin=EvidenceOrigin.WEB,
                        domain=registrable_domain(url),
                        # SearXNG already reports which of its engines
                        # returned a given result; two hits found by
                        # different indexes are better corroboration than
                        # two found by the same one.
                        engines=list(item.get("engines") or []),
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

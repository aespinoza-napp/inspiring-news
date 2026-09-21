from datetime import datetime
from urllib.parse import urlparse

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.concurrency import bounded_map
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.search import SearxngClient

from .query_builder import PlannedQuery, fuse_by_rank, plan_queries


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

    def plan(
        self,
        claim: Claim,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> list[PlannedQuery]:
        """
        The queries `search` will send, each with the question it asks.
        Public so the live view can show what is being looked up *before*
        the search returns, from the same code that runs it rather than a
        copy that drifts.
        """

        return plan_queries(claim, context, language)

    def queries_for(
        self,
        claim: Claim,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> list[str]:
        """Just the query strings, for callers that only report them."""

        return [query.text for query in self.plan(claim, context, language)]

    def search(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> list[Evidence]:
        """
        Every query in the plan, run concurrently, fused into one ranked
        candidate list.

        Concurrent because the queries are independent and a SearXNG
        round trip is seconds, not milliseconds - three in sequence was
        three times the wait for nothing. The process-wide ceiling on how
        many of those may be in flight lives in SearxngClient, not here
        (see src/services/concurrency.py): the limit belongs to the
        service, which does not care which claim a request came from.
        """

        thresholds = thresholds or PipelineThresholds()

        candidates = thresholds.evidence_fetch_candidates

        queries = self.plan(claim, context, language)

        if not queries:
            return []

        results = bounded_map(
            lambda query: self._run(query, candidates, language),
            queries,
            max_workers=settings.QUERY_MAX_CONCURRENCY,
            thread_name_prefix="searxng-query",
        )

        return self._fuse(queries, results)

    ##########################################################

    def _run(
        self,
        query: PlannedQuery,
        candidates: int,
        language: str | None,
    ) -> list[Evidence]:
        """One query's hits, in the order the engine returned them."""

        evidence: list[Evidence] = []

        seen: set[str] = set()

        for item in self.client.search(
            query.text,
            max_results=candidates,
            language=language,
        ):

            url = item.get("url")
            title = item.get("title")

            if not url or not title or url in seen:
                continue

            # A search result is untrusted input. Anything that is not
            # a web page (javascript:, file:, data:) is not evidence,
            # cannot be scraped, and must never reach a link in the UI.
            if not url.lower().startswith(("http://", "https://")):
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
                    found_by=[query.kind.value],
                )
            )

        return evidence

    @staticmethod
    def _fuse(
        queries: list[PlannedQuery],
        results: list[list[Evidence]],
    ) -> list[Evidence]:
        """
        One ranked list from several, by reciprocal rank fusion.

        This used to be "concatenate and dedupe by URL", which ordered
        the candidates by *which query ran first* - so the anchor query's
        eighth hit outranked the proposition query's first, and the
        pre-rank funnel then scraped the wrong five. Fusion orders them
        by how well the queries agreed instead, and `found_by` records
        which ones returned a page at all: a hit only the anchor query
        found is about the subject, and a hit the proposition query found
        too is about the claim.
        """

        fused = fuse_by_rank([[item.url for item in hits] for hits in results])

        merged: dict[str, Evidence] = {}
        found_by: dict[str, list[str]] = {}

        for query, hits in zip(queries, results):
            for item in hits:

                kinds = found_by.setdefault(item.url, [])

                if query.kind.value not in kinds:
                    kinds.append(query.kind.value)

                # The first query to return a page owns its metadata; the
                # later ones only add to found_by. Snippets differ per
                # query and one of them is not more true than another.
                merged.setdefault(item.url, item)

        evidence = [
            item.model_copy(update={
                "found_by": found_by[url],
                "fusion_score": fused.get(url, 0.0),
            })
            for url, item in merged.items()
        ]

        evidence.sort(key=lambda item: item.fusion_score or 0.0, reverse=True)

        return evidence

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:

        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

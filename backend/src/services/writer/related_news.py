"""
News on the same story as the analysed article, from other outlets
(docs/decisions/writing.md, "Writing").

Two routes, both asked every time, at once:

- **the internal corpus**: articles this pipeline already admitted and
  checked, nearest to the analysed article's own stored embedding
  (`VectorRepository.search`, the store `VectorRetriever` reads for
  internal evidence). Same kind of vector on both sides, so the
  similarity means what it means for duplicate detection, and no call to
  inference/ is needed when the processed record holds the embedding;
- **a news search**: the headline through SearXNG's news category
  (`!news`, Bing News in docker/searxng/settings.yml) and its general
  one, with DuckDuckGo behind it when SearXNG cannot answer (the
  `SearxngClient` fallback the fact-checker uses). The SearXNG ceiling in
  src/services/concurrency.py applies inside the client.

Then: drop the analysed article and its own outlet, keep one article per
domain, drop what is dated well before the story, prefer rated and
recent domains, fetch the web pages through the extraction cascade (URL
guard included) under the SCRAPE ceiling, and keep a bounded excerpt of
each. The writer sees excerpts, never whole pages.

Web search often answers with nothing, or not at all
(docs/decisions/retrieval.md). Neither route failing ever fails a draft:
`RelatedNews.notes` says what happened, the writer is told, and the
draft is written from what there is.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Callable

from src.config.settings import settings
from src.config.thresholds import WriterThresholds
from src.models.writer.draft import DraftSource
from src.services.concurrency import SCRAPE, bounded_map
from src.services.fact_checker.retrieval.query_builder import fuse_by_rank
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.reader.views import excerpt
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of
from src.services.search import SearchUnavailableError
from src.services.writer.analysed_article import AnalysedArticle

logger = logging.getLogger(__name__)

# Why these pages are fetched, as the scraper's request stats count it.
# A plain string: ExtractorService takes `Purpose | str` and the stats
# record whatever they are given, so no enum member is needed for it.
PURPOSE = "writing"

# SearXNG's category shortcut: "!news <query>" asks its news engines only.
NEWS_BANG = "!news"

# The headline is the query. Past this many words a headline is a
# sentence, and the engines match fewer pages, not better ones.
QUERY_WORDS = 14

# A search snippet stands in for a page that could not be read only when
# it says something; a title and a date is not a source.
MIN_SNIPPET_CHARS = 120

# How the candidates are ordered: how well they match the story, whether
# we hold a reliability rating for their domain, and how close in time
# they are to it. Reasoned, not fitted - relevance leads, a rating and
# recency break the many near-ties between engine results.
RELEVANCE_WEIGHT = 0.5
RATED_WEIGHT = 0.3
RECENCY_WEIGHT = 0.2

# Recency: a candidate this many days from the story scores 1/e.
RECENCY_DAYS = 14.0

# Fetched for each source kept: some pages will not extract, and a list
# cut before fetching would come back short.
FETCH_FACTOR = 2


@dataclass(frozen=True)
class Candidate:

    url: str

    title: str

    domain: str

    # "corpus" or "web".
    route: str

    # 0-1: corpus similarity, or the web result's place in the fused list.
    relevance: float

    published_at: datetime | None = None

    snippet: str = ""

    # The page's text: the corpus has it; a web page has it once fetched.
    text: str | None = None

    reliability_known: bool = False

    # Set when the page was asked for and could not be read.
    unread: bool = False


@dataclass
class RouteResult:

    candidates: list[Candidate] = field(default_factory=list)

    # A failure of ours ("could not search"), as opposed to an empty answer.
    failure: str | None = None

    queries: list[str] = field(default_factory=list)


@dataclass
class RelatedNews:

    sources: list[DraftSource]

    # What happened, for the writer's prompt and the log.
    notes: list[str] = field(default_factory=list)

    # No web query could be answered at all.
    search_unavailable: bool = False

    corpus_unavailable: bool = False

    queries: list[str] = field(default_factory=list)


def _aware(value) -> datetime | None:

    if value is None or value == "":
        return None

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if not isinstance(value, datetime):
        return None

    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def search_query(headline: str) -> str:
    """The headline as a query: one line, no quotes, at most QUERY_WORDS."""

    words = re.sub(r"[\"“”«»]", " ", headline or "").split()

    return " ".join(words[:QUERY_WORDS])


class RatedDomains:
    """
    Whether we hold a reliability rating for a domain: the configured
    sources', matched by host or a parent of it (news.bbc.co.uk is still
    bbc.co.uk), as the reader names outlets.
    """

    def __init__(self, domains: set[str] | None = None, loader: Callable[[], list] | None = None):

        self._domains = domains
        self._loader = loader

    @property
    def domains(self) -> set[str]:

        if self._domains is None:
            try:
                loader = self._loader or _configured_sources
                self._domains = {domain_of(str(source.base_url)) for source in loader()}
            except Exception:  # noqa: BLE001 - an unrated list, not a failed draft
                logger.warning("Could not load the configured sources", exc_info=True)
                self._domains = set()

        return self._domains

    def __contains__(self, domain: str) -> bool:

        labels = (domain or "").lower().split(".")

        return any(".".join(labels[start:]) in self.domains for start in range(len(labels) - 1))


def _configured_sources() -> list:

    from src.repositories.source_repository import SourceRepository

    return SourceRepository().list()


class RelatedNewsFinder:

    def __init__(
        self,
        search=None,
        extractor=None,
        repository: Callable[[], object] | None = None,
        embeddings=None,
        rated: RatedDomains | None = None,
    ):
        """
        Every collaborator is built on first use, not here: the container
        constructs this for a route that may never search, and the corpus
        is Qdrant's local store, which only one process may hold - a
        failure to open it is a note on the draft, not a failed import.

        `repository` is a callable returning the VectorRepository
        (`container.get_vector_repository`), for the same reason.
        """

        self._search = search
        self._extractor = extractor
        self._repository = repository
        self._embeddings = embeddings
        self.rated = rated or RatedDomains()

    # ------------------------------------------------------------------
    # Collaborators
    # ------------------------------------------------------------------

    @property
    def search(self):

        if self._search is None:
            from src.services.fact_checker.retrieval.search_provider import default_fallback
            from src.services.search import SearxngClient

            self._search = SearxngClient(fallback=default_fallback())

        return self._search

    @property
    def extractor(self):

        if self._extractor is None:
            from src.services.scraper.extractor import ExtractorService

            self._extractor = ExtractorService()

        return self._extractor

    @property
    def embeddings(self):

        if self._embeddings is None:
            from src.services.embeddings.service import EmbeddingService

            self._embeddings = EmbeddingService()

        return self._embeddings

    # ------------------------------------------------------------------
    # The search
    # ------------------------------------------------------------------

    def find(
        self,
        article: AnalysedArticle,
        thresholds: WriterThresholds | None = None,
    ) -> RelatedNews:

        thresholds = thresholds or WriterThresholds()

        wanted = thresholds.related_max_sources

        if wanted == 0:
            return RelatedNews(sources=[], notes=["Related news was not searched for (related_max_sources is 0)."])

        # The two routes at once: neither holds a permit the other needs.
        corpus, web = bounded_map(
            lambda route: route(article, thresholds),
            [self._corpus, self._web],
            max_workers=2,
            thread_name_prefix="writer-related",
        )

        notes: list[str] = []

        if web.failure:
            notes.append(
                f"Web search was unavailable ({web.failure}), so no news from the web could be "
                "looked for; related news comes from articles this newsroom already analysed."
            )
        elif not web.candidates:
            notes.append("Web search answered, but found nothing on this story.")

        if corpus.failure:
            notes.append(f"Articles this newsroom already analysed could not be searched ({corpus.failure}).")

        candidates = self._shortlist(article, corpus.candidates + web.candidates, thresholds)

        read = bounded_map(
            lambda candidate: self._read(candidate, thresholds),
            candidates[: wanted * FETCH_FACTOR],
            max_workers=settings.SCRAPE_MAX_CONCURRENCY,
            thread_name_prefix="writer-fetch",
        )

        unread = sum(candidate.unread for candidate in read)

        # A page's own date is known only once it is read: the age rule is
        # applied again, and the order recomputed with it.
        usable = self._order(
            article,
            [
                candidate
                for candidate in read
                if candidate.text and self._in_window(article, candidate, thresholds)
            ],
        )[:wanted]

        if unread:
            notes.append(f"{unread} related page(s) could not be read and were left out, or kept as their search snippet.")

        if not usable:
            notes.append(
                "No related news was found: the article rests on the analysed article "
                "and the evidence behind its fact-checks only."
            )

        sources = [
            DraftSource(
                url=candidate.url,
                title=candidate.title,
                domain=candidate.domain,
                origin="related",
                published_at=candidate.published_at.isoformat() if candidate.published_at else None,
                excerpt=excerpt(candidate.text, thresholds.related_excerpt_chars),
                reliability_known=candidate.reliability_known,
            )
            for candidate in usable
        ]

        for note in notes:
            logger.info("Related news for %s: %s", article.url, note)

        return RelatedNews(
            sources=sources,
            notes=notes,
            search_unavailable=bool(web.failure),
            corpus_unavailable=bool(corpus.failure),
            queries=web.queries,
        )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def _corpus(self, article: AnalysedArticle, thresholds: WriterThresholds) -> RouteResult:

        if self._repository is None:
            return RouteResult(failure="no corpus configured")

        try:
            vector = (
                list(article.embedding)
                if article.embedding
                else _as_vector(self.embeddings.encode(f"{article.headline}\n{article.lead}"))
            )

            hits = self._repository().search(
                vector,
                limit=thresholds.related_max_sources * FETCH_FACTOR + 1,
                exclude_url=article.url,
            )
        except Exception as exc:  # noqa: BLE001 - Qdrant held by another process, inference/ down
            logger.warning("Corpus search for %s failed: %s", article.url, exc)
            return RouteResult(failure=str(exc) or type(exc).__name__)

        candidates = []

        for hit in hits:

            if hit.similarity < thresholds.related_min_similarity:
                continue

            stored = hit.article

            candidates.append(Candidate(
                url=stored.url,
                title=stored.title or "",
                domain=domain_of(stored.url),
                route="corpus",
                relevance=float(hit.similarity),
                published_at=_aware(stored.published_at),
                snippet=stored.body[:500],
                text=stored.body,
                reliability_known=domain_of(stored.url) in self.rated,
            ))

        return RouteResult(candidates=candidates)

    def _web(self, article: AnalysedArticle, thresholds: WriterThresholds) -> RouteResult:

        query = search_query(article.headline)

        if not query:
            return RouteResult(failure="the article has no headline to search for")

        # News first; the general index answers when the news engine does
        # not, and finds the outlets it does not carry.
        queries = [f"{NEWS_BANG} {query}", query]

        # Only the languages the engines are asked in elsewhere: a source
        # language is en or es (CLAUDE.md, invariant 8).
        language = article.language if article.language in ("en", "es") else None

        limit = max(settings.SEARXNG_MAX_RESULTS, thresholds.related_max_sources * 3)

        def run(text: str) -> list[dict] | SearchUnavailableError:
            try:
                return self.search.search(text, max_results=limit, language=language)
            except SearchUnavailableError as exc:
                return exc

        answers = bounded_map(
            run,
            queries,
            max_workers=settings.QUERY_MAX_CONCURRENCY,
            thread_name_prefix="writer-search",
        )

        failures = [answer for answer in answers if isinstance(answer, SearchUnavailableError)]

        if len(failures) == len(answers):
            return RouteResult(failure=str(failures[0]), queries=queries)

        results = [[] if isinstance(answer, SearchUnavailableError) else answer for answer in answers]

        hits: dict[str, dict] = {}

        ranked = []

        for answer in results:

            urls = []

            for item in answer:

                url = str(item.get("url") or "")

                # A search result is untrusted input: only web pages, which
                # are the only thing the cascade fetches or a link may show.
                if not url.lower().startswith(("http://", "https://")) or not item.get("title"):
                    continue

                hits.setdefault(url, item)
                urls.append(url)

            ranked.append(urls)

        fused = sorted(fuse_by_rank(ranked).items(), key=lambda pair: pair[1], reverse=True)

        candidates = []

        for position, (url, _) in enumerate(fused):

            item = hits[url]

            candidates.append(Candidate(
                url=url,
                title=str(item.get("title") or ""),
                domain=domain_of(url),
                route="web",
                # Top result 1.0, falling with its place in the fused list.
                relevance=1.0 / (1.0 + 0.25 * position),
                published_at=_aware(item.get("publishedDate")),
                snippet=str(item.get("content") or ""),
                reliability_known=domain_of(url) in self.rated,
            ))

        return RouteResult(candidates=candidates, queries=queries)

    # ------------------------------------------------------------------
    # Choosing
    # ------------------------------------------------------------------

    def _shortlist(
        self,
        article: AnalysedArticle,
        candidates: list[Candidate],
        thresholds: WriterThresholds,
    ) -> list[Candidate]:
        """
        Best first, one per domain, never the analysed article or its own
        outlet, nothing dated well before the story.
        """

        own_url = comparable_url(article.url)
        own_domain = domain_of(article.url)

        kept: dict[str, Candidate] = {}

        for candidate in self._order(article, candidates):

            if comparable_url(candidate.url) == own_url or candidate.domain == own_domain:
                continue

            if not self._in_window(article, candidate, thresholds):
                continue

            # Best-ranked first, so the first one seen per domain is kept.
            kept.setdefault(candidate.domain, candidate)

        return list(kept.values())

    def _order(self, article: AnalysedArticle, candidates: list[Candidate]) -> list[Candidate]:

        anchor = _aware(article.published_at) or datetime.now(timezone.utc)

        def priority(candidate: Candidate) -> float:

            if candidate.published_at is None:
                recency = 0.5
            else:
                days = abs((candidate.published_at - anchor).total_seconds()) / 86400
                recency = math.exp(-days / RECENCY_DAYS)

            return (
                RELEVANCE_WEIGHT * candidate.relevance
                + RATED_WEIGHT * (1.0 if candidate.reliability_known else 0.0)
                + RECENCY_WEIGHT * recency
            )

        # Stable: ties keep the routes' own order.
        return sorted(candidates, key=priority, reverse=True)

    @staticmethod
    def _in_window(article: AnalysedArticle, candidate: Candidate, thresholds: WriterThresholds) -> bool:

        published = _aware(article.published_at)

        if published is None or candidate.published_at is None:
            return True

        return candidate.published_at >= published - timedelta(days=thresholds.related_max_age_days)

    def _read(self, candidate: Candidate, thresholds: WriterThresholds) -> Candidate:
        """
        The page's text, through the extraction cascade - the URL guard
        and the request stats included. A page that will not extract keeps
        its search snippet when the snippet says something, and is marked
        unread either way.
        """

        if candidate.text:
            return candidate

        news = None

        try:
            # Held around the fetch only (src/services/concurrency.py).
            with SCRAPE.permit():
                news = self.extractor.extract(EvidenceScraper.GENERIC_SOURCE, candidate.url, purpose=PURPOSE)
        except Exception as exc:  # noqa: BLE001 - one page, not the draft
            logger.info("Could not read related page %s: %s", candidate.url, exc)

        if news is not None and (news.content or "").strip():
            return replace(
                candidate,
                text=news.content,
                title=candidate.title or news.title or "",
                published_at=candidate.published_at or _aware(news.published_at),
            )

        snippet = (candidate.snippet or "").strip()

        return replace(candidate, text=snippet if len(snippet) >= MIN_SNIPPET_CHARS else None, unread=True)


def _as_vector(embedding) -> list[float]:

    if hasattr(embedding, "tolist"):
        return embedding.tolist()

    return [float(value) for value in embedding]

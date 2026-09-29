"""
The day's labelling batch: ~10 articles from the configured sources, each
with the 1-3 claims the pipeline itself would check, ready for a person
to verify in labeller/.

Hand-labelling used to start with a search - pick an outlet, pick an
article, read it, decide which sentence was worth checking - and that
search took longer than the verification. It also biased the set: the
annotator picked what looked easy to check (see the Limitations of
docs/final_document/sections/custom_dataset.tex). Here the choice is
made by chance and by the system:

1. **Discovery** over every enabled source, exactly as ingestion does it.
2. **Exclusion** of every URL the caller already has - labelled facts and
   earlier batches - compared by host and path.
3. **A seeded random draw**: one article per source, sources shuffled,
   languages alternated. The seed is the day, so the same links give the
   same draw - not a fresh roll to cherry-pick from. Feeds change during
   the day, though, so a second batch hours later can differ.
4. **Extraction** through the real cascade (purpose `labelling`), then
   **claims**: the enrichment pipeline's extractor and the fact-checker's
   own ClaimSelector anchors, so the set is labelled on the claims the
   system actually checks. When `inference/` is down the anchors cannot
   be scored (they need embeddings); the extractor's own confidence ranks
   them instead, and each claim says which (`selectedBy`).
5. **Preference**: over-sample, then choose recent articles first (see
   RECENT_DAYS), then those whose predicted topic the caller is short of
   (`preferTopics`, computed by the labeller from its verdict x
   topic-group table).

Side-effect free apart from the scraper stats: nothing is stored in the
lake, nothing is fact-checked, and no verdict is shown - the annotator
labels blind to what the pipeline would say. The batch is returned, not
written: labeller/ saves it, because the backend may be running in a
container whose data directory the labeller cannot see.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from logging import getLogger

from src.config.thresholds import PipelineThresholds
from src.config.topics import TOPICS
from src.models.core.news import News
from src.models.core.source import NewsSource
from src.services.concurrency import bounded_map
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.inference_client import InferenceUnavailable
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService
from src.services.scraper.request_stats import Purpose

logger = getLogger(__name__)

# Sources discovered, and articles extracted, at once - the same courtesy
# as ingestion's DISCOVERY_CONCURRENCY: other people's servers.
DISCOVERY_CONCURRENCY = 4
EXTRACTION_CONCURRENCY = 3

# Candidates extracted per article wanted. Some fail to extract or yield
# no claim, and the topic preference needs something to choose between.
OVERSAMPLE = 2

# The claim the labeller pre-fills is the article's sentence as is, so a
# sentence this short is a fragment the splitter cut, not a claim.
MIN_CLAIM_CHARS = 40

# Articles published within this many days of the batch come first.
# Feeds carry old pieces (a 2022 book review, a 2023 CNN story in the
# first batches), and the older the article, the wider the gap between
# the evidence the annotator may use - only what existed on publication
# day (the guide's Rule 3) - and today's web, which the system searches.
# custom_dataset.tex lists that gap as a limitation; recent articles keep
# it small. A preference, not a filter: an old article still fills a
# batch that has nothing newer.
RECENT_DAYS = 60

# display name -> key: TopicPrediction.topic carries the display name
# ("Climate"), the labeller and topics.py are keyed ("climate").
_TOPIC_KEY = {topic.name: key for key, topic in TOPICS.items()}


@dataclass
class BatchRequest:

    articles: int = 10

    claims_per_article: int = 3

    # URLs the caller already has: labelled facts, earlier batches.
    exclude: list[str] = field(default_factory=list)

    # Topic keys the caller is short of; articles on them are preferred.
    prefer_topics: list[str] = field(default_factory=list)

    # None: every language the sources publish in.
    languages: list[str] | None = None

    # The draw's seed. The day, by default: the same day proposes the
    # same articles.
    seed: str | None = None

    # Echoed back, so the caller can tell its batch from an older one.
    request_id: str | None = None


def _topic_key(name: str | None) -> str | None:
    if not name:
        return None
    return _TOPIC_KEY.get(name, name if name in TOPICS else None)


def _day(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


class LabellingBatch:

    def __init__(
        self,
        sources: list[NewsSource],
        extractor,
        enrichment,
        selector,
        claim_extractor,
        discovery: DiscoveryService | None = None,
    ):
        self.sources = sources
        self.extractor = extractor
        self.enrichment = enrichment
        self.selector = selector
        self.claim_extractor = claim_extractor
        self.discovery = discovery or DiscoveryService()

        self._lock = threading.Lock()
        self._running = False
        self._started_at: str | None = None
        self._error: str | None = None
        self._request_id: str | None = None
        self.last_batch: dict | None = None

    # ------------------------------------------------------------------
    # Background run, polled - a batch takes a minute or two
    # ------------------------------------------------------------------

    def state(self) -> dict:

        with self._lock:
            return {
                "running": self._running,
                "startedAt": self._started_at,
                "requestId": self._request_id,
                "error": self._error,
                "batch": self.last_batch,
            }

    def start(self, request: BatchRequest) -> bool:
        """False when a batch is already being built."""

        with self._lock:

            if self._running:
                return False

            self._running = True
            self._started_at = _now()
            self._request_id = request.request_id
            self._error = None

        threading.Thread(
            target=self._run_in_background,
            args=(request,),
            name="labelling-batch",
            daemon=True,
        ).start()

        return True

    def _run_in_background(self, request: BatchRequest) -> None:

        try:
            self.run(request)
        except Exception as exc:
            logger.exception("Labelling batch failed")
            with self._lock:
                self._error = str(exc)
        finally:
            with self._lock:
                self._running = False

    # ------------------------------------------------------------------

    def run(self, request: BatchRequest) -> dict:

        seed = request.seed or date.today().isoformat()
        rng = random.Random(seed)

        sources = sorted(
            (
                source
                for source in self.sources
                if source.enabled
                and (not request.languages or source.language in request.languages)
            ),
            key=lambda source: source.id,
        )

        discovered = bounded_map(
            self._discover,
            sources,
            max_workers=DISCOVERY_CONCURRENCY,
            thread_name_prefix="labelling-discovery",
        )

        known = {comparable_url(url) for url in request.exclude if url}

        candidates = self._draw(sources, discovered, known, rng, request.articles * OVERSAMPLE)

        processed = bounded_map(
            lambda candidate: self._prepare(candidate, request.claims_per_article),
            candidates,
            max_workers=EXTRACTION_CONCURRENCY,
            thread_name_prefix="labelling-extract",
        )

        ready = [item for item in processed if item.get("claims")]
        skipped = [
            {"url": item["url"], "source": item["source"], "reason": item["skipReason"]}
            for item in processed
            if not item.get("claims")
        ]

        chosen = self._choose(
            ready, request.articles, set(request.prefer_topics), _as_date(seed) or date.today()
        )

        batch = {
            "requestId": request.request_id,
            "seed": seed,
            "createdAt": _now(),
            "requested": {
                "articles": request.articles,
                "claimsPerArticle": request.claims_per_article,
                "languages": request.languages,
                "preferTopics": request.prefer_topics,
                "excluded": len(known),
            },
            "totals": {
                "sources": len(sources),
                "discovered": sum(len(result.urls) for result in discovered),
                "candidates": len(candidates),
                "ready": len(ready),
                "articles": len(chosen),
                "claims": sum(len(item["claims"]) for item in chosen),
            },
            "articles": chosen,
            "skipped": skipped,
        }

        with self._lock:
            self.last_batch = batch

        return batch

    # ------------------------------------------------------------------

    def _discover(self, source: NewsSource) -> DiscoveryResult:

        try:
            return self.discovery.run(source, topics=list(TOPICS))
        except Exception as exc:
            logger.warning("Discovery failed for %s", source.id, exc_info=True)
            return DiscoveryResult(error=str(exc))

    @staticmethod
    def _draw(
        sources: list[NewsSource],
        discovered: list[DiscoveryResult],
        known: set[str],
        rng: random.Random,
        wanted: int,
    ) -> list[dict]:
        """
        One fresh article per source per round, sources in a seeded random
        order with the languages interleaved, until `wanted`. A second
        round only when there are fewer sources than wanted.
        """

        pools: dict[str, list[str]] = {}
        by_source = {source.id: source for source in sources}

        for source, result in zip(sources, discovered):

            fresh = []
            for url in result.urls:
                key = comparable_url(url)
                if key in known:
                    continue
                known.add(key)
                fresh.append(url)

            if fresh:
                rng.shuffle(fresh)
                pools[source.id] = fresh

        by_language: dict[str, list[str]] = {}
        for source_id in sorted(pools):
            by_language.setdefault(by_source[source_id].language, []).append(source_id)
        for ids in by_language.values():
            rng.shuffle(ids)

        # en, es, en, es...: one language cannot fill the batch just
        # because it has more sources.
        order = []
        queues = [list(ids) for _, ids in sorted(by_language.items())]
        while any(queues):
            for queue in queues:
                if queue:
                    order.append(queue.pop(0))

        candidates = []
        round_ = 0

        while len(candidates) < wanted and any(len(pools[s]) > round_ for s in order):
            for source_id in order:
                if len(candidates) >= wanted:
                    break
                if len(pools[source_id]) > round_:
                    source = by_source[source_id]
                    candidates.append({
                        "url": pools[source_id][round_],
                        "source": source_id,
                        "sourceObj": source,
                        "rank": len(candidates),
                    })
            round_ += 1

        return candidates

    def _prepare(self, candidate: dict, claims_per_article: int) -> dict:

        source: NewsSource = candidate["sourceObj"]
        url = candidate["url"]

        item = {"url": url, "source": source.id, "rank": candidate["rank"]}

        try:
            news = self.extractor.extract(source, url, purpose=Purpose.LABELLING)
        except Exception as exc:
            return {**item, "skipReason": f"extraction failed: {exc}"}

        if news is None or not (news.content or "").strip():
            return {**item, "skipReason": "no article text could be extracted"}

        try:
            claims, selected_by, topics = self._claims(news, claims_per_article)
        except Exception as exc:
            logger.warning("Claim selection failed for %s", url, exc_info=True)
            return {**item, "skipReason": f"claim selection failed: {exc}"}

        if not claims:
            return {**item, "skipReason": "no checkable claim found"}

        return {
            **item,
            "title": news.title,
            "site": _site(url),
            "sourceName": source.name,
            "language": news.language or source.language,
            "publishedAt": _day(news.published_at),
            "author": news.author,
            "topic": topics[0] if topics else None,
            "topics": topics,
            "claims": [
                {
                    "text": claim.text,
                    "selectedBy": selected_by,
                    "score": claim.anchor_score if selected_by == "anchor" else claim.confidence,
                    "figures": claim.facts.figures,
                }
                for claim in claims
            ],
        }

    def _claims(self, news: News, limit: int):
        """
        (claims, how they were chosen, topic keys best first).

        The same extractor and selector the fact-checker uses, so the set
        is labelled on the claims the system would actually check.
        """

        thresholds = PipelineThresholds()

        try:
            article = self.enrichment.process(news, thresholds)
        except InferenceUnavailable:
            article = None

        if article is not None:

            candidates = [c for c in (article.claims or []) if len(c.text) >= MIN_CLAIM_CHARS]
            topics = [
                key
                for key in (_topic_key(t.topic) for t in (article.topics or []))
                if key
            ]

            try:
                selected = self.selector.select(
                    candidates,
                    thresholds,
                    context=ArticleContext(
                        title=article.title or "",
                        url=article.url,
                        lead=(article.body or "")[:400],
                        keywords=article.keywords or [],
                        entities=article.entities or {},
                    ),
                ).selected
                return selected[:limit], "anchor", topics
            except InferenceUnavailable:
                pass

            return (
                sorted(candidates, key=lambda c: c.confidence, reverse=True)[:limit],
                "confidence",
                topics,
            )

        # inference/ down: no embeddings, no topics, and entities degrade
        # to {} - the extractor still finds and scores sentences.
        claims = [
            c
            for c in self.claim_extractor.process(news.content, language=news.language)
            if len(c.text) >= MIN_CLAIM_CHARS
        ]

        return sorted(claims, key=lambda c: c.confidence, reverse=True)[:limit], "confidence", []

    @staticmethod
    def _choose(ready: list[dict], wanted: int, prefer: set[str], today: date) -> list[dict]:
        """
        Recent articles first, then articles on a wanted topic, each group
        in the draw's order; one per source before any source gets a
        second.
        """

        def recent(item) -> bool:
            published = _as_date(item.get("publishedAt"))
            return published is not None and (today - published).days <= RECENT_DAYS

        ordered = sorted(
            ready,
            key=lambda item: (
                0 if recent(item) else 1,
                0 if prefer and item.get("topic") in prefer else 1,
                item["rank"],
            ),
        )

        chosen, seen = [], set()

        for item in ordered:
            if len(chosen) >= wanted:
                break
            if item["source"] not in seen:
                chosen.append(item)
                seen.add(item["source"])

        for item in ordered:
            if len(chosen) >= wanted:
                break
            if item not in chosen:
                chosen.append(item)

        return [{k: v for k, v in item.items() if k != "rank"} for item in chosen]


def _as_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _site(url: str) -> str:
    return comparable_url(url).split("/", 1)[0]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

"""
Writing a draft, start to finish (docs/decisions/writing.md, "Writing"):
the analysed article, the news related to it, the sources in the order
the body will cite them, the fact-checks, then the writer.

`POST /drafts` (src/api/draft_routes.py) finds the article, saves a draft
holding only its headline, and hands `generate` to
`DraftStore.run_in_background` - the draft is `busy` ("generating") until
it returns, and a failure lands in the draft's `error`.

The sources are saved before the model is asked. The page then shows
what was found while the article is being written (minutes, on a CPU),
and the numbering the body cites is fixed from that moment
(`DraftSource`'s docstring).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.config.topics import DEVASTATING_TOPICS
from src.config.thresholds import WriterThresholds
from src.models.writer.draft import ArticleDraft, DraftContent, DraftFactCheck, DraftSource, DraftTrend, Language
from src.services.reader.views import excerpt
from src.services.scraper.article_stats import comparable_url
from src.services.writer.analysed_article import AnalysedArticle, AnalysedArticles
from src.services.writer.article_writer import ArticleWriter
from src.services.writer.draft_store import DraftStore, new_draft_id, now, revise
from src.services.writer.related_news import RatedDomains, RelatedNewsFinder

logger = logging.getLogger(__name__)

_SPACE = re.compile(r"\s+")


def edition_of_article(article: AnalysedArticle) -> str:
    """
    The edition an analysed article was analysed in: its topic is one of
    that edition's labels (the classifier reads only the run's edition's,
    src/config/editions.py). No topic: the positive edition, as before.
    """

    devastating = {topic.name for topic in DEVASTATING_TOPICS.values()}

    return "devastating" if article.topic in devastating else "positive"


def window(content: str | None, anchor: str | None, limit: int) -> str:
    """
    `limit` characters of a page around the passage a verdict was judged
    on (`anchor`, the source's quote), or its opening when the passage
    cannot be found in it. What the writer needs from an evidence page is
    what bore on the claim, not its navigation and first paragraph.
    """

    text = _SPACE.sub(" ", content or "").strip()

    if not text:
        return ""

    probe = _SPACE.sub(" ", anchor or "").strip()[:80]

    position = text.find(probe) if probe else -1

    if position <= 0:
        return excerpt(text, limit)

    start = max(0, position - limit // 4)

    # Start on a word, not inside one.
    if start > 0:
        space = text.find(" ", start)
        start = space + 1 if 0 <= space < position else start

    return "…" + excerpt(text[start:], limit)


def build_fact_checks(article: AnalysedArticle) -> list[DraftFactCheck]:
    """
    Each checked claim with its verdict, and the sources it rests on - the
    ones the model cited, as the reader shows them.
    """

    return [
        DraftFactCheck(
            claim=claim.text,
            verdict=claim.verdict,
            confidence=claim.confidence,
            source_urls=[str(source.get("url")) for source in claim.cited if source.get("url")],
        )
        for claim in article.claims
    ]


def build_sources(
    article: AnalysedArticle,
    related: list[DraftSource],
    thresholds: WriterThresholds,
    rated: RatedDomains | None = None,
    angle: list[DraftSource] | None = None,
) -> list[DraftSource]:
    """
    The analysed article first, then the related news, then - for a draft
    from a trend - the sources behind its confirmed constructive angles,
    then the evidence behind the fact-checks - each URL once. The body
    cites `[n]` into this list, 1-based, so [1] is always the analysed
    article.

    Evidence: only sources a verdict was actually based on (cited), taken
    one claim at a time in turn so every claim's evidence is represented
    before any claim's second source, up to `evidence_max_sources`.
    """

    sources = [
        DraftSource(
            url=article.url,
            title=article.headline,
            domain=article.domain,
            origin="analysed",
            published_at=article.published_at,
            excerpt=excerpt(article.body or article.lead, thresholds.analysed_excerpt_chars),
            reliability_known=bool(rated is not None and article.domain in rated),
        )
    ]

    seen = {comparable_url(article.url)}

    for source in list(related) + list(angle or []):

        key = comparable_url(source.url)

        if key not in seen:
            seen.add(key)
            sources.append(source)

    queues = [list(claim.cited) for claim in article.claims]

    evidence: list[DraftSource] = []

    while len(evidence) < thresholds.evidence_max_sources and any(queues):

        for queue in queues:

            if not queue or len(evidence) >= thresholds.evidence_max_sources:
                continue

            item = queue.pop(0)

            url = str(item.get("url") or "")

            key = comparable_url(url) if url else ""

            if not url.lower().startswith(("http://", "https://")) or key in seen:
                continue

            seen.add(key)

            evidence.append(DraftSource(
                url=url,
                title=item.get("title") or "",
                domain=item.get("domain") or "",
                origin="evidence",
                published_at=item.get("publishedAt"),
                excerpt=window(
                    article.pages.get(url) or item.get("quote") or item.get("snippet"),
                    item.get("quote"),
                    thresholds.evidence_excerpt_chars,
                ),
                reliability_known=bool(item.get("reliabilityKnown")),
            ))

    return sources + evidence


@dataclass
class _TrendMaterial:
    """What a draft from a trend carries: the trend as the draft keeps it, and its angles' sources."""

    draft: DraftTrend

    sources: list[DraftSource]


class DraftWriter:

    def __init__(
        self,
        articles: AnalysedArticles,
        related: RelatedNewsFinder,
        writer: ArticleWriter,
        ledger=None,
        angles=None,
    ):

        self.articles = articles
        self.related = related
        self.writer = writer

        # A draft from a trend (docs/decisions/trends.md): the ledger says
        # which trend brought the article (services/trends/ledger.py), the
        # angle step looks for a confirmed constructive angle
        # (services/trends/angles.py). None: no draft is from a trend.
        self.ledger = ledger
        self.angles = angles

    def find_article(
        self,
        article_id: str | None = None,
        article_url: str | None = None,
    ) -> AnalysedArticle | None:

        return self.articles.find(article_id=article_id, article_url=article_url)

    @staticmethod
    def new_draft(
        article: AnalysedArticle,
        language: Language,
        instructions: str,
        edition: str | None = None,
    ) -> ArticleDraft:
        """
        A draft before anything is written: the analysed article's
        headline as a placeholder title, so the list says what it is.
        `edition` None: the edition the article was analysed in, told by
        its topic label (edition_of_article).
        """

        stamp = now()

        return ArticleDraft(
            id=new_draft_id(),
            source_article_id=article.id,
            language=language,
            edition=edition or edition_of_article(article),
            instructions=instructions,
            content=DraftContent(title=article.headline),
            created_at=stamp,
            updated_at=stamp,
        )

    def start(
        self,
        store: DraftStore,
        draft_id: str,
        article: AnalysedArticle,
        thresholds: WriterThresholds | None = None,
        *,
        wait: bool = False,
    ) -> ArticleDraft:
        """
        Generation in the background. Raises DraftBusy when a step already
        runs on the draft - a second generation is refused, not queued.
        """

        return store.run_in_background(
            draft_id,
            "generating",
            lambda: self.generate(store, draft_id, article, thresholds),
            wait=wait,
        )

    def trend_of(self, article: AnalysedArticle, thresholds: WriterThresholds) -> "_TrendMaterial | None":
        """
        For an article a trending round brought: its trend, and the
        constructive angles looked for and their sources. None otherwise -
        and when no ledger or angle step is configured.
        """

        card = self.ledger.find(article.url) if self.ledger is not None else None

        if not card:
            return None

        result = self.angles.find(article, card, thresholds) if self.angles is not None else None

        draft = DraftTrend(
            id=str(card.get("id") or ""),
            name=str(card.get("name") or ""),
            signal=str(card.get("signal") or ""),
            signal_name=str(card.get("signalName") or ""),
            traffic=card.get("traffic"),
            started_at=card.get("startedAt"),
            link=card.get("link"),
            video=card.get("video"),
            angles=result.angles if result else [],
            angle_note=(result.note if result else "No angle step is configured."),
        )

        return _TrendMaterial(draft=draft, sources=result.sources if result else [])

    def generate(
        self,
        store: DraftStore,
        draft_id: str,
        article: AnalysedArticle,
        thresholds: WriterThresholds | None = None,
    ) -> None:

        thresholds = thresholds or WriterThresholds()

        draft = store.get(draft_id)

        if draft is None:
            return

        article = self.articles.complete(article)

        found = self.related.find(article, thresholds)

        notes = list(found.notes)

        if not article.body:
            notes.append("The analysed article's full text could not be read; source [1] is its stored lead only.")

        fact_checks = build_fact_checks(article)

        # The trend step looks for *constructive* angles to a trend: not the
        # Devastating edition's question, so its drafts go without.
        trend = self.trend_of(article, thresholds) if draft.edition == "positive" else None

        sources = self.writer.fit(
            article,
            build_sources(
                article, found.sources, thresholds, self.related.rated,
                angle=trend.sources if trend else None,
            ),
            fact_checks,
            draft.language,
            draft.instructions,
            notes,
            thresholds,
            trend=trend.draft if trend else None,
            edition=draft.edition,
        )

        def record_material(current: ArticleDraft) -> None:
            current.sources = sources
            current.fact_checks = fact_checks
            if trend:
                current.trend = trend.draft

        store.update(draft_id, record_material)

        written = self.writer.write(
            article,
            sources,
            fact_checks,
            draft.language,
            draft.instructions,
            notes,
            thresholds,
            trend=trend.draft if trend else None,
            edition=draft.edition,
        )

        # No field on the draft holds these yet (docs/decisions/writing.md,
        # "Writing"): logged, for the operator, until the review shows them.
        for finding in written.findings:
            logger.warning("Draft %s: %s", draft_id, finding)

        for note in notes:
            logger.info("Draft %s: %s", draft_id, note)

        def record_article(current: ArticleDraft) -> None:
            revise(current, written.content, "generated", model=written.model)
            current.metadata = written.metadata
            current.model = written.model

        store.update(draft_id, record_article)

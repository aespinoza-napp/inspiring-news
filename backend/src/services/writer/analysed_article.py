"""
The analysed article a draft starts from, as the writer needs it
(docs/decisions/writing.md, "Writing").

Two reads, at two moments:

- `find` is the reader view (`ReaderIndex.article`): headline, lead,
  language, topic, every checked claim with its verdict and the sources
  it rests on. Cheap - the index is a cache - so the request can answer
  404 before a draft exists.
- `complete` adds what the reader view deliberately leaves out: the
  article's body and the text of the evidence pages, from the lake's
  processed layer. Server-side source material, read on the writer's
  thread. The body is somebody else's journalism: the writer sees an
  excerpt of it, paraphrases it and cites it, and nothing here ever puts
  it in front of a reader (docs/decisions/storage.md).

Only articles the reader publishes can be written from: `ReaderIndex.
article` returns None for anything else, including an article whose
newest run was judged FALSE or MISLEADING. That is the reader's rule, kept
on purpose - a draft starts from an article the newsroom stood behind.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from src.models.storage.lineage import DataLayer, build_record_id
from src.services.reader.views import NOT_CHECKED, NOT_JUDGED, reader_id
from src.services.scraper.request_stats import domain_of

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckedClaim:
    """One claim of the analysed article and how its check ended."""

    text: str

    # The pipeline's verdict - or NOT_CHECKED when our search or our model
    # failed, as the reader shows it: an UNVERIFIED there is an outage of
    # ours, not a finding about the claim, and the writer must not be told
    # it is one.
    verdict: str

    confidence: float | None

    explanation: str = ""

    # The reader's source views, cited first.
    sources: tuple[dict, ...] = ()

    @property
    def cited(self) -> list[dict]:

        return [source for source in self.sources if source.get("cited")]


@dataclass(frozen=True)
class AnalysedArticle:

    # The reader id: host and path, hashed (views.reader_id).
    id: str

    url: str

    headline: str

    # The lead the lake keeps (the body's first 500 characters).
    lead: str

    language: str | None

    topic: str | None

    published_at: str | None

    source_name: str

    domain: str

    keywords: tuple[str, ...] = ()

    claims: tuple[CheckedClaim, ...] = ()

    # From the processed layer, by `complete`. None until then, and when
    # that record could not be read - the writer then has the lead only.
    body: str | None = None

    # The article's own stored embedding: the corpus is searched with the
    # same kind of vector it holds, and without a call to inference/.
    embedding: tuple[float, ...] | None = None

    # Evidence page text by URL, from the processed record's fact-check.
    pages: dict[str, str] = field(default_factory=dict)


def _claim(view: dict) -> CheckedClaim:

    outcome = view.get("outcome")

    verdict = NOT_CHECKED if outcome in NOT_JUDGED else (view.get("verdict") or "UNVERIFIED")

    return CheckedClaim(
        text=view.get("text") or "",
        verdict=verdict,
        confidence=view.get("confidence"),
        explanation=view.get("explanation") or "",
        sources=tuple(source for source in view.get("sources") or [] if isinstance(source, dict)),
    )


def from_view(view: dict) -> AnalysedArticle:
    """The reader view's article, before `complete` reads the lake."""

    url = str(view.get("url") or "")

    source = view.get("source") or {}

    return AnalysedArticle(
        id=view.get("id") or reader_id(url),
        url=url,
        headline=view.get("headline") or "",
        lead=view.get("summary") or view.get("excerpt") or "",
        language=view.get("language"),
        topic=view.get("topic"),
        published_at=view.get("publishedAt"),
        source_name=source.get("name") or domain_of(url),
        domain=source.get("domain") or domain_of(url),
        keywords=tuple(str(keyword) for keyword in view.get("keywords") or []),
        claims=tuple(
            _claim(claim)
            for claim in view.get("claims") or []
            if isinstance(claim, dict) and claim.get("text")
        ),
    )


class AnalysedArticles:

    def __init__(self, index, lake):
        """
        `index` is the reader's (`article(id) -> view | None`); `lake` is
        anything with DataLakeRepository's `list(layer)` and `get(layer, id)`.
        """

        self.index = index
        self.lake = lake

    def find(
        self,
        article_id: str | None = None,
        article_url: str | None = None,
    ) -> AnalysedArticle | None:
        """The published article with this reader id or URL, or None."""

        if not article_id:
            if not article_url:
                return None
            article_id = reader_id(article_url)

        view = self.index.article(article_id)

        return from_view(view) if view else None

    def complete(self, article: AnalysedArticle) -> AnalysedArticle:
        """
        The article with its body, embedding and evidence pages, from the
        processed record of the run the reader shows - or unchanged, and
        logged, when that record cannot be found or read.

        The reader view does not say which run it was built from, so the
        run is found again here: the newest exploitation record with the
        same reader id, which is the rule the reader index decides by.
        That lists the exploitation layer once per draft - small records,
        and a draft costs minutes of the model's time anyway.
        """

        try:
            processed = self._processed(article.id)
        except Exception:  # noqa: BLE001 - a lake read must not cost the draft
            logger.warning("Could not read the processed record of %s", article.url, exc_info=True)
            processed = None

        if not processed:
            logger.warning(
                "No processed record for %s: the writer gets its stored lead only",
                article.url,
            )
            return article

        enriched = processed.get("article") or {}

        embedding = enriched.get("embedding")

        pages: dict[str, str] = {}

        for check in ((processed.get("fact_check") or {}).get("claim_checks") or []):
            for item in (check or {}).get("evidence") or []:
                if isinstance(item, dict) and item.get("url") and item.get("content"):
                    pages.setdefault(str(item["url"]), str(item["content"]))

        return replace(
            article,
            body=enriched.get("body") or None,
            embedding=tuple(float(value) for value in embedding) if embedding else None,
            pages=pages,
            keywords=article.keywords or tuple(str(keyword) for keyword in enriched.get("keywords") or []),
        )

    def _processed(self, article_id: str) -> dict | None:

        # Newest first (the lake lists by when each record was produced).
        for document in self.lake.list(DataLayer.EXPLOITATION):

            lineage = document.get("lineage") or {}

            url = document.get("url") or lineage.get("source_url")

            if not url or reader_id(url) != article_id:
                continue

            lake_article_id = document.get("article_id") or lineage.get("article_id")
            run_id = lineage.get("run_id")

            if not (lake_article_id and run_id):
                return None

            return self.lake.get(
                DataLayer.PROCESSED,
                build_record_id(DataLayer.PROCESSED, lake_article_id, run_id),
            )

        return None

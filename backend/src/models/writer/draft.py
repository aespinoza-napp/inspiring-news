"""
An article the newsroom writes, from one analysed article and the news
related to it, through review and rewriting to publication.

One shape shared by every stage of the writing flow
(docs/decisions/writing.md): the writer creates it, the corrector reviews
it, the rewrite loop revises it, the publisher publishes it. Each stage
fills its own fields and leaves the others alone.

Python names are snake_case; the JSON - on disk and over the API - is
camelCase, as everything else the frontend reads is. Always dump with
`by_alias=True`; `populate_by_name` lets either spelling load.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.models.corrector.correction_metric import CorrectionMetric

# Catalan is a writing language only: no source is ingested or scored in
# it (CLAUDE.md, invariant 8 - a third *source* language still fails the
# suite). The corrector's own metrics for a Catalan draft are its job.
Language = Literal["ca", "es", "en"]

# The editorial lifecycle. What is running on a draft right now is `busy`,
# not a status: a draft being rewritten is still a draft.
DraftStatus = Literal["draft", "approved", "published"]

Busy = Literal["generating", "reviewing", "rewriting", "publishing"]

# Why a revision exists. `edited` is a person; `restored` is a person
# putting an earlier revision's text back (POST /drafts/{id}/restore),
# under the model that wrote that text - not `edited`, which the
# published page discloses as "edited by a person" (story.py) about text
# the person did not write. The rest are a model.
RevisionReason = Literal["generated", "edited", "corrected", "rewritten", "restored"]

# Where a source came from: the article the draft starts from, news the
# writer found about the same story, the evidence a claim of the analysed
# article was checked against, or - for a draft from a trend - a source
# behind a constructive angle the fact-check confirmed
# (src/services/trends/angles.py).
SourceOrigin = Literal["analysed", "related", "evidence", "angle"]


class CamelModel(BaseModel):

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DraftSource(CamelModel):
    """
    One source the writer was given. The body cites it as [n], where n is
    its 1-based position in `ArticleDraft.sources` - the list is never
    reordered once the draft exists, or every citation re-points.
    """

    url: str

    title: str = ""

    domain: str = ""

    origin: SourceOrigin

    published_at: str | None = None

    # The text the writer actually saw for this source - not the whole
    # page. What a review can hold the draft to.
    excerpt: str = ""

    reliability_known: bool = False


class DraftFactCheck(CamelModel):
    """A claim of the analysed article, with the pipeline's verdict on it."""

    claim: str

    verdict: str

    confidence: float | None = None

    # URLs of the sources the verdict rests on, as in the reader view.
    source_urls: list[str] = Field(default_factory=list)


class DraftMetadata(CamelModel):

    slug: str = ""

    seo_description: str = ""

    keywords: list[str] = Field(default_factory=list)

    topic: str | None = None

    tags: list[str] = Field(default_factory=list)


class DraftContent(CamelModel):
    """What a person reads. `body` is Markdown; citations are [n]."""

    title: str

    subtitle: str = ""

    body: str = ""


class DraftReview(CamelModel):
    """
    The corrector's judgement of one `DraftContent`.

    `metrics` is keyed by metric name - the corrector's seven
    (`TextCorrector.correct`) plus whatever the draft review adds, such as
    title and subtitle. `corrected`, when present, is the corrector's
    proposed version: a person accepts it or not, it never replaces the
    content on its own.
    """

    metrics: dict[str, CorrectionMetric] = Field(default_factory=dict)

    corrected: DraftContent | None = None

    model: str | None = None

    reviewed_at: str


class DraftRevision(CamelModel):

    content: DraftContent

    reason: RevisionReason

    # The review of *this* content, if one was run before it was replaced.
    review: DraftReview | None = None

    # None for a person's edit.
    model: str | None = None

    at: str


class DraftAngle(CamelModel):
    """
    A constructive angle the writer model proposed for a story from a
    trend, and what the fact-check made of it (docs/decisions/trends.md,
    "The angle"). Kept only when its claim came back TRUE from supporting
    sources of enough domains; a refused one stays here, with why.
    """

    question: str

    # The one checkable sentence that would have to be true.
    claim: str

    query: str = ""

    kept: bool = False

    reason: str = ""

    verdict: str | None = None

    confidence: float | None = None

    # The domains of the cited sources that support the claim.
    domains: list[str] = Field(default_factory=list)

    # Those sources, as they are in the draft's `sources` (origin "angle").
    source_urls: list[str] = Field(default_factory=list)


class DraftTrend(CamelModel):
    """
    The trend a draft's article was found through, from the trend ledger
    (src/services/trends/ledger.py): its card, the angles looked for, and
    the video a person gave with it.
    """

    id: str

    name: str

    signal: str = ""

    signal_name: str = ""

    traffic: int | None = None

    started_at: str | None = None

    link: str | None = None

    # A TikTok video: provider, id, url, title, author. Shown on the
    # published story only through TikTok's own player, after a click.
    video: dict | None = None

    angles: list[DraftAngle] = Field(default_factory=list)

    # Why no angle was looked for, or what went wrong looking.
    angle_note: str | None = None


class PublishRecord(CamelModel):
    """One publication on one channel."""

    channel: str

    at: str

    # Where it can be read, when the channel gives an address.
    url: str | None = None


class ArticleDraft(CamelModel):

    # 16 hex characters, like the reader's article ids, so the frontend's
    # proxies can validate both the same way.
    id: str

    # The reader id (`/reader/articles/{id}`) of the analysed article the
    # draft starts from.
    source_article_id: str

    language: Language

    # The editor's indications for the writer: angle, length, register.
    instructions: str = ""

    content: DraftContent

    sources: list[DraftSource] = Field(default_factory=list)

    fact_checks: list[DraftFactCheck] = Field(default_factory=list)

    metadata: DraftMetadata = Field(default_factory=DraftMetadata)

    # The latest review of `content`; cleared whenever `content` changes,
    # so a review never describes text it did not read.
    review: DraftReview | None = None

    # Oldest first. The last entry's content is `content`.
    revisions: list[DraftRevision] = Field(default_factory=list)

    status: DraftStatus = "draft"

    busy: Busy | None = None

    # The last background step's failure, for the page to show. Cleared
    # when the next step starts.
    error: str | None = None

    # The model that wrote the first version.
    model: str | None = None

    created_at: str

    updated_at: str

    published: list[PublishRecord] = Field(default_factory=list)

    # Set when the analysed article came from a trending round: the trend,
    # and the constructive angles looked for. None for any other draft.
    trend: DraftTrend | None = None


class DraftSummary(CamelModel):
    """A row of the drafts list: no body, no sources."""

    id: str

    source_article_id: str

    language: Language

    title: str

    status: DraftStatus

    busy: Busy | None = None

    created_at: str

    updated_at: str

    @classmethod
    def of(cls, draft: ArticleDraft) -> "DraftSummary":

        return cls(
            id=draft.id,
            source_article_id=draft.source_article_id,
            language=draft.language,
            title=draft.content.title,
            status=draft.status,
            busy=draft.busy,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

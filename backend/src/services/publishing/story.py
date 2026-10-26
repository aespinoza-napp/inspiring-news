"""
What the public sees of a published draft: an immutable snapshot, taken
when the draft is published (docs/decisions/writing.md, "Publishing").

Built field by field from an allowlist, never by dumping the draft and
excluding what is private. `ArticleDraft` grows with every stage of the
writing flow - the review, the rewrite loop - and an exclude list would
publish whatever the next stage adds until someone remembered to exclude
it. Here a new draft field is private until it is copied in by name.

So the snapshot holds the article, the sources it cites, the
fact-checks it rests on, its metadata, when it was published, the
analysed article it started from and what wrote it. Never the editor's
instructions, the revisions, the review, an error, the busy state, or a
source's excerpt: the excerpt is the text of somebody else's page, which
the reader view never republishes either (src/services/reader/views.py).
"""

from __future__ import annotations

from pydantic import Field

from src.models.writer.draft import ArticleDraft, CamelModel, DraftRevision, Language, SourceOrigin


class StoryContent(CamelModel):
    """Markdown body; [n] cites `PublishedStory.sources[n - 1]`."""

    title: str

    subtitle: str = ""

    body: str = ""


class StorySource(CamelModel):

    url: str

    title: str = ""

    domain: str = ""

    origin: SourceOrigin

    published_at: str | None = None


class StoryFactCheck(CamelModel):

    claim: str

    verdict: str

    confidence: float | None = None

    source_urls: list[str] = Field(default_factory=list)


class StoryMetadata(CamelModel):

    slug: str = ""

    seo_description: str = ""

    keywords: list[str] = Field(default_factory=list)

    topic: str | None = None

    tags: list[str] = Field(default_factory=list)


class StoryDisclosure(CamelModel):
    """
    That a model wrote the article, which models, and whether a person
    changed the text. Shown on the public page. A person approving the
    text is not recorded here because it is always true: nothing reaches
    the reader without an approval (src/api/publish_routes.py).

    Disclosed even though the EU AI Act's Article 50(4) exempts
    AI-generated text that has undergone human review or editorial
    control when a person holds editorial responsibility for it: whether
    this site meets that is a judgement nobody has made, the reader's
    own pages already name the model that checked an article, and the
    site's whole point is that a reader can see what a text rests on.
    """

    # Every draft in this flow starts from the writer model; there is no
    # way to start one by hand. Kept explicit so a future hand-written
    # original can say false rather than change shape.
    ai_written: bool = True

    # Distinct, in the order they first wrote: the writer, then any model
    # whose rewrite or correction became the text. Empty when no
    # revision recorded one.
    models: list[str] = Field(default_factory=list)

    human_edited: bool = False


class StoryVideo(CamelModel):
    """
    The TikTok video a person gave with the trend (docs/decisions/trends.md,
    "The story"). The page shows it only through TikTok's own player, and
    only after the reader clicks: the player sets TikTok's cookies.
    """

    provider: str = "tiktok"

    # The player's id: https://www.tiktok.com/player/v1/<id>.
    id: str

    url: str

    title: str | None = None

    author: str | None = None


class StoryTrend(CamelModel):
    """That the story was found through a trend, and which one. Not its angles, searches or link."""

    name: str

    signal_name: str = ""

    video: StoryVideo | None = None


def story_trend(draft: ArticleDraft) -> StoryTrend | None:
    """
    The trend a reader may see, from the draft's: its name and signal, and
    a TikTok video only with a numeric player id and a TikTok link - what
    the page will load after a click is fixed here, not by the draft.
    """

    trend = draft.trend

    if trend is None:
        return None

    video = None
    given = trend.video or {}
    url = str(given.get("url") or "")

    if (
        given.get("provider") == "tiktok"
        and str(given.get("id") or "").isdigit()
        and url.startswith(("https://www.tiktok.com/", "https://tiktok.com/", "https://m.tiktok.com/", "https://vm.tiktok.com/"))
    ):
        video = StoryVideo(
            id=str(given["id"]),
            url=url,
            title=given.get("title") or None,
            author=given.get("author") or None,
        )

    return StoryTrend(name=trend.name, signal_name=trend.signal_name, video=video)


class StoryCard(CamelModel):
    """A row of the public list: no body, no sources."""

    id: str

    language: Language

    title: str

    subtitle: str = ""

    description: str = ""

    topic: str | None = None

    published_at: str

    source_article_id: str

    disclosure: StoryDisclosure


class PublishedStory(CamelModel):

    # The draft's id. The public page lives at /reader/stories/<id>, so
    # unpublishing and publishing again keeps the link.
    id: str

    # The analysed article's reader id: /reader/<id>.
    source_article_id: str

    language: Language

    content: StoryContent

    sources: list[StorySource] = Field(default_factory=list)

    fact_checks: list[StoryFactCheck] = Field(default_factory=list)

    metadata: StoryMetadata = Field(default_factory=StoryMetadata)

    disclosure: StoryDisclosure = Field(default_factory=StoryDisclosure)

    # When this text went public. A later publication of the same draft
    # (after an unpublish, an edit and a new approval) is a new text and
    # takes a new date.
    published_at: str

    # A story from a trend: which, and the video a person gave with it.
    trend: StoryTrend | None = None

    @classmethod
    def of(cls, draft: ArticleDraft, published_at: str) -> "PublishedStory":

        chain = lineage(draft)

        models: list[str] = []

        for model in [draft.model, *(revision.model for revision in chain)]:
            if model and model not in models:
                models.append(model)

        return cls(
            id=draft.id,
            source_article_id=draft.source_article_id,
            language=draft.language,
            content=StoryContent(
                title=draft.content.title,
                subtitle=draft.content.subtitle,
                body=draft.content.body,
            ),
            # In the draft's order, never re-sorted: the body cites them
            # by position.
            sources=[
                StorySource(
                    url=source.url,
                    title=source.title,
                    domain=source.domain,
                    origin=source.origin,
                    published_at=source.published_at,
                )
                for source in draft.sources
            ],
            fact_checks=[
                StoryFactCheck(
                    claim=check.claim,
                    verdict=check.verdict,
                    confidence=check.confidence,
                    source_urls=list(check.source_urls),
                )
                for check in draft.fact_checks
            ],
            metadata=StoryMetadata(
                slug=draft.metadata.slug,
                seo_description=draft.metadata.seo_description,
                keywords=list(draft.metadata.keywords),
                topic=draft.metadata.topic,
                tags=list(draft.metadata.tags),
            ),
            disclosure=StoryDisclosure(
                models=models,
                human_edited=any(revision.reason == "edited" for revision in chain),
            ),
            published_at=published_at,
            trend=story_trend(draft),
        )

    def card(self) -> StoryCard:

        return StoryCard(
            id=self.id,
            language=self.language,
            title=self.content.title,
            subtitle=self.content.subtitle,
            description=self.metadata.seo_description,
            topic=self.metadata.topic,
            published_at=self.published_at,
            source_article_id=self.source_article_id,
            disclosure=self.disclosure,
        )


def lineage(draft: ArticleDraft) -> list[DraftRevision]:
    """
    The revisions that made the current text, oldest first - not every
    revision the draft ever had. A restore puts an earlier text back, so
    what came between (a person's edit, another model's rewrite) is not in
    the published text, and the disclosure must not say it is: "edited by
    a person" on a model's text restored after an edit was false.

    Walks back from the current revision: a correction, a rewrite or an
    edit changed the text before it, so the walk continues; a restore
    copied an earlier text, so the walk jumps to the first revision that
    wrote it; the generated revision is where every text starts.
    """

    revisions = draft.revisions

    chain: list[DraftRevision] = []

    index = len(revisions) - 1

    while index >= 0:

        revision = revisions[index]

        if revision.reason == "restored":

            origin = next(
                (
                    earlier for earlier in range(index)
                    if revisions[earlier].reason != "restored" and revisions[earlier].content == revision.content
                ),
                None,
            )

            if origin is not None:
                index = origin
                continue

            # The text it copied is not in the history (an older draft,
            # a hand-edited file): count everything before it, as the
            # disclosure did before restores existed.

        chain.append(revision)

        if revision.reason == "generated":
            break

        index -= 1

    return list(reversed(chain))


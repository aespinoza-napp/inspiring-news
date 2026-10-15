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

from src.models.writer.draft import ArticleDraft, CamelModel, Language, SourceOrigin


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

    @classmethod
    def of(cls, draft: ArticleDraft, published_at: str) -> "PublishedStory":

        models: list[str] = []

        for model in [draft.model, *(revision.model for revision in draft.revisions)]:
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
                human_edited=any(revision.reason == "edited" for revision in draft.revisions),
            ),
            published_at=published_at,
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

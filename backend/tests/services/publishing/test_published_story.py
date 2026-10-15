"""
The public snapshot of a draft (src/services/publishing/story.py): what
it holds, and above all what it never holds.
"""

import json

from src.models.writer.draft import DraftContent, DraftReview, DraftRevision
from src.services.publishing.story import PublishedStory
from tests.factories import create_draft

PUBLISHED_AT = "2026-10-15T09:00:00+00:00"

# The snapshot's whole shape. A field added to it is a decision to show
# it to anyone on the internet: change this set on purpose.
PUBLIC_FIELDS = {
    "id",
    "sourceArticleId",
    "language",
    "content",
    "sources",
    "factChecks",
    "metadata",
    "disclosure",
    "publishedAt",
}

PRIVATE_FIELDS = {"instructions", "revisions", "review", "error", "busy", "status", "published", "excerpt"}


def every_key(value) -> set[str]:

    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in every_key(item)}

    if isinstance(value, list):
        return {key for item in value for key in every_key(item)}

    return set()


def a_draft_with_everything_private():

    draft = create_draft(
        instructions="PRIVATE-INSTRUCTIONS: angle it towards the funding bid.",
        error="PRIVATE-ERROR: the last rewrite timed out.",
        status="approved",
    )

    draft.review = DraftReview(model="PRIVATE-REVIEWER", reviewed_at="2026-10-15T08:00:00+00:00")
    draft.revisions.insert(
        0,
        DraftRevision(
            content=DraftContent(title="PRIVATE-OLD-TITLE", body="PRIVATE-OLD-BODY"),
            reason="generated",
            at="2026-10-14T08:00:00+00:00",
        ),
    )
    draft.sources[0].excerpt = "PRIVATE-EXCERPT of somebody else's page."

    return draft


def test_the_snapshot_holds_exactly_the_public_fields():

    story = PublishedStory.of(create_draft(), PUBLISHED_AT).model_dump(mode="json", by_alias=True)

    assert set(story) == PUBLIC_FIELDS


def test_nothing_private_reaches_the_snapshot():

    draft = a_draft_with_everything_private()

    story = PublishedStory.of(draft, PUBLISHED_AT).model_dump(mode="json", by_alias=True)

    assert every_key(story) & PRIVATE_FIELDS == set()

    text = json.dumps(story)
    assert "PRIVATE-" not in text


def test_the_article_its_sources_and_checks_are_copied_in_order():

    draft = create_draft()

    story = PublishedStory.of(draft, PUBLISHED_AT)

    assert story.id == draft.id
    assert story.source_article_id == draft.source_article_id
    assert story.content.body == draft.content.body
    # The body cites [n] by position: never re-sorted.
    assert [source.url for source in story.sources] == [source.url for source in draft.sources]
    assert story.fact_checks[0].verdict == "TRUE"
    assert story.fact_checks[0].source_urls == ["https://example.org/seagrass"]
    assert story.published_at == PUBLISHED_AT


def test_the_disclosure_names_every_model_once_and_a_persons_edit():

    draft = create_draft(model="writer-model")
    draft.revisions += [
        DraftRevision(content=draft.content, reason="rewritten", model="writer-model", at=PUBLISHED_AT),
        DraftRevision(content=draft.content, reason="corrected", model="corrector-model", at=PUBLISHED_AT),
    ]

    disclosure = PublishedStory.of(draft, PUBLISHED_AT).disclosure

    assert disclosure.ai_written is True
    assert disclosure.models == ["writer-model", "test-model", "corrector-model"]
    assert disclosure.human_edited is False

    draft.revisions.append(DraftRevision(content=draft.content, reason="edited", at=PUBLISHED_AT))

    assert PublishedStory.of(draft, PUBLISHED_AT).disclosure.human_edited is True


def test_a_card_has_no_body_and_no_sources():

    card = PublishedStory.of(create_draft(), PUBLISHED_AT).card().model_dump(mode="json", by_alias=True)

    assert "content" not in card and "body" not in card
    assert "sources" not in card
    assert card["title"] == "Seagrass meadows return to the bay"
    assert card["disclosure"]["aiWritten"] is True

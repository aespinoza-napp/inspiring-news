"""
Approving and publishing a draft, and the public view of what was
published (docs/decisions/writing.md, "Publishing"). Registered in
main.py.

No router-wide API key: the public reader's endpoints must stay open,
as /reader/articles is. Each private endpoint declares the key itself.

The lifecycle, decided here and nowhere else for every channel:

- approve: `draft` -> `approved`. A person's edit sends it back
  (draft_routes.py). Refused while a step runs, or once published.
- publish: `approved` -> `published`, on every channel asked for, all of
  them available - an unavailable one refuses the whole request before
  anything is written. Each channel adds its PublishRecord, replacing
  that channel's earlier one, so `published` lists where the article can
  be read now.
- unpublish: `published` -> `approved`. The public page goes, the
  records go with it; the text stays approved, so it can be published
  again as it is, or edited (back to `draft`) and approved again.

Synchronous, not `DraftStore.run_in_background`: the only channel that
works writes one small file, and a thread would add a busy state, a poll
and a race for milliseconds of work. It still runs under the store's
lock and refuses a busy draft, so it cannot interleave with a review or a
rewrite. A channel that posts to someone else's API, after rendering
media, is minutes of work: that is when publishing moves onto
`run_in_background(id, "publishing", ...)`, which the contract already
names.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.api.routes import require_storage_key
from src.container import get_draft_store, get_publishers
from src.models.writer.draft import ArticleDraft
from src.services.publishing.publisher import Publisher
from src.services.writer.draft_store import DraftBusy, DraftNotFound

logger = logging.getLogger(__name__)

router = APIRouter()

ID_PATTERN = r"^[0-9a-f]{16}$"

NO_DRAFT = "No draft with this id."


class PublishRequest(BaseModel):

    channels: list[str] = Field(min_length=1, max_length=10)


def dump(draft: ArticleDraft) -> dict:

    return draft.model_dump(mode="json", by_alias=True)


def change(draft_id: str, apply) -> dict:
    """`DraftStore.update` with the errors every action here shares."""

    try:
        return dump(get_draft_store().update(draft_id, apply))
    except DraftNotFound:
        raise HTTPException(status_code=404, detail=NO_DRAFT)
    except DraftBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def refuse_busy(draft: ArticleDraft) -> None:

    if draft.busy is not None:
        raise DraftBusy(draft.busy)


# ----------------------------------------------------------------------
# Private: behind the API key, like everything under /drafts
# ----------------------------------------------------------------------


# Not /drafts/channels: draft_routes.py's GET /drafts/{draft_id} is
# registered first and matches any single segment, so "channels" would
# reach it and fail its id pattern with a 422
# (tests/api/test_publish_routes.py holds both).
@router.get("/publishing/channels", dependencies=[Depends(require_storage_key)])
def publishing_channels():
    """Every channel, whether it can publish now and, if not, why."""

    return get_publishers().channels()


@router.post("/drafts/{draft_id}/approve", dependencies=[Depends(require_storage_key)])
def approve_draft(draft_id: str = Path(pattern=ID_PATTERN)):
    """
    The text as it stands is ready to publish. Not gated on a review: the
    panel warns when the current text has none, and the person decides.
    Approving an approved draft changes nothing.
    """

    def apply(draft: ArticleDraft) -> None:

        refuse_busy(draft)

        if draft.status == "published":
            raise HTTPException(status_code=409, detail="This draft is already published.")

        if not draft.content.title.strip() or not draft.content.body.strip():
            raise HTTPException(status_code=422, detail="There is nothing to approve: the draft has no title or no body.")

        draft.status = "approved"

    return change(draft_id, apply)


@router.post("/drafts/{draft_id}/publish", dependencies=[Depends(require_storage_key)])
def publish_draft(request: PublishRequest, draft_id: str = Path(pattern=ID_PATTERN)):
    """
    Publish an approved draft on the channels asked for. Every channel is
    checked before any is used: an unknown one is a 422, an unavailable
    one a 409 with its reason, and in both cases nothing is written.
    """

    publishers = get_publishers()

    chosen: list[Publisher] = []

    for name in dict.fromkeys(request.channels):

        publisher = publishers.get(name)

        if publisher is None:
            raise HTTPException(status_code=422, detail=f"There is no channel called {name!r}.")

        available, reason = publisher.available()

        if not available:
            raise HTTPException(status_code=409, detail=f"{publisher.label} is not available yet. {reason}")

        chosen.append(publisher)

    done: list[tuple[Publisher, ArticleDraft]] = []

    def apply(draft: ArticleDraft) -> None:

        refuse_busy(draft)

        if draft.status == "published":
            raise HTTPException(status_code=409, detail="This draft is already published.")

        if draft.status != "approved":
            raise HTTPException(status_code=409, detail="Approve the draft before publishing it.")

        records = []

        try:
            for publisher in chosen:
                records.append(publisher.publish(draft))
                done.append((publisher, draft))
        except Exception:
            # All or none: a channel that failed must not leave the
            # others live under a draft that still says approved.
            withdraw(done)
            raise

        names = {publisher.name for publisher in chosen}

        draft.published = [record for record in draft.published if record.channel not in names] + records
        draft.status = "published"

    try:
        return change(draft_id, apply)
    except HTTPException:
        raise
    except Exception:
        # Published, then the draft could not be saved: take the page
        # down again rather than leave it public under an approved draft.
        withdraw(done)
        raise


def withdraw(done: list[tuple[Publisher, ArticleDraft]]) -> None:

    for publisher, draft in done:
        try:
            publisher.unpublish(draft)
        except Exception:  # noqa: BLE001 - the original failure is what is raised
            logger.exception("Could not take %s back down from %s", draft.id, publisher.name)

    done.clear()


@router.post("/drafts/{draft_id}/unpublish", dependencies=[Depends(require_storage_key)])
def unpublish_draft(draft_id: str = Path(pattern=ID_PATTERN)):
    """
    Take the article down from every channel it is on, and the web page
    always. The draft goes back to `approved` and its records are
    cleared: `published` says where it can be read now, and now it is
    nowhere.
    """

    publishers = get_publishers()

    def apply(draft: ArticleDraft) -> None:

        refuse_busy(draft)

        if draft.status != "published":
            raise HTTPException(status_code=409, detail="This draft is not published.")

        # The web page goes whatever the records say: it is the one
        # channel that can be public without a record (a crash between
        # writing the page and saving the draft).
        names = dict.fromkeys([publishers.web.name, *(record.channel for record in draft.published)])

        for name in names:

            publisher = publishers.get(name)

            if publisher is None:
                logger.warning("Draft %s has a record on %r, a channel that no longer exists", draft.id, name)
                continue

            publisher.unpublish(draft)

        draft.published = []
        draft.status = "approved"

    return change(draft_id, apply)


# ----------------------------------------------------------------------
# Public: the stories on the reader
#
# Open on purpose, like /reader/articles (tests/api/test_api_key.py,
# OPEN_ENDPOINTS): they return what the public page shows anyone - the
# published snapshot, never the draft.
# ----------------------------------------------------------------------


@router.get("/reader/stories")
def reader_stories(
    topic: str | None = Query(default=None, max_length=100),
    language: str | None = Query(default=None, max_length=8),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
):
    """
    The articles this newsroom wrote and published, newest first, as
    cards (no body). Filter by `topic` (the article's own) and
    `language`; paged like /reader/articles, with facet counts.
    """

    return get_publishers().web.stories(topic=topic, language=language, offset=offset, limit=limit)


@router.get("/reader/stories/{story_id}")
def reader_story(story_id: str = Path(pattern=ID_PATTERN)):
    """One published article, as it was when it was published."""

    story = get_publishers().web.story(story_id)

    if story is None:
        raise HTTPException(status_code=404, detail="No published story with this id.")

    return story

"""
/drafts: the newsroom's articles in progress (docs/decisions/writing.md).

Reading a draft and a person's edit live here, beside creating one (the
writer). Reviewing is in review_routes.py and publishing in
publish_routes.py, so each stage of the flow owns its own module.

Every endpoint takes the API key: a draft is unpublished work, and
creating or revising one costs minutes of the model's time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.routes import require_storage_key
from src.container import get_draft_store
from src.models.writer.draft import ArticleDraft, DraftContent, DraftSummary
from src.services.writer.draft_store import DraftBusy, DraftNotFound, revise

router = APIRouter(prefix="/drafts", dependencies=[Depends(require_storage_key)])

DRAFT_ID_PATTERN = r"^[0-9a-f]{16}$"


def dump(draft: ArticleDraft) -> dict:

    return draft.model_dump(mode="json", by_alias=True)


def draft_or_404(draft_id: str) -> ArticleDraft:

    draft = get_draft_store().get(draft_id)

    if draft is None:
        raise HTTPException(status_code=404, detail="No draft with this id.")

    return draft


def busy_409(exc: DraftBusy) -> HTTPException:

    return HTTPException(status_code=409, detail=str(exc))


@router.get("")
def list_drafts():
    """Every draft, most recently changed first, without bodies."""

    return [
        DraftSummary.of(draft).model_dump(mode="json", by_alias=True)
        for draft in get_draft_store().list()
    ]


@router.get("/{draft_id}")
def get_draft(draft_id: str = Path(pattern=DRAFT_ID_PATTERN)):
    """One draft, whole. Polled by the page while `busy` is set."""

    return dump(draft_or_404(draft_id))


@router.put("/{draft_id}/content")
def edit_draft(content: DraftContent, draft_id: str = Path(pattern=DRAFT_ID_PATTERN)):
    """
    A person's edit: a new revision, and the review cleared - it read the
    old text. Refused while a background step runs on the draft (its
    result would land on top of the edit) and once it is published
    (the live article would change with no one deciding to republish).
    An approved draft goes back to `draft`: what was approved was the old
    text.
    """

    def apply(draft: ArticleDraft) -> None:

        if draft.busy is not None:
            raise DraftBusy(draft.busy)

        if draft.status == "published":
            raise HTTPException(status_code=409, detail="This draft is published; unpublish it before editing.")

        revise(draft, content, "edited")
        draft.status = "draft"

    try:
        return dump(get_draft_store().update(draft_id, apply))
    except DraftNotFound:
        raise HTTPException(status_code=404, detail="No draft with this id.")
    except DraftBusy as exc:
        raise busy_409(exc)

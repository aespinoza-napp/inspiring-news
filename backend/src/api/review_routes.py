"""
Reviewing a draft: the corrector's metrics and its proposed corrections
(docs/decisions/writing.md, "Review"). Registered in main.py.

- `POST /drafts/{id}/review` starts the review in the background (202,
  the draft comes back `busy: "reviewing"`; the page polls it). The
  review lands on `draft.review` - unless the content it read has changed
  by the time it finishes.
- `POST /drafts/{id}/accept-correction` replaces the content with the
  review's proposal, as a `"corrected"` revision. Synchronous: it is a
  copy, not a model call.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.routes import require_storage_key
from src.container import get_draft_reviewer, get_draft_store
from src.models.writer.draft import ArticleDraft
from src.services.writer.draft_store import DRAFT_ID, DraftBusy, DraftNotFound, revise

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drafts", dependencies=[Depends(require_storage_key)])

# The store's own rule for an id, so the route and the store cannot
# disagree on what names a draft.
DRAFT_ID_PATTERN = DRAFT_ID.pattern

NOT_FOUND = "No draft with this id."

STALE = (
    "The draft changed while it was being reviewed, so the review described "
    "text that is no longer there and was not kept. Review it again."
)


class StaleReview(RuntimeError):
    """The content a review read is not the draft's content any more."""


def dump(draft: ArticleDraft) -> dict:

    return draft.model_dump(mode="json", by_alias=True)


@router.post("/{draft_id}/review", status_code=202)
def review_draft(draft_id: str = Path(pattern=DRAFT_ID_PATTERN)):
    """
    Review the draft's current content: nine metrics and a proposed
    correction. 202 with the draft marked busy; 404 for an unknown draft,
    409 while another step runs on it. A failure - the model or
    inference/ unreachable, the draft edited meanwhile - is kept in the
    draft's `error`.
    """

    store = get_draft_store()
    reviewer = get_draft_reviewer()

    def work() -> None:

        draft = store.get(draft_id)

        if draft is None:
            # Deleted after it was claimed; nothing to review.
            return

        read = draft.content.model_copy(deep=True)

        review = reviewer.review(draft)

        def attach(current: ArticleDraft) -> None:

            # A review describes the text it read. Edits are refused while
            # the draft is busy, but this is the one place that would
            # otherwise put a review on top of different text for good:
            # nothing clears it until the next change.
            if current.content != read:
                raise StaleReview(STALE)

            current.review = review

        store.update(draft_id, attach)

    try:
        claimed = store.run_in_background(draft_id, "reviewing", work)
    except DraftNotFound:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    except DraftBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return dump(claimed)


@router.post("/{draft_id}/accept-correction")
def accept_correction(draft_id: str = Path(pattern=DRAFT_ID_PATTERN)):
    """
    Make the review's proposal the draft's content: a `"corrected"`
    revision by the review's model. The outgoing revision keeps the
    review, and the draft's is cleared - it described the old text
    (`revise`). An approved draft goes back to `draft`, as after a
    person's edit: what was approved was the old text.

    409 while a step runs, once the draft is published, and when there is
    no proposal to accept.
    """

    def apply(draft: ArticleDraft) -> None:

        if draft.busy is not None:
            raise DraftBusy(draft.busy)

        if draft.status == "published":
            raise HTTPException(
                status_code=409,
                detail="This draft is published; unpublish it before changing it.",
            )

        if draft.review is None or draft.review.corrected is None:
            raise HTTPException(
                status_code=409,
                detail="There is no proposed correction to accept. Review the draft first.",
            )

        revise(draft, draft.review.corrected, "corrected", draft.review.model)
        draft.status = "draft"

    try:
        return dump(get_draft_store().update(draft_id, apply))
    except DraftNotFound:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    except DraftBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))

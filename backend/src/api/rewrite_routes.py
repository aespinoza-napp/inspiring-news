"""
Rewriting a draft whose review fell short of the metrics expected, and
going back to an earlier text (docs/decisions/writing.md, "Rewriting").
Registered in main.py.

- `POST /drafts/{id}/rewrite` starts the rewrite in the background (202,
  the draft comes back `busy: "rewriting"`; the page polls it). Each round
  is a `"rewritten"` revision with its own review
  (src/services/writer/rewriter.py).
- `POST /drafts/{id}/restore` puts an earlier revision's text and review
  back, as a new `"restored"` revision. Synchronous: it is a copy.
- `GET /writing/targets`: the default targets and the bounds of a
  rewrite request, for the page to judge each metric before anyone asks
  for one. Not `/drafts/targets`: draft_routes.py's `GET
  /drafts/{draft_id}` is registered first and answers any single segment
  with a 422 on its id pattern - what moved the publishing stage's
  channels to /publishing/channels.

No router-wide key, so `/writing/targets` and `/drafts/...` can share the
module: each endpoint declares `require_storage_key` itself, as
publish_routes.py does.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import ConfigDict, Field

from src.api.routes import require_storage_key
from src.config.thresholds import RewriteTargetOverrides, RewriteTargets
from src.container import get_draft_rewriter, get_draft_store
from src.models.writer.draft import ArticleDraft, CamelModel
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY
from src.services.writer.draft_store import DRAFT_ID, DraftBusy, DraftNotFound, revise
from src.services.writer.rewriter import (
    DEFAULT_ROUNDS,
    MAX_EXTRA_INSTRUCTIONS_CHARS,
    MAX_ROUNDS,
    NO_REVIEW,
    PUBLISHED,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DRAFT_ID_PATTERN = DRAFT_ID.pattern

NOT_FOUND = "No draft with this id."


class RewriteRequest(CamelModel):
    """
    Everything optional: `{}` rewrites once against the default targets,
    with the draft's own instructions.
    """

    model_config = ConfigDict(extra="forbid")

    # Under the review's metric keys: {"factConsistency": 90}.
    targets: RewriteTargetOverrides | None = None

    # Extra guidance for this rewrite, beside the draft's instructions.
    instructions: str = Field("", max_length=MAX_EXTRA_INSTRUCTIONS_CHARS)

    max_rounds: int = Field(DEFAULT_ROUNDS, ge=1, le=MAX_ROUNDS)


class RestoreRequest(CamelModel):

    model_config = ConfigDict(extra="forbid")

    # 0-based, into the draft's `revisions`, oldest first.
    revision: int = Field(ge=0)


def dump(draft: ArticleDraft) -> dict:

    return draft.model_dump(mode="json", by_alias=True)


def refuse(draft: ArticleDraft) -> None:
    """What both actions refuse, in the order a person would want to hear it."""

    if draft.busy is not None:
        raise DraftBusy(draft.busy)

    if draft.status == "published":
        raise HTTPException(status_code=409, detail=PUBLISHED)


@router.get("/writing/targets", dependencies=[Depends(require_storage_key)])
def writing_targets():
    """
    The default target of each review metric, and what a rewrite request
    may ask for. The page judges a review against these until the person
    changes them for a rewrite; an unscored metric is told by
    `unscoredSummary`, which the review puts in its summary.
    """

    return {
        "targets": RewriteTargets().by_metric(),
        "rounds": {"default": DEFAULT_ROUNDS, "max": MAX_ROUNDS},
        "maxInstructionsChars": MAX_EXTRA_INSTRUCTIONS_CHARS,
        "unscoredSummary": UNAVAILABLE_SUMMARY,
    }


@router.post(
    "/drafts/{draft_id}/rewrite",
    status_code=202,
    dependencies=[Depends(require_storage_key)],
)
def rewrite_draft(request: RewriteRequest | None = None, draft_id: str = Path(pattern=DRAFT_ID_PATTERN)):
    """
    Rewrite the draft's current text, guided by the metrics of its review
    that are below target; then review the new text. 202 with the draft
    busy. 404 for an unknown draft; 409 while a step runs on it, once it
    is published, and when the current text has no review - a rewrite is
    guided by one, so ask for it first. A rewrite that cannot be kept, or
    a model that cannot be reached, is reported in the draft's `error`.
    """

    request = request or RewriteRequest()

    targets = RewriteTargets.resolve(request.targets)

    store = get_draft_store()

    draft = store.get(draft_id)

    if draft is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)

    try:
        refuse(draft)
    except DraftBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if draft.review is None:
        raise HTTPException(status_code=409, detail=NO_REVIEW)

    try:
        claimed = get_draft_rewriter().start(
            store,
            draft_id,
            targets,
            request.instructions.strip(),
            request.max_rounds,
        )
    except DraftNotFound:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    except DraftBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return dump(claimed)


@router.post("/drafts/{draft_id}/restore", dependencies=[Depends(require_storage_key)])
def restore_revision(request: RestoreRequest, draft_id: str = Path(pattern=DRAFT_ID_PATTERN)):
    """
    Put an earlier revision's text back, with the review of that text, as
    a new `"restored"` revision under the model that wrote it - so nothing
    is lost: the text it replaces stays in the history, with its review.
    An approved draft goes back to `draft`, as after any change of text.

    404 for an unknown draft; 422 for a revision it does not have; 409
    while a step runs on it, once it is published, and when that text is
    already the current one.
    """

    def apply(draft: ArticleDraft) -> None:

        refuse(draft)

        if request.revision >= len(draft.revisions):
            raise HTTPException(
                status_code=422,
                detail=f"This draft has {len(draft.revisions)} revision(s); there is no revision {request.revision}.",
            )

        earlier = draft.revisions[request.revision]

        if earlier.content == draft.content:
            raise HTTPException(status_code=409, detail="That revision's text is already the current text.")

        # Copies: the restored revision and the one it came from must not
        # share objects that a later change to one would alter in both.
        content = earlier.content.model_copy(deep=True)
        review = earlier.review.model_copy(deep=True) if earlier.review is not None else None

        revise(draft, content, "restored", earlier.model)

        # The review of that text describes this text: it is the same text.
        draft.review = review
        draft.status = "draft"

    try:
        return dump(get_draft_store().update(draft_id, apply))
    except DraftNotFound:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    except DraftBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc))

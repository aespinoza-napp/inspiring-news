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
from pydantic import Field, model_validator

from src.api.routes import require_storage_key
from src.config.thresholds import WriterThresholdOverrides, WriterThresholds
from src.container import get_draft_store, get_draft_writer
from src.models.writer.draft import ArticleDraft, CamelModel, DraftContent, DraftSummary, Language
from src.services.writer.draft_store import DraftBusy, DraftNotFound, revise

router = APIRouter(prefix="/drafts", dependencies=[Depends(require_storage_key)])

DRAFT_ID_PATTERN = r"^[0-9a-f]{16}$"

# The editor's indications go into the prompt whole. A page of them is
# plenty; more is a second article competing with the sources for the
# model's context.
MAX_INSTRUCTIONS_CHARS = 4000


class NewDraftRequest(CamelModel):
    """
    Which analysed article, by its reader id or its URL (the reader's own
    matching: host and path, so a tracking parameter does not matter),
    the language to write in, and the editor's indications.
    """

    article_id: str | None = Field(None, pattern=DRAFT_ID_PATTERN)

    article_url: str | None = Field(None, max_length=2048)

    language: Language

    instructions: str = Field("", max_length=MAX_INSTRUCTIONS_CHARS)

    # Per-draft overrides, snake_case like /analyze's (WriterThresholds).
    thresholds: WriterThresholdOverrides | None = None

    @model_validator(mode="after")
    def one_article(self) -> "NewDraftRequest":

        if bool(self.article_id) == bool((self.article_url or "").strip()):
            raise ValueError("Give the analysed article's id or its URL - one of the two.")

        return self


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


@router.post("", status_code=202)
def create_draft(request: NewDraftRequest):
    """
    Write a new article from an analysed one (docs/decisions/writing.md,
    "Writing"). Answers at once with the draft `busy: "generating"`,
    holding only the analysed article's headline; the page polls it while
    related news is found and the model writes - minutes on a CPU. A
    failure lands in the draft's `error`.

    Only articles the reader publishes can be written from: anything else
    is a 404 here, before a draft exists.
    """

    writer = get_draft_writer()

    article = writer.find_article(
        article_id=request.article_id,
        article_url=(request.article_url or "").strip() or None,
    )

    if article is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No published article matches. A draft starts from an article the reader "
                "publishes: analysed, admitted, and not judged FALSE or MISLEADING."
            ),
        )

    thresholds = WriterThresholds.resolve(request.thresholds)

    store = get_draft_store()

    draft = store.save(writer.new_draft(article, request.language, request.instructions.strip()))

    try:
        return dump(writer.start(store, draft.id, article, thresholds))
    except DraftBusy as exc:  # a fresh draft cannot be busy; kept for the contract
        raise busy_409(exc)


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

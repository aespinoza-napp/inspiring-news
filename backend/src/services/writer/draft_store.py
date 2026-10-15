"""
Where drafts live: one JSON file per draft under `settings.DRAFTS_PATH`.

Not the lake. The lake is the record of what the pipeline found and
checked (docs/decisions/storage.md); a draft is the newsroom's own work in
progress, edited in place many times. Kept beside it, in the same storage
root, so a backup of one is a backup of both.

Every change goes through `update`, a read-modify-write under one lock:
generation, review, rewriting and publishing run in background threads
while a person can edit the same draft, and two writers that each read,
change and save would silently drop one change.

Background work follows one pattern (`run_in_background`): mark the draft
`busy`, do the work in a thread, record a failure in `error`, always clear
`busy`. A second step on a busy draft is refused rather than queued -
the page shows what is running and the person tries again.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.models.writer.draft import ArticleDraft, Busy, DraftContent, DraftRevision, RevisionReason

logger = logging.getLogger(__name__)

DRAFT_ID = re.compile(r"^[0-9a-f]{16}$")

INTERRUPTED = "Interrupted: the server restarted while this was running. Try again."


class DraftNotFound(LookupError):
    pass


class DraftBusy(RuntimeError):
    """A background step is already running on this draft."""

    def __init__(self, busy: str):
        super().__init__(f"This draft is busy: {busy}.")
        self.busy = busy


def now() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_draft_id() -> str:

    return secrets.token_hex(8)


def revise(
    draft: ArticleDraft,
    content: DraftContent,
    reason: RevisionReason,
    model: str | None = None,
) -> None:
    """
    Replace a draft's content, keeping the history: the outgoing revision
    keeps the review of its own text, a new revision is appended, and the
    draft's `review` is cleared - it described the old text.
    """

    if draft.revisions and draft.review is not None and draft.revisions[-1].review is None:
        draft.revisions[-1].review = draft.review

    draft.revisions.append(DraftRevision(content=content, reason=reason, model=model, at=now()))
    draft.content = content
    draft.review = None


class DraftStore:

    def __init__(self, root: Path):

        self.root = Path(root)
        self._lock = threading.RLock()

        # This process just started, so nothing is running: a draft still
        # marked busy was cut off by the last restart.
        self._clear_stale_busy()

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def _path(self, draft_id: str) -> Path:

        # The id reaches here from a URL: never let it name another path.
        if not DRAFT_ID.fullmatch(draft_id or ""):
            raise DraftNotFound(draft_id)

        return self.root / f"{draft_id}.json"

    def get(self, draft_id: str) -> ArticleDraft | None:

        try:
            path = self._path(draft_id)
        except DraftNotFound:
            return None

        if not path.exists():
            return None

        return ArticleDraft.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[ArticleDraft]:
        """Every draft, most recently changed first."""

        if not self.root.exists():
            return []

        drafts = []

        for path in self.root.glob("*.json"):

            try:
                drafts.append(ArticleDraft.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError) as exc:
                # One unreadable file must not hide every other draft.
                logger.warning("Skipping unreadable draft %s: %s", path.name, exc)

        return sorted(drafts, key=lambda draft: draft.updated_at, reverse=True)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def save(self, draft: ArticleDraft) -> ArticleDraft:

        with self._lock:

            path = self._path(draft.id)
            path.parent.mkdir(parents=True, exist_ok=True)

            draft.updated_at = now()

            # Written beside and renamed over: a crash mid-write leaves the
            # old draft, never half a file.
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(draft.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, path)

            return draft

    def update(self, draft_id: str, change: Callable[[ArticleDraft], None]) -> ArticleDraft:
        """Read, change in place, save - atomically with every other update."""

        with self._lock:

            draft = self.get(draft_id)

            if draft is None:
                raise DraftNotFound(draft_id)

            change(draft)

            return self.save(draft)

    # ------------------------------------------------------------------
    # Background work
    # ------------------------------------------------------------------

    def claim(self, draft_id: str, busy: Busy) -> ArticleDraft:
        """Mark a draft busy, or raise DraftBusy if something already runs."""

        def mark(draft: ArticleDraft) -> None:

            if draft.busy is not None:
                raise DraftBusy(draft.busy)

            draft.busy = busy
            draft.error = None

        return self.update(draft_id, mark)

    def release(self, draft_id: str, error: str | None = None) -> None:

        def clear(draft: ArticleDraft) -> None:
            draft.busy = None
            draft.error = error

        try:
            self.update(draft_id, clear)
        except DraftNotFound:
            # Deleted while it ran; nothing to release.
            pass

    def run_in_background(
        self,
        draft_id: str,
        busy: Busy,
        work: Callable[[], None],
        *,
        wait: bool = False,
    ) -> ArticleDraft:
        """
        Claim the draft (raising DraftBusy or DraftNotFound now, in the
        request), then run `work` in a thread and release the draft when
        it ends. `work` saves its own results through `update`. A failure
        is logged and its message kept in `error` for the page.

        `wait=True` runs it in the caller's thread instead - for tests and
        the CLI, where a thread only adds a race.
        """

        claimed = self.claim(draft_id, busy)

        def run() -> None:

            error = None

            try:
                work()
            except Exception as exc:  # noqa: BLE001 - reported on the draft
                logger.exception("Draft %s: %s failed", draft_id, busy)
                error = f"{busy} failed: {exc}"

            self.release(draft_id, error)

        if wait:
            run()
            return self.get(draft_id) or claimed

        threading.Thread(target=run, name=f"draft-{busy}-{draft_id}", daemon=True).start()

        return claimed

    def _clear_stale_busy(self) -> None:

        for draft in self.list():

            if draft.busy is not None:
                self.release(draft.id, INTERRUPTED)

"""
The draft store every stage of the writing flow shares
(src/services/writer/draft_store.py).
"""

import json
import threading

import pytest

from src.models.writer.draft import ArticleDraft, DraftContent
from src.services.writer.draft_store import (
    INTERRUPTED,
    DraftBusy,
    DraftNotFound,
    DraftStore,
    revise,
)
from tests.factories import create_draft


def test_a_saved_draft_reads_back_whole(draft_store):

    draft = draft_store.save(create_draft())

    assert draft_store.get(draft.id) == draft


def test_the_file_is_camel_case_like_the_api(draft_store):

    draft = draft_store.save(create_draft())

    stored = json.loads((draft_store.root / f"{draft.id}.json").read_text(encoding="utf-8"))

    assert {"sourceArticleId", "factChecks", "createdAt"} <= set(stored)
    assert "source_article_id" not in stored


def test_an_id_that_is_not_a_draft_id_names_no_file(draft_store):

    # It comes from a URL: "../" must never reach the filesystem.
    assert draft_store.get("../../etc/passwd") is None

    with pytest.raises(DraftNotFound):
        draft_store.update("../secrets", lambda draft: None)


def test_the_list_is_most_recently_changed_first(draft_store):

    first = draft_store.save(create_draft())
    second = draft_store.save(create_draft())

    draft_store.update(first.id, lambda draft: setattr(draft, "instructions", "changed"))

    # Seconds resolution: equal stamps keep either order, so compare sets
    # when the clock did not tick, and the order when it did.
    listed = [draft.id for draft in draft_store.list()]

    assert set(listed) == {first.id, second.id}
    assert draft_store.get(first.id).updated_at >= draft_store.get(second.id).updated_at


def test_an_unreadable_file_does_not_hide_the_others(draft_store):

    draft = draft_store.save(create_draft())

    (draft_store.root / "ffffffffffffffff.json").write_text("{not json", encoding="utf-8")

    assert [listed.id for listed in draft_store.list()] == [draft.id]


def test_revise_keeps_the_old_review_with_the_old_text():

    from src.models.writer.draft import DraftReview

    draft = create_draft()
    review = DraftReview(reviewed_at="2026-10-15T08:00:00+00:00")
    draft.review = review

    revise(draft, DraftContent(title="New title"), "edited")

    assert draft.content.title == "New title"
    assert draft.review is None
    assert draft.revisions[-2].review == review
    assert [revision.reason for revision in draft.revisions] == ["generated", "edited"]


def test_a_busy_draft_refuses_a_second_step(draft_store):

    draft = draft_store.save(create_draft())

    draft_store.claim(draft.id, "reviewing")

    with pytest.raises(DraftBusy):
        draft_store.claim(draft.id, "rewriting")


def test_background_work_clears_busy_and_keeps_its_result(draft_store):

    draft = draft_store.save(create_draft())

    def work():
        draft_store.update(draft.id, lambda d: setattr(d, "instructions", "done"))

    result = draft_store.run_in_background(draft.id, "reviewing", work, wait=True)

    assert result.busy is None
    assert result.error is None
    assert result.instructions == "done"


def test_a_failure_is_kept_for_the_page_and_busy_is_cleared(draft_store):

    draft = draft_store.save(create_draft())

    def work():
        raise RuntimeError("model said no")

    result = draft_store.run_in_background(draft.id, "generating", work, wait=True)

    assert result.busy is None
    assert "model said no" in result.error


def test_the_thread_runs_and_releases(draft_store):

    draft = draft_store.save(create_draft())
    done = threading.Event()

    def work():
        draft_store.update(draft.id, lambda d: setattr(d, "instructions", "threaded"))
        done.set()

    claimed = draft_store.run_in_background(draft.id, "rewriting", work)

    assert claimed.busy == "rewriting"
    assert done.wait(5)

    # release() runs just after work() returns, on the same thread.
    for _ in range(50):
        if draft_store.get(draft.id).busy is None:
            break
        threading.Event().wait(0.02)

    assert draft_store.get(draft.id).busy is None
    assert draft_store.get(draft.id).instructions == "threaded"


def test_a_restart_clears_a_busy_flag_the_last_process_left(tmp_path):

    store = DraftStore(tmp_path)
    draft = store.save(create_draft())
    store.claim(draft.id, "generating")

    reopened = DraftStore(tmp_path)

    assert reopened.get(draft.id).busy is None
    assert reopened.get(draft.id).error == INTERRUPTED


def test_either_spelling_loads():

    draft = create_draft()

    by_alias = draft.model_dump(mode="json", by_alias=True)
    by_name = draft.model_dump(mode="json")

    assert ArticleDraft.model_validate(by_alias) == ArticleDraft.model_validate(by_name)

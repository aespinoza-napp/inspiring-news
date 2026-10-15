"""
/drafts/{id}/restore (src/api/rewrite_routes.py): an earlier revision's
text and review back, as a new revision, so nothing is lost.
"""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.config.settings import settings
from src.main import app
from src.models.writer.draft import ArticleDraft
from src.services.writer.draft_store import revise
from tests.services.writer.rewrite_fakes import GOOD_BODY, a_review, content, reviewed_draft

client = TestClient(app)


def rewritten_twice(**kwargs) -> ArticleDraft:
    """
    generated (reviewed at 80) -> rewritten (reviewed at 40) -> rewritten
    (reviewed at 60, current): a rewrite that scored worse than the text
    it replaced, then another.
    """

    draft = reviewed_draft(review=a_review(80, model="first-reviewer"), **kwargs)

    revise(draft, content(GOOD_BODY), "rewritten", "writer-model")
    draft.review = a_review(40, model="second-reviewer")

    revise(draft, content(GOOD_BODY.replace("rose", "grew")), "rewritten", "other-writer")
    draft.review = a_review(60, model="third-reviewer")

    return draft


def restore(draft_id, revision):

    return client.post(f"/drafts/{draft_id}/restore", json={"revision": revision})


def test_restore_reapplies_an_earlier_revision_as_a_new_one(draft_store):

    draft = draft_store.save(rewritten_twice(status="approved"))
    first = draft.revisions[0]

    response = restore(draft.id, 0)

    assert response.status_code == 200

    stored = draft_store.get(draft.id)

    # The text and the review of that text, back.
    assert stored.content == first.content
    assert stored.review == first.review
    assert stored.review.model == "first-reviewer"

    # A new revision, under the model that wrote the text; nothing lost.
    assert [revision.reason for revision in stored.revisions] == ["generated", "rewritten", "rewritten", "restored"]
    assert stored.revisions[-1].model == first.model
    assert stored.revisions[-1].content == first.content
    # The text it replaced keeps its own review.
    assert stored.revisions[2].review.model == "third-reviewer"
    assert stored.revisions[2].content.body == GOOD_BODY.replace("rose", "grew")

    # What was approved was another text.
    assert stored.status == "draft"

    assert response.json()["revisions"][-1]["reason"] == "restored"


def test_a_restored_text_can_be_restored_away_again(draft_store):

    draft = draft_store.save(rewritten_twice())

    restore(draft.id, 0)
    response = restore(draft.id, 2)

    assert response.status_code == 200

    stored = draft_store.get(draft.id)

    assert stored.content.body == GOOD_BODY.replace("rose", "grew")
    assert stored.review.model == "third-reviewer"
    # And the restored revision kept the review it was restored with.
    assert stored.revisions[3].review.model == "first-reviewer"


def test_a_revision_never_reviewed_comes_back_without_a_review(draft_store):

    draft = rewritten_twice()
    draft.revisions[1].review = None
    draft = draft_store.save(draft)

    restore(draft.id, 1)

    assert draft_store.get(draft.id).review is None


def test_restoring_the_current_text_is_refused(draft_store):

    draft = draft_store.save(rewritten_twice())

    response = restore(draft.id, 2)

    assert response.status_code == 409
    assert "already the current text" in response.json()["detail"]
    assert len(draft_store.get(draft.id).revisions) == 3


def test_a_busy_or_published_draft_is_not_restored(draft_store):

    busy = draft_store.save(rewritten_twice())
    draft_store.claim(busy.id, "rewriting")

    published = draft_store.save(rewritten_twice(status="published"))

    for draft in (busy, published):
        assert restore(draft.id, 0).status_code == 409
        assert draft_store.get(draft.id).content == draft.content


def test_a_revision_the_draft_does_not_have(draft_store):

    draft = draft_store.save(rewritten_twice())

    assert restore(draft.id, 3).status_code == 422
    assert restore(draft.id, -1).status_code == 422
    assert client.post(f"/drafts/{draft.id}/restore", json={}).status_code == 422
    assert client.post(f"/drafts/{draft.id}/restore", json={"revision": 0, "reason": "x"}).status_code == 422


def test_an_unknown_draft(draft_store):

    assert restore("0000000000000000", 0).status_code == 404
    assert restore("nope", 0).status_code == 422


def test_restore_takes_the_api_key(draft_store, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    draft = draft_store.save(rewritten_twice())

    assert restore(draft.id, 0).status_code == 401
    assert draft_store.get(draft.id).content == draft.content

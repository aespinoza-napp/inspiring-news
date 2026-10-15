"""
/drafts: reading drafts and a person's edit (src/api/draft_routes.py).
"""

from fastapi.testclient import TestClient

from src.main import app
from tests.factories import create_draft

client = TestClient(app)


def test_the_list_has_no_bodies(draft_store):

    draft = draft_store.save(create_draft())

    response = client.get("/drafts")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": draft.id,
            "sourceArticleId": draft.source_article_id,
            "language": "en",
            "title": draft.content.title,
            "status": "draft",
            "busy": None,
            "createdAt": draft.created_at,
            "updatedAt": draft.updated_at,
        }
    ]


def test_one_draft_is_whole_and_camel_case(draft_store):

    draft = draft_store.save(create_draft())

    body = client.get(f"/drafts/{draft.id}").json()

    assert body["content"]["title"] == draft.content.title
    assert body["sources"][0]["origin"] == "analysed"
    assert body["factChecks"][0]["sourceUrls"] == ["https://example.org/seagrass"]


def test_an_unknown_or_malformed_id(draft_store):

    assert client.get("/drafts/0000000000000000").status_code == 404
    assert client.get("/drafts/not-an-id").status_code == 422


def test_an_edit_is_a_revision_and_clears_the_review(draft_store):

    from src.models.writer.draft import DraftReview

    draft = create_draft(status="approved")
    draft.review = DraftReview(reviewed_at="2026-10-15T08:00:00+00:00")
    draft_store.save(draft)

    response = client.put(
        f"/drafts/{draft.id}/content",
        json={"title": "Edited", "subtitle": "By a person", "body": "New text [1]."},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["content"]["title"] == "Edited"
    assert body["review"] is None
    assert body["status"] == "draft"
    assert [revision["reason"] for revision in body["revisions"]] == ["generated", "edited"]
    assert body["revisions"][0]["review"] is not None


def test_an_edit_waits_for_a_running_step(draft_store):

    draft = draft_store.save(create_draft())
    draft_store.claim(draft.id, "rewriting")

    response = client.put(f"/drafts/{draft.id}/content", json={"title": "Too soon"})

    assert response.status_code == 409
    assert draft_store.get(draft.id).content.title == draft.content.title


def test_a_published_draft_is_not_edited_in_place(draft_store):

    draft = draft_store.save(create_draft(status="published"))

    response = client.put(f"/drafts/{draft.id}/content", json={"title": "Silently changed"})

    assert response.status_code == 409

"""
Approving, publishing and unpublishing a draft, and the public stories
(src/api/publish_routes.py).
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.config.settings import settings
from src.main import app
from src.models.writer.draft import DraftContent, DraftMetadata
from tests.factories import create_draft

client = TestClient(app)

KEY = "s3cret"


@pytest.fixture
def publishers(draft_store, monkeypatch):
    """
    The container's channels over tmp_path, beside the test's draft store,
    so nothing is written under settings.DRAFTS_PATH.
    """

    import src.container as container
    from src.services.publishing.registry import Publishers
    from src.services.publishing.social import InstagramPublisher, TikTokPublisher
    from src.services.publishing.web import WebPublisher

    registry = Publishers(
        WebPublisher(draft_store.root / "published"),
        [TikTokPublisher(), InstagramPublisher()],
    )

    monkeypatch.setattr(container, "_publishers", registry)

    return registry


def publish(draft_id, channels=("web",)):

    return client.post(f"/drafts/{draft_id}/publish", json={"channels": list(channels)})


# ----------------------------------------------------------------------
# Channels
# ----------------------------------------------------------------------


def test_the_channels_say_which_can_publish_and_why_not(publishers):

    response = client.get("/publishing/channels")

    assert response.status_code == 200

    channels = {channel["name"]: channel for channel in response.json()}

    assert list(channels) == ["web", "tiktok", "instagram"]
    assert channels["web"]["available"] is True
    assert channels["tiktok"]["available"] is False
    assert "video.publish" in channels["tiktok"]["reason"]
    assert channels["instagram"]["available"] is False
    assert "professional" in channels["instagram"]["reason"]


def test_the_channels_are_not_under_drafts_because_the_id_route_would_take_them(publishers, draft_store):
    """
    GET /drafts/{draft_id} (draft_routes.py) is registered before this
    module and matches any one segment; FastAPI does not fall through to
    a later route when the id pattern fails, it answers 422. So the
    channels live at /publishing/channels, and the drafts proxy - which
    only forwards /drafts/<16 hex> - needs no change.
    """

    assert client.get("/drafts/channels").status_code == 422
    assert client.get("/publishing/channels").status_code == 200


# ----------------------------------------------------------------------
# Approve
# ----------------------------------------------------------------------


def test_approve_moves_a_draft_to_approved(publishers, draft_store):

    draft = draft_store.save(create_draft())

    response = client.post(f"/drafts/{draft.id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert draft_store.get(draft.id).status == "approved"

    # Again: nothing changes, nothing fails.
    assert client.post(f"/drafts/{draft.id}/approve").json()["status"] == "approved"


def test_approve_does_not_require_a_review(publishers, draft_store):
    """The panel warns; the person decides."""

    draft = draft_store.save(create_draft())

    assert draft.review is None
    assert client.post(f"/drafts/{draft.id}/approve").status_code == 200


def test_approve_is_refused_while_busy_or_once_published(publishers, draft_store):

    busy = draft_store.save(create_draft(busy="reviewing"))
    published = draft_store.save(create_draft(status="published"))

    assert client.post(f"/drafts/{busy.id}/approve").status_code == 409
    assert client.post(f"/drafts/{published.id}/approve").status_code == 409

    assert draft_store.get(busy.id).status == "draft"


def test_an_empty_draft_cannot_be_approved(publishers, draft_store):

    draft = draft_store.save(create_draft(content=DraftContent(title="A title", body="  ")))

    assert client.post(f"/drafts/{draft.id}/approve").status_code == 422


def test_unknown_and_malformed_ids(publishers, draft_store):

    for action in ("approve", "unpublish"):
        assert client.post(f"/drafts/0000000000000000/{action}").status_code == 404
        assert client.post(f"/drafts/not-an-id/{action}").status_code == 422

    assert publish("0000000000000000").status_code == 404
    assert publish("not-an-id").status_code == 422


# ----------------------------------------------------------------------
# Publish
# ----------------------------------------------------------------------


def test_publish_requires_an_approved_draft(publishers, draft_store):

    draft = draft_store.save(create_draft())

    response = publish(draft.id)

    assert response.status_code == 409
    assert "Approve" in response.json()["detail"]
    assert draft_store.get(draft.id).status == "draft"
    assert client.get(f"/reader/stories/{draft.id}").status_code == 404


def test_publish_to_the_web(publishers, draft_store):

    draft = draft_store.save(create_draft(status="approved"))

    response = publish(draft.id)

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "published"
    assert body["busy"] is None
    assert len(body["published"]) == 1

    record = body["published"][0]
    assert record["channel"] == "web"
    assert record["url"] == f"/reader/stories/{draft.id}"

    story = client.get(f"/reader/stories/{draft.id}")
    assert story.status_code == 200
    assert story.json()["content"]["title"] == draft.content.title
    assert story.json()["publishedAt"] == record["at"]


def test_publish_is_refused_while_busy(publishers, draft_store):

    draft = draft_store.save(create_draft(status="approved", busy="rewriting"))

    assert publish(draft.id).status_code == 409
    assert client.get(f"/reader/stories/{draft.id}").status_code == 404


def test_a_published_draft_is_not_published_twice(publishers, draft_store):

    draft = draft_store.save(create_draft(status="approved"))
    publish(draft.id)

    assert publish(draft.id).status_code == 409
    assert len(draft_store.get(draft.id).published) == 1


@pytest.mark.parametrize("channel, label", [("tiktok", "TikTok"), ("instagram", "Instagram")])
def test_tiktok_and_instagram_are_refused_with_their_reason_and_nothing_is_written(
    publishers, draft_store, channel, label
):

    draft = draft_store.save(create_draft(status="approved"))

    # Asked together with the web: refused before the web is written.
    response = publish(draft.id, ["web", channel])

    assert response.status_code == 409

    _, reason = publishers.get(channel).available()
    assert response.json()["detail"] == f"{label} is not available yet. {reason}"

    stored = draft_store.get(draft.id)
    assert stored.status == "approved"
    assert stored.published == []
    assert not publishers.web.root.exists() or list(publishers.web.root.iterdir()) == []
    assert client.get("/reader/stories").json()["total"] == 0


def test_an_unknown_channel_is_refused(publishers, draft_store):

    draft = draft_store.save(create_draft(status="approved"))

    assert publish(draft.id, ["myspace"]).status_code == 422
    assert client.post(f"/drafts/{draft.id}/publish", json={"channels": []}).status_code == 422
    assert draft_store.get(draft.id).status == "approved"


def test_the_public_story_holds_nothing_private(publishers, draft_store):

    from src.models.writer.draft import DraftReview

    draft = create_draft(status="approved", instructions="PRIVATE: angle it for the funders.")
    draft.review = DraftReview(model="PRIVATE-REVIEWER", reviewed_at="2026-10-15T08:00:00+00:00")
    draft.sources[0].excerpt = "PRIVATE excerpt of somebody else's page."
    draft_store.save(draft)

    publish(draft.id)

    story = client.get(f"/reader/stories/{draft.id}").json()

    for private in ("instructions", "revisions", "review", "error", "busy", "status", "published"):
        assert private not in story

    assert "excerpt" not in story["sources"][0]
    assert "PRIVATE" not in client.get(f"/reader/stories/{draft.id}").text
    assert "PRIVATE" not in client.get("/reader/stories").text


def test_a_change_to_the_draft_after_publishing_does_not_reach_the_public_page(publishers, draft_store):
    """
    Edits to a published draft are refused (draft_routes.py), but a
    background step or another stage can still write to it. The public
    page reads the snapshot, so none of that shows.
    """

    draft = draft_store.save(create_draft(status="approved"))
    publish(draft.id)

    def tamper(stored):
        stored.content = DraftContent(title="Changed behind the page", body="Changed.")
        stored.metadata = DraftMetadata(topic="Something else")

    draft_store.update(draft.id, tamper)

    story = client.get(f"/reader/stories/{draft.id}").json()
    assert story["content"]["title"] == "Seagrass meadows return to the bay"
    assert client.get("/reader/stories").json()["items"][0]["title"] == "Seagrass meadows return to the bay"


def test_a_failed_save_takes_the_page_back_down(publishers, draft_store, monkeypatch):

    draft = draft_store.save(create_draft(status="approved"))

    def broken_save(_draft):
        raise OSError("disk full")

    monkeypatch.setattr(draft_store, "save", broken_save)

    response = TestClient(app, raise_server_exceptions=False).post(
        f"/drafts/{draft.id}/publish", json={"channels": ["web"]}
    )

    assert response.status_code == 500
    assert publishers.web.story(draft.id) is None


# ----------------------------------------------------------------------
# Unpublish
# ----------------------------------------------------------------------


def test_unpublish_takes_it_off_the_reader_and_back_to_approved(publishers, draft_store):

    draft = draft_store.save(create_draft(status="approved"))
    publish(draft.id)

    assert client.get("/reader/stories").json()["total"] == 1

    response = client.post(f"/drafts/{draft.id}/unpublish")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["published"] == []

    assert client.get(f"/reader/stories/{draft.id}").status_code == 404
    assert client.get("/reader/stories").json()["total"] == 0


def test_after_unpublishing_an_edit_sends_it_back_to_draft(publishers, draft_store):

    draft = draft_store.save(create_draft(status="approved"))
    publish(draft.id)

    content = {"title": "Edited", "subtitle": "", "body": "Edited [1]."}

    # Refused while published (draft_routes.py)...
    assert client.put(f"/drafts/{draft.id}/content", json=content).status_code == 409

    client.post(f"/drafts/{draft.id}/unpublish")

    # ...accepted after, and what was approved was the old text.
    edited = client.put(f"/drafts/{draft.id}/content", json=content)
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"

    # Publishing the new text takes a new approval.
    assert publish(draft.id).status_code == 409
    client.post(f"/drafts/{draft.id}/approve")
    assert publish(draft.id).status_code == 200
    assert client.get(f"/reader/stories/{draft.id}").json()["content"]["title"] == "Edited"


def test_unpublish_is_refused_when_not_published_or_busy(publishers, draft_store):

    approved = draft_store.save(create_draft(status="approved"))
    busy = draft_store.save(create_draft(status="published", busy="reviewing"))

    assert client.post(f"/drafts/{approved.id}/unpublish").status_code == 409
    assert client.post(f"/drafts/{busy.id}/unpublish").status_code == 409


# ----------------------------------------------------------------------
# The public list
# ----------------------------------------------------------------------


def test_the_public_list_filters_and_pages(publishers, draft_store):

    english = draft_store.save(create_draft(status="approved", metadata=DraftMetadata(topic="Climate")))
    catalan = draft_store.save(create_draft(status="approved", language="ca", metadata=DraftMetadata(topic="Health")))

    publish(english.id)
    publish(catalan.id)

    assert client.get("/reader/stories").json()["total"] == 2
    assert [item["id"] for item in client.get("/reader/stories", params={"language": "ca"}).json()["items"]] == [catalan.id]
    assert [item["id"] for item in client.get("/reader/stories", params={"topic": "Climate"}).json()["items"]] == [english.id]
    assert len(client.get("/reader/stories", params={"limit": 1}).json()["items"]) == 1
    assert client.get("/reader/stories", params={"limit": 51}).status_code == 422
    assert client.get("/reader/stories/not-an-id").status_code == 422


# ----------------------------------------------------------------------
# The key
# ----------------------------------------------------------------------


def test_the_public_stories_answer_without_the_key_and_the_rest_refuse(publishers, draft_store, monkeypatch):

    draft = draft_store.save(create_draft(status="approved"))
    publish(draft.id)

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))

    assert client.get("/reader/stories").status_code == 200
    assert client.get(f"/reader/stories/{draft.id}").status_code == 200

    assert client.get("/publishing/channels").status_code == 401
    for action in ("approve", "publish", "unpublish"):
        assert client.post(f"/drafts/{draft.id}/{action}", json={"channels": ["web"]}).status_code == 401

    # Nothing changed behind the 401s.
    assert draft_store.get(draft.id).status == "published"

    keyed = {"X-API-Key": KEY}
    assert client.get("/publishing/channels", headers=keyed).status_code == 200
    assert client.post(f"/drafts/{draft.id}/unpublish", headers=keyed).status_code == 200

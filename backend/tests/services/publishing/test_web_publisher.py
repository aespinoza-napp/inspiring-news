"""
Publishing to the web: one snapshot file per article, read by the
public endpoints (src/services/publishing/web.py). Always over tmp_path.
"""

import json

import pytest

from src.models.writer.draft import DraftContent, DraftMetadata
from src.services.publishing.web import WebPublisher, public_path
from tests.factories import create_draft


@pytest.fixture
def web(tmp_path):

    return WebPublisher(tmp_path / "published")


def test_publishing_writes_one_snapshot_and_records_where_to_read_it(web):

    draft = create_draft(status="approved")

    record = web.publish(draft)

    assert record.channel == "web"
    assert record.url == f"/reader/stories/{draft.id}" == public_path(draft.id)
    assert [path.name for path in web.root.iterdir()] == [f"{draft.id}.json"]

    stored = json.loads((web.root / f"{draft.id}.json").read_text(encoding="utf-8"))
    assert stored["content"]["title"] == draft.content.title
    assert stored["publishedAt"] == record.at


def test_publishing_again_replaces_the_snapshot(web):

    draft = create_draft()
    web.publish(draft)

    draft.content = DraftContent(title="A second title", body="A second body [1].")
    web.publish(draft)

    assert web.story(draft.id)["content"]["title"] == "A second title"
    assert len(list(web.root.glob("*.json"))) == 1
    # No temporary file left behind.
    assert len(list(web.root.iterdir())) == 1


def test_the_snapshot_does_not_follow_the_draft(web):

    draft = create_draft()
    web.publish(draft)

    draft.content = DraftContent(title="Changed after publishing", body="Changed.")

    assert web.story(draft.id)["content"]["title"] == "Seagrass meadows return to the bay"


def test_unpublishing_removes_it_and_is_idempotent(web):

    draft = create_draft()
    web.publish(draft)

    web.unpublish(draft)

    assert web.story(draft.id) is None
    assert web.stories()["total"] == 0

    web.unpublish(draft)
    assert web.remove(draft.id) is False


def test_an_id_that_is_not_a_story_id_names_no_file(web, tmp_path):

    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")

    for bad in ("../secret", "..\\secret", "", "ABCDEF0123456789", "0123"):
        assert web.story(bad) is None
        assert web.remove(bad) is False


def test_nothing_published_yet_is_an_empty_list_not_an_error(web):

    assert web.stories() == {
        "total": 0,
        "offset": 0,
        "limit": 20,
        "items": [],
        "topics": [],
        "languages": [],
        "published": 0,
    }


def stamped(web, monkeypatch, at, **kwargs):
    """Publish a draft as if at `at`, so the order is the test's, not the clock's."""

    import src.services.publishing.web as module

    monkeypatch.setattr(module, "now", lambda: at)

    draft = create_draft(**kwargs)
    web.publish(draft)

    return draft


def test_the_list_is_newest_first_filtered_and_paged(web, monkeypatch):

    old = stamped(web, monkeypatch, "2026-10-13T09:00:00+00:00", language="es",
                  metadata=DraftMetadata(topic="Climate"))
    middle = stamped(web, monkeypatch, "2026-10-14T09:00:00+00:00", language="en",
                     metadata=DraftMetadata(topic="Health"))
    new = stamped(web, monkeypatch, "2026-10-15T09:00:00+00:00", language="en",
                  metadata=DraftMetadata(topic="Climate"))

    every = web.stories()
    assert [item["id"] for item in every["items"]] == [new.id, middle.id, old.id]
    assert every["topics"] == [{"topic": "Climate", "count": 2}, {"topic": "Health", "count": 1}]
    assert every["languages"] == [{"language": "en", "count": 2}, {"language": "es", "count": 1}]

    climate = web.stories(topic="climate")
    assert [item["id"] for item in climate["items"]] == [new.id, old.id]
    # Each facet is counted under the other filter.
    assert climate["languages"] == [{"language": "en", "count": 1}, {"language": "es", "count": 1}]

    assert [item["id"] for item in web.stories(language="es")["items"]] == [old.id]

    second = web.stories(offset=1, limit=1)
    assert second["total"] == 3
    assert [item["id"] for item in second["items"]] == [middle.id]


def test_one_unreadable_file_does_not_empty_the_list(web):

    draft = create_draft()
    web.publish(draft)

    (web.root / "0123456789abcdef.json").write_text("{not json", encoding="utf-8")

    assert [item["id"] for item in web.stories()["items"]] == [draft.id]
    assert web.story("0123456789abcdef") is None

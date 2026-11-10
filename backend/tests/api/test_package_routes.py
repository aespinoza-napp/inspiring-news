"""
/drafts/{id}/packages (src/api/package_routes.py): building a package,
reading it back, downloading it and sending its post to WordPress.
"""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models.writer.package import WordPressDelivery
from src.services.packages import video, wordpress
from src.services.packages.builder import PackageBuilder
from tests.services.packages.test_packages import approved

client = TestClient(app)


@pytest.fixture
def packages(draft_store, tmp_path, monkeypatch):

    import src.container as container

    monkeypatch.setattr(video, "available", lambda: False)

    builder = PackageBuilder(tmp_path / "packages", "https://inspiring.example")
    monkeypatch.setattr(container, "_package_builder", builder)

    return builder


def saved(draft_store, **changes):

    return draft_store.save(approved(**changes))


def test_a_package_is_built_listed_and_read(draft_store, packages):

    draft = saved(draft_store)

    created = client.post(f"/drafts/{draft.id}/packages", json={"channels": ["instagram", "wordpress"]})

    assert created.status_code == 201

    body = created.json()

    assert [channel["channel"] for channel in body["channels"]] == ["wordpress", "instagram"]
    assert body["draftId"] == draft.id

    listed = client.get(f"/drafts/{draft.id}/packages").json()

    assert [item["id"] for item in listed["packages"]] == [body["id"]]
    assert listed["currentContentHash"] == body["contentHash"]
    assert [channel["name"] for channel in listed["channels"]] == ["wordpress", "instagram", "stories", "tiktok"]

    assert client.get(f"/drafts/{draft.id}/packages/{body['id']}").json() == body


def test_all_four_channels_by_default(draft_store, packages):

    draft = saved(draft_store)

    body = client.post(f"/drafts/{draft.id}/packages").json()

    assert [channel["channel"] for channel in body["channels"]] == ["wordpress", "instagram", "stories", "tiktok"]


def test_a_draft_not_yet_approved_is_refused(draft_store, packages):

    draft = saved(draft_store, status="draft")

    response = client.post(f"/drafts/{draft.id}/packages")

    assert response.status_code == 409
    assert "approve" in response.json()["detail"]


def test_an_unknown_draft_or_package_is_404(draft_store, packages):

    assert client.post("/drafts/0123456789abcdef/packages").status_code == 404

    draft = saved(draft_store)

    assert client.get(f"/drafts/{draft.id}/packages/0123456789abcdef").status_code == 404


def test_the_zip_and_a_card_download(draft_store, packages):

    draft = saved(draft_store)
    body = client.post(f"/drafts/{draft.id}/packages", json={"channels": ["instagram"]}).json()

    archive = client.get(f"/drafts/{draft.id}/packages/{body['id']}/zip")

    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"
    assert "manifest.json" in zipfile.ZipFile(io.BytesIO(archive.content)).namelist()

    card = client.get(f"/drafts/{draft.id}/packages/{body['id']}/files/instagram/card-01.png")

    assert card.status_code == 200
    assert card.headers["content-type"] == "image/png"
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert client.get(f"/drafts/{draft.id}/packages/{body['id']}/files/instagram/nothing.png").status_code == 404


def test_wordpress_needs_the_sites_keys(draft_store, packages, monkeypatch):

    monkeypatch.setattr(wordpress, "configured", lambda: False)

    draft = saved(draft_store)
    body = client.post(f"/drafts/{draft.id}/packages", json={"channels": ["wordpress"]}).json()

    response = client.post(f"/drafts/{draft.id}/packages/{body['id']}/wordpress")

    assert response.status_code == 409
    assert "WORDPRESS_URL" in response.json()["detail"]


def test_wordpress_is_sent_once_as_a_draft_and_recorded(draft_store, packages, monkeypatch):

    sent = []

    def send_draft(post):
        sent.append(post)
        return WordPressDelivery(post_id=7, status="draft", link="https://news.example/wp-admin/post.php?post=7&action=edit", sent_at="2026-11-10T12:00:00+00:00")

    monkeypatch.setattr(wordpress, "configured", lambda: True)
    monkeypatch.setattr(wordpress, "send_draft", send_draft)

    draft = saved(draft_store)
    body = client.post(f"/drafts/{draft.id}/packages", json={"channels": ["wordpress", "stories"]}).json()

    response = client.post(f"/drafts/{draft.id}/packages/{body['id']}/wordpress")

    assert response.status_code == 200
    assert sent[0]["status"] == "draft"
    assert response.json()["channels"][0]["delivery"]["postId"] == 7

    again = client.post(f"/drafts/{draft.id}/packages/{body['id']}/wordpress")

    assert again.status_code == 409
    assert len(sent) == 1


def test_a_package_without_wordpress_files_cannot_be_sent(draft_store, packages, monkeypatch):

    monkeypatch.setattr(wordpress, "configured", lambda: True)

    draft = saved(draft_store)
    body = client.post(f"/drafts/{draft.id}/packages", json={"channels": ["stories"]}).json()

    assert client.post(f"/drafts/{draft.id}/packages/{body['id']}/wordpress").status_code == 409

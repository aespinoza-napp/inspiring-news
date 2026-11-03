"""POST/GET /imports/wordpress: thin over the container's WordPressImport."""

import time
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import routes
from src.config.settings import settings
from src.main import app
from src.services.imports.wordpress_import import WordPressImport

from tests.services.imports.test_wordpress import BODY, export, item

client = TestClient(app)


def runner(monkeypatch, tmp_path):

    analysis = Mock()
    analysis.analyze_news.return_value = {"validity": {"isValid": True}, "storage": {}, "factCheck": {}}
    made = WordPressImport(analysis, tmp_path)
    monkeypatch.setattr(routes, "get_wordpress_import", lambda: made)

    return made, analysis


def test_an_export_is_taken_as_the_body_and_followed(monkeypatch, tmp_path):

    made, analysis = runner(monkeypatch, tmp_path)

    response = client.post(
        "/imports/wordpress?statuses=publish,private&limit=1",
        content=export(item(1, "Uno", BODY), item(2, "Dos", BODY + " dos", status="private")),
        headers={"Content-Type": "application/xml"},
    )

    assert response.status_code == 202
    assert response.json()["total"] == 1 and response.json()["statuses"] == ["publish", "private"]

    for _ in range(200):
        if not client.get("/imports/wordpress").json()["running"]:
            break
        time.sleep(0.01)

    state = client.get("/imports/wordpress").json()
    assert state["done"] == 1 and len(state["results"]) == 1
    assert "results" not in client.get("/imports/wordpress?results=false").json()

    snapshot = client.get("/imports/wordpress/snapshot")
    assert snapshot.status_code == 200 and '"wp_id": 1' in snapshot.text


def test_what_is_not_an_export_is_a_422(monkeypatch, tmp_path):

    runner(monkeypatch, tmp_path)

    assert client.post("/imports/wordpress", content=b"").status_code == 422
    assert client.post("/imports/wordpress", content=b"<html/>").status_code == 422
    assert client.post("/imports/wordpress?statuses=published", content=export()).status_code == 422


def test_no_snapshot_before_an_import(monkeypatch, tmp_path):

    runner(monkeypatch, tmp_path)

    assert client.get("/imports/wordpress/snapshot").status_code == 404


def test_imports_are_behind_the_storage_key(monkeypatch, tmp_path):

    runner(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.post("/imports/wordpress", content=export()).status_code == 401
    assert client.get("/imports/wordpress").status_code == 401
    assert client.get("/imports/wordpress/snapshot").status_code == 401

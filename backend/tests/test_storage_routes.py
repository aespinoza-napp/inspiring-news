import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.routes as routes
from src.config.settings import settings
from src.main import app
from src.models.storage.lineage import DataLayer
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.lake_backend import JsonFileLakeBackend

from tests.factories import create_article
from tests.storage.test_datalake_repository import make_news, make_report

client = TestClient(app)


@pytest.fixture
def lake(tmp_path, monkeypatch):
    """
    Points the storage endpoints at a throwaway lake, so route tests
    never read or write the real data directory.
    """

    repository = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    monkeypatch.setattr(routes, "get_datalake_repository", lambda: repository)

    return repository


def seed(lake):

    run = lake.start_run("https://bbc.com/test")

    return lake.persist_all(run, make_news(), create_article(), make_report())


def test_list_records_returns_the_layer_contents(lake):

    seed(lake)

    response = client.get("/storage/exploitation")

    assert response.status_code == 200

    body = response.json()

    assert body["layer"] == "exploitation"
    assert len(body["records"]) == 1
    assert body["records"][0]["publishable"] is True


def test_list_records_honours_limit(lake):

    seed(lake)
    seed(lake)

    assert len(client.get("/storage/raw?limit=1").json()["records"]) == 1


def test_list_records_of_an_empty_layer_is_an_empty_list(lake):

    assert client.get("/storage/processed").json()["records"] == []


def test_unknown_layer_is_rejected_before_any_io(lake):

    assert client.get("/storage/not-a-layer").status_code == 422


def test_get_record_returns_the_stored_document(lake):

    written = seed(lake)

    response = client.get(
        f"/storage/processed/records/{written.processed_record_id}"
    )

    assert response.status_code == 200
    assert response.json()["lineage"]["run_id"] == written.run_id


def test_get_unknown_record_is_a_404(lake):

    assert client.get("/storage/raw/records/nope").status_code == 404


def test_trace_returns_every_layer_and_the_manifest(lake):

    written = seed(lake)

    body = client.get("/storage/trace/11111111-1111-1111-1111-111111111111").json()

    assert set(body["layers"]) == {layer.value for layer in DataLayer}
    assert len(body["manifest"]) == 3
    assert all(entry["run_id"] == written.run_id for entry in body["manifest"])


def test_trace_of_an_unknown_article_is_empty_rather_than_a_404(lake):
    """
    Tracing is a lookup over an append-only log; "nothing recorded for
    this id" is a legitimate answer, not an error.
    """

    seed(lake)

    body = client.get("/storage/trace/unknown").json()

    assert body["manifest"] == []
    assert all(records == [] for records in body["layers"].values())


# ----------------------------------------------------------------------
# Authentication
#
# These endpoints return whole article bodies and the full lineage of
# every run. Open by default is the local-dev choice (src/main.py warns
# at startup); setting STORAGE_API_KEY closes them.
# ----------------------------------------------------------------------


def test_storage_is_open_when_no_key_is_configured(lake, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", None)

    assert client.get("/storage/raw").status_code == 200


def test_a_configured_key_is_required(lake, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("s3cret"))

    assert client.get("/storage/raw").status_code == 401
    assert client.get("/storage/exploitation").status_code == 401
    assert client.get("/storage/raw/records/anything").status_code == 401
    assert client.get("/storage/trace/anything").status_code == 401


def test_the_right_key_is_accepted(lake, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("s3cret"))

    response = client.get("/storage/raw", headers={"X-API-Key": "s3cret"})

    assert response.status_code == 200


def test_a_wrong_key_is_rejected(lake, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("s3cret"))

    response = client.get("/storage/raw", headers={"X-API-Key": "guess"})

    assert response.status_code == 401


def test_the_analysis_endpoints_are_not_behind_the_storage_key(monkeypatch):
    """
    The key guards stored content, not the ability to run an analysis -
    locking /analyze would break the frontend for no security gain.
    """

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("s3cret"))

    # 422 (bad body), not 401 - the request reached validation.
    assert client.post("/enrich", json={}).status_code == 422

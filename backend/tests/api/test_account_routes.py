import pytest
from fastapi.testclient import TestClient

import src.api.account_routes as account_routes
from src.main import app

from tests.services.accounts.accounts_fixtures import make_service

PASSWORD = "correct horse battery"
OURS = {"X-Requested-With": "inspiring-news"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(account_routes, "get_account_service", lambda: service)
    # HTTPS, so the Secure session cookie is kept as a browser keeps it.
    return TestClient(app, base_url="https://testserver")


def register(client, username="ada"):
    response = client.post("/account/register", json={"username": username, "password": PASSWORD}, headers=OURS)
    assert response.status_code == 201, response.text
    return response.json()["csrf"]


def test_registering_signs_in_with_a_secure_httponly_cookie(client):

    response = client.post("/account/register", json={"username": "ada", "password": PASSWORD}, headers=OURS)

    cookie = response.headers["set-cookie"].lower()
    assert "in_session=" in cookie and "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert client.get("/account/me").json()["user"]["username"] == "ada"


def test_signing_in_from_another_site_is_refused(client):
    """No X-Requested-With: a cross-site form, which cannot set one."""

    register(client)
    client.cookies.clear()

    assert client.post("/account/login", json={"username": "ada", "password": PASSWORD}).status_code == 403
    assert client.post("/account/register", json={"username": "eve", "password": PASSWORD}).status_code == 403


def test_a_state_change_without_the_csrf_token_is_refused(client):

    csrf = register(client)

    assert client.post("/account/logout").status_code == 403
    assert client.post("/account/logout", headers={"X-CSRF-Token": "forged"}).status_code == 403
    assert client.post("/account/delete", json={"password": PASSWORD}, headers={"X-CSRF-Token": "forged"}).status_code == 403
    assert client.get("/account/me").status_code == 200

    assert client.post("/account/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/account/me").status_code == 401


def test_the_sixth_failed_sign_in_is_a_429_with_retry_after(client):

    register(client)
    client.cookies.clear()

    for _ in range(5):
        assert client.post("/account/login", json={"username": "ada", "password": "wrong password!"}, headers=OURS).status_code == 401

    limited = client.post("/account/login", json={"username": "ada", "password": PASSWORD}, headers=OURS)
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


def test_export_is_a_file_and_delete_leaves_nothing(client):

    csrf = register(client)

    exported = client.get("/account/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    assert exported.json()["users"][0]["username"] == "ada"

    assert client.post("/account/delete", json={"password": PASSWORD}, headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/account/me").status_code == 401
    assert client.post("/account/login", json={"username": "ada", "password": PASSWORD}, headers=OURS).status_code == 401


def test_every_answer_is_no_store(client):

    csrf = register(client)

    for response in (client.get("/account/me"), client.get("/account/export"),
                     client.post("/account/logout", headers={"X-CSRF-Token": csrf}),
                     client.get("/account/me")):
        assert response.headers.get("cache-control") == "no-store", response.request.url


def test_nothing_about_a_reader_reaches_metrics(client):

    register(client, "uniquereadername")

    assert "uniquereadername" not in client.get("/metrics").text

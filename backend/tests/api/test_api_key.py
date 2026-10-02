"""
The API key (STORAGE_API_KEY, sent as X-API-Key): which endpoints take
it, what happens without one configured, and that the frontend sends it.

Every endpoint is behind the key unless OPEN_ENDPOINTS below says
otherwise, with the reason. So a new route is closed until someone
decides, here, that it may be open - the analysis endpoints were open by
default once, and with the frontend on a public address each of them is
minutes of the server's CPU (src/api/routes.py::require_storage_key).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.routes as routes
from src.config.settings import settings
from src.main import app
from src.services.job_store import JobStore

KEY = "s3cret"

# Past the key, the tests below hit tripwires that raise: a 500 there is
# expected, and only whether the key stopped the request matters.
client = TestClient(app, raise_server_exceptions=False)

# Each decided, not defaulted.
OPEN_ENDPOINTS = {
    # The uptime check and the smoke test's first call. Names the
    # dependency that failed, never the error (services/health.py).
    ("GET", "/healthz"),
    # Counts and durations, no URLs or claims. Scraped by the Ops Agent
    # over the VM's loopback; Caddy does not forward it.
    ("GET", "/metrics"),
    # Polling a job by id: a uuid4 only whoever started the job holds.
    # Starting one, and listing them, take the key.
    ("GET", "/analyze/jobs/{job_id}"),
    ("GET", "/analyze/jobs/batch"),
}

# What was open until 2026-10-02, with a body each would accept: the
# key must stop them before any of it runs.
EXPENSIVE = [
    ("/analyze", {"urls": ["https://example.com/a"]}),
    ("/analyze/jobs", {"url": "https://example.com/a"}),
    ("/analyze/jobs/batch", {"urls": ["https://example.com/a"]}),
    ("/verify-claim", {"claim": "The river was declared clean in 2024."}),
    ("/enrich", {"text": "A short article about a river."}),
    ("/correct", {"text": "A short article about a river."}),
]


def endpoints() -> list[tuple[str, str]]:
    """
    Every (method, path) the app serves, from its OpenAPI schema rather
    than app.routes: FastAPI 0.139 no longer flattens an included router
    into app.routes (it is one `_IncludedRouter` entry), and a walk over
    that internal shape would pass by finding nothing - this test's first
    version did exactly that.
    """

    return sorted(
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    )


def concrete(path: str) -> str:
    """/storage/{layer} -> /storage/x: any value, the key is checked first."""

    return re.sub(r"\{[^}]+\}", "x", path)


# ----------------------------------------------------------------------
# Which endpoints
# ----------------------------------------------------------------------


def test_the_app_serves_the_endpoints_this_file_checks():

    assert len(endpoints()) >= 30


def test_every_endpoint_takes_the_key_unless_it_was_decided_otherwise(reached, monkeypatch):
    """
    Asked, not inspected: a request without the key, to every endpoint.
    The key is a dependency, solved before any path, query or body
    parameter is validated, so a 401 here means the handler never ran -
    no analysis starts, nothing is written. `reached` puts tripwires in
    front of the pipeline, so a new route that is open by mistake fails
    here instead of starting a real analysis inside the test run.
    """

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))

    unguarded = [
        (method, path)
        for method, path in endpoints()
        if (method, path) not in OPEN_ENDPOINTS
        and client.request(method, concrete(path)).status_code != 401
    ]

    assert unguarded == [], (
        f"{unguarded} answer without the API key. Every endpoint is closed "
        "unless this file decides otherwise. For each one, either\n"
        "  - close it: add dependencies=[Depends(require_storage_key)] to "
        "its decorator in src/api/routes.py (the frontend's proxy for it "
        "must then send the key, which test_every_frontend_server_route_"
        "sends_the_key_on_every_call checks), or\n"
        "  - keep it open on purpose: add (method, path), exactly as listed "
        "above, to OPEN_ENDPOINTS in backend/tests/api/test_api_key.py, "
        "with a comment saying why anyone on the internet may call it. "
        "Only Caddy's routes reach the internet (docker/caddy/Caddyfile): "
        "an open backend route is reachable from there only through the "
        "frontend's proxy for it."
    )


def test_the_open_list_names_endpoints_that_exist():
    """Otherwise the list rots into a set of names nothing checks."""

    stale = OPEN_ENDPOINTS - set(endpoints())

    assert stale == set(), (
        f"OPEN_ENDPOINTS names {sorted(stale)}, which the app no longer "
        "serves. Remove the entry, or update it if the route was renamed "
        "(and decide again whether the new route may be open)."
    )


# ----------------------------------------------------------------------
# What the key does
# ----------------------------------------------------------------------


@pytest.fixture
def reached(monkeypatch):
    """
    Every service the expensive endpoints would start, replaced by a
    tripwire that records the call. A 401 must leave this empty.
    """

    calls: list[str] = []

    def tripwire(name):
        def call(*args, **kwargs):
            calls.append(name)
            raise RuntimeError(f"{name} reached")
        return call

    for getter in (
        "get_analysis_service", "get_job_queue", "get_claim_service",
        "get_enrichment_service", "get_text_corrector",
    ):
        monkeypatch.setattr(routes, getter, tripwire(getter))

    # A job created before the queue tripwire fires must not land in
    # the store every other test reads.
    monkeypatch.setattr(routes, "job_store", JobStore())

    return calls


@pytest.mark.parametrize("path, body", EXPENSIVE)
def test_without_the_key_nothing_runs(path, body, reached, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))

    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers={"X-API-Key": "guess"}).status_code == 401
    assert client.post(path, json=body, headers={"X-API-Key": ""}).status_code == 401

    assert reached == []


@pytest.mark.parametrize("path, body", EXPENSIVE)
def test_with_the_key_the_request_gets_through(path, body, reached, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))

    response = client.post(path, json=body, headers={"X-API-Key": KEY})

    assert response.status_code != 401
    assert len(reached) == 1


@pytest.mark.parametrize("path, body", EXPENSIVE)
def test_with_no_key_configured_local_dev_stays_open(path, body, reached, monkeypatch):
    """
    The local-dev default: no key in backend/.env, nothing to send, and
    src/main.py warns at startup. Production cannot get here -
    docker-compose.prod.yml refuses to start without STORAGE_API_KEY.
    """

    monkeypatch.setattr(settings, "STORAGE_API_KEY", None)

    response = client.post(path, json=body)

    assert response.status_code != 401
    assert len(reached) == 1


def test_the_open_endpoints_stay_open_with_a_key_set(monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))
    monkeypatch.setattr(routes, "health_checks", lambda: {"searxng": lambda: None})
    monkeypatch.setattr(routes, "job_store", JobStore())

    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/analyze/jobs/unknown").status_code == 404
    assert client.get("/analyze/jobs/batch", params={"ids": "unknown"}).status_code == 200


# ----------------------------------------------------------------------
# The frontend sends it
#
# Its server routes are the backend's only client in production, and
# the key is read there, on the server, so the browser never holds it.
# A route that forgets it is a page that works on a laptop (no key) and
# answers 401 on the server.
# ----------------------------------------------------------------------

FRONTEND_API = Path(__file__).resolve().parents[3] / "frontend" / "src" / "app" / "api"


def code_of(path: Path) -> str:
    """The route's source without its comments, which mention fetch() too."""

    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)

    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))


def frontend_routes() -> list[Path]:

    return sorted(FRONTEND_API.rglob("route.ts"))


def test_the_frontend_has_server_routes_to_check():

    assert len(frontend_routes()) >= 10


@pytest.mark.parametrize(
    "route", frontend_routes(), ids=lambda path: path.parent.relative_to(FRONTEND_API).as_posix()
)
def test_every_frontend_server_route_sends_the_key_on_every_call(route):
    """
    Each route file defines a `headers()` that adds X-API-Key from
    process.env.STORAGE_API_KEY, and every request it makes passes
    `headers: headers(...)` - the pattern graph/[...path]/route.ts
    started. Sent even to the endpoints that are open today (polling a
    job by id), so closing one is a backend-only change.

    Read from the source, not run: there is no frontend test runner. So
    it checks what a regex can - at least one keyed options object per
    fetch() (graph's relay() has one fetch and two), and no headers set
    any other way.
    """

    code = code_of(route)

    calls = len(re.findall(r"\bfetch\(", code))
    keyed = len(re.findall(r"\bheaders:\s*headers\(", code))
    every_headers = len(re.findall(r"\bheaders:", code))

    fix = (
        "Copy the `headers(json)` helper from frontend/src/app/api/analyze/"
        "route.ts into this file and pass `headers: headers(true)` (a JSON "
        "body) or `headers: headers(false)` in every fetch()'s options - "
        "also to a backend endpoint that is open today."
    )

    assert calls, (
        f"{route} calls no backend endpoint. Every server route here is a "
        "proxy onto the backend; a route that answers by itself is new - "
        "exclude it in frontend_routes() with the reason."
    )
    assert keyed >= calls, (
        f"{route}: {calls} fetch() call(s), only {keyed} with "
        f"`headers: headers(...)`. {fix}"
    )
    assert every_headers == keyed, f"{route} sets headers without headers(). {fix}"
    assert "process.env.STORAGE_API_KEY" in code, f"{route} never reads the key. {fix}"
    assert '"X-API-Key"' in code, f"{route} never sends X-API-Key. {fix}"

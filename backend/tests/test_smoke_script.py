"""
scripts/smoke.sh against the real app: the routes, the key and the
status codes it expects are the ones the API actually answers with.

The app is served by uvicorn on a free local port, in this process, with
what lies past a socket swapped out: the health checks (no SearXNG,
inference/, LLM or Neo4j here), the reader's lake and the evaluation
folder (temporary), and, for --claim, the claim service. The script is
run by the bash on PATH - Git Bash on Windows, as check.sh is - and
skipped where there is no bash or curl.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from pydantic import SecretStr

import src.api.routes as routes
import src.services.evaluation_summary as summary_module
from src.config.settings import settings
from src.main import app
from src.services.reader.index import ReaderIndex

from tests.services.reader.reader_lake import make_lake, publish

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke.sh"

# shutil.which, not a bare "bash": Windows' process search tries System32
# before PATH, and System32's bash.exe is WSL's, not Git's.
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None or shutil.which("curl") is None, reason="needs bash and curl on PATH"
)

KEY = "smoke-s3cret"


def free_port() -> int:

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def server(monkeypatch, tmp_path):
    """The real app on 127.0.0.1, its dependencies faked; yields its URL."""

    monkeypatch.setattr(settings, "LAKE_ENABLED", False)
    monkeypatch.setattr(routes, "health_checks", lambda: {"searxng": lambda: None, "llm": lambda: None})

    index = ReaderIndex(make_lake(tmp_path / "lake"))
    publish(index.lake)
    monkeypatch.setattr(routes, "get_reader_index", lambda: index)

    monkeypatch.setattr(summary_module, "EVALUATION_PATH", tmp_path / "evaluation")

    port = free_port()

    instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))

    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10

    while not instance.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    instance.should_exit = True
    thread.join(timeout=10)


def smoke(*args: str) -> subprocess.CompletedProcess:

    return subprocess.run(
        [BASH, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        # Not the developer's own key: the argument is what is under test.
        env={**__import__("os").environ, "STORAGE_API_KEY": ""},
    )


def test_a_healthy_keyed_server_passes_every_check(server, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))

    result = smoke(server, KEY)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL" not in result.stdout

    for line in (
        "/healthz: every dependency answers",
        "/metrics: Prometheus counters served",
        "the key is on",
        "the key is accepted",
        "/reader/articles: open, 1 published article(s)",
        "polling a job by id: open",
        "/evaluation/summary: served",
    ):
        assert line in result.stdout, line


def test_a_wrong_key_and_a_server_without_one_both_fail(server, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr(KEY))

    wrong = smoke(server, "not-the-key")

    # The keyed read and the newest keyed route both refuse it.
    assert wrong.returncode == 2
    assert "wrong key for this server" in wrong.stdout
    assert "/evaluation/summary: 401" in wrong.stdout

    monkeypatch.setattr(settings, "STORAGE_API_KEY", None)

    open_server = smoke(server, KEY)

    assert open_server.returncode >= 1
    assert "the key is OFF" in open_server.stdout


def test_no_key_against_a_local_server_without_one_passes(server, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", None)

    result = smoke(server)

    assert result.returncode == 0, result.stdout
    assert "asks for none" in result.stdout


def test_a_failing_dependency_is_named(server, monkeypatch):

    def down():
        raise RuntimeError("refused")

    monkeypatch.setattr(routes, "health_checks", lambda: {"searxng": lambda: None, "llm": down})

    result = smoke(server)

    assert result.returncode == 1
    assert "/healthz: 503, not answering: llm" in result.stdout


def test_nothing_listening_stops_at_the_first_check():

    result = smoke(f"http://127.0.0.1:{free_port()}")

    assert result.returncode == 1
    assert "no answer from" in result.stdout
    assert "/metrics" not in result.stdout


class FakeClaimService:

    def __init__(self, answer: dict):
        self.answer = answer

    def verify(self, text, on_phase=None, thresholds=None):
        return self.answer


@pytest.mark.parametrize("answer, expected", [
    ({"verdict": "TRUE", "evidenceCount": 4, "llmUnreachable": False, "searchUnavailable": False},
     "ok    /verify-claim: TRUE, from 4 source(s)"),
    ({"verdict": "UNVERIFIED", "evidenceCount": 3, "llmUnreachable": True, "searchUnavailable": False},
     "the LLM was unreachable"),
    ({"verdict": "UNVERIFIED", "evidenceCount": 0, "llmUnreachable": False, "searchUnavailable": True},
     "the web search failed"),
    ({"verdict": "UNVERIFIED", "evidenceCount": 0, "llmUnreachable": False, "searchUnavailable": False},
     "UNVERIFIED with no evidence"),
])
def test_claim_tells_a_real_verdict_from_a_failed_one(server, monkeypatch, answer, expected):

    monkeypatch.setattr(routes, "get_claim_service", lambda: FakeClaimService(answer))

    result = smoke(server, "--claim")

    assert expected in result.stdout, result.stdout
    assert result.returncode == (0 if expected.startswith("ok") else 1)

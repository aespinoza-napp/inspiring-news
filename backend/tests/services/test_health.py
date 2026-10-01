import httpx
import pytest
from pydantic import SecretStr

import src.services.health as health
from src.config.settings import settings
from src.services.health import CheckFailed, run_checks


def failing(exc):
    def check():
        raise exc
    return check


def test_all_dependencies_answering_is_ok():

    report = run_checks({"a": lambda: None, "b": lambda: None})

    assert report["ok"] is True
    assert set(report["checks"]) == {"a", "b"}
    assert all(check["ok"] for check in report["checks"].values())


def test_one_failing_dependency_fails_the_whole_report():

    report = run_checks({"up": lambda: None, "down": failing(httpx.ConnectError("refused"))})

    assert report["ok"] is False
    assert report["checks"]["up"]["ok"] is True
    assert report["checks"]["down"] == {"ok": False, "error": "ConnectError", "ms": report["checks"]["down"]["ms"]}


def test_errors_name_the_kind_of_failure_not_the_exception_text():
    """The endpoint is unauthenticated, and exception text names internal hosts."""

    request = httpx.Request("GET", "http://inference:8001/healthz")
    status = httpx.HTTPStatusError(
        "503 for http://inference:8001/healthz",
        request=request,
        response=httpx.Response(503, request=request),
    )

    report = run_checks({
        "status": failing(status),
        "other": failing(RuntimeError("bolt://neo4j:7687 refused")),
    })

    assert report["checks"]["status"]["error"] == "HTTP 503"
    assert report["checks"]["other"]["error"] == "RuntimeError"
    assert "neo4j:7687" not in str(report)


def test_an_answering_llm_without_the_configured_model_fails(monkeypatch):
    """Ollama answers with no model pulled, and every verification then fails."""

    monkeypatch.setattr(settings, "LLM_MODEL", "llama3.2:3b")
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("ollama"))
    monkeypatch.setattr(
        health, "_get",
        lambda url, headers=None: httpx.Response(200, json={"data": [{"id": "other:1b"}]}),
    )

    with pytest.raises(CheckFailed, match="llama3.2:3b"):
        health._check_llm()


def test_an_llm_serving_the_configured_model_passes(monkeypatch):

    monkeypatch.setattr(settings, "LLM_MODEL", "llama3.2:3b")
    monkeypatch.setattr(
        health, "_get",
        lambda url, headers=None: httpx.Response(200, json={"data": [{"id": "llama3.2:3b"}]}),
    )

    health._check_llm()


def test_the_graph_is_not_checked_when_it_is_off(monkeypatch):

    monkeypatch.setattr(settings, "GRAPH_ENABLED", False)

    assert "neo4j" not in health.default_checks()

    monkeypatch.setattr(settings, "GRAPH_ENABLED", True)

    assert "neo4j" in health.default_checks()

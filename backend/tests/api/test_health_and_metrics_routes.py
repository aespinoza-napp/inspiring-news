from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app
from src.services.run_metrics import RunClock, RunMetrics

client = TestClient(app)


def test_healthz_is_200_when_every_dependency_answers(monkeypatch):

    monkeypatch.setattr(routes, "health_checks", lambda: {"searxng": lambda: None})

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_healthz_is_503_naming_the_dependency_that_does_not(monkeypatch):

    def down():
        raise ConnectionError("refused")

    monkeypatch.setattr(
        routes, "health_checks", lambda: {"searxng": lambda: None, "inference": down}
    )

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["checks"]["inference"]["ok"] is False
    assert response.json()["checks"]["searxng"]["ok"] is True


def test_metrics_are_served_in_prometheus_text_format(monkeypatch):

    metrics = RunMetrics()
    RunClock(metrics, "article").observe("done", {})
    monkeypatch.setattr(routes, "run_metrics", metrics)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert 'inspiring_runs_total{outcome="done",purpose="article"} 1' in response.text

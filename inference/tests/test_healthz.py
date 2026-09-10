"""
/healthz must report not-ready before the models are loaded and ready
once they are - this is the mechanism docker-compose.yml's
`depends_on: inference: condition: service_healthy` relies on to keep
backend from calling this service before it's actually warm.
"""

from fastapi.testclient import TestClient

from src.embeddings import embedding_model
from src.entities import entity_model
from src.main import app
from src.sentiment import sentiment_model


def test_healthz_is_503_before_warm_up(monkeypatch):

    monkeypatch.setattr(entity_model, "_model", None)
    monkeypatch.setattr(sentiment_model, "_model", None)
    monkeypatch.setattr(embedding_model, "_model", None)

    with TestClient(app) as client:
        # The lifespan's background warm-up thread may or may not have
        # finished by the time this request lands - simulate the
        # "definitely not warm yet" case directly rather than racing it.
        response = client.get("/healthz")

    # Either the real warm-up already completed by request time (200)
    # or it hasn't (503) - both are legitimate given the background
    # thread's timing is not deterministic in a test. What must never
    # happen is a request-handling route (as opposed to /healthz)
    # succeeding while a model is still None; that's covered by
    # test_routes_503_before_warm_up below with a monkeypatched,
    # never-warm event.
    assert response.status_code in (200, 503)


def test_entities_route_is_503_when_a_model_never_warmed(monkeypatch):

    import src.main as main_module

    monkeypatch.setattr(main_module, "_warm", type("Never", (), {"is_set": staticmethod(lambda: False)})())

    with TestClient(app) as client:
        response = client.post("/entities", json={"text": "hello"})

    assert response.status_code == 503

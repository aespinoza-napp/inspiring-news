from fastapi.testclient import TestClient

import src.api.routes as routes
from src.config.settings import settings
from src.main import app
from src.models.fact_checker.fact_check import Verdict

client = TestClient(app)


class FakeClaimService:

    def __init__(self):
        self.calls = []

    def verify(self, text, on_phase=None, thresholds=None):
        self.calls.append((text, thresholds))
        return {
            "claim": text,
            "verdict": Verdict.TRUE,
            "confidence": 0.8,
            "explanation": "Confirmed.",
            "evidence": [],
        }


class FakeEnrichmentService:

    def __init__(self):
        self.calls = []

    def enrich(self, text, title=None, url=None, language=None, on_phase=None, thresholds=None):
        self.calls.append((text, title, url, thresholds, language))
        return {"keywords": ["mars"], "claims": [], "entities": {}}


def use_claim(monkeypatch):
    service = FakeClaimService()
    monkeypatch.setattr(routes, "get_claim_service", lambda: service)
    return service


def use_enrich(monkeypatch):
    service = FakeEnrichmentService()
    monkeypatch.setattr(routes, "get_enrichment_service", lambda: service)
    return service


# ----------------------------------------------------------------------
# POST /verify-claim
# ----------------------------------------------------------------------


def test_verify_claim_returns_a_verdict(monkeypatch):

    use_claim(monkeypatch)

    response = client.post(
        "/verify-claim", json={"claim": "NASA discovered water on Mars."}
    )

    assert response.status_code == 200

    body = response.json()

    assert body["claim"] == "NASA discovered water on Mars."
    assert body["verdict"] == "TRUE"


def test_verify_claim_uses_the_default_thresholds(monkeypatch):

    service = use_claim(monkeypatch)

    client.post("/verify-claim", json={"claim": "A claim."})

    assert service.calls[0][1].max_evidence_per_claim == settings.MAX_EVIDENCE_PER_CLAIM


def test_verify_claim_applies_per_run_thresholds(monkeypatch):

    service = use_claim(monkeypatch)

    client.post(
        "/verify-claim",
        json={"claim": "A claim.", "thresholds": {"max_evidence_per_claim": 2}},
    )

    assert service.calls[0][1].max_evidence_per_claim == 2


def test_an_empty_claim_is_rejected(monkeypatch):

    service = use_claim(monkeypatch)

    assert client.post("/verify-claim", json={"claim": ""}).status_code == 422
    assert service.calls == []


def test_a_missing_claim_is_rejected(monkeypatch):

    use_claim(monkeypatch)

    assert client.post("/verify-claim", json={}).status_code == 422


def test_an_invalid_threshold_is_rejected_before_any_work(monkeypatch):

    service = use_claim(monkeypatch)

    response = client.post(
        "/verify-claim",
        json={"claim": "A claim.", "thresholds": {"max_evidence_per_claim": 0}},
    )

    assert response.status_code == 422
    assert service.calls == []


def test_an_unavailable_verifier_is_a_503_not_a_500(monkeypatch):
    """
    Reaching the service opens Qdrant and loads the embedding model,
    which can genuinely fail (e.g. a transient storage lock). That is
    "try again", not "the request was malformed".
    """

    def boom():
        raise RuntimeError("qdrant is locked")

    monkeypatch.setattr(routes, "get_claim_service", boom)

    response = client.post("/verify-claim", json={"claim": "A claim."})

    assert response.status_code == 503
    assert "qdrant is locked" in response.json()["detail"]


# ----------------------------------------------------------------------
# POST /enrich
# ----------------------------------------------------------------------


def test_enrich_returns_the_enrichment(monkeypatch):

    use_enrich(monkeypatch)

    response = client.post("/enrich", json={"text": "Some article text."})

    assert response.status_code == 200
    assert response.json()["keywords"] == ["mars"]


def test_enrich_forwards_the_optional_title_and_url(monkeypatch):

    service = use_enrich(monkeypatch)

    client.post(
        "/enrich",
        json={
            "text": "Some text.",
            "title": "A title",
            "url": "https://example.com/a",
        },
    )

    text, title, url, _thresholds, _language = service.calls[0]

    assert (text, title, url) == ("Some text.", "A title", "https://example.com/a")


def test_enrich_defaults_title_and_url_to_none(monkeypatch):

    service = use_enrich(monkeypatch)

    client.post("/enrich", json={"text": "Some text."})

    assert service.calls[0][1] is None
    assert service.calls[0][2] is None


def test_enrich_applies_per_run_thresholds(monkeypatch):

    service = use_enrich(monkeypatch)

    client.post(
        "/enrich",
        json={"text": "Some text.", "thresholds": {"topic_classifier_threshold": 0.8}},
    )

    assert service.calls[0][3].topic_classifier_threshold == 0.8


def test_empty_text_is_rejected(monkeypatch):

    service = use_enrich(monkeypatch)

    assert client.post("/enrich", json={"text": ""}).status_code == 422
    assert service.calls == []


def test_an_unknown_threshold_name_is_rejected(monkeypatch):

    service = use_enrich(monkeypatch)

    response = client.post(
        "/enrich",
        json={"text": "Some text.", "thresholds": {"topic_treshold": 0.8}},
    )

    assert response.status_code == 422
    assert service.calls == []


def test_an_unavailable_enricher_is_a_503(monkeypatch):

    def boom():
        raise RuntimeError("models failed to load")

    monkeypatch.setattr(routes, "get_enrichment_service", boom)

    response = client.post("/enrich", json={"text": "Some text."})

    assert response.status_code == 503


def test_enrich_forwards_an_explicit_language(monkeypatch):
    """
    Omitting it lets the pipeline detect; supplying it is for the caller
    who knows better than a stopword count on a short fragment.
    """

    service = use_enrich(monkeypatch)

    client.post("/enrich", json={"text": "Un texto corto.", "language": "es"})

    assert service.calls[0][4] == "es"


def test_enrich_defaults_language_to_none_so_it_is_detected(monkeypatch):

    service = use_enrich(monkeypatch)

    client.post("/enrich", json={"text": "Some text."})

    assert service.calls[0][4] is None

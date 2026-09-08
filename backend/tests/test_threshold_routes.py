from fastapi.testclient import TestClient

import src.api.routes as routes
from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.main import app

client = TestClient(app)


class RecordingAnalysisService:
    """Captures the thresholds each analyse call actually received."""

    def __init__(self):
        self.calls = []

    def analyze(self, url, force_refresh=False, on_phase=None, thresholds=None):

        self.calls.append(thresholds)

        report = on_phase or (lambda phase, data: None)
        result = {"url": url, "title": "Fake title", "cached": False}
        report("done", result)

        return result


def use(service, monkeypatch):

    monkeypatch.setattr(routes, "get_analysis_service", lambda: service)

    return service


# ----------------------------------------------------------------------
# POST /analyze
# ----------------------------------------------------------------------


def test_analyze_without_thresholds_uses_the_environment_defaults(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    response = client.post("/analyze", json={"urls": ["https://example.com/a"]})

    assert response.status_code == 200
    assert service.calls == [PipelineThresholds()]


def test_analyze_applies_the_thresholds_the_caller_picked(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    client.post(
        "/analyze",
        json={
            "urls": ["https://example.com/a"],
            "thresholds": {"positive_impact_min_score": 0.85},
        },
    )

    assert service.calls[0].positive_impact_min_score == 0.85


def test_omitted_thresholds_still_fall_back_to_defaults(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    client.post(
        "/analyze",
        json={
            "urls": ["https://example.com/a"],
            "thresholds": {"positive_impact_min_score": 0.85},
        },
    )

    thresholds = service.calls[0]

    assert thresholds.topic_min_confidence == settings.TOPIC_MIN_CONFIDENCE
    assert thresholds.max_claims_per_article == settings.MAX_CLAIMS_PER_ARTICLE


def test_every_url_in_a_batch_gets_the_same_thresholds(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    client.post(
        "/analyze",
        json={
            "urls": ["https://example.com/a", "https://example.com/b"],
            "thresholds": {"max_claims_per_article": 2},
        },
    )

    assert len(service.calls) == 2
    assert all(call.max_claims_per_article == 2 for call in service.calls)


def test_an_out_of_range_threshold_is_a_422_not_a_broken_run(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    response = client.post(
        "/analyze",
        json={
            "urls": ["https://example.com/a"],
            "thresholds": {"positive_impact_min_score": 5.0},
        },
    )

    assert response.status_code == 422
    assert service.calls == []


def test_an_unknown_threshold_name_is_a_422(monkeypatch):
    """
    A typo'd knob must not be silently ignored - the caller would
    believe a threshold was applied when it never was.
    """

    service = use(RecordingAnalysisService(), monkeypatch)

    response = client.post(
        "/analyze",
        json={
            "urls": ["https://example.com/a"],
            "thresholds": {"positive_impact_treshold": 0.5},
        },
    )

    assert response.status_code == 422
    assert service.calls == []


# ----------------------------------------------------------------------
# POST /analyze/jobs
# ----------------------------------------------------------------------


def test_a_job_carries_the_thresholds_through_to_the_background_run(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    response = client.post(
        "/analyze/jobs",
        json={
            "url": "https://example.com/a",
            "thresholds": {"topic_min_confidence": 0.6},
        },
    )

    assert response.status_code == 202

    assert service.calls[0].topic_min_confidence == 0.6


def test_a_job_without_thresholds_runs_on_the_defaults(monkeypatch):

    service = use(RecordingAnalysisService(), monkeypatch)

    client.post("/analyze/jobs", json={"url": "https://example.com/a"})

    assert service.calls == [PipelineThresholds()]


def test_an_invalid_job_threshold_is_rejected_before_the_job_is_created(monkeypatch):
    """
    Resolved on the request thread, so a bad value is a 422 on the POST
    rather than a job that is accepted, starts, and then fails - which
    the client would only discover by polling.
    """

    service = use(RecordingAnalysisService(), monkeypatch)

    response = client.post(
        "/analyze/jobs",
        json={"url": "https://example.com/a", "thresholds": {"max_claims_per_article": 0}},
    )

    assert response.status_code == 422
    assert "jobId" not in response.json()
    assert service.calls == []


def test_the_job_reports_which_thresholds_were_overridden(monkeypatch):

    use(RecordingAnalysisService(), monkeypatch)

    job_id = client.post(
        "/analyze/jobs",
        json={
            "url": "https://example.com/a",
            "thresholds": {"positive_impact_min_score": 0.85},
        },
    ).json()["jobId"]

    events = client.get(f"/analyze/jobs/{job_id}").json()["events"]

    initializing = next(e for e in events if e["phase"] == "initializing")

    assert initializing["data"]["thresholdOverrides"] == {
        "positive_impact_min_score": 0.85
    }


def test_a_default_job_reports_no_overrides(monkeypatch):

    use(RecordingAnalysisService(), monkeypatch)

    job_id = client.post(
        "/analyze/jobs", json={"url": "https://example.com/a"}
    ).json()["jobId"]

    events = client.get(f"/analyze/jobs/{job_id}").json()["events"]

    initializing = next(e for e in events if e["phase"] == "initializing")

    assert initializing["data"]["thresholdOverrides"] == {}

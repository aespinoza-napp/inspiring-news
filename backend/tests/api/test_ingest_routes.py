from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app

from tests.builders.source_builder import build_source

client = TestClient(app)


class FakeIngestion:

    def __init__(self):
        self.calls = []
        self.last_run = None

    def enabled_sources(self):
        return [build_source(id="bbc", name="BBC"), build_source(id="nasa", name="NASA")]

    def run(self, start_job, source_ids=None, per_source=3, groups=None):
        self.calls.append((source_ids, per_source) if groups is None else (source_ids, per_source, groups))
        job_id, _ = start_job("https://bbc.com/a")
        return {"sources": [], "totals": {"queued": 1}, "jobId": job_id}


def use_ingestion(monkeypatch):

    service = FakeIngestion()
    started = []

    monkeypatch.setattr(routes, "get_ingestion_service", lambda: service)
    monkeypatch.setattr(
        routes,
        "_start_job",
        lambda url, force, thresholds, purpose="article": (
            started.append((url, purpose)) or ("job-1", False)
        ),
    )

    return service, started


def test_ingest_queues_jobs_marked_as_ingestion(monkeypatch):
    """The purpose is what separates discovered articles in the scraper stats."""

    service, started = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"sources": ["nasa"], "perSource": 2})

    assert response.status_code == 200
    assert service.calls == [(["nasa"], 2)]
    assert started == [("https://bbc.com/a", "ingestion")]


def test_an_unknown_source_is_rejected_before_anything_runs(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"sources": ["nope"]})

    assert response.status_code == 422
    assert service.calls == []


def test_per_source_is_bounded(monkeypatch):
    """Each queued article is a full analysis; one call must not start hundreds."""

    use_ingestion(monkeypatch)

    assert client.post("/ingest", json={"perSource": 500}).status_code == 422


def test_the_sources_and_last_run_are_listed(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources").json()

    assert [source["id"] for source in body["sources"]] == ["bbc", "nasa"]
    assert body["lastRun"] is None


# ----------------------------------------------------------------------
# Topic groups and candidate rounds
# ----------------------------------------------------------------------


def test_ingest_can_be_narrowed_to_topic_groups(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"groups": ["environment", "science"]})

    assert response.status_code == 200
    assert service.calls == [(None, 3, ["environment", "science"])]


def test_at_most_three_known_groups_are_accepted(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    for groups in (["sports"], ["society", "science", "environment", "health"], []):
        assert client.post("/ingest", json={"groups": groups}).status_code == 422

    assert service.calls == []


def test_the_groups_and_their_source_counts_are_listed(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources").json()

    assert [group["id"] for group in body["groups"]] == ["society", "science", "environment", "culture", "health"]
    assert (body["maxGroups"], body["maxSelected"]) == (3, 20)
    assert (body["listed"], body["maxListed"]) == (20, 40)
    assert body["groups"][1]["topics"][0] == {"id": "space", "name": "Space"}


class FakeSelection:

    def __init__(self):
        self.calls = []

    def create_round(self, groups, source_ids, per_source, listed=20):
        self.calls.append(("create", groups, source_ids, per_source, listed))
        return {"id": "0123456789abcdef", "candidates": []}

    def get(self, round_id):
        from src.services.selection.selection_service import RoundNotFound
        if round_id != "0123456789abcdef":
            raise RoundNotFound(round_id)
        return {"id": round_id}

    def show_more(self, round_id):
        self.calls.append(("more", round_id))
        return {**self.get(round_id), "candidates": []}

    def list(self, limit=20):
        return []

    def start_ai_selection(self, round_id, limit, min_score):
        self.calls.append(("ai", round_id, limit, min_score))
        return {"status": "running"}

    def queue(self, round_id, urls, start_job):
        self.calls.append(("queue", round_id, urls))
        job_id, _ = start_job(urls[0])
        return {"jobs": [{"url": urls[0], "jobId": job_id}]}


def use_selection(monkeypatch):

    _, started = use_ingestion(monkeypatch)
    selection = FakeSelection()
    monkeypatch.setattr(routes, "get_selection_service", lambda: selection)
    return selection, started


def test_a_round_needs_groups_and_known_sources(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    assert client.post("/ingest/rounds", json={}).status_code == 422
    assert client.post("/ingest/rounds", json={"groups": ["science"], "sources": ["nope"]}).status_code == 422
    assert client.post("/ingest/rounds", json={"groups": ["science"], "perSource": 50}).status_code == 422
    # Twenty shown by default, forty at most.
    assert client.post("/ingest/rounds", json={"groups": ["science"], "listed": 41}).status_code == 422

    response = client.post("/ingest/rounds", json={"groups": ["science"], "sources": ["nasa"], "perSource": 4})

    assert response.status_code == 200
    assert selection.calls == [("create", ["science"], ["nasa"], 4, 20)]

    client.post("/ingest/rounds", json={"groups": ["science"], "listed": 40})

    assert selection.calls[-1] == ("create", ["science"], None, 3, 40)


def test_more_of_a_round_is_shown_only_when_asked(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    assert client.post("/ingest/rounds/0123456789abcdef/more").status_code == 200
    assert selection.calls == [("more", "0123456789abcdef")]
    assert client.post("/ingest/rounds/fedcba9876543210/more").status_code == 404
    assert client.post("/ingest/rounds/not-a-round/more").status_code == 422


def test_the_ai_selection_starts_in_the_background(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    response = client.post("/ingest/rounds/0123456789abcdef/ai-selection", json={"limit": 12, "minScore": 7})

    assert response.status_code == 202
    assert selection.calls == [("ai", "0123456789abcdef", 12, 7.0)]
    assert client.post("/ingest/rounds/0123456789abcdef/ai-selection", json={"limit": 21}).status_code == 422


def test_a_queued_selection_becomes_ingestion_jobs(monkeypatch):

    selection, started = use_selection(monkeypatch)

    response = client.post("/ingest/rounds/0123456789abcdef/queue", json={"urls": ["https://news.example/1"]})

    assert response.status_code == 200
    assert started == [("https://news.example/1", "ingestion")]
    assert client.post("/ingest/rounds/0123456789abcdef/queue", json={"urls": []}).status_code == 422
    assert client.post(
        "/ingest/rounds/0123456789abcdef/queue",
        json={"urls": [f"https://news.example/{i}" for i in range(21)]},
    ).status_code == 422


def test_an_unknown_or_malformed_round_id(monkeypatch):

    use_selection(monkeypatch)

    assert client.get("/ingest/rounds/fedcba9876543210").status_code == 404
    assert client.get("/ingest/rounds/not-a-round").status_code == 422

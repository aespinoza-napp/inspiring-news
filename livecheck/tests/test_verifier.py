from livecheck.verifier import FALSE, MIXED, NOT_CHECKED, TRUE, UNVERIFIED, BackendVerifier, to_outcome


def test_verdicts_map_to_outcomes():
    assert to_outcome({"verdict": "TRUE"})["outcome"] == TRUE
    assert to_outcome({"verdict": "FALSE"})["outcome"] == FALSE
    assert to_outcome({"verdict": "MISLEADING"})["outcome"] == MIXED
    assert to_outcome({"verdict": "PARTIALLY_TRUE"})["outcome"] == MIXED
    assert to_outcome({"verdict": "UNVERIFIED"})["outcome"] == UNVERIFIED


def test_a_failed_search_or_model_is_not_a_finding_about_the_claim():
    assert to_outcome({"verdict": "UNVERIFIED", "searchUnavailable": True})["outcome"] == NOT_CHECKED
    assert to_outcome({"verdict": "UNVERIFIED", "llmUnreachable": True})["outcome"] == NOT_CHECKED


def test_only_the_cited_sources_are_listed():
    body = {
        "verdict": "FALSE",
        "evidence": [
            {"url": "a", "title": "A", "cited": True},
            {"url": "b", "title": "B", "cited": False},
        ],
    }

    assert [s["url"] for s in to_outcome(body)["sources"]] == ["a"]


def test_an_absent_backend_is_not_checked_rather_than_a_crash():
    verifier = BackendVerifier("http://127.0.0.1:9", timeout=1)

    assert verifier("The sky is blue.")["outcome"] == NOT_CHECKED
    assert verifier.reachable()


class _Answer:

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def test_a_graph_that_is_down_does_not_stop_claims_from_being_checked(monkeypatch):
    # /healthz answered 503 with only Neo4j down; a claim was then checked fine.
    checks = {name: {"ok": True} for name in ("inference", "searxng", "llm")}
    checks["neo4j"] = {"ok": False}

    monkeypatch.setattr("httpx.get", lambda *a, **k: _Answer({"ok": False, "checks": checks}))

    assert BackendVerifier().reachable() is None


def test_a_service_a_claim_needs_being_down_is_said_by_name(monkeypatch):
    checks = {"inference": {"ok": True}, "searxng": {"ok": False}, "llm": {"ok": True}}

    monkeypatch.setattr("httpx.get", lambda *a, **k: _Answer({"checks": checks}))

    assert "searxng" in BackendVerifier().reachable()

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.routes as routes
from src.config.settings import settings
from src.database.neo4j_client import ReadResult
from src.main import app
from src.services.graph.graph_reader import GraphReader
from src.services.graph.graph_writer import GraphWriter

from tests.services.graph.fake_graph_client import RecordingGraphClient

client = TestClient(app)


@pytest.fixture
def graph(monkeypatch):
    """
    A reader and writer over a recording fake, so these tests never touch
    the developer's own Neo4j - which, unlike the lake, has no tmp_path.
    """

    fake = RecordingGraphClient()

    monkeypatch.setattr(routes, "get_graph_reader", lambda: GraphReader(fake))
    monkeypatch.setattr(routes, "get_graph_writer", lambda: GraphWriter(fake))

    return fake


def test_neo4j_down_is_a_503_that_says_how_to_start_it(graph):

    graph.down = True

    response = client.get("/graph/schema")

    assert response.status_code == 503
    assert "docker compose" in response.json()["detail"]


def test_a_refused_console_query_is_a_400_and_never_sent(graph):

    response = client.post("/graph/query", json={"cypher": "LOAD CSV FROM 'http://x' AS l RETURN l"})

    assert response.status_code == 400
    assert "LOAD CSV" in response.json()["detail"]
    assert graph.reads_made == []


def test_a_console_query_returns_rows_and_the_graph_in_them(graph):

    graph._reads = [ReadResult(["n"], [{"n": 1}], False, [])]

    response = client.post("/graph/query", json={"cypher": "RETURN 1 AS n"})

    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [{"n": 1}]
    assert body["graph"] == {"nodes": [], "relationships": []}


def test_presets_answer_without_a_database(graph):

    graph.down = True

    response = client.get("/graph/presets")

    assert response.status_code == 200
    assert response.json()["presets"]


def test_related_needs_a_url(graph):

    assert client.get("/graph/related").status_code == 422


def test_sync_reports_what_it_wrote(graph, monkeypatch, tmp_path):

    import src.services.graph.graph_sync as graph_sync

    monkeypatch.setattr(graph_sync, "MANUAL_FACTS_PATH", tmp_path)
    monkeypatch.setattr(routes, "get_datalake_repository", lambda: None)

    response = client.post("/graph/sync")

    assert response.status_code == 200
    assert response.json() == {"sources": 0, "facts": 0, "articles": 0, "errors": []}


def test_graph_endpoints_are_behind_the_storage_key(graph, monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    for method, path in [
        ("get", "/graph/schema"),
        ("get", "/graph/presets"),
        ("get", "/graph/articles"),
        ("get", "/graph/related?url=x"),
        ("post", "/graph/query"),
        ("post", "/graph/sync"),
    ]:
        response = getattr(client, method)(path, **({"json": {"cypher": "RETURN 1"}} if method == "post" else {}))
        assert response.status_code == 401, path


# ----------------------------------------------------------------------
# /labelling/batch lives beside the graph routes: both are thin views over
# one container singleton.


class FakeBatch:

    def __init__(self, running=False):
        self.running = running
        self.requests = []

    def start(self, request):
        if self.running:
            return False
        self.requests.append(request)
        return True

    def state(self):
        return {"running": self.running, "batch": None, "error": None}


def test_a_labelling_batch_is_started_with_what_the_labeller_sent(monkeypatch):

    fake = FakeBatch()
    monkeypatch.setattr(routes, "get_labelling_batch", lambda: fake)

    response = client.post("/labelling/batch", json={
        "articles": 8, "claimsPerArticle": 2, "exclude": ["https://a/"],
        "preferTopics": ["medicine"], "languages": ["es"], "requestId": "r1",
    })

    assert response.status_code == 202
    request = fake.requests[0]
    assert (request.articles, request.claims_per_article, request.exclude) == (8, 2, ["https://a/"])
    assert (request.prefer_topics, request.languages, request.request_id) == (["medicine"], ["es"], "r1")


def test_a_second_labelling_batch_while_one_runs_is_a_409(monkeypatch):

    monkeypatch.setattr(routes, "get_labelling_batch", lambda: FakeBatch(running=True))

    assert client.post("/labelling/batch", json={}).status_code == 409


def test_labelling_batch_is_behind_the_storage_key(monkeypatch):

    monkeypatch.setattr(routes, "get_labelling_batch", lambda: FakeBatch())
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.get("/labelling/batch").status_code == 401
    assert client.post("/labelling/batch", json={}).status_code == 401

"""
POST /drafts: writing a new article from an analysed one
(src/api/draft_routes.py::create_draft). Over a real lake and a real
DraftStore; search, fetches, Qdrant and the model faked
(tests/services/writer/writer_fakes.py).
"""

import pytest
from fastapi.testclient import TestClient

import src.container as container
from src.main import app
from src.models.fact_checker.fact_check import Verdict
from tests.services.fact_checker.fakes import FakeLLMClient, FakeSearxngClient
from tests.services.writer.writer_fakes import ANALYSED_URL, answer, make_writer, published_lake

client = TestClient(app)


@pytest.fixture
def inline_store(draft_store, monkeypatch):
    """
    The draft store, with background work run in the request's thread:
    the route answers with the finished draft, and no test races a thread.
    """

    original = draft_store.run_in_background

    monkeypatch.setattr(
        draft_store,
        "run_in_background",
        lambda *args, **kwargs: original(*args, **{**kwargs, "wait": True}),
    )

    return draft_store


def install(monkeypatch, writer):

    monkeypatch.setattr(container, "_draft_writer", writer)

    return writer


def test_a_draft_is_written_from_a_published_article(tmp_path, inline_store, monkeypatch):

    lake, article_id = published_lake(tmp_path)
    llm = FakeLLMClient(answer())
    install(monkeypatch, make_writer(lake, llm=llm, search=FakeSearxngClient(results=[])))

    response = client.post(
        "/drafts",
        json={"articleId": article_id, "language": "ca", "instructions": "  Per a joves.  "},
    )

    assert response.status_code == 202

    body = response.json()

    assert body["sourceArticleId"] == article_id
    assert body["language"] == "ca"
    assert body["instructions"] == "Per a joves."
    assert body["busy"] is None and body["error"] is None
    assert body["content"]["title"] == "Un bosc torna a la vall"
    assert body["sources"][0] == {
        "url": ANALYSED_URL,
        "title": "Volunteers plant 40,000 trees",
        "domain": "bbc.com",
        "origin": "analysed",
        "publishedAt": body["sources"][0]["publishedAt"],
        "excerpt": body["sources"][0]["excerpt"],
        "reliabilityKnown": False,
    }
    assert body["factChecks"][0]["verdict"] == "TRUE"
    assert body["metadata"]["slug"] == "un-bosc-torna-a-la-vall"

    # The indications reach the model, and the language is named to it.
    _, prompt = llm.calls[0]
    assert "Per a joves." in prompt
    assert "LANGUAGE: Catalan (català)" in prompt

    # Listed, and saved where the store keeps it.
    assert [row["id"] for row in client.get("/drafts").json()] == [body["id"]]


def test_the_article_can_be_named_by_its_url(tmp_path, inline_store, monkeypatch):

    lake, article_id = published_lake(tmp_path)
    install(monkeypatch, make_writer(lake))

    response = client.post(
        "/drafts",
        json={"articleUrl": f"{ANALYSED_URL}?utm_source=newsletter", "language": "es"},
    )

    assert response.status_code == 202
    assert response.json()["sourceArticleId"] == article_id


def test_the_answer_is_immediate_and_the_draft_busy(tmp_path, draft_store, monkeypatch):
    """Without the inline store: the request does not wait for the model."""

    lake, article_id = published_lake(tmp_path)

    started = []

    writer = install(monkeypatch, make_writer(lake))
    monkeypatch.setattr(writer, "generate", lambda *args, **kwargs: started.append(args))

    body = client.post("/drafts", json={"articleId": article_id, "language": "en"}).json()

    assert body["busy"] == "generating"
    assert body["content"]["title"] == "Volunteers plant 40,000 trees"


def test_an_article_the_reader_withholds_is_a_404_and_no_draft(tmp_path, inline_store, monkeypatch):

    lake, article_id = published_lake(tmp_path, verdict=Verdict.MISLEADING)
    install(monkeypatch, make_writer(lake))

    response = client.post("/drafts", json={"articleId": article_id, "language": "en"})

    assert response.status_code == 404
    assert "publishes" in response.json()["detail"]
    assert inline_store.list() == []


@pytest.mark.parametrize(
    "body",
    [
        {"language": "en"},
        {"articleId": "0123456789abcdef", "articleUrl": ANALYSED_URL, "language": "en"},
        {"articleId": "not-an-id", "language": "en"},
        {"articleId": "0123456789abcdef", "language": "fr"},
        {"articleId": "0123456789abcdef", "language": "en", "instructions": "x" * 4001},
        {"articleId": "0123456789abcdef", "language": "en", "thresholds": {"related_max_sources": 99}},
        {"articleId": "0123456789abcdef", "language": "en", "thresholds": {"no_such_knob": 1}},
    ],
)
def test_a_malformed_request_is_a_422(body, inline_store):

    assert client.post("/drafts", json=body).status_code == 422


def test_per_draft_thresholds_reach_the_writer(tmp_path, inline_store, monkeypatch):

    lake, article_id = published_lake(tmp_path)
    search = FakeSearxngClient(results=[])
    install(monkeypatch, make_writer(lake, search=search))

    response = client.post(
        "/drafts",
        json={"articleId": article_id, "language": "en", "thresholds": {"related_max_sources": 0}},
    )

    assert response.status_code == 202
    # related_max_sources=0 searches nothing.
    assert search.queries == []
    assert [source["origin"] for source in response.json()["sources"]] == ["analysed", "evidence"]


def test_a_model_failure_is_kept_on_the_draft(tmp_path, inline_store, monkeypatch):

    from src.services.llms import LLMUnavailableError

    lake, article_id = published_lake(tmp_path)
    install(monkeypatch, make_writer(lake, llm=FakeLLMClient(LLMUnavailableError("connection refused"))))

    body = client.post("/drafts", json={"articleId": article_id, "language": "en"}).json()

    assert body["busy"] is None
    assert "could not be reached" in body["error"]
    assert body["sources"][0]["origin"] == "analysed"

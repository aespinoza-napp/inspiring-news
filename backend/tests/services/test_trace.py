"""
One article's journey (src/services/trace.py): every stage's own record,
joined by the article's host and path - whatever id a page shows.
"""

import pytest
from fastapi.testclient import TestClient

import src.api.routes as routes
import src.container as container
from src.main import app
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.lake_backend import JsonFileLakeBackend
from src.services.job_journal import JobJournal
from src.services.job_store import JobStore
from src.services.reader.views import reader_id
from src.services.selection.rounds import SelectionRounds
from src.services.trace import NotTraceable, resolve, trace

from tests.factories import create_article, create_draft
from tests.repositories.test_datalake_repository import make_news, make_report

URL = "https://bbc.com/test"
KEY = reader_id(URL)


class NoReader:
    """The reader index for an article it does not publish."""

    def article(self, article_id):
        return None


@pytest.fixture
def stages(tmp_path):

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path / "lake"))
    jobs = JobStore(journal=JobJournal(tmp_path / "journal"))
    rounds = SelectionRounds(tmp_path / "rounds")

    from src.services.writer.draft_store import DraftStore

    drafts = DraftStore(tmp_path / "drafts")

    return {"lake": lake, "jobs": jobs, "rounds": rounds, "drafts": drafts, "reader": NoReader()}


def a_round(round_id="r1", url=URL, queued_job=None):

    round_ = {
        "id": round_id,
        "startedAt": "2026-11-01T09:00:00+00:00",
        "edition": "positive",
        "groups": ["planet"],
        "candidates": [
            {"url": "https://example.org/other", "title": "Another"},
            {"url": url + "/?utm_source=feed", "title": "The test article", "sourceName": "BBC News", "rank": {"score": 0.7}},
        ],
        "reserve": [],
        "aiSelection": {"status": "done", "model": "m", "picks": [{"url": url + "/?utm_source=feed", "score": 8, "reason": "constructive"}]},
        "queued": None,
    }

    if queued_job:
        round_["queued"] = {
            "at": "2026-11-01T09:05:00+00:00",
            "urls": [url + "/?utm_source=feed"],
            "jobs": [{"url": url + "/?utm_source=feed", "jobId": queued_job, "reused": False}],
            "selectedBy": "ai",
        }

    return round_


def test_every_stage_is_found_from_the_url(stages):

    job = stages["jobs"].create(URL)
    stages["jobs"].complete(job.job_id, {"url": URL})

    stages["rounds"].save(a_round(queued_job=job.job_id))

    run = stages["lake"].start_run(URL)
    stages["lake"].persist_all(run, make_news(), create_article(), make_report())

    stages["drafts"].save(create_draft(source_article_id=KEY))

    found = trace(URL, **stages)

    assert found["key"] == KEY
    assert found["url"] == URL

    # The round listed it second, the AI picked it and it was sent on as this job.
    [listed] = found["discovery"]
    assert listed["place"] == 2
    assert listed["ai"]["picked"] is True
    assert listed["queued"] is True and listed["jobId"] == job.job_id

    assert [entry["jobId"] for entry in found["jobs"]] == [job.job_id]

    # One run, all three layers, each with its parent.
    [stored] = found["runs"]
    assert set(stored["layers"]) == {"raw", "processed", "exploitation"}
    assert stored["reached"] == "exploitation"
    assert stored["outcome"]["publishable"] is True
    assert any(write["parentLayer"] == "raw" for write in stored["writes"])

    assert found["reader"] == {"published": False, "id": KEY}
    assert len(found["drafts"]) == 1


def test_a_tracking_parameter_or_slash_is_the_same_article(stages):

    stages["rounds"].save(a_round())

    assert len(trace(URL + "/?ref=x", **stages)["discovery"]) == 1


def test_another_article_is_not_mixed_in(stages):

    stages["rounds"].save(a_round(url="https://bbc.com/elsewhere"))

    run = stages["lake"].start_run("https://bbc.com/elsewhere")
    stages["lake"].persist_all(run, make_news(url="https://bbc.com/elsewhere"), create_article(url="https://bbc.com/elsewhere"), make_report())

    found = trace(URL, **stages)

    assert found["discovery"] == [] and found["runs"] == []


def test_a_job_id_resolves_to_its_article(stages):

    job = stages["jobs"].create(URL)

    assert resolve(job.job_id, jobs=stages["jobs"], drafts=stages["drafts"], reader=None)["key"] == KEY


def test_a_draft_id_resolves_to_the_article_it_was_written_from(stages):

    draft = stages["drafts"].save(create_draft(source_article_id=KEY))

    target = resolve(draft.id, jobs=stages["jobs"], drafts=stages["drafts"], reader=None)

    assert target == {"key": KEY, "url": None, "from": "draft"}


def test_a_claim_job_has_no_journey(stages):

    job = stages["jobs"].create("The river was declared clean.", kind="claim")

    with pytest.raises(NotTraceable):
        resolve(job.job_id, jobs=stages["jobs"], drafts=stages["drafts"], reader=None)


def test_anything_else_is_refused(stages):

    with pytest.raises(NotTraceable):
        resolve("../../etc/passwd", jobs=stages["jobs"], drafts=stages["drafts"], reader=None)


def test_a_job_only_in_the_journal_is_still_found(tmp_path):
    """After a restart: memory is empty, the journal is not."""

    journal = JobJournal(tmp_path / "journal")

    before = JobStore(journal=journal)
    job = before.create(URL)
    before.complete(job.job_id, {"url": URL})

    after = JobStore(journal=journal)

    [found] = after.find(lambda url, kind: url == URL)

    assert found.job_id == job.job_id
    assert found.status == "done"


# ----------------------------------------------------------------------
# The route
# ----------------------------------------------------------------------


def test_the_route_answers_and_refuses(stages, monkeypatch):

    monkeypatch.setattr(routes, "get_datalake_repository", lambda: stages["lake"])
    monkeypatch.setattr(routes, "job_store", stages["jobs"])
    monkeypatch.setattr(routes, "get_reader_index", lambda: stages["reader"])
    monkeypatch.setattr(container, "_draft_store", stages["drafts"])

    import src.services.selection.rounds as rounds_module

    monkeypatch.setattr(rounds_module, "selection_rounds", stages["rounds"])

    stages["rounds"].save(a_round())

    client = TestClient(app)

    response = client.get("/trace", params={"q": URL})

    assert response.status_code == 200
    assert len(response.json()["discovery"]) == 1

    assert client.get("/trace", params={"q": "not an id"}).status_code == 422

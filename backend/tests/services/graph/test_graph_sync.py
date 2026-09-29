import json
from datetime import datetime

from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.storage.lineage import DataLayer
from src.services.graph import graph_writer as gw
from src.services.graph.graph_sync import GraphSync
from src.services.graph.graph_writer import GraphWriter

from tests.factories import create_article
from tests.services.graph.fake_graph_client import RecordingGraphClient


class FakeLake:

    def __init__(self, records):
        self.records = records

    def list(self, layer, limit=None):
        assert layer == DataLayer.PROCESSED
        return self.records


def processed(url, checked_at, report=True, run_id="run"):

    article = create_article(url=url)

    return {
        "record_id": f"{url}-{checked_at}",
        "layer": "processed",
        "lineage": {
            "run_id": run_id,
            "article_id": article.id,
            "layer": "processed",
            "source_url": url,
            "content_hash": "h",
            "pipeline_version": "1",
        },
        "article": article.model_dump(mode="json"),
        "fact_check": (
            FactCheckReport(
                article_id=article.id,
                validation_passed=True,
                checked_at=checked_at,
            ).model_dump(mode="json")
            if report
            else None
        ),
    }


def fact(fact_id, **kwargs):
    values = {
        "id": fact_id,
        "claim": f"Claim of {fact_id}",
        "label": "TRUE",
        "articleUrl": f"https://example.com/{fact_id}",
        "referenceEvidenceLinks": [],
    }
    values.update(kwargs)
    return values


def test_sync_writes_every_fact_and_reports_a_bad_file_without_stopping(tmp_path):

    (tmp_path / "fact001.json").write_text(json.dumps(fact("fact001")), encoding="utf-8")
    (tmp_path / "fact002.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "fact003.json").write_text(json.dumps(fact("fact003")), encoding="utf-8")
    (tmp_path / "notes.json").write_text(json.dumps(fact("ignored")), encoding="utf-8")

    client = RecordingGraphClient()

    report = GraphSync(GraphWriter(client), facts_path=tmp_path).run()

    assert report["facts"] == 2
    assert [e["item"] for e in report["errors"]] == ["fact002.json"]

    written = [p["fact_id"] for p in client.params_of(gw.LINK_FACT)]
    assert written == ["fact001", "fact003"]


def test_sync_writes_the_newest_verified_run_of_each_lake_article(tmp_path):

    lake = FakeLake([
        processed("https://a/", datetime(2026, 9, 1), run_id="old"),
        processed("https://a/", datetime(2026, 9, 2), run_id="new"),
        processed("https://b/", datetime(2026, 9, 1), report=False),
    ])

    client = RecordingGraphClient()

    report = GraphSync(GraphWriter(client), lake=lake, facts_path=tmp_path).run()

    assert report["articles"] == 1

    upserts = client.params_of(gw.UPSERT_ARTICLE)
    assert [(p["url"], p["props"]["run_id"]) for p in upserts] == [("https://a/", "new")]


def test_an_unreadable_lake_record_is_reported_not_fatal(tmp_path):

    lake = FakeLake([{"record_id": "broken"}, processed("https://a/", datetime(2026, 9, 1))])

    report = GraphSync(GraphWriter(RecordingGraphClient()), lake=lake, facts_path=tmp_path).run()

    assert report["articles"] == 1
    assert report["errors"][0]["item"] == "broken"

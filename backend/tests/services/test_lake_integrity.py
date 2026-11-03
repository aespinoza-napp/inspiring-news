"""
Does the lake hold together (services/lake_integrity.py): a clean lake
passes, and each way a record can be untrue is caught.
"""

import json

import pytest

from src.models.storage.lineage import DataLayer
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.lake_backend import JsonFileLakeBackend
from src.services.lake_integrity import verify

from tests.factories import create_article
from tests.repositories.test_datalake_repository import make_news, make_report


@pytest.fixture
def lake(tmp_path):
    return DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))


def seed(lake):

    run = lake.start_run("https://bbc.com/test")

    news = make_news()

    return lake.persist_all(run, news, create_article(body=news.content), make_report())


def edit(lake, layer, record_id, change):

    path = lake.backend.root / layer.value / f"{record_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    change(record)
    path.write_text(json.dumps(record), encoding="utf-8")


def kinds(report):
    return {issue.kind for issue in report.errors}


def test_a_clean_lake_has_no_errors(lake):

    seed(lake)

    report = verify(lake)

    assert report.errors == []
    assert report.runs == report.runs_complete == 1
    assert report.records["raw"] == report.records["processed"] == report.records["exploitation"] == 1


def test_an_empty_lake_is_fine(lake):

    assert verify(lake).view()["ok"] is True


def test_a_changed_body_is_caught(lake):

    written = seed(lake)

    edit(lake, DataLayer.RAW, written.raw_record_id, lambda record: record["article"].update(content="Another text."))

    assert "body_hash_mismatch" in kinds(verify(lake))


def test_a_vanished_parent_is_caught(lake):

    written = seed(lake)

    (lake.backend.root / "processed" / f"{written.processed_record_id}.json").unlink()

    assert "parent_missing" in kinds(verify(lake))


def test_a_served_verdict_that_is_not_the_reports_is_caught(lake):

    written = seed(lake)

    edit(lake, DataLayer.EXPLOITATION, written.exploitation_record_id, lambda record: record.update(verdict="TRUE" if record["verdict"] != "TRUE" else "FALSE"))

    assert "verdict_differs_from_report" in kinds(verify(lake))


def test_a_publishable_false_is_caught(lake):

    written = seed(lake)

    def falsify(record):
        record.update(verdict="FALSE", publishable=True)

    edit(lake, DataLayer.EXPLOITATION, written.exploitation_record_id, falsify)

    assert "publishable_with_blocking_verdict" in kinds(verify(lake))


def test_a_record_in_the_wrong_folder_is_caught(lake):

    written = seed(lake)

    edit(lake, DataLayer.RAW, written.raw_record_id, lambda record: record["lineage"].update(run_id="another"))

    found = kinds(verify(lake))

    assert "wrong_id" in found and "parent_mismatch" in found


def test_a_record_the_manifest_never_logged_is_a_warning_not_an_error(lake):

    seed(lake)

    (lake.backend.root / "_manifest.jsonl").write_text("", encoding="utf-8")

    report = verify(lake)

    assert report.errors == []
    assert "not_in_manifest" in {issue.kind for issue in report.issues}


def test_a_run_records_every_threshold_it_used(lake):

    from src.config.thresholds import PipelineThresholds

    run = lake.start_run("https://bbc.com/test", PipelineThresholds(evidence_independence=False))

    assert run.thresholds["evidence_independence"] is False
    assert run.thresholds["max_evidence_per_claim"] == PipelineThresholds().max_evidence_per_claim


def test_the_image_says_which_code_it_holds(monkeypatch):

    from src.repositories.datalake_repository import _code_revision

    monkeypatch.setenv("CODE_REVISION", "abc1234-dirty")

    assert _code_revision() == "abc1234-dirty"


def test_the_models_the_lineage_names_are_the_ones_inference_loads():
    """
    The lineage names them from the backend's settings; they load in
    inference/, from its own defaults. Two lists, kept the same here, or
    every record would name a model that did not run.
    """

    import re
    from pathlib import Path

    from src.config.settings import Settings

    config = (Path(__file__).resolve().parents[3] / "inference" / "src" / "config.py").read_text(encoding="utf-8")

    for name in ("SENTIMENT_MODEL", "EMBEDDING_MODEL"):
        declared = re.search(rf'{name}: str = "([^"]+)"', config).group(1)
        assert Settings.model_fields[name].default == declared, name

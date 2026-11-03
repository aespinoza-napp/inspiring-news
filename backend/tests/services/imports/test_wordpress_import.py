"""
A WordPress export into the lake and the graph without a fact-check
(services/imports/wordpress_import.py, AnalysisService.analyze_news).
"""

import json
import time
from unittest.mock import Mock

import pytest

from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.repositories.datalake_repository import DataLakeRepository
from src.services.analysis_service import AnalysisService
from src.services.graph.graph_writer import GraphWriter
from src.services.imports.wordpress import NotAnExport
from src.services.imports.wordpress_import import WordPressImport, summarise, to_news

from tests.factories import create_article, create_claim
from tests.services.graph.fake_graph_client import RecordingGraphClient
from tests.services.imports.test_wordpress import BODY, export, item
from tests.services.test_analysis_service import FakeAdmission, admitted


def service(admission, graph=None):

    enrichment = Mock()
    enrichment.process.side_effect = lambda news, thresholds=None: create_article(
        url=news.url, source_id=news.source_id, claims=[create_claim(), create_claim()],
    )

    fact_checker = Mock()
    fact_checker.run.return_value = FactCheckReport(article_id="a", validation_passed=True, overall_verdict=Verdict.TRUE)

    return AnalysisService(
        fact_checker=fact_checker,
        extractor=Mock(),
        enrichment_pipeline=enrichment,
        admission=admission,
        graph=graph,
    )


def news():

    from src.services.imports.wordpress import parse

    (post,) = parse(export(item(7332, "La línea de ayuda", BODY))).posts

    return to_news(post, "wordpress:inspiringnews.ai")


def test_an_unverified_import_is_enriched_and_admitted_but_never_checked_or_remembered():

    admission = FakeAdmission(admitted())
    graph = Mock()
    made = service(admission, graph)
    phases = []

    result = made.analyze_news(news(), on_phase=lambda phase, data: phases.append(phase), verify=False, remember=False)

    made.extractor.extract.assert_not_called()
    made.fact_checker.run.assert_not_called()
    assert "fact_check_skipped" in phases

    # Not in the corpus a later check searches: it would be its own evidence.
    assert admission.remembered == []

    assert result["validity"]["isValid"] is True
    assert result["factCheck"]["claimsTotal"] == 2 and result["factCheck"]["claimsChecked"] == 0

    report = graph.write_analysis.call_args.args[1]
    assert report.fact_check_skipped == "import"
    # And never on the reader as an article this newsroom checked.
    assert not DataLakeRepository._is_publishable(report)
    assert DataLakeRepository._rejection_reasons(report) == ["imported_not_checked"]


def test_a_post_that_fails_the_filters_is_still_imported_as_rejected():

    graph = Mock()
    made = service(FakeAdmission(admitted(passed=False, positive_ok=False)), graph)

    result = made.analyze_news(news(), verify=False, remember=False)

    assert result["validity"]["isValid"] is False
    assert result["validity"]["reasons"] == ["not_positive_impact"]
    graph.write_analysis.assert_called_once()


def test_a_verified_import_is_checked_on_the_same_text():

    admission = FakeAdmission(admitted())
    made = service(admission)

    made.analyze_news(news(), verify=True, remember=True)

    made.fact_checker.run.assert_called_once()
    (article,) = admission.remembered
    assert article.url == "https://inspiringnews.ai/sociedad/p7332/"


def test_the_graph_says_no_one_checked_it_rather_than_unverified():

    writer = GraphWriter(RecordingGraphClient())
    report = AnalysisService._unchecked(create_article(source_id="wordpress:inspiringnews.ai"), "import")

    props = writer.analysis_statements(create_article(source_id="wordpress:inspiringnews.ai"), report)[0][1]["props"]

    assert props["admitted"] is True
    assert props["fact_checked"] is False and props["fact_check_skipped"] == "import"
    assert props["overall_verdict"] is None and props["overall_confidence"] is None
    assert props["topic_ok"] is True and props["source_id"] == "wordpress:inspiringnews.ai"


def test_a_checked_article_keeps_its_verdict_in_the_graph():

    writer = GraphWriter(RecordingGraphClient())
    report = FactCheckReport(article_id="a", validation_passed=True, overall_verdict=Verdict.TRUE)

    props = writer.analysis_statements(create_article(), report)[0][1]["props"]

    assert props["fact_checked"] is True and props["overall_verdict"] == "TRUE"


def wait(runner):

    for _ in range(200):
        if not runner.state()["running"]:
            return runner.state()
        time.sleep(0.01)

    raise AssertionError("the import never finished")


def test_the_import_keeps_a_snapshot_and_a_line_per_post(tmp_path):

    analysis = Mock()
    analysis.analyze_news.side_effect = [
        {"validity": {"isValid": True, "reasons": []}, "storage": {"runId": "r1", "persisted": True},
         "factCheck": {"claimsTotal": 3, "claimsChecked": 0}, "topics": [{"topic": "health"}]},
        {"validity": {"isValid": False, "reasons": ["off_topic"]}, "storage": {"runId": "r2", "persisted": True},
         "factCheck": {"claimsTotal": 1, "claimsChecked": 0}},
        RuntimeError("inference down"),
    ]

    runner = WordPressImport(analysis, tmp_path)
    started = runner.start(export(
        item(1, "Uno", BODY, date="2026-01-01 00:00:00"),
        item(2, "Dos", BODY + " dos", date="2026-01-02 00:00:00"),
        item(3, "Tres", BODY + " tres", date="2026-01-03 00:00:00"),
    ))

    assert started["total"] == 3 and started["sourceId"] == "wordpress:inspiringnews.ai"

    state = wait(runner)

    # Unverified, and kept out of the corpus, every time.
    for call in analysis.analyze_news.call_args_list:
        assert call.kwargs["verify"] is False and call.kwargs["remember"] is False

    assert state["summary"] == {
        "imported": 2, "failed": 1, "passedFilters": 1, "rejected": 1,
        "rejectedFor": {"off_topic": 1}, "duplicatesInFile": 0, "claims": 4, "stored": 2,
    }

    folder = tmp_path / started["importId"]
    snapshot = [json.loads(line) for line in (folder / "snapshot.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["wp_id"] for row in snapshot] == [1, 2, 3]
    assert len((folder / "results.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert json.loads((folder / "summary.json").read_text(encoding="utf-8"))["summary"]["failed"] == 1
    assert runner.snapshot_path() == folder / "snapshot.jsonl"


def test_a_bad_file_is_refused_before_anything_runs(tmp_path):

    runner = WordPressImport(Mock(), tmp_path)

    with pytest.raises(NotAnExport):
        runner.start(b"<html/>")

    assert runner.state()["importId"] is None and not list(tmp_path.iterdir())


def test_one_import_at_a_time(tmp_path):

    analysis = Mock()
    analysis.analyze_news.side_effect = lambda *args, **kwargs: time.sleep(0.2) or {}

    runner = WordPressImport(analysis, tmp_path)
    runner.start(export(item(1, "Uno", BODY)))

    with pytest.raises(RuntimeError, match="already running"):
        runner.start(export(item(2, "Dos", BODY)))

    wait(runner)


def test_an_empty_run_summarises_to_zeros():

    assert summarise([])["imported"] == 0


def test_the_lake_keeps_the_post_as_read_and_never_publishes_it(tmp_path):

    from src.models.storage.lineage import DataLayer
    from src.repositories.lake_backend import JsonFileLakeBackend

    made = service(FakeAdmission(admitted()))
    made.lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    result = made.analyze_news(news(), verify=False, remember=False, extractor="wordpress_export")

    assert result["storage"]["persisted"] is True
    assert result["storage"]["publishable"] is False

    (raw,) = made.lake.list(DataLayer.RAW)
    assert raw["extractor"] == "wordpress_export"
    assert raw["article"]["metadata"]["wp_id"] == 7332
    assert raw["article"]["metadata"]["imported_from"] == "wordpress:inspiringnews.ai"

    (served,) = made.lake.list(DataLayer.EXPLOITATION)
    assert served["publishable"] is False

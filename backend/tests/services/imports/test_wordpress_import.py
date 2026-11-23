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
    enrichment.process.side_effect = lambda news, thresholds=None, article_entities=True: create_article(
        url=news.url, source_id=news.source_id, claims=[create_claim(), create_claim()],
        entities={}, image_url=news.image_url, image_alt=news.image_alt,
    )
    enrichment.entities_of.return_value = {"person": ["Olga Moraga"], "organization": ["Colegio Oficial de Psicología"]}

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
        # Its names all the same: what joins its posts in the graph.
        assert call.kwargs["unchecked_entities"] is True

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


# ---------------------------------------------------------------------------
# Names, sources and photos (2026-11-20)
# ---------------------------------------------------------------------------

def test_an_unverified_import_keeps_its_names_though_it_never_checks_out():
    """
    The 17 Nov rule keeps an article's names for after its check; an
    unverified import never checks out, and would have none in the graph.
    """

    graph = Mock()
    made = service(FakeAdmission(admitted()), graph)
    events = []

    result = made.analyze_news(
        news(), on_phase=lambda phase, data: events.append((phase, data)),
        verify=False, remember=False, unchecked_entities=True,
    )

    assert ("article_entities", {"reason": "import"}) in events
    assert result["entities"]["person"] == ["Olga Moraga"]
    assert graph.write_analysis.call_args.args[0].entities["person"] == ["Olga Moraga"]


def test_a_rejected_import_keeps_its_names_too():

    made = service(FakeAdmission(admitted(passed=False, positive_ok=False)), Mock())

    result = made.analyze_news(news(), verify=False, remember=False, unchecked_entities=True)

    assert result["validity"]["isValid"] is False and result["entities"]["person"] == ["Olga Moraga"]


def test_without_the_switch_the_rule_of_17_nov_holds():

    made = service(FakeAdmission(admitted()), Mock())
    events = []

    result = made.analyze_news(news(), on_phase=lambda phase, data: events.append(phase), verify=False, remember=False)

    assert "article_entities_skipped" in events and result["entities"] == {}
    made.enrichment_pipeline.entities_of.assert_not_called()


def photographed():

    from src.services.imports.wordpress import parse
    from tests.services.imports.test_wordpress import METADATA, STORY, attachment

    (post,) = parse(export(
        attachment(267, "https://inspiringnews.ai//wp-content/uploads/2025/02/tmpnjt92rgc.png", alt="Monos", metadata=METADATA),
        item(250, "Monos que bromean", STORY + "<p><strong>Fuentes:</strong></p><p>NPR.</p>", meta={"_thumbnail_id": "267"}),
    )).posts

    return post


def test_the_post_s_photos_and_sources_go_with_it_and_its_text_has_neither():

    post = photographed()
    made = to_news(post, "wordpress:inspiringnews.ai")

    assert made.image_url == "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc.png"
    assert made.image_alt == "Monos"
    assert made.metadata["images"] == post.images
    assert made.metadata["source_list"] == [{"text": "NPR", "url": None}]
    assert "Fuentes" not in made.content and "NPR" not in made.content


def test_the_lake_and_the_graph_keep_the_photo(tmp_path):

    from src.models.storage.lineage import DataLayer
    from src.repositories.lake_backend import JsonFileLakeBackend

    graph = Mock()
    made = service(FakeAdmission(admitted()), graph)
    made.lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    made.analyze_news(to_news(photographed(), "wordpress:inspiringnews.ai"), verify=False, remember=False, unchecked_entities=True)

    (raw,) = made.lake.list(DataLayer.RAW)
    assert raw["article"]["image_url"].endswith("/tmpnjt92rgc.png")
    assert raw["article"]["metadata"]["images"][0]["sizes"]["medium_large"]["width"] == 768

    (processed,) = made.lake.list(DataLayer.PROCESSED)
    assert processed["article"]["image_url"].endswith("/tmpnjt92rgc.png")

    article = graph.write_analysis.call_args.args[0]
    props = GraphWriter(RecordingGraphClient()).analysis_statements(article, graph.write_analysis.call_args.args[1])[0][1]["props"]
    assert props["image_url"].endswith("/tmpnjt92rgc.png") and props["image_alt"] == "Monos"


def test_the_import_s_line_counts_names_sources_and_photos():

    from src.services.imports.wordpress_import import outcome

    line = outcome(photographed(), {"validity": {"isValid": True}, "entities": {"person": ["A", "B"], "city": ["C"]}})

    assert (line["entities"], line["sourcesListed"], line["images"]) == (3, 1, 1)

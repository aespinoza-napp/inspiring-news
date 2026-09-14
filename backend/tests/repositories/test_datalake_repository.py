from datetime import datetime

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.core.news import News
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.models.storage.lineage import DataLayer, build_record_id
from src.repositories.datalake_repository import DataLakeRepository, content_hash
from src.repositories.lake_backend import JsonFileLakeBackend

from tests.factories import create_article, create_evidence

ARTICLE_ID = "11111111-1111-1111-1111-111111111111"

BODY = "A long article body about a real event."


@pytest.fixture
def lake(tmp_path):

    return DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))


def make_news(**kwargs) -> News:

    defaults = dict(
        id=ARTICLE_ID,
        source_id="bbc",
        url="https://bbc.com/test",
        title="Test article",
        published_at=datetime(2024, 1, 1),
        content=BODY,
    )

    defaults.update(kwargs)

    return News(**defaults)


def make_report(**kwargs) -> FactCheckReport:

    defaults = dict(
        article_id=ARTICLE_ID,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        impact_score=0.72,
        claims_total=3,
        claims_selected=2,
        overall_verdict=Verdict.TRUE,
        overall_confidence=0.81,
    )

    defaults.update(kwargs)

    return FactCheckReport(**defaults)


def persist(lake, news=None, article=None, report=None):

    run = lake.start_run("https://bbc.com/test")

    news = news if news is not None else make_news()
    article = article if article is not None else create_article(body=BODY)
    report = report if report is not None else make_report()

    return run, lake.persist_all(run, news, article, report)


# ----------------------------------------------------------------------
# Record ids and runs
# ----------------------------------------------------------------------


def test_record_id_is_deterministic_per_layer_article_and_run():

    first = build_record_id(DataLayer.RAW, "article", "run")
    second = build_record_id(DataLayer.RAW, "article", "run")

    assert first == second


def test_record_id_differs_across_layers_articles_and_runs():

    base = build_record_id(DataLayer.RAW, "article", "run")

    assert base != build_record_id(DataLayer.PROCESSED, "article", "run")
    assert base != build_record_id(DataLayer.RAW, "other", "run")
    assert base != build_record_id(DataLayer.RAW, "article", "other")


def test_start_run_stamps_the_component_versions(lake):

    run = lake.start_run("https://bbc.com/test")

    assert run.run_id
    assert set(run.components) == {
        "embedding_model",
        "sentiment_model",
        "llm_model",
    }


def test_two_runs_get_different_ids(lake):

    assert lake.start_run("https://a").run_id != lake.start_run("https://a").run_id


# ----------------------------------------------------------------------
# The three layers
# ----------------------------------------------------------------------


def test_persist_all_writes_one_record_into_each_layer(lake):

    persist(lake)

    for layer in DataLayer:
        assert len(lake.list(layer)) == 1


def test_persist_all_returns_the_written_record_ids(lake):

    _, written = persist(lake)

    assert lake.get(DataLayer.RAW, written.raw_record_id) is not None
    assert lake.get(DataLayer.PROCESSED, written.processed_record_id) is not None
    assert lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id) is not None


def test_every_layer_shares_the_run_id_and_content_hash(lake):

    run, written = persist(lake)

    assert written.content_hash == content_hash(BODY)

    for layer in DataLayer:

        lineage = lake.list(layer)[0]["lineage"]

        assert lineage["run_id"] == run.run_id
        assert lineage["content_hash"] == written.content_hash
        assert lineage["article_id"] == ARTICLE_ID


def test_each_layer_points_back_at_the_one_above_it(lake):

    _, written = persist(lake)

    raw = lake.get(DataLayer.RAW, written.raw_record_id)
    processed = lake.get(DataLayer.PROCESSED, written.processed_record_id)
    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert raw["lineage"]["parent_record_id"] is None
    assert raw["lineage"]["parent_layer"] is None

    assert processed["lineage"]["parent_layer"] == "raw"
    assert processed["lineage"]["parent_record_id"] == written.raw_record_id

    assert exploitation["lineage"]["parent_layer"] == "processed"
    assert exploitation["lineage"]["parent_record_id"] == written.processed_record_id


def test_raw_layer_keeps_the_untouched_article_and_fetch_metadata(lake):

    _, written = persist(lake)

    raw = lake.get(DataLayer.RAW, written.raw_record_id)

    assert raw["article"]["content"] == BODY
    assert raw["content_length"] == len(BODY)
    assert raw["extractor"] == "trafilatura"


def test_processed_layer_keeps_the_enrichment_and_the_fact_check(lake):

    _, written = persist(lake)

    processed = lake.get(DataLayer.PROCESSED, written.processed_record_id)

    assert processed["article"]["embedding_model"] == "bge-m3"
    assert processed["fact_check"]["overall_verdict"] == "TRUE"
    assert processed["fact_check"]["claims_total"] == 3


def test_exploitation_layer_is_flat_and_carries_no_embedding(lake):
    """
    The serving document points at the vector in Qdrant rather than
    inlining 1024 floats that would dwarf the rest of the document.
    """

    _, written = persist(lake)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert "embedding" not in exploitation
    assert exploitation["vector_collection"] == "news"
    assert exploitation["embedding_model"] == "bge-m3"
    assert exploitation["embedding_dimension"] == 1024


def test_exploitation_layer_flattens_the_editorial_decision(lake):

    _, written = persist(lake)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["publishable"] is True
    assert exploitation["validation_passed"] is True
    assert exploitation["rejection_reasons"] == []
    assert exploitation["verdict"] == "TRUE"
    assert exploitation["verdict_confidence"] == 0.81
    assert exploitation["claims_total"] == 3
    assert exploitation["claims_checked"] == 2
    assert exploitation["impact_score"] == 0.72
    assert exploitation["primary_topic"] == "environment"


# ----------------------------------------------------------------------
# Publishability - the edge cases that decide what reaches a reader
# ----------------------------------------------------------------------


def test_article_that_failed_validation_is_not_publishable(lake):

    report = make_report(
        validation_passed=False,
        skipped_reason="topic_not_relevant,duplicate_article",
        topic_ok=False,
        duplicate=True,
        failed_stage=PipelineStage.ADMISSION_FILTER,
        overall_verdict=Verdict.UNVERIFIED,
    )

    _, written = persist(lake, report=report)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert written.publishable is False
    assert exploitation["publishable"] is False
    assert exploitation["is_duplicate"] is True
    assert exploitation["rejection_reasons"] == [
        "topic_not_relevant",
        "duplicate_article",
    ]


@pytest.mark.parametrize("verdict", [Verdict.FALSE, Verdict.MISLEADING])
def test_a_false_or_misleading_verdict_blocks_publication(lake, verdict):

    _, written = persist(lake, report=make_report(overall_verdict=verdict))

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["publishable"] is False
    assert exploitation["rejection_reasons"] == [f"verdict_{verdict.value.lower()}"]


def test_an_unverified_verdict_still_allows_publication(lake):
    """
    UNVERIFIED means "no evidence either way", not "wrong" - and with a
    local model plus a self-hosted search index it is the common outcome.
    Treating it as a block would empty the feed.
    """

    _, written = persist(lake, report=make_report(overall_verdict=Verdict.UNVERIFIED))

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["publishable"] is True
    assert exploitation["rejection_reasons"] == []


def test_a_missing_fact_check_report_is_not_publishable(lake):

    run = lake.start_run("https://bbc.com/test")

    written = lake.persist_all(run, make_news(), create_article(body=BODY), None)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["publishable"] is False
    assert exploitation["rejection_reasons"] == ["no_fact_check_report"]
    assert exploitation["verdict"] == "UNVERIFIED"


def test_only_cited_evidence_urls_reach_the_exploitation_layer(lake):

    cited = create_evidence(url="https://cited.example/one")
    ignored = create_evidence(url="https://ignored.example/two")

    report = make_report(
        claim_checks=[
            FactCheck(
                verdict=Verdict.TRUE,
                explanation="Confirmed.",
                confidence=0.9,
                claim="A claim.",
                evidence=[cited, ignored],
                cited_evidence_indices=[0],
                evidence_count=2,
            )
        ]
    )

    _, written = persist(lake, report=report)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["cited_evidence_urls"] == ["https://cited.example/one"]


def test_out_of_range_citation_indices_are_ignored(lake):
    """
    cited_evidence_indices comes from an LLM. A hallucinated index must
    not raise on the way into storage.
    """

    report = make_report(
        claim_checks=[
            FactCheck(
                verdict=Verdict.TRUE,
                explanation="Confirmed.",
                confidence=0.9,
                claim="A claim.",
                evidence=[create_evidence(url="https://only.example/one")],
                cited_evidence_indices=[0, 7, -1],
                evidence_count=1,
            )
        ]
    )

    _, written = persist(lake, report=report)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["cited_evidence_urls"] == ["https://only.example/one"]


def test_the_same_url_cited_by_two_claims_appears_once(lake):

    evidence = create_evidence(url="https://shared.example/one")

    check = FactCheck(
        verdict=Verdict.TRUE,
        explanation="Confirmed.",
        confidence=0.9,
        claim="A claim.",
        evidence=[evidence],
        cited_evidence_indices=[0],
        evidence_count=1,
    )

    _, written = persist(lake, report=make_report(claim_checks=[check, check]))

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["cited_evidence_urls"] == ["https://shared.example/one"]


def test_an_article_without_topics_has_no_primary_topic(lake):

    _, written = persist(lake, article=create_article(body=BODY, topics=None))

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["primary_topic"] is None
    assert exploitation["topics"] == []


def test_an_article_without_keywords_or_entities_stores_empty_collections(lake):

    article = create_article(body=BODY, keywords=None, entities={})

    _, written = persist(lake, article=article)

    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert exploitation["keywords"] == []
    assert exploitation["entities"] == {}


# ----------------------------------------------------------------------
# Traceability
# ----------------------------------------------------------------------


def test_trace_returns_the_full_chain_for_an_article(lake):

    run, written = persist(lake)

    trace = lake.trace(ARTICLE_ID)

    assert trace["articleId"] == ARTICLE_ID

    for layer in DataLayer:
        assert len(trace["layers"][layer.value]) == 1

    assert len(trace["manifest"]) == 3
    assert {entry["layer"] for entry in trace["manifest"]} == {
        "raw",
        "processed",
        "exploitation",
    }
    assert all(entry["run_id"] == run.run_id for entry in trace["manifest"])


def test_trace_of_an_unknown_article_is_empty_not_an_error(lake):

    persist(lake)

    trace = lake.trace("no-such-article")

    assert trace["manifest"] == []
    assert all(records == [] for records in trace["layers"].values())


def test_re_running_the_same_article_adds_a_second_traceable_version(lake):

    first_run, _ = persist(lake)
    second_run, _ = persist(lake)

    assert first_run.run_id != second_run.run_id

    trace = lake.trace(ARTICLE_ID)

    # One record per layer per run, and the audit log has both runs.
    assert len(trace["layers"]["exploitation"]) == 2
    assert len(trace["manifest"]) == 6
    assert {entry["run_id"] for entry in trace["manifest"]} == {
        first_run.run_id,
        second_run.run_id,
    }


def test_persisting_the_same_run_twice_is_idempotent(lake):
    """
    Record ids are derived from (layer, article, run), so a retried
    persist overwrites its own records rather than duplicating them.
    """

    run = lake.start_run("https://bbc.com/test")

    news, article, report = make_news(), create_article(body=BODY), make_report()

    first = lake.persist_all(run, news, article, report)
    second = lake.persist_all(run, news, article, report)

    assert first.raw_record_id == second.raw_record_id

    for layer in DataLayer:
        assert len(lake.list(layer)) == 1


def test_the_same_content_under_two_urls_shares_a_content_hash(lake):
    """
    content_hash is a content-level key, independent of URL - it is what
    makes cross-run and cross-source duplicate detection possible.
    """

    _, first = persist(lake, news=make_news(id="a", url="https://one.example"))
    _, second = persist(lake, news=make_news(id="b", url="https://two.example"))

    assert first.content_hash == second.content_hash


def test_lineage_records_the_pipeline_and_component_versions(lake):

    _, written = persist(lake)

    lineage = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)["lineage"]

    assert lineage["pipeline_version"] == "1"
    assert lineage["components"]["embedding_model"]
    assert lineage["components"]["llm_model"]


def test_list_limit_is_honoured_per_layer(lake):

    for index in range(3):
        persist(lake, news=make_news(id=f"article-{index}"))

    assert len(lake.list(DataLayer.EXPLOITATION)) == 3
    assert len(lake.list(DataLayer.EXPLOITATION, limit=2)) == 2


def test_get_returns_none_for_an_unknown_record(lake):

    assert lake.get(DataLayer.RAW, "missing") is None


def test_a_custom_backend_needs_no_pipeline_change(tmp_path):
    """
    The backend is an interface precisely so the lake can move to a real
    database later. A stand-in that only implements the protocol must
    work unchanged.
    """

    class MemoryBackend:

        def __init__(self):
            self.documents = {}
            self.entries = []

        def write(self, layer, record_id, document):
            self.documents[(layer, record_id)] = document
            self.entries.append({"layer": layer.value, **document["lineage"]})

        def read(self, layer, record_id):
            return self.documents.get((layer, record_id))

        def list(self, layer, limit=None):
            found = [d for (l, _), d in self.documents.items() if l == layer]
            return found[:limit] if limit else found

        def find_by_article(self, layer, article_id):
            return [
                d
                for d in self.list(layer)
                if d["lineage"]["article_id"] == article_id
            ]

        def manifest(self, limit=None):
            return self.entries[-limit:] if limit else self.entries

    backend = MemoryBackend()

    lake = DataLakeRepository(backend=backend)

    _, written = persist(lake)

    assert written.publishable is True
    assert len(backend.documents) == 3
    assert len(lake.trace(ARTICLE_ID)["layers"]["exploitation"]) == 1


# ----------------------------------------------------------------------
# Thresholds are part of the lineage
# ----------------------------------------------------------------------


def test_a_default_run_records_no_threshold_overrides(lake):

    _, written = persist(lake)

    lineage = lake.get(DataLayer.RAW, written.raw_record_id)["lineage"]

    assert lineage["threshold_overrides"] == {}


def test_a_tuned_run_records_exactly_what_was_changed(lake):
    """
    A record's numbers are only reproducible if you know the thresholds
    that produced them - the same article yields a different verdict
    under a different admission bar.
    """

    tuned = PipelineThresholds(positive_impact_min_score=0.85)

    run = lake.start_run("https://bbc.com/test", tuned)

    written = lake.persist_all(run, make_news(), create_article(body=BODY), make_report())

    for layer in DataLayer:

        lineage = lake.list(layer)[0]["lineage"]

        assert lineage["threshold_overrides"] == {"positive_impact_min_score": 0.85}


def test_start_run_without_thresholds_records_none(lake):

    assert lake.start_run("https://bbc.com/test").threshold_overrides == {}


def test_two_runs_with_different_thresholds_are_distinguishable_in_the_trace(lake):

    default_run = lake.start_run("https://bbc.com/test")
    lake.persist_all(default_run, make_news(), create_article(body=BODY), make_report())

    tuned_run = lake.start_run(
        "https://bbc.com/test",
        PipelineThresholds(max_claims_per_article=1),
    )
    lake.persist_all(tuned_run, make_news(), create_article(body=BODY), make_report())

    records = lake.trace(ARTICLE_ID)["layers"]["exploitation"]

    overrides = {
        record["lineage"]["run_id"]: record["lineage"]["threshold_overrides"]
        for record in records
    }

    assert overrides[default_run.run_id] == {}
    assert overrides[tuned_run.run_id] == {"max_claims_per_article": 1}


def test_an_integer_threshold_stays_an_integer_in_the_lineage(lake):
    """
    Typing threshold_overrides as plain float coerced count knobs to
    e.g. 2.0, changing an integer setting's type in the one record whose
    job is to say faithfully what the run used.
    """

    run = lake.start_run(
        "https://bbc.com/test",
        PipelineThresholds(max_claims_per_article=2),
    )

    written = lake.persist_all(
        run, make_news(), create_article(body=BODY), make_report()
    )

    stored = lake.get(DataLayer.RAW, written.raw_record_id)

    assert stored["lineage"]["threshold_overrides"] == {"max_claims_per_article": 2}
    assert isinstance(
        stored["lineage"]["threshold_overrides"]["max_claims_per_article"], int
    )

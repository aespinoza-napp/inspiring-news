import pytest
from datetime import datetime
from unittest.mock import Mock

from src.models.core.news import News
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.analysis_service import AnalysisService

from tests.factories import create_article, create_claim


def make_news(**kwargs) -> News:

    defaults = dict(
        source_id="web",
        url="https://example.com/a",
        title="A title",
        published_at=datetime(2024, 1, 1),
        content="Some article content.",
    )

    defaults.update(kwargs)

    return News(**defaults)


class FakeCache:
    """
    Keys on URL plus any non-default thresholds, mirroring the real
    AnalysisCache - a fake that ignored thresholds would hide a run
    being served another run's answer.
    """

    def __init__(self):
        self.store = {}

    @staticmethod
    def _key(url, thresholds):
        overridden = thresholds.overridden_from_defaults() if thresholds else {}
        return (url, tuple(sorted(overridden.items())))

    def get(self, url, thresholds=None):
        return self.store.get(self._key(url, thresholds))

    def set(self, url, result, thresholds=None):
        self.store[self._key(url, thresholds)] = result


def make_service(extract_return, article, report, cache=None) -> AnalysisService:

    extractor = Mock()
    extractor.extract.return_value = extract_return

    enrichment_pipeline = Mock()
    enrichment_pipeline.process.return_value = article

    fact_checker = Mock()
    fact_checker.run.return_value = report

    return AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment_pipeline,
        cache=cache if cache is not None else FakeCache(),
    )


def test_analyze_returns_error_when_extraction_fails():

    service = make_service(extract_return=None, article=None, report=None)

    result = service.analyze("https://example.com/a")

    assert result["url"] == "https://example.com/a"
    assert "error" in result


def test_analyze_returns_error_on_extractor_exception():

    extractor = Mock()
    extractor.extract.side_effect = RuntimeError("boom")

    service = AnalysisService(
        fact_checker=Mock(),
        extractor=extractor,
        enrichment_pipeline=Mock(),
        cache=FakeCache(),
    )

    result = service.analyze("https://example.com/a")

    assert "error" in result


def test_analyze_shapes_successful_result_with_sorted_claims():

    article = create_article(
        title="Test article",
        keywords=["mars", "water"],
        entities={"organization": ["NASA"]},
    )

    checks = [
        FactCheck(
            verdict=Verdict.TRUE,
            explanation="Confirmed.",
            confidence=0.9,
            claim="A true claim.",
            evidence_count=2,
        ),
        FactCheck(
            verdict=Verdict.FALSE,
            explanation="Contradicted.",
            confidence=0.8,
            claim="A false claim.",
            evidence_count=3,
        ),
    ]

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=2,
        claims_selected=2,
        claim_checks=checks,
        overall_verdict=Verdict.FALSE,
        overall_confidence=0.85,
    )

    service = make_service(make_news(), article, report)

    result = service.analyze("https://example.com/a")

    assert result["title"] == "Test article"
    assert result["keywords"] == ["mars", "water"]
    assert result["entities"] == {"organization": ["NASA"]}

    # worst verdict (FALSE) sorted first
    assert [c["verdict"] for c in result["claims"]] == [Verdict.FALSE, Verdict.TRUE]
    assert all(c["reachedStage"] == "aggregation" for c in result["claims"])

    assert result["validity"] == {
        "isValid": True,
        "isDuplicate": False,
        "hasTopic": True,
        "reasons": [],
        "impactScore": 0.0,
        "impactReasons": [],
        "failedStage": None,
    }

    assert result["sentiment"]["label"] == "neutral"
    assert result["sentiment"]["emotionalIntensity"] == 0.2
    assert result["quality"]["constructiveness"] == 0.8

    assert result["factCheck"]["overallVerdict"] == Verdict.FALSE
    assert result["factCheck"]["claimsChecked"] == 2


def test_analyze_exposes_evidence_with_cited_flag():

    from tests.factories import create_evidence

    article = create_article()

    cited_evidence = create_evidence(url="https://cited.com", relevance_score=0.9)
    other_evidence = create_evidence(url="https://ignored.com", relevance_score=0.4)

    checks = [
        FactCheck(
            verdict=Verdict.TRUE,
            explanation="Confirmed.",
            confidence=0.9,
            claim="A checked claim.",
            evidence=[cited_evidence, other_evidence],
            cited_evidence_indices=[0],
            evidence_count=2,
        ),
    ]

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=1,
        claims_selected=1,
        claim_checks=checks,
        overall_verdict=Verdict.TRUE,
        overall_confidence=0.9,
    )

    service = make_service(make_news(), article, report)

    result = service.analyze("https://example.com/a")

    evidence = result["claims"][0]["evidence"]
    assert [item["url"] for item in evidence] == ["https://cited.com", "https://ignored.com"]
    assert [item["cited"] for item in evidence] == [True, False]


def test_analyze_includes_claims_dropped_during_selection():

    from src.models.core.claim import RejectedClaim

    article = create_article()

    checks = [
        FactCheck(
            verdict=Verdict.TRUE,
            explanation="Confirmed.",
            confidence=0.9,
            claim="A checked claim.",
            evidence_count=1,
        ),
    ]

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=2,
        claims_selected=1,
        claim_checks=checks,
        unselected_claims=[
            RejectedClaim(text="A dropped claim.", confidence=0.4, reason="exceeds_max_claims_cap"),
        ],
        overall_verdict=Verdict.TRUE,
        overall_confidence=0.9,
    )

    service = make_service(make_news(), article, report)

    result = service.analyze("https://example.com/a")

    assert [c["text"] for c in result["claims"]] == ["A checked claim.", "A dropped claim."]

    dropped = result["claims"][1]
    assert dropped["verdict"] is None
    assert dropped["reachedStage"] == "claim_selection"
    assert dropped["stageNote"] == "exceeds_max_claims_cap"


def test_analyze_falls_back_to_raw_claims_when_validation_failed():

    claim = create_claim(text="Unchecked claim.", confidence=0.7)

    article = create_article(claims=[claim])

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=False,
        skipped_reason="topic_not_relevant",
        topic_ok=False,
        positive_ok=True,
        duplicate=False,
        claims_total=1,
        claims_selected=0,
        claim_checks=[],
    )

    service = make_service(make_news(), article, report)

    result = service.analyze("https://example.com/a")

    assert result["validity"]["isValid"] is False
    assert result["validity"]["hasTopic"] is False
    assert result["validity"]["reasons"] == ["topic_not_relevant"]

    assert result["claims"] == [
        {
            "text": "Unchecked claim.",
            "confidence": 0.7,
            "verdict": None,
            "explanation": None,
            "evidenceCount": 0,
            "evidence": [],
            "rejectedSources": [],
            "reachedStage": PipelineStage.ADMISSION_FILTER,
            "stageNote": "topic_not_relevant",
            "rawVerdict": None,
            "rawConfidence": None,
        }
    ]


def _successful_report(article) -> FactCheckReport:

    return FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=0,
        claims_selected=0,
    )


def test_analyze_returns_cached_result_without_running_pipeline():

    cache = FakeCache()
    cache.store[cache._key("https://example.com/a", None)] = {"url": "https://example.com/a", "title": "Cached"}

    extractor = Mock()
    enrichment_pipeline = Mock()
    fact_checker = Mock()

    service = AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment_pipeline,
        cache=cache,
    )

    result = service.analyze("https://example.com/a")

    assert result["title"] == "Cached"
    assert result["cached"] is True

    extractor.extract.assert_not_called()
    enrichment_pipeline.process.assert_not_called()
    fact_checker.run.assert_not_called()


def test_analyze_caches_successful_result_for_next_call():

    article = create_article()
    cache = FakeCache()

    service = make_service(make_news(), article, _successful_report(article), cache=cache)

    first = service.analyze("https://example.com/a")

    assert first["cached"] is False
    assert cache.get("https://example.com/a") is not None

    second = service.analyze("https://example.com/a")

    assert second["cached"] is True
    # Only the first call should have touched the pipeline.
    service.extractor.extract.assert_called_once()


def test_analyze_does_not_cache_errors():

    cache = FakeCache()

    service = make_service(extract_return=None, article=None, report=None, cache=cache)

    service.analyze("https://example.com/a")

    assert cache.get("https://example.com/a") is None


def test_analyze_force_refresh_bypasses_and_overwrites_cache():

    article = create_article()
    cache = FakeCache()
    cache.store[cache._key("https://example.com/a", None)] = {"url": "https://example.com/a", "title": "Stale"}

    service = make_service(make_news(), article, _successful_report(article), cache=cache)

    result = service.analyze("https://example.com/a", force_refresh=True)

    assert result["cached"] is False
    assert result["title"] != "Stale"
    service.extractor.extract.assert_called_once()

    assert cache.get("https://example.com/a")["title"] != "Stale"


def test_analyze_reports_phases_in_order():

    article = create_article(title="Phased article")
    report = _successful_report(article)

    fact_checker = Mock()

    def run_with_phases(article, on_phase=None, thresholds=None):
        if on_phase:
            on_phase("validating", {})
            on_phase("fact_check_done", {"overallVerdict": report.overall_verdict})
        return report

    fact_checker.run.side_effect = run_with_phases

    extractor = Mock()
    extractor.extract.return_value = make_news()

    enrichment_pipeline = Mock()
    enrichment_pipeline.process.return_value = article

    service = AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment_pipeline,
        cache=FakeCache(),
    )

    events = []

    service.analyze("https://example.com/a", on_phase=lambda phase, data: events.append(phase))

    assert events == [
        "scraping",
        "scraped",
        "enriching",
        "enriched",
        "validating",
        "fact_check_done",
        "done",
    ]


def test_analyze_reports_cache_hit_instead_of_pipeline_phases():

    cache = FakeCache()
    cache.store[cache._key("https://example.com/a", None)] = {"url": "https://example.com/a", "title": "Cached"}

    service = AnalysisService(
        fact_checker=Mock(),
        extractor=Mock(),
        enrichment_pipeline=Mock(),
        cache=cache,
    )

    events = []

    service.analyze("https://example.com/a", on_phase=lambda phase, data: events.append(phase))

    assert events == ["cache_hit"]


def test_analyze_reports_failed_phase_on_extraction_error():

    service = make_service(extract_return=None, article=None, report=None)

    events = []

    service.analyze("https://example.com/a", on_phase=lambda phase, data: events.append(phase))

    assert events == ["scraping", "failed"]


# ----------------------------------------------------------------------
# Persist stage (the three-layer lake)
# ----------------------------------------------------------------------


def _service_with_lake(lake, article=None, report=None):

    article = article if article is not None else create_article()

    return AnalysisService(
        fact_checker=_fact_checker_returning(
            report if report is not None else _successful_report(article)
        ),
        # Same id as the enriched article: the real NewsEnrichmentPipeline
        # carries News.id straight through, and the lake keys every layer
        # on that id, so a fake that invented a new one would silently
        # split one article's lineage across two chains.
        extractor=_extractor_returning(make_news(id=article.id)),
        enrichment_pipeline=_enrichment_returning(article),
        cache=FakeCache(),
        lake=lake,
    )


def _extractor_returning(news):

    extractor = Mock()
    extractor.extract.return_value = news
    return extractor


def _enrichment_returning(article):

    pipeline = Mock()
    pipeline.process.return_value = article
    return pipeline


def _fact_checker_returning(report):

    fact_checker = Mock()
    fact_checker.run.return_value = report
    return fact_checker


def test_analyze_without_a_lake_persists_nothing_and_reports_no_storage():

    article = create_article()

    service = make_service(make_news(), article, _successful_report(article))

    assert service.lake is None

    events = []

    result = service.analyze(
        "https://example.com/a",
        on_phase=lambda phase, data: events.append(phase),
    )

    assert result["storage"] is None
    assert "persisting" not in events


def test_analyze_persists_all_three_layers(tmp_path):

    from src.models.storage.lineage import DataLayer
    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    article = create_article()

    result = _service_with_lake(lake, article=article).analyze("https://example.com/a")

    assert result["storage"]["persisted"] is True
    assert result["storage"]["runId"]
    assert set(result["storage"]["records"]) == {
        "raw",
        "processed",
        "exploitation",
    }

    for layer in DataLayer:
        assert len(lake.list(layer)) == 1

    assert lake.trace(article.id)["layers"]["exploitation"]


def test_analyze_reports_the_persist_phases_after_the_fact_check(tmp_path):

    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    events = []
    detailed = []

    def record(phase, data):
        events.append(phase)
        detailed.append((phase, data))

    _service_with_lake(lake).analyze("https://example.com/a", on_phase=record)

    # One write per stage, as that stage completes: raw right after the
    # fetch, processed right after enrichment, then the verification
    # stage rewrites processed with the report and adds exploitation.
    assert events == [
        "scraping",
        "scraped",
        "storing",
        "stored_layer",
        "enriching",
        "enriched",
        "storing",
        "stored_layer",
        "storing",
        "stored_layer",
        "storing",
        "stored_layer",
        "stored",
        "done",
    ]

    layers = [
        data["layer"]
        for phase, data in detailed
        if phase == "stored_layer"
    ]

    assert layers == ["raw", "processed", "processed", "exploitation"]


def test_a_storage_failure_does_not_fail_the_analysis():
    """
    Persisting is a side effect of analysis. A full disk must not throw
    away a complete result that already cost a scrape, an enrichment and
    one LLM call per claim - it must degrade to a reported warning.
    """

    lake = Mock()
    lake.start_run.side_effect = OSError("disk full")

    events = []

    result = _service_with_lake(lake).analyze(
        "https://example.com/a",
        on_phase=lambda phase, data: events.append(phase),
    )

    assert result["storage"]["persisted"] is False

    # The analysis itself still completed and is still cacheable.
    assert result["title"] == "Test article"
    assert "error" not in result

    assert "store_failed" in events
    assert events[-1] == "done"


def test_a_cache_hit_does_not_re_persist(tmp_path):
    """
    A cached result short-circuits before the pipeline runs, so it must
    not write a second set of records describing a run that never
    happened. The cached payload keeps the original run's storage ids.
    """

    from src.models.storage.lineage import DataLayer
    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    service = _service_with_lake(lake)

    first = service.analyze("https://example.com/a")
    second = service.analyze("https://example.com/a")

    assert second["cached"] is True
    assert second["storage"]["runId"] == first["storage"]["runId"]

    assert len(lake.list(DataLayer.EXPLOITATION)) == 1


def test_an_article_that_failed_validation_is_still_persisted(tmp_path):
    """
    Rejections are data too: the raw fetch and the reason for the
    rejection have to be traceable, otherwise the only record of a
    dropped article is a log line.
    """

    from src.models.storage.lineage import DataLayer
    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    article = create_article()

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=False,
        skipped_reason="not_positive_impact",
        topic_ok=True,
        positive_ok=False,
        duplicate=False,
        claims_total=1,
        claims_selected=0,
    )

    result = _service_with_lake(lake, article=article, report=report).analyze(
        "https://example.com/a"
    )

    assert result["storage"]["publishable"] is False

    exploitation = lake.list(DataLayer.EXPLOITATION)[0]

    assert exploitation["publishable"] is False
    assert exploitation["rejection_reasons"] == ["not_positive_impact"]

    # ...and the raw fetch is still there to re-run from.
    assert lake.list(DataLayer.RAW)[0]["article"]["content"] == "Some article content."


def test_extraction_failure_persists_nothing():

    lake = Mock()

    service = AnalysisService(
        fact_checker=Mock(),
        extractor=_extractor_returning(None),
        enrichment_pipeline=Mock(),
        cache=FakeCache(),
        lake=lake,
    )

    service.analyze("https://example.com/a")

    lake.persist_all.assert_not_called()


# ----------------------------------------------------------------------
# Staged storage: each layer is written as its stage completes
# ----------------------------------------------------------------------


def _lake(tmp_path):

    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend

    return DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))


def test_raw_is_stored_even_when_enrichment_blows_up(tmp_path):
    """
    The point of writing per stage: a fetch that succeeded is not thrown
    away because a later stage failed. Before this, nothing was written
    until the very end, so a crash anywhere lost the scrape too.
    """

    from src.models.storage.lineage import DataLayer

    lake = _lake(tmp_path)

    enrichment = Mock()
    enrichment.process.side_effect = RuntimeError("model exploded")

    service = AnalysisService(
        fact_checker=Mock(),
        extractor=_extractor_returning(make_news()),  # never enriched, id irrelevant
        enrichment_pipeline=enrichment,
        cache=FakeCache(),
        lake=lake,
    )

    with pytest.raises(RuntimeError):
        service.analyze("https://example.com/a")

    assert len(lake.list(DataLayer.RAW)) == 1
    assert lake.list(DataLayer.RAW)[0]["article"]["content"] == "Some article content."

    # ...and nothing downstream was invented.
    assert lake.list(DataLayer.PROCESSED) == []
    assert lake.list(DataLayer.EXPLOITATION) == []


def test_enrichment_is_stored_even_when_fact_checking_blows_up(tmp_path):
    """
    Verification is the stage most likely to fail in practice - it needs
    a live SearXNG and a live LLM. The enrichment it depends on must
    survive that, since re-running it costs the whole NLP stack.
    """

    from src.models.storage.lineage import DataLayer

    lake = _lake(tmp_path)

    article = create_article()

    fact_checker = Mock()
    fact_checker.run.side_effect = RuntimeError("searxng is down")

    service = AnalysisService(
        fact_checker=fact_checker,
        extractor=_extractor_returning(make_news(id=article.id)),
        enrichment_pipeline=_enrichment_returning(article),
        cache=FakeCache(),
        lake=lake,
    )

    with pytest.raises(RuntimeError):
        service.analyze("https://example.com/a")

    assert len(lake.list(DataLayer.RAW)) == 1

    processed = lake.list(DataLayer.PROCESSED)

    assert len(processed) == 1
    assert processed[0]["article"]["id"] == article.id
    assert processed[0]["article"]["embedding_model"] == "bge-m3"

    # Not verified, so no serving document and no report yet.
    assert processed[0]["fact_check"] is None
    assert lake.list(DataLayer.EXPLOITATION) == []


def test_the_processed_record_gains_the_report_after_verification(tmp_path):

    from src.models.storage.lineage import DataLayer

    lake = _lake(tmp_path)

    article = create_article()

    _service_with_lake(lake, article=article).analyze("https://example.com/a")

    processed = lake.list(DataLayer.PROCESSED)

    # One record, not two: the post-verification write rewrites the same
    # document (record ids are uuid5(layer, article, run)).
    assert len(processed) == 1
    assert processed[0]["fact_check"] is not None
    assert processed[0]["fact_check"]["validation_passed"] is True


def test_the_manifest_shows_processed_written_twice(tmp_path):
    """
    The record shows current state; the append-only manifest shows how it
    got there - written after enrichment, updated after verification.
    """

    lake = _lake(tmp_path)

    article = create_article()

    _service_with_lake(lake, article=article).analyze("https://example.com/a")

    layers = [entry["layer"] for entry in lake.trace(article.id)["manifest"]]

    assert layers == ["raw", "processed", "processed", "exploitation"]


def test_a_failure_at_one_layer_does_not_stop_the_next(tmp_path):
    """
    Layers are independently writable - the raw write failing costs the
    parent link, not the enrichment record.
    """

    from src.models.storage.lineage import DataLayer

    lake = _lake(tmp_path)

    lake.persist_raw = Mock(side_effect=OSError("disk full"))

    article = create_article()

    result = _service_with_lake(lake, article=article).analyze("https://example.com/a")

    assert lake.list(DataLayer.RAW) == []

    processed = lake.list(DataLayer.PROCESSED)

    assert len(processed) == 1
    assert processed[0]["lineage"]["parent_record_id"] is None

    assert len(lake.list(DataLayer.EXPLOITATION)) == 1

    # Reported honestly: some of it did not land.
    assert result["storage"]["persisted"] is False
    assert result["storage"]["records"]["raw"] is None
    assert result["storage"]["records"]["exploitation"] is not None


def test_storage_reports_a_record_id_per_layer_on_a_clean_run(tmp_path):

    lake = _lake(tmp_path)

    result = _service_with_lake(lake).analyze("https://example.com/a")

    records = result["storage"]["records"]

    assert result["storage"]["persisted"] is True
    assert all(records[layer] for layer in ("raw", "processed", "exploitation"))

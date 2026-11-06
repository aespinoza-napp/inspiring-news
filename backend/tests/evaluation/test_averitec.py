"""
The benchmark's rows and numbers. A wrong mapping or a kinder denominator would
move every figure the thesis reports, and nothing else would notice.
"""

import json
import zipfile
from datetime import date

import pytest

from src.evaluation import averitec
from src.evaluation.dataset import AVERITEC, DatasetError, load_dataset, parse_row
from src.evaluation.knowledge_store import (
    ClaimIndex,
    KnowledgeStore,
    KnowledgeStoreProvider,
    KnowledgeStoreScraper,
    _pages_of,
    audit,
)
from src.evaluation.runner import context_for, store_indexes
from src.config.thresholds import PipelineThresholds

from tests.factories import create_claim


def _official(**extra):

    return {
        "claim": "A claim.",
        "label": averitec.REFUTED,
        "claim_date": "31-10-2020",
        "fact_checking_article": "https://web.archive.org/web/20201130144023/https://www.checker.example/a",
        "questions": [
            {"question": "q", "answers": [
                {"answer": "a", "source_url": "https://one.example/x"},
                {"answer": "b", "source_url": "https://one.example/x"},
                {"answer": "c", "source_url": "https://two.example/y"},
            ]},
        ],
        **extra,
    }


def test_an_official_claim_becomes_a_row():

    row = averitec.to_row(_official(), "dev", 7)

    assert row["id"] == "averitec-dev-0007"
    assert row["claimDate"] == "2020-10-31"
    assert row["label"] == "FALSE"
    assert row["labelRaw"] == averitec.REFUTED
    assert row["factCheckUrl"] == "https://www.checker.example/a"
    assert row["site"] == "checker.example"
    assert row["referenceEvidenceLinks"] == ["https://one.example/x", "https://two.example/y"]


@pytest.mark.parametrize("extra", [
    {"claim_date": None},
    {"claim_date": "not a date"},
    {"claim_date": "31-02-2020"},
    # A typo for 2019-2022, not a claim from 1919: its cutoff would refuse the web.
    {"claim_date": "01-01-1919"},
    {"label": "Pants on fire"},
    {"claim": ""},
])
def test_a_claim_that_cannot_be_run_soundly_is_left_out(extra):

    assert averitec.to_row(_official(**extra), "train", 0) is None


def test_the_import_is_hash_ordered_and_says_what_it_made(tmp_path):

    raw = tmp_path / "dev.json"
    raw.write_text(json.dumps([_official(claim=f"Claim {index}.") for index in range(30)] + [_official(claim_date=None)]))

    target = tmp_path / "rows.jsonl"

    provenance = averitec.import_split(raw, "dev", target)

    rows = [json.loads(line) for line in target.read_text().splitlines()]

    assert [row["id"] for row in rows] == sorted((row["id"] for row in rows), key=averitec.order_key)
    assert [row["id"] for row in rows] != sorted(row["id"] for row in rows)

    assert provenance["official"] == 31 and provenance["rows"] == 30
    assert [item["id"] for item in provenance["excluded"]] == ["averitec-dev-0030"]
    assert json.loads(target.with_suffix(".provenance.json").read_text())["rows"] == 30


def test_the_row_loads_as_averitec_and_refuses_to_run_without_a_date():

    row = parse_row(averitec.to_row(_official(), "dev", 7))

    assert row.dataset == AVERITEC
    assert row.split == "dev"
    assert row.fact_check_url == "https://www.checker.example/a"

    raw = averitec.to_row(_official(), "dev", 7)
    del raw["claimDate"]

    with pytest.raises(DatasetError, match="temporal cutoff"):
        parse_row(raw)


def test_the_pipeline_is_given_the_cutoff_and_nothing_of_the_gold_row():

    context = context_for(parse_row(averitec.to_row(_official(speaker="Someone"), "dev", 7)))

    assert context.evidence_before == date(2020, 10, 31)
    assert context.url == "https://www.checker.example/a"
    assert context.title == "" and context.lead == "" and context.keywords == [] and context.entities == {}


@pytest.mark.parametrize("verdict,expected", [
    ("TRUE", averitec.SUPPORTED),
    ("FALSE", averitec.REFUTED),
    ("UNVERIFIED", averitec.NOT_ENOUGH),
    ("MISLEADING", averitec.CONFLICTING),
    ("PARTIALLY_TRUE", averitec.CONFLICTING),
    (None, None),
])
def test_five_verdicts_score_as_four_classes(verdict, expected):

    assert averitec.predicted_class({"verdict": verdict}) == expected


def _record(index, gold, verdict, status="ok", **extra):

    return {
        "id": f"averitec-dev-{index:04d}",
        "dataset": "averitec",
        "claimDate": "2020-10-31",
        "labelRaw": gold,
        "label": averitec.TO_VERDICT[gold],
        "verdict": verdict,
        "status": status,
        "evidence": [],
        "candidates": [],
        **extra,
    }


def test_a_claim_with_no_verdict_counts_against_the_figure():

    records = [
        _record(0, averitec.REFUTED, "FALSE"),
        _record(1, averitec.REFUTED, None, status="error"),
        _record(2, averitec.SUPPORTED, "UNVERIFIED", searchUnavailable=True),
        _record(3, averitec.SUPPORTED, "TRUE"),
    ]

    result = averitec.evaluate(records, rows=4, resamples=50)

    assert result["all"]["accuracy"] == 0.5 and result["all"]["n"] == 4
    assert result["scored"]["accuracy"] == 1.0 and result["scored"]["n"] == 2
    assert result["complete"] is True


def test_macro_f1_is_over_all_four_classes_as_the_official_scorer_has_it():

    pairs = [(averitec.REFUTED, averitec.REFUTED), (averitec.SUPPORTED, averitec.REFUTED)]

    # Refuted: tp 1, fp 1, fn 0 -> 2/3. The other three are 0, not left out.
    assert averitec.macro_f1(pairs) == pytest.approx((2 / 3) / 4)


def test_the_trivial_answer_is_reported_beside_the_figure():

    records = [_record(index, averitec.REFUTED, "FALSE") for index in range(6)] + [
        _record(index + 6, averitec.SUPPORTED, "TRUE") for index in range(4)
    ]

    result = averitec.evaluate(records, rows=10, resamples=50)

    assert result["alwaysRefuted"]["accuracy"] == 0.6
    assert result["alwaysRefuted"]["macroF1"] == pytest.approx(0.75 / 4)


def test_the_audit_reads_the_records_not_the_gates_word():

    clean = _record(0, averitec.REFUTED, "FALSE", evidence=[
        {"url": "https://a.example/page", "publishedAt": "2020-10-30T00:00:00"},
        {"url": "https://b.example/page", "publishedAt": None},
    ], candidates=[
        {"url": "https://c.example", "reason": "published on or after the claim's date (temporal cutoff)"},
        {"url": "https://d.example", "reason": "no date to show it predates the claim (temporal cutoff)"},
    ])

    audit_result = averitec.temporal_audit([clean])

    assert audit_result["held"] is True
    assert audit_result["sources"] == 2 and audit_result["datedBeforeTheClaim"] == 1 and audit_result["undated"] == 1
    assert audit_result["refusedAsLate"] == 1 and audit_result["refusedAsUndated"] == 1

    late = _record(1, averitec.REFUTED, "FALSE", evidence=[
        {"url": "https://a.example/2020/10/31/same-day", "publishedAt": None},
    ])

    assert averitec.temporal_audit([late])["held"] is False

    own = _record(
        2, averitec.REFUTED, "FALSE",
        factCheckUrl="https://www.checker.example/a",
        evidence=[{"url": "https://checker.example/a/", "publishedAt": "2020-01-01"}],
    )

    assert averitec.temporal_audit([own])["factCheckInEvidence"]

    # The leak found live: the same fact-check at another address, undated.
    moved = _record(
        3, averitec.REFUTED, "FALSE",
        factCheckUrl="https://fit.thequint.com/a",
        evidence=[{"url": "https://www.thequint.com/b", "publishedAt": None}],
    )

    assert averitec.temporal_audit([moved])["held"] is False

    wikipedia = _record(4, averitec.REFUTED, "FALSE", evidence=[
        {"url": "https://en.wikipedia.org/wiki/Walmart", "publishedAt": "2001-09-12"},
    ])

    assert averitec.temporal_audit([wikipedia])["held"] is False


def test_a_broken_rule_is_the_first_thing_the_report_says():

    records = [_record(0, averitec.REFUTED, "FALSE", evidence=[
        {"url": "https://a.example/2021/01/01/late", "publishedAt": None},
    ])]

    text = "\n".join(averitec.render(averitec.evaluate(records, rows=1, resamples=20)))

    assert "BROKEN" in text


def test_a_partial_run_says_so():

    records = [_record(0, averitec.REFUTED, "FALSE")]

    text = "\n".join(averitec.render(averitec.evaluate(records, rows=500, resamples=20)))

    assert "Partial: 1 of 500" in text


def test_the_submission_is_in_the_official_shape():

    records = [
        _record(1, averitec.REFUTED, "PARTIALLY_TRUE", claim="B", evidence=[{"quote": "a passage", "title": "t"}]),
        _record(0, averitec.REFUTED, None, status="error", claim="A"),
    ]

    first, second = averitec.submission(records)

    assert first["claim"] == "A" and first["pred_label"] == averitec.NOT_ENOUGH
    assert second["pred_label"] == averitec.CONFLICTING and second["string_evidence"] == ["a passage"]


# ----------------------------------------------------------------------
# The knowledge store
# ----------------------------------------------------------------------


def _store(tmp_path, pages_by_claim):

    path = tmp_path / "store.zip"

    with zipfile.ZipFile(path, "w") as archive:
        for index, pages in pages_by_claim.items():
            archive.writestr(f"output_dev/{index}.json", "\n".join(json.dumps(page) for page in pages) + "\n")

    return KnowledgeStore(path)


def test_bm25_finds_the_page_about_the_query_and_the_order_is_repeatable():

    index = ClaimIndex(_pages_of([
        {"url": "https://a.example/1", "url2text": ["Bananas are yellow fruit.", "They grow in clusters."]},
        {"url": "https://b.example/2", "url2text": ["Sean Connery wrote a letter to Steve Jobs."]},
        {"url": "https://c.example/3", "url2text": ["Nothing here."]},
        {"url": "https://c.example/3", "url2text": ["The same address twice."]},
        {"url": "https://d.example/4", "url2text": []},
    ]))

    assert len(index.pages) == 3

    assert [page.url for page in index.search("connery letter", 5)] == ["https://b.example/2"]
    assert index.search("connery letter", 5) == index.search("connery letter", 5)
    assert index.search("no such words", 5) == []


def test_a_broken_line_loses_a_page_not_the_claim(tmp_path):

    path = tmp_path / "store.zip"

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("output_dev/3.json", '{"url": "https://a.example", "url2text": ["Fine."]}\n{"url": \n')

    assert [line["url"] for line in KnowledgeStore(path).raw_pages(3)] == ["https://a.example"]


def test_the_provider_searches_this_claims_pages_and_never_the_web(tmp_path):

    store = _store(tmp_path, {
        0: [{"url": "https://a.example/mars", "url2text": ["NASA found water on Mars in a crater."]}],
        1: [{"url": "https://b.example/other", "url2text": ["NASA and water and Mars, for another claim."]}],
    })

    provider = KnowledgeStoreProvider(store, {"NASA discovered water on Mars.": 0})

    claim = create_claim(text="NASA discovered water on Mars.", entities={"ORG": ["NASA"]})

    timings = []

    found = provider.search(claim, PipelineThresholds(), language="en", timings=timings)

    assert [item.url for item in found] == ["https://a.example/mars"]
    assert found[0].content and found[0].published_at is None
    assert {timing["via"] for timing in timings} == {"knowledge-store"}

    with pytest.raises(RuntimeError, match="live web"):
        provider.client.search("anything")

    with pytest.raises(ValueError):
        provider.search_queries([])

    with pytest.raises(KeyError):
        provider.search(create_claim(text="Not in the store."), PipelineThresholds())


def test_the_scraper_reads_nothing_new():

    timings = []

    assert KnowledgeStoreScraper().enrich([], timings=timings) == []


def test_store_indexes_come_from_the_official_position(tmp_path):

    target = tmp_path / "rows.jsonl"

    raw = tmp_path / "dev.json"
    raw.write_text(json.dumps([_official(claim=f"Claim {index}.") for index in range(12)] + [_official(claim="Claim 3.")]))

    averitec.import_split(raw, "dev", target)

    indexes = store_indexes(load_dataset(target))

    assert indexes["Claim 11."] == 11
    # A repeated claim: its first position stands for both.
    assert indexes["Claim 3."] == 3


def test_the_audit_finds_late_pages_and_the_fact_check(tmp_path):

    store = _store(tmp_path, {
        0: [
            {"url": "https://a.example/2020/11/03/late", "url2text": ["x"]},
            {"url": "https://a.example/2020/01/03/fine", "url2text": ["x"]},
            {"url": "https://a.example/undated", "url2text": ["x"]},
            {"url": "https://www.checker.example/a/", "url2text": ["x"]},
        ],
    })

    result = audit(store, [
        {"index": 0, "id": "averitec-dev-0000", "claimDate": "2020-10-31", "factCheckUrl": "https://checker.example/a"},
        {"index": 9, "id": "averitec-dev-0009", "claimDate": "2020-10-31", "factCheckUrl": None},
    ])

    assert result["pages"] == 4 and result["pagesWithADateInTheirAddress"] == 2
    assert result["lateCount"] == 1 and result["factCheckCount"] == 1
    assert result["claimsWithALatePage"] == 1 and result["lateShareOfDated"] == 0.5
    assert result["onTheClaimsFactCheckSite"] == 1
    assert result["missing"] == ["averitec-dev-0009"]


def test_the_audit_finds_a_later_date_in_a_sources_text():

    stated = _record(0, averitec.REFUTED, "FALSE", evidence=[
        {"url": "https://a.example/page", "publishedAt": None, "latestDateInText": "2022-01-18"},
    ])

    result = averitec.temporal_audit([stated])

    assert result["held"] is False
    assert result["lateInText"][0]["statedInText"] == "2022-01-18"
    assert result["undatedAnywhere"] == 0


def test_the_audit_counts_the_sources_with_no_date_anywhere():

    silent = _record(0, averitec.REFUTED, "FALSE", evidence=[
        {"url": "https://a.example/page", "publishedAt": None, "latestDateInText": None},
    ], candidates=[
        {"url": "https://b.example", "reason": "its text states a date on or after the claim's (temporal cutoff)"},
    ])

    result = averitec.temporal_audit([silent])

    assert result["held"] is True
    assert result["undatedAnywhere"] == 1
    assert result["refusedForTheirText"] == 1

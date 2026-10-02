import pytest

from src.models.core.source import NewsSource
from src.services.fact_checker.verification.llm_verification import (
    INVALID_OUTPUT_EXPLANATION,
)
from src.services.reader.views import (
    LLM_UNREACHABLE,
    NO_ANSWER,
    NO_EVIDENCE,
    NOT_CHECKED,
    SEARCH_UNAVAILABLE,
    UNGROUNDED,
    JUDGED,
    SourceNames,
    article_view,
    claim_outcome,
    claim_view,
    excerpt,
    headline,
    reader_id,
    verdict_summary,
)

SOURCE = {"url": "https://a.example/x", "title": "A source"}


# ----------------------------------------------------------------------
# How a claim's check ended
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "check, outcome",
    [
        ({"verdict": "TRUE", "raw_verdict": "TRUE", "evidence": [SOURCE]}, JUDGED),
        # The model looked at real evidence and could not decide: a real
        # UNVERIFIED, not a failure.
        ({"verdict": "UNVERIFIED", "raw_verdict": "UNVERIFIED", "evidence": [SOURCE]}, JUDGED),
        ({"verdict": "UNVERIFIED", "raw_verdict": "TRUE", "evidence": [SOURCE]}, UNGROUNDED),
        ({"verdict": "UNVERIFIED", "evidence": []}, NO_EVIDENCE),
        ({"verdict": "UNVERIFIED", "evidence": [], "search_unavailable": True}, SEARCH_UNAVAILABLE),
        (
            {"verdict": "UNVERIFIED", "evidence": [SOURCE], "llm_unreachable": True},
            LLM_UNREACHABLE,
        ),
        (
            {"verdict": "UNVERIFIED", "evidence": [SOURCE], "explanation": INVALID_OUTPUT_EXPLANATION},
            NO_ANSWER,
        ),
    ],
)
def test_each_way_a_check_can_end_is_told_apart(check, outcome):

    assert claim_outcome(check) == outcome


def test_a_failed_search_with_evidence_left_is_still_judged():
    """
    The internal corpus can answer when the web cannot. That verdict
    stands - flagged, not discarded.
    """

    check = {"verdict": "TRUE", "raw_verdict": "TRUE", "evidence": [SOURCE], "search_unavailable": True}

    assert claim_outcome(check) == JUDGED
    assert claim_view(0, check)["searchUnavailable"] is True


# ----------------------------------------------------------------------
# The verdict a reader weighs
# ----------------------------------------------------------------------


def processed_with(*checks) -> dict:

    return {"fact_check": {"claim_checks": list(checks)}}


def test_claims_we_failed_to_check_are_not_counted_as_verdicts():
    """
    An outage leaves UNVERIFIED in the record. Counting it among the
    verdicts would present our failure as a finding about the article.
    """

    summary = verdict_summary(
        {"verdict": "UNVERIFIED", "claims_total": 5},
        processed_with(
            {"verdict": "TRUE", "raw_verdict": "TRUE", "evidence": [SOURCE]},
            {"verdict": "UNVERIFIED", "evidence": [], "search_unavailable": True},
            {"verdict": "UNVERIFIED", "evidence": [SOURCE], "llm_unreachable": True},
            {"verdict": "UNVERIFIED", "evidence": []},
        ),
    )

    assert summary["counts"] == {"TRUE": 1, "UNVERIFIED": 1}
    assert summary["notJudged"] == 2
    assert summary["searchUnavailable"] == 1
    assert summary["llmUnreachable"] == 1
    assert summary["claimsChecked"] == 4
    assert summary["display"] == "UNVERIFIED"


def test_an_article_none_of_whose_claims_were_judged_is_not_shown_as_unverified():

    summary = verdict_summary(
        {"verdict": "UNVERIFIED"},
        processed_with({"verdict": "UNVERIFIED", "evidence": [SOURCE], "llm_unreachable": True}),
    )

    assert summary["display"] == NOT_CHECKED
    assert summary["overall"] == "UNVERIFIED"


def test_without_the_processed_record_the_overall_verdict_is_all_there_is():

    summary = verdict_summary({"verdict": "TRUE", "claims_checked": 3}, None)

    assert summary["display"] == "TRUE"
    assert summary["claimsChecked"] == 3
    assert summary["counts"] == {}


# ----------------------------------------------------------------------
# One claim and its sources
# ----------------------------------------------------------------------


def test_cited_sources_come_first_and_keep_their_own_citation():
    """
    Citations are resolved by index before anything is reordered: the
    index is what the model cited, and re-pointing it would credit the
    wrong page.
    """

    view = claim_view(0, {
        "verdict": "TRUE",
        "evidence": [
            {"url": "https://first.example", "relevance_score": 0.9},
            {"url": "https://second.example", "relevance_score": 0.8},
            {"url": "https://third.example", "relevance_score": 0.7},
        ],
        "cited_evidence_indices": [2],
    })

    assert [(source["url"], source["cited"]) for source in view["sources"]] == [
        ("https://third.example", True),
        ("https://first.example", False),
        ("https://second.example", False),
    ]


def test_a_source_record_from_before_the_newer_fields_still_renders():
    """
    The lake keeps records from every past pipeline version; the oldest
    have no pertinence, no lexical score and no reliability_known. An
    unknown rating is shown as unrated, never as a real 0.5.
    """

    view = claim_view(0, {
        "verdict": "UNVERIFIED",
        "explanation": "No evidence.",
        "evidence": [{"url": "https://old.example/a", "reliability_score": 0.5, "origin": "web"}],
    })

    source = view["sources"][0]

    assert source["reliabilityKnown"] is False
    assert source["scores"]["pertinence"] is None
    assert source["scores"]["lexical"] is None
    assert source["domain"] == "old.example"
    assert view["modelVerdict"] is None


def test_the_model_verdict_is_kept_when_the_guardrail_overrode_it():

    view = claim_view(0, {"verdict": "UNVERIFIED", "raw_verdict": "TRUE", "evidence": [SOURCE]})

    assert view["outcome"] == UNGROUNDED
    assert view["modelVerdict"] == "TRUE"


# ----------------------------------------------------------------------
# Text and identity
# ----------------------------------------------------------------------


def test_excerpts_end_on_a_word_and_say_they_were_cut():

    text = "word " * 100

    cut = excerpt(text, 42)

    assert cut.endswith("…")
    assert len(cut) <= 42
    assert "wor…" not in cut

    assert excerpt("Short lead.", 42) == "Short lead."


@pytest.mark.parametrize(
    "url, lead, expected",
    [
        (
            "https://inspiringnews.ai/ciencia/equal-earth-mapa-tom-patterson/",
            None,
            "Equal earth mapa tom patterson",
        ),
        ("https://site.example/2026/09/18/trees-return-to-the-valley.html", None, "Trees return to the valley"),
        # An opaque id is not a headline; the lead's first sentence is.
        ("https://www.bbc.com/news/articles/c0k4x2y3z", "The valley is green again. More text.", "The valley is green again."),
        ("https://www.bbc.com/news/articles/c0k4x2y3z", None, "bbc.com"),
    ],
)
def test_a_missing_title_falls_back_to_something_readable(url, lead, expected):

    assert headline("", url, lead) == expected


def test_a_real_title_always_wins():

    assert headline("  Trees  return ", "https://a.example/other-words-entirely-here", None) == "Trees return"


def test_the_reader_id_survives_a_tracking_parameter_and_a_trailing_slash():
    """
    The lake's article_id is minted per extraction; a reader link must not
    break each time the article is re-analysed.
    """

    assert reader_id("https://www.a.example/story/") == reader_id("https://a.example/story?utm_source=x")
    assert reader_id("https://a.example/story") != reader_id("https://a.example/other")


def test_sources_are_named_by_id_then_by_domain_then_shown_as_the_domain():

    names = SourceNames([
        NewsSource(id="bbc", name="BBC News", base_url="https://www.bbc.co.uk"),
    ])

    assert names.describe("bbc", "https://www.bbc.co.uk/news/x")["name"] == "BBC News"
    # Posted by hand: no source id, but a configured domain.
    assert names.describe("web", "https://www.bbc.co.uk/news/x")["name"] == "BBC News"
    assert names.describe("web", "https://news.bbc.co.uk/x")["name"] == "BBC News"
    assert names.describe("web", "https://unknown.example/x")["name"] == "unknown.example"


# ----------------------------------------------------------------------
# The article view
# ----------------------------------------------------------------------


def test_the_article_view_never_carries_a_scraped_page_or_the_article_body():

    exploitation = {
        "url": "https://a.example/story-about-the-valley-trees",
        "summary": "Lead. " * 200,
        "verdict": "TRUE",
        "lineage": {"produced_at": "2026-09-01T10:00:00", "components": {"llm_model": "llama3.1"}},
    }

    processed = {
        "article": {"body": "THE WHOLE BODY"},
        "fact_check": {
            "claim_checks": [{
                "verdict": "TRUE",
                "evidence": [{"url": "https://b.example", "content": "SCRAPED PAGE"}],
                "cited_evidence_indices": [0],
            }],
        },
    }

    raw = {"article": {"content": "THE WHOLE BODY", "author": "A. Reporter"}}

    view = article_view(exploitation, processed, raw, SourceNames())

    text = repr(view)

    assert "SCRAPED PAGE" not in text
    assert "THE WHOLE BODY" not in text
    assert view["author"] == "A. Reporter"
    assert view["checkedWith"]["model"] == "llama3.1"
    assert len(view["summary"]) <= 500


def test_an_article_whose_processed_record_is_gone_says_so():

    view = article_view({"url": "https://a.example/x", "verdict": "TRUE"}, None, None, SourceNames())

    assert view["claimsAvailable"] is False
    assert view["claims"] == []

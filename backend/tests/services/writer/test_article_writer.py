"""
The writer (src/services/writer/article_writer.py) and the material it is
given (draft_writer.build_sources / build_fact_checks): the order of the
sources, what each verdict lets the model say, the prompt's size, and
what is done with the model's answer.
"""

import pytest

from src.config.thresholds import WriterThresholds
from src.models.writer.draft import DraftFactCheck, DraftSource
from src.services.llms import LLMUnavailableError
from src.services.writer.analysed_article import AnalysedArticle, CheckedClaim, from_view
from src.services.writer.article_writer import (
    MIN_ANALYSED_EXCERPT,
    SYSTEM_PROMPT,
    ArticleWriter,
    WriterError,
    user_prompt,
)
from src.services.writer.draft_writer import build_fact_checks, build_sources, window
from src.services.writer.related_news import RatedDomains

from tests.services.fact_checker.fakes import FakeLLMClient
from tests.services.writer.writer_fakes import answer

BODY = "Volunteers in the valley planted forty thousand native trees this spring. " * 20


def source_view(url: str, cited: bool = True, **extra) -> dict:

    view = {
        "url": url,
        "title": f"Page at {url}",
        "domain": url.split("/")[2],
        "publishedAt": "2026-09-02T00:00:00",
        "snippet": "A snippet.",
        "quote": "forty thousand trees",
        "cited": cited,
        "reliabilityKnown": True,
    }

    view.update(extra)

    return view


def article(**changes) -> AnalysedArticle:

    base = AnalysedArticle(
        id="0123456789abcdef",
        url="https://www.bbc.com/news/valley-trees",
        headline="Volunteers plant 40,000 trees",
        lead="Volunteers planted forty thousand native trees.",
        language="en",
        topic="Environment",
        published_at="2026-09-01T08:00:00",
        source_name="BBC News",
        domain="bbc.com",
        claims=(
            CheckedClaim(
                text="Volunteers planted 40,000 trees.",
                verdict="TRUE",
                confidence=0.82,
                sources=(source_view("https://rated.example/planting"), source_view("https://x.example/u", cited=False)),
            ),
            CheckedClaim(
                text="The wetland is now the largest in Europe.",
                verdict="FALSE",
                confidence=0.77,
                sources=(source_view("https://atlas.example/wetlands"),),
            ),
        ),
        body=BODY,
        pages={"https://rated.example/planting": "Intro. " * 50 + "They planted forty thousand trees in the valley. " + "More. " * 50},
    )

    return base.__class__(**{**base.__dict__, **changes})


def related() -> list[DraftSource]:

    return [
        DraftSource(url="https://other.example/valley", title="Schools join", domain="other.example", origin="related", excerpt="Schools joined the replanting."),
    ]


# ----------------------------------------------------------------------
# The material
# ----------------------------------------------------------------------


def test_the_analysed_article_is_source_one_then_related_then_evidence():

    sources = build_sources(article(), related(), WriterThresholds(), RatedDomains({"bbc.com"}))

    assert [(source.origin, source.url) for source in sources] == [
        ("analysed", "https://www.bbc.com/news/valley-trees"),
        ("related", "https://other.example/valley"),
        ("evidence", "https://rated.example/planting"),
        ("evidence", "https://atlas.example/wetlands"),
    ]
    assert sources[0].reliability_known


def test_only_cited_evidence_is_given_and_each_url_once():

    duplicate = DraftSource(url="https://rated.example/planting", title="Same page", domain="rated.example", origin="related", excerpt="x")

    sources = build_sources(article(), [duplicate], WriterThresholds())

    urls = [source.url for source in sources]

    assert "https://x.example/u" not in urls
    assert urls.count("https://rated.example/planting") == 1


def test_evidence_is_taken_one_claim_at_a_time_up_to_the_cap():

    many = article(claims=(
        CheckedClaim("A", "TRUE", 0.8, sources=(source_view("https://a.example/1"), source_view("https://a.example/2"))),
        CheckedClaim("B", "TRUE", 0.8, sources=(source_view("https://b.example/1"),)),
    ))

    sources = build_sources(many, [], WriterThresholds(evidence_max_sources=2))

    assert [source.url for source in sources[1:]] == ["https://a.example/1", "https://b.example/1"]


def test_the_analysed_excerpt_is_bounded_and_falls_back_to_the_lead():

    sources = build_sources(article(), [], WriterThresholds(analysed_excerpt_chars=500))

    assert len(sources[0].excerpt) <= 501

    no_body = build_sources(article(body=None), [], WriterThresholds())

    assert no_body[0].excerpt == "Volunteers planted forty thousand native trees."


def test_an_evidence_excerpt_is_the_passage_the_verdict_was_judged_on():

    text = "Intro. " * 50 + "They planted forty thousand trees in the valley. " + "More. " * 50

    passage = window(text, "forty thousand trees", 200)

    assert "forty thousand trees" in passage
    assert passage.startswith("…")
    assert len(passage) <= 202


def test_fact_checks_carry_the_verdict_and_the_cited_sources():

    fact_checks = build_fact_checks(article())

    assert [(check.verdict, check.source_urls) for check in fact_checks] == [
        ("TRUE", ["https://rated.example/planting"]),
        ("FALSE", ["https://atlas.example/wetlands"]),
    ]


def test_a_claim_our_search_failed_on_is_not_checked_not_unverified():

    view = {
        "url": "https://www.bbc.com/news/valley-trees",
        "headline": "Trees",
        "claims": [
            {"text": "Search failed here.", "verdict": "UNVERIFIED", "outcome": "search_unavailable", "sources": []},
            {"text": "Looked for, not found.", "verdict": "UNVERIFIED", "outcome": "no_evidence", "sources": []},
        ],
    }

    assert [claim.verdict for claim in from_view(view).claims] == ["NOT_CHECKED", "UNVERIFIED"]


# ----------------------------------------------------------------------
# The prompt
# ----------------------------------------------------------------------


def prompt_for(language="ca", instructions="Short, for young readers.", notes=()) -> str:

    a = article()
    sources = build_sources(a, related(), WriterThresholds())

    return user_prompt(a, sources, build_fact_checks(a), language, instructions, list(notes))


def test_a_false_claim_reaches_the_prompt_as_false_and_not_to_be_stated():

    prompt = prompt_for()

    line = next(line for line in prompt.splitlines() if "largest in Europe" in line)

    assert "verdict FALSE" in line
    assert "never state it as fact" in line
    # Its source, by the number the body would cite.
    assert "[4]" in line


def test_the_prompt_names_the_language_carries_the_instructions_and_numbers_every_source():

    prompt = prompt_for(language="ca", notes=["Web search answered, but found nothing on this story."])

    assert "LANGUAGE: Catalan (català)" in prompt
    assert "Short, for young readers." in prompt
    assert "found nothing on this story" in prompt
    assert '[1] the analysed article - "Volunteers plant 40,000 trees" - bbc.com - 2026-09-01' in prompt
    assert "[2] related news" in prompt
    assert "[3] evidence behind a fact-check" in prompt


def test_the_rules_are_closed_world():

    assert "Use only the numbered SOURCES and the FACT-CHECKS" in SYSTEM_PROMPT
    assert "never copy its sentences" in SYSTEM_PROMPT
    assert '"## "' in SYSTEM_PROMPT and "**bold**" in SYSTEM_PROMPT


def test_without_instructions_the_writer_gets_a_default():

    assert "(none given" in prompt_for(instructions="   ")


def test_the_prompt_is_cut_to_its_budget_keeping_the_analysed_article():

    a = article(body="Long body sentence about the valley. " * 2000)
    sources = build_sources(a, related() * 1, WriterThresholds(analysed_excerpt_chars=20000))
    fact_checks = build_fact_checks(a)

    writer = ArticleWriter(FakeLLMClient(answer()))

    fitted = writer.fit(a, sources, fact_checks, "en", "", [], WriterThresholds(prompt_max_chars=12000))

    size = len(SYSTEM_PROMPT) + len(user_prompt(a, fitted, fact_checks, "en", "", []))

    assert size <= 12000
    assert fitted[0].origin == "analysed"
    assert len(fitted[0].excerpt) >= MIN_ANALYSED_EXCERPT


def test_a_prompt_within_budget_is_left_alone():

    a = article()
    sources = build_sources(a, related(), WriterThresholds())

    fitted = ArticleWriter(FakeLLMClient(answer())).fit(a, sources, build_fact_checks(a), "en", "", [], WriterThresholds())

    assert fitted == sources


# ----------------------------------------------------------------------
# The answer
# ----------------------------------------------------------------------


def write(response, sources_count=3, **thresholds):

    a = article()
    sources = build_sources(a, related(), WriterThresholds())[:sources_count]
    llm = FakeLLMClient(response)
    llm.model = "test-writer:7b"

    written = ArticleWriter(llm).write(a, sources, build_fact_checks(a), "ca", "", [], WriterThresholds(**thresholds))

    return written, llm


def test_citations_stay_in_range():

    written, _ = write(answer(body="Van plantar arbres [1]. Les escoles s'hi van sumar [2, 7]. Res més [12]."))

    assert written.content.body == "Van plantar arbres [1]. Les escoles s'hi van sumar [2]. Res més."
    assert any("past the 3 sources" in finding for finding in written.findings)


def test_the_answer_cap_is_sent_to_the_model():

    _, llm = write(answer(), max_output_tokens=2048)

    assert llm.max_tokens == [2048]


def test_metadata_is_cleaned_and_the_topic_is_the_pipelines():

    written, _ = write(answer())

    assert written.content.title == "Un bosc torna a la vall"
    assert written.metadata.slug == "un-bosc-torna-a-la-vall"
    assert written.metadata.keywords == ["arbres", "voluntaris"]
    assert written.metadata.topic == "Environment"
    assert written.model == "test-writer:7b"


def test_a_title_or_body_left_empty_is_an_error():

    with pytest.raises(WriterError, match="no title"):
        write(answer(title="  "))

    with pytest.raises(WriterError, match="no body"):
        write(answer(body="```\nnothing\n```"))


def test_no_json_is_an_error_that_says_why():

    with pytest.raises(WriterError, match="not with the JSON"):
        write(None)


def test_an_unreachable_model_is_an_error_that_names_it():

    with pytest.raises(WriterError, match="could not be reached"):
        write(LLMUnavailableError("connection refused"))


def test_a_body_sent_as_paragraphs_is_joined():

    written, _ = write(answer(body=["Primer paràgraf [1].", "Segon paràgraf [2]."]))

    assert written.content.body == "Primer paràgraf [1].\n\nSegon paràgraf [2]."


def test_a_fact_check_with_an_unknown_verdict_is_treated_as_unverified():

    a = article()

    prompt = user_prompt(a, build_sources(a, [], WriterThresholds()), [DraftFactCheck(claim="X happened.", verdict="WEIRD")], "en", "", [])

    assert "could NOT be verified" in next(line for line in prompt.splitlines() if "X happened." in line)

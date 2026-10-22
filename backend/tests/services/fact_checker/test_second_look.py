"""
The second look: when it fires, what it searches for, which pages it
adds, and what it leaves on the verdict. Real ranker, verifier and
scorer over the shared fakes; the model is a FakeLLMClient answering
the planner first and the verifier second.
"""

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, SecondLook, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.second_look import (
    LOW_CONFIDENCE,
    UNVERIFIED,
    FollowUpPlanner,
    doubt,
    needs_second_look,
)
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerifier

from tests.factories import create_claim
from tests.services.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEvidenceScraper,
    FakeLLMClient,
    FakeSearchProvider,
    FakeSourceRepository,
    FakeVectorRetriever,
)

# Written against the list verifier, one call for every source (conftest.py).
pytestmark = pytest.mark.usefixtures("list_verifier")


def page(url: str, title: str = "A report") -> Evidence:

    from src.services.fact_checker.retrieval.search_provider import registrable_domain

    return Evidence(
        url=url,
        title=title,
        snippet="The agency's 2025 report gives the figure.",
        origin=EvidenceOrigin.WEB,
        domain=registrable_domain(url),
    )


def thresholds(**overrides) -> PipelineThresholds:
    # Nothing cut by the pertinence gate: the fake embeddings are hashes.
    return PipelineThresholds(evidence_min_pertinence=0.0, **overrides)


def checker(llm: FakeLLMClient, *, first=None, follow_up=None, unavailable=False):

    embeddings = FakeEmbeddingService()
    provider = FakeSearchProvider(first or [], unavailable=unavailable, follow_up=follow_up or [])
    scraper = FakeEvidenceScraper()

    fact_checker = FactChecker(
        repository=None,
        evidence_retriever=EvidenceRetriever(
            repository=None,
            search_provider=provider,
            scraper=scraper,
            vector_retriever=FakeVectorRetriever([]),
            embeddings=embeddings,
        ),
        ranker=EvidenceRanker(embeddings=embeddings, source_repository=FakeSourceRepository()),
        verifier=LLMVerifier(client=llm),
        confidence_scorer=ConfidenceScorer(),
    )

    return fact_checker, provider, scraper


def verdict(value: str, cited=(0,), confidence=0.8) -> dict:

    return {
        "verdict": value,
        "confidence": confidence,
        "explanation": f"The sources say {value}.",
        "cited_evidence": list(cited),
        "assessments": [{"index": i, "stance": "supports"} for i in cited],
    }


def check(verdict_=Verdict.TRUE, confidence=0.9, **extra) -> FactCheck:

    return FactCheck(verdict=verdict_, explanation="", confidence=confidence, **extra)


# ----------------------------------------------------------------------
# When it fires
# ----------------------------------------------------------------------


def test_doubt_is_an_unverified_or_unsure_verdict_never_an_outage():

    assert doubt(check(Verdict.UNVERIFIED, 0.0), 0.5) == UNVERIFIED
    assert doubt(check(Verdict.TRUE, 0.4), 0.5) == LOW_CONFIDENCE
    assert doubt(check(Verdict.TRUE, 0.9), 0.5) is None

    # A second search would meet the same outage.
    assert doubt(check(Verdict.UNVERIFIED, 0.0, search_unavailable=True), 0.5) is None
    assert doubt(check(Verdict.UNVERIFIED, 0.0, llm_unreachable=True), 0.5) is None

    # Never a third look.
    looked = SecondLook(trigger=UNVERIFIED, first_verdict=Verdict.UNVERIFIED, first_confidence=0.0)
    assert doubt(check(Verdict.UNVERIFIED, 0.0, second_look=looked), 0.5) is None


def test_the_pipeline_takes_one_only_when_the_run_enables_it():

    unsure = check(Verdict.UNVERIFIED, 0.0)

    assert needs_second_look(unsure, thresholds()) is None
    assert needs_second_look(unsure, thresholds(second_look_enabled=True)) == UNVERIFIED


def test_a_disabled_run_asks_the_model_nothing_more():

    llm = FakeLLMClient([])
    fact_checker, provider, _ = checker(llm, follow_up=[page("https://www.ine.es/informe")])

    result = fact_checker.check_claim(create_claim(), thresholds=thresholds())

    assert result.verdict == Verdict.UNVERIFIED
    assert result.second_look is None
    assert llm.calls == []
    assert provider.follow_up_queries == []


# ----------------------------------------------------------------------
# What it does
# ----------------------------------------------------------------------


def test_an_unverified_claim_is_searched_again_and_judged_on_the_new_page():

    llm = FakeLLMClient([
        {"queries": ["NASA water Mars 2024 announcement", "\"agua Marte NASA\" 2024", "x"]},
        verdict("TRUE"),
    ])
    fact_checker, provider, _ = checker(llm, follow_up=[page("https://www.nasa.gov/news/mars-water")])
    events = []

    result = fact_checker.check_claim(
        create_claim(),
        lambda phase, data: events.append((phase, data)),
        thresholds(second_look_enabled=True),
    )

    assert result.verdict == Verdict.TRUE
    assert [item.url for item in result.evidence] == ["https://www.nasa.gov/news/mars-water"]
    assert result.evidence[0].found_by == ["follow_up"]

    trace = result.second_look
    assert (trace.trigger, trace.first_verdict, trace.new_evidence) == (UNVERIFIED, Verdict.UNVERIFIED, 1)
    # Quotes stripped, a one-word query dropped.
    assert trace.queries == ["NASA water Mars 2024 announcement", "agua Marte NASA 2024"]
    assert provider.follow_up_queries == [trace.queries]

    # The planner was told what the first check concluded.
    assert "First check: UNVERIFIED" in llm.calls[0][1]

    phases = [phase for phase, _ in events]
    assert phases.index("second_look") < phases.index("second_look_checked") < phases.index("claim_checked")
    assert phases.count("claim_checked") == 1
    assert events[-1][1]["verdict"] == Verdict.TRUE


def test_only_pages_and_domains_the_first_pass_did_not_have_are_added():

    first = check(
        Verdict.TRUE, 0.3,
        evidence=[page("https://www.ine.es/a")],
        rejected_sources=[RejectedEvidence(
            url="https://elpais.com/seen", title="", origin=EvidenceOrigin.WEB,
            stage=PipelineStage.EVIDENCE_RETRIEVAL, reason="cut",
        )],
    )
    llm = FakeLLMClient([{"queries": ["ine informe 2025 pobreza"]}, verdict("TRUE", cited=(0, 1))])
    fact_checker, _, scraper = checker(llm, follow_up=[
        page("https://www.ine.es/b"),              # a domain it had
        page("https://elpais.com/seen/"),          # a page it saw
        page("https://www.diario.es/articulo"),    # the article itself
        page("https://www.eurostat.eu/table"),     # new
        page("https://eurostat.eu/other"),         # new page, a domain just added
    ])

    result = fact_checker.second_look(
        create_claim(),
        first,
        thresholds=thresholds(),
        context=ArticleContext(url="https://diario.es/articulo", title="", lead="", keywords=[], entities={}),
    )

    assert [item.url for item in scraper.enrich_calls[0]] == ["https://www.eurostat.eu/table"]
    assert {item.url for item in result.evidence} == {"https://www.ine.es/a", "https://www.eurostat.eu/table"}
    assert result.second_look.trigger == "requested"
    assert result.second_look.new_evidence == 1


def test_a_model_that_writes_no_query_still_gets_a_second_search():

    claim = create_claim(text="La planta desaladora abastece a 300.000 personas desde marzo de 2026 en Almería.")
    planner = FollowUpPlanner(FakeLLMClient("not an object"))

    queries = planner.plan(claim, check(Verdict.UNVERIFIED, 0.0), language="es")

    assert queries == ["La planta desaladora abastece a 300.000 personas desde marzo de 2026 en Almería."]
    assert "Language for the queries: Spanish" in planner.client.calls[0][1]


def test_a_failed_follow_up_search_is_recorded_not_raised():

    llm = FakeLLMClient([{"queries": ["NASA Mars water"]}])
    fact_checker, _, _ = checker(llm, unavailable=True)

    result = fact_checker.second_look(create_claim(), check(Verdict.UNVERIFIED, 0.0), thresholds=thresholds())

    assert result.verdict == Verdict.UNVERIFIED
    assert result.second_look.search_unavailable is True


# ----------------------------------------------------------------------
# Against given pages
# ----------------------------------------------------------------------


def test_a_claim_is_judged_against_the_pages_it_is_given_with_no_search():

    llm = FakeLLMClient([verdict("FALSE", cited=(0, 1))])
    fact_checker, provider, scraper = checker(llm)

    result, read = fact_checker.check_against(
        create_claim(),
        ["https://www.nasa.gov/a", "https://www.esa.int/b", "https://www.nasa.gov/a"],
        thresholds=PipelineThresholds(),
    )

    assert read == 2
    assert result.verdict == Verdict.FALSE
    # The annotator chose them: no pertinence gate, whatever the default.
    assert [item.url for item in result.evidence] == ["https://www.nasa.gov/a", "https://www.esa.int/b"]
    assert provider.calls == [] and provider.follow_up_queries == []
    assert [item.url for item in scraper.enrich_calls[0]] == ["https://www.nasa.gov/a", "https://www.esa.int/b"]

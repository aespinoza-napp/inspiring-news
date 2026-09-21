from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

from tests.factories import create_article, create_claim, create_evidence
from tests.services.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEvidenceRetriever,
    FakeRanker,
    FakeVerifier,
)


def test_run_short_circuits_when_validation_fails(repository):

    article = create_article(topics=[])  # fails topic validation

    checker = FactChecker(repository)

    report = checker.run(article)

    assert report.validation_passed is False
    assert "topic_not_relevant" in report.skipped_reason
    assert report.claims_selected == 0
    assert report.claim_checks == []
    assert report.failed_stage == "admission_filter"


def test_run_persists_article_so_a_later_duplicate_is_detected(repository):
    """
    Nothing else in the app ever calls VectorRepository.save() - confirmed
    by grepping src/ for ".save(" - so without FactChecker.run() persisting
    a successfully-checked article itself, DuplicateValidator and
    VectorRetriever (internal-corpus evidence) permanently query an empty
    collection: re-analyzing the exact same article twice never gets
    flagged as a duplicate, no matter how many times it's run.
    """

    checker = FactChecker(
        repository,
        evidence_retriever=FakeEvidenceRetriever({}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    first = create_article(id="11111111-1111-1111-1111-111111111111", claims=[])
    report_one = checker.run(first)

    assert report_one.validation_passed is True
    assert report_one.duplicate is False
    assert repository.count() == 1

    # Same embedding (the factory default), different id *and* a different
    # URL - the same story from another outlet. (The same URL again is a
    # re-analysis, which is covered by the test below.)
    second = create_article(
        id="22222222-2222-2222-2222-222222222222",
        url="https://example.com/another-outlet",
        claims=[],
    )
    report_two = checker.run(second)

    assert report_two.validation_passed is False
    assert report_two.duplicate is True
    # A rejected duplicate must not also get persisted a second time.
    assert repository.count() == 1


def test_reanalysing_the_same_url_is_accepted_and_replaces_the_stored_copy(repository):
    """
    Regression: extraction mints a new id every time, so re-running a URL
    (force_refresh, or a changed threshold that changes the cache key) hit
    its own stored copy at similarity 1.0 and was rejected as a duplicate
    of itself. It must pass, and the collection must keep one point per
    URL rather than growing a copy per run.
    """

    checker = FactChecker(
        repository,
        evidence_retriever=FakeEvidenceRetriever({}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    checker.run(create_article(id="11111111-1111-1111-1111-111111111111", claims=[]))

    rerun = create_article(id="22222222-2222-2222-2222-222222222222", claims=[])
    report = checker.run(rerun)

    assert report.validation_passed is True
    assert report.duplicate is False
    assert repository.count() == 1
    assert repository.exists("22222222-2222-2222-2222-222222222222")
    assert not repository.exists("11111111-1111-1111-1111-111111111111")


def test_run_produces_worst_case_wins_overall_verdict(repository):

    claim_false = create_claim(text="Claim that turns out false.", confidence=0.9)
    claim_true = create_claim(text="Claim that turns out true.", confidence=0.8)

    article = create_article(claims=[claim_false, claim_true])

    embeddings = FakeEmbeddingService(vectors={
        claim_false.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        claim_true.text: [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    evidence_false = [create_evidence(url="https://a.com", relevance_score=0.9)]
    evidence_true = [create_evidence(url="https://b.com", relevance_score=0.9)]

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({
            claim_false.text: evidence_false,
            claim_true.text: evidence_true,
        }),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim_false.text: LLMVerificationResult(
                verdict=Verdict.FALSE,
                confidence=0.9,
                explanation="Contradicted by evidence.",
                cited_evidence=[0],
            ),
            claim_true.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed by evidence.",
                cited_evidence=[0],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(article)

    assert report.validation_passed is True
    assert report.claims_total == 2
    assert report.claims_selected == 2
    assert len(report.claim_checks) == 2

    verdicts = {check.claim: check.verdict for check in report.claim_checks}
    assert verdicts[claim_false.text] == Verdict.FALSE
    assert verdicts[claim_true.text] == Verdict.TRUE

    # One false claim should dominate the article-level verdict.
    assert report.overall_verdict == Verdict.FALSE
    assert 0.0 < report.overall_confidence <= 1.0


def test_run_tracks_reached_stage_for_each_claim(repository):

    claim_ok = create_claim(text="A claim with cited evidence.", confidence=0.9)
    claim_no_evidence = create_claim(text="A claim with no evidence.", confidence=0.8)

    article = create_article(claims=[claim_ok, claim_no_evidence])

    embeddings = FakeEmbeddingService(vectors={
        claim_ok.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        claim_no_evidence.text: [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    cited = create_evidence(url="https://a.com", relevance_score=0.9)
    not_cited = create_evidence(url="https://b.com", relevance_score=0.4)

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({
            claim_ok.text: [cited, not_cited],
        }),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim_ok.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed.",
                cited_evidence=[0],
            ),
            claim_no_evidence.text: LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM verification unavailable or returned invalid output.",
                cited_evidence=[],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(article)

    checks = {check.claim: check for check in report.claim_checks}

    ok_check = checks[claim_ok.text]
    assert ok_check.reached_stage == "aggregation"
    assert ok_check.stage_note is None
    assert ok_check.raw_verdict == Verdict.TRUE
    assert [source.url for source in ok_check.rejected_sources] == ["https://b.com"]
    assert ok_check.rejected_sources[0].stage == "llm_verification"

    no_evidence_check = checks[claim_no_evidence.text]
    assert no_evidence_check.reached_stage == "confidence_recalibration"
    assert "No evidence" in no_evidence_check.stage_note
    assert no_evidence_check.verdict == Verdict.UNVERIFIED


def test_run_records_claims_dropped_during_selection(repository):

    kept_claim = create_claim(text="Kept claim.", confidence=0.9)
    dropped_claim = create_claim(text="Dropped claim.", confidence=0.5)

    article = create_article(claims=[kept_claim, dropped_claim])

    # Selection ranks by how load-bearing a claim is, not by extraction
    # confidence, so which one survives has to be pinned through the
    # thing that actually decides it: closeness to the article's thesis.
    on_thesis = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    off_thesis = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    thesis = f"{article.title}. {article.body[:400]}".strip()

    selector = ClaimSelector(embeddings=FakeEmbeddingService(vectors={
        thesis: on_thesis,
        kept_claim.text: on_thesis,
        dropped_claim.text: off_thesis,
    }))

    checker = FactChecker(
        repository,
        claim_selector=selector,
        evidence_retriever=FakeEvidenceRetriever({
            kept_claim.text: [create_evidence(url="https://a.com", relevance_score=0.9)],
        }),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            kept_claim.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed.",
                cited_evidence=[0],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    # The cap is a per-run threshold now, so it can be exercised the way
    # a real caller sets it rather than by reassigning a class attribute.
    report = checker.run(
        article,
        thresholds=PipelineThresholds(anchor_claims_max=1),
    )

    assert report.claims_selected == 1
    assert [c.text for c in report.unselected_claims] == ["Dropped claim."]
    assert report.unselected_claims[0].reason == "outside_anchor_band"


def test_run_with_no_claims_returns_unverified_overall(repository):

    article = create_article(claims=[])

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=FakeEmbeddingService()),
        evidence_retriever=FakeEvidenceRetriever({}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(article)

    assert report.validation_passed is True
    assert report.claims_selected == 0
    assert report.overall_verdict == Verdict.UNVERIFIED
    assert report.overall_confidence == 0.0


def test_run_reports_phases_when_validation_fails(repository):

    article = create_article(topics=[])

    checker = FactChecker(repository)

    events = []

    checker.run(article, on_phase=lambda phase, data: events.append((phase, data)))

    phases = [phase for phase, _ in events]
    assert phases == ["validating", "validated", "skipped"]

    validated_data = dict(events[1][1])
    assert validated_data["passed"] is False


def test_run_reports_a_phase_per_claim_and_final_summary(repository):

    claim = create_claim(text="A checkable claim.", confidence=0.9)

    article = create_article(claims=[claim])

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({
            claim.text: [create_evidence(url="https://a.com", relevance_score=0.9)],
        }),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed.",
                cited_evidence=[0],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    events = []

    checker.run(article, on_phase=lambda phase, data: events.append((phase, data)))

    phases = [phase for phase, _ in events]

    # Several events per claim, not one. Retrieval and the LLM call are the
    # slowest steps in the pipeline, and a single `claim_checked` at the
    # end left a polling client with nothing to show for the whole of it.
    # (A real EvidenceRetriever adds searching_web, web_results and the
    # scraping pair between the first two; this test injects a fake.)
    assert phases == [
        "validating",
        "validated",
        "selecting_claims",
        "claims_selected",
        "retrieving_evidence",
        "evidence_retrieved",
        "evidence_ranked",
        "verifying_claim",
        "claim_checked",
        "fact_check_done",
    ]

    by_phase = dict(events)

    # Each per-claim event names its claim, so a client checking five
    # claims can tell which one it is watching.
    for phase in (
        "retrieving_evidence",
        "evidence_retrieved",
        "evidence_ranked",
        "verifying_claim",
        "claim_checked",
    ):
        assert by_phase[phase]["claim"] == claim.text

    assert by_phase["evidence_retrieved"]["found"] == 1
    assert by_phase["verifying_claim"]["evidence"] == 1

    claim_checked_data = dict(events[phases.index("claim_checked")][1])
    assert claim_checked_data["verdict"] == Verdict.TRUE


def _run_one_claim_and_collect_events(repository, evidence):

    claim = create_claim(text="A checkable claim.", confidence=0.9)

    article = create_article(claims=[claim])

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({claim.text: evidence}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed.",
                cited_evidence=[0],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    events = []

    checker.run(article, on_phase=lambda phase, data: events.append((phase, data)))

    return dict(events)


def test_the_ranking_event_carries_each_sources_rating(repository):

    by_phase = _run_one_claim_and_collect_events(repository, [
        create_evidence(
            url="https://a.com",
            domain="a.com",
            relevance_score=0.9,
            semantic_score=0.8,
            recency_score=0.5,
            reliability_score=0.95,
            reliability_known=True,
        ),
    ])

    [source] = by_phase["evidence_ranked"]["sources"]

    assert source["url"] == "https://a.com"
    assert source["domain"] == "a.com"
    assert source["relevanceScore"] == 0.9
    assert source["semanticScore"] == 0.8
    assert source["recencyScore"] == 0.5
    assert source["reliabilityScore"] == 0.95
    assert source["reliabilityKnown"] is True


def test_the_verdict_event_says_which_sources_were_cited(repository):

    by_phase = _run_one_claim_and_collect_events(repository, [
        create_evidence(url="https://a.com", relevance_score=0.9),
        create_evidence(url="https://b.com", relevance_score=0.4),
    ])

    checked = by_phase["claim_checked"]

    assert checked["verdict"] == Verdict.TRUE
    assert [item["url"] for item in checked["evidence"]] == ["https://a.com", "https://b.com"]
    assert [item["cited"] for item in checked["evidence"]] == [True, False]
    assert checked["evidenceCount"] == 2


def test_events_never_carry_a_scraped_article_body(repository):
    """
    Events are held in memory, polled every second and journalled. A full
    page of text in each would make all three grow without bound.
    """

    import json

    by_phase = _run_one_claim_and_collect_events(repository, [
        create_evidence(
            url="https://a.com",
            content="body " * 5000,
            snippet="snippet " * 500,
            relevance_score=0.9,
        ),
    ])

    for phase in ("evidence_ranked", "claim_checked"):

        payload = by_phase[phase]
        source = (payload.get("sources") or payload["evidence"])[0]

        assert "content" not in source
        assert len(source["snippet"]) <= 240

    assert len(json.dumps(by_phase, default=str)) < 20_000

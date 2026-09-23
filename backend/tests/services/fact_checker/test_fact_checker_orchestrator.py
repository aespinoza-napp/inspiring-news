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


def test_run_does_not_judge_admission(repository):
    """
    Admission (topic, positive impact, duplicates) is its own module, run
    before FactChecker. An article that admission would turn away - no
    topics at all - is still checked when handed here directly.
    """

    checker = FactChecker(
        repository,
        evidence_retriever=FakeEvidenceRetriever({}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(create_article(topics=[], claims=[]))

    assert report.validation_passed is True
    assert report.skipped_reason is None
    assert report.failed_stage is None


def test_run_does_not_store_the_article(repository):
    """
    Storing it for later duplicate checks belongs to admission
    (AdmissionFilter.remember), not to fact-checking.
    """

    checker = FactChecker(
        repository,
        evidence_retriever=FakeEvidenceRetriever({}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    checker.run(create_article(claims=[]))

    assert repository.count() == 0


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


def test_run_traces_llm_unreachable_separately_from_no_evidence(repository):
    """
    Both a dead LLM and a claim with no evidence come back UNVERIFIED,
    but they must not be traced (or explained) identically - a run full
    of unreachable errors has to be visibly different from one that
    genuinely found nothing.
    """

    claim = create_claim(text="A claim the LLM was never reached for.", confidence=0.9)

    article = create_article(claims=[claim])

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    evidence = create_evidence(url="https://a.com", relevance_score=0.9)

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({claim.text: [evidence]}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim.text: LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM provider was unreachable; verdict could not be produced.",
                cited_evidence=[],
                llm_unreachable=True,
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(article)

    check = report.claim_checks[0]
    assert check.llm_unreachable is True
    assert check.reached_stage == "llm_verification"
    assert "unreachable" in check.stage_note


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
    #
    # One claim, so the order is still exact. With several the per-claim
    # events interleave by design - see the concurrency tests below.
    # No admission events: admission is its own module now, run before
    # FactChecker by AnalysisService.
    assert phases == [
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

    # Each per-claim event names its claim *and* its position in the
    # selected set, so a client watching five interleaved claims can tell
    # which one each event belongs to without re-deriving it from the text.
    for phase in (
        "retrieving_evidence",
        "evidence_retrieved",
        "evidence_ranked",
        "verifying_claim",
        "claim_checked",
    ):
        assert by_phase[phase]["claim"] == claim.text
        assert by_phase[phase]["claimIndex"] == 0

    # The full set of claims arrives with the count, before any of them
    # has been checked: concurrent checks have no order to arrive in, so
    # a client that learned each claim's text from its first event would
    # shuffle its own rows as the run progressed.
    assert [entry["text"] for entry in by_phase["claims_selected"]["claims"]] == [
        claim.text
    ]

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

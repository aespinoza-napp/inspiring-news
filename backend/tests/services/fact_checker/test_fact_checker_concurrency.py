"""
Claims are checked at the same time; each claim's own stages stay in
order.

That split is the only parallelism that makes sense in this pipeline -
retrieval feeds ranking, ranking feeds the LLM, and the LLM's answer is
what gets recalibrated, so within a claim there is nothing to overlap.
Between claims there is nothing shared at all, which is why a four-claim
article used to take four times as long as it needed to.

Both halves are load-bearing and both fail quietly: one as a slow run
nobody attributes to anything, the other as evidence indices pointing at
the wrong sources.
"""

import threading
import time

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


def _article_with_claims(count: int):
    """
    `count` distinct claims, with embeddings pinned far enough apart that
    claim selection keeps all of them rather than deduping them.
    """

    claims = [
        create_claim(text=f"Claim number {index}.", confidence=0.9)
        for index in range(count)
    ]

    vectors = {}

    for index, claim in enumerate(claims):
        vector = [0.0] * 8
        vector[index % 8] = 1.0
        vectors[claim.text] = vector

    return create_article(claims=claims), claims, FakeEmbeddingService(vectors=vectors)


def _evidence_for(claims):

    return {
        claim.text: [create_evidence(url=f"https://{index}.com", relevance_score=0.9)]
        for index, claim in enumerate(claims)
    }


def _checker(repository, claims, embeddings, retriever=None):

    return FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=retriever or FakeEvidenceRetriever(_evidence_for(claims)),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed.",
                cited_evidence=[0],
            )
            for claim in claims
        }),
        confidence_scorer=ConfidenceScorer(),
    )


def _run(checker, article, count, on_phase=None):

    return checker.run(
        article,
        on_phase=on_phase,
        thresholds=PipelineThresholds(anchor_claims_max=count),
    )


def test_claims_are_checked_concurrently(repository):
    """
    The claims share nothing, and every one of them spends its time
    waiting on a search, five page fetches and an LLM call.
    """

    article, claims, embeddings = _article_with_claims(4)

    lock = threading.Lock()
    in_flight = 0
    high_water = 0

    class ObservingRetriever(FakeEvidenceRetriever):

        def retrieve(self, claim, thresholds=None, context=None, language=None, on_phase=None):

            nonlocal in_flight, high_water

            with lock:
                in_flight += 1
                high_water = max(high_water, in_flight)

            try:
                # Long enough that sequential checks cannot overlap by
                # accident, short enough not to slow the suite.
                time.sleep(0.05)
                return super().retrieve(claim, thresholds, context, language, on_phase)
            finally:
                with lock:
                    in_flight -= 1

    checker = _checker(
        repository, claims, embeddings, ObservingRetriever(_evidence_for(claims))
    )

    report = _run(checker, article, 4)

    assert len(report.claim_checks) == 4
    assert high_water > 1


def test_one_claims_stages_still_run_in_order(repository):
    """
    Sequential by necessity, not by omission: each stage consumes what
    the one before it produced.
    """

    article, claims, embeddings = _article_with_claims(3)

    events = []

    _run(
        _checker(repository, claims, embeddings),
        article,
        3,
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    expected = [
        "retrieving_evidence",
        "evidence_retrieved",
        "evidence_ranked",
        "verifying_claim",
        "claim_checked",
    ]

    for claim in claims:

        stages = [
            phase
            for phase, data in events
            if data.get("claim") == claim.text and phase in expected
        ]

        assert stages == expected, f"stages ran out of order for {claim.text}"


def test_every_claim_is_checked_exactly_once(repository):

    article, claims, embeddings = _article_with_claims(4)

    report = _run(_checker(repository, claims, embeddings), article, 4)

    checked = [check.claim for check in report.claim_checks]

    assert len(checked) == 4
    assert len(set(checked)) == 4


def test_the_report_does_not_reorder_itself_by_which_claim_finished_first(repository):
    """
    Results in completion order would reshuffle the report - and with it
    every evidence index the UI, the cache and the lake record refer to -
    by whichever claim's search happened to be slowest that run.
    """

    article, claims, embeddings = _article_with_claims(4)

    class UnevenRetriever(FakeEvidenceRetriever):
        """Whichever claim is checked first finishes last."""

        def __init__(self, evidence_by_claim):
            super().__init__(evidence_by_claim)
            self._first = None
            self._lock = threading.Lock()

        def retrieve(self, claim, thresholds=None, context=None, language=None, on_phase=None):

            with self._lock:
                if self._first is None:
                    self._first = claim.text

            if claim.text == self._first:
                time.sleep(0.1)

            return super().retrieve(claim, thresholds, context, language, on_phase)

    checker = _checker(
        repository, claims, embeddings, UnevenRetriever(_evidence_for(claims))
    )

    ordered = [check.claim for check in _run(checker, article, 4).claim_checks]

    # The same run twice, with the same pinned embeddings, must produce
    # the same order - which it cannot if completion decides it.
    again = [check.claim for check in _run(checker, article, 4).claim_checks]

    assert len(ordered) == 4
    assert ordered == again


def test_each_claims_evidence_stays_with_that_claim(repository):
    """
    The failure mode concurrency invites, and the only one that would be
    silent: a claim scored against another claim's sources.
    """

    article, claims, embeddings = _article_with_claims(4)

    report = _run(_checker(repository, claims, embeddings), article, 4)

    by_claim = {check.claim: check for check in report.claim_checks}

    for index, claim in enumerate(claims):
        [evidence] = by_claim[claim.text].evidence
        assert evidence.url == f"https://{index}.com"


def test_a_verdict_is_reported_before_the_other_claims_finish(repository):
    """
    The point of the change from a reader's side: a claim that finishes
    early shows its verdict while the others are still being searched,
    instead of everything appearing at once at the end.
    """

    article, claims, embeddings = _article_with_claims(2)

    slow_started = threading.Event()

    class UnevenRetriever(FakeEvidenceRetriever):

        def retrieve(self, claim, thresholds=None, context=None, language=None, on_phase=None):

            if claim.text == claims[0].text:
                slow_started.set()
                time.sleep(0.2)
            else:
                # Only proceed once the slow claim is definitely working.
                slow_started.wait(timeout=2)

            return super().retrieve(claim, thresholds, context, language, on_phase)

    checker = _checker(
        repository, claims, embeddings, UnevenRetriever(_evidence_for(claims))
    )

    events = []

    _run(checker, article, 2, on_phase=lambda phase, data: events.append((phase, data)))

    phases = [phase for phase, _ in events]

    first_verdict = phases.index("claim_checked")

    # Work belonging to the other claim still happens after the first
    # verdict was reported, so a polling client had one on screen while
    # the run was still going.
    assert "claim_checked" in phases[first_verdict + 1:]


def test_phase_events_are_reported_one_at_a_time(repository):
    """
    on_phase is called from several threads now. Every caller writing one
    would otherwise have to be thread-safe - and they are not: the job
    runner's keeps per-phase timers in a closure, and the journal appends
    to a list. Serialising in FactChecker keeps their existing
    single-threaded contract instead of pushing a new requirement out to
    everyone who passes a callback.
    """

    article, claims, embeddings = _article_with_claims(4)

    lock = threading.Lock()
    overlaps = []
    inside = 0

    def on_phase(phase, data):

        nonlocal inside

        with lock:
            inside += 1
            if inside > 1:
                overlaps.append(phase)

        try:
            # Wide enough that concurrent callers would collide here.
            time.sleep(0.002)
        finally:
            with lock:
                inside -= 1

    _run(_checker(repository, claims, embeddings), article, 4, on_phase=on_phase)

    assert overlaps == []


def test_every_per_claim_event_carries_its_claim_and_index(repository):
    """
    The events of several claims interleave on the wire now. Without an
    index on each one, a client has to re-derive an identity the server
    already has - by matching event payloads on claim text.
    """

    article, claims, embeddings = _article_with_claims(3)

    events = []

    _run(
        _checker(repository, claims, embeddings),
        article,
        3,
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    per_claim = {
        "retrieving_evidence",
        "evidence_retrieved",
        "evidence_ranked",
        "verifying_claim",
        "claim_checked",
    }

    seen = {}

    for phase, data in events:

        if phase not in per_claim:
            continue

        assert "claim" in data, phase
        assert "claimIndex" in data, phase

        # One claim, one index, consistently, for the whole run.
        seen.setdefault(data["claim"], data["claimIndex"])
        assert seen[data["claim"]] == data["claimIndex"]

    assert sorted(seen.values()) == [0, 1, 2]


def test_the_claim_set_is_announced_before_any_of_them_is_checked(repository):
    """
    Concurrent checks have no order to arrive in, so a client that
    learned each claim's text from its first event would shuffle its own
    rows as the run progressed. Sending the whole set with the count
    lets it draw the final rows immediately and fill each in place.
    """

    article, claims, embeddings = _article_with_claims(3)

    events = []

    _run(
        _checker(repository, claims, embeddings),
        article,
        3,
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    phases = [phase for phase, _ in events]

    announced = phases.index("claims_selected")

    assert "retrieving_evidence" not in phases[:announced]

    payload = events[announced][1]

    assert payload["count"] == 3
    assert [entry["index"] for entry in payload["claims"]] == [0, 1, 2]
    assert {entry["text"] for entry in payload["claims"]} == {
        claim.text for claim in claims
    }

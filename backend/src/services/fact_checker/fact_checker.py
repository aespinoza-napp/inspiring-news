import threading
import time
from logging import getLogger
from typing import Callable, Optional

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.concurrency import bounded_map
from src.services.fact_checker.claim_selector import ArticleContext, ClaimSelector
from src.services.fact_checker.deadline import MIN_STAGE_SECONDS, Deadline
from src.services.fact_checker.progress import source_summary
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.retrieval.search_provider import registrable_domain
from src.services.fact_checker.second_look import SecondLooker, needs_second_look
from src.services.fact_checker.verification.confidence_scorer import (
    ConfidenceScorer,
    below_evidence_floor,
    holds_to_stances,
)
from src.services.fact_checker.verification.llm_verification import (
    LLMVerificationResult,
    LLMVerifier,
)

logger = getLogger(__name__)

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass


def _serialised(on_phase: OnPhase) -> OnPhase:
    """
    Wraps a phase callback so only one thread is inside it at a time.

    Claims are now checked concurrently, so `on_phase` is called from
    several threads at once. Every caller writing one would otherwise
    have to be thread-safe itself - and they are not: the job runner's
    callback keeps `last`/`start` timers in a closure to log how long
    each phase took, and the journal appends to a list. Serialising here
    keeps the callback's existing single-threaded contract intact rather
    than pushing a new requirement out to everyone who passes one.

    It does *not* serialise the work - only the reporting of it, which is
    a dict and a list append.
    """

    lock = threading.Lock()

    def report(phase: str, data: dict) -> None:
        with lock:
            on_phase(phase, data)

    return report


# How bad each verdict is for the article, since the article takes its
# worst claim's verdict. PARTIALLY_TRUE sits above TRUE but below
# UNVERIFIED: a claim whose detail is off has still been checked, which
# is strictly more than can be said for one nothing could be found for.
_VERDICT_SEVERITY = {
    Verdict.TRUE: 0,
    Verdict.PARTIALLY_TRUE: 1,
    Verdict.UNVERIFIED: 2,
    Verdict.MISLEADING: 3,
    Verdict.FALSE: 4,
}


class FactChecker:
    """
    Selects an article's most check-worthy claims and verifies each one
    against retrieved evidence, producing a FactCheckReport.

    It does not decide whether the article deserves checking - that is
    the admission module's job (src/services/admission/), run before
    this by AnalysisService. Everything here assumes the article was
    admitted.

    Claims are verified **concurrently**; each claim's own stages stay
    strictly **sequential**. That split is deliberate and is the only
    parallelism that makes sense here: retrieval feeds ranking, ranking
    feeds the LLM, and the LLM's answer is what gets recalibrated, so
    within a claim there is nothing to overlap. Between claims there is
    nothing shared at all - which is why a four-claim article used to
    take four times as long as it needed to.
    """

    def __init__(
        self,
        repository: VectorRepository,
        claim_selector: ClaimSelector | None = None,
        evidence_retriever: EvidenceRetriever | None = None,
        ranker: EvidenceRanker | None = None,
        verifier: LLMVerifier | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
        second_looker: SecondLooker | None = None,
    ):
        self.repository = repository
        self.claim_selector = claim_selector or ClaimSelector()
        self.evidence_retriever = evidence_retriever or EvidenceRetriever(repository)
        self.ranker = ranker or EvidenceRanker()
        self.verifier = verifier or LLMVerifier()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.second_looker = second_looker or SecondLooker()

    def run(
        self,
        article: EnrichedArticle,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> FactCheckReport:

        report_phase = _serialised(on_phase or _noop)

        thresholds = thresholds or PipelineThresholds()

        report_phase("selecting_claims", {})

        context = self._context(article)

        selection = self.claim_selector.select(
            article.claims or [],
            thresholds,
            context=context,
        )
        selected = selection.selected

        # The claim texts ride along with the count. They are all known
        # at this point and the client needs them all at once: with the
        # checks running concurrently there is no longer an order in
        # which claims appear, so a screen that waited to learn each
        # claim's text from its first event would shuffle its own rows as
        # the run progressed. Sent up front, the client draws the final
        # set of rows immediately and fills each one in place.
        report_phase("claims_selected", {
            "count": len(selected),
            "claims": [
                {"index": index, "text": claim.text, "anchorScore": claim.anchor_score}
                for index, claim in enumerate(selected)
            ],
        })

        claim_checks = bounded_map(
            lambda indexed: self._check_claim(
                indexed[1],
                report_phase,
                thresholds,
                context=context,
                language=article.language,
                claim_index=indexed[0],
            ),
            list(enumerate(selected)),
            max_workers=settings.CLAIM_MAX_CONCURRENCY,
            thread_name_prefix="claim-check",
        )

        report = FactCheckReport(
            article_id=article.id,
            # The admission fields keep their defaults here; AnalysisService
            # fills them from the admission result it ran first.
            validation_passed=True,
            claims_total=len(article.claims or []),
            claims_selected=len(selected),
            claim_checks=claim_checks,
            unselected_claims=selection.rejected,
            overall_verdict=self._aggregate_verdict(claim_checks),
            overall_confidence=self._aggregate_confidence(claim_checks),
            below_anchor_floor=len(selected) < thresholds.anchor_claims_min,
            **self._coverage(claim_checks),
        )

        report_phase("fact_check_done", {
            "overallVerdict": report.overall_verdict,
            "overallConfidence": report.overall_confidence,
            "belowAnchorFloor": report.below_anchor_floor,
        })

        return report

    def check_claim(
        self,
        claim: Claim,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> FactCheck:
        """
        Verify one claim on its own: retrieve evidence, rank it, ask the
        LLM, then recalibrate the confidence.

        Public because a single claim is a useful unit by itself, not
        only as a step inside an article run - POST /verify-claim calls
        exactly this, so the standalone checker and the pipeline cannot
        drift apart in what they consider verified.

        `context` and `language` are what an article run hands every
        claim, and what the evaluation harness has to hand a labelled
        one. Without `language` the query builder falls back to English,
        so a Spanish claim was searched with the English lexicon; without
        `context.url` the claim's own article could come back as evidence
        for it. Keyword-only and optional: /verify-claim has neither and
        passes neither.

        Note this skips claim selection: that judges an *article*, and a
        bare claim has none. (Admission is not part of FactChecker at all.)
        """

        return self._check_claim(
            claim,
            on_phase or _noop,
            thresholds or PipelineThresholds(),
            context=context,
            language=language,
        )

    @staticmethod
    def _context(article: EnrichedArticle) -> ArticleContext:
        """
        The article's thesis and main subjects, for claim selection and
        for restoring the subject a per-sentence claim lost.
        """

        return ArticleContext(
            title=article.title or "",
            url=article.url,
            # The opening of the body stands in for the lead. Nothing
            # upstream marks one, and the first few hundred characters of
            # a news article are the lead often enough to be useful here.
            lead=(article.body or "")[:400],
            keywords=article.keywords or [],
            entities=article.entities or {},
        )

    def _check_claim(
        self,
        claim: Claim,
        report_phase: OnPhase,
        thresholds: PipelineThresholds,
        context: ArticleContext | None = None,
        language: str | None = None,
        claim_index: int = 0,
    ) -> FactCheck:
        """
        One claim, end to end, in order: retrieve, rank, ask, recalibrate.

        Sequential by necessity, not by omission - each stage consumes
        what the one before it produced. The concurrency is between
        calls to this method, not inside it.

        `claim_index` is this claim's position in the selected set. Every
        event carries it because the events of several claims now
        interleave on the wire, and matching them up by claim text alone
        means the client re-derives an identity the server already has.
        """

        def phase(name: str, data: dict) -> None:
            report_phase(name, {"claim": claim.text, "claimIndex": claim_index, **data})

        # The claim's own clock, from here to its verdict: what the live
        # view shows as the time this claim took, stage by stage, and the
        # budget `claim_deadline_seconds` holds it to (deadline.py).
        deadline = Deadline(thresholds.claim_deadline_seconds)
        clock: dict = {}

        # The four sub-stages below are the slowest in the whole pipeline -
        # a live SearXNG search, scraping the top hits, and one LLM call -
        # and they used to emit nothing until `claim_checked` at the very
        # end. A five-claim article therefore showed the client four
        # updates spread over a minute of apparent silence. CLAUDE.md's
        # rule is per stage, not per method.

        phase("retrieving_evidence", {"deadline": deadline.seconds})

        retrieval = self.evidence_retriever.retrieve(
            claim,
            thresholds,
            context=context,
            language=language,
            on_phase=lambda name, data: report_phase(
                name, {"claimIndex": claim_index, **data}
            ),
            deadline=deadline,
        )

        clock["retrieval"] = round(deadline.elapsed(), 3)

        phase("evidence_retrieved", {
            "found": len(retrieval.kept),
            "rejected": len(retrieval.rejected),
            "queries": retrieval.queries,
            "rejectedSources": self._rejected_summary(retrieval.rejected),
        })

        check = self._judge(
            claim,
            retrieval.kept,
            phase,
            thresholds,
            context=context,
            language=language,
            # Already computed during retrieval; re-encoding it here was
            # a second round trip to inference/ for the same answer.
            claim_embedding=retrieval.claim_embedding,
            rejected=retrieval.rejected,
            search_unavailable=retrieval.search_unavailable,
            deadline=deadline,
            clock=clock,
        )

        # A verdict in doubt gets a second, wider search before it is
        # reported (second_look.py). Off unless the run asks for it - and
        # never past a deadline, which the first verdict already used.
        trigger = None if deadline.active else needs_second_look(check, thresholds)

        if trigger:
            first_done = deadline.elapsed()
            check = self.second_look(
                claim,
                check,
                phase,
                thresholds,
                context=context,
                language=language,
                trigger=trigger,
            )
            clock["secondLook"] = round(deadline.elapsed() - first_done, 3)

        cited = set(check.cited_evidence_indices)

        call = clock.pop("call", None) or {}

        phase("claim_checked", {
            "claim": check.claim,
            "verdict": check.verdict,
            "confidence": check.confidence,
            "explanation": check.explanation,
            "evidenceCount": check.evidence_count,
            "independentDomains": check.independent_domains,
            "searchUnavailable": check.search_unavailable,
            "agreements": check.agreements,
            "discrepancies": check.discrepancies,
            "evidence": [
                source_summary(item, cited=index in cited)
                for index, item in enumerate(check.evidence)
            ],
            # Where this claim's seconds went. `llmWait` is the queue for
            # the one model (another claim's call), `llm` the call itself;
            # `total` is the claim's own clock, second look included.
            "timings": {
                **clock,
                "llmWait": call.get("wait"),
                "llm": call.get("seconds"),
                "total": round(deadline.elapsed(), 3),
            },
            "llm": {
                "model": call.get("model"),
                "promptTokens": call.get("promptTokens"),
                "completionTokens": call.get("completionTokens"),
            } if call else None,
            "deadline": {
                "seconds": deadline.seconds,
                "exceeded": deadline.exceeded(),
            } if deadline.active else None,
        })

        return check

    def second_look(
        self,
        claim: Claim,
        first: FactCheck,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
        trigger: str = "requested",
    ) -> FactCheck:
        """
        A claim checked again, wider: follow-up queries written from what
        the first verdict said was missing, the new pages they find added
        to the first pass's evidence, and the whole judged once more.
        Public because the evaluation harness takes one on a claim whose
        first verdict disagrees with the gold label (the tuning loop).
        """

        return self.second_looker.recheck(
            self,
            claim,
            first,
            on_phase or _noop,
            thresholds or PipelineThresholds(),
            context=context,
            language=language,
            trigger=trigger,
        )

    def check_against(
        self,
        claim: Claim,
        urls: list[str],
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> tuple[FactCheck, int]:
        """
        The claim judged against the pages at `urls`, with no search: the
        annotator's own evidence links, so the verifier sees what the
        person who set the gold label saw (the "oracle" condition of
        FEVER and AVeriTeC). Every page is kept that could be read - no
        pertinence gate, since the annotator already chose them - up to
        the evidence cap. Returns the check and how many pages were read.
        """

        thresholds = thresholds or PipelineThresholds()

        pages = [
            Evidence(
                url=url,
                title="",
                origin=EvidenceOrigin.WEB,
                domain=registrable_domain(url),
                found_by=["reference"],
            )
            for url in dict.fromkeys(urls)
        ]

        read = [
            page for page in self.evidence_retriever.scraper.enrich(pages)
            if page.content
        ]

        check = self._judge(
            claim,
            read,
            on_phase or _noop,
            thresholds.model_copy(update={
                "evidence_min_pertinence": 0.0,
                "max_evidence_per_claim": max(thresholds.max_evidence_per_claim, len(read)),
            }),
            context=context,
            language=language,
        )

        return check, len(read)

    def _judge(
        self,
        claim: Claim,
        candidates: list[Evidence],
        phase: OnPhase,
        thresholds: PipelineThresholds,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
        claim_embedding=None,
        rejected: list[RejectedEvidence] | None = None,
        search_unavailable: bool = False,
        deadline: Deadline | None = None,
        clock: dict | None = None,
    ) -> FactCheck:
        """
        Rank, ask, recalibrate: everything after retrieval. One copy, so
        the first pass, a second look and a check against given pages
        cannot drift apart in what they consider verified.

        `deadline` bounds the model's call by what the claim has left;
        `clock`, when given, receives the ranking's seconds and the
        model call's record (LLMClient.last_call) for `claim_checked`.
        """

        clock = {} if clock is None else clock

        started = time.perf_counter()

        ranking = self.ranker.rank(
            claim,
            candidates,
            thresholds,
            claim_embedding=claim_embedding,
            language=language,
            context=context,
        )
        ranked = ranking.kept

        clock["ranking"] = round(time.perf_counter() - started, 3)

        # The rating each source received: relevance and the four factors
        # behind it, including how much its reliability figure is a real
        # rating rather than the default, and whether it addresses the
        # claim at all rather than merely its subject.
        phase("evidence_ranked", {
            "sources": [source_summary(item) for item in ranked],
            "cut": self._rejected_summary(ranking.rejected),
            "seconds": clock["ranking"],
        })

        left = deadline.remaining() if deadline is not None else None

        out_of_time = False

        if below_evidence_floor(ranked, thresholds):

            # Below the evidence floor the scorer forces UNVERIFIED
            # whatever the model says, so asking it was the single longest
            # step spent on an answer that was then thrown away - for 23
            # of 24 claims on 2026-09-25, when search returned nothing.
            # No `verifying_claim` either: the model is not being asked.
            llm_result = LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="",
            )

        elif left is not None and left < MIN_STAGE_SECONDS:

            # Out of time before the model could be asked: not checked,
            # as if it were unreachable - never a verdict for lack of time.
            out_of_time = True
            llm_result = LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM provider was unreachable; verdict could not be produced.",
                llm_unreachable=True,
            )

        else:

            # Ranking is embedding arithmetic over a handful of items, fast
            # enough not to deserve its own pair of events - but the LLM call
            # after it is the single longest step, so it gets one.
            phase("verifying_claim", {"evidence": len(ranked), "timeLeft": left})

            llm_result = self.verifier.verify(
                claim,
                ranked,
                context=context,
                thresholds=thresholds,
                language=language,
                **({"timeout": left} if left is not None else {}),
            )

            out_of_time = llm_result.llm_unreachable and deadline is not None and deadline.exceeded()

            if llm_result.call:
                clock["call"] = llm_result.call

        check = self.confidence_scorer.score(claim, ranked, llm_result, thresholds)

        not_cited = [
            RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.LLM_VERIFICATION,
                reason="retrieved and ranked, but not cited by the LLM",
                score=item.relevance_score,
            )
            for index, item in enumerate(ranked)
            if index not in llm_result.cited_evidence
        ]

        reached_stage, stage_note = self._trace(
            ranked, llm_result, check, thresholds, search_unavailable
        )

        if out_of_time:
            stage_note = (
                f"The model did not answer within the claim's {deadline.seconds:.0f} s "
                "deadline (claim_deadline_seconds); not checked, which says nothing "
                "about the claim."
            )

        return check.model_copy(update={
            "rejected_sources": (rejected or []) + ranking.rejected + not_cited,
            "reached_stage": reached_stage,
            "stage_note": stage_note,
            "raw_verdict": llm_result.verdict,
            "raw_confidence": llm_result.confidence,
            "llm_unreachable": llm_result.llm_unreachable,
            "search_unavailable": search_unavailable,
        })

    @staticmethod
    def _rejected_summary(rejected: list[RejectedEvidence]) -> list[dict]:

        return [
            {
                "url": item.url,
                "title": item.title,
                "reason": item.reason,
                "score": item.score,
            }
            for item in rejected
        ]

    def _trace(
        self,
        ranked: list[Evidence],
        llm_result: LLMVerificationResult,
        check: FactCheck,
        thresholds: PipelineThresholds,
        search_unavailable: bool = False,
    ) -> tuple[PipelineStage, Optional[str]]:

        if llm_result.llm_unreachable:
            return (
                PipelineStage.LLM_VERIFICATION,
                "LLM provider was unreachable; verdict could not be produced.",
            )

        # Before the evidence floor on purpose: both end in UNVERIFIED
        # with no evidence, and only this one says the web was never asked.
        if search_unavailable and below_evidence_floor(ranked, thresholds):
            return (
                PipelineStage.EVIDENCE_RETRIEVAL,
                "Web search was unavailable (SearXNG unreachable or its engines "
                "down); no evidence could be looked up, so this UNVERIFIED says "
                "nothing about the claim.",
            )

        if below_evidence_floor(ranked, thresholds):
            return (
                PipelineStage.CONFIDENCE_RECALIBRATION,
                "No evidence could be retrieved for this claim; verdict forced to "
                "UNVERIFIED without asking the LLM.",
            )

        if check.verdict != llm_result.verdict:

            # Each override has its own cause, and the note used to give
            # the first one for all of them - including a TRUE turned
            # PARTIALLY_TRUE by a contradicting source, which had cited
            # plenty.
            if check.verdict != Verdict.UNVERIFIED:
                reason = "a cited source contradicts part of it"
            elif not llm_result.cited_evidence:
                reason = "it cited no evidence"
            elif holds_to_stances(thresholds) and llm_result.verdict == Verdict.FALSE:
                # The stated rules (verifier_rules): no FALSE without a
                # cited source that contradicts, no TRUE without one that
                # supports (ConfidenceScorer).
                reason = "no source it cited states otherwise"
            elif holds_to_stances(thresholds) and ConfidenceScorer.cited_stances(llm_result):
                reason = "no source it cited states it"
            else:
                reason = "it cited only sources it judged unrelated to the claim"

            return (
                PipelineStage.CONFIDENCE_RECALIBRATION,
                f"LLM verdict {llm_result.verdict.value} recalibrated to "
                f"{check.verdict.value}: {reason}.",
            )

        return PipelineStage.AGGREGATION, None

    @staticmethod
    def _aggregate_verdict(claim_checks: list[FactCheck]) -> Verdict:

        if not claim_checks:
            return Verdict.UNVERIFIED

        return max(
            (check.verdict for check in claim_checks),
            key=lambda verdict: _VERDICT_SEVERITY[verdict],
        )

    @staticmethod
    def _coverage(claim_checks: list[FactCheck]) -> dict:
        """
        How each claim ended, apart from what the definitive ones found:
        not checked (the search or the model failed - ours, not a finding),
        unverified (looked for, nothing decisive), judged (a definitive
        verdict). found_verdict is the worst of the judged, by the same
        severity as the article's verdict.
        """

        def failed(check: FactCheck) -> bool:
            return check.search_unavailable or check.llm_unreachable

        judged = [check for check in claim_checks if not failed(check) and check.verdict != Verdict.UNVERIFIED]
        not_checked = sum(1 for check in claim_checks if failed(check))

        return {
            "found_verdict": (
                max((check.verdict for check in judged), key=lambda verdict: _VERDICT_SEVERITY[verdict])
                if judged else None
            ),
            "claims_judged": len(judged),
            "claims_unverified": len(claim_checks) - len(judged) - not_checked,
            "claims_not_checked": not_checked,
        }

    @staticmethod
    def _aggregate_confidence(claim_checks: list[FactCheck]) -> float:

        if not claim_checks:
            return 0.0

        return sum(check.confidence for check in claim_checks) / len(claim_checks)

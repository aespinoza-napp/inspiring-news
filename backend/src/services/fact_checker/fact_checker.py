import threading
from logging import getLogger
from typing import Callable, Optional

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.concurrency import bounded_map
from src.services.fact_checker.claim_selector import ArticleContext, ClaimSelector
from src.services.fact_checker.progress import source_summary
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.validation_pipeline import (
    ValidationPipeline,
    ValidationPipelineResult,
)
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
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
    Top-level orchestrator: validates an EnrichedArticle, and - only if
    validation passes - selects its most check-worthy claims and verifies
    each one against retrieved evidence, producing a FactCheckReport.

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
        validation_pipeline: ValidationPipeline | None = None,
        claim_selector: ClaimSelector | None = None,
        evidence_retriever: EvidenceRetriever | None = None,
        ranker: EvidenceRanker | None = None,
        verifier: LLMVerifier | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
    ):
        self.repository = repository
        self.validation_pipeline = validation_pipeline or ValidationPipeline(repository)
        self.claim_selector = claim_selector or ClaimSelector()
        self.evidence_retriever = evidence_retriever or EvidenceRetriever(repository)
        self.ranker = ranker or EvidenceRanker()
        self.verifier = verifier or LLMVerifier()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()

    def run(
        self,
        article: EnrichedArticle,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> FactCheckReport:

        report_phase = _serialised(on_phase or _noop)

        thresholds = thresholds or PipelineThresholds()

        report_phase("validating", {})

        validation = self.validation_pipeline.validate(article, thresholds)

        report_phase("validated", {
            "topicOk": validation.topic_ok,
            "positiveOk": validation.positive_ok,
            "duplicate": validation.duplicate,
            "passed": validation.passed,
            "impactScore": validation.impact_score,
            "impactReasons": validation.impact_reasons,
        })

        if not validation.passed:

            reason = self._reason(validation)

            report_phase("skipped", {"reason": reason})

            return FactCheckReport(
                article_id=article.id,
                validation_passed=False,
                skipped_reason=reason,
                topic_ok=validation.topic_ok,
                positive_ok=validation.positive_ok,
                impact_score=validation.impact_score,
                impact_reasons=validation.impact_reasons,
                duplicate=validation.duplicate,
                failed_stage=PipelineStage.ADMISSION_FILTER,
                claims_total=len(article.claims or []),
                claims_selected=0,
            )

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

        # Persist the article now that its own claim-checks are done (not
        # before - EvidenceRetriever's internal-corpus lookup would
        # otherwise sometimes surface this very article as "evidence" for
        # its own claims). That ordering is also why this is not inside
        # the fan-out above: it is a barrier, and every claim must be
        # past its retrieval before it runs.
        #
        # Nothing else in the app calls VectorRepository.save() at all,
        # so without this every duplicate check and every internal-evidence
        # lookup was permanently querying an empty collection - confirmed
        # live: DuplicateValidator never flagged a duplicate even when
        # re-validating the exact same article object twice in a row.
        try:
            self.repository.save(article)
        except Exception:
            logger.warning("Failed to persist article %s to the vector store", article.id, exc_info=True)

        report = FactCheckReport(
            article_id=article.id,
            validation_passed=True,
            topic_ok=validation.topic_ok,
            positive_ok=validation.positive_ok,
            impact_score=validation.impact_score,
            impact_reasons=validation.impact_reasons,
            duplicate=validation.duplicate,
            claims_total=len(article.claims or []),
            claims_selected=len(selected),
            claim_checks=claim_checks,
            unselected_claims=selection.rejected,
            overall_verdict=self._aggregate_verdict(claim_checks),
            overall_confidence=self._aggregate_confidence(claim_checks),
            below_anchor_floor=len(selected) < thresholds.anchor_claims_min,
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
    ) -> FactCheck:
        """
        Verify one claim on its own: retrieve evidence, rank it, ask the
        LLM, then recalibrate the confidence.

        Public because a single claim is a useful unit by itself, not
        only as a step inside an article run - POST /verify-claim calls
        exactly this, so the standalone checker and the pipeline cannot
        drift apart in what they consider verified.

        Note this skips the admission filter (topic/positivity/duplicate)
        and claim selection entirely: those judge an *article*, and a
        bare claim has neither.
        """

        return self._check_claim(
            claim,
            on_phase or _noop,
            thresholds or PipelineThresholds(),
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

        # The four sub-stages below are the slowest in the whole pipeline -
        # a live SearXNG search, scraping the top hits, and one LLM call -
        # and they used to emit nothing until `claim_checked` at the very
        # end. A five-claim article therefore showed the client four
        # updates spread over a minute of apparent silence. CLAUDE.md's
        # rule is per stage, not per method.

        phase("retrieving_evidence", {})

        retrieval = self.evidence_retriever.retrieve(
            claim,
            thresholds,
            context=context,
            language=language,
            on_phase=lambda name, data: report_phase(
                name, {"claimIndex": claim_index, **data}
            ),
        )

        phase("evidence_retrieved", {
            "found": len(retrieval.kept),
            "rejected": len(retrieval.rejected),
            "queries": retrieval.queries,
            "rejectedSources": self._rejected_summary(retrieval.rejected),
        })

        ranking = self.ranker.rank(
            claim,
            retrieval.kept,
            thresholds,
            # Already computed during retrieval; re-encoding it here was
            # a second round trip to inference/ for the same answer.
            claim_embedding=retrieval.claim_embedding,
            language=language,
        )
        ranked = ranking.kept

        # The rating each source received: relevance and the four factors
        # behind it, including how much its reliability figure is a real
        # rating rather than the default, and whether it addresses the
        # claim at all rather than merely its subject.
        phase("evidence_ranked", {
            "sources": [source_summary(item) for item in ranked],
            "cut": self._rejected_summary(ranking.rejected),
        })

        # Ranking is embedding arithmetic over a handful of items, fast
        # enough not to deserve its own pair of events - but the LLM call
        # after it is the single longest step, so it gets one.
        phase("verifying_claim", {"evidence": len(ranked)})

        llm_result = self.verifier.verify(claim, ranked)

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
            ranked, llm_result, check, thresholds
        )

        check = check.model_copy(update={
            "rejected_sources": retrieval.rejected + ranking.rejected + not_cited,
            "reached_stage": reached_stage,
            "stage_note": stage_note,
            "raw_verdict": llm_result.verdict,
            "raw_confidence": llm_result.confidence,
        })

        cited = set(check.cited_evidence_indices)

        phase("claim_checked", {
            "claim": check.claim,
            "verdict": check.verdict,
            "confidence": check.confidence,
            "explanation": check.explanation,
            "evidenceCount": check.evidence_count,
            "independentDomains": check.independent_domains,
            "agreements": check.agreements,
            "discrepancies": check.discrepancies,
            "evidence": [
                source_summary(item, cited=index in cited)
                for index, item in enumerate(check.evidence)
            ],
        })

        return check

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
    ) -> tuple[PipelineStage, Optional[str]]:

        if len(ranked) < thresholds.min_evidence_for_verdict:
            return (
                PipelineStage.CONFIDENCE_RECALIBRATION,
                "No evidence could be retrieved for this claim; verdict forced to UNVERIFIED.",
            )

        if check.verdict != llm_result.verdict:
            return (
                PipelineStage.CONFIDENCE_RECALIBRATION,
                f"LLM verdict {llm_result.verdict.value} cited no evidence; "
                "downgraded to UNVERIFIED with a low confidence ceiling.",
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
    def _aggregate_confidence(claim_checks: list[FactCheck]) -> float:

        if not claim_checks:
            return 0.0

        return sum(check.confidence for check in claim_checks) / len(claim_checks)

    @staticmethod
    def _reason(validation: ValidationPipelineResult) -> str:

        reasons = []

        if not validation.topic_ok:
            reasons.append("topic_not_relevant")

        if not validation.positive_ok:
            reasons.append("not_positive_impact")

        if validation.duplicate:
            reasons.append("duplicate_article")

        return ",".join(reasons) or "validation_failed"

"""
The second look: a claim whose first verdict is in doubt, checked again
with a wider search.

The first pass asks three questions of the web, planned from the claim
alone (`query_builder.py`: who and what, the assertion, its refutation).
When they find nothing usable the claim comes back UNVERIFIED, and when
they find something thin the model answers with low confidence - and
the first verdict's explanation usually says what was missing ("no
source reports the 2024 figure", "the sources describe a different
programme"). The second look turns that sentence into new queries:

1. The model is asked for up to three follow-up queries, in the claim's
   language, aimed at what the first check said was missing - the
   original study or report, an official figure, the organisation's own
   announcement. If it writes none, the claim itself is the query.
2. They are searched through the same provider as the first pass
   (concurrency, failure rule and fusion included), and only pages the
   first pass never saw, on domains it did not already have, are kept;
   the best `max_evidence_per_claim` of those are fetched.
3. The first pass's evidence and the new pages are judged together, by
   the same ranking, pertinence gate, verifier and recalibration
   (`FactChecker._judge`): the second verdict replaces the first, and
   the first is kept on it (`FactCheck.second_look`).

It fires, in production, only when the run asks for it
(`second_look_enabled`) and the first verdict is UNVERIFIED or below
`second_look_below_confidence` - never on an outage (no search, no
model), which a second search cannot fix, and never twice.

The evaluation harness takes one in a second place: on the tuning half
of the custom set, on every claim whose first verdict disagrees with the
gold label (`cli run --loop`, docs/decisions/evaluation.md, "The second
look"). That is how the trigger and its threshold are chosen without
looking at the test half.

After FIRE (Xie et al., NAACL 2025 Findings: iterative retrieval and verification) and
the question-generation step of AVeriTeC's baseline (Schlichtkrull et al.
2023), cut down to one extra round: on a CPU each round is a search, a
handful of page fetches and two model calls.
"""

from __future__ import annotations

import re
from logging import getLogger
from typing import TYPE_CHECKING, Callable

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, SecondLook, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.retrieval.evidence_retriever import _comparable
from src.services.fact_checker.retrieval.query_builder import PlannedQuery, QueryKind
from src.services.fact_checker.retrieval.search_provider import registrable_domain
from src.services.llms import LLMClient, LLMUnavailableError
from src.services.search import SearchUnavailableError

if TYPE_CHECKING:
    from src.services.fact_checker.fact_checker import FactChecker

logger = getLogger(__name__)

OnPhase = Callable[[str, dict], None]

UNVERIFIED = "unverified"
LOW_CONFIDENCE = "low_confidence"

MAX_FOLLOW_UP_QUERIES = 3

# A query longer than this is a sentence, not a search; one the model
# padded is cut rather than sent.
MAX_QUERY_WORDS = 14

_LANGUAGES = {"en": "English", "es": "Spanish", "ca": "Catalan"}

_WHITESPACE = re.compile(r"\s+")

FOLLOW_UP_SYSTEM_PROMPT = (
    "You help a fact-checker search the web. You are given a claim from a "
    "news article and what a first check concluded from the sources it "
    "found. Write search queries that would find a source able to settle "
    "the claim: the original study or report, an official statistic, the "
    "organisation's own announcement, or an independent news report of "
    "the same event.\n\n"
    'Respond with ONLY a JSON object: {"queries": ["<query>", "<query>"]}\n\n'
    "Rules:\n"
    "- At most 3 queries, each 3 to 10 words.\n"
    "- Write every query in the language you are told to use.\n"
    "- Name the specific people, organisations, places, figures and dates "
    "the claim names.\n"
    "- Aim at what the first check said was missing, not at what it "
    "already found.\n"
    "- No quotation marks, no site: or other search operators.\n"
    "- Do not judge the claim; only write the queries."
)


def doubt(check: FactCheck, below_confidence: float) -> str | None:
    """
    Why this verdict is in doubt, or None. An outage is not doubt: with
    no search or no model, a second search would meet the same outage.
    """

    if check.second_look is not None:
        return None

    if check.llm_unreachable or check.search_unavailable:
        return None

    if check.verdict == Verdict.UNVERIFIED:
        return UNVERIFIED

    if check.confidence < below_confidence:
        return LOW_CONFIDENCE

    return None


def needs_second_look(check: FactCheck, thresholds: PipelineThresholds) -> str | None:
    """The trigger the pipeline itself applies: `doubt`, when the run enabled it."""

    if not thresholds.second_look_enabled:
        return None

    return doubt(check, thresholds.second_look_below_confidence)


def _quiet(phase: str, data: dict) -> None:
    pass


class FollowUpPlanner:
    """The model, asked for the queries the first pass did not send."""

    def __init__(self, client: LLMClient | None = None):

        # None: the fact-checker's own verifier's client, so the
        # evaluation harness meters these calls with the verdict's.
        self.client = client

    def plan(
        self,
        claim: Claim,
        first: FactCheck,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
        client: LLMClient | None = None,
    ) -> list[str]:

        client = self.client or client or LLMClient()

        try:
            answer = client.complete_json(
                FOLLOW_UP_SYSTEM_PROMPT,
                self.prompt(claim, first, context=context, language=language),
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM unreachable while planning a second look: %s", exc)
            answer = None

        queries = self.clean(answer.get("queries") if isinstance(answer, dict) else None)

        # A model that wrote nothing usable still gets a second search:
        # the claim as a sentence, which the first pass never sent whole.
        return queries or [self._shorten(claim.text)]

    @staticmethod
    def prompt(
        claim: Claim,
        first: FactCheck,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> str:

        sources = "\n".join(
            f"- {item.title or item.url} ({item.domain or registrable_domain(item.url)})"
            for item in first.evidence
        ) or "- none"

        article = f"Article headline: {context.title}\n" if context and context.title else ""

        return (
            f"Language for the queries: {_LANGUAGES.get(language or 'en', 'English')}\n\n"
            f"{article}Claim: {claim.text}\n\n"
            f"First check: {first.verdict.value}, confidence {first.confidence:.2f}.\n"
            f"Its explanation: {first.explanation or '(none)'}\n"
            f"Sources it had:\n{sources}"
        )

    @classmethod
    def clean(cls, raw) -> list[str]:

        if not isinstance(raw, list):
            return []

        queries = []

        for item in raw:

            if not isinstance(item, str):
                continue

            text = _WHITESPACE.sub(" ", item.replace('"', " ").replace("“", " ").replace("”", " ")).strip()

            if len(text.split()) < 2:
                continue

            text = cls._shorten(text)

            if text.lower() not in (query.lower() for query in queries):
                queries.append(text)

        return queries[:MAX_FOLLOW_UP_QUERIES]

    @staticmethod
    def _shorten(text: str) -> str:

        return " ".join(text.split()[:MAX_QUERY_WORDS])


class SecondLooker:

    def __init__(self, planner: FollowUpPlanner | None = None):

        self.planner = planner or FollowUpPlanner()

    def recheck(
        self,
        checker: "FactChecker",
        claim: Claim,
        first: FactCheck,
        phase: OnPhase,
        thresholds: PipelineThresholds,
        *,
        context: ArticleContext | None = None,
        language: str | None = None,
        trigger: str = "requested",
    ) -> FactCheck:

        queries = self.planner.plan(
            claim,
            first,
            context=context,
            language=language,
            client=getattr(checker.verifier, "client", None),
        )

        phase("second_look", {
            "trigger": trigger,
            "firstVerdict": first.verdict,
            "firstConfidence": first.confidence,
            "queries": queries,
        })

        retriever = checker.evidence_retriever

        search_unavailable = False

        try:
            found = retriever.search_provider.search_queries(
                [PlannedQuery(query, QueryKind.FOLLOW_UP) for query in queries],
                thresholds,
                language,
            )
        except SearchUnavailableError:
            found, search_unavailable = [], True

        new, cut = self._new_pages(found, first, context, thresholds.max_evidence_per_claim)

        fetched = retriever.scraper.enrich(new)

        # The first pass's stances and quotes were the first judgment's;
        # the second one assigns its own.
        earlier = [
            item.model_copy(update={"stance": None, "quote": None})
            for item in first.evidence
        ]

        check = checker._judge(
            claim,
            earlier + fetched,
            _quiet,
            thresholds,
            context=context,
            language=language,
            rejected=[
                item for item in first.rejected_sources
                if item.stage == PipelineStage.EVIDENCE_RETRIEVAL
            ] + cut,
        )

        new_urls = {item.url for item in fetched}

        check = check.model_copy(update={
            "second_look": SecondLook(
                trigger=trigger,
                first_verdict=first.verdict,
                first_confidence=first.confidence,
                first_explanation=first.explanation,
                queries=queries,
                new_evidence=sum(item.url in new_urls for item in check.evidence),
                search_unavailable=search_unavailable,
            ),
        })

        phase("second_look_checked", {
            "verdict": check.verdict,
            "confidence": check.confidence,
            "firstVerdict": first.verdict,
            "newEvidence": check.second_look.new_evidence,
            "searchUnavailable": search_unavailable,
        })

        return check

    @staticmethod
    def _new_pages(
        found: list[Evidence],
        first: FactCheck,
        context: ArticleContext | None,
        limit: int,
    ) -> tuple[list[Evidence], list[RejectedEvidence]]:
        """
        Pages the first pass never saw, one per domain it did not already
        have, in the search's fused order; the article itself never.
        """

        seen = {_comparable(item.url) for item in first.evidence}
        seen |= {_comparable(item.url) for item in first.rejected_sources}

        if context and context.url:
            seen.add(_comparable(context.url))

        domains = {item.domain or registrable_domain(item.url) for item in first.evidence}

        kept: list[Evidence] = []
        cut: list[RejectedEvidence] = []

        for item in found:

            domain = item.domain or registrable_domain(item.url)

            if _comparable(item.url) in seen or domain in domains:
                continue

            if len(kept) >= limit:
                cut.append(RejectedEvidence(
                    url=item.url,
                    title=item.title,
                    origin=item.origin,
                    stage=PipelineStage.EVIDENCE_RETRIEVAL,
                    reason=f"second look: beyond the {limit} new pages fetched",
                    score=item.fusion_score,
                ))
                continue

            domains.add(domain)
            kept.append(item)

        return kept, cut

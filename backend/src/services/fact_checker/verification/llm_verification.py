import re
import time
from logging import getLogger

from pydantic import BaseModel, Field

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.terms import claim_terms
from src.services.fact_checker.verification import excerpts, per_source
from src.services.llms import LLMClient, LLMUnavailableError

logger = getLogger(__name__)

_VALID_VERDICTS = {verdict.value for verdict in Verdict}
_VALID_STANCES = {stance.value for stance in EvidenceStance}

# Quotes are compared with whitespace collapsed: a model reproducing a
# sentence faithfully still tends to normalise the line breaks and double
# spaces that scraped article text is full of, and rejecting a correct
# quote over a newline would defeat the check.
_WHITESPACE = re.compile(r"\s+")

# The explanation a claim gets when the model *was* reached but sent back
# nothing usable (an empty or unparseable response, or JSON that is not an
# object). No flag records this case - unlike `llm_unreachable` - so the
# text is the only trace of it in a stored report. A constant because two
# readers match it: the reader view (services/reader/views.py), so it does
# not show it as if the model had judged the claim, and the evaluation
# harness, which counts it per model - a small model failing the output
# format is a model-quality result. A copy of the sentence in either would
# stop matching the day it is reworded here.
INVALID_OUTPUT_EXPLANATION = "LLM verification unavailable or returned invalid output."

# A ceiling on the verdict's answer, so a model that loops stops. The
# longest of 196 answers in four evaluation runs (2026-10-20/21) was 328
# tokens, the median ~145; one call in those runs never stopped and held
# the LLM permit until LLM_TIMEOUT, twice. At ~9 tokens a second this
# ends a loop in under two minutes, and an answer cut here is not retried
# (LLMClient.complete_json): it comes back as invalid output, UNVERIFIED.
MAX_ANSWER_TOKENS = 1024

SYSTEM_PROMPT = (
    "You are a rigorous fact-checking assistant. You are given a claim "
    "extracted from a news article, usually with the article's headline "
    "and opening for context, and a numbered list of evidence "
    "snippets gathered from the web and from previously verified "
    "articles. Judge the claim against that evidence, source by source.\n\n"
    "Respond with ONLY a JSON object with this exact shape:\n"
    '{"verdict": "TRUE" | "PARTIALLY_TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED", '
    '"confidence": <float 0-1>, '
    '"explanation": "<one or two sentences>", '
    '"cited_evidence": [<int indices of evidence items you relied on>], '
    '"assessments": [{"index": <int>, '
    '"stance": "supports" | "contradicts" | "unrelated", '
    '"quote": "<text copied verbatim from that evidence item, or empty>"}]}\n\n'
    "Rules:\n"
    "- Give one assessment entry per evidence item you were shown.\n"
    "- The claim means what it means inside its article. When the article "
    "is given, judge the claim about the article's subject, even if the "
    "sentence itself does not name it. Evidence about a different event, "
    "activity or subject is \"unrelated\", even when it shares a place, a "
    "date or a figure with the claim.\n"
    "- A quote MUST be copied word for word from that evidence item. Do "
    "not paraphrase, translate, correct or shorten it mid-sentence. If "
    "nothing in the item is worth quoting, use an empty string.\n"
    "- PARTIALLY_TRUE means the central assertion holds but a detail "
    "(a figure, a date, an attribution) does not match the evidence.\n"
    "- MISLEADING means technically-true-but-deceptive framing or missing "
    "crucial context.\n"
    "- If the evidence list is empty or unrelated to the claim, answer UNVERIFIED.\n"
    "- Never state a fact that is not present in the evidence."
)

# The `compact` answer (PipelineThresholds.verifier_answer): the verdict,
# one stance per source and a short reason - no quotes, no per-source
# objects. On a CPU the model writes 6-14 tokens a second, and the full
# answer's median was ~145 tokens (328 the longest of 196): a third to a
# half of every call was the model writing quotes. The stance per source
# stays, because the scorer needs it (a citation of an "unrelated" source
# does not count); the quote goes, and the reader shows the passage the
# model read instead. The prompt is shorter too, and like the full one it
# is the same for every call, so Ollama reads it once and keeps it.
COMPACT_SYSTEM_PROMPT = (
    "You are a rigorous fact-checker. You get a claim from a news article, "
    "usually with the article's headline and opening, and numbered evidence "
    "from the web. Judge the claim against that evidence only.\n\n"
    "Respond with ONLY a JSON object:\n"
    '{"verdict": "TRUE" | "PARTIALLY_TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED", '
    '"confidence": <float 0-1>, '
    '"stances": ["supports" | "contradicts" | "unrelated", ...], '
    '"cited": [<int indices of the evidence you relied on>], '
    '"reason": "<at most 20 words>"}\n\n'
    "Rules:\n"
    "- stances: one per evidence item, in the order given.\n"
    "- Judge the claim about the article's subject. Evidence about a "
    "different event or subject is \"unrelated\", even when it shares a "
    "place, a date or a figure with the claim.\n"
    "- PARTIALLY_TRUE: the central assertion holds but a detail (a figure, "
    "a date, an attribution) does not match the evidence.\n"
    "- MISLEADING: technically true but deceptive framing or missing "
    "crucial context.\n"
    "- If no evidence supports or contradicts the claim, answer UNVERIFIED."
)

# The compact answer is ~50 tokens; this only stops a loop sooner than
# MAX_ANSWER_TOKENS would, since an answer cut here is not retried.
COMPACT_MAX_ANSWER_TOKENS = 200

# The `stated` rules (PipelineThresholds.verifier_rules). The prompts
# above define neither TRUE nor FALSE and offer no stance for a source
# that is on the subject but says nothing on the claim's point; on
# 2026-10-22 the 3B answered FALSE to 21 of 45 true train claims, most
# explained as "the evidence does not mention ...". These define each
# verdict by what a source states, and add "silent"; the scorer then
# holds the verdict to the stances (ConfidenceScorer).
_STATED_STANCES = (
    "- supports: the item states what the claim says.\n"
    "- contradicts: the item states something that cannot be true at the "
    "same time as the claim - another figure, date, person or outcome for "
    "the same thing.\n"
    "- silent: the item is about the claim's subject but does not say "
    "whether the claim is true.\n"
    "- unrelated: the item is about a different event, activity or subject, "
    "even when it shares a place, a date or a figure with the claim.\n\n"
)

_STATED_VERDICTS = (
    "Verdicts:\n"
    "- TRUE: an item supports the claim - its point, and its figures, dates "
    "and names.\n"
    "- FALSE: an item contradicts the claim.\n"
    "- PARTIALLY_TRUE: an item supports the central assertion and another "
    "contradicts a detail (a figure, a date, an attribution).\n"
    "- MISLEADING: technically true but deceptive framing or missing "
    "crucial context.\n"
    "- UNVERIFIED: no item supports or contradicts the claim.\n"
    "- Silence is not contradiction: a detail the evidence does not mention "
    "never makes a claim FALSE.\n\n"
)

STATED_SYSTEM_PROMPT = (
    "You are a rigorous fact-checking assistant. You are given a claim "
    "extracted from a news article, usually with the article's headline "
    "and opening for context, and a numbered list of evidence "
    "snippets gathered from the web and from previously verified "
    "articles. Judge the claim against that evidence, source by source.\n\n"
    "Respond with ONLY a JSON object with this exact shape:\n"
    '{"verdict": "TRUE" | "PARTIALLY_TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED", '
    '"confidence": <float 0-1>, '
    '"explanation": "<one or two sentences>", '
    '"cited_evidence": [<int indices of evidence items your verdict rests on>], '
    '"assessments": [{"index": <int>, '
    '"stance": "supports" | "contradicts" | "silent" | "unrelated", '
    '"quote": "<text copied verbatim from that evidence item, or empty>"}]}\n\n'
    "Stances, one assessment entry per evidence item you were shown:\n"
    + _STATED_STANCES
    + _STATED_VERDICTS
    + "Rules:\n"
    "- The claim means what it means inside its article. When the article "
    "is given, judge the claim about the article's subject, even if the "
    "sentence itself does not name it.\n"
    "- A quote MUST be copied word for word from that evidence item. Do "
    "not paraphrase, translate, correct or shorten it mid-sentence. If "
    "nothing in the item is worth quoting, use an empty string.\n"
    "- Never state a fact that is not present in the evidence."
)

COMPACT_STATED_SYSTEM_PROMPT = (
    "You are a rigorous fact-checker. You get a claim from a news article, "
    "usually with the article's headline and opening, and numbered evidence "
    "from the web. Judge the claim against that evidence only.\n\n"
    "Respond with ONLY a JSON object:\n"
    '{"verdict": "TRUE" | "PARTIALLY_TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED", '
    '"confidence": <float 0-1>, '
    '"stances": ["supports" | "contradicts" | "silent" | "unrelated", ...], '
    '"cited": [<int indices of the evidence your verdict rests on>], '
    '"reason": "<at most 20 words>"}\n\n'
    "Stances, one per evidence item, in the order given:\n"
    + _STATED_STANCES
    + _STATED_VERDICTS
    + "- Judge the claim about the article's subject."
)

# A source's turn is skipped when the claim's deadline leaves less than
# this for its call (fact_checker's MIN_STAGE_SECONDS, for one source).
_MIN_CALL_SECONDS = 2.0


def system_prompt(thresholds: PipelineThresholds) -> str:
    """The instructions a run's verifier is sent, by its answer and rules."""

    if thresholds.verifier_answer == "per_source":
        return per_source.PER_SOURCE_SYSTEM_PROMPT

    stated = thresholds.verifier_rules == "stated"

    if thresholds.verifier_answer == "compact":
        return COMPACT_STATED_SYSTEM_PROMPT if stated else COMPACT_SYSTEM_PROMPT

    return STATED_SYSTEM_PROMPT if stated else SYSTEM_PROMPT


def _is_index(value, evidence: list) -> bool:
    """
    Whether the model's `value` names one of the evidence items it was
    shown. `bool` is excluded explicitly: it subclasses `int`, so JSON
    `true` would otherwise name item 1.
    """

    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value < len(evidence)
    )


class EvidenceAssessment(BaseModel):
    """What the model concluded about one specific source."""

    index: int

    stance: EvidenceStance

    # Only ever set when the span was found verbatim in that source - see
    # LLMVerifier._validate_quote.
    quote: str | None = None


class LLMVerificationResult(BaseModel):

    verdict: Verdict

    confidence: float

    explanation: str

    cited_evidence: list[int] = Field(default_factory=list)

    assessments: list[EvidenceAssessment] = Field(default_factory=list)

    # True only when the provider was never actually reached - a dead
    # socket, not the model declining to find support. Kept separate from
    # a plain UNVERIFIED verdict so downstream (FactCheck.llm_unreachable)
    # can tell "checked, no evidence" from "never asked".
    llm_unreachable: bool = False

    # How the call went (LLMClient.last_call): the model, seconds waiting
    # for the LLM permit, the call's own seconds, tokens. For the timing
    # the live view shows; None when the client keeps no such record.
    call: dict | None = None


class LLMVerifier:

    def __init__(self, client: LLMClient | None = None):

        self.client = client or LLMClient()

    def verify(
        self,
        claim: Claim,
        evidence: list[Evidence],
        context: ArticleContext | None = None,
        *,
        thresholds: PipelineThresholds | None = None,
        language: str | None = None,
        timeout: float | None = None,
    ) -> LLMVerificationResult:
        """
        `context` is the article the claim came from. Without it the
        model judges a lone sentence - and a sentence about prize-money
        contests in Mexico City was confirmed by the city's marathon when
        the article was about aura-farming battles. Every word matched;
        the subject did not.

        `thresholds` says how much of each source the model is shown
        (`verifier_excerpt`, `verifier_excerpt_chars`) and in which shape
        it answers (`verifier_answer`); `language` is the claim's, for
        the stopwords the passages are chosen without.

        `timeout` is what the claim's deadline has left, permit wait
        included (LLMClient.complete_json); None is no deadline.
        """

        thresholds = thresholds or PipelineThresholds()

        if thresholds.verifier_answer == "per_source":
            return self._verify_per_source(claim, evidence, context, thresholds, language, timeout)

        compact = thresholds.verifier_answer == "compact"

        limits = {"timeout": timeout} if timeout is not None else {}

        try:
            result = self.client.complete_json(
                system_prompt(thresholds),
                self._build_prompt(claim, evidence, context, thresholds, language),
                max_tokens=COMPACT_MAX_ANSWER_TOKENS if compact else MAX_ANSWER_TOKENS,
                **limits,
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM unreachable while verifying claim: %s", exc)
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM provider was unreachable; verdict could not be produced.",
                llm_unreachable=True,
                call=self._last_call(),
            )

        return self._normalize(result, evidence).model_copy(update={"call": self._last_call()})

    def _verify_per_source(
        self,
        claim: Claim,
        evidence: list[Evidence],
        context: ArticleContext | None,
        thresholds: PipelineThresholds,
        language: str | None,
        timeout: float | None,
    ) -> LLMVerificationResult:
        """
        One call per source, then the verdict by per_source's rule. A
        source whose call failed or came back unusable has no stance, as
        the list verifier leaves a source without an assessment; only
        when no call reached the model is the claim "not checked".
        """

        if not evidence:
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="No evidence to judge the claim against.",
            )

        excerpt = self._excerpter(claim, context, thresholds, language)
        article = self._article_block(context)

        ends_at = None if timeout is None else time.monotonic() + timeout

        answers: list[per_source.SourceAnswer] = []

        for index, item in enumerate(evidence):

            limits = {}

            if ends_at is not None:

                left = ends_at - time.monotonic()

                if left < _MIN_CALL_SECONDS:
                    answers.append(per_source.SourceAnswer(index=index, unreachable=True))
                    continue

                limits["timeout"] = left

            try:
                answer = self.client.complete_json(
                    per_source.PER_SOURCE_SYSTEM_PROMPT,
                    per_source.prompt(article, claim.text, item, excerpt(item.content or item.snippet)),
                    max_tokens=per_source.PER_SOURCE_MAX_ANSWER_TOKENS,
                    **limits,
                )
            except LLMUnavailableError as exc:
                logger.warning("LLM unreachable while judging source %s: %s", index, exc)
                answers.append(per_source.SourceAnswer(index=index, call=self._last_call(), unreachable=True))
                continue

            stance = per_source.stance_of(answer)

            answers.append(per_source.SourceAnswer(
                index=index,
                stance=stance,
                quote=(
                    self._validate_quote(answer.get("quote"), item)
                    if stance in (EvidenceStance.SUPPORTS, EvidenceStance.CONTRADICTS)
                    else None
                ),
                call=self._last_call(),
            ))

        call = per_source.merged_call(answers)

        if all(answer.unreachable for answer in answers):
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM provider was unreachable; verdict could not be produced.",
                llm_unreachable=True,
                call=call,
            )

        if all(answer.stance is None for answer in answers):
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation=INVALID_OUTPUT_EXPLANATION,
                call=call,
            )

        verdict, confidence, cited = per_source.verdict_from(answers, evidence)

        return LLMVerificationResult(
            verdict=verdict,
            confidence=confidence,
            explanation=per_source.explanation(answers, evidence, language),
            cited_evidence=cited,
            assessments=[
                EvidenceAssessment(index=answer.index, stance=answer.stance, quote=answer.quote)
                for answer in answers
                if answer.stance is not None
            ],
            call=call,
        )

    def _last_call(self) -> dict | None:
        """The client's record of the call just made, if it keeps one."""

        last_call = getattr(self.client, "last_call", None)

        if not callable(last_call):
            return None

        call = last_call()

        return dict(call) if call else None

    def _build_prompt(
        self,
        claim: Claim,
        evidence: list[Evidence],
        context: ArticleContext | None = None,
        thresholds: PipelineThresholds | None = None,
        language: str | None = None,
    ) -> str:

        thresholds = thresholds or PipelineThresholds()

        if not evidence:
            block = "(no evidence retrieved)"
        elif thresholds.verifier_answer == "compact":
            # The outlet, not the URL: a URL is ~20 tokens of path the
            # model reads at CPU speed for nothing it judges on.
            excerpt = self._excerpter(claim, context, thresholds, language)
            block = "\n\n".join(
                f"[{i}] {item.title} ({item.domain or item.url})\n{excerpt(item.content or item.snippet)}"
                for i, item in enumerate(evidence)
            )
        else:
            excerpt = self._excerpter(claim, context, thresholds, language)
            block = "\n\n".join(
                f"[{i}] {item.title}\nURL: {item.url}\n{excerpt(item.content or item.snippet)}"
                for i, item in enumerate(evidence)
            )

        # The article block first: an article's claims share it, so after
        # the first claim's call Ollama finds it already read, with the
        # system prompt, and reads only the claim and its evidence.
        return f"{self._article_block(context)}Claim:\n{claim.text}\n\nEvidence:\n{block}"

    @staticmethod
    def _excerpter(
        claim: Claim,
        context: ArticleContext | None,
        thresholds: PipelineThresholds,
        language: str | None,
    ):
        """What of one source's text goes into the prompt."""

        budget = thresholds.verifier_excerpt_chars

        if thresholds.verifier_excerpt == "head":
            return lambda text: excerpts.head(text, budget)

        anchors, content = claim_terms(claim, language, context)

        return lambda text: excerpts.passages(text, budget, anchors, content)

    @staticmethod
    def _article_block(context: ArticleContext | None) -> str:
        """
        The headline and opening the claim was taken from, or nothing.

        Both, because either alone falls short often enough: extraction
        does not always find a headline, and an opening can be pure scene
        setting. Together they name the subject.
        """

        if context is None:
            return ""

        lines = []

        if context.title:
            lines.append(f"Headline: {context.title}")

        if context.lead:
            lines.append(f"Opening: {context.lead}")

        if not lines:
            return ""

        return "Article the claim comes from:\n" + "\n".join(lines) + "\n\n"

    def _normalize(self, result: dict | None, evidence: list[Evidence]) -> LLMVerificationResult:

        # Valid JSON is not necessarily an object: a model can answer a
        # bare "TRUE" or a list, and `.get` on either raised out of the
        # claim's thread and failed the whole article, every other
        # claim's verdict included (stress-tested 2026-10-02).
        if not result or not isinstance(result, dict):
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation=INVALID_OUTPUT_EXPLANATION,
                cited_evidence=[],
            )

        verdict_raw = str(result.get("verdict", "")).upper()
        verdict = Verdict(verdict_raw) if verdict_raw in _VALID_VERDICTS else Verdict.UNVERIFIED

        try:
            confidence = max(0.0, min(float(result.get("confidence", 0.0)), 1.0))
        except (TypeError, ValueError):
            confidence = 0.0

        # The compact answer names the same things more briefly: `reason`,
        # `cited`, and `stances` as a list in evidence order. Either shape
        # is read whatever was asked, since a small model mixes them.
        stances = result.get("stances")

        assessments = result.get("assessments")

        if not isinstance(assessments, list) and isinstance(stances, list):
            assessments = [
                {"index": index, "stance": stance}
                for index, stance in enumerate(stances)
            ]

        return LLMVerificationResult(
            verdict=verdict,
            confidence=confidence,
            explanation=str(
                result.get("explanation") or result.get("reason") or "No explanation provided."
            ).strip(),
            cited_evidence=self._citations(
                result["cited_evidence"] if "cited_evidence" in result else result.get("cited"),
                evidence,
            ),
            assessments=self._assessments(assessments, evidence),
        )

    @staticmethod
    def _citations(raw, evidence: list[Evidence]) -> list[int]:
        """
        The indices cited, each once, in the order first given.

        Each of these was a way to bluff, found by the 2026-10-02 stress
        test with an adversarial fake model:

        - `null`, or a bare `0` instead of a list, raised and failed the
          whole article.
        - A repeated index counted every time: `ConfidenceScorer` divides
          the citations by the sources, so `[0, 0, 0, ...]` took a FALSE
          resting on one source from 0.70 to 1.00 confidence.
        - JSON `true` is a Python `bool`, which is an `int`: `[true]`
          counted as citing source 1.
        """

        if not isinstance(raw, list):
            return []

        cited: list[int] = []

        for index in raw:

            if not _is_index(index, evidence) or index in cited:
                continue

            cited.append(index)

        return cited

    def _assessments(
        self,
        raw,
        evidence: list[Evidence],
    ) -> list[EvidenceAssessment]:
        """
        Parses the per-source block defensively: a local model asked for
        one more nested structure is the most likely part of the response
        to come back malformed, and a missing or broken `assessments` key
        must degrade to "no per-source detail" rather than lose the
        verdict that came back with it.
        """

        if not isinstance(raw, list):
            return []

        assessments = []
        seen: set[int] = set()

        for entry in raw:

            if not isinstance(entry, dict):
                continue

            index = entry.get("index")

            if not _is_index(index, evidence):
                continue

            if index in seen:
                continue

            stance_raw = str(entry.get("stance", "")).lower()

            if stance_raw not in _VALID_STANCES:
                continue

            seen.add(index)

            assessments.append(EvidenceAssessment(
                index=index,
                stance=EvidenceStance(stance_raw),
                quote=self._validate_quote(entry.get("quote"), evidence[index]),
            ))

        return assessments

    @staticmethod
    def _validate_quote(quote, item: Evidence) -> str | None:
        """
        Returns the quote only if it really appears in that source.

        A small local model will produce a plausible sentence and present
        it as a quotation, and an invented quote is worse than no quote at
        all: it is the one part of this output a reader would take at face
        value without clicking through. Anything not found verbatim in the
        source text is dropped.

        The title and the body are searched apart. Joined into one string,
        the end of the headline and the start of the body read as one
        sentence that appears in neither, and a quote made of the two
        passed as verbatim (2026-10-02 stress test).
        """

        if not isinstance(quote, str):
            return None

        candidate = _WHITESPACE.sub(" ", quote).strip()

        if len(candidate) < 10:
            return None

        needle = candidate.lower()

        if not any(
            needle in _WHITESPACE.sub(" ", text or "").lower()
            for text in (item.title, item.content or item.snippet)
        ):
            logger.debug("Dropped unlocatable quote for %s", item.url)
            return None

        return candidate

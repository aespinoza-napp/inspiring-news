import re
from logging import getLogger

from pydantic import BaseModel, Field

from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ArticleContext
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
# nothing usable (an empty or unparseable response). No flag records this
# case - unlike `llm_unreachable` - so the text is the only trace of it in
# a stored report. Named so the reader view (services/reader/views.py) can
# recognise it rather than show it as if the model had judged the claim.
INVALID_OUTPUT_EXPLANATION = "LLM verification unavailable or returned invalid output."

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


class LLMVerifier:

    def __init__(self, client: LLMClient | None = None):

        self.client = client or LLMClient()

    def verify(
        self,
        claim: Claim,
        evidence: list[Evidence],
        context: ArticleContext | None = None,
    ) -> LLMVerificationResult:
        """
        `context` is the article the claim came from. Without it the
        model judges a lone sentence - and a sentence about prize-money
        contests in Mexico City was confirmed by the city's marathon when
        the article was about aura-farming battles. Every word matched;
        the subject did not.
        """

        try:
            result = self.client.complete_json(
                SYSTEM_PROMPT,
                self._build_prompt(claim, evidence, context),
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM unreachable while verifying claim: %s", exc)
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM provider was unreachable; verdict could not be produced.",
                llm_unreachable=True,
            )

        return self._normalize(result, evidence)

    def _build_prompt(
        self,
        claim: Claim,
        evidence: list[Evidence],
        context: ArticleContext | None = None,
    ) -> str:

        if not evidence:
            block = "(no evidence retrieved)"
        else:
            block = "\n\n".join(
                f"[{i}] {item.title}\nURL: {item.url}\n{(item.content or item.snippet)[:1500]}"
                for i, item in enumerate(evidence)
            )

        return f"{self._article_block(context)}Claim:\n{claim.text}\n\nEvidence:\n{block}"

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

        return LLMVerificationResult(
            verdict=verdict,
            confidence=confidence,
            explanation=str(result.get("explanation") or "No explanation provided.").strip(),
            cited_evidence=self._citations(result.get("cited_evidence"), evidence),
            assessments=self._assessments(result.get("assessments"), evidence),
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

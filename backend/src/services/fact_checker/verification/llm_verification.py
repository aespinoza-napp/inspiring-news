import re
from logging import getLogger

from pydantic import BaseModel, Field

from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.services.llms import LLMClient, LLMUnavailableError

logger = getLogger(__name__)

_VALID_VERDICTS = {verdict.value for verdict in Verdict}
_VALID_STANCES = {stance.value for stance in EvidenceStance}

# Quotes are compared with whitespace collapsed: a model reproducing a
# sentence faithfully still tends to normalise the line breaks and double
# spaces that scraped article text is full of, and rejecting a correct
# quote over a newline would defeat the check.
_WHITESPACE = re.compile(r"\s+")

SYSTEM_PROMPT = (
    "You are a rigorous fact-checking assistant. You are given a claim "
    "extracted from a news article and a numbered list of evidence "
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

    def verify(self, claim: Claim, evidence: list[Evidence]) -> LLMVerificationResult:

        try:
            result = self.client.complete_json(
                SYSTEM_PROMPT,
                self._build_prompt(claim, evidence),
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

    def _build_prompt(self, claim: Claim, evidence: list[Evidence]) -> str:

        if not evidence:
            block = "(no evidence retrieved)"
        else:
            block = "\n\n".join(
                f"[{i}] {item.title}\nURL: {item.url}\n{(item.content or item.snippet)[:1500]}"
                for i, item in enumerate(evidence)
            )

        return f"Claim:\n{claim.text}\n\nEvidence:\n{block}"

    def _normalize(self, result: dict | None, evidence: list[Evidence]) -> LLMVerificationResult:

        if not result:
            return LLMVerificationResult(
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                explanation="LLM verification unavailable or returned invalid output.",
                cited_evidence=[],
            )

        verdict_raw = str(result.get("verdict", "")).upper()
        verdict = Verdict(verdict_raw) if verdict_raw in _VALID_VERDICTS else Verdict.UNVERIFIED

        try:
            confidence = max(0.0, min(float(result.get("confidence", 0.0)), 1.0))
        except (TypeError, ValueError):
            confidence = 0.0

        cited = [
            index
            for index in result.get("cited_evidence", [])
            if isinstance(index, int) and 0 <= index < len(evidence)
        ]

        return LLMVerificationResult(
            verdict=verdict,
            confidence=confidence,
            explanation=str(result.get("explanation") or "No explanation provided.").strip(),
            cited_evidence=cited,
            assessments=self._assessments(result.get("assessments"), evidence),
        )

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

            if not isinstance(index, int) or not 0 <= index < len(evidence):
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
        """

        if not isinstance(quote, str):
            return None

        candidate = _WHITESPACE.sub(" ", quote).strip()

        if len(candidate) < 10:
            return None

        haystack = _WHITESPACE.sub(" ", f"{item.title} {item.content or item.snippet}")

        if candidate.lower() not in haystack.lower():
            logger.debug("Dropped unlocatable quote for %s", item.url)
            return None

        return candidate

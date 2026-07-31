from logging import getLogger

from pydantic import BaseModel, Field

from src.models.claim import Claim
from src.models.evidence import Evidence
from src.models.fact_check import Verdict
from src.services.llms import LLMClient

logger = getLogger(__name__)

_VALID_VERDICTS = {verdict.value for verdict in Verdict}

SYSTEM_PROMPT = (
    "You are a rigorous fact-checking assistant. You are given a claim "
    "extracted from a news article and a numbered list of evidence "
    "snippets gathered from the web and from previously verified "
    "articles. Decide whether the evidence supports, contradicts, or "
    "is insufficient to judge the claim.\n\n"
    "Respond with ONLY a JSON object with this exact shape:\n"
    '{"verdict": "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED", '
    '"confidence": <float 0-1>, '
    '"explanation": "<one or two sentences>", '
    '"cited_evidence": [<int indices of evidence items you relied on>]}\n\n'
    "Rules:\n"
    "- If the evidence list is empty or unrelated to the claim, answer UNVERIFIED.\n"
    "- MISLEADING means technically-true-but-deceptive framing or missing crucial context.\n"
    "- Never state a fact that is not present in the evidence."
)


class LLMVerificationResult(BaseModel):

    verdict: Verdict

    confidence: float

    explanation: str

    cited_evidence: list[int] = Field(default_factory=list)


class LLMVerifier:

    def __init__(self, client: LLMClient | None = None):

        self.client = client or LLMClient()

    def verify(self, claim: Claim, evidence: list[Evidence]) -> LLMVerificationResult:

        result = self.client.complete_json(
            SYSTEM_PROMPT,
            self._build_prompt(claim, evidence),
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
        )

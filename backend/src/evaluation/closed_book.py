"""
The closed-book condition: the verifier's model with no evidence at all,
answering from its training alone (RQ2's first evidence condition, P0.5).

    uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split test \
        --closed-book --model llama3.2:3b

It cannot run through the pipeline: a claim with no evidence never reaches
the model there (FactChecker skips the call and ConfidenceScorer forces
UNVERIFIED), and the verifier's prompt tells it to answer UNVERIFIED on an
empty evidence list. So it has a prompt of its own - the same five
verdicts with the same definitions as LLMVerifier's, and nothing else: no
evidence, no claimant, no date, no fact-checker named - and the same
client (LLMClient, JSON mode, its retry).

As a harness mode its records are ordinary records, so `cli report`,
`--compare` and `cli table` pair it claim by claim with the run that
searched and the oracle run: the first gap is what retrieval adds, the
second what better retrieval could. Two questions the probe answered for
x-fact (scripts/closed_book_probe.py, which now imports this prompt):
does the model remember a published fact-check of the claim
(`closedBook.recallsFactCheck`), and how far does it get without evidence
- X-Fact's Claim-Only baseline, zero-shot.
"""

from __future__ import annotations

from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.fact_checker.verification.llm_verification import INVALID_OUTPUT_EXPLANATION
from src.services.llms import LLMUnavailableError

VERDICTS = ("TRUE", "PARTIALLY_TRUE", "MISLEADING", "FALSE", "UNVERIFIED")

SYSTEM_PROMPT = (
    "You are a rigorous fact-checking assistant. You are given a single "
    "claim, with no evidence and no context. Say what you know about it "
    "from your own knowledge.\n\n"
    "Respond with ONLY a JSON object with this exact shape:\n"
    '{"verdict": "TRUE" | "PARTIALLY_TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED", '
    '"confidence": <float 0-1>, '
    '"recalls_fact_check": <true if you remember a published fact-check of this '
    'specific claim, else false>, '
    '"fact_checker": "<the organisation that checked it, or empty>", '
    '"explanation": "<one sentence>"}\n\n'
    "Rules:\n"
    "- PARTIALLY_TRUE means the central assertion holds but a detail "
    "(a figure, a date, an attribution) does not.\n"
    "- MISLEADING means technically-true-but-deceptive framing or missing "
    "crucial context.\n"
    "- If you do not know, answer UNVERIFIED."
)

STAGE_NOTE = "Closed book: the model answered from the claim alone, with no evidence."


def _confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    # NaN fails both comparisons and falls to 0, as LLMVerifier treats it.
    return min(max(number, 0.0), 1.0) if number == number else 0.0


class ClosedBookJudge:
    """One claim to the model with no evidence: a FactCheck and what it recalled."""

    def __init__(self, client):
        self.client = client

    def judge(self, claim: str) -> tuple[FactCheck, dict]:

        try:
            answer = self.client.complete_json(SYSTEM_PROMPT, f"Claim: {claim}")
        except LLMUnavailableError as exc:
            # Set apart like any run's unreachable model, never scored.
            return FactCheck(
                verdict=Verdict.UNVERIFIED,
                raw_verdict=Verdict.UNVERIFIED,
                explanation=f"LLM provider was unreachable: {exc}"[:300],
                confidence=0.0,
                claim=claim,
                reached_stage=PipelineStage.LLM_VERIFICATION,
                stage_note=STAGE_NOTE,
                llm_unreachable=True,
            ), {"recallsFactCheck": None, "factChecker": None}

        verdict = str(answer.get("verdict", "")).strip().upper() if isinstance(answer, dict) else ""

        if verdict not in VERDICTS:
            # Scored as the UNVERIFIED the pipeline makes of an answer it
            # cannot read, and counted as invalid output (record.py).
            return FactCheck(
                verdict=Verdict.UNVERIFIED,
                raw_verdict=Verdict.UNVERIFIED,
                explanation=INVALID_OUTPUT_EXPLANATION,
                confidence=0.0,
                claim=claim,
                reached_stage=PipelineStage.LLM_VERIFICATION,
                stage_note=STAGE_NOTE,
            ), {"recallsFactCheck": None, "factChecker": None}

        confidence = _confidence(answer.get("confidence"))

        return FactCheck(
            verdict=Verdict(verdict),
            # No guardrail: nothing to cite, and forcing UNVERIFIED for
            # that would erase the condition being measured.
            raw_verdict=Verdict(verdict),
            explanation=str(answer.get("explanation") or "")[:400],
            confidence=confidence,
            raw_confidence=confidence,
            claim=claim,
            reached_stage=PipelineStage.LLM_VERIFICATION,
            stage_note=STAGE_NOTE,
        ), {
            "recallsFactCheck": answer.get("recalls_fact_check") is True,
            "factChecker": str(answer.get("fact_checker") or "")[:80] or None,
        }

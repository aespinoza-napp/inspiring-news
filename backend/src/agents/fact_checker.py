"""
Mock fact-checking agent.

Future implementation

    claim

        ↓

    Google Search

        ↓

    LLM

        ↓

    Verdict
"""

from src.models.claim import Claim
from src.models.fact_check import FactCheck


class FactChecker:

    def verify(
        self,
        claim: Claim,
    ) -> FactCheck:

        if "fake" in claim.text.lower():

            return FactCheck(
                verdict="FALSE",
                confidence=0.95,
                explanation="Mock keyword detection.",
            )

        return FactCheck(
            verdict="TRUE",
            confidence=0.80,
            explanation="Mock verification.",
        )
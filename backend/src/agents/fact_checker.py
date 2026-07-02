import openai
import os

class FactChecker:
    def check(self, title: str, content: str):
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"Fact check this headline: '{title}'. Context: {content}. Provide a status: Verified, Unverified, or False. Brief explanation."
        
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except:
            return "Fact check service unavailable"
        

from src.models.claim import Claim
from src.models.fact_check import FactCheck


class FactChecker:
    """
    Mock fact checker.

    If a claim contains 'fake'
    it is considered false.

    Everything else is true.
    """

    def verify(
        self,
        claim: Claim,
    ) -> FactCheck:

        if "fake" in claim.text.lower():

            return FactCheck(
                verdict="FALSE",
                explanation="Detected keyword 'fake'.",
                confidence=0.95,
            )

        return FactCheck(
            verdict="TRUE",
            explanation="Mock verification passed.",
            confidence=0.80,
        )
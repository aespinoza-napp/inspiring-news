"""
Natural Language Processing module.

Current implementation:
    • sentence segmentation
    • claim extraction
    • naive entity extraction

Future implementations may use

- spaCy
- OpenAI
- Gemini
- LangChain
"""

import re

from src.models.claim import Claim


class NLPProcessor:

    ENTITY_PATTERN = re.compile(r"\b[A-Z][a-zA-Z]+\b")

    def process(self, text: str) -> list[Claim]:
        """
        Convert an article into a list of factual claims.

        Parameters
        ----------
        text:
            Complete article text.

        Returns
        -------
        list[Claim]
        """

        claims = []

        sentences = [
            s.strip()
            for s in text.split(".")
            if s.strip()
        ]

        for sentence in sentences:

            entities = list(
                set(
                    self.ENTITY_PATTERN.findall(sentence)
                )
            )

            claims.append(
                Claim(
                    text=sentence,
                    entities=entities,
                    confidence=1.0,
                )
            )

        return claims
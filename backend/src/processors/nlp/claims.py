import re

from src.models.claim import Claim

from .base import BaseProcessor


class ClaimExtractor(BaseProcessor):

    ENTITY_PATTERN = re.compile(r"\b[A-Z][a-zA-Z]+\b")

    def process(self, text: str):

        claims = []

        sentences = [
            s.strip()
            for s in re.split(r"[.!?]", text)
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
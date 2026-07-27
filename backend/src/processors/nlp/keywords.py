"""
Keyword extraction processor.

Responsibilities
----------------
Extract the most representative keywords from a news article.

Current implementation
----------------------
- YAKE (lightweight)
- multilingual
- CPU friendly

Future implementations
----------------------
- KeyBERT
- spaCy
- LLM-based extraction
"""

from __future__ import annotations

from typing import List

import yake

from .base import BaseProcessor


class KeywordExtractor(BaseProcessor):
    """
    Extract keywords from a news article.

    Designed to be used inside the NLP Airflow module.
    """

    def __init__(
        self,
        language: str = "en",
        max_keywords: int = 10,
    ) -> None:

        self.language = language
        self.max_keywords = max_keywords

        self._extractor = yake.KeywordExtractor(
            lan=language,
            n=2,                  # unigrams + bigrams
            top=max_keywords,
            dedupLim=0.9,
        )

    def process(self, text: str) -> List[str]:
        """
        Parameters
        ----------
        text:
            Complete article.

        Returns
        -------
        list[str]
            Ranked keywords.
        """

        if not text:
            return []

        keywords = self._extractor.extract_keywords(text)

        return [
            keyword
            for keyword, _
            in keywords
        ]
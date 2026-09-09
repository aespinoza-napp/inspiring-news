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

        # One yake extractor per language, built on first use. yake takes
        # its language at construction (it selects the stopword list from
        # it), so a single English-configured extractor was ranking
        # Spanish articles against English stopwords - "de", "la" and
        # "que" all looked like meaningful keywords.
        self._extractors: dict[str, yake.KeywordExtractor] = {}

    def _extractor_for(self, language: str) -> "yake.KeywordExtractor":

        if language not in self._extractors:

            self._extractors[language] = yake.KeywordExtractor(
                lan=language,
                n=2,                  # unigrams + bigrams
                top=self.max_keywords,
                dedupLim=0.9,
            )

        return self._extractors[language]

    def process(self, text: str, language: str | None = None) -> List[str]:
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

        keywords = self._extractor_for(
            language or self.language
        ).extract_keywords(text)

        return [
            keyword
            for keyword, _
            in keywords
        ]
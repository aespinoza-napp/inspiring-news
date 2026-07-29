import textstat

from .base import BaseProcessor


class ReadabilityAnalyzer(BaseProcessor):

    def process(self, text: str) -> float:

        score = textstat.flesch_reading_ease(text)

        return max(
            0.0,
            min(score / 100.0, 1.0),
        )
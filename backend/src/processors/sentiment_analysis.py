"""
Sentiment analysis processor.

This module computes the overall sentiment polarity of a news article.
The implementation currently uses TextBlob but can easily be replaced
by another NLP model (e.g. VADER, spaCy, Hugging Face, OpenAI).
"""

from textblob import TextBlob


class SentimentAnalyzer:
    """Computes sentiment polarity for a piece of text."""

    def analyze(self, text: str) -> float:
        """
        Analyze the sentiment of a text.

        Parameters
        ----------
        text:
            Input text.

        Returns
        -------
        float
            Sentiment polarity in the range [-1.0, 1.0].

            -1.0 -> Very negative
             0.0 -> Neutral
             1.0 -> Very positive
        """

        if not text.strip():
            return 0.0

        return TextBlob(text).sentiment.polarity
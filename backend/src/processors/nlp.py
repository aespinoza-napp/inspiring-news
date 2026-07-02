from textblob import TextBlob
from rake_nltk import Rake
import nltk

nltk.download('punkt')
nltk.download('stopwords')

class NLPEngine:
    def __init__(self):
        self.rake = Rake()

    def analyze(self, text: str):
        # Sentiment
        analysis = TextBlob(text)
        sentiment = "Positive" if analysis.sentiment.polarity > 0 else "Negative" if analysis.sentiment.polarity < 0 else "Neutral"
        
        # Keywords
        self.rake.extract_keywords_from_text(text)
        keywords = self.rake.get_ranked_phrases()[:5]
        
        return sentiment, keywords
    

import re

from src.models.claim import Claim


class NLPProcessor:
    """
    Extremely simple NLP processor.

    - Splits the article into sentences.
    - Every sentence becomes a claim.
    - Extracts capitalized words as entities.
    """

    ENTITY_REGEX = re.compile(r"\b[A-Z][a-zA-Z]+\b")

    def process(self, text: str) -> list[Claim]:

        claims = []

        sentences = [
            sentence.strip()
            for sentence in text.split(".")
            if sentence.strip()
        ]

        for sentence in sentences:

            entities = sorted(
                set(self.ENTITY_REGEX.findall(sentence))
            )

            claims.append(
                Claim(
                    text=sentence,
                    confidence=1.0,
                    entities=entities,
                )
            )

        return claims
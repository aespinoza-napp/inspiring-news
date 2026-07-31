
from src.config.settings import settings
from src.models.nlp.nlp_result import NLPResult

from .claims import ClaimExtractor
from .classifier import TopicClassifier
from .embeddings import EmbeddingProcessor
from .entities import EntityExtractor
from .keywords import KeywordExtractor
from .sentiment import SentimentAnalyzer


class NLPProcessor:

    def __init__(self):

        self.keywords = KeywordExtractor()

        self.entities = EntityExtractor()

        self.classifier = TopicClassifier()

        self.sentiment = SentimentAnalyzer(settings)

        self.claims = ClaimExtractor()

        self.embeddings = EmbeddingProcessor()

    def process(self, text: str) -> NLPResult:

        return NLPResult(

            keywords=self.keywords.process(text),

            entities=self.entities.process(text),

            category=self.classifier.process(text),

            sentiment=self.sentiment.process(text),

            claims=self.claims.process(text),

            embedding=self.embeddings.process(text),
        )
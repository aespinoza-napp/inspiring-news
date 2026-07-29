from src.processors.nlp.keywords import KeywordExtractor
from src.processors.nlp.entities import EntityExtractor
from src.processors.nlp.claims import ClaimExtractor
from src.processors.nlp.classifier import TopicClassifier
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.embeddings import EmbeddingProcessor

from src.models.enriched_article import EnrichedArticle

class NewsEnrichmentPipeline:

    def __init__(self, cfg):

        self.keywords = KeywordExtractor()

        self.entities = EntityExtractor()

        self.claims = ClaimExtractor()

        self.topics = TopicClassifier()

        self.sentiment = SentimentAnalyzer(cfg)

        self.quality = QualityAnalyzer()

        self.embedding = EmbeddingProcessor()

    ####################################################

    def process(self, article):

        embedding = self.embedding.process(article.content)

        return EnrichedArticle(

            id=article.id,

            source_id=article.source_id,

            url=article.url,

            title=article.title,

            body=article.content,

            #language=article.language,

            keywords=self.keywords.process(article.content),

            entities=self.entities.process(article.content),

            topics=self.topics.process(article.content),

            claims=self.claims.process(article.content),

            sentiment=self.sentiment.process(article.content),

            quality=self.quality.process(article.content),

            embedding=embedding.tolist(),

            embedding_model=self.embedding.service.model_name,

            embedding_dimension=len(embedding),
        )
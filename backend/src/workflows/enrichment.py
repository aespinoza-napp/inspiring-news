from src.processors.nlp.keywords import KeywordExtractor
from src.processors.nlp.entities import EntityExtractor
from src.processors.nlp.claims import ClaimExtractor
from src.processors.nlp.classifier import TopicClassifier
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.embeddings import EmbeddingProcessor

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle

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

    def process(self, article, thresholds: PipelineThresholds | None = None):

        # Thresholds arrive per call, not per construction: this pipeline
        # is a long-lived singleton (it holds GLiNER, the topic
        # classifier and the sentiment model) shared by every request.
        thresholds = thresholds or PipelineThresholds()

        embedding = self.embedding.process(article.content)

        return EnrichedArticle(

            id=article.id,

            source_id=article.source_id,

            url=article.url,

            title=article.title or "",

            body=article.content,

            #language=article.language,
            
            published_at=article.published_at,

            keywords=self.keywords.process(article.content),

            entities=self.entities.process(
                article.content,
                thresholds.entity_threshold,
            ),

            topics=self.topics.process(
                article.content,
                thresholds.topic_classifier_threshold,
            ),

            claims=self.claims.process(
                article.content,
                thresholds.claim_min_confidence,
                thresholds.entity_threshold,
            ),

            sentiment=self.sentiment.process(article.content),

            quality=self.quality.process(article.content),

            embedding=embedding.tolist(),

            embedding_model=self.embedding.service.model_name,

            embedding_dimension=len(embedding),
        )

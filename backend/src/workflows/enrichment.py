from src.processors.nlp.keywords import KeywordExtractor
from src.processors.nlp.entities import EntityExtractor
from src.processors.nlp.claims import ClaimExtractor
from src.processors.nlp.classifier import TopicClassifier
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.embeddings import EmbeddingProcessor
from src.processors.nlp.iptc_topics import IptcTopicClassifier, lead as iptc_lead
from src.config.topics import GROUP_OF, TOPICS

# A TopicPrediction carries the topic's display name ("Mental Health"), not its
# id: the group of each name, for ordering by the IPTC classifier's group.
GROUP_OF_NAME = {TOPICS[topic].name: group for topic, group in GROUP_OF.items() if topic in TOPICS}

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.processors.nlp.language import LanguageDetector

class NewsEnrichmentPipeline:

    def __init__(self, cfg):

        self.keywords = KeywordExtractor()

        self.entities = EntityExtractor()

        self.claims = ClaimExtractor()

        self.topics = TopicClassifier()

        self.sentiment = SentimentAnalyzer(cfg)

        self.quality = QualityAnalyzer()

        self.embedding = EmbeddingProcessor()

        self.iptc = IptcTopicClassifier()

    ####################################################

    def entities_of(self, text: str, thresholds: PipelineThresholds | None = None) -> dict:
        """
        The article's entities, apart from the rest of the enrichment: since
        2026-11-17 they are extracted only after the article's check passed
        (AnalysisService), for the draft and the graph.
        """

        thresholds = thresholds or PipelineThresholds()

        return self.entities.process(text, thresholds.entity_threshold)

    def process(self, article, thresholds: PipelineThresholds | None = None, article_entities: bool = True):

        # Thresholds arrive per call, not per construction: this pipeline
        # is a long-lived singleton (it holds GLiNER, the topic
        # classifier and the sentiment model) shared by every request.
        thresholds = thresholds or PipelineThresholds()

        # Detect here too rather than trusting the caller: /enrich and any
        # News built by hand have no extractor to have set it.
        language = getattr(article, "language", None) or LanguageDetector.detect(
            article.content
        )

        embedding = self.embedding.process(article.content)

        # Computed before the constructor call so it can be handed to
        # QualityAnalyzer, whose `inspiration` metric weights sentiment
        # positivity at 0.35. It accepted a `sentiment` argument that the
        # pipeline never passed, so inspiration was scored against a
        # hardcoded 0.5 for every article ever analysed.
        sentiment = self.sentiment.process(article.content)

        topics = self.topics.process(
            article.content,
            thresholds.topic_classifier_threshold,
            embedding=embedding,
            edition=thresholds.edition,
        )

        topics, iptc_topic = self._iptc_group(article, topics, thresholds)

        return EnrichedArticle(

            id=article.id,

            source_id=article.source_id,

            url=article.url,

            title=article.title or "",

            body=article.content,

            language=language,
            
            published_at=article.published_at,

            keywords=self.keywords.process(article.content, language),

            # The article-level pass; `article_entities=False` leaves it for
            # after the check (entities_of). Each claim's sentence still gets
            # its own entities below, which the search needs either way.
            entities=self.entities.process(
                article.content,
                thresholds.entity_threshold,
            ) if article_entities else {},

            # The article's vector, computed above for storage: the
            # classifier would otherwise embed the same text again.
            topics=topics,

            iptc_topic=iptc_topic,

            claims=self.claims.process(
                article.content,
                thresholds.claim_min_confidence,
                thresholds.entity_threshold,
                language=language,
                opinion_max_score=thresholds.opinion_max_score,
            ),

            sentiment=sentiment,

            quality=self.quality.process(
                article.content,
                sentiment=sentiment,
                language=language,
            ),

            embedding=embedding.tolist(),

            embedding_model=self.embedding.service.model_name,

            embedding_dimension=len(embedding),
        )

    ####################################################

    def _iptc_group(self, article, topics, thresholds: PipelineThresholds):
        """
        Under `topic_group_classifier: iptc`, the group comes from the MN-DS
        classifier and the 23 topics are ordered with that group's first, the
        rest after in their own order: the topic shown and the group agree.
        An article the classifier reads as off the mission (politics, sport...)
        keeps its topics as they were, with the category recorded. Positive
        edition only: the IPTC table maps onto its five groups.
        """

        if thresholds.topic_group_classifier != "iptc" or thresholds.edition != "positive" or not self.iptc.available:
            return topics, None

        vector = self.embedding.service.encode(iptc_lead(article.title, article.content))
        best = self.iptc.predict(vector)[0]

        if best.group and topics:
            topics = sorted(topics, key=lambda topic: GROUP_OF_NAME.get(topic.topic) != best.group)

        return topics, best.as_dict()


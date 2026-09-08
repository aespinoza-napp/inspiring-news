
from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle


class TopicValidator:

    def validate(
        self,
        article: EnrichedArticle,
        thresholds: PipelineThresholds | None = None,
    ) -> bool:

        minimum = (thresholds or PipelineThresholds()).topic_min_confidence

        if not article.topics:
            return False

        return any(
            topic.confidence > minimum
            for topic in article.topics
        )

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle


class TopicFilter:
    """
    Is the article about one of the topics this publication covers?

    Reads only what enrichment already put on the article - its topic
    predictions - so it needs no service and makes no call.
    """

    def accepts(
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

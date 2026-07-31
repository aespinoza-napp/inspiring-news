
from src.models.core.enriched_article import EnrichedArticle


class TopicValidator:

    def validate(self, article: EnrichedArticle) -> bool:

        if not article.topics:
            return False

        return any(
            topic.confidence > 0.35
            for topic in article.topics
        )
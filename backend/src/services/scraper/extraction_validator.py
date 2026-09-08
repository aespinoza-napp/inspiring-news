from src.config.thresholds import PipelineThresholds
from src.models.scraper.extraction import ExtractionResult


class ExtractionValidator:

    @classmethod
    def is_valid(
        cls,
        article: ExtractionResult,
        thresholds: PipelineThresholds | None = None,
    ) -> bool:

        minimum = (thresholds or PipelineThresholds()).min_body_length

        #if not article.title:
        #    return False

        if len(article.body.strip()) < minimum:
            return False

        return True

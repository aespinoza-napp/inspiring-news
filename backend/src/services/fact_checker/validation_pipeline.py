# src/services/fact_checker/validation_pipeline.py

from dataclasses import dataclass

from src.models.core.enriched_article import EnrichedArticle
from src.repositories.vector_repository import VectorRepository
from src.services.fact_checker.validators.topic_validator import TopicValidator
from src.services.fact_checker.validators.positive_impact_validator import (
    PositiveImpactValidator,
)
from src.services.fact_checker.validators.duplicate_validator import (
    DuplicateValidator,
)


@dataclass
class ValidationPipelineResult:

    passed: bool

    topic_ok: bool

    positive_ok: bool

    duplicate: bool

    impact_score: float

    impact_reasons: list[str]


class ValidationPipeline:

    def __init__(self, repository: VectorRepository):

        self.topic_validator = TopicValidator()

        self.positive_validator = PositiveImpactValidator()

        self.duplicate_validator = DuplicateValidator(repository)


    def validate(self, article: EnrichedArticle):

        topic_ok = self.topic_validator.validate(article)

        positive = self.positive_validator.validate(
            article.sentiment,
            article.quality,
        )

        duplicate = self.duplicate_validator.validate(article)

        return ValidationPipelineResult(
            passed=(
                topic_ok
                and positive.passed
                and not duplicate.duplicate
            ),
            topic_ok=topic_ok,
            positive_ok=positive.passed,
            duplicate=duplicate.duplicate,
            impact_score=positive.score,
            impact_reasons=positive.reasons,
        )
from src.services.fact_checker.validation_pipeline import ValidationPipeline
from datetime import datetime
from tests.factories import create_article

def test_pipeline_accepts_valid_article(repository):

    pipeline = ValidationPipeline(repository)

    article = create_article()

    result = pipeline.validate(article)
    print(result)
    assert result.topic_ok
    assert result.positive_ok
    assert not result.duplicate
    assert result.passed

def test_pipeline_rejects_duplicate(repository):

    repository.clear()

    repository.save(
        create_article(
            id="11111111-1111-1111-1111-111111111111",
            embedding=[0.1] * 1024,
        )
    )

    duplicated = create_article(
        id="22222222-2222-2222-2222-222222222222",
        embedding=[0.1] * 1024,
    )

    pipeline = ValidationPipeline(repository)

    result = pipeline.validate(duplicated)

    assert result.duplicate

    assert not result.passed

def test_pipeline_rejects_invalid_topic(repository):

    pipeline = ValidationPipeline(repository)

    article = create_article()

    article.topics = []

    result = pipeline.validate(article)

    assert not result.topic_ok

    assert not result.passed

def test_pipeline_rejects_negative_article(repository):

    pipeline = ValidationPipeline(repository)

    article = create_article()

    article.sentiment.negative = 0.90
    article.sentiment.positive = 0.05
    article.sentiment.label = "negative"

    result = pipeline.validate(article)

    assert not result.positive_ok

    assert not result.passed
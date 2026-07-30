from src.config.settings import settings
from src.services.fact_checker.validators.duplicate_validator import (
    DuplicateValidator,
)

from tests.factories import create_article

def test_duplicate_detection(repository):

    original_article = create_article(
        id="11111111-1111-1111-1111-111111111111",
        title="NASA discovers water reserves on Mars",
        body="""
        NASA scientists have discovered underground
        water deposits beneath the surface of Mars.
        """,
        embedding=[
            0.1
        ] * 1024,
    )


    repository.save(original_article)


    duplicated_article = create_article(
        id="22222222-2222-2222-2222-222222222222",
        title="Scientists find underground water on Mars",
        body="""
        Researchers found evidence of water reservoirs
        below the Martian surface.
        """,
        embedding=[
            0.1
        ] * 1024,
    )


    validator = DuplicateValidator(
        repository
    )


    result = validator.validate(
        duplicated_article
    )
    print(result)

    assert result.duplicate is True

    assert result.matched_article_id == original_article.id

    assert (
        result.similarity
        >= settings.DUPLICATE_THRESHOLD
    )

def test_new_article_is_not_duplicate(repository):

    original_article = create_article(
        id="11111111-1111-1111-1111-111111111111",
        title="NASA discovers water reserves on Mars",
        embedding=[
            1.0
        ] + [
            0.0
        ] * 1023,
    )


    repository.save(original_article)


    new_article = create_article(
        id="22222222-2222-2222-2222-222222222222",
        title="Spain launches renewable energy program",
        embedding=[
            0.0,
            1.0
        ] + [
            0.0
        ] * 1022,
    )


    validator = DuplicateValidator(
        repository
    )


    result = validator.validate(
        new_article
    )


    assert result.duplicate is False

    assert result.matched_article_id is None

    assert result.reason == "Article is unrelated"


def test_related_article(repository):

    original_article = create_article(
        id="11111111-1111-1111-1111-111111111111",
        embedding=[
            1.0,
            0.0,
        ] + [
            0.0
        ] * 1022,
    )

    repository.save(original_article)


    related_article = create_article(
        id="22222222-2222-2222-2222-222222222222",
        embedding=[
            0.8,
            0.2,
        ] + [
            0.0
        ] * 1022,
    )


    validator = DuplicateValidator(
        repository
    )


    result = validator.validate(
        related_article
    )


    assert result.duplicate is False

    assert result.matched_article_id == original_article.id

    assert (
        result.similarity
        >= settings.RELATEDNESS_THRESHOLD
    )
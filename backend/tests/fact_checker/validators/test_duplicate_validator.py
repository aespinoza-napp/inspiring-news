"""
Every test here passes explicit thresholds rather than relying on
whatever `.env` happens to contain.

These used to depend on the *gap* between the configured duplicate and
relatedness thresholds happening to straddle a hard-coded vector's
similarity: `test_related_article` builds two vectors 0.970 apart and
needed 0.80 <= 0.970 < DUPLICATE_THRESHOLD to hold. Lowering
DUPLICATE_THRESHOLD to 0.96 in `.env` - a legitimate tuning change that
breaks nothing in the app - turned that test red. Thresholds are per-call
now, so the behaviour can be pinned instead of inherited.
"""

from src.config.thresholds import PipelineThresholds
from src.services.fact_checker.validators.duplicate_validator import (
    DuplicateValidator,
)

from tests.factories import create_article

ORIGINAL_ID = "11111111-1111-1111-1111-111111111111"
OTHER_ID = "22222222-2222-2222-2222-222222222222"

# 0.90 / 0.80: the app's own defaults (src/config/settings.py), stated
# here so the tests describe fixed behaviour instead of tracking .env.
THRESHOLDS = PipelineThresholds(
    duplicate_threshold=0.90,
    relatedness_threshold=0.80,
)


def unit_vector(*leading: float) -> list[float]:
    """A 1024-dim embedding with `leading` at the front, zeros after."""

    return list(leading) + [0.0] * (1024 - len(leading))


def test_duplicate_detection(repository):

    repository.save(
        create_article(
            id=ORIGINAL_ID,
            title="NASA discovers water reserves on Mars",
            body="NASA scientists have discovered underground water on Mars.",
            embedding=[0.1] * 1024,
        )
    )

    duplicated_article = create_article(
        id=OTHER_ID,
        title="Scientists find underground water on Mars",
        body="Researchers found evidence of water reservoirs below Mars.",
        embedding=[0.1] * 1024,
    )

    result = DuplicateValidator(repository).validate(
        duplicated_article, THRESHOLDS
    )

    assert result.duplicate is True
    assert result.matched_article_id == ORIGINAL_ID
    assert result.similarity >= THRESHOLDS.duplicate_threshold


def test_new_article_is_not_duplicate(repository):

    repository.save(
        create_article(id=ORIGINAL_ID, embedding=unit_vector(1.0))
    )

    # Orthogonal - similarity 0.0.
    new_article = create_article(id=OTHER_ID, embedding=unit_vector(0.0, 1.0))

    result = DuplicateValidator(repository).validate(new_article, THRESHOLDS)

    assert result.duplicate is False
    assert result.matched_article_id is None
    assert result.reason == "Article is unrelated"


def test_related_article(repository):
    """
    Similar enough to be worth linking (~0.97), below the duplicate bar
    of 0.90... which it is not. Use a genuinely in-between pair instead:
    0.85 sits above relatedness and below the duplicate threshold.
    """

    repository.save(
        create_article(id=ORIGINAL_ID, embedding=unit_vector(1.0))
    )

    # cos = 0.85 against (1, 0, 0, ...).
    related_article = create_article(
        id=OTHER_ID,
        embedding=unit_vector(0.85, (1 - 0.85**2) ** 0.5),
    )

    result = DuplicateValidator(repository).validate(
        related_article, THRESHOLDS
    )

    assert result.duplicate is False
    assert result.matched_article_id == ORIGINAL_ID
    assert result.reason == "Related article detected"
    assert (
        THRESHOLDS.relatedness_threshold
        <= result.similarity
        < THRESHOLDS.duplicate_threshold
    )


def test_the_duplicate_threshold_decides_the_verdict(repository):
    """
    The same pair of articles is a duplicate or merely related depending
    only on the threshold the run was given - which is the whole reason
    it is overridable.
    """

    repository.save(
        create_article(id=ORIGINAL_ID, embedding=unit_vector(1.0))
    )

    article = create_article(
        id=OTHER_ID,
        embedding=unit_vector(0.85, (1 - 0.85**2) ** 0.5),
    )

    validator = DuplicateValidator(repository)

    strict = validator.validate(
        article, PipelineThresholds(duplicate_threshold=0.99)
    )
    lenient = validator.validate(
        article, PipelineThresholds(duplicate_threshold=0.50)
    )

    assert strict.duplicate is False
    assert lenient.duplicate is True


def test_an_article_is_never_a_duplicate_of_itself(repository):
    """
    Re-validating an already-stored article must not flag it - the
    pipeline persists after fact-checking, so a re-run would otherwise
    reject every article the second time it was seen.
    """

    article = create_article(id=ORIGINAL_ID, embedding=unit_vector(1.0))

    repository.save(article)

    result = DuplicateValidator(repository).validate(article, THRESHOLDS)

    assert result.duplicate is False
    assert result.matched_article_id is None


def test_an_empty_corpus_yields_no_match(repository):

    result = DuplicateValidator(repository).validate(
        create_article(id=ORIGINAL_ID, embedding=unit_vector(1.0)),
        THRESHOLDS,
    )

    assert result.duplicate is False
    assert result.similarity == 0.0
    assert result.reason == "No similar articles found"

from src.config.topics import TOPICS
from src.processors.nlp.classifier import TopicClassifier


def test_topic_classifier(require_inference):
    """
    Needs a real embedding model (via a real, reachable inference/
    service) to mean anything - a fake's hash-derived vectors can't
    exercise real semantic similarity. Skips rather than fails when
    inference isn't running; see conftest.py's require_inference.
    """

    classifier = TopicClassifier()

    text = """
    OpenAI announced a new artificial intelligence
    model that improves programming and reasoning.
    """

    predictions = classifier.process(text)

    assert isinstance(predictions, list)

    assert len(predictions) > 0

    # This previously asserted an "artificial_intelligence" topic, which
    # is not one of the configured TOPICS at all - the assertion could
    # never pass. Assert the real contract instead: every prediction is a
    # configured topic, they come back ranked, and the probabilities are
    # a distribution.
    assert all(prediction.topic in TOPICS for prediction in predictions)

    assert predictions[0].topic == "technology"

    confidences = [prediction.confidence for prediction in predictions]
    assert confidences == sorted(confidences, reverse=True)

    assert all(
        0.0 <= prediction.confidence <= 1.0
        and 0.0 <= prediction.probability <= 1.0
        for prediction in predictions
    )

    # Tolerance, not 1e-6: TopicClassifier rounds each probability to 4
    # decimals, so across ~20 topics the rounding error alone reaches
    # ~1e-4 and the sum lands on e.g. 1.0001.
    assert abs(sum(p.probability for p in predictions) - 1.0) < 1e-3


def test_off_topic_text_returns_no_predictions(require_inference):

    classifier = TopicClassifier(threshold=0.99)

    assert classifier.process("asdf qwerty zxcv") == []


# ----------------------------------------------------------------------
# Each predicted topic carries its own keywords, scored against the article.
#
# These use a fake embedding service, so they need no inference/ and pin
# exactly which keyword is closest. The real-model tests above cover
# whether the classifier's topics are sensible; these cover what is done
# with a topic once it has matched.
# ----------------------------------------------------------------------

import pytest

from tests.services.fact_checker.fakes import FakeEmbeddingService

E0 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
E1 = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
E2 = [0.6, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

ARTICLE = (
    "Education matters. The school opened a new school year, and every "
    "education system in the city benefits. Social impact was measured."
)


@pytest.fixture
def fresh_caches(monkeypatch):
    """The classifier caches embeddings on the class; tests must not share them."""

    monkeypatch.setattr(TopicClassifier, "_topic_embeddings", None)
    monkeypatch.setattr(TopicClassifier, "_keyword_embeddings", None)


def _classifier(fresh_caches):

    embeddings = FakeEmbeddingService(vectors={
        ARTICLE: E0,
        "education": E0,       # identical to the article
        "school": E2,          # partly aligned
        "teacher": E1,         # unrelated
    })

    return TopicClassifier(threshold=-1.0, embedding_service=embeddings)


def _education(predictions):

    return next(p for p in predictions if p.topic == TOPICS["education"].name)


def test_a_topic_carries_its_own_keywords_closest_first(fresh_caches):

    education = _education(_classifier(fresh_caches).process(ARTICLE))

    assert {k.keyword for k in education.keywords} == set(TOPICS["education"].keywords)

    scores = [k.score for k in education.keywords]
    assert scores == sorted(scores, reverse=True)

    ranked = [k.keyword for k in education.keywords]
    assert ranked[0] == "education"
    assert ranked.index("school") < ranked.index("teacher")

    assert education.keywords[0].score == pytest.approx(1.0, abs=1e-4)


def test_mentions_count_whole_words_case_insensitively(fresh_caches):

    education = _education(_classifier(fresh_caches).process(ARTICLE))

    mentions = {k.keyword: k.mentions for k in education.keywords}

    assert mentions["education"] == 2   # "Education" and "education"
    assert mentions["school"] == 2
    assert mentions["teacher"] == 0     # scored on meaning, never mentioned


def test_a_keyword_is_not_found_inside_a_longer_word(fresh_caches):

    predictions = _classifier(fresh_caches).process(
        "The city has many cities and a citywide plan."
    )

    cities = next(p for p in predictions if p.topic == TOPICS["cities"].name)

    assert {k.keyword: k.mentions for k in cities.keywords}["city"] == 1


def test_a_multi_word_keyword_is_matched_as_a_phrase(fresh_caches):

    community = next(
        p for p in _classifier(fresh_caches).process(ARTICLE)
        if p.topic == TOPICS["community"].name
    )

    assert {k.keyword: k.mentions for k in community.keywords}["social impact"] == 1


def test_a_failed_start_does_not_leave_a_half_built_cache(fresh_caches):
    """
    The class caches topic embeddings for every later instance. Filling
    the cache while still computing it meant one failed call to the
    inference service left it partly full, and every later classifier
    silently knew fewer topics.
    """

    class FailsAfterTwoTopics(FakeEmbeddingService):

        calls = 0

        def encode(self, text):
            FailsAfterTwoTopics.calls += 1
            if FailsAfterTwoTopics.calls > 2:
                raise RuntimeError("inference is down")
            return super().encode(text)

    with pytest.raises(RuntimeError):
        TopicClassifier(embedding_service=FailsAfterTwoTopics())

    assert TopicClassifier._topic_embeddings is None

    class KeywordsFail(FakeEmbeddingService):

        def encode_many(self, texts):
            raise RuntimeError("inference is down")

    with pytest.raises(RuntimeError):
        TopicClassifier(embedding_service=KeywordsFail())

    assert TopicClassifier._keyword_embeddings is None

from src.config.thresholds import PipelineThresholds
from src.services.admission.admission_filter import AdmissionFilter
from tests.factories import create_article

def test_pipeline_accepts_valid_article(repository):

    pipeline = AdmissionFilter(repository)

    article = create_article()

    result = pipeline.admit(article)

    assert result.topic_ok
    assert result.positive_ok
    assert not result.duplicate
    assert result.passed

def test_pipeline_rejects_duplicate(repository):

    repository.save(
        create_article(
            id="11111111-1111-1111-1111-111111111111",
            embedding=[0.1] * 1024,
        )
    )

    duplicated = create_article(
        id="22222222-2222-2222-2222-222222222222",
        url="https://example.com/another-outlet",
        embedding=[0.1] * 1024,
    )

    pipeline = AdmissionFilter(repository)

    result = pipeline.admit(duplicated)

    assert result.duplicate

    assert not result.passed

def test_pipeline_rejects_invalid_topic(repository):

    pipeline = AdmissionFilter(repository)

    article = create_article()

    article.topics = []

    result = pipeline.admit(article)

    assert not result.topic_ok

    assert not result.passed

def test_pipeline_rejects_negative_article(repository):

    pipeline = AdmissionFilter(repository)

    article = create_article()

    article.sentiment.negative = 0.90
    article.sentiment.positive = 0.05
    article.sentiment.label = "negative"

    # Explicit: whether strong negative sentiment is a hard fail is a
    # setting, and this test is about what happens when it is on.
    result = pipeline.admit(
        article, PipelineThresholds(positive_impact_hard_fail_enabled=True)
    )

    assert not result.positive_ok

    assert not result.passed

def test_every_reason_is_reported_not_only_the_first(repository):
    """
    All three checks run even after one has failed, so the report can
    name every reason an article was turned away.
    """

    repository.save(create_article(id="11111111-1111-1111-1111-111111111111"))

    article = create_article(
        id="22222222-2222-2222-2222-222222222222",
        url="https://example.com/another-outlet",
        topics=[],
    )

    result = AdmissionFilter(repository).admit(article)

    assert result.topic_ok is False
    assert result.duplicate is True
    assert result.reason == "topic_not_relevant,duplicate_article"


def test_an_admitted_article_has_no_reason(repository):

    result = AdmissionFilter(repository).admit(create_article())

    assert result.passed
    assert result.reason is None


def test_admission_reports_its_phases(repository):

    events = []

    AdmissionFilter(repository).admit(
        create_article(topics=[]),
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    # The frontend's PhaseStepper matches these literals; they did not
    # change when admission moved out of FactChecker.
    assert [phase for phase, _ in events] == ["validating", "validated", "skipped"]
    assert events[1][1]["passed"] is False
    assert events[2][1] == {"reason": "topic_not_relevant"}


def test_an_admitted_article_reports_no_skip(repository):

    events = []

    AdmissionFilter(repository).admit(
        create_article(),
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    assert [phase for phase, _ in events] == ["validating", "validated"]


def test_admitting_does_not_store_the_article(repository):
    """
    Storing is a separate step, `remember`, taken after the fact-check:
    stored at admission, the article would be found as internal evidence
    for its own claims.
    """

    AdmissionFilter(repository).admit(create_article())

    assert repository.count() == 0


def test_a_remembered_article_is_caught_as_a_duplicate_next_time(repository):

    admission = AdmissionFilter(repository)

    first = create_article(id="11111111-1111-1111-1111-111111111111")
    assert admission.admit(first).passed
    admission.remember(first)

    # Same embedding (the factory default), another outlet's URL.
    second = create_article(
        id="22222222-2222-2222-2222-222222222222",
        url="https://example.com/another-outlet",
    )

    result = admission.admit(second)

    assert result.duplicate is True
    assert not result.passed
    assert repository.count() == 1


def test_reanalysing_the_same_url_is_admitted_and_replaces_the_stored_copy(repository):
    """
    Regression: extraction mints a new id every time, so re-running a URL
    hit its own stored copy at similarity 1.0 and was rejected as a
    duplicate of itself. It must pass, and the collection must keep one
    point per URL rather than growing a copy per run.
    """

    admission = AdmissionFilter(repository)

    admission.remember(create_article(id="11111111-1111-1111-1111-111111111111"))

    rerun = create_article(id="22222222-2222-2222-2222-222222222222")
    result = admission.admit(rerun)
    admission.remember(rerun)

    assert result.passed
    assert result.duplicate is False
    assert repository.count() == 1
    assert repository.exists("22222222-2222-2222-2222-222222222222")
    assert not repository.exists("11111111-1111-1111-1111-111111111111")


def test_a_failing_vector_store_does_not_fail_remember():

    class BrokenRepository:
        def save(self, article):
            raise RuntimeError("disk full")

    AdmissionFilter(BrokenRepository()).remember(create_article())

"""
Shared pieces for the rewrite stage's tests (not a test module: no
`test_` prefix). The writer's and the reviewer's models are
FakeLLMClients answering in order; sentiment is faked as in the review's
tests; readability and the positive-impact score are the real ones.
"""

from __future__ import annotations

from src.models.corrector.correction_metric import CorrectionMetric
from src.models.nlp.sentiment_result import SentimentResult
from src.models.writer.draft import DraftContent, DraftReview
from src.services.corrector.draft_reviewer import METRIC_ORDER, DraftReviewer
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY
from src.services.writer.article_writer import ArticleWriter
from src.services.writer.rewriter import DraftRewriter

from tests.factories import create_draft
from tests.services.fact_checker.fakes import FakeLLMClient, FakeSentimentAnalyzer

POSITIVE = SentimentResult(
    label="positive",
    positive=0.8,
    neutral=0.15,
    negative=0.05,
    polarity=0.75,
    subjectivity=0.3,
    confidence=0.9,
    emotional_intensity=0.75,
)

# What the review's model scores (draft_reviewer.REVIEW_LLM_KEYS).
MODEL_METRICS = ("title", "subtitle", "grammar", "factConsistency", "seo", "hallucinationIndex", "style")

# readability and coverageVerification are measured from the text, not
# by the model: a test about the loop sets their targets to 0 so it
# turns on the model's scores alone. Also what proves overrides arrive.
LOOSE = {"readability": 0, "coverageVerification": 0}

WRITER_MODEL = "writer-model"

REVIEWER_MODEL = "reviewer-model"

# The factory draft's body, rewritten as a copy editor would: the same
# facts, the same citations on the same statements.
GOOD_BODY = "Since 2015 the meadow has doubled in size [1], and fish counts rose with it [2]."


def review_answer(score: float = 90, **overrides) -> dict:
    """The review model's answer: every metric at `score`; a key set to None is left out (unscored)."""

    answer = {key: {"score": score, "summary": "Fine.", "issues": []} for key in MODEL_METRICS}

    for key, value in overrides.items():
        if value is None:
            answer.pop(key, None)
        elif isinstance(value, dict):
            answer[key] = value
        else:
            answer[key] = {"score": value, "summary": f"{key} at {value}.", "issues": [f"An issue with {key}."]}

    return answer


def rewrite_answer(body: str = GOOD_BODY, **fields) -> dict:

    return {
        "title": "Seagrass meadows double in the bay",
        "subtitle": "Ten years of replanting doubled the meadow, and the fish came back",
        "body": body,
        **fields,
    }


def a_review(score: float = 90, model: str = "first-reviewer", **scores) -> DraftReview:
    """A stored review: every metric at `score`, any named one at its own; None = unscored."""

    metrics = {}

    for key in METRIC_ORDER:

        value = scores.get(key, score)

        metrics[key] = (
            CorrectionMetric(score=0.0, summary=UNAVAILABLE_SUMMARY)
            if value is None
            else CorrectionMetric(score=value, summary=f"{key} summary.", issues=[f"{key} issue."])
        )

    return DraftReview(metrics=metrics, model=model, reviewed_at="2026-10-15T08:00:00+00:00")


def reviewed_draft(review: DraftReview | None = None, **kwargs):
    """The factory draft with a review of its current text."""

    draft = create_draft(**kwargs)
    draft.review = review or a_review(factConsistency=50)

    return draft


def llm(responses: list, model: str) -> FakeLLMClient:

    client = FakeLLMClient(list(responses))
    client.model = model

    return client


def make_rewriter(rewrites: list, reviews: list) -> DraftRewriter:
    """
    `rewrites` answer the writer's model in order; `reviews` the reviewer's,
    two calls per review - the metrics, then the proposed correction
    (None: no proposal).
    """

    return DraftRewriter(
        writer=ArticleWriter(llm(rewrites, WRITER_MODEL)),
        reviewer=DraftReviewer(
            llm=llm(reviews, REVIEWER_MODEL),
            sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE),
        ),
    )


def content(body: str) -> DraftContent:

    return DraftContent(
        title="Seagrass meadows return to the bay",
        subtitle="Ten years of replanting doubled the meadow's area",
        body=body,
    )

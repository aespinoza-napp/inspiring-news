"""
/drafts/{id}/review and /drafts/{id}/accept-correction
(src/api/review_routes.py).
"""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.container as container
from src.config.settings import settings
from src.main import app
from src.models.nlp.sentiment_result import SentimentResult
from src.models.writer.draft import DraftContent, DraftReview
from src.services.corrector.draft_reviewer import METRIC_ORDER, DraftReviewer
from src.services.llms import LLMUnavailableError
from src.services.writer.draft_store import DraftStore, revise
from tests.factories import create_draft
from tests.services.fact_checker.fakes import FakeLLMClient, FakeSentimentAnalyzer

client = TestClient(app)

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

ANSWER = {
    key: {"score": 85, "summary": "Fine.", "issues": []}
    for key in ("title", "subtitle", "grammar", "factConsistency", "seo", "hallucinationIndex", "style")
}

CORRECTED = {
    "title": "Seagrass meadows double in the bay after ten years",
    "subtitle": "Replanting since 2015 doubled the meadow, and the fish came back",
    "body": "The meadow has doubled in size since 2015 [1], and fish counts rose with it [2].",
}


@pytest.fixture
def synchronous(monkeypatch):
    """Background work runs in the request, so a test reads its result."""

    run = DraftStore.run_in_background

    def waiting(self, draft_id, busy, work, *, wait=False):
        return run(self, draft_id, busy, work, wait=True)

    monkeypatch.setattr(DraftStore, "run_in_background", waiting)


def install(monkeypatch, llm) -> DraftReviewer:

    reviewer = DraftReviewer(llm=llm, sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE))

    monkeypatch.setattr(container, "_draft_reviewer", reviewer)

    return reviewer


@pytest.fixture
def reviewer(monkeypatch):

    return install(monkeypatch, FakeLLMClient([ANSWER, CORRECTED]))


# ----------------------------------------------------------------------
# Reviewing
# ----------------------------------------------------------------------


def test_a_review_lands_on_the_draft(draft_store, reviewer, synchronous):

    draft = draft_store.save(create_draft())

    response = client.post(f"/drafts/{draft.id}/review")

    assert response.status_code == 202

    stored = draft_store.get(draft.id)

    assert stored.busy is None
    assert stored.error is None
    assert list(stored.review.metrics) == list(METRIC_ORDER)
    assert stored.review.corrected == DraftContent(**CORRECTED)
    # The content itself is a person's to change.
    assert stored.content == draft.content

    body = response.json()
    assert body["review"]["metrics"]["title"]["score"] == 85
    assert body["review"]["corrected"]["title"] == CORRECTED["title"]


def test_the_review_starts_in_the_background_and_answers_busy(draft_store, monkeypatch):

    started = threading.Event()
    release = threading.Event()

    class SlowLLM(FakeLLMClient):
        def complete_json(self, system_prompt, user_prompt, max_retries=1):
            started.set()
            release.wait(5)
            return super().complete_json(system_prompt, user_prompt, max_retries)

    install(monkeypatch, SlowLLM([ANSWER, CORRECTED]))

    draft = draft_store.save(create_draft())

    response = client.post(f"/drafts/{draft.id}/review")

    assert response.status_code == 202
    assert response.json()["busy"] == "reviewing"

    assert started.wait(5)
    # A second step on a busy draft is refused, not queued.
    assert client.post(f"/drafts/{draft.id}/review").status_code == 409

    release.set()

    deadline = time.monotonic() + 5
    while draft_store.get(draft.id).busy is not None and time.monotonic() < deadline:
        time.sleep(0.02)

    stored = draft_store.get(draft.id)

    assert stored.busy is None
    assert stored.review is not None


def test_an_unknown_or_malformed_id(draft_store, reviewer, synchronous):

    assert client.post("/drafts/0000000000000000/review").status_code == 404
    assert client.post("/drafts/not-an-id/review").status_code == 422
    assert client.post("/drafts/0123456789ABCDEF/review").status_code == 422


def test_a_busy_draft_is_not_reviewed(draft_store, reviewer, synchronous):

    draft = draft_store.save(create_draft())
    draft_store.claim(draft.id, "rewriting")

    response = client.post(f"/drafts/{draft.id}/review")

    assert response.status_code == 409
    assert draft_store.get(draft.id).busy == "rewriting"


def test_a_review_never_lands_on_content_edited_while_it_ran(draft_store, monkeypatch, synchronous):

    draft = draft_store.save(create_draft())

    class EditingLLM(FakeLLMClient):
        """A person's edit arriving while the model reads the old text."""

        def complete_json(self, system_prompt, user_prompt, max_retries=1):

            if not self.calls:
                draft_store.update(
                    draft.id,
                    lambda current: revise(current, DraftContent(title="Edited meanwhile", body="New [1]."), "edited"),
                )

            return super().complete_json(system_prompt, user_prompt, max_retries)

    install(monkeypatch, EditingLLM([ANSWER, CORRECTED]))

    assert client.post(f"/drafts/{draft.id}/review").status_code == 202

    stored = draft_store.get(draft.id)

    assert stored.content.title == "Edited meanwhile"
    assert stored.review is None
    assert "changed while it was being reviewed" in stored.error
    assert stored.busy is None


def test_an_unreachable_model_is_an_error_not_a_review(draft_store, monkeypatch, synchronous):

    install(monkeypatch, FakeLLMClient([LLMUnavailableError("llama3.2:3b unreachable after 2 attempt(s)")]))

    draft = draft_store.save(create_draft())

    assert client.post(f"/drafts/{draft.id}/review").status_code == 202

    stored = draft_store.get(draft.id)

    assert stored.review is None
    assert "unreachable" in stored.error
    assert stored.busy is None


def test_a_malformed_answer_is_still_a_review(draft_store, monkeypatch, synchronous):

    install(monkeypatch, FakeLLMClient([None, None]))

    draft = draft_store.save(create_draft())

    client.post(f"/drafts/{draft.id}/review")

    stored = draft_store.get(draft.id)

    assert stored.error is None
    assert stored.review.corrected is None
    assert stored.review.metrics["grammar"].score == 0.0


# ----------------------------------------------------------------------
# Accepting the correction
# ----------------------------------------------------------------------


def reviewed(**kwargs):

    draft = create_draft(**kwargs)
    draft.review = DraftReview(
        corrected=DraftContent(**CORRECTED),
        model="corrector-model",
        reviewed_at="2026-10-15T08:00:00+00:00",
    )

    return draft


def test_accepting_a_correction_is_a_corrected_revision_and_clears_the_review(draft_store):

    draft = draft_store.save(reviewed(status="approved"))

    response = client.post(f"/drafts/{draft.id}/accept-correction")

    assert response.status_code == 200

    body = response.json()

    assert body["content"] == CORRECTED
    assert body["review"] is None
    assert [revision["reason"] for revision in body["revisions"]] == ["generated", "corrected"]
    assert body["revisions"][-1]["model"] == "corrector-model"
    # The outgoing revision keeps the review of its own text.
    assert body["revisions"][0]["review"]["corrected"]["title"] == CORRECTED["title"]
    # What was approved was the old text.
    assert body["status"] == "draft"


def test_nothing_to_accept(draft_store):

    unreviewed = draft_store.save(create_draft())

    no_proposal = create_draft()
    no_proposal.review = DraftReview(reviewed_at="2026-10-15T08:00:00+00:00")
    draft_store.save(no_proposal)

    for draft in (unreviewed, no_proposal):
        response = client.post(f"/drafts/{draft.id}/accept-correction")
        assert response.status_code == 409
        assert draft_store.get(draft.id).content == draft.content


def test_a_busy_or_published_draft_is_not_corrected(draft_store):

    busy = draft_store.save(reviewed())
    draft_store.claim(busy.id, "reviewing")

    published = draft_store.save(reviewed(status="published"))

    for draft in (busy, published):
        assert client.post(f"/drafts/{draft.id}/accept-correction").status_code == 409
        assert draft_store.get(draft.id).content == draft.content


def test_accepting_on_an_unknown_draft(draft_store):

    assert client.post("/drafts/0000000000000000/accept-correction").status_code == 404
    assert client.post("/drafts/nope/accept-correction").status_code == 422


# ----------------------------------------------------------------------
# The key and the model
# ----------------------------------------------------------------------


def test_both_endpoints_take_the_api_key(draft_store, monkeypatch, synchronous):

    llm = FakeLLMClient([ANSWER, CORRECTED])
    install(monkeypatch, llm)

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    draft = draft_store.save(reviewed())

    assert client.post(f"/drafts/{draft.id}/review").status_code == 401
    assert client.post(f"/drafts/{draft.id}/accept-correction").status_code == 401

    assert llm.calls == []
    assert draft_store.get(draft.id).content == draft.content


def test_the_reviewer_uses_the_corrector_model_and_the_writers_timeout(monkeypatch):

    monkeypatch.setattr(container, "_draft_reviewer", None)
    monkeypatch.setattr(container, "_text_corrector", None)
    monkeypatch.setattr(settings, "CORRECTOR_LLM_MODEL", "corrector-model")
    monkeypatch.setattr(settings, "WRITER_LLM_TIMEOUT", 300.0)

    reviewer = container.get_draft_reviewer()

    assert reviewer.model == "corrector-model"
    assert reviewer.llm._client.timeout == 300.0
    # One inference/ client for /correct and the draft review.
    assert reviewer.sentiment_analyzer is container.get_text_corrector().sentiment_analyzer


def test_without_a_corrector_model_the_reviewer_uses_llm_model(monkeypatch):

    monkeypatch.setattr(container, "_draft_reviewer", None)
    monkeypatch.setattr(container, "_text_corrector", None)
    monkeypatch.setattr(settings, "CORRECTOR_LLM_MODEL", None)
    monkeypatch.setattr(settings, "LLM_MODEL", "the-default-model")

    assert container.get_draft_reviewer().model == "the-default-model"

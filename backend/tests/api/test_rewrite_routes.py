"""
/drafts/{id}/rewrite and /writing/targets (src/api/rewrite_routes.py).
Restoring an earlier revision is tests/api/test_draft_restore.py.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.container as container
from src.config.settings import settings
from src.config.thresholds import RewriteTargets
from src.main import app
from src.services.corrector.draft_reviewer import METRIC_ORDER
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY
from src.services.writer.draft_store import DraftStore
from src.services.writer.rewriter import MAX_EXTRA_INSTRUCTIONS_CHARS, MAX_ROUNDS
from tests.services.writer.rewrite_fakes import (
    GOOD_BODY,
    LOOSE,
    REVIEWER_MODEL,
    WRITER_MODEL,
    a_review,
    make_rewriter,
    review_answer,
    reviewed_draft,
    rewrite_answer,
)

client = TestClient(app)


@pytest.fixture
def synchronous(monkeypatch):
    """Background work runs in the request, so a test reads its result."""

    run = DraftStore.run_in_background

    def waiting(self, draft_id, busy, work, *, wait=False):
        return run(self, draft_id, busy, work, wait=True)

    monkeypatch.setattr(DraftStore, "run_in_background", waiting)


def install(monkeypatch, rewrites, reviews):

    rewriter = make_rewriter(rewrites, reviews)

    monkeypatch.setattr(container, "_draft_rewriter", rewriter)

    return rewriter


def rewrite(draft_id, **body):

    return client.post(f"/drafts/{draft_id}/rewrite", json=body)


# ----------------------------------------------------------------------
# Refusals
# ----------------------------------------------------------------------


def test_no_review_is_a_409_and_nothing_runs(draft_store, monkeypatch, synchronous):

    rewriter = install(monkeypatch, [rewrite_answer()], [])

    draft = draft_store.save(reviewed_draft())
    draft.review = None
    draft_store.save(draft)

    response = rewrite(draft.id)

    assert response.status_code == 409
    assert "Review the draft first" in response.json()["detail"]
    assert rewriter.writer.llm.calls == []
    assert draft_store.get(draft.id).busy is None


def test_a_published_or_busy_draft_is_not_rewritten(draft_store, monkeypatch, synchronous):

    rewriter = install(monkeypatch, [rewrite_answer()], [])

    published = draft_store.save(reviewed_draft(status="published"))

    busy = draft_store.save(reviewed_draft())
    draft_store.claim(busy.id, "reviewing")

    for draft in (published, busy):
        assert rewrite(draft.id).status_code == 409
        assert draft_store.get(draft.id).content == draft.content

    assert "unpublish" in rewrite(published.id).json()["detail"]
    assert draft_store.get(busy.id).busy == "reviewing"
    assert rewriter.writer.llm.calls == []


def test_an_unknown_or_malformed_id(draft_store, monkeypatch, synchronous):

    install(monkeypatch, [], [])

    assert rewrite("0000000000000000").status_code == 404
    assert rewrite("not-an-id").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"maxRounds": 0},
        {"maxRounds": MAX_ROUNDS + 1},
        {"instructions": "x" * (MAX_EXTRA_INSTRUCTIONS_CHARS + 1)},
        {"targets": {"seo": 120}},
        {"targets": {"clarity": 50}},
        {"rounds": 2},
    ],
)
def test_a_request_out_of_bounds_is_a_422(draft_store, monkeypatch, synchronous, body):

    rewriter = install(monkeypatch, [rewrite_answer()], [])

    draft = draft_store.save(reviewed_draft())

    assert rewrite(draft.id, **body).status_code == 422
    assert rewriter.writer.llm.calls == []


# ----------------------------------------------------------------------
# A rewrite
# ----------------------------------------------------------------------


def test_a_rewrite_is_a_rewritten_revision_with_its_own_review(draft_store, monkeypatch, synchronous):

    install(monkeypatch, [rewrite_answer()], [review_answer(90), None])

    draft = draft_store.save(reviewed_draft())

    response = rewrite(draft.id, targets=LOOSE)

    assert response.status_code == 202

    stored = draft_store.get(draft.id)

    assert stored.busy is None
    assert stored.error is None
    assert stored.content.body == GOOD_BODY
    assert [revision.reason for revision in stored.revisions] == ["generated", "rewritten"]
    assert stored.revisions[-1].model == WRITER_MODEL

    # Reviewed at once: the new text's scores, by the reviewer.
    assert list(stored.review.metrics) == list(METRIC_ORDER)
    assert stored.review.model == REVIEWER_MODEL
    # The text it replaced keeps the review it had.
    assert stored.revisions[0].review == draft.review


def test_the_202_answers_with_the_draft_busy(draft_store, monkeypatch):
    """Without `synchronous`: the work is started, not awaited."""

    import threading

    release = threading.Event()

    rewriter = install(monkeypatch, [rewrite_answer()], [review_answer(90), None])

    complete = rewriter.writer.complete

    def slow(*args, **kwargs):
        release.wait(5)
        return complete(*args, **kwargs)

    rewriter.writer.complete = slow

    draft = draft_store.save(reviewed_draft())

    response = rewrite(draft.id, targets=LOOSE)

    try:
        assert response.status_code == 202
        assert response.json()["busy"] == "rewriting"
        # A second step on a busy draft is refused, not queued.
        assert rewrite(draft.id).status_code == 409
    finally:
        release.set()

    import time

    deadline = time.monotonic() + 5
    while draft_store.get(draft.id).busy is not None and time.monotonic() < deadline:
        time.sleep(0.02)

    assert draft_store.get(draft.id).content.body == GOOD_BODY


def test_an_approved_draft_goes_back_to_draft(draft_store, monkeypatch, synchronous):

    install(monkeypatch, [rewrite_answer()], [review_answer(90), None])

    draft = draft_store.save(reviewed_draft(status="approved"))

    rewrite(draft.id, targets=LOOSE)

    assert draft_store.get(draft.id).status == "draft"


@pytest.mark.parametrize(
    "body, why",
    [
        ("Since 2015, 40 divers doubled the meadow [1], and fish counts rose with it [2].", "figures neither"),
        ("Since 2015 the meadow has doubled in size [1], and fish counts rose with it.", "no longer cites [2]"),
        ("Since 2015 the meadow has doubled in size [1]. The bay is now completely free of plastic pollution [2].", "moved [2]"),
    ],
    ids=["a figure from nowhere", "a dropped citation", "a moved citation"],
)
def test_a_rewrite_that_breaks_a_rule_is_not_kept(draft_store, monkeypatch, synchronous, body, why):

    rewriter = install(monkeypatch, [rewrite_answer(body)], [review_answer(90), None])

    draft = draft_store.save(reviewed_draft(status="approved"))

    assert rewrite(draft.id).status_code == 202

    stored = draft_store.get(draft.id)

    assert stored.content == draft.content
    assert stored.review == draft.review
    assert len(stored.revisions) == 1
    assert stored.status == "approved"
    assert stored.busy is None
    assert "not kept" in stored.error and why in stored.error
    # Not reviewed: nothing new to review.
    assert rewriter.reviewer.llm.calls == []


def test_an_unreachable_writing_model_is_an_error(draft_store, monkeypatch, synchronous):

    from src.services.llms import LLMUnavailableError

    install(monkeypatch, [LLMUnavailableError("down")], [])

    draft = draft_store.save(reviewed_draft())

    rewrite(draft.id)

    stored = draft_store.get(draft.id)

    assert stored.content == draft.content
    assert "could not be reached" in stored.error


# ----------------------------------------------------------------------
# Targets and rounds
# ----------------------------------------------------------------------


def test_the_rounds_stop_when_the_targets_are_met(draft_store, monkeypatch, synchronous):

    rewriter = install(
        monkeypatch,
        [rewrite_answer(), rewrite_answer(GOOD_BODY.replace("rose", "grew"))],
        [review_answer(90), None, review_answer(90), None],
    )

    draft = draft_store.save(reviewed_draft())

    rewrite(draft.id, targets=LOOSE, maxRounds=3)

    assert len(rewriter.writer.llm.calls) == 1
    assert len(draft_store.get(draft.id).revisions) == 2


def test_the_rounds_stop_at_max_rounds_when_the_targets_are_not(draft_store, monkeypatch, synchronous):

    rewriter = install(
        monkeypatch,
        [rewrite_answer(), rewrite_answer(GOOD_BODY.replace("rose", "grew")), rewrite_answer()],
        # Round 1's review has a round after it: no proposal is asked for.
        [review_answer(90, factConsistency=50), review_answer(90, factConsistency=60), None],
    )

    draft = draft_store.save(reviewed_draft())

    rewrite(draft.id, targets=LOOSE, maxRounds=2)

    stored = draft_store.get(draft.id)

    assert len(rewriter.writer.llm.calls) == 2
    assert [revision.reason for revision in stored.revisions] == ["generated", "rewritten", "rewritten"]
    assert stored.revisions[1].review.metrics["factConsistency"].score == 50
    assert stored.review.metrics["factConsistency"].score == 60
    assert stored.error is None


def test_an_unscored_metric_neither_passes_nor_fails(draft_store, monkeypatch, synchronous):

    # The review after the first round could not score hallucinationIndex;
    # every other metric is at 90. With a target of 100 on it, a 0 read as
    # a score would send the draft round again.
    rewriter = install(
        monkeypatch,
        [rewrite_answer(), rewrite_answer(GOOD_BODY.replace("rose", "grew"))],
        [review_answer(90, hallucinationIndex=None), None, review_answer(90), None],
    )

    draft = draft_store.save(reviewed_draft())

    rewrite(draft.id, targets={**LOOSE, "hallucinationIndex": 100}, maxRounds=2)

    stored = draft_store.get(draft.id)

    assert len(rewriter.writer.llm.calls) == 1
    assert stored.review.metrics["hallucinationIndex"].summary == UNAVAILABLE_SUMMARY


def test_target_overrides_are_honoured(draft_store, monkeypatch, synchronous):
    """
    At 90 every model metric meets its default target; with grammar's
    raised to 95, the same reviews leave it below and a second round runs.
    """

    def run(targets):

        rewriter = install(
            monkeypatch,
            [rewrite_answer(), rewrite_answer(GOOD_BODY.replace("rose", "grew"))],
            [review_answer(90), None, review_answer(90), None],
        )

        draft = draft_store.save(reviewed_draft(review=a_review(90, grammar=60)))

        rewrite(draft.id, targets=targets, maxRounds=2)

        return rewriter

    defaults = run(LOOSE)
    raised = run({**LOOSE, "grammar": 95})

    assert len(defaults.writer.llm.calls) == 1
    assert len(raised.writer.llm.calls) == 2

    # And the rewrite is told the target it is held to.
    assert "- grammar: 60, target 95." in raised.writer.llm.calls[0][1]
    assert "- grammar: 60, target 80." in defaults.writer.llm.calls[0][1]


def test_the_extra_instructions_reach_the_model(draft_store, monkeypatch, synchronous):

    rewriter = install(monkeypatch, [rewrite_answer()], [review_answer(90), None])

    draft = draft_store.save(reviewed_draft())

    rewrite(draft.id, instructions="  Shorter, and lead with the fish.  ", targets=LOOSE)

    prompt = rewriter.writer.llm.calls[0][1]

    assert "Shorter, and lead with the fish." in prompt
    assert draft.instructions in prompt
    # The draft's own instructions are the writer's record, not changed.
    assert draft_store.get(draft.id).instructions == draft.instructions


# ----------------------------------------------------------------------
# The targets endpoint
# ----------------------------------------------------------------------


def test_the_targets_endpoint_answers_with_the_defaults_under_the_metric_keys():

    response = client.get("/writing/targets")

    assert response.status_code == 200

    body = response.json()

    assert set(body["targets"]) == set(METRIC_ORDER)
    assert body["targets"] == RewriteTargets().by_metric()
    assert body["rounds"] == {"default": 1, "max": MAX_ROUNDS}
    assert body["maxInstructionsChars"] == MAX_EXTRA_INSTRUCTIONS_CHARS
    assert body["unscoredSummary"] == UNAVAILABLE_SUMMARY


def test_the_targets_endpoint_takes_the_key(monkeypatch):

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.get("/writing/targets").status_code == 401
    assert client.get("/writing/targets", headers={"X-API-Key": "secret"}).status_code == 200


def test_the_targets_are_not_under_drafts():
    """GET /drafts/{draft_id} answers first, on its id pattern - why the path is /writing/targets."""

    assert client.get("/drafts/targets").status_code == 422


def test_rewrite_takes_the_api_key(draft_store, monkeypatch, synchronous):

    rewriter = install(monkeypatch, [rewrite_answer()], [review_answer(90), None])

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    draft = draft_store.save(reviewed_draft())

    assert rewrite(draft.id).status_code == 401
    assert rewriter.writer.llm.calls == []
    assert draft_store.get(draft.id).content == draft.content


# ----------------------------------------------------------------------
# The models
# ----------------------------------------------------------------------


def test_the_rewriter_writes_with_the_writers_model_and_reviews_with_the_reviewer(monkeypatch):

    for name in ("_draft_rewriter", "_article_writer", "_draft_reviewer", "_text_corrector"):
        monkeypatch.setattr(container, name, None)

    monkeypatch.setattr(settings, "WRITER_LLM_MODEL", "writer-model")
    monkeypatch.setattr(settings, "CORRECTOR_LLM_MODEL", "corrector-model")
    monkeypatch.setattr(settings, "WRITER_LLM_TIMEOUT", 300.0)

    rewriter = container.get_draft_rewriter()

    assert rewriter.writer is container.get_article_writer()
    assert rewriter.reviewer is container.get_draft_reviewer()
    assert rewriter.model == "writer-model"
    assert rewriter.writer.llm._client.timeout == 300.0
    assert rewriter.reviewer.model == "corrector-model"

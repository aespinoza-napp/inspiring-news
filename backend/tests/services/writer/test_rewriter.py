"""
The rewrite stage (src/services/writer/rewriter.py): the targets, the
prompt, the checks a rewrite must pass to be kept, and the rounds.
"""

import pytest

from src.config.thresholds import RewriteTargetOverrides, RewriteTargets
from src.models.writer.draft import DraftContent, DraftFactCheck, DraftSource
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY
from src.services.llms import LLMUnavailableError
from src.services.writer.article_writer import CLOSED_WORLD_RULES, WriterError
from src.services.writer.draft_store import revise
from src.services.writer.rewriter import (
    MAX_ROUNDS,
    REWRITE_SYSTEM_PROMPT,
    RewriteRefused,
    RewriteRejected,
    StaleRewrite,
    below_target,
    guidance_lines,
    standings,
)
from tests.factories import create_draft
from tests.services.writer.rewrite_fakes import (
    GOOD_BODY,
    LOOSE,
    REVIEWER_MODEL,
    WRITER_MODEL,
    a_review,
    content,
    make_rewriter,
    review_answer,
    reviewed_draft,
    rewrite_answer,
)

LOOSE_TARGETS = RewriteTargets.resolve(RewriteTargetOverrides(**LOOSE))


# ----------------------------------------------------------------------
# The targets
# ----------------------------------------------------------------------


def test_a_metric_is_met_below_or_not_scored():

    review = a_review(90, factConsistency=60, hallucinationIndex=None)

    by_key = {standing.key: standing for standing in standings(review, RewriteTargets())}

    assert by_key["factConsistency"].standing == "below"
    assert by_key["factConsistency"].score == 60
    assert by_key["factConsistency"].target == 85

    assert by_key["grammar"].standing == "met"

    unscored = by_key["hallucinationIndex"]
    assert unscored.standing == "unscored"
    assert unscored.score is None
    assert unscored.summary == UNAVAILABLE_SUMMARY


def test_an_unscored_metric_is_never_below_target_whatever_its_zero():
    """
    The 0 an unscored metric carries is not a judgement: read as one it
    would fail every target, and a target of 0 would "pass" it.
    """

    review = a_review(90, hallucinationIndex=None)

    assert below_target(review, RewriteTargets()) == []

    zero = RewriteTargets(hallucination_index=0)
    standing = next(item for item in standings(review, zero) if item.key == "hallucinationIndex")

    assert standing.standing == "unscored"


def test_targets_are_judged_in_the_order_a_person_reads_them():

    keys = [standing.key for standing in standings(a_review(), RewriteTargets())]

    assert keys == [
        "title", "subtitle", "grammar", "factConsistency", "coverageVerification",
        "seo", "readability", "hallucinationIndex", "style",
    ]


def test_truth_is_held_to_a_stricter_target_than_seo():

    targets = RewriteTargets()

    assert targets.hallucination_index > targets.seo
    assert targets.fact_consistency > targets.seo
    # One citation to no source costs factConsistency 20 of its ceiling
    # (draft_reviewer.DANGLING_CITATION_PENALTY): one alone fails it.
    assert 100 - 20 < targets.fact_consistency


def test_targets_speak_the_reviews_metric_keys():

    overrides = RewriteTargetOverrides.model_validate({"factConsistency": 95, "hallucinationIndex": 99})

    targets = RewriteTargets.resolve(overrides)

    assert targets.by_metric()["factConsistency"] == 95
    assert targets.by_metric()["hallucinationIndex"] == 99
    assert targets.by_metric()["seo"] == RewriteTargets().seo


def test_a_target_outside_0_to_100_or_an_unknown_one_is_refused():

    with pytest.raises(ValueError):
        RewriteTargetOverrides.model_validate({"seo": 101})

    with pytest.raises(ValueError):
        RewriteTargetOverrides.model_validate({"clarity": 50})


# ----------------------------------------------------------------------
# The prompt
# ----------------------------------------------------------------------


def test_the_rewrite_is_held_to_the_writers_own_rules():

    assert CLOSED_WORLD_RULES in REWRITE_SYSTEM_PROMPT
    assert "Keep every citation [n] with the statement it supports" in REWRITE_SYSTEM_PROMPT
    assert "No new figures" in REWRITE_SYSTEM_PROMPT


def test_the_prompt_carries_the_sources_the_checks_the_instructions_and_the_failing_metrics():

    draft = reviewed_draft(
        review=a_review(90, factConsistency=50, seo=40),
        fact_checks=[
            DraftFactCheck(claim="The meadow has doubled in area since 2015.", verdict="TRUE"),
            DraftFactCheck(claim="The bay is free of plastic.", verdict="FALSE"),
        ],
    )

    rewriter = make_rewriter([rewrite_answer()], [review_answer(), None])

    rewriter.rewrite(draft, instructions="Lead with the fish.")

    system, prompt = rewriter.writer.llm.calls[0]

    assert system == REWRITE_SYSTEM_PROMPT

    # The draft's own sources, numbered as it cites them.
    assert "[1] the analysed article" in prompt
    assert "The restored meadow covered twice its 2015 area." in prompt
    assert "[2] related news" in prompt

    # The draft's instructions and this rewrite's, both.
    assert draft.instructions in prompt
    assert "Lead with the fish." in prompt

    # What fell short, with its score against its target.
    assert "- factConsistency: 50, target 85." in prompt
    assert "- seo: 40, target 60." in prompt
    assert "factConsistency issue." in prompt
    # A metric that met its target is not something to fix.
    assert "grammar issue." not in prompt

    # The claims not to state, last - as the writer's prompt ends.
    assert 'Do NOT state these as fact: "The bay is free of plastic."' in prompt
    assert draft.content.body in prompt


def test_with_every_target_met_the_rewrite_is_guided_by_the_instructions_and_the_notes():

    lines = guidance_lines(a_review(95), RewriteTargets())

    assert lines[0].startswith("Every scored metric meets its target")
    assert any("grammar issue." in line for line in lines)


def test_the_issues_of_an_unscored_metric_still_guide_the_rewrite():
    """They came from the checks that need no model, which are certain."""

    review = a_review(90, hallucinationIndex=None)
    review.metrics["hallucinationIndex"].issues = ["States a fact and cites no source: “40 divers”"]

    lines = guidance_lines(review, RewriteTargets())

    assert any("reviewer gave no score" in line for line in lines)
    assert any("40 divers" in line for line in lines)


def test_no_review_no_rewrite():

    rewriter = make_rewriter([rewrite_answer()], [])

    with pytest.raises(RewriteRefused):
        rewriter.rewrite(create_draft())

    assert rewriter.writer.llm.calls == []


def test_the_rewrite_uses_the_writers_model_and_its_cap():

    rewriter = make_rewriter([rewrite_answer()], [])

    rewritten = rewriter.rewrite(reviewed_draft())

    assert rewritten.model == WRITER_MODEL
    assert rewriter.writer.llm.max_tokens == [4096]


def test_an_unreachable_model_is_the_writers_error():

    rewriter = make_rewriter([LLMUnavailableError("down")], [])

    with pytest.raises(WriterError, match="could not be reached"):
        rewriter.rewrite(reviewed_draft())


# ----------------------------------------------------------------------
# What is kept
# ----------------------------------------------------------------------


def read(answer, draft=None):

    return make_rewriter([], []).read(answer, draft or reviewed_draft())


def test_a_faithful_rewrite_is_kept_and_repaired_like_the_writers_answer():

    rewritten = read(rewrite_answer(
        "# Seagrass meadows double in the bay\n\n"
        "*Since 2015* the meadow has doubled in size [1], and fish counts rose with it [2, 9].",
        title="Seagrass meadows double in the bay [1]",
    ))

    # The title repeated as a heading dropped, italics and a citation
    # past the two sources removed, no citation in the title.
    assert rewritten.content.body == GOOD_BODY
    assert rewritten.content.title == "Seagrass meadows double in the bay"


def test_a_figure_from_nowhere_is_not_kept():

    with pytest.raises(RewriteRejected, match="figures neither the draft nor its sources have: 40"):
        read(rewrite_answer("Since 2015, 40 divers doubled the meadow [1], and fish counts rose with it [2]."))


def test_a_figure_put_right_from_its_source_is_kept():
    """
    What a rewrite can do and a review's proposal cannot: the proposal
    never saw the sources, so a figure the draft lacks is refused there.
    """

    draft = reviewed_draft(
        content=content("Divers replanted 30 hectares in 2015 [1], and fish counts rose with it [2]."),
        sources=[
            DraftSource(
                url="https://example.org/seagrass",
                origin="analysed",
                excerpt="Divers replanted 12 hectares in 2015, and the meadow doubled.",
            ),
            DraftSource(
                url="https://example.com/fish",
                origin="related",
                excerpt="Surveys found more juvenile fish in the restored area.",
            ),
        ],
    )

    rewritten = read(
        rewrite_answer("Divers replanted 12 hectares in 2015 [1], and fish counts rose with it [2]."),
        draft,
    )

    assert "12 hectares" in rewritten.content.body


def test_a_dropped_citation_is_not_kept():

    with pytest.raises(RewriteRejected, match=r"no longer cites \[2\]"):
        read(rewrite_answer("Since 2015 the meadow has doubled in size [1], and fish counts rose with it."))


def test_a_moved_citation_is_not_kept():

    with pytest.raises(RewriteRejected, match=r"moved \[2\]"):
        read(rewrite_answer(
            "Since 2015 the meadow has doubled in size [1]. "
            "The bay is now completely free of plastic pollution [2]."
        ))


def test_a_citation_added_where_the_source_says_it_is_kept():
    """The fix for a sentence the review found citing nothing."""

    draft = reviewed_draft(content=content(
        "The meadow has doubled since 2015 [1], and fish counts rose with it [2]. "
        "Surveys found more juvenile fish in the restored area."
    ))

    rewritten = read(
        rewrite_answer(
            "The meadow has doubled since 2015 [1], and fish counts rose with it [2]. "
            "Surveys found more juvenile fish in the restored area [2]."
        ),
        draft,
    )

    assert rewritten.content.body.endswith("restored area [2].")


def test_a_citation_added_where_the_source_does_not_say_it_is_not_kept():

    draft = reviewed_draft(content=content(
        "The meadow has doubled since 2015 [1], and fish counts rose with it [2]. "
        "Volunteers from the town planted the shoots by hand."
    ))

    with pytest.raises(RewriteRejected, match=r"moved \[2\]"):
        read(
            rewrite_answer(
                "The meadow has doubled since 2015 [1], and fish counts rose with it [2]. "
                "Volunteers from the town planted the shoots by hand [2]."
            ),
            draft,
        )


def test_a_rewrite_in_another_language_is_not_kept():

    with pytest.raises(RewriteRejected, match="not in English"):
        read(rewrite_answer(
            "Desde 2015 la pradera se ha duplicado [1], y el número de peces creció con ella [2]."
        ))


def test_an_unusable_answer_or_the_same_text_is_not_kept():

    with pytest.raises(RewriteRejected, match="usable title and body"):
        read(None)

    with pytest.raises(RewriteRejected, match="usable title and body"):
        read({"title": "Only a title"})

    draft = reviewed_draft()

    with pytest.raises(RewriteRejected, match="identical"):
        read(draft.content.model_dump(), draft)


def test_a_citation_the_draft_had_to_no_source_is_not_counted_as_dropped():
    """The writer's repair removes it; the rewrite is not blamed for that."""

    draft = reviewed_draft(content=content(
        "The meadow has doubled since 2015 [1], and fish counts rose with it [2][7]."
    ))

    rewritten = read(rewrite_answer(GOOD_BODY), draft)

    assert rewritten.content.body == GOOD_BODY


# ----------------------------------------------------------------------
# The rounds
# ----------------------------------------------------------------------


def test_a_round_is_a_rewritten_revision_with_its_own_review(draft_store):

    draft = draft_store.save(reviewed_draft(status="approved"))
    first_review = draft.review

    rewriter = make_rewriter([rewrite_answer()], [review_answer(), None])

    rewriter.run(draft_store, draft.id, LOOSE_TARGETS)

    stored = draft_store.get(draft.id)

    assert [revision.reason for revision in stored.revisions] == ["generated", "rewritten"]
    assert stored.revisions[-1].model == WRITER_MODEL
    assert stored.content.body == GOOD_BODY

    # The new text's own review, by the reviewer.
    assert stored.review is not None
    assert stored.review.model == REVIEWER_MODEL
    assert stored.review.metrics["factConsistency"].score == 90
    # The older text keeps the review of the older text.
    assert stored.revisions[0].review == first_review

    # What was approved was the older text.
    assert stored.status == "draft"


def test_the_rounds_stop_once_the_targets_are_met(draft_store):

    draft = draft_store.save(reviewed_draft())

    rewriter = make_rewriter(
        [rewrite_answer(), rewrite_answer(GOOD_BODY.replace("rose", "grew"))],
        [review_answer(90), None, review_answer(90), None],
    )

    rewriter.run(draft_store, draft.id, LOOSE_TARGETS, rounds=3)

    stored = draft_store.get(draft.id)

    assert len(rewriter.writer.llm.calls) == 1
    assert [revision.reason for revision in stored.revisions] == ["generated", "rewritten"]


def test_the_rounds_stop_at_the_limit_when_the_targets_are_not_met(draft_store):

    draft = draft_store.save(reviewed_draft())

    second = GOOD_BODY.replace("rose", "grew")

    rewriter = make_rewriter(
        [rewrite_answer(), rewrite_answer(second), rewrite_answer(GOOD_BODY)],
        [review_answer(90, factConsistency=60), None, review_answer(90, factConsistency=70), None],
    )

    rewriter.run(draft_store, draft.id, LOOSE_TARGETS, rounds=2)

    stored = draft_store.get(draft.id)

    assert len(rewriter.writer.llm.calls) == 2
    assert [revision.reason for revision in stored.revisions] == ["generated", "rewritten", "rewritten"]
    # Every revision keeps the review of its own text.
    assert stored.revisions[1].review.metrics["factConsistency"].score == 60
    assert stored.review.metrics["factConsistency"].score == 70
    assert stored.content.body == second

    # The second round was guided by the first round's review.
    assert "- factConsistency: 60, target 85." in rewriter.writer.llm.calls[1][1]


def test_more_rounds_than_the_cap_are_not_run(draft_store):
    """The request refuses more (test_rewrite_routes.py); the service holds the cap too."""

    draft = draft_store.save(reviewed_draft())

    bodies = [GOOD_BODY, GOOD_BODY.replace("rose", "grew"), GOOD_BODY.replace("rose", "climbed"), GOOD_BODY.replace("rose", "went up")]

    rewriter = make_rewriter(
        [rewrite_answer(body) for body in bodies],
        [item for _ in bodies for item in (review_answer(90, factConsistency=10), None)],
    )

    rewriter.run(draft_store, draft.id, LOOSE_TARGETS, rounds=MAX_ROUNDS + 5)

    assert len(rewriter.writer.llm.calls) == MAX_ROUNDS


def test_an_unscored_metric_does_not_send_the_draft_round_again(draft_store):

    draft = draft_store.save(reviewed_draft())

    rewriter = make_rewriter(
        [rewrite_answer(), rewrite_answer(GOOD_BODY.replace("rose", "grew"))],
        # hallucinationIndex left out of the answer: unscored, its 0 no verdict.
        [review_answer(90, hallucinationIndex=None), None, review_answer(90), None],
    )

    rewriter.run(draft_store, draft.id, LOOSE_TARGETS, rounds=3)

    stored = draft_store.get(draft.id)

    assert len(rewriter.writer.llm.calls) == 1
    assert stored.review.metrics["hallucinationIndex"].summary == UNAVAILABLE_SUMMARY


def test_a_rewrite_scoring_worse_is_still_kept_with_its_review(draft_store):

    draft = draft_store.save(reviewed_draft(review=a_review(80, factConsistency=70)))

    rewriter = make_rewriter([rewrite_answer()], [review_answer(30), None])

    rewriter.run(draft_store, draft.id, LOOSE_TARGETS)

    stored = draft_store.get(draft.id)

    assert stored.content.body == GOOD_BODY
    assert stored.review.metrics["grammar"].score == 30
    # The better-scored text is in the history, to go back to.
    assert stored.revisions[0].review.metrics["grammar"].score == 80


def test_a_rejected_first_round_leaves_the_draft_as_it_was(draft_store):

    draft = draft_store.save(reviewed_draft(status="approved"))

    rewriter = make_rewriter([rewrite_answer("Since 2015 the meadow has doubled in size [1].")], [])

    with pytest.raises(RewriteRejected, match=r"no longer cites \[2\].*keeps its current text and review"):
        rewriter.run(draft_store, draft.id, LOOSE_TARGETS)

    stored = draft_store.get(draft.id)

    assert stored.content == draft.content
    assert stored.review == draft.review
    assert len(stored.revisions) == 1
    # Nothing changed, so nothing to approve again.
    assert stored.status == "approved"


def test_a_rejected_later_round_keeps_the_earlier_rounds(draft_store):

    draft = draft_store.save(reviewed_draft())

    rewriter = make_rewriter(
        [rewrite_answer(), rewrite_answer("Since 2015, 40 divers doubled the meadow [1], and fish rose [2].")],
        [review_answer(90, factConsistency=60), None],
    )

    with pytest.raises(RewriteRejected, match="Round 2 of 2: .*keeps round 1's rewrite"):
        rewriter.run(draft_store, draft.id, LOOSE_TARGETS, rounds=2)

    stored = draft_store.get(draft.id)

    assert stored.content.body == GOOD_BODY
    assert stored.review.metrics["factConsistency"].score == 60


def test_a_rewrite_never_lands_on_text_changed_while_it_ran(draft_store):

    draft = draft_store.save(reviewed_draft())

    rewriter = make_rewriter([rewrite_answer()], [])

    complete = rewriter.writer.complete

    def edited_meanwhile(*args, **kwargs):
        draft_store.update(draft.id, lambda current: revise(current, content("Edited meanwhile [1][2]."), "edited"))
        return complete(*args, **kwargs)

    rewriter.writer.complete = edited_meanwhile

    with pytest.raises(StaleRewrite):
        rewriter.run(draft_store, draft.id, LOOSE_TARGETS)

    stored = draft_store.get(draft.id)

    assert stored.content.body == "Edited meanwhile [1][2]."
    assert [revision.reason for revision in stored.revisions] == ["generated", "edited"]


def test_a_failed_review_of_the_new_text_says_the_rewrite_was_kept(draft_store):

    draft = draft_store.save(reviewed_draft())

    rewriter = make_rewriter([rewrite_answer()], [LLMUnavailableError("reviewer down")])

    with pytest.raises(RuntimeError, match="was kept, but its review failed"):
        rewriter.run(draft_store, draft.id, LOOSE_TARGETS)

    stored = draft_store.get(draft.id)

    assert stored.content.body == GOOD_BODY
    assert stored.review is None

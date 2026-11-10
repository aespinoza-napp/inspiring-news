"""
The grounding index (hallucinationIndex) of a draft review, 2026-11-10:

- it drops only for a statement no source says;
- a statement a source says but the draft does not cite is a citation
  issue, under factConsistency;
- the model's score cannot contradict its own summary: when it does, the
  score follows the automatic check and the model's number is kept.

The New Heart draft (tests/fixtures/drafts/new_heart.json) is the case
that showed all three: it cited nothing, every factual sentence of it is
in its analysed article, and the model scored it 0 while writing "Todas
las afirmaciones del texto están respaldadas por fuentes."
"""

import json
from pathlib import Path

from src.models.corrector.correction_metric import CorrectionMetric
from src.models.writer.draft import DraftContent, DraftFactCheck, DraftSource
from src.services.corrector import grounding
from src.services.corrector.draft_reviewer import (
    CONTRADICTED_BELOW,
    clean_summary,
    follow_the_check,
    source_texts,
)
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY
from tests.factories import create_draft
from tests.services.corrector.test_draft_review import answer, proposal_for, reviewer

NEW_HEART = Path(__file__).resolve().parents[2] / "fixtures" / "drafts" / "new_heart.json"


def new_heart():

    data = json.loads(NEW_HEART.read_text(encoding="utf-8"))

    draft = create_draft(
        language=data["language"],
        content=DraftContent(**data["content"]),
        sources=[DraftSource(**source) for source in data["sources"]],
        fact_checks=[DraftFactCheck.model_validate(check) for check in data["factChecks"]],
    )

    return draft, data["modelAnswer"]


# ----------------------------------------------------------------------
# The New Heart draft
# ----------------------------------------------------------------------


def test_the_new_heart_draft_scores_100():

    draft, model_answer = new_heart()

    review = reviewer(answer(score=90, **model_answer), proposal_for(draft.content)).review(draft)

    metric = review.metrics["hallucinationIndex"]

    assert metric.score == 100.0
    # The model's 0 is kept, and the summary says why it was set aside.
    assert metric.reported == 0.0
    assert "contradicts its own summary" in metric.summary
    assert not any("no source says it" in issue for issue in metric.issues)


def test_the_new_heart_drafts_uncited_sentences_are_citation_issues():

    draft, model_answer = new_heart()

    review = reviewer(answer(score=90, **model_answer), proposal_for(draft.content)).review(draft)

    issues = review.metrics["factConsistency"].issues

    added = [issue for issue in issues if issue.startswith("Cites no source, though [1] says it")]

    assert len(added) == 2
    assert any("New Heart" in issue for issue in added)
    assert any("2024" in issue for issue in added)


# ----------------------------------------------------------------------
# What lowers the index
# ----------------------------------------------------------------------


def test_only_a_statement_no_source_says_lowers_the_index():

    draft = create_draft(content=DraftContent(
        title="Seagrass meadows return to the bay in Girona",
        subtitle="Ten years of replanting doubled the meadow's area",
        body=(
            "The meadow has doubled since 2015 [1]. "
            "The restored meadow covered twice its 2015 area, the report found. "
            "In March 2024 the council said 40 divers joined the replanting."
        ),
    ))

    review = reviewer(answer(score=95), proposal_for(draft.content)).review(draft)

    metric = review.metrics["hallucinationIndex"]

    # Three factual sentences: one cited, one in source [1] uncited, one in
    # no source. Only the last counts against the index.
    assert metric.score == round(100 * 2 / 3, 1)
    assert any("no source says it" in issue and "40 divers" in issue for issue in metric.issues)
    assert not any("twice its 2015 area" in issue for issue in metric.issues)

    citation = review.metrics["factConsistency"].issues
    assert any("[1] says it" in issue and "twice its 2015 area" in issue for issue in citation)


def test_a_figure_the_source_does_not_have_is_not_in_the_source():

    found = grounding.in_source(
        "The restored meadow covered three times its 2015 area by 2023, the report found.",
        "The restored meadow covered three times its 2015 area.",
        "en",
    )

    assert not found


def test_without_the_sources_text_every_uncited_sentence_is_unsupported():

    draft = create_draft(content=DraftContent(
        title="t",
        subtitle="s",
        body="The restored meadow covered twice its 2015 area, the report found.",
    ))

    found = grounding.check(draft.content.body, len(draft.sources), [], grounding.WRITING_LEXICONS["en"])

    assert found.unsupported == found.uncited
    assert found.uncited_present == []

    with_texts = grounding.check(
        draft.content.body, len(draft.sources), [], grounding.WRITING_LEXICONS["en"], source_texts(draft)
    )

    assert with_texts.unsupported == []
    assert [number for _, number in with_texts.uncited_present] == [1]


# ----------------------------------------------------------------------
# The score and the summary
# ----------------------------------------------------------------------


def test_clean_summaries_in_english_and_spanish():

    assert clean_summary("Todas las afirmaciones del texto están respaldadas por fuentes.")
    assert clean_summary("All factual statements are supported by the cited sources.")
    assert clean_summary("No unsupported claims were found.")
    # An exception named is not a clean summary.
    assert not clean_summary("All statements are supported, except the figure for 2024.")
    assert not clean_summary("La mayoría de las afirmaciones están respaldadas, aunque hay ambigüedades.")
    assert not clean_summary("The draft invents a figure.")


def test_a_low_score_under_a_clean_summary_follows_the_check():

    metric = CorrectionMetric(score=10.0, summary="All claims are supported by the sources.")

    followed = follow_the_check(metric, 80.0)

    assert followed.score == 80.0
    assert followed.reported == 10.0


def test_a_score_that_agrees_with_its_summary_is_left_alone():

    clean_and_high = CorrectionMetric(score=CONTRADICTED_BELOW + 30, summary="All claims are supported.")
    flagged_and_low = CorrectionMetric(score=10.0, summary="The draft invents a figure.")

    assert follow_the_check(clean_and_high, 100.0) == clean_and_high
    assert follow_the_check(flagged_and_low, 100.0) == flagged_and_low


def test_the_check_never_lowers_the_models_score_and_never_touches_an_unavailable_metric():

    # The check is a floor for the model's score here, never a cut: a low
    # automatic score is applied as a ceiling elsewhere, with its reason.
    low_check = CorrectionMetric(score=20.0, summary="All claims are supported.")
    unavailable = CorrectionMetric(score=0.0, summary=UNAVAILABLE_SUMMARY)

    assert follow_the_check(low_check, 10.0) == low_check
    assert follow_the_check(unavailable, 100.0) == unavailable

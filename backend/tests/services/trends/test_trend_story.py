"""
Writing and reviewing a story from a trend (docs/decisions/trends.md, "The
story"): what the writer is told, and what the review holds the draft to.
"""

from src.config.lexicons import writing_lexicon_for
from src.models.corrector.correction_metric import CorrectionMetric
from src.models.writer.draft import DraftAngle, DraftContent, DraftSource, DraftTrend
from src.services.corrector.draft_reviewer import apply_angle_check
from src.services.writer.article_writer import CLOSED_WORLD_RULES, user_prompt
from src.services.writer.analysed_article import AnalysedArticle
from tests.factories import create_draft

ARTICLE = AnalysedArticle(
    id="0123456789abcdef", url="https://whyy.org/articles/microplastics", headline="Princeton alumni remove microplastics",
    lead="A filter removes microplastics.", language="en", topic=None, published_at=None,
    source_name="WHYY", domain="whyy.org",
)

CLAIM = "The filtration system removed 90 percent of microplastics from Atlantic City wastewater."

SOURCES = [
    DraftSource(url=ARTICLE.url, title="Princeton alumni", domain="whyy.org", origin="analysed", excerpt="x"),
    DraftSource(url="https://related.example/a", title="Related", domain="related.example", origin="related", excerpt="x"),
    DraftSource(url="https://nj.example/filter", title="Filter", domain="nj.example", origin="angle", excerpt="x"),
    DraftSource(url="https://acua.example/report", title="Report", domain="acua.example", origin="angle", excerpt="x"),
]


def trend(kept: bool = True) -> DraftTrend:
    return DraftTrend(
        id="t1", name="Princeton alumni remove microplastics", signal="uplifting_news",
        signal_name="r/UpliftingNews · top of the day",
        angles=[DraftAngle(question="Does it work at scale?", claim=CLAIM, kept=kept,
                           source_urls=["https://nj.example/filter", "https://acua.example/report"])],
    )


# ----------------------------------------------------------------------
# What the writer is told
# ----------------------------------------------------------------------


def test_the_writer_is_told_the_trend_never_as_evidence_and_the_confirmed_angle_with_its_sources():

    prompt = user_prompt(ARTICLE, SOURCES, [], "en", "", [], trend())

    assert 'THE TREND: this story was found through what is trending, "Princeton alumni remove microplastics"' in prompt
    assert "Popularity proves nothing: never use it as evidence" in prompt
    assert f'1. Does it work at scale? - "{CLAIM}" Its sources: [3][4].' in prompt
    assert "or none" in prompt
    # The angle sources are listed under their own label.
    assert "[3] a source behind a confirmed constructive angle" in prompt


def test_without_a_confirmed_angle_the_writer_is_told_to_add_no_bright_side():

    prompt = user_prompt(ARTICLE, SOURCES[:2], [], "en", "", [], trend(kept=False))

    assert "No constructive angle was confirmed" in prompt
    assert "add no bright side they do not support" in prompt
    assert "CONFIRMED CONSTRUCTIVE ANGLES" not in prompt


def test_a_draft_no_trend_brought_is_told_nothing_of_trends():

    assert "TREND" not in user_prompt(ARTICLE, SOURCES[:2], [], "en", "", [])


def test_the_closed_world_rules_are_the_same_for_a_trend():
    """An angle is a source like any other: rule 1 still forbids anything the sources do not say."""

    assert "Closed world. Use only the numbered SOURCES and the FACT-CHECKS." in CLOSED_WORLD_RULES


# ----------------------------------------------------------------------
# What the review holds it to
# ----------------------------------------------------------------------


def metrics() -> dict:
    return {
        "factConsistency": CorrectionMetric(score=90, summary="ok", issues=[]),
        "coverageVerification": CorrectionMetric(score=60, summary="ok", issues=[]),
    }


def draft_with(body: str, kept: bool = True):
    draft = create_draft()
    draft.sources = list(SOURCES)
    draft.content = DraftContent(title="Microplastics", body=body)
    draft.trend = trend(kept)
    return draft


LEXICON = writing_lexicon_for("en")


def test_the_angle_stated_with_its_own_sources_raises_nothing():

    found = metrics()
    apply_angle_check(found, draft_with(f"Graduates built a filter [1]. {CLAIM[:-1]} [3]."), LEXICON)

    assert found["factConsistency"].issues == [] and found["coverageVerification"].issues == []


def test_the_angle_stated_uncited_or_on_another_source_is_an_issue():

    uncited = metrics()
    apply_angle_check(uncited, draft_with(f"Graduates built a filter [1]. {CLAIM}"), LEXICON)

    elsewhere = metrics()
    apply_angle_check(elsewhere, draft_with(f"Graduates built a filter [1]. {CLAIM[:-1]} [2]."), LEXICON)

    assert "States a confirmed angle's claim and cites nothing; its sources are [3][4]" in uncited["factConsistency"].issues[0]
    assert "cites [2], not its sources [3][4]" in elsewhere["factConsistency"].issues[0]
    # Issues, not a cap: the score is the model's.
    assert uncited["factConsistency"].score == 90


def test_taking_no_confirmed_angle_is_noted_not_penalised():

    found = metrics()
    apply_angle_check(found, draft_with("Graduates built a filter in New Jersey, the outlet reported [1]."), LEXICON)

    assert "takes none of the confirmed constructive angles (sources [3][4])" in found["coverageVerification"].issues[0]
    assert found["coverageVerification"].score == 60


def test_a_draft_with_no_kept_angle_is_not_checked():

    found = metrics()
    apply_angle_check(found, draft_with(f"{CLAIM}", kept=False), LEXICON)

    assert found["factConsistency"].issues == [] and found["coverageVerification"].issues == []

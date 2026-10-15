"""
The corrector's review of a draft (src/services/corrector/draft_reviewer.py):
nine metrics grounded in what the writer was given, and a proposed
correction checked before a person is offered it.
"""

from typing import get_args

import pytest
import textstat

from src.config.lexicons import (
    CATALAN,
    LEXICONS,
    WRITING_LEXICONS,
    UnsupportedWritingLanguage,
    writing_lexicon_for,
)
from src.models.corrector.correction_metric import CorrectionMetric
from src.models.nlp.sentiment_result import SentimentResult
from src.models.writer.draft import DraftContent, DraftFactCheck, DraftSource, Language
from src.processors.nlp.quality import QualityAnalyzer, _TEXTSTAT_LOCK
from src.services.corrector import draft_language, grounding
from src.services.corrector.draft_reviewer import (
    METRIC_ORDER,
    REVIEW_SYSTEM_PROMPT,
    DraftReviewer,
    correction_prompt,
    read_proposal,
    review_prompt,
)
from src.services.corrector.text_corrector import SYSTEM_PROMPT, UNAVAILABLE_SUMMARY, TextCorrector
from src.services.llms import LLMUnavailableError
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

LLM_KEYS = ("title", "subtitle", "grammar", "factConsistency", "seo", "hallucinationIndex", "style")


def answer(score=90, **overrides):
    """A well-formed review answer: every metric at `score`, no issues."""

    metrics = {key: {"score": score, "summary": "Fine.", "issues": []} for key in LLM_KEYS}
    metrics.update(overrides)

    return metrics


def proposal_for(content: DraftContent, **changes) -> dict:

    return {"title": content.title, "subtitle": content.subtitle, "body": content.body, **changes}


def reviewer(*responses, quality_analyzer=None) -> DraftReviewer:

    return DraftReviewer(
        llm=FakeLLMClient(list(responses)),
        sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE),
        quality_analyzer=quality_analyzer,
    )


# ----------------------------------------------------------------------
# The metrics
# ----------------------------------------------------------------------


def test_title_and_subtitle_are_metrics_beside_the_corrector_seven():

    draft = create_draft()

    review = reviewer(answer(), proposal_for(draft.content)).review(draft)

    assert list(review.metrics) == list(METRIC_ORDER)
    assert {"title", "subtitle"} <= set(review.metrics)
    assert {
        "grammar", "factConsistency", "coverageVerification", "seo",
        "readability", "hallucinationIndex", "style",
    } <= set(review.metrics)

    for metric in review.metrics.values():
        assert isinstance(metric, CorrectionMetric)
        assert 0 <= metric.score <= 100


def test_the_model_sees_the_excerpts_and_the_verdicts():
    """
    factConsistency and hallucinationIndex are judged against what the
    writer was given - not against the model's own idea of the world.
    """

    draft = create_draft(
        fact_checks=[DraftFactCheck(claim="The bay is free of pollution.", verdict="FALSE", confidence=0.9)],
    )

    llm = FakeLLMClient([answer(), proposal_for(draft.content)])
    DraftReviewer(llm=llm, sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE)).review(draft)

    system, prompt = llm.calls[0]

    assert system == REVIEW_SYSTEM_PROMPT
    assert "[1] example.org" in prompt
    assert "The restored meadow covered twice its 2015 area." in prompt
    assert "FALSE (confidence 0.90): The bay is free of pollution." in prompt
    assert draft.content.body in prompt


def test_a_factual_sentence_with_no_citation_is_reported_and_caps_the_score():

    draft = create_draft(content=DraftContent(
        title="Seagrass meadows return to the bay in Girona",
        subtitle="Ten years of replanting doubled the meadow's area",
        body=(
            "The meadow has doubled since 2015 [1]. "
            "In March 2024 the council said 40 divers joined the replanting."
        ),
    ))

    review = reviewer(answer(score=95), proposal_for(draft.content)).review(draft)

    metric = review.metrics["hallucinationIndex"]

    assert any("cites no source" in issue and "40 divers" in issue for issue in metric.issues)
    # Two factual sentences, one uncited: the model's 95 cannot stand.
    assert metric.score == 50.0
    assert "Capped at 50" in metric.summary


def test_a_claim_judged_false_repeated_as_fact_is_reported():

    draft = create_draft(
        content=DraftContent(
            title="Seagrass meadows return to the bay in Girona",
            subtitle="Ten years of replanting doubled the meadow's area",
            body="The meadow has doubled since 2015 [1]. The bay is now completely free of plastic pollution [2].",
        ),
        fact_checks=[
            DraftFactCheck(claim="The bay is now completely free of plastic pollution.", verdict="FALSE"),
            DraftFactCheck(claim="The meadow has doubled in area since 2015.", verdict="TRUE"),
        ],
    )

    review = reviewer(answer(), proposal_for(draft.content)).review(draft)

    issues = review.metrics["factConsistency"].issues

    assert any("judged FALSE" in issue and "free of plastic pollution" in issue for issue in issues)
    # The TRUE claim is the draft's to state.
    assert not any("doubled" in issue for issue in issues)


def test_a_claim_judged_unverified_is_reported_under_hallucination():

    draft = create_draft(
        content=DraftContent(
            title="Seagrass meadows return to the bay in Girona",
            subtitle="Ten years of replanting doubled the meadow's area",
            body="Dolphins have returned to the restored bay every summer [2].",
        ),
        fact_checks=[DraftFactCheck(claim="Dolphins returned to the restored bay every summer.", verdict="UNVERIFIED")],
    )

    review = reviewer(answer(), proposal_for(draft.content)).review(draft)

    assert any("judged UNVERIFIED" in issue for issue in review.metrics["hallucinationIndex"].issues)


def test_a_citation_to_a_source_that_does_not_exist_is_reported():

    draft = create_draft(content=DraftContent(
        title="Seagrass meadows return to the bay in Girona",
        subtitle="Ten years of replanting doubled the meadow's area",
        body="The meadow has doubled since 2015 [1], and fish counts rose with it [3].",
    ))

    review = reviewer(answer(), proposal_for(draft.content, body="The meadow has doubled since 2015 [1].")).review(draft)

    metric = review.metrics["factConsistency"]

    assert any("Cites [3], but the draft has 2 sources" in issue for issue in metric.issues)
    assert metric.score == 80.0


def test_headline_checks_need_no_model():

    draft = create_draft(content=DraftContent(
        title="Seagrass",
        subtitle="",
        body="The meadow has doubled since 2015 [1].",
    ))

    review = reviewer(answer(), proposal_for(draft.content)).review(draft)

    assert any("too short" in issue for issue in review.metrics["title"].issues)
    assert any("no subtitle" in issue for issue in review.metrics["subtitle"].issues)
    assert review.metrics["subtitle"].score == 20.0


def test_a_malformed_answer_is_unavailable_not_a_crash():

    draft = create_draft()

    # complete_json returns None when the model answered but never with
    # usable JSON; a dict of the wrong shape is the same failure.
    review = reviewer(None, {"verdict": "looks good"}).review(draft)

    for key in LLM_KEYS:
        assert review.metrics[key].summary == UNAVAILABLE_SUMMARY, key
        assert review.metrics[key].score == 0.0

    # The deterministic metrics did not need the model.
    assert review.metrics["readability"].summary != UNAVAILABLE_SUMMARY
    assert review.metrics["coverageVerification"].summary != UNAVAILABLE_SUMMARY

    assert review.corrected is None


def test_an_unavailable_metric_still_carries_the_checks_findings():

    draft = create_draft(content=DraftContent(
        title="Seagrass meadows return to the bay in Girona",
        subtitle="Ten years of replanting doubled the meadow's area",
        body="In March 2024 the council said 40 divers joined the replanting.",
    ))

    review = reviewer(None, None).review(draft)

    metric = review.metrics["hallucinationIndex"]

    assert metric.summary == UNAVAILABLE_SUMMARY
    assert metric.score == 0.0
    assert any("cites no source" in issue for issue in metric.issues)


def test_an_unreachable_model_fails_the_review():
    """A review of zeros would read as a draft that failed every metric."""

    draft = create_draft()

    with pytest.raises(LLMUnavailableError):
        reviewer(LLMUnavailableError("down")).review(draft)


def test_an_unreachable_model_for_the_proposal_keeps_the_metrics():

    draft = create_draft()

    review = reviewer(answer(), LLMUnavailableError("down")).review(draft)

    assert review.metrics["grammar"].score == 90
    assert review.corrected is None


def test_the_review_records_its_model():

    class NamedLLM(FakeLLMClient):
        model = "corrector-model"

    draft = create_draft()

    review = DraftReviewer(
        llm=NamedLLM([answer(), proposal_for(draft.content)]),
        sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE),
    ).review(draft)

    assert review.model == "corrector-model"


# ----------------------------------------------------------------------
# The proposal
# ----------------------------------------------------------------------


def test_the_correction_is_guided_by_the_review_and_keeps_the_language():

    draft = create_draft(language="ca", content=DraftContent(
        title="Les praderies tornen",
        subtitle="",
        body="La praderia ha duplicat la seva superfície des del 2015 [1].",
    ))

    llm = FakeLLMClient([
        answer(grammar={"score": 60, "summary": "Errors.", "issues": ["Falta un accent a «superficie»."]}),
        None,
    ])

    DraftReviewer(llm=llm, sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE)).review(draft)

    system, prompt = llm.calls[1]

    assert "Write in Catalan" in system
    assert "Never translate" in system
    assert "Add no facts" in system
    assert "[grammar] Falta un accent" in prompt
    assert "[subtitle] There is no subtitle" in prompt
    # The proposal adds no facts, so it is not handed the excerpts.
    assert "SOURCES" not in prompt


def test_a_good_proposal_is_offered():

    draft = create_draft()

    corrected = {
        "title": "Seagrass meadows double in the bay after ten years",
        "subtitle": "Replanting since 2015 doubled the meadow, and the fish came back",
        "body": "The meadow has doubled in size since 2015 [1], and fish counts rose with it [2].",
    }

    review = reviewer(answer(), corrected).review(draft)

    assert review.corrected == DraftContent(**corrected)


def test_a_proposal_citing_a_source_the_draft_never_cited_is_not_offered():

    original = DraftContent(title="T", subtitle="S", body="Doubled since 2015 [1].")

    proposal, reason = read_proposal({"title": "T", "body": "Doubled since 2015 [1][2]."}, original, CATALAN)

    assert proposal is None
    assert "[2]" in reason


def test_a_proposal_that_lost_every_citation_is_not_offered():

    original = DraftContent(title="T", subtitle="S", body="Doubled since 2015 [1].")

    proposal, reason = read_proposal({"title": "T", "body": "Doubled since 2015."}, original, writing_lexicon_for("en"))

    assert proposal is None
    assert "citation" in reason


def test_a_proposal_cut_short_is_not_offered():

    body = " ".join(["The meadow has doubled since 2015 and the fish came back [1]."] * 10)
    original = DraftContent(title="T", subtitle="S", body=body)

    proposal, _ = read_proposal({"title": "T", "body": "The meadow doubled [1]."}, original, writing_lexicon_for("en"))

    assert proposal is None


def test_a_proposal_that_came_back_translated_is_not_offered():

    catalan = (
        "La platja ha recuperat la posidònia després de deu anys de treball i els pescadors "
        "en són testimonis [1]. Els investigadors van anunciar que la praderia és més extensa "
        "que mai, i també que hi ha més peixos [2]."
    )
    spanish = (
        "La playa ha recuperado la posidonia después de diez años de trabajo y los pescadores "
        "son testigos [1]. Los investigadores anunciaron que la pradera es más extensa que "
        "nunca, y también que hay más peces [2]."
    )

    original = DraftContent(title="La posidònia torna", subtitle="", body=catalan)

    proposal, reason = read_proposal({"title": "La posidonia vuelve", "body": spanish}, original, CATALAN)

    assert proposal is None
    assert "Catalan" in reason

    kept, _ = read_proposal({"title": "La posidònia torna a la platja", "body": catalan}, original, CATALAN)

    assert kept is not None


def test_a_proposal_without_a_subtitle_keeps_the_drafts():

    original = DraftContent(title="T", subtitle="The standfirst", body="Doubled since 2015 [1].")

    proposal, _ = read_proposal({"title": "Better", "body": "It doubled since 2015 [1]."}, original, writing_lexicon_for("en"))

    assert proposal.subtitle == "The standfirst"


# ----------------------------------------------------------------------
# Catalan
# ----------------------------------------------------------------------

CATALAN_BODY = (
    "La platja de la Barceloneta ha recuperat la posidònia després de deu anys de treball [1]. "
    "Els investigadors de la Universitat de Barcelona van anunciar que la praderia ha duplicat "
    "la seva superfície [2]. La col·laboració entre voluntaris, pescadors i l'Ajuntament ha "
    "estat clau per a l'èxit del projecte."
)


class LexiconSpy(QualityAnalyzer):
    """The real analyser, noting which lexicon each metric was asked with."""

    def __init__(self):
        super().__init__()
        self.languages: list[str] = []

    def _note(self, lexicon):
        self.languages.append(lexicon.language if lexicon else "default")

    def readability(self, text, lexicon=None):
        self._note(lexicon)
        return super().readability(text, lexicon)

    def objectivity(self, text, entities, lexicon=None):
        self._note(lexicon)
        return super().objectivity(text, entities, lexicon)

    def constructiveness(self, text, lexicon=None):
        self._note(lexicon)
        return super().constructiveness(text, lexicon)

    def hopefulness(self, text, lexicon=None):
        self._note(lexicon)
        return super().hopefulness(text, lexicon)

    def societal_impact(self, text, entities, lexicon=None):
        self._note(lexicon)
        return super().societal_impact(text, entities, lexicon)

    def inspiration(self, text, sentiment, lexicon=None):
        self._note(lexicon)
        return super().inspiration(text, sentiment, lexicon)


def catalan_draft():

    return create_draft(language="ca", content=DraftContent(
        title="La posidònia torna a la Barceloneta després de deu anys",
        subtitle="La praderia ha duplicat la seva superfície gràcies a voluntaris i pescadors",
        body=CATALAN_BODY,
    ))


def test_catalan_is_never_scored_with_english_rules():

    spy = LexiconSpy()
    draft = catalan_draft()

    review = reviewer(answer(), proposal_for(draft.content), quality_analyzer=spy).review(draft)

    # Every word-list metric was asked with the Catalan lexicon, never
    # with the English fallback `lexicon_for("ca")` would have given.
    assert spy.languages
    assert set(spy.languages) == {"ca"}

    # The readability formula is the named stand-in, not textstat's
    # English constants that set_lang("ca") silently falls back to.
    body = grounding.plain(CATALAN_BODY)

    with _TEXTSTAT_LOCK:
        textstat.set_lang("ca")
        stand_in = textstat.fernandez_huerta(body)
        english_constants = textstat.flesch_reading_ease(body)

    readability = review.metrics["readability"]

    assert readability.score == round(max(0, min(stand_in / 100, 1)) * 100, 1)
    assert readability.score != round(max(0, min(english_constants / 100, 1)) * 100, 1)
    assert readability.summary.startswith("Stand-in for Catalan")
    assert "Fernández Huerta" in readability.summary

    assert "Catalan lexicon" in review.metrics["coverageVerification"].summary


def test_catalan_words_reach_the_lexicon():
    """Elision and the punt volat would otherwise hide them from it."""

    prepared = draft_language.prepare_for_scoring("La col·laboració d'investigació amb l'escola", "ca")

    assert prepared == "La collaboració d investigació amb l escola"

    analyzer = QualityAnalyzer()

    assert analyzer.constructiveness(prepared, CATALAN) > analyzer.constructiveness(
        "La col·laboració d'investigació amb l'escola", CATALAN
    )


def test_a_catalan_report_counts_as_a_factual_sentence():

    sentence = "Els investigadors de la Universitat de Barcelona van anunciar que la praderia creix"

    assert grounding.is_factual(sentence, CATALAN)
    assert not grounding.is_factual("La col·laboració ha estat clau per a l'èxit del projecte.", CATALAN)


def test_catalan_is_a_writing_language_not_a_source_language():
    """
    LanguageDetector and the pipeline read LEXICONS; Catalan joining it
    would change how every Spanish article is detected and scored.
    """

    assert "ca" not in LEXICONS
    assert writing_lexicon_for("ca") is CATALAN

    with pytest.raises(UnsupportedWritingLanguage):
        writing_lexicon_for("fr")


def test_every_draft_language_has_a_complete_writing_lexicon():
    """
    Adding a writing language to the draft model without a lexicon would
    make the review raise on every draft in it - better here, at once.
    """

    assert set(get_args(Language)) <= set(WRITING_LEXICONS)

    for language in get_args(Language):
        assert language in draft_language.READABILITY


# ----------------------------------------------------------------------
# /correct and the writing benchmark are untouched
# ----------------------------------------------------------------------


def test_llm_metrics_still_sends_the_benchmarks_prompt():
    """
    src/evaluation/writing.py benchmarks TextCorrector.llm_metrics with
    SYSTEM_PROMPT; the draft review is a separate prompt.
    """

    llm = FakeLLMClient(None)

    TextCorrector(llm=llm, sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE)).llm_metrics("Some text.")

    assert llm.calls[0][0] == SYSTEM_PROMPT
    assert REVIEW_SYSTEM_PROMPT != SYSTEM_PROMPT


def test_sources_share_one_budget_in_the_prompt():

    many = [
        DraftSource(url=f"https://example.org/{index}", origin="related", excerpt="x" * 5_000)
        for index in range(20)
    ]

    prompt = review_prompt(create_draft(sources=many))

    # Every source is listed - a draft citing [20] must have it in view.
    assert "[20] https://example.org/19" in prompt
    assert len(prompt) < 20_000


def test_the_correction_prompt_has_no_notes_when_nothing_was_found():

    draft = create_draft()

    prompt = correction_prompt(draft, {key: CorrectionMetric(score=90, summary="Fine.") for key in METRIC_ORDER})

    assert "(none recorded)" in prompt

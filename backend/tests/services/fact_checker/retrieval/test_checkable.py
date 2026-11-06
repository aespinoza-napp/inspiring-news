"""
`query_plan: checkable` (2026-11-04): what a claim turns on, read from its
sentence (retrieval/checkable.py), and the queries planned from it
(query_builder.plan_checkable). The claims are the 4 Nov comparison's
(docs/troubleshooting/fact-checking/), whose queries had lost every figure.
"""

import pytest

from src.config.thresholds import PipelineThresholds, ThresholdOverrides
from src.evaluation.runner import keyed_thresholds, thresholds_hash
from src.services.fact_checker.retrieval.checkable import FILLERS, FRAMING, checkable_point, dates_of, figures_of, name_groups
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.retrieval.query_builder import QueryKind, plan_queries

from tests.factories import create_claim
from tests.services.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEvidenceScraper,
    FakeSearchProvider,
    FakeVectorRetriever,
)

DENGUE = "There have been a total of 212 known travel-related cases in Florida reported so far in 2026."
ROAD = (
    "Cuando sea ejecutada esta infraestructura, la función de ronda metropolitana pasará a esa 'nueva' SE-20 "
    "y desaparecerá por tanto de la Ronda Urbana Norte, en la que se invertirán casi 25 millones de euros "
    "hasta su culminación a finales de 2028."
)
WINERY = "Ignacio Calvo de Mora es el director general de Bodegas Benjamin de Rothschild & Vega Sicilia (Macán)."


def claim(text, entities=None):

    return create_claim(text=text, entities=entities or {})


# ----------------------------------------------------------------------
# The point
# ----------------------------------------------------------------------


def test_a_figure_reaches_the_point_without_the_article_pipelines_facts():
    """ClaimService builds claims with no `facts`: the point reads the sentence itself."""

    bare = claim(DENGUE)

    assert bare.facts.figures == []

    point = checkable_point(bare, None, "en")

    assert point.figures == ["212"]
    assert point.dates == ["2026"]
    assert point.names == ["Florida"]


def test_identifiers_times_and_counts_are_kept_whole():

    identifiers, figures = figures_of("La SE-20 y la SE-40; despegó a las 14:49; un diagrama 11-set de 13 conjuntos")

    assert identifiers == ["SE-20", "SE-40", "11-set", "14:49"]
    assert "20" not in figures and "49" not in figures and "11" not in figures
    assert figures == ["13"]


def test_a_percentage_and_a_scale_belong_to_their_figure():

    assert figures_of("fewer than 0.001 per cent of all brain cells")[1] == ["0.001 per cent"]
    assert figures_of("se invertirán casi 25 millones de euros")[1] == ["25 millones"]


def test_most_distinctive_figures_first_and_a_single_digit_is_not_one():

    assert figures_of("cataloged 138,000 books, added 23,000 titles and converted 10 books, in 3 days")[1] == [
        "138,000", "23,000", "10",
    ]


def test_a_day_with_its_month_is_a_date_and_not_also_a_figure():

    assert dates_of("officials made the declaration on 24 September", "en") == ["24 September"]
    assert dates_of("el 24 de septiembre de 2026", "es") == ["24 de septiembre", "2026"]

    point = checkable_point(claim("Officials declared it on 24 September as 134 cases were recorded."), None, "en")

    assert point.dates == ["24 September"] and point.figures == ["134"]


def test_the_sentences_filler_is_not_looked_for():

    point = checkable_point(claim("Meanwhile, the Arctic recorded its minimum summer sea ice extent on 12 September."), None, "en")

    assert "Meanwhile" not in point.names + point.terms
    assert point.names == ["Arctic"]
    assert point.terms[:3] == ["recorded", "minimum", "summer"]


def test_both_languages_have_fillers():
    """Invariant 8's rule for every lexicon: a third language must not be scored as English silently."""

    assert set(FILLERS) == {"en", "es"}
    assert all(FILLERS.values())


@pytest.mark.parametrize("text, expected", [
    ("“We found that”, says study co-author James Michael Roe, a neuroscientist at the University of Oslo",
     ["James Michael Roe", "University of Oslo"]),
    (WINERY, ["Ignacio Calvo de Mora", "Bodegas Benjamin de Rothschild & Vega Sicilia", "Macán"]),
    ("the nonprofit has restored the Eastlands and Kaloleni libraries", ["Eastlands", "Kaloleni"]),
    ("Meanwhile, the Arctic recorded", ["Arctic"]),
])
def test_names_are_runs_of_capitalised_words(text, expected):

    assert name_groups(text, set()) == expected


def test_a_country_written_with_stops_is_not_two_acronyms():

    point = checkable_point(claim("desde el complejo de SpaceX en el extremo sur de Texas, EE.UU, y reingresó"), None, "es")

    assert "EE" not in point.names and "UU" not in point.names


# ----------------------------------------------------------------------
# The queries
# ----------------------------------------------------------------------


def test_every_query_carries_the_figure_the_claim_turns_on():

    plan = plan_queries(claim(DENGUE), None, "en", style="checkable")

    assert [query.kind for query in plan] == [QueryKind.ANCHOR, QueryKind.PROPOSITION, QueryKind.SPECIFICS]
    assert all('"212"' in query.text for query in plan)
    assert "been" not in plan[1].text and "total" not in plan[1].text


def test_identifiers_and_scales_are_searched_verbatim():

    anchor = plan_queries(claim(ROAD), None, "es", style="checkable")[0].text

    assert '"SE-20"' in anchor and '"25 millones"' in anchor and "2028" in anchor
    assert "Ronda Urbana Norte" in anchor


def test_a_claim_with_nothing_specific_keeps_the_refutation_query():

    plan = plan_queries(claim(WINERY), None, "es", style="checkable")

    assert plan[-1].kind is QueryKind.REFUTATION
    assert "verificación" in plan[-1].text


def test_a_year_alone_does_not_make_a_specifics_query():

    plan = plan_queries(claim("Founded in 2017 by Wanjiru Koinange, the nonprofit restored the libraries."), None, "en", style="checkable")

    assert plan[-1].kind is QueryKind.REFUTATION


def test_specifics_is_switched_by_the_refutation_kind():

    without = plan_queries(claim(DENGUE), None, "en", ("anchor", "proposition"), style="checkable")
    only = plan_queries(claim(DENGUE), None, "en", ("refutation",), style="checkable")

    assert QueryKind.SPECIFICS not in [query.kind for query in without]
    assert [query.kind for query in only] == [QueryKind.SPECIFICS]


def test_a_claim_naming_nothing_is_anchored_on_its_assertion():

    anchor = plan_queries(
        claim("In eight of 11 industrial sectors, fossil fuel use has already peaked, the analysis found."),
        None, "en", style="checkable",
    )[0].text

    assert anchor.startswith("eight industrial sectors")


# ----------------------------------------------------------------------
# The default is the sentence plan, and old runs keep their keys
# ----------------------------------------------------------------------


def test_the_sentence_plan_is_the_default_and_unchanged():

    plain = claim("NASA discovered water on Mars in 2025.", {"ORG": ["NASA"]})

    assert PipelineThresholds().query_plan == "sentence"
    assert plan_queries(plain, None, "en") == plan_queries(plain, None, "en", style="sentence")
    assert QueryKind.SPECIFICS not in [query.kind for query in plan_queries(claim(DENGUE), None, "en")]


def test_a_run_with_the_sentence_plan_keeps_the_key_it_had():

    assert "query_plan" not in keyed_thresholds(PipelineThresholds())
    assert thresholds_hash(PipelineThresholds(query_plan="sentence")) == thresholds_hash(PipelineThresholds())
    assert thresholds_hash(PipelineThresholds(query_plan="checkable")) != thresholds_hash(PipelineThresholds())


def test_a_request_or_a_thresholds_file_sets_it():

    resolved = PipelineThresholds.resolve(ThresholdOverrides.model_validate({"query_plan": "checkable"}))

    assert resolved.query_plan == "checkable"


def _retriever():

    return EvidenceRetriever(
        repository=None,
        search_provider=FakeSearchProvider([]),
        scraper=FakeEvidenceScraper(),
        vector_retriever=FakeVectorRetriever([]),
        embeddings=FakeEmbeddingService(),
    )


def test_the_search_event_says_what_was_looked_for_under_the_checkable_plan():

    events = []

    _retriever().retrieve(
        claim(DENGUE), thresholds=PipelineThresholds(query_plan="checkable"), language="en",
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    point = dict(events)["searching_web"]["checkablePoint"]

    assert point["figures"] == ["212"] and point["names"] == ["Florida"]


def test_the_search_event_is_as_before_under_the_sentence_plan():

    events = []

    _retriever().retrieve(claim(DENGUE), language="en", on_phase=lambda phase, data: events.append((phase, data)))

    assert "checkablePoint" not in dict(events)["searching_web"]


# ----------------------------------------------------------------------
# The subject the sentence lost, from the article's headline
# ----------------------------------------------------------------------

from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.retrieval.checkable import headline_of, title_subject

HEADLINE = "Dengue fever outbreak prompts Florida counties to declare state of emergency"
SIBLING = ("Hillsborough county officials made the declaration as health authorities recorded 134 "
           "confirmed cases of dengue fever, in counties across the state.")


def test_the_headline_gives_the_subject_the_sentence_never_says():

    assert title_subject(HEADLINE, DENGUE, "en", [SIBLING]) == ["Dengue", "fever", "counties"]


def test_a_headline_word_the_article_never_repeats_is_framing_not_subject():

    assert title_subject("Mi querida suegra dice que tengo gusto de champán", WINERY, "es",
                         ["Macán es el proyecto conjunto de las dos familias."]) == []


def test_without_the_articles_other_sentences_there_is_no_subject():

    assert title_subject(HEADLINE, DENGUE, "en", []) == []


def test_the_sites_name_is_not_part_of_the_headline():

    assert headline_of("Brain area discovered that may be critical for viable pregnancies | New Scientist") == (
        "Brain area discovered that may be critical for viable pregnancies"
    )
    assert headline_of("Arctic ice persists - Carbon Brief") == "Arctic ice persists"


def test_a_plural_in_the_headline_is_the_singular_in_the_claim():

    assert "pregnancies" not in title_subject(
        "Brain area critical for viable pregnancies", "It blocks the ability to establish a viable pregnancy.", "en",
        ["Every pregnancy failed."],
    )


def test_the_search_title_restores_the_subject_in_every_query():

    context = ArticleContext(url="https://example.org/dengue", search_title=HEADLINE, search_sentences=[SIBLING])

    plan = plan_queries(claim(DENGUE), context, "en", style="checkable")

    assert all("Dengue fever" in query.text for query in plan)
    assert checkable_point(claim(DENGUE), context, "en").headline == HEADLINE


def test_the_apps_title_and_keywords_still_decide_when_they_exist():
    """The search title is the harness's fallback; the app's context keeps terms.subject_terms' rule."""

    context = ArticleContext(title=HEADLINE, keywords=["dengue", "florida"], search_title="Something else entirely")

    point = checkable_point(claim(DENGUE), context, "en")

    assert point.subject == ["Dengue"] and point.headline == ""


# ----------------------------------------------------------------------
# The harness: headlines from the labeller's batches, under checkable only
# ----------------------------------------------------------------------

import json as _json

from src.evaluation.dataset import article_titles, title_for
from src.evaluation.runner import context_for


class _Row:
    dataset = "custom"

    def __init__(self, url, claim_text):
        self.article_url = url
        self.claim = claim_text


def _queue(tmp_path):

    queue = tmp_path / "queue"
    queue.mkdir()
    (queue / "2026-09-29.json").write_text(_json.dumps({"articles": [{
        "url": "https://www.theguardian.com/us-news/2026/sep/28/dengue-fever-cases-florida-counties",
        "title": HEADLINE,
        "claims": [{"text": DENGUE}, {"text": SIBLING}],
    }]}), encoding="utf-8")
    (queue / "broken.json").write_text("{not json", encoding="utf-8")

    return tmp_path


def test_the_batches_give_each_article_its_headline_and_other_sentences(tmp_path):

    titles = article_titles(_queue(tmp_path))

    # Matched by host and path: www and a trailing slash do not matter.
    row = _Row("https://theguardian.com/us-news/2026/sep/28/dengue-fever-cases-florida-counties/", DENGUE)

    assert title_for(row, titles) == (HEADLINE, [SIBLING])


def test_the_verifier_is_not_shown_the_headline():
    """`title` is what the verifier's prompt reads; the harness leaves it empty."""

    context = context_for(_Row("https://example.org/a", DENGUE), HEADLINE, [SIBLING])

    assert context.title == "" and context.search_title == HEADLINE


def test_under_the_sentence_plan_the_harness_context_is_as_before():

    context = context_for(_Row("https://example.org/a", DENGUE))

    assert context.search_title == "" and context.search_sentences == []


# ----------------------------------------------------------------------
# checkable_terms (2026-11-05): the sentence's framing after its finding
# ----------------------------------------------------------------------

# Two sentences of the 5 Nov batch (20261105-next20, fact085 and fact088),
# whose six term slots went to who led, wrote or found it and lost the
# finding: "disfunción diastólica", "older mice".
CNIC = (
    "Un estudio liderado por el Centro Nacional de Investigaciones Cardiovasculares Carlos III (CNIC) ha "
    "identificado la activación del receptor de glucocorticoides como un mecanismo causal de la disfunción "
    "diastólica temprana asociada a la obesidad."
)
KNEE = (
    "Blau and her colleague, Nidhi Bhutani, an associate professor of orthopedic surgery, discovered that in "
    "older mice, blocking 15‑PGDH reversed the cartilage loss that normally accompanies aging in the knee."
)
# fact122: "main goal" took two slots, and "third" was the seventh word.
JUICE = (
    "While the main goal was to alter Juice’s trajectory, the flyby also provided a third opportunity to test "
    "out Juice’s science instruments on a real surface in space – with the first being during the "
    "spacecraft’s 2024 lunar-Earth gravity assist, and the second during the 2025 observations of Comet 3I/ATLAS."
)


def test_by_default_the_terms_keep_the_sentences_order():

    assert PipelineThresholds().checkable_terms == "sentence"

    point = checkable_point(claim(CNIC), None, "es")

    assert point.terms[:3] == ["estudio", "liderado", "identificado"]
    assert checkable_point(claim(CNIC), None, "es", "sentence") == point


# fact085 gains "disfunción" but not "diastólica": "mecanismo causal",
# which is not framing, still takes the slots before it. Recorded as it is.
@pytest.mark.parametrize("text, language, finding", [
    (CNIC, "es", {"disfunción"}),
    (KNEE, "en", {"older", "mice"}),
    (JUICE, "en", {"third"}),
])
def test_framing_last_keeps_the_finding_the_framing_crowded_out(text, language, finding):

    before = checkable_point(claim(text), None, language)
    after = checkable_point(claim(text), None, language, "framing_last")

    assert not finding <= set(before.terms)
    assert finding <= set(after.terms)

    # Only the terms move: the names, figures and dates are the same.
    assert (after.names, after.figures, after.dates) == (before.names, before.figures, before.dates)


def test_framing_last_only_reorders_a_short_sentences_terms():
    """Nothing is dropped: under six terms the same words come back, framing at the end."""

    text = "Un estudio liderado por el CNIC detecta daño cardíaco temprano."

    before = checkable_point(claim(text), None, "es").terms
    after = checkable_point(claim(text), None, "es", "framing_last").terms

    assert sorted(before) == sorted(after)
    assert after[-2:] == ["estudio", "liderado"]


def test_the_proposition_query_carries_the_finding_under_framing_last():

    def proposition(plan):
        return next(query.text for query in plan if query.kind is QueryKind.PROPOSITION)

    sentence_order = plan_queries(claim(KNEE), None, "en", style="checkable")
    framing_last = plan_queries(claim(KNEE), None, "en", style="checkable", terms_order="framing_last")

    assert "mice" not in proposition(sentence_order)
    assert "older mice" in proposition(framing_last)

    # Read under the checkable plan only: the sentence plan is as it was.
    assert plan_queries(claim(CNIC), None, "es", terms_order="framing_last") == plan_queries(claim(CNIC), None, "es")


def test_both_languages_have_a_framing_lexicon():

    assert FRAMING["en"] and FRAMING["es"]


def test_a_run_with_sentence_ordered_terms_keeps_the_key_it_had():

    assert "checkable_terms" not in keyed_thresholds(PipelineThresholds(checkable_terms="sentence"))
    assert thresholds_hash(PipelineThresholds(checkable_terms="framing_last")) != thresholds_hash(PipelineThresholds())


def test_a_request_or_a_thresholds_file_sets_checkable_terms():

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides.model_validate({"query_plan": "checkable", "checkable_terms": "framing_last"}),
    )

    assert resolved.checkable_terms == "framing_last"


def test_the_search_event_reads_the_point_with_the_runs_terms_order():

    events = []

    _retriever().retrieve(
        claim(KNEE), thresholds=PipelineThresholds(query_plan="checkable", checkable_terms="framing_last"),
        language="en", on_phase=lambda phase, data: events.append((phase, data)),
    )

    assert "mice" in dict(events)["searching_web"]["checkablePoint"]["terms"]


# ----------------------------------------------------------------------
# checkable_terms: finding_first (2026-11-05): the asides after the finding
# ----------------------------------------------------------------------

# fact123 of the 5 Nov batch (20261105-next20), its sentence only.
CAMERAS = (
    "As Juice flew just 8640 km above the Indian Ocean, it snapped a series of images with its onboard "
    "monitoring cameras."
)

# The entity model's names for KNEE, as the measure had them: "Blau" opens
# the sentence, so without them it is a term and takes a slot.
KNEE_NAMES = {"person": ["Blau", "Nidhi Bhutani"]}


@pytest.mark.parametrize("text, entities, finding", [
    (CAMERAS, None, {"monitoring", "cameras"}),
    (KNEE, KNEE_NAMES, {"cartilage"}),
])
def test_finding_first_keeps_the_finding_the_asides_crowded_out(text, entities, finding):

    framing = checkable_point(claim(text, entities), None, "en", "framing_last")
    after = checkable_point(claim(text, entities), None, "en", "finding_first")

    assert not finding <= set(framing.terms)
    assert finding <= set(after.terms)

    # What framing_last kept of the finding stays: "older mice" (fact088).
    assert {"older", "mice"} <= set(checkable_point(claim(KNEE, KNEE_NAMES), None, "en", "finding_first").terms)

    assert (after.names, after.figures, after.dates) == (framing.names, framing.figures, framing.dates)


def test_finding_first_moves_the_asides_and_drops_nothing():
    """Under six terms the same words come back: finding, then asides, then framing."""

    english = "Researchers explained the bridge above the river collapsed."
    terms = checkable_point(claim(english), None, "en", "finding_first").terms

    assert sorted(terms) == sorted(checkable_point(claim(english), None, "en").terms)
    assert terms == ["bridge", "river", "above", "collapsed", "Researchers", "explained"]

    # The accent makes the verb: "llenó" goes after "primera" and "inicios",
    # and stays (fact117's decisive word).
    spanish = "Judeline llenó por primera vez el Palacio de Deportes de Madrid a inicios de 2026."
    point = checkable_point(claim(spanish, {"person": ["Judeline"]}), None, "es", "finding_first")
    assert point.terms == ["primera", "inicios", "llenó"]


@pytest.mark.parametrize("word, language, aside", [
    ("reversed", "en", True), ("snapped", "en", True),
    ("need", "en", False), ("speed", "en", False), ("monitoring", "en", False),
    ("logró", "es", True), ("presentaron", "es", True), ("estado", "es", False), ("bajo", "es", False),
])
def test_what_counts_as_an_aside(word, language, aside):

    from src.services.fact_checker.retrieval.checkable import finding_first

    assert (finding_first([word, "finding"], language) == ["finding", word]) is aside


def test_both_languages_have_an_asides_lexicon():

    from src.services.fact_checker.retrieval.checkable import ASIDES, PAST_TENSE

    assert ASIDES["en"] and ASIDES["es"] and set(PAST_TENSE) == {"en", "es"}


def test_finding_first_is_a_threshold_value_with_its_own_key():

    resolved = PipelineThresholds.resolve(ThresholdOverrides.model_validate({"checkable_terms": "finding_first"}))

    assert resolved.checkable_terms == "finding_first"
    assert PipelineThresholds().checkable_terms == "sentence"
    assert thresholds_hash(resolved) != thresholds_hash(PipelineThresholds(checkable_terms="framing_last"))


# ----------------------------------------------------------------------
# checkable_terms: finding_closing (2026-11-05, 20261105-next20-round-05.md)
# ----------------------------------------------------------------------

# fact086 of the 5 Nov batch, its sentence only, with the names the entity
# model gave it: "macrófagos" closes a list long past the six slots.
CELLS = (
    "Según la primera autora, Antonella Ausiello, también investigadora en el CNIC, los resultados muestran que "
    "“la obesidad y la hiperglucemia provocan la remodelación molecular más intensa y extensa, con cambios en "
    "distintos tipos de células presentes en el corazón: cardiomiocitos, fibroblastos, células endoteliales y "
    "macrófagos”."
)
CELLS_NAMES = {"person": ["Antonella Ausiello"], "org": ["CNIC"], "other": ["cardiomiocitos"]}


@pytest.mark.parametrize("text, entities, language, closing", [
    (CELLS, CELLS_NAMES, "es", "macrófagos"),
    (KNEE, KNEE_NAMES, "en", "knee"),
])
def test_finding_closing_keeps_the_closing_word_the_cut_took(text, entities, language, closing):

    first = checkable_point(claim(text, entities), None, language, "finding_first")
    after = checkable_point(claim(text, entities), None, language, "finding_closing")

    assert closing not in first.terms and len(first.terms) == 6

    # finding_first's six, exactly, and one more: nothing leaves the point.
    assert after.terms == first.terms + [closing]

    assert (after.names, after.figures, after.dates) == (first.names, first.figures, first.dates)


def test_finding_closing_changes_nothing_when_the_closing_word_was_kept():

    # Six terms or fewer, or the last finding word among the six.
    assert (
        checkable_point(claim(CAMERAS), None, "en", "finding_closing")
        == checkable_point(claim(CAMERAS), None, "en", "finding_first")
    )


def test_the_closing_word_is_a_finding_word_not_an_aside_or_framing():

    from src.services.fact_checker.retrieval.checkable import finding_closing

    # "again" and "reported" are closer to the end, and neither is the finding.
    terms = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "harbour", "again", "reported"]

    assert finding_closing(terms, "en") == ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "harbour"]


def test_the_closing_word_reaches_the_proposition_query_and_the_others_stay():

    plan = {query.kind: query.text for query in plan_queries(
        claim(KNEE, KNEE_NAMES), None, "en", None, "checkable", "finding_closing", "counted",
    )}
    first = {query.kind: query.text for query in plan_queries(
        claim(KNEE, KNEE_NAMES), None, "en", None, "checkable", "finding_first", "counted",
    )}

    assert plan[QueryKind.PROPOSITION] == f"{first[QueryKind.PROPOSITION]} knee"

    # Only the proposition asks for it: the anchor and the third are the same.
    assert plan[QueryKind.ANCHOR] == first[QueryKind.ANCHOR]


def test_the_older_orders_still_stop_at_six():

    for order in (None, "sentence", "framing_last", "finding_first"):
        assert len(checkable_point(claim(KNEE, KNEE_NAMES), None, "en", order).terms) <= 6


def test_finding_closing_is_a_threshold_value_with_its_own_key():

    resolved = PipelineThresholds.resolve(ThresholdOverrides.model_validate({"checkable_terms": "finding_closing"}))

    assert resolved.checkable_terms == "finding_closing"
    assert PipelineThresholds().checkable_terms == "sentence"
    assert thresholds_hash(resolved) != thresholds_hash(PipelineThresholds(checkable_terms="finding_first"))


# ----------------------------------------------------------------------
# checkable_figures (2026-11-05): a figure with its currency or unit on it
# ----------------------------------------------------------------------

# Two sentences of the 5 Nov batch (20261105-next20, fact099 and fact101)
# whose one figure the bare pattern dropped whole, since it stops at the
# letter after the digits.
GAS_IMPORTS = (
    "The UK has avoided the need for gas imports worth £5.9bn since the start of the Hormuz crisis as a "
    "result of record generation from wind and solar, reveals Carbon Brief analysis."
)
THERM = (
    "In September 2026 to date, gas prices have averaged 189p per therm, reaching their highest level "
    "since the global energy crisis in 2022, as shown in the figure below."
)


def test_by_default_a_figure_with_a_unit_on_it_is_dropped_as_before():

    assert PipelineThresholds().checkable_figures == "bare"

    assert checkable_point(claim(GAS_IMPORTS), None, "en").figures == []
    assert checkable_point(claim(THERM), None, "en").figures == []
    assert checkable_point(claim(THERM), None, "en", None, "bare") == checkable_point(claim(THERM), None, "en")


@pytest.mark.parametrize("text, figure", [(GAS_IMPORTS, "£5.9bn"), (THERM, "189p")])
def test_with_units_keeps_the_figure_as_written(text, figure):

    before = checkable_point(claim(text), None, "en")
    after = checkable_point(claim(text), None, "en", None, "with_units")

    assert after.figures == [figure]

    # A sign or a unit makes it distinctive, so the third query asks for it.
    assert after.specific and figure in after.distinctive_figures

    # Only the figures change: the names and dates are the same.
    assert (after.names, after.dates) == (before.names, before.dates)


@pytest.mark.parametrize("text, kept, not_kept", [
    # Signs and units in either language, and a bare number beside them.
    ("Costó €40m y 3,5kg de material, frente a 120 unidades.", ["€40m", "3,5kg"], []),
    ("A $2bn deal for 50GW over 8640km.", ["$2bn", "50GW", "8640km"], []),
    # Ordinals are not units, in either language; nor is one digit and a letter.
    ("The 21st edition, the 2nd round, a 5G mast and a 3D film.", [], ["21st", "2nd", "5G", "3D"]),
    ("Es la 3er edición y el 2do intento.", [], ["3er", "2do"]),
])
def test_what_counts_as_a_figure_with_a_unit(text, kept, not_kept):

    _, figures = figures_of(text, units=True)

    assert set(kept) <= set(figures)
    assert not set(not_kept) & set(figures)


def test_a_shorter_figure_does_not_eat_a_longer_one():

    _, figures = figures_of("From £40 to £400m in a year.", units=True)

    assert set(figures) == {"£40", "£400m"}


def test_the_anchor_query_quotes_the_figure_under_with_units():

    def anchor(plan):
        return next(query.text for query in plan if query.kind is QueryKind.ANCHOR)

    bare = plan_queries(claim(GAS_IMPORTS), None, "en", style="checkable")
    with_units = plan_queries(claim(GAS_IMPORTS), None, "en", style="checkable", figures_style="with_units")

    assert "5.9" not in anchor(bare)
    assert '"£5.9bn"' in anchor(with_units)

    # Read under the checkable plan only: the sentence plan is as it was.
    assert plan_queries(claim(THERM), None, "en", figures_style="with_units") == plan_queries(claim(THERM), None, "en")


def test_a_run_with_bare_figures_keeps_the_key_it_had():

    assert "checkable_figures" not in keyed_thresholds(PipelineThresholds(checkable_figures="bare"))
    assert thresholds_hash(PipelineThresholds(checkable_figures="with_units")) != thresholds_hash(PipelineThresholds())

    resolved = PipelineThresholds.resolve(ThresholdOverrides.model_validate({"checkable_figures": "with_units"}))

    assert resolved.checkable_figures == "with_units"


def test_the_search_event_reads_the_point_with_the_runs_figures():

    events = []

    _retriever().retrieve(
        claim(THERM), thresholds=PipelineThresholds(query_plan="checkable", checkable_figures="with_units"),
        language="en", on_phase=lambda phase, data: events.append((phase, data)),
    )

    assert dict(events)["searching_web"]["checkablePoint"]["figures"] == ["189p"]


# ----------------------------------------------------------------------
# checkable_figures: counted (2026-11-05, 20261105-next20-round-04.md)
# ----------------------------------------------------------------------

# The 5 Nov batch's fact106 sentence, with the names the entity model gave
# it in that run: "minutes", a word of its own, took the sixth term slot and
# "crew" was cut.
STRANGER = (
    "Two days later, last Friday, a stranger arrived at Kirk’s debris-laden front lawn in Wyandotte County, "
    "and said he’d be back in 30 minutes with a tarp, some lumber, and a crew to cover up the maple-shaped "
    "gash in Kirk’s house."
)
STRANGER_NAMES = {"person": ["Kirk"], "other": ["stranger", "Wyandotte County", "tarp"]}


def test_counted_keeps_the_noun_a_figure_counts_and_frees_its_term_slot():

    before = checkable_point(claim(STRANGER, STRANGER_NAMES), None, "en", "finding_first", "with_units")
    after = checkable_point(claim(STRANGER, STRANGER_NAMES), None, "en", "finding_first", "counted")

    assert before.figures == ["30"] and "minutes" in before.terms and "crew" not in before.terms

    assert after.figures == ["30 minutes"]
    assert "minutes" not in after.terms and "crew" in after.terms

    # Only the figures and the terms move: names and dates are the same.
    assert (after.names, after.dates) == (before.names, before.dates)


@pytest.mark.parametrize("text, language, figures", [
    # Either language (invariant 8): the count's noun right after it.
    ("En el estudio participaron 116 mujeres con ciclos menstruales naturales.", "es", ["116 mujeres"]),
    ("Wind and solar generated a record 41% share of the UK's electricity.", "en", ["41% share"]),
    # Not an aside: "since" is not what £5.9bn counts.
    (GAS_IMPORTS, "en", ["£5.9bn"]),
    # Not a stopword, a capital (a name) or half a compound.
    ("Some 10% of Americans saw 212 travel-related cases.", "en", ["10%", "212"]),
    ("Over 45 Spanish towns joined.", "en", ["45"]),
])
def test_what_counts_as_a_figures_noun(text, language, figures):

    assert checkable_point(claim(text), None, language, None, "counted").figures == figures


def test_counted_reads_units_as_with_units_does():

    # No figure here has a noun after it: the point is with_units's.
    assert checkable_point(claim(THERM), None, "en", None, "counted") == checkable_point(claim(THERM), None, "en", None, "with_units")

    resolved = PipelineThresholds.resolve(ThresholdOverrides.model_validate({"checkable_figures": "counted"}))

    assert resolved.checkable_figures == "counted"
    assert thresholds_hash(PipelineThresholds(checkable_figures="counted")) != thresholds_hash(PipelineThresholds(checkable_figures="with_units"))

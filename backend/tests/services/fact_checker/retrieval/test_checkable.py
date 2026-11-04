"""
`query_plan: checkable` (2026-11-04): what a claim turns on, read from its
sentence (retrieval/checkable.py), and the queries planned from it
(query_builder.plan_checkable). The claims are the 4 Nov comparison's
(docs/troubleshooting/), whose queries had lost every figure.
"""

import pytest

from src.config.thresholds import PipelineThresholds, ThresholdOverrides
from src.evaluation.runner import keyed_thresholds, thresholds_hash
from src.services.fact_checker.retrieval.checkable import FILLERS, checkable_point, dates_of, figures_of, name_groups
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

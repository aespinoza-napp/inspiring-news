from src.services.fact_checker.retrieval.search_provider import SearchProvider
from src.models.fact_checker.evidence import EvidenceOrigin

from tests.factories import create_claim
from tests.services.fact_checker.fakes import FakeSearxngClient


def test_search_maps_raw_results_to_evidence():

    client = FakeSearxngClient(results=[
        {
            "url": "https://example.com/a",
            "title": "Article A",
            "content": "Some snippet text.",
            "publishedDate": "2024-05-01T00:00:00Z",
        },
    ])

    provider = SearchProvider(client=client)

    claim = create_claim(text="NASA discovered water on Mars.")

    results = provider.search(claim)

    assert len(results) == 1
    evidence = results[0]
    assert evidence.url == "https://example.com/a"
    assert evidence.title == "Article A"
    assert evidence.snippet == "Some snippet text."
    assert evidence.origin == EvidenceOrigin.WEB
    assert evidence.published_at is not None
    assert evidence.published_at.year == 2024


def test_search_anchors_the_query_on_the_claims_entities():
    """
    Traceability check for what actually leaves the process: the query
    is built from `claim.entities`, not the full sentence. A single-word
    entity goes in bare; a multi-word one is quoted so SearXNG's
    underlying engines treat it as one phrase instead of splitting
    "the two countries" across unrelated pages.

    This replaced sending the raw grammatical sentence (stopwords,
    articles and all) as a bag of words - see git history on this test
    for what that looked like and why it was suspected of hurting
    recall.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(
        text=(
            "According to officials, the new trade agreement between the "
            "two countries will reduce tariffs starting next year."
        ),
        entities={"ORG": ["the two countries"], "PERSON": ["Jane Doe"]},
    )

    provider.search(claim)

    assert client.queries == ['"the two countries" "Jane Doe"']


def test_search_includes_figures_the_entity_extractor_does_not_capture():
    """
    EntityExtractor's DEFAULT_LABELS (src/processors/nlp/entities.py) has
    no "date" or "number" label, so a percentage or a year never shows up
    in claim.entities even though it is often what pins a claim to one
    real event rather than a similar-sounding one. FIGURE_PATTERN pulls
    those out of the claim text directly and appends them to the
    entity-anchored query.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(
        text="The treaty, signed in 2024, will cut tariffs by 15%.",
        entities={"ORG": ["the treaty"]},
    )

    provider.search(claim)

    assert client.queries == ['"the treaty" 2024 15%']


def test_search_dedupes_terms_case_insensitively():

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(
        text="NASA and nasa both confirmed the 2024 mission.",
        entities={"ORG": ["NASA"], "PRODUCT": ["nasa"]},
    )

    provider.search(claim)

    assert client.queries == ["NASA 2024"]


def test_search_falls_back_to_the_full_sentence_with_no_entities_or_figures():
    """
    EntityExtractor degrades to `{}` on an inference outage rather than
    raising (see entities.py) - a claim can legitimately reach here with
    no entities and no figures in its text. An empty query would still
    be sent to SearXNG otherwise, so this falls back to the full
    sentence instead of searching for nothing.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(
        text="  Officials confirmed the deal will proceed as planned.  ",
        entities={},
    )

    provider.search(claim)

    assert client.queries == ["Officials confirmed the deal will proceed as planned."]


def test_search_skips_entries_missing_url_or_title():

    client = FakeSearxngClient(results=[
        {"title": "Missing URL"},
        {"url": "https://example.com/b"},
        {"url": "https://example.com/c", "title": "Complete"},
    ])

    provider = SearchProvider(client=client)

    results = provider.search(create_claim())

    assert len(results) == 1
    assert results[0].url == "https://example.com/c"


def test_search_handles_unparsable_date():

    client = FakeSearxngClient(results=[
        {"url": "https://example.com/a", "title": "A", "publishedDate": "not-a-date"},
    ])

    provider = SearchProvider(client=client)

    results = provider.search(create_claim())

    assert results[0].published_at is None

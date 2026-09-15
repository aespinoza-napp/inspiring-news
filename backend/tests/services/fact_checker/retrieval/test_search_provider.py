from src.services.fact_checker.retrieval.search_provider import SearchProvider
from src.models.core.claim import ClaimFacts
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


def test_search_queries_by_identifying_terms_not_the_raw_sentence():
    """
    The raw claim sentence used to be the query. It is a poor one: a
    search engine matches it as a bag of words, so the terms that
    actually pin the event down - the organisation, the figure, the year
    - are diluted by the prose around them.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(
        text="  NASA discovered water on Mars in 2024, covering 40% of the pole.  ",
        entities={"ORG": ["NASA"]},
    )
    claim = claim.model_copy(update={
        "facts": ClaimFacts(figures=["40%"], dates=["2024"]),
    })

    provider.search(claim)

    affirmative = client.queries[0]

    assert "NASA" in affirmative
    # Quoted, so the engine matches it verbatim instead of treating the
    # most checkable part of the claim as an ignorable common token.
    assert '"40%"' in affirmative
    assert "2024" in affirmative
    assert "discovered water on Mars" not in affirmative


def test_search_also_runs_a_refutation_query():
    """
    Every query built from a claim is phrased affirmatively, which biases
    retrieval toward documents that agree with it. Without a second pass
    that can surface a contradiction, the retrieval step can only ever
    confirm.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    provider.search(create_claim(entities={"ORG": ["NASA"]}), language="es")

    assert len(client.queries) == 2
    assert "desmentido" in client.queries[1]
    assert client.languages == ["es", "es"]


def test_search_dedupes_the_same_url_across_both_queries():

    client = FakeSearxngClient(results=[
        {"url": "https://example.com/a", "title": "A"},
    ])

    provider = SearchProvider(client=client)

    results = provider.search(create_claim(entities={"ORG": ["NASA"]}))

    # Both passes returned it; it is one piece of evidence, not two.
    assert len(client.queries) == 2
    assert len(results) == 1


def test_search_records_domain_and_engines():

    client = FakeSearxngClient(results=[
        {
            "url": "https://www.example.com/a",
            "title": "A",
            "engines": ["bing", "brave"],
        },
    ])

    provider = SearchProvider(client=client)

    results = provider.search(create_claim())

    assert results[0].domain == "example.com"
    assert results[0].engines == ["bing", "brave"]


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

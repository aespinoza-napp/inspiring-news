from src.services.fact_checker.retrieval.search_provider import SearchProvider
from src.models.fact_checker.evidence import EvidenceOrigin

from tests.factories import create_claim
from tests.fact_checker.fakes import FakeSearxngClient


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


def test_search_uses_claim_text_as_query():

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(text="  NASA discovered water on Mars.  ")

    provider.search(claim)

    assert client.queries == ["NASA discovered water on Mars."]


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

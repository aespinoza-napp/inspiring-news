import time

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
    retrieval toward documents that agree with it. Without a pass that
    can surface a contradiction, the retrieval step can only ever
    confirm.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(entities={"ORG": ["NASA"]})

    provider.search(claim, language="es")

    kinds = [query.kind.value for query in provider.plan(claim, language="es")]

    assert "refutation" in kinds

    refutation = client.queries[kinds.index("refutation")]

    assert "desmentido" in refutation

    # Every query goes out in the claim's own language, not just the first.
    assert set(client.languages) == {"es"}


def test_search_asks_what_the_claim_says_and_not_only_who_it_is_about():
    """
    The anchor query alone retrieves the claim's *subject*. That is how a
    claim mentioning ACME came back with three pages on the etymology of
    the word - every name matched, the assertion appeared nowhere, and
    the model cited them as confirmation.
    """

    client = FakeSearxngClient(results=[])

    provider = SearchProvider(client=client)

    claim = create_claim(
        text="NASA discovered water on Mars in 2024.",
        entities={"ORG": ["NASA"]},
    )

    plan = provider.plan(claim)

    kinds = [query.kind.value for query in plan]

    assert kinds[0] == "anchor"
    assert "proposition" in kinds

    proposition = plan[kinds.index("proposition")].text

    # The assertion's own words, minus the anchor they belong to.
    assert "discovered" in proposition
    assert "water" in proposition
    assert "NASA" in proposition


def test_search_dedupes_the_same_url_across_every_query():

    client = FakeSearxngClient(results=[
        {"url": "https://example.com/a", "title": "A"},
    ])

    provider = SearchProvider(client=client)

    claim = create_claim(entities={"ORG": ["NASA"]})

    results = provider.search(claim)

    # Every pass returned it; it is one piece of evidence, not three.
    assert len(client.queries) == len(provider.plan(claim))
    assert len(results) == 1

    # ...and the result records that all of them found it, which is the
    # signal that separates a page about the claim from one about its
    # subject.
    assert set(results[0].found_by) == {"anchor", "proposition", "refutation"}


def test_the_queries_run_concurrently_rather_than_one_after_another():
    """
    A SearXNG round trip is seconds, not milliseconds, and the queries
    are independent. In sequence they were three times the wait for
    nothing.

    Measured as "more than one was in flight at once" rather than "all of
    them were": how many run together is capped by
    QUERY_MAX_CONCURRENCY, which is a tuning decision, while running them
    one at a time is the bug.
    """

    import threading

    lock = threading.Lock()
    in_flight = 0
    high_water = 0

    class ObservingClient(FakeSearxngClient):

        def search(self, query, max_results=None, language=None):

            nonlocal in_flight, high_water

            with lock:
                in_flight += 1
                high_water = max(high_water, in_flight)

            try:
                # Long enough that a sequential implementation cannot
                # overlap by accident, short enough not to slow the suite.
                time.sleep(0.05)
                return super().search(query, max_results, language)
            finally:
                with lock:
                    in_flight -= 1

    provider = SearchProvider(client=ObservingClient(results=[]))

    provider.search(create_claim(entities={"ORG": ["NASA"]}))

    assert high_water > 1


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


def test_search_ignores_results_that_are_not_web_pages():
    """
    Results are untrusted. A `javascript:` or `file:` URL is not evidence
    and would otherwise be scraped and rendered as a link.
    """

    client = FakeSearxngClient(results=[
        {"url": "javascript:alert(1)", "title": "Hostile", "content": "x"},
        {"url": "file:///etc/passwd", "title": "Local file", "content": "x"},
        {"url": "data:text/html,<b>x</b>", "title": "Inline", "content": "x"},
        {"url": "HTTPS://example.com/ok", "title": "Fine", "content": "x"},
    ])

    results = SearchProvider(client=client).search(create_claim())

    assert [item.url for item in results] == ["HTTPS://example.com/ok"]

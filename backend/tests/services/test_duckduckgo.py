import httpx
import pytest

from src.services.duckduckgo import DuckDuckGoClient, parse_results
from src.services.search import SearchUnavailableError, SearxngClient


class FakeResponse:

    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code


# The markup open-source DuckDuckGo clients read. Not a captured page: on
# 2026-09-30 every request from the development machine was challenged,
# so no real results page came back to capture.
RESULTS_PAGE = """
<html><body>
<div class="result results_links results_links_deep result--ad">
  <h2 class="result__title"><a class="result__a" href="https://ads.example/buy">An advert</a></h2>
  <a class="result__snippet" href="https://ads.example/buy">Buy now</a>
</div>
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.nasa.gov%2Fmars%2Fwater%3Fa%3D1&amp;rut=abc">
      NASA confirms <b>water</b> on Mars
    </a>
  </h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.nasa.gov%2Fmars%2Fwater">
    Liquid <b>water</b> flows on present-day Mars.
  </a>
</div>
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a" href="https://example.org/l/not-a-redirect">Direct link</a>
  </h2>
</div>
</body></html>
"""

# Trimmed from the page DuckDuckGo actually returned, with HTTP 202, to
# every keyless request from the development machine on 2026-09-30.
CHALLENGE_PAGE = """
<html><body>
<div class="anomaly-modal__box">
  <div class="anomaly-modal__description">Unfortunately, bots use DuckDuckGo too.</div>
  <div class="anomaly-modal__instructions">Please complete the following challenge to confirm
  this search was made by a human.</div>
  <div class="anomaly-modal__image">Select all squares containing a duck:</div>
</div>
</body></html>
"""

NO_RESULTS_PAGE = '<html><body><div class="no-results">No results.</div></body></html>'


def answering(monkeypatch, *responses):
    """httpx.get answering with each response in turn; returns the calls."""

    calls = []
    queue = list(responses)

    def fake_get(url, params=None, timeout=None, headers=None, follow_redirects=None):
        calls.append(params)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(httpx, "get", fake_get)

    return calls


def test_results_are_mapped_to_searxngs_shape_without_adverts():

    results = parse_results(RESULTS_PAGE)

    assert [item["url"] for item in results] == [
        "https://www.nasa.gov/mars/water?a=1",
        "https://example.org/l/not-a-redirect",
    ]
    assert results[0]["title"] == "NASA confirms water on Mars"
    assert results[0]["content"] == "Liquid water flows on present-day Mars."
    assert results[0]["engines"] == ["duckduckgo-direct"]
    assert results[1]["content"] == ""


def test_fetch_sends_the_query_with_the_claims_region(monkeypatch):

    calls = answering(monkeypatch, FakeResponse(RESULTS_PAGE))

    DuckDuckGoClient(url="https://ddg.test/html/").fetch("agua en Marte", language="es")

    assert calls == [{"q": "agua en Marte", "kl": "es-es"}]


def test_a_bot_challenge_is_unavailable_and_pauses_further_requests(monkeypatch):
    """
    A challenged IP asked again is a challenged IP asked again. After one
    challenge the client refuses locally, without sending anything.
    """

    calls = answering(monkeypatch, FakeResponse(CHALLENGE_PAGE, status_code=202))

    client = DuckDuckGoClient(url="https://ddg.test/html/")

    with pytest.raises(SearchUnavailableError, match="bot challenge"):
        client.fetch("anything")

    with pytest.raises(SearchUnavailableError, match="paused"):
        client.fetch("anything else")

    assert len(calls) == 1


def test_it_asks_again_once_the_pause_is_over(monkeypatch):

    calls = answering(
        monkeypatch,
        FakeResponse(CHALLENGE_PAGE, status_code=202),
        FakeResponse(RESULTS_PAGE),
    )

    client = DuckDuckGoClient(url="https://ddg.test/html/")
    client.COOLDOWN_SECONDS = 0

    with pytest.raises(SearchUnavailableError):
        client.fetch("q")

    assert len(client.fetch("q")) == 2
    assert len(calls) == 2


def test_a_real_empty_answer_is_empty(monkeypatch):

    answering(monkeypatch, FakeResponse(NO_RESULTS_PAGE))

    assert DuckDuckGoClient(url="https://ddg.test/html/").fetch("q") == []


def test_a_page_it_does_not_recognise_is_unavailable_not_empty(monkeypatch):
    """
    Changed markup parses to nothing. Reported as "nothing found", it
    would be the 2026-09-25 outage again: every claim an honest-looking
    UNVERIFIED.
    """

    answering(monkeypatch, FakeResponse("<html><body><div>Something new</div></body></html>"))

    with pytest.raises(SearchUnavailableError, match="markup"):
        DuckDuckGoClient(url="https://ddg.test/html/").fetch("q")


def test_a_network_error_is_unavailable(monkeypatch):

    def refuse(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", refuse)

    with pytest.raises(SearchUnavailableError, match="connection refused"):
        DuckDuckGoClient(url="https://ddg.test/html/").fetch("q")


# ----------------------------------------------------------------------
# As SearxngClient's fallback
# ----------------------------------------------------------------------


class StubFallback:

    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.queries = []

    def fetch(self, query, language=None):
        self.queries.append((query, language))
        if self.error:
            raise self.error
        return list(self.results)


SEARXNG_DOWN = {
    "results": [],
    "unresponsive_engines": [["brave", "too many requests"]],
}


class JsonResponse:

    def __init__(self, data):
        self._data = data
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_the_fallback_answers_when_searxng_cannot(monkeypatch):

    monkeypatch.setattr(httpx, "get", lambda *a, **k: JsonResponse(SEARXNG_DOWN))

    fallback = StubFallback(results=[{"url": "https://a.com", "title": "A", "engines": ["duckduckgo-direct"]}])

    results = SearxngClient(base_url="http://s", fallback=fallback).search("q", language="en")

    assert [item["url"] for item in results] == ["https://a.com"]
    assert fallback.queries == [("q", "en")]


def test_the_fallback_is_not_asked_when_searxng_answers(monkeypatch):

    monkeypatch.setattr(
        httpx, "get",
        lambda *a, **k: JsonResponse({"results": [{"url": "https://s.com", "title": "S"}]}),
    )

    fallback = StubFallback(results=[{"url": "https://a.com", "title": "A"}])

    SearxngClient(base_url="http://s", fallback=fallback).search("q")

    assert fallback.queries == []


def test_both_routes_failing_is_unavailable_and_names_both(monkeypatch):

    monkeypatch.setattr(httpx, "get", lambda *a, **k: JsonResponse(SEARXNG_DOWN))

    fallback = StubFallback(error=SearchUnavailableError("DuckDuckGo answered with a bot challenge"))

    with pytest.raises(SearchUnavailableError) as raised:
        SearxngClient(base_url="http://s", fallback=fallback).search("q")

    assert "brave" in str(raised.value)
    assert "bot challenge" in str(raised.value)


def test_a_fallback_answer_is_remembered_like_any_other(monkeypatch):

    monkeypatch.setattr(httpx, "get", lambda *a, **k: JsonResponse(SEARXNG_DOWN))

    fallback = StubFallback(results=[{"url": "https://a.com", "title": "A"}])

    client = SearxngClient(base_url="http://s", fallback=fallback)

    client.search("q")
    client.search("q")

    assert len(fallback.queries) == 1


def test_the_fact_checkers_search_falls_back_to_duckduckgo_by_default():

    from src.services.fact_checker.retrieval.search_provider import SearchProvider

    assert isinstance(SearchProvider().client.fallback, DuckDuckGoClient)


def test_the_fallback_can_be_switched_off(monkeypatch):

    from src.config.settings import settings
    from src.services.fact_checker.retrieval.search_provider import SearchProvider

    monkeypatch.setattr(settings, "DUCKDUCKGO_FALLBACK_ENABLED", False)

    assert SearchProvider().client.fallback is None

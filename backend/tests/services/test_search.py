import httpx

from src.services.search import SearxngClient


class FakeResponse:

    def __init__(self, json_data=None, status_code=200, raise_exc=None):
        self._json_data = json_data
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc

    def json(self):
        if self._json_data is None:
            raise ValueError("invalid json")
        return self._json_data


def test_search_sends_the_raw_query_with_no_retrieval_filters(monkeypatch):
    """
    Traceability check for what actually leaves the process: captures the
    exact request SearxngClient builds so it's visible in one place,
    rather than having to read the method to find out.

    As of this test, the request carries no information-retrieval
    tuning at all - no `language` (SearXNG supports it; News.language is
    known upstream and never passed down), no `time_range` (most claims
    are about one specific recent event), no `categories`, no
    `safesearch`, no phrase quoting or boolean operators. `q` is exactly
    `claim.text.strip()` - a full natural-language sentence, stopwords
    and all - handed to SearXNG's default engine mix as-is.

    This is a deliberate pin, not an endorsement: if evidence recall is
    weak, this request is the first place to look, and this test is
    what stops that diagnosis from requiring a debugger. Adding real
    filtering should update this assertion, not work around it.
    """

    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse(json_data={"results": []})

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    # Unstripped on purpose: SearxngClient does not trim its input either -
    # whatever string it's handed becomes `q` verbatim. Stripping happens
    # one layer up, in SearchProvider.search().
    client.search("  Does the new treaty violate Article 5 of the charter?  ")

    assert captured["url"] == "http://localhost:8080/search"
    assert captured["params"] == {
        "q": "  Does the new treaty violate Article 5 of the charter?  ",
        "format": "json",
    }
    assert captured["headers"] == {
        "User-Agent": "InspiringNewsBot/1.0 (fact-checker)"
    }


def test_search_returns_results(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        return FakeResponse(json_data={
            "results": [
                {"url": "https://a.com", "title": "A"},
                {"url": "https://b.com", "title": "B"},
            ]
        })

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    results = client.search("some claim")

    assert len(results) == 2
    assert results[0]["url"] == "https://a.com"


def test_search_truncates_to_max_results(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        return FakeResponse(json_data={
            "results": [{"url": f"https://{i}.com", "title": str(i)} for i in range(10)]
        })

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    results = client.search("some claim", max_results=3)

    assert len(results) == 3


def test_search_returns_empty_on_http_error(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        return FakeResponse(raise_exc=httpx.HTTPStatusError(
            "error", request=None, response=None,
        ))

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    assert client.search("some claim") == []


def test_search_returns_empty_on_timeout(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    assert client.search("some claim") == []


def test_search_returns_empty_on_invalid_json(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        return FakeResponse(json_data=None)

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    assert client.search("some claim") == []

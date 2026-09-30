import httpx
import pytest

from src.services.search import SearchUnavailableError, SearxngClient


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


def test_search_is_unavailable_on_http_error(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        return FakeResponse(raise_exc=httpx.HTTPStatusError(
            "error", request=None, response=None,
        ))

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    with pytest.raises(SearchUnavailableError):
        client.search("some claim")


def test_search_is_unavailable_on_timeout(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    with pytest.raises(SearchUnavailableError):
        client.search("some claim")


def test_search_is_unavailable_on_invalid_json(monkeypatch):

    def fake_get(url, params=None, timeout=None, headers=None):
        return FakeResponse(json_data=None)

    monkeypatch.setattr(httpx, "get", fake_get)

    client = SearxngClient(base_url="http://localhost:8080")

    with pytest.raises(SearchUnavailableError):
        client.search("some claim")


# ----------------------------------------------------------------------
# Engines that did not answer
#
# Measured 2026-09-25: 68 of 69 queries came back empty with Brave and
# Google rate-limited and DuckDuckGo answering with a CAPTCHA. SearXNG
# said so in `unresponsive_engines`; nothing here read it.
# ----------------------------------------------------------------------


DOWN = {
    "results": [],
    "unresponsive_engines": [["brave", "too many requests"], ["duckduckgo", "CAPTCHA"]],
}


def test_an_empty_answer_with_engines_down_is_unavailable_not_empty(monkeypatch, caplog):
    """
    The 2026-09-25 outage: every claim came back UNVERIFIED as if the web
    had nothing on it. Nobody had looked - and now that says so.
    """

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(json_data=DOWN))

    with caplog.at_level("WARNING"):
        with pytest.raises(SearchUnavailableError) as raised:
            SearxngClient(base_url="http://s").search("anything")

    assert "brave (too many requests)" in caplog.text
    assert "duckduckgo (CAPTCHA)" in caplog.text
    assert "brave" in str(raised.value)


def test_an_empty_answer_with_every_engine_up_is_a_real_empty_answer(monkeypatch):

    monkeypatch.setattr(
        httpx, "get",
        lambda *a, **k: FakeResponse(json_data={"results": [], "unresponsive_engines": []}),
    )

    assert SearxngClient(base_url="http://s").search("anything") == []


def test_results_with_some_engines_down_are_still_results(monkeypatch):

    data = {
        "results": [{"url": "https://a.com", "title": "A"}],
        "unresponsive_engines": [["brave", "too many requests"]],
    }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(json_data=data))

    assert len(SearxngClient(base_url="http://s").search("anything")) == 1


def test_health_reports_which_engines_answered_and_which_did_not(monkeypatch):

    data = {
        "results": [
            {"url": "https://a.com", "engines": ["wikipedia"]},
            {"url": "https://b.com", "engines": ["wikipedia", "bing"]},
        ],
        "unresponsive_engines": [["brave", "too many requests"]],
    }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(json_data=data))

    health = SearxngClient(base_url="http://s").health("renewable energy", "en")

    assert health["ok"] is True
    assert health["results"] == 2
    assert health["engines"] == ["bing", "wikipedia"]
    assert health["unresponsive"] == [{"engine": "brave", "reason": "too many requests"}]


def test_health_with_every_engine_down_is_not_ok(monkeypatch):

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(json_data=DOWN))

    health = SearxngClient(base_url="http://s").health()

    assert health["ok"] is False
    assert len(health["unresponsive"]) == 2


def test_health_reports_searxng_itself_unreachable(monkeypatch):

    def refuse(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", refuse)

    health = SearxngClient(base_url="http://s").health()

    assert health["ok"] is False
    assert "connection refused" in health["error"]


# ----------------------------------------------------------------------
# Repeated queries are sent once
#
# An article's claims share a subject and plan the same anchor query,
# concurrently. Each one sent was another request SearXNG forwarded to
# engines that suspend it for "too many requests".
# ----------------------------------------------------------------------


def counting_get(monkeypatch, json_data):

    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        calls.append(params)
        return FakeResponse(json_data=json_data)

    monkeypatch.setattr(httpx, "get", fake_get)

    return calls


RESULTS = {"results": [{"url": f"https://e{i}.com", "title": str(i)} for i in range(6)]}


def test_a_repeated_query_is_sent_once(monkeypatch):

    calls = counting_get(monkeypatch, RESULTS)

    client = SearxngClient(base_url="http://s")

    first = client.search("the anchor", language="en")
    second = client.search("the anchor", language="en")

    assert len(calls) == 1
    assert first == second


def test_the_same_query_in_another_language_is_a_different_query(monkeypatch):

    calls = counting_get(monkeypatch, RESULTS)

    client = SearxngClient(base_url="http://s")

    client.search("NASA", language="en")
    client.search("NASA", language="es")

    assert [call["language"] for call in calls] == ["en", "es"]


def test_a_cached_answer_is_cut_to_each_callers_limit(monkeypatch):

    counting_get(monkeypatch, RESULTS)

    client = SearxngClient(base_url="http://s")

    assert len(client.search("q", max_results=6)) == 6
    assert len(client.search("q", max_results=2)) == 2
    assert len(client.search("q", max_results=5)) == 5


def test_an_empty_answer_is_not_remembered(monkeypatch):
    """
    Empty is most often every engine suspended. Remembering it would turn
    a three-minute suspension into ten minutes of UNVERIFIED.
    """

    calls = counting_get(monkeypatch, DOWN)

    client = SearxngClient(base_url="http://s")

    for _ in range(2):
        with pytest.raises(SearchUnavailableError):
            client.search("q")

    assert len(calls) == 2


def test_an_expired_answer_is_asked_again(monkeypatch):

    calls = counting_get(monkeypatch, RESULTS)

    client = SearxngClient(base_url="http://s")
    client.CACHE_TTL_SECONDS = 0

    client.search("q")
    client.search("q")

    assert len(calls) == 2


def test_the_cache_is_bounded(monkeypatch):

    counting_get(monkeypatch, RESULTS)

    client = SearxngClient(base_url="http://s")
    client.CACHE_MAX_ENTRIES = 3

    for query in ("a", "b", "c", "d"):
        client.search(query)

    assert [key[0] for key in client._cache] == ["b", "c", "d"]


def test_two_claims_asking_the_same_query_at_once_send_it_once(monkeypatch):
    """
    Claims run concurrently, so the second asker usually arrives while
    the first is still waiting on SearXNG - which a cache alone misses.
    """

    import threading
    import time

    entered = threading.Event()
    release = threading.Event()
    calls = []

    def slow_get(url, params=None, timeout=None, headers=None):
        calls.append(params)
        entered.set()
        release.wait(5)
        return FakeResponse(json_data=RESULTS)

    monkeypatch.setattr(httpx, "get", slow_get)

    client = SearxngClient(base_url="http://s")
    answers = []

    def ask():
        answers.append(client.search("the anchor"))

    first = threading.Thread(target=ask)
    first.start()
    entered.wait(5)

    second = threading.Thread(target=ask)
    second.start()

    # Long enough for the second asker to reach the wait.
    time.sleep(0.2)
    release.set()

    first.join(5)
    second.join(5)

    assert len(calls) == 1
    assert len(answers) == 2
    assert answers[0] == answers[1] != []


def test_a_failed_request_does_not_leave_the_query_stuck(monkeypatch):

    def refuse(*args, **kwargs):
        raise RuntimeError("not an httpx error")

    monkeypatch.setattr(httpx, "get", refuse)

    client = SearxngClient(base_url="http://s")

    try:
        client.search("q")
    except RuntimeError:
        pass

    assert client._inflight == {}

    counting_get(monkeypatch, RESULTS)

    assert client.search("q") != []


def test_a_caller_waiting_on_a_failed_request_gets_the_failure_too(monkeypatch):
    """
    The second asker shares the first one's request. If that request
    failed, an empty list would tell the second claim "nothing exists" -
    the exact confusion this error was added to end.
    """

    import threading
    import time

    entered = threading.Event()
    release = threading.Event()

    def slow_down(url, params=None, timeout=None, headers=None):
        entered.set()
        release.wait(5)
        return FakeResponse(json_data=DOWN)

    monkeypatch.setattr(httpx, "get", slow_down)

    client = SearxngClient(base_url="http://s")
    outcomes = []

    def ask():
        try:
            outcomes.append(client.search("the anchor"))
        except SearchUnavailableError:
            outcomes.append("unavailable")

    first = threading.Thread(target=ask)
    first.start()
    entered.wait(5)

    second = threading.Thread(target=ask)
    second.start()

    time.sleep(0.2)
    release.set()

    first.join(5)
    second.join(5)

    assert outcomes == ["unavailable", "unavailable"]
    assert client._inflight == {}

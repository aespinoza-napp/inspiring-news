import re
import unicodedata
import threading
import time
from dataclasses import dataclass, field
from logging import getLogger

import httpx

from src.config.settings import settings
from src.services.concurrency import SEARXNG

logger = getLogger(__name__)


# The share of a query's words its best result has to hold for the search to
# have answered at all. Measured 2026-11-03 on 12 of the train half's
# proposition queries: when Bing searched only the first word, the best
# result of every query held 0-29% of the words; through the fixed engines,
# 44-100%. Not per-run: it says whether a service works, not how to judge.
MIN_QUERY_COVERAGE = 0.35

# A query needs this many words for the share to mean anything.
MIN_QUERY_WORDS = 3

# Not asked of the scholarly engines, which answer anything with whatever
# paper shares a word; what is being checked is whether the web answered.
# Also what `search_science_engines: drop` leaves out of the evidence. Held
# equal to the science engines of docker/searxng/settings.yml by a test.
SCHOLARLY_ENGINES = frozenset({"arxiv", "crossref", "semantic scholar", "pubmed"})
_SCHOLARLY_ENGINES = SCHOLARLY_ENGINES


def only_scholarly(item: dict) -> bool:
    """Whether only the scholarly engines returned this result: none of the web engines did."""

    engines = set(item.get("engines") or [])

    return bool(engines) and engines <= SCHOLARLY_ENGINES

# Refutation queries end in these: they say what is being looked for, not
# what the results must be about.
_QUERY_NOISE = frozenset({
    "fact", "check", "debunked", "false", "verificacion", "desmentido", "falso", "bulo",
    "the", "and", "for", "del", "las", "los", "con", "por", "una",
})

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _words(text: str) -> set[str]:

    decomposed = unicodedata.normalize("NFKD", (text or "").lower())

    return set(_WORD.findall("".join(char for char in decomposed if not unicodedata.combining(char))))


def best_query_coverage(query: str, results: list[dict]) -> float | None:
    """
    The largest share of `query`'s words any one result's title and summary
    hold; None when that says nothing (no results, or too short a query).
    """

    terms = {word for word in _words(query) if len(word) >= 3} - _QUERY_NOISE

    if len(terms) < MIN_QUERY_WORDS or not results:
        return None

    general = [item for item in results if not _SCHOLARLY_ENGINES & set(item.get("engines") or [])]

    return max(
        len(terms & _words(f"{item.get('title') or ''} {item.get('content') or ''}")) / len(terms)
        for item in (general or results)
    )


class SearchUnavailableError(RuntimeError):
    """
    The search could not be carried out, as opposed to having found
    nothing. On 2026-09-25, 68 of 69 queries came back empty because the
    engines behind SearXNG were rate-limited or CAPTCHA'd, and every
    affected claim came out as an honest-looking UNVERIFIED. The same
    split `LLMUnavailableError` makes for the model.
    """


@dataclass
class _InFlight:

    done: threading.Event = field(default_factory=threading.Event)

    results: list[dict] = field(default_factory=list)

    # Set when the leader's request could not be answered, so a caller
    # that waited on it gets the same failure rather than a plain [].
    error: SearchUnavailableError | None = None


class SearxngClient:

    # A repeated query is answered from memory for this long. An article's
    # claims share their subject, so they plan the same anchor query -
    # and every one sent is another request SearXNG forwards to engines
    # that suspend it for "too many requests". Minutes, not forever:
    # a verdict depends on today's web, and the analysis cache that never
    # expires is already a known problem (CLAUDE.md).
    CACHE_TTL_SECONDS = 600

    CACHE_MAX_ENTRIES = 512

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        fallback=None,
    ):
        self.base_url = (base_url or settings.SEARXNG_URL).rstrip("/")
        self.timeout = timeout or settings.SEARXNG_TIMEOUT

        # A second route asked only when SearXNG cannot answer - anything
        # with `fetch(query, language) -> list[dict]` that raises
        # SearchUnavailableError when it cannot answer either
        # (DuckDuckGoClient). None by default: the fact-checker's
        # SearchProvider passes one in, the source probe does not, since
        # it exists to report on SearXNG itself.
        self.fallback = fallback

        self._lock = threading.Lock()

        # (query, language) -> (stored at, every result SearXNG returned)
        self._cache: dict[tuple, tuple[float, list[dict]]] = {}

        # (query, language) -> the request already in flight for it
        self._inflight: dict[tuple, _InFlight] = {}

        # How this thread's last `search` was answered, for the timing a
        # claim reports per query (`last_route`). Per thread because each
        # query of a claim runs in its own and asks right after its call.
        self._route = threading.local()

    def last_route(self) -> str | None:
        """
        How the last `search` on this thread was answered: `cache` (from
        memory), `shared` (another claim's request for the same query),
        `searxng`, `duckduckgo` (the fallback) or `failed`. A query that
        took 0.0 s and one that took 4 s are both "a search"; this says
        which one did the work.
        """

        return getattr(self._route, "value", None)

    def search(
        self,
        query: str,
        max_results: int | None = None,
        language: str | None = None,
    ) -> list[dict]:
        """
        One query's results, sent at most once at a time and remembered
        for CACHE_TTL_SECONDS.

        Claims are checked concurrently, so two of an article's claims
        asking the same anchor query usually do so at the same moment -
        a cache alone would miss both. The second waits for the first
        instead, and is never holding a SearXNG permit while it waits
        (the bounded-pool deadlock, src/services/concurrency.py).

        Only answers with results are kept. An empty one is most often
        every engine suspended, and remembering it would stretch a
        three-minute suspension into ten minutes of UNVERIFIED.

        Raises SearchUnavailableError when SearXNG could not be reached,
        or answered with nothing while reporting engines down: "the web
        has nothing on this" cannot be told from "nobody looked". An
        empty answer with no engine reported down is a real empty answer.
        """

        limit = max_results or settings.SEARXNG_MAX_RESULTS

        key = (query, language)

        with self._lock:

            cached = self._cache.get(key)

            if cached and time.monotonic() - cached[0] < self.CACHE_TTL_SECONDS:
                self._route.value = "cache"
                return cached[1][:limit]

            flight = self._inflight.get(key)
            leader = flight is None

            if leader:
                flight = self._inflight[key] = _InFlight()

        if not leader:
            flight.done.wait()

            self._route.value = "failed" if flight.error else "shared"

            if flight.error:
                raise flight.error

            return flight.results[:limit]

        try:
            flight.results = self._fetch_or_fall_back(query, language)
        except SearchUnavailableError as exc:
            self._route.value = "failed"
            flight.error = exc
            raise
        finally:
            with self._lock:

                del self._inflight[key]

                if flight.results:

                    if len(self._cache) >= self.CACHE_MAX_ENTRIES:
                        # Insertion order: the oldest entry goes first.
                        del self._cache[next(iter(self._cache))]

                    self._cache[key] = (time.monotonic(), flight.results)

            flight.done.set()

        return flight.results[:limit]

    def _fetch_or_fall_back(self, query: str, language: str | None) -> list[dict]:
        """
        SearXNG, and the fallback only when SearXNG could not answer.

        Inside the shared flight, so a query two claims ask at once goes
        to the fallback once too, and its answer is cached like any other.
        The SearXNG permit is already released here: nothing waits on the
        fallback's permit while holding SearXNG's.
        """

        try:
            results = self._fetch(query, language)
            self._route.value = "searxng"
            return results
        except SearchUnavailableError as primary:

            if self.fallback is None:
                raise

            try:
                results = self.fallback.fetch(query, language)
                self._route.value = "duckduckgo"
            except SearchUnavailableError as secondary:
                raise SearchUnavailableError(
                    f"{primary}; fallback: {secondary}"
                ) from secondary

            logger.info(
                "SearXNG could not answer %r; the fallback returned %d results",
                query,
                len(results),
            )

            return results

    def _fetch(self, query: str, language: str | None) -> list[dict]:
        """
        The request itself: every result SearXNG returned, [] when it
        answered and found nothing, SearchUnavailableError when it could
        not answer.
        """

        params = {
            "q": query,
            "format": "json",
        }

        # 7 of the 12 configured sources publish in Spanish, and until
        # this was passed every query was answered as if it were English -
        # so a Spanish claim competed against the English-language web for
        # the same handful of result slots.
        if language:
            params["language"] = language

        # The permit is held around this one request and nothing else.
        # A claim's queries now run concurrently and several claims run
        # at once, so without a ceiling here a single article can put a
        # dozen simultaneous requests on SearXNG - which answers them by
        # querying real upstream engines that rate-limit it, not us. See
        # src/services/concurrency.py for why the limit lives with the
        # resource rather than with the caller.
        try:
            with SEARXNG.permit():

                response = httpx.get(
                    f"{self.base_url}/search",
                    params=params,
                    timeout=self.timeout,
                    headers={
                        "User-Agent": "InspiringNewsBot/1.0 (fact-checker)"
                    },
                )

            response.raise_for_status()

            data = response.json()

        except (httpx.HTTPError, ValueError) as exc:

            logger.warning(
                "SearXNG search failed for %r: %s",
                query,
                exc,
            )

            raise SearchUnavailableError(
                f"SearXNG request failed: {exc or type(exc).__name__}"
            ) from exc

        results = data.get("results", [])

        # SearXNG says which upstream engines failed, and an empty answer
        # with every engine down is not "the web has nothing on this" -
        # but the two looked identical from here. Measured 2026-09-25: 68
        # of 69 queries came back empty with Brave and Google rate-limited
        # and DuckDuckGo answering with a CAPTCHA (docs/decisions/retrieval.md).
        unresponsive = data.get("unresponsive_engines") or []

        if unresponsive and not results:

            down = ", ".join(f"{name} ({reason})" for name, reason in unresponsive)

            logger.warning(
                "SearXNG returned nothing for %r; engines down: %s",
                query,
                down,
            )

            # Any engine down, not every one: SearXNG does not say which
            # engines answered with nothing, so an empty answer with even
            # one failure cannot be read as "nothing exists". Reporting
            # search as unavailable when it half-worked is the honest
            # error of the two - the other one is a verdict.
            raise SearchUnavailableError(f"no results; engines down: {down}")

        # Results about something else are not an answer either, and they
        # look like one to everything downstream (off_subject).
        best = best_query_coverage(query, results)

        if best is not None and best < MIN_QUERY_COVERAGE:

            logger.warning(
                "SearXNG answered %r with %d results about something else: the best holds %.0f%% of its words",
                query,
                len(results),
                best * 100,
            )

            raise SearchUnavailableError(
                f"answered about something else: the best of {len(results)} results "
                f"holds {best:.0%} of the query's words"
            )

        return results

    def health(self, query: str = "news", language: str | None = None) -> dict:
        """
        One real query, reported rather than consumed: how many results,
        which engines answered and which did not, and why. For the source
        probe - every fact check depends on this one service.
        """

        params = {"q": query, "format": "json"}

        if language:
            params["language"] = language

        started = time.perf_counter()

        try:
            with SEARXNG.permit():
                response = httpx.get(
                    f"{self.base_url}/search",
                    params=params,
                    timeout=self.timeout,
                    headers={"User-Agent": "InspiringNewsBot/1.0 (fact-checker)"},
                )

            response.raise_for_status()
            data = response.json()

        except (httpx.HTTPError, ValueError) as exc:
            return {
                "query": query,
                "ok": False,
                "results": 0,
                "engines": [],
                "unresponsive": [],
                "error": str(exc) or type(exc).__name__,
                "ms": round((time.perf_counter() - started) * 1000),
            }

        results = data.get("results", [])

        engines = sorted({
            engine
            for item in results
            for engine in (item.get("engines") or [])
        })

        # A count says nothing: ten results about the query's first word
        # read as a healthy search for as long as nobody looked at them.
        coverage = best_query_coverage(query, results)
        off_subject = coverage is not None and coverage < MIN_QUERY_COVERAGE

        return {
            "query": query,
            "ok": bool(results) and not off_subject,
            "results": len(results),
            "queryCoverage": None if coverage is None else round(coverage, 2),
            "offSubject": off_subject,
            "engines": engines,
            "unresponsive": [
                {"engine": name, "reason": reason}
                for name, reason in (data.get("unresponsive_engines") or [])
            ],
            "error": None,
            "ms": round((time.perf_counter() - started) * 1000),
        }

import time
from logging import getLogger

import httpx

from src.config.settings import settings
from src.services.concurrency import SEARXNG

logger = getLogger(__name__)


class SearxngClient:

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.SEARXNG_URL).rstrip("/")
        self.timeout = timeout or settings.SEARXNG_TIMEOUT

    def search(
        self,
        query: str,
        max_results: int | None = None,
        language: str | None = None,
    ) -> list[dict]:

        limit = max_results or settings.SEARXNG_MAX_RESULTS

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

            return []

        results = data.get("results", [])

        # SearXNG says which upstream engines failed, and an empty answer
        # with every engine down is not "the web has nothing on this" -
        # but the two looked identical from here. Measured 2026-09-25: 68
        # of 69 queries came back empty with Brave and Google rate-limited
        # and DuckDuckGo answering with a CAPTCHA (docs/decisions/retrieval.md).
        unresponsive = data.get("unresponsive_engines") or []

        if unresponsive and not results:
            logger.warning(
                "SearXNG returned nothing for %r; engines down: %s",
                query,
                ", ".join(f"{name} ({reason})" for name, reason in unresponsive),
            )

        return results[:limit]

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

        return {
            "query": query,
            "ok": bool(results),
            "results": len(results),
            "engines": engines,
            "unresponsive": [
                {"engine": name, "reason": reason}
                for name, reason in (data.get("unresponsive_engines") or [])
            ],
            "error": None,
            "ms": round((time.perf_counter() - started) * 1000),
        }

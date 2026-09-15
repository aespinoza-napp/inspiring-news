from logging import getLogger

import httpx

from src.config.settings import settings

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

        try:
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

        return data.get("results", [])[:limit]

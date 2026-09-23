from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.models.scraper.extraction import ExtractionResult
from src.models.core.source import NewsSource
from src.services.scraper.request_stats import Outcome

class DiscoveryStrategy(ABC):

    @abstractmethod
    def discover(
        self,
        source: NewsSource,
        topics: list[str],
    ) -> list[str]:
        ...


@dataclass
class ExtractionAttempt:
    """
    One try at extracting a page, and why it came to what it did.

    `extract()` answers only "article or None", which is all the pipeline
    needs - but None hides whether the server said 403, the connection
    timed out or the page simply had no article in it, and those call for
    entirely different fixes.
    """

    result: ExtractionResult | None

    outcome: Outcome

    status: int | None = None

    error: str | None = None


class ExtractionStrategy(ABC):

    @abstractmethod
    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> ExtractionResult | None:
        ...

    def attempt(
        self,
        source: NewsSource,
        url: str,
    ) -> ExtractionAttempt:
        """
        `extract()` plus the reason. Strategies that can tell a failure
        apart override this; the default can only say whether text came
        back, which is still better than nothing.
        """

        try:
            result = self.extract(source, url)
        except Exception as exc:
            return ExtractionAttempt(None, Outcome.ERROR, error=str(exc))

        if result is None:
            return ExtractionAttempt(None, Outcome.NO_CONTENT)

        return ExtractionAttempt(result, Outcome.OK)

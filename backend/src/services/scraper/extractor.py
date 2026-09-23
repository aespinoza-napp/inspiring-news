import time

from src.config.thresholds import PipelineThresholds
from src.models.core.news import News
from src.processors.nlp.language import LanguageDetector
from src.models.core.source import NewsSource

from .strategies.trafilatura import TrafilaturaStrategy
from .strategies.beautifulsoup import BeautifulSoupStrategy
from .strategies.playwright_extraction import PlaywrightExtractionStrategy

from .extraction_validator import ExtractionValidator
from .request_stats import Outcome, Purpose, RequestStats, request_stats

class ExtractorService:

    def __init__(self, stats: RequestStats | None = None):

        self.strategies = [
            TrafilaturaStrategy(),
            #BeautifulSoupStrategy(),
            #PlaywrightExtractionStrategy()
        ]

        # Every attempt is counted here, not in the strategies: this is
        # the one place every fetch in the process passes through, and
        # the only one that knows both why the page was wanted and
        # whether what came back was long enough to use.
        self.stats = stats if stats is not None else request_stats

    def extract(
        self,
        source: NewsSource,
        url: str,
        thresholds: PipelineThresholds | None = None,
        purpose: Purpose | str = Purpose.ARTICLE,
    ) -> News | None:

        for strategy in self.strategies:

            started = time.perf_counter()

            attempt = strategy.attempt(
                source,
                url,
            )

            extracted = attempt.result
            outcome = attempt.outcome
            error = attempt.error

            if extracted is not None and not ExtractionValidator.is_valid(extracted, thresholds):
                outcome = Outcome.TOO_SHORT
                error = f"body too short ({len(extracted.body.strip())} characters)"
                extracted = None

            self.stats.record(
                url,
                outcome,
                purpose=purpose,
                strategy=type(strategy).__name__,
                source_id=source.id,
                status=attempt.status,
                error=error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

            if extracted is None:
                continue

            news = News(
                source_id=source.id,
                url=url,
                # Detected from the body, with the source's declared
                # language as the fallback for text too short or too
                # ambiguous to call. The body is what gets scored, so the
                # body is what decides - a Spanish article syndicated by
                # an "en" source must still be scored in Spanish.
                language=LanguageDetector.detect(
                    extracted.body,
                    fallback=source.language,
                ),
                title=extracted.title,
                author=extracted.author,
                published_at=extracted.published_at,
                content=extracted.body,
                image_url=extracted.lead_image,
            )
            return news

        return None

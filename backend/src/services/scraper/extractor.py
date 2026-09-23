import time

from src.config.thresholds import PipelineThresholds
from src.models.core.news import News
from src.processors.nlp.language import LanguageDetector
from src.models.core.source import NewsSource

from .strategies.base import ExtractionAttempt, ExtractionStrategy
from .strategies.trafilatura import TrafilaturaStrategy
from .strategies.beautifulsoup import BeautifulSoupStrategy
from .strategies.playwright_extraction import PlaywrightExtractionStrategy

from .extraction_validator import ExtractionValidator
from .request_stats import Outcome, Purpose, RequestStats, request_stats

# Failures a different parser can fix: the page arrived, but this parser
# found no article in it, or not enough of one. The next strategy gets a
# go - on the same HTML if it can read HTML.
PARSE_FAILURES = {Outcome.NO_CONTENT, Outcome.TOO_SHORT, Outcome.ERROR}

# Refusals a real browser can sometimes get past (bot walls, rate
# limits). Another HTML parser would only be refused the same way, so
# the cascade skips straight to strategies that render.
BROWSER_MAY_HELP = {401, 403, 429}

# Who is worth a browser. Evidence is fetched by the handful for every
# claim and already falls back to its search snippet when a page cannot
# be read, so rendering each one would multiply the cost of the most
# expensive step by the most frequent purpose for very little.
BROWSER_PURPOSES = {Purpose.ARTICLE.value, Purpose.INGESTION.value, Purpose.ENRICHMENT.value}


# The fields a parser can find the text and still miss.
METADATA_FIELDS = ("title", "author", "published_at", "summary", "lead_image")


def _fill_metadata(result, source: NewsSource, page):
    """
    Fills whatever metadata the winning parser missed from the same page,
    at no extra request. Trafilatura often finds an article's text and
    not its byline; BeautifulSoup reads meta tags and JSON-LD, where the
    byline usually is. What the winner found is never overwritten.
    """

    if page is None or all(getattr(result, name) for name in METADATA_FIELDS):
        return result

    try:
        found = BeautifulSoupStrategy.metadata(source, page)
    except Exception:
        return result

    missing = {
        name: found[name]
        for name in METADATA_FIELDS
        if not getattr(result, name) and found.get(name)
    }

    if not missing:
        return result

    # Validated, not model_copy'd: the page gives a date as text, and the
    # model is what turns it into the datetime everything else expects.
    return type(result).model_validate({**result.model_dump(), **missing})


class ExtractorService:
    """
    Tries strategies cheapest first, and stops the moment trying further
    cannot help.

    The order is the cost: trafilatura (one request), then BeautifulSoup
    (no request - it reads the page trafilatura fetched), then a headless
    browser (a full render; never for evidence pages). A page that is not
    there - a 404, a timeout, a host that does not resolve - is not there
    for any of them, so those end the cascade instead of spending more
    requests on a source that is already failing.
    """

    def __init__(self, stats: RequestStats | None = None):

        self.strategies: list[ExtractionStrategy] = [
            TrafilaturaStrategy(),
            BeautifulSoupStrategy(),
            PlaywrightExtractionStrategy(),
        ]

        # Every extraction is counted here, not in the strategies: this
        # is the one place every fetch in the process passes through, and
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

        started = time.perf_counter()

        page = None
        html_unavailable = False
        browser_only = False

        tried: list[str] = []
        sent = 0
        last: ExtractionAttempt | None = None
        winner: str | None = None
        extracted = None
        unavailable: str | None = None

        purpose_value = purpose.value if isinstance(purpose, Purpose) else str(purpose)

        for strategy in self.strategies:

            if strategy.reads_html and (html_unavailable or browser_only):
                continue

            if not strategy.reads_html and purpose_value not in BROWSER_PURPOSES:
                continue

            tried.append(type(strategy).__name__)

            attempt = strategy.attempt(
                source,
                url,
                page if strategy.reads_html else None,
            )

            sent += attempt.sent

            # A strategy that cannot run here (a browser not installed)
            # says nothing about the page: keep the previous step's
            # outcome as the answer, and say why nothing further was tried.
            if attempt.outcome == Outcome.UNAVAILABLE:
                unavailable = attempt.error
                continue

            if attempt.result is not None and not ExtractionValidator.is_valid(attempt.result, thresholds):
                attempt = ExtractionAttempt(
                    None,
                    Outcome.TOO_SHORT,
                    attempt.status,
                    f"body too short ({len(attempt.result.body.strip())} characters)",
                    page=attempt.page,
                    sent=attempt.sent,
                )

            last = attempt

            if attempt.result is not None:
                extracted = _fill_metadata(attempt.result, source, attempt.page)
                winner = tried[-1]
                break

            if strategy.reads_html:
                page = attempt.page or page
                # The fetch itself failed: every HTML parser after this
                # one would need the same page and not get it.
                html_unavailable = page is None

            if attempt.outcome in PARSE_FAILURES:
                continue

            if attempt.outcome == Outcome.HTTP_ERROR and attempt.status in BROWSER_MAY_HELP:
                browser_only = True
                continue

            break

        error = None

        if not winner:
            error = last.error if last else "no strategy could run"
            if unavailable:
                error = f"{error}; not escalated: {unavailable}" if last else unavailable

        self.stats.record(
            url,
            last.outcome if last else (Outcome.UNAVAILABLE if unavailable else Outcome.ERROR),
            purpose=purpose,
            strategy=winner or "",
            source_id=source.id,
            status=last.status if last else None,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            sent=sent,
            tried=tried,
        )

        if extracted is None:
            return None

        return News(
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

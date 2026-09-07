# Scraper

Article discovery and content extraction, composed by `scraper.py` (`Scraper`) into a two-step
pipeline: find URLs, then fetch and extract each one.

- **`discovery.py`** (`DiscoveryService`) — finds article URLs for a given `NewsSource`. Implemented via
  `strategies/rss.py` (`RSSDiscoveryStrategy`), driven by each source's `rss_url` (see
  `backend/data/sources/`).
- **`extractor.py`** (`ExtractorService`) — fetches a single URL's full content. Implemented via
  `strategies/trafilatura.py` (`TrafilaturaStrategy`). This is the piece reused directly by the
  fact-checker's evidence scraper (`services/fact_checker/retrieval/scraper.py`) — don't duplicate it.
- **`extraction_validator.py`** (`ExtractionValidator`) — a cheap sanity gate (minimum body length)
  applied after extraction, before an article is accepted.

**`strategies/beautifulsoup.py`, `strategies/playwright_discover.py`, and
`strategies/playwright_extraction.py` are unimplemented placeholders** — intended for JS-rendered
sources (`NewsSource.requires_javascript`), but not wired into `ExtractorService`/`DiscoveryService` yet
(`BeautifulSoupStrategy.extract()` just returns `None`). Don't assume they do anything until they're
actually implemented and wired in.

`strategies/base.py` defines the `ExtractionStrategy`/`DiscoveryStrategy` interfaces both real and
placeholder strategies implement.

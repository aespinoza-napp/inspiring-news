# How a page is extracted, and what it costs

Read this before adding an extraction strategy, changing the order of
the cascade, or touching what `ExtractorService` counts.

## Cheapest first, and only escalate when it can help

`ExtractorService` tries strategies in order of cost:

| Step | Strategy | Cost |
|---|---|---|
| 1 | `TrafilaturaStrategy` | one HTTP request |
| 2 | `BeautifulSoupStrategy` | **none**: it parses the HTML step 1 already fetched |
| 3 | a browser (Playwright, once wired) | a full render: a second request, JavaScript, seconds |

The fetch is shared (`fetcher.py`, `strategies/html.py`). Before this,
each strategy fetched for itself, so a fallback parser doubled the
requests sent to exactly the sites that were already hardest to scrape.

A failed step only goes to the next one when a different strategy could
plausibly succeed:

| Outcome of a step | What happens next |
|---|---|
| `no_content`, `too_short`, `error` (the page came back, no article found in it) | next strategy; an HTML parser gets the same page |
| `http_error` 401 / 403 / 429 (bot wall, rate limit) | skip the HTML parsers, which would get the same refusal; go to a browser |
| any other `http_error` (404, 500...), `timeout`, `connection_error`, `blocked` | **stop**. No strategy can fix a page that is not there |

So a dead source costs one request per URL, not one per strategy.

## Metadata is filled from the same page

When a strategy finds the text but not the title, author or date,
`_fill_metadata` reads them from the same HTML with BeautifulSoup (JSON-LD
first, then meta tags) at no extra request. It never overwrites what the
winning strategy found. The page came from the missing-title incident:
every article in the lake had been analysed with `title: None`
(`retrieval.md`).

## What BeautifulSoup looks at, in order

1. `metadata.selectors` in the source's YAML (`title`, `body`, `author`,
   `date`): for layouts nothing else guesses.
2. What the page declares about itself: the JSON-LD `NewsArticle`
   (`articleBody` is often the full text behind a teaser) and meta tags.
3. The usual containers (`article`, `[itemprop=articleBody]`, `main`),
   then whichever element holds the most paragraph text of its own.

## What is counted

One entry per **extraction** (a page wanted), not per strategy attempt:
its final outcome, the strategy that produced the article, every strategy
tried, and the HTTP requests actually sent (0 for a guard refusal, 1 for
trafilatura + BeautifulSoup, 2 once a browser steps in). The `/scraper`
page shows all four. "Which step does the work for this source" is the
`strategies` count; a source that only ever succeeds via the last step is
a candidate for `requires_javascript`.

## Checked against real sources (2026-09-23)

Two articles from each configured feed, both parsers on the same page:
trafilatura produced the article for El Mundo, La Vanguardia, NASA, CNN
and BBC. BeautifulSoup extracted comparable text on the same pages (and on
a CNN live blog picked a much smaller block, which is why it is second).
El País answered 403: the case the browser step exists for. Five feeds
could not be read at all (National Geographic, RTVE and SINC return
malformed XML; EFE and Reuters timed out), and ABC's feed links point to
its homepage - discovery problems, not extraction ones.

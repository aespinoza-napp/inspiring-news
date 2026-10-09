# How a page is extracted, and what it costs

Read this before adding an extraction strategy, changing the order of
the cascade, or touching what `ExtractorService` counts.

## Cheapest first, and only escalate when it can help

`ExtractorService` tries strategies in order of cost:

| Step | Strategy | Cost |
|---|---|---|
| 1 | `TrafilaturaStrategy` | one HTTP request |
| 2 | `BeautifulSoupStrategy` | **none**: it parses the HTML step 1 already fetched |
| 3 | `PlaywrightExtractionStrategy` | a full render: a second request, JavaScript, seconds - and never for evidence pages |

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

## The browser step

`PlaywrightExtractionStrategy` only *renders*: the rendered HTML goes
through the same trafilatura and BeautifulSoup `parse()`, so there is one
notion of where an article is, not a third one written against the
Playwright API.

- **Never for evidence.** Evidence pages are fetched by the handful for
  every claim and already fall back to their search snippet;
  `BROWSER_PURPOSES` keeps the render to articles, ingestion and the
  enrichment page.
- **Guarded like every other fetch.** The start URL is checked before a
  browser launches; every request the page makes goes through the URL
  guard (cached per host); the navigation's redirect chain is checked
  after it lands, and content that arrived by way of a forbidden address
  is discarded. Route handlers do not see redirect hops, which is why that
  last check exists. **Gap:** a forbidden hop has already been *requested*
  by then - its response is thrown away, but a blind request to it was
  made. Closing that needs a proxy in front of the browser.
- **Capped.** `BROWSER_MAX_CONCURRENCY` (default 2), a `settings` ceiling
  like the others. One Chromium per render: Playwright's sync objects are
  thread-bound and extraction runs on many threads.
- **Optional.** The `browser` extra plus `playwright install chromium`.
  Absent, the attempt is `unavailable`, and the extraction keeps the
  previous step's outcome with "not escalated: ..." in its error, so the
  stats still say why the page failed.

Checked live (2026-09-23): a page whose text is built by JavaScript
(quotes.toscrape.com/js) has 29 characters in its HTML; trafilatura's
result is refused as too short, BeautifulSoup finds nothing, the browser
renders 1,097 characters - 2 requests, 11s on a cold start. An ordinary
NASA page never gets past trafilatura: 1 request, no browser.

## Routing: sources recognised by domain, and `requires_javascript`

A URL posted to `/analyze` arrives with the generic `"web"` source, so an
El País article was never treated as El País. `ExtractorService` now
matches it to the enabled configured source by domain (its host or a
subdomain; the most specific wins), so per-source `selectors` and
`requires_javascript` apply, and the stored article carries the real
`source_id`.

`requires_javascript: true` puts the browser first: the two cheap steps
are known to fail for that site and would each cost a request finding
that out again. They still follow the browser, for when none is
installed. Evidence never renders, flag or not.

Every configured source is `false` today. The flag is meant to be
set from evidence, not guessed: the `/scraper` page flags a domain whose
every article came from the browser.

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

## Discovery and ingestion

`POST /ingest` (`services/ingestion_service.py`) turns configured sources
into analysis jobs; since 2026-10-05 the usual way in is `/discover`,
which scopes discovery to up to three topic groups and lets a person or
the AI choose what is analysed. What discovery drops for that - off-mission
sections, links filed under another topic, Spanish items without a topic
word, section-page navigation - is in `selection.md`. Discovery is
cheapest first too:

1. the source's `rss_url`, fetched through `Fetcher` (URL guard and a
   timeout - feedparser's own HTTP has neither) and parsed by feedparser;
2. only if that finds nothing new: the source's **JSON listing**
   (`json_feed`: WHO's news API) and then its **Google News sitemap**
   (`news_sitemap_url`: CNN's), each only for a source that names one -
   titled and timed like a feed (`strategies/listings.py`);
3. then the source's **topic section pages** (below), or the sections it
   names for a group (`sections`: Smithsonian's `/science-nature/` for
   Environment, where a guessed `/food/` gave food travel);
4. last: trafilatura's feed discovery, on the `rss_url` and then the
   homepage - lenient with broken XML, and able to find the feed a site
   advertises today.

**Since 2026-10-09.** trafilatura was second, but from 2026-10-04 it had
not run at all: `DiscoveryService` asks a step for `discover_items` first,
and it had inherited the feed step's, so it re-read the dead feed. Section
pages were the fallback in practice. Run for real it was worse than them -
ABC's homepage feeds gave a Culture round 38 links of every section,
unfiltered and untitled, and WHO's dead feed 21 items from 2024-2025 that
read as undated (WHO dates its links day first: `date_from_url` now reads
that too) - so it is last, and narrowed Spanish sources' links must name a
topic in their slug. A section page's links are now **titled with the text
they are linked with** (ABC 94 of 96, National Geographic 42/44, France 24
59/59), not made up from their slugs: the mission screen, the ranking and
the same-story check read those titles. WHO's feed's newest item was from
February and CNN's stopped in 2024; ABC's `sitemap_news.xml` still lists
2021 and WHO's sitemap index dates from 2018, so neither is configured.

Then, before anything is queued:

- **Article shape**, in any language: the old English section-name
  patterns kept 0 of El Mundo's 26 feed entries, 5 of El País's 149 and
  0 of NASA's 10. A date in the path or a four-word slug now counts.
- **Topic**, for English sources only. Every TOPICS keyword is English;
  against a Spanish feed they matched at random. Spanish articles are left
  to the admission filter, which rejects before any LLM call. Short
  keywords match whole words and acronyms in capitals (`keyword_in`):
  as substrings, "ai" matched "said" and "detained", "who" (the WHO) every
  "who", "art" "start" - 85 of 419 matches on the 2026-10-09 English feeds,
  every one politics, sport or war let into Science or Health. A source
  all of whose groups were asked for (WHO in Health) needs no keyword.
- **Not already in the lake** (host and path, so tracking parameters do
  not make an old article new; a syndicated article is queued once).
- **At most `perSource`** per source per run; the rest are reported as
  deferred.

Each queued URL is an ordinary job with purpose `ingestion`: it shows on
`/live`, lands in the lake, and is counted apart from posted articles.
`POST /ingest` is behind `STORAGE_API_KEY`, since one call can start dozens
of full analyses.

Live, 2026-09-23: discovery went from 4 of 12 sources producing links to
9 (El Mundo 26, El País 146, La Vanguardia 132, ABC 42 via its homepage,
CNN 25, BBC 17, NASA 9). A NASA article went discovered → queued →
extracted (title, four authors, date) → enriched → fact-checked →
stored in 52s, and the next run reported it as already stored. The feed
URLs for National Geographic, Reuters, RTVE and SINC return **404** -
earlier read here as "malformed XML", which was feedparser parsing the
404 page - and need replacing in their YAMLs.

## Time to reception: when was it published, when did we have it

Added 2026-10-04. Both extractors cut the publication time to a date, and
discovery threw away the feed item's time, so "how long after publication
did we get this?" could only be answered to the day. Now:

- **The feed's time is kept.** `RSSDiscoveryStrategy.discover_entries`
  returns each URL with feedparser's `published_parsed` (or
  `updated_parsed`), UTC; `DiscoveryResult.published` carries it. Checked
  live the same day: all 1,248 URLs from the 29 feeds that answered had one.
  Topic pages and trafilatura's feed search give none.
- **The page's time is kept,** to the minute, when the page states one
  (`article:published_time`, JSON-LD `datePublished`, `<time datetime>`):
  `ExtractionResult.published_time`, stored in the raw record as
  `article.metadata.publishedTime`. A bare date is not a time, and neither
  is exactly midnight - date-only sites write `T00:00:00`. Only for stored
  articles (`TIMED_PURPOSES`: article, ingestion), since it costs one more
  parse of the page when trafilatura won. Live: 6 of 7 sampled articles
  stated their time to the second. `published_at` keeps meaning the date.
- **When ingestion first saw each URL** is recorded
  (`services/scraper/sightings.py`, `lake/stats/sightings.json`): first
  sighting kept, keyed by host and path, deferred URLs included. Only
  ingestion records: the probe, `/sources` and the labelling batch see
  articles that are never queued.

`services/freshness.py` (`GET /scraper/freshness`, the Time to reception
panel on `/scraper`) joins those with the lake's own times - the first raw
`fetched_at`, the first processed record, the first publishable
exploitation record - and reports per article and per source, in hours:
**seen** (published -> first seen: the feed and our polling), **queue**
(first seen -> fetched: our backlog), **reception** (published -> fetched)
and **available** (published -> on the reader). Precise times only; an
article with only a date gets `receptionDays`, apart. A negative lag (a
wrong timezone, a rewritten feed time) is counted, not averaged; a page
time with no timezone is flagged. The lake's naive timestamps are read as
the local time of the machine that wrote them.

What it means today: ingestion runs only when someone presses Ingest, so
"seen" is mostly the time until the next press. Queue and available are
the pipeline's own. Articles already in the lake before 2026-10-04 have no
precise time and no sighting; the numbers start with the next ingestion.

## Topic section pages: articles without a feed

`strategies/topic_pages.py`. Four feed URLs went 404 and their homepages
advertise no feed, so those sources produced nothing although their sites
were up. Every news site files articles under sections, and the sections
this project wants are the ones `TOPIC_URL_PATTERNS` already names. The
step reads them as HTML and keeps the article-shaped links on them:

1. **Sections the homepage links to** (a short path ending in a topic
   pattern) - they exist, so nothing is spent on a guess.
2. **Then guesses**, `base_url + pattern`, one per topic, capped at six
   pages in all - and none at all when the homepage refused us: EFE (403)
   and Reuters (401) refused every guess the same way.

Spanish sources also get `TOPIC_SECTION_PATTERNS_ES` (`/ciencia/`,
`/salud/`, `/cultura/`...). It is a separate table on purpose:
`TOPIC_URL_PATTERNS` also decides whether a *feed* link looks like an
article, and that behaviour on the English feeds is settled.

A link is kept when it is on the source's host or a subdomain of it
(NASA's science sections live on `science.nasa.gov`), is not itself a
section, and passes the same article-shape test as feed links.

## The source probe: is each source up?

`services/scraper/source_probe.py`, `POST /scraper/probe` and the "Source
health" panel on `/scraper`. The request stats only know about pages
someone happened to ask for; the probe asks on purpose, per source: the
feed (both feed steps), the topic pages (always - how many links they add
is the point), and a real extraction of `perSource` sampled links, split
between the two, with purpose `probe`. It calls a source **up** (feed
links and at least half the sample extracted), **degraded** (articles can
be had but not the normal way: dead feed rescued by topic pages, or under
half extracting) or **down** (nothing extracted). It also sends one query
per language to SearXNG and reports which engines answered
(`retrieval.md`).

It runs on a background thread (409 while one is running), is behind
`STORAGE_API_KEY`, and keeps the last report in
`lake/stats/source_probe.json`. Never on a timer: one run is ~10-15
requests per source.

First run, 2026-09-25, 6 articles per source, from the host (no Chromium
installed, so nothing escalated to the browser):

| | Sources | |
|---|---|---|
| up | ABC, BBC, CNN, El Mundo, La Vanguardia, NASA | feed works, 5-6 of 6 extracted |
| degraded | National Geographic, RTVE, SINC | feed dead; **topic pages gave 113, 115 and 64 links, 6/6 extracted each** |
| down | EFE (403 on everything), Reuters (401 on everything), El País (feed gives 138 links, every article 403) | bot walls |

The feeds gave 395 links in all; the topic pages **1,272 more** that no
feed had. 53 of 60 sampled articles extracted, all by trafilatura - with
a title on 53, a date on 52 and an author on 44 (the metadata fix above
holds). El País and EFE are what the browser step is for; the host run
could not try it.

**2026-10-06: EFE and Reuters disabled** (`enabled: false`). In the
container's scraper stats since 2026-09-23 neither delivered once (21 and
24 attempts: 403, 401, no links); the probe that day found EFE's homepage
403 with no feed, Reuters' homepage 401 and its feed 404. EFE had
answered the 2026-09-29 host probe through its section pages, but never
the container. Their YAMLs stay: the reliability map reads every file,
so their pages still rank as evidence (`backend/data/sources/README.md`).

## Checked against real sources (2026-09-23)

Two articles from each configured feed that could be read, both parsers
on the same page:
trafilatura produced the article for El Mundo, La Vanguardia, NASA, CNN
and BBC. BeautifulSoup extracted comparable text on the same pages (and on
a CNN live blog picked a much smaller block, which is why it is second).
El País answered 403: the case the browser step exists for. Five feeds
could not be read at all (National Geographic, Reuters, RTVE and SINC
404; EFE timed out), and ABC's feed links point to its homepage -
discovery problems, not extraction ones (see "Discovery and ingestion").

## Checking every source: `/sources`

Ingestion cannot tell a source whose articles stopped extracting from
one with nothing new: it skips what is stored and hands the rest to a
full analysis. `SourceCheckService` (`services/scraper/source_check.py`,
`POST /sources/check`) answers "is every configured page still working?"
directly: discovery, then a few links through the same cascade, purpose
`source_check` (it escalates to the browser exactly as ingestion would,
and is counted apart on `/scraper`). Nothing is stored or analysed.
Disabled sources are checked too.

A source is **working** when every sample extracted with a title, author
and date; **partial** when some failed or one lacked those; **broken**
when discovery found nothing or no sample extracted.

First run, 2026-09-24, two per source: 6 working (ABC, BBC, CNN, El
Mundo, La Vanguardia, NASA), every sample with title, author and date,
all by trafilatura. 6 broken: EFE, National Geographic, Reuters, RTVE
and SINC discover nothing (the feed URLs above, plus EFE's); El País
discovers 147 links and answers **403 to the headless browser too**, so
`requires_javascript` would not fix it.

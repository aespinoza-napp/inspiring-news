# News sources

One YAML file per source, loaded by `src/repositories/source_repository.py` (`SourceRepository`) into
`src/models/core/source.py`'s `NewsSource` model. **Adding a new source means adding a YAML file here —
not writing code.**

## Schema

```yaml
id: bbc                      # unique identifier, used as a key elsewhere (e.g. article.source_id)
name: BBC
base_url: https://www.bbc.com
rss_url: http://feeds.bbci.co.uk/news/rss.xml   # optional — required for RSS discovery to work
search_url: https://www.bbc.co.uk/search?q={query}   # optional
language: en
country: UK
source_type: news            # news | blog | government | academic | social
reliability_index: 0.94      # 0.0-1.0, editorial reliability — feeds the fact-checker's evidence ranking
                              # (see EvidenceRanker in src/services/fact_checker/ranking/) and the
                              # duplicate/relatedness scoring's source-quality signal
enabled: true
requires_javascript: false   # true: articles go to the headless browser first, skipping the two
                              # cheap steps that are known to fail for this site. Set it when the
                              # /scraper page says "only the browser gets articles here"
                              # (docs/decisions/scraping.md)
tags:
  - general
  - world
metadata:                    # free-form, strategy-specific hints
  extractor: trafilatura
  discovery:
    - rss
    - search
  selectors:                 # optional CSS selectors for BeautifulSoup, step two of the
    body: .article-body      # extraction cascade - only needed when trafilatura and the
    author: .byline          # generic heuristics both miss this site's layout
    title: h1.headline       # (see docs/decisions/scraping.md)
    date: time.published
```

Only `id`, `name`, and `base_url` are required — everything else has a default (see `NewsSource` for
exact defaults).

`enabled: false` keeps a source out of ingestion, the probe and posted-URL recognition — but **not** out
of the reliability map, which reads every YAML. That makes it the way to *rate* a domain without
*ingesting* it: `newtral.yaml` and `maldita.yaml` are disabled because a fact-check quotes the claim it
debunks, and claim extraction would take that quote for the article's own claim. `efe.yaml` and
`reuters.yaml` are disabled because they refused every request (HTTP 403 and 401) from 2026-09-23 to
2026-10-06; their pages still rank as evidence.

**One source per domain.** Reliability and posted-URL recognition are both looked up by domain, so a
second YAML on the same domain (BBC Mundo on bbc.com, The Conversation's Spanish edition) silently
overrides the first. `tests/repositories/test_source_repository.py` fails on it.

**Before adding a source,** check its feed yields article links *and* that two of them extract: the
`/sources` page does both for every YAML. English feeds are filtered by topic keyword, so a feed with
nothing on the configured topics discovers zero links even when it works. Feeds tried on 2026-09-28
and left out: NPR, Phys.org and El Confidencial (feed fine, articles would not extract), ScienceDaily,
DW Español and CSIC (no article links), AP (403).

`reliability_index` matters beyond discovery: `EvidenceRanker` looks it up by domain (via
`SourceRepository`) when scoring a piece of evidence during fact-checking, with a neutral default for
unknown domains — so a source's reliability here directly affects how much its articles are trusted as
corroborating evidence for other claims.

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
requires_javascript: false   # true routes to a JS-capable strategy once one exists — see
                              # src/services/scraper/README.md; currently a no-op either way
tags:
  - general
  - world
metadata:                    # free-form, strategy-specific hints
  extractor: trafilatura
  discovery:
    - rss
    - search
```

Only `id`, `name`, and `base_url` are required — everything else has a default (see `NewsSource` for
exact defaults). Set `enabled: false` to keep a source's YAML around without it being loaded.

`reliability_index` matters beyond discovery: `EvidenceRanker` looks it up by domain (via
`SourceRepository`) when scoring a piece of evidence during fact-checking, with a neutral default for
unknown domains — so a source's reliability here directly affects how much its articles are trusted as
corroborating evidence for other claims.

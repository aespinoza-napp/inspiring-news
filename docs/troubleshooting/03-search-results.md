# 3. Search results

**The part:** SearXNG's answers to the three queries (DuckDuckGo directly when
a query fails), merged with the internal corpus, become the candidates
(`retrieval/evidence_retriever.py`, `search_provider.py`).

## Finding (4 Nov 2026, 20 train claims, run `cc053417c0cb`)

For each claim, was the source that settled it for Claude (`claude.jsonl`,
`sources`), or the annotator's reference link, among the pipeline's candidates
(14-24 a claim)? Compared by domain:

| | Claims |
|---|---:|
| Claude's settling source's domain among the candidates | **6 of 20** (fact009 Wikipedia, fact012 ScienceDaily, fact038 NSIDC and NASA, fact063 Ember, fact065 okdiario, fact082 GitHub) |
| A reference link's domain among the candidates | 7 of 20 |
| Claude's source among the candidates, and the pipeline right | 4 of those 6 (fact012, fact038, fact063, fact065) |
| Claude's source not among them, and the pipeline right anyway | 5 of 14 (fact008, fact015, fact021, fact036, fact064: other sources that also held the fact, e.g. fact036's Tampa outlets) |

Examples of what the search returned instead:

- **fact037**: Florida tourism and a 2010 cholera story (NYT), CNN and
  WorldAtlas pages on Florida. No Florida Health report, the primary source
  that holds the figure. The queries had neither "dengue" nor "212" (see
  [02-queries.md](02-queries.md)).
- **fact062 / fact064**: no Ember page among the candidates, though Ember's 8 Sep
  analysis is the source of both claims and its domain is the reference. The
  pipeline found Ember for fact063, whose query named it ("China Ember").
- **fact016**: bookshop.org, Barnes & Noble, Project Gutenberg, the App Store:
  "Book Bunk" read as books.
- **fact008 / fact009**: Spanish outlets carrying EFE's wire story word for
  word (abc.es, efe.com, noticiassin.com). Every one repeats the article's own
  "frente a las costas de Chile". Since 3 Nov, `evidence_independence` rejects
  a source that repeats the sentence verbatim, yet abc.es and efe.com were still
  kept in today's replay: their text differs from the claim's by more than the
  copy test allows.

## Caveats

- Different engines: Claude used its own WebSearch, the pipeline SearXNG on 29
  Oct. Which engines answered that day is in the run's events, not checked here.
  On 4 Nov, four of SearXNG's engines were refusing this machine (DuckDuckGo
  CAPTCHA, Google suspended, PubMed timing out, Yep erroring). Part of the gap
  may be the engine. Most of it is the query: the pipeline's queries for
  fact037 contain neither "dengue" nor "212", and cannot find a page about
  them on any engine.
- Since 3 Nov the search counts an answer as failed when its best result holds
  under 35% of the query's words, and the engines changed. This run is from
  before that.

## What to try

Search-side, so searched tries: the query changes in
[02-queries.md](02-queries.md) first, since they cause most of this. Then a
source-type hint for claims with an official figure (health department,
statistics office, the study), via the restatement in
[01-what-to-look-for.md](01-what-to-look-for.md).

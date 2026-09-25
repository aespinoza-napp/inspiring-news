# What gets sent to SearXNG, and what counts as evidence

Read this before changing query building, ranking weights, or the
pertinence gate.

## The failure this exists to prevent

A Spanish claim — the Coyote's mail-order ACME purchases standing for the
consumerism the United States threw itself into after the Second World
War — was returned **FALSE at 83% confidence**, citing three sources.

The three sources explained that *acme* is a Greek word meaning "peak" or
"culmination".

Nothing in the pipeline was in a position to notice, and each stage
behaved exactly as designed:

- The query was built from the claim's anchors: `coyote ACME Estados
  Unidos Segunda Guerra Mundial`. Every one of those appears on a page
  explaining what ACME means. The assertion — consumerism,
  representation, post-war — was not in the query at all.
- The pre-rank funnel scored candidates by embedding similarity over
  title and snippet. A page *about ACME* is a near-perfect embedding
  match for a claim *mentioning ACME*, so the etymology pages were the
  ones worth scraping.
- Ranking orders sources. It had no way to refuse one.
- `min_evidence_for_verdict` counted evidence items. It did not ask what
  they were about.
- The model was shown three documents and asked to judge the claim
  against them. It did.

The single most important consequence: **the honest answer was
`UNVERIFIED`**, and every stage was structurally incapable of producing
it.

## Three queries, not one

`retrieval/query_builder.py` plans a set:

| Kind | What it asks | Why |
|---|---|---|
| `anchor` | entities, quoted figures, dates | Precision on the subject. Unchanged — it was never wrong, only insufficient. |
| `proposition` | the assertion's own content words, plus two anchors | The part the etymology pages do not have. |
| `refutation` | the anchor query plus per-language refutation terms | Every query built from a claim is phrased affirmatively, so the others can only ever confirm. |

The proposition query keeps a couple of anchors deliberately. Content
words alone swing the query to the opposite failure — broad essays on
consumerism with no connection to this event — and a document has to
satisfy both to be worth reading.

The queries run concurrently and their ranked lists are fused by
**reciprocal rank fusion**, not concatenated. Concatenating and deduping
by URL ordered candidates by *which query ran first*, so the anchor
query's eighth hit outranked the proposition query's first and the
funnel scraped the wrong five. Fusion orders by how much the queries
agreed, and `found_by` records which of them returned a page at all —
which is precisely the anchor-page-versus-real-source distinction, made
visible.

## Terms: anchors and content, kept disjoint

`services/fact_checker/terms.py` is shared by query building and by
lexical ranking on purpose. A term the planner thinks is worth searching
for is exactly the term a source has to contain to count as addressing
the claim; two copies of that judgement drift, and the drift is
invisible.

- **anchors** — entities, figures, dates. These pin an event.
- **content** — the remaining words after stopword and query-noise
  filtering. These carry the assertion.

`claim_terms()` keeps the two **disjoint**, and that was worth a bug to
learn: an entity's own words also survive content-word filtering, so
`ACME` and `Estados Unidos` were counted once as anchors and again as
content. Anchors are weighted double, so the etymology page — every name
present, nothing else — scored 0.5 and passed a 0.25 gate. With the sets
disjoint it scores 0.36, and 0.18 after the semantic half.

`query_noise` is a new per-language lexicon field, kept apart from
`stopwords` because that set is tuned to tell the two languages apart for
the language detector and padding it with shared vocabulary would make it
worse at the one job it has.

## Ranking gained a fourth factor

```
relevance = 0.45·semantic + 0.20·lexical + 0.20·recency + 0.15·reliability
```

`lexical` is term coverage. It is the counterweight to `semantic`, which
cannot tell a page that addresses the assertion from one that merely
shares its subject. The other three weights were reduced to make room;
the group still sums to 1.0, which is why it stays environment-only.

## The pertinence gate

```
pertinence = 0.5·semantic + 0.5·lexical
```

Deliberately free of recency and reliability: a recent, reliable page
about something else is still about something else, and letting those two
lift it over the gate is the exact mistake the gate exists to stop.

Below `evidence_min_pertinence` (default 0.25) a source is cut **at
ranking, before the LLM sees it**, with a reason that names the figure.
It therefore cannot be cited, counted toward `min_evidence_for_verdict`,
or treated as corroboration. The Coyote claim comes back `UNVERIFIED`.

It is a **per-run threshold**, unlike the weights, because it is the knob
that trades a confident wrong answer for an honest one:

- **raise it** when a run is citing sources that are merely on-topic;
- **lower it** when claims come back unverified with plausible sources
  sitting in the cut list.

The default is low on purpose. This is a floor against off-target
retrieval, not a relevance ranking — cutting real evidence here turns a
checkable claim into `UNVERIFIED`, which is a different way of being
useless.

The pre-rank funnel scores candidates with the same semantic/lexical
split, so it spends its five page fetches on pages that can survive the
gate rather than on ones already destined to be cut.

## A sentence is checked inside its article

"En agosto de 2026 ya había convocatorias en Ciudad de México con premios
económicos" came from an article about *farmear aura* battles in public
squares. It came back **TRUE at 84%**, confirmed by the Mexico City
marathon's prize money.

Three things had to be true at once for that to happen, and all three
were:

- **The title was never extracted.** trafilatura 2.x leaves title,
  author and date out of its JSON unless called with `with_metadata=True`.
  Every article in the lake had `title: None`, so every fallback built on
  the headline was dead. The strategy's tests mocked `extract()`, which is
  why nobody noticed; one test now runs it for real.
- **Restoring the subject required the claim to have no entity.** This
  one names a city, so it was searched as the city.
- **The LLM was shown the lone sentence**, so it had no way to know which
  contests the article meant.

Now `terms.subject_terms` takes the headline words the article's own
keywords agree on (`Farmear`, `aura`, but not `volvió` or `viral`), or the
top keyword when there's no headline. It restores them whenever the claim
doesn't already mention them: as the leading anchors (so every query
carries them and lexical coverage counts them) and in front of the
embedded claim text (so the funnel and the pertinence gate compare
sources with the claim in its article's sense). The verifier also gets
the headline and opening, with a rule that evidence about a different
event is `unrelated` even when it shares a place, a date or a figure.

With the subject in the queries, the search engine's best answer was the
article itself, which the model then cited as support. The article's own
URL is now dropped from its web results as well as from the internal
corpus (host and path compared, so `www.`, a trailing slash or tracking
parameters don't hide it).

`POST /verify-claim` has no article, so none of this applies there: a
bare claim is searched as it stands.

## Why web evidence so often comes back empty (measured 2026-09-25)

Better queries cannot help when the search itself returns nothing, and
most of the time it did. Measured with 24 claims from the x-fact pilot
set (12 Spanish, 12 English), the pipeline's own query planner and the
pipeline's own extractor:

| | |
|---|---|
| Queries sent to SearXNG | 69 |
| Queries that came back **empty** | **68** |
| Claims left with **zero** web evidence | 23 of 24 |

SearXNG says why in its own answer (`unresponsive_engines`), and until
this date nothing read it:

- **Brave and Google CSE: "too many requests".** SearXNG scrapes them
  from one IP with no API key. One article sends 3 queries per claim for
  2-4 claims, all at once, so a single analysis is a burst of 6-12; after
  a 429 SearXNG suspends the engine (180 s here) and every query in that
  window gets nothing from it.
- **DuckDuckGo: a CAPTCHA on every request**, or a timeout - 104
  CAPTCHAs and 231 timeouts in the three hours before the measurement,
  before any of it was sent.
- **Wikidata: times out** (251 timeouts in the same window). Wikipedia
  answers, but rarely has a page for a specific claim.

So the default engine mix of a self-hosted SearXNG is, from this
machine, a coin toss that mostly lands on nothing. The burst of the
measurement itself made Brave's suspension worse; the DuckDuckGo and
Wikidata failures predate it.

When search *did* answer (the four journalled runs of 2026-09-21), the
second loss is reading the pages: **11 of 20** top results were
extracted. The rest were social networks (Facebook, Instagram, Reddit),
a paywall (nytimes.com) and sites that refuse bots - and evidence never
escalates to the browser, by design (`scraping.md`). Those fall back to
their search snippet.

The third, smaller one is the queries for a claim with no named entity:
x-fact's "El 65% del total del presupuesto está comprendido ahí" plans
the anchor query `"65%"`. In the pipeline the article's headline is
restored to the claim (above), which is why this matters less there than
in a bare `/verify-claim`.

What changed: `SearxngClient.search` logs the engines that were down
whenever an answer is empty, and `SearxngClient.health` - run by the
source probe on `/scraper` - reports which engines answered. What would
fix it, in order of leverage:

1. **An engine with an API key** (Brave Search API, Google Programmable
   Search) configured in `searxng/settings.yml`: a key is not
   rate-limited per scraping IP.
2. **Disable the engines that only fail** (DuckDuckGo, Wikidata) so they
   stop costing a timeout on every query.
3. **Report "search unavailable" apart from "nothing found"**, the way
   `llm_unreachable` separates a dead LLM from `UNVERIFIED`: today a
   claim with every engine down is `UNVERIFIED`, which reads as a
   judgement about the claim.

## What is still not fixed

- **The LLM is still not asked whether a source is on-point.** The gate
  is embedding and term arithmetic; it catches a page about a different
  subject, not a page about the right subject making a different claim.
  A real stance/entailment step is the next thing.
- **Accuracy is still unmeasured.** There is no labelled set, so the
  threshold defaults are reasoned, not fitted.
- **Only the 12 configured domains have a real reliability rating.**

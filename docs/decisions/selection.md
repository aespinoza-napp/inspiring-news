# Discovering by topic, and choosing what to analyse

Built 2026-10-05. Until then ingestion had one way in: `POST /ingest`
read every enabled source and sent every new article it found straight to
a full analysis - a scrape, an enrichment and an LLM call per claim each.
Two things changed:

1. **Discovery is scoped to topics.** Pick up to three of the five topic
   groups; only the sources that cover them are read, and only for their
   topics.
2. **A choice sits between discovery and analysis.** Discovery lists
   candidates with what their feed says about them; a person, or an LLM
   reading titles and summaries, chooses at most twenty; only those are
   analysed.

The page is `/discover`; the API is `POST /ingest/rounds` and its
children; the code is `src/services/selection/` (README there) on top of
`src/services/ingestion_service.py`.

## The five groups, defined once

`src/config/topics.py` `TOPIC_GROUPS` - society, science, environment,
culture, health - the groups the labeller already balanced over. They
were copied in three places (the labeller, `evaluation/dataset.py`,
`evaluation_summary.py`); the backend now has one definition, which the
two backend modules import, and the labeller keeps its own copy (it
imports nothing from `backend/`), held equal by tests.

Groups rather than the 23 topics because several topics have one or two
sources: a topic picker would often return nothing. **At most three**
(`MAX_GROUPS`): four of five is close to everything, which is what the
scoping exists to avoid.

## Which sources a group reads

Each source YAML names its `groups:` - a decision per source, written by
hand from what it actually publishes, not derived from its free-form
`tags`. A generalist names the groups it has real sections for, not all
five. A test holds every enabled source to at least one group and every
group to at least one English and one Spanish source, so no pick returns
a one-language list. Unknown group names are refused when the YAML is
read.

## What discovery drops before anything is fetched

All in `src/services/scraper/strategies/rss.py` (the topic-page strategy
shares the first two):

- **Off-mission sections** (`OFF_MISSION_SECTIONS`): sport, celebrity,
  horoscopes, lotteries, betting, weather forecasts - whatever was asked
  for. The trigger: the 2026-10-05 labelling batch drew a La Vanguardia
  `/deportes/` match report, and the positive-impact score put it above
  an analysis of Chinese industry leaving fossil fuels (0.34 against
  0.28). Whole path segments: `/sports-health/` and `/deporte-y-salud/`
  are fitness and stay.
- **Section-page navigation.** On a section page every link contains the
  section, so the section patterns say nothing; a link there must look
  like an article by its own shape (a date, a headline-length slug, an
  `/article/` segment). BBC's section pages had given `/culture/music`
  and `/sustainability/strategy` as Environment candidates.
- **Links filed under a topic that was not asked for** - an El País
  `/ciencia/` link when only Environment was picked - *unless* the item
  mentions a topic that was: a section is a coarse label, and elDiario
  files wind-power records under `/economia/`.
- **Spanish feeds, keyword-filtered when scoped.** The topic keywords
  are English; against a Spanish feed they kept 5 of El País's 149
  entries at random, so Spanish feeds were never filtered, and an
  Environment round listed El País's and elDiario's election coverage.
  `TOPIC_KEYWORDS_ES` is read only when a run is narrowed to some topics,
  and only against an item's **title and categories**: summaries of a
  general feed are long, and a campaign speech mentions renewables,
  harvests and the political "clima". Measured on the live feeds the same
  day: Environment kept 18 of El País's 159 items and 6 of elDiario's
  109, nearly all on topic. Asked for every topic (`POST /ingest` without
  groups, the labelling batch), Spanish feeds are not filtered, as before.

**Fixed on the way:** from 2026-10-04 (when discovery started asking for
feed times) the topic-page step re-read the dead feed of every source it
exists for instead of crawling a section - it inherits the RSS strategy's
feed reader. National Geographic, Reuters and SINC found nothing through
it for a day. Now overridden, and a test runs it through
`DiscoveryService` as discovery does.

## The candidate round

`POST /ingest/rounds {groups, sources?, perSource}` lists, per source, up
to `perSource` new articles, each with its feed title (or one made from
the URL's slug, marked as such), summary, time and language. It reads
feeds and section pages only. Every round is written to
`lake/stats/selection/<id>.json` as it changes: what was found, what the
AI proposed and why, what was sent, who chose it. That file is the
selection step's own data (`docs/experiments.md`).

`POST /ingest/rounds/{id}/queue {urls}` sends at most **twenty**
(`MAX_SELECTED`; on the production CPU model one article is about three
minutes) of the round's own candidates to analysis as ordinary
`ingestion` jobs. A round is sent once. `selectedBy` - `user`, `ai`,
`ai+user` - and how many AI picks were kept, dropped and added are worked
out by the backend from the AI's proposal, not claimed by the page.

## The AI selection

`POST /ingest/rounds/{id}/ai-selection` scores every candidate 0-10 for
positive impact from its title and summary, against a written definition
(`DEFINITION` in `ai_selector.py`): a real change that improves things
for people or the planet beyond the people in the story, backed by
something checkable; low for sports, celebrity, lifestyle, entertainment,
advice, opinion, crime, conflict and disasters. Picks are the best twenty
at 6 or more. It runs in the background (one at a time: the model is
shared) and the page polls the round.

Why an LLM here, when admission deliberately has none: what the
publication means by positive impact is a judgement of what changed and
for whom, and the admission score counts upbeat words. It costs one call
per ten candidates over a few sentences each, not one per article, and a
pick still goes through admission and the whole pipeline - this ranks
what to spend analyses on; it replaces no check.

**Measured 2026-10-05**, llama3.1 (8B) on the dev laptop, 26 Environment
candidates: 3 calls, 167 s. Picked: UK wind and solar savings (10),
Amazon deforestation under Lula (10), a rewilded gorilla's birth (10),
Indigenous fire prevention in Peru (9), seed bombs in burned L.A. (8),
Japan's solar farms on golf courses (8). Scored 0: four election stories,
the comedy wildlife photo awards, weather pages, a livestock-disease
outbreak. Two weaknesses seen: it scored threat stories that are on
topic high (an orangutan extinction warning, 9), and candidates found
through section pages, which have no summary, score 0 for lack of
information (a rhino rescue, pangolins).

One batch of 13 took 72 s on that GPU, and the dev `LLM_TIMEOUT` (30 s)
failed every selection - the selection has its own limit,
`AI_SELECTION_TIMEOUT` (240 s), infrastructure like `LLM_TIMEOUT`, and
batches of ten with reasons of at most twelve words.

## What was left out

- **No age limit on candidates.** A feed can carry year-old items (the
  WHO's did, 2025-07-24); the round shows each one's date.
- **A candidate from a section page has no summary.** Fetching each
  page's description would cost a request per candidate before anything
  is chosen; the AI scores such candidates low, and says why.
- **The old one-shot path stays.** `POST /ingest` (now with optional
  `groups`) still queues everything it finds; the Scraper page's panel
  for it is gone in favour of `/discover`.

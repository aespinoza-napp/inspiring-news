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

Mostly in `src/services/scraper/strategies/rss.py` (the topic-page
strategy shares the off-mission sections and the article shape); the age
limit is `DiscoveryService`'s and the section rule `topic_pages.py`'s:

- **Off-mission sections** (`OFF_MISSION_SECTIONS`): sport, celebrity,
  horoscopes, lotteries, betting, weather forecasts - whatever was asked
  for. The trigger: the 2026-10-05 labelling batch drew a La Vanguardia
  `/deportes/` match report, and the positive-impact score put it above
  an analysis of Chinese industry leaving fossil fuels (0.34 against
  0.28). Whole path segments: `/sports-health/` and `/deporte-y-salud/`
  are fitness and stay. Added 2026-10-06: `/icon/` (El País's lifestyle
  and celebrity magazine - a Brad Pitt stunt double as Culture) and
  `/sucesos/` (crime).
- **Old items** (`MAX_CANDIDATE_AGE`, 30 days, in `ingestion_service.py`;
  applied by `DiscoveryService(max_age=...)`). Undated items stay - a
  section page dates nothing. A feed with nothing newer counts as empty,
  so the next step runs: RTVE's feed has carried only June 2022 items
  since then, and a Culture round listed two of them (a tanker crash on
  the AP-7 among them) until its section pages took over. Measured on a
  2026-10-06 sample: 38 of 363 dated candidates older than 30 days (24 of
  them WHO's, back to 2025); 14 days would also have cut 9 MIT News
  research stories. The labelling batch has its own discovery and is
  not cut.
- **A section page's links outside its own section**, when the page has
  any inside it (`_within_section` in `topic_pages.py`): ABC's
  `/cultura/` page links the day's top stories, and two `/espana/`
  election pieces came back as Culture. A site whose article URLs carry
  no section (SINC's `/Noticias/...`) keeps every link, as before.
- **Old links with their date in the path.** A section page dates
  nothing, but many links carry the date: `/2026/10/06/`, `/20261006/`,
  ABC's slug stamp (`calcula-hipoteca-20260525124640-nt`). The age limit
  reads it when there is no feed time (`date_from_url`) - ABC's mortgage
  and tax calculators, stamped May, had been offered as news. Only for
  the age check: a day is no publication time, and the freshness report
  keeps to feed times.
- **Live coverage and opinion** (`LIVE_COVERAGE`, and `/opinion/`,
  `/commentisfree/` among the off-mission sections): "Elecciones
  generales del 29-N, en directo" and France 24's live student protests
  were Society candidates; a live page is a stream of updates, not an
  article, and a column's claims are interpretation.
- **Index pages** (`INDEX_SEGMENTS`: `/categoria/`, `/tag/`,
  `/especiales/`, `/autor/`...), whose slugs read like headlines: SINC's
  `/Especiales/Incendios-forestales-en-Espana` and Xataka's
  `/categoria/no-te-lo-creas` were candidates.
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

## The mission screen

Keywords say nothing about tone. A 2026-10-06 Culture round listed
election polls, a cancelled concert and celebrity interviews beside a
free-music-education programme - all on topic by their words.
`src/services/selection/mission_screen.py` leaves a candidate out on
either of two grounds:

1. **Its headline reports a death** - one of the language's
   `death_report` phrases (`src/config/lexicons.py`: "dies aged",
   "dies at", "muere", "fallece"...), title only, present tense only
   ("murió" is the tense of history pieces). No model needed.
2. **Nearest meaning.** Its title and summary (bge-m3, through
   `inference/`) are nearer one of nine descriptions of what the
   publication never covers - politics, strikes and protests, crime,
   accidents and disasters, war, celebrity, sport, markets and personal
   finance, service pages - than every one of the 23 topics, by more than
   **0.04**; for politics, by any amount (`MARGINS`).

It runs before the per-source cap, over the first `per_source x 5` new
articles of each source (`SCREEN_DEPTH`), so a source's slots go to what
passes. What it left out is in the round (`screened`, with the reason and
the margin) and behind a "left out as off-mission" line on `/discover`.
If `inference/` cannot be reached, nothing is left out and the round says
`screen.status: unavailable` - never a silent pass. `POST /ingest`
screens the same way.

**Measured 2026-10-06** on 527 live candidates (Culture, Society and
Health rounds, 40 per source; `docs/experiments.md`): above 0.04, 68 of
the 484 from general outlets - elections, crime, accidents, storms,
market wire items, celebrity interviews; the doubtful ones four National
Geographic war-history pieces and a data-centre regulation story. Between
0.03 and 0.04 about 3 in 17 were stories worth keeping (a UN piece on
breaking prison stigma, a tourism record), so the line is 0.04. It is a
screen for the obvious, not a judge of positive impact: opinion
interviews and topical bad news stay for the person, the AI selection and
admission.

**Widened the same day**, after a Science and Society round still listed
a general strike three times, ABC's mortgage and income-tax calculators,
a coin worth 85,000 euros, Jeffrey Archer's obituary and a drone strike in
Gaza. Re-measured on the 527 plus that round's 114:

- `labour` (strikes, unions against employers, protests) and `markets`
  (markets and personal finance) added, `politics` and `conflict`
  widened: 115 of 545 left out instead of 80, all 36 new ones strikes,
  union-employer disputes, protests, finance, election politics, the
  drone strike and an outbreak at a military academy; one came back in
  (a TV reaction to the election call).
- **Politics needs no lead.** Its stories sit close to their subject's
  topic - housing politics to `cities` - and 14 of the 15 nearest politics
  between 0 and 0.04 were party politics; the other, workers' new right
  to company information, is left out with them. A housing decree that
  protects tenants from eviction goes too: policy is news, but this week
  it was all campaign.
- **No `obituary` description.** Worded broadly it left out research on
  ageing and the Smithsonian's identified Revolutionary War soldiers;
  narrowly, pieces on Unamuno and a poet's letters, while "Jeffrey Archer
  dies aged 86" got through. The death-report phrases matched 6 of 639
  headlines, every one a death. A profile that never says the person died
  ("Jeffrey Archer: bestselling novelist whose political career ended in
  scandal") still gets through.

**What it cannot do**, on that round: the Spanish front pages' housing
policy and social stories - a loans announcement, a minister on tourist
flats, healthcare privatisation, migrants returned from Ceuta - are
*nearer a topic than any of the nine* (-0.02 to -0.07), where good stories
also sit (a poetry prize for a teacher at -0.07). Telling hard news from
positive news there is a judgement: the AI selection's.

- **Not the sentiment model.** On the same candidates it rated an
  endangered primate's birth 0.89 negative, a lost theatre reborn 0.89
  and restoring hearing 0.62: a problem being solved reads as negative.
- **Not the outlets that publish only positive news** (`positive_editorial`
  in the source YAML: Good News Network, Positive News, Reasons to be
  Cheerful). Their editors already chose, and the screen would have left
  out Good News Network's ex-prisoners-as-firefighters jobs story as
  "crime". A test holds the list to those three.

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

- **No age limit on a candidate dated nowhere** - no feed time and no
  date in its link (CNN's and National Geographic's section-page links).
  Dating them would cost a request each.
- **A candidate from a section page has no summary.** Fetching each
  page's description would cost a request per candidate before anything
  is chosen; the AI scores such candidates low, and says why.
- **The old one-shot path stays.** `POST /ingest` (now with optional
  `groups`) still queues everything it finds; the Scraper page's panel
  for it is gone in favour of `/discover`.

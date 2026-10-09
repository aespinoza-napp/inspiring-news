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

Since 2026-10-06 the candidates come best first and a round shows the
best twenty, forty on request ("The ranking", below).

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
  research stories. Since 2026-10-09 the labelling batch is
  cut the same way, and screened (below).
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
- **Pages that are not articles** (`NOT_ARTICLE_SEGMENTS`,
  `NOT_ARTICLE_SLUG_STARTS`, added 2026-10-09): podcasts (`/audio/`,
  `/podcasts/`), galleries (`/image-article/`, a slug starting "fotos-"),
  branded content (elDiario's `/edcreativo/` and 20minutos's `/bc/`, which
  say so on the page), shopping (`/comprar/`, `/bazar/`,
  `/cnn-underscored/`) and recipes (`/el-comidista/`, a slug starting
  "receta-"); and more live pages (`-directo_`, `directo-cronica`,
  `ultima-hora`, CNN's `/live-news/`, France 24's `/20261009-live-`).
  "Receta" only at the start: "Las recetas del responsable económico de
  Vox" is a metaphor.

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
any of three grounds:

0. **It is not an article** (`FORMATS`, `SUMMARY_FORMATS`, added
   2026-10-09): a podcast, a roundup ("What We're Reading", "Books in
   brief", Positive News's weekly "What went right"), a quiz, a gallery,
   a media advisory ("Media are invited to join NASA..."), a promotion
   (a magazine's new issue) or shopping - by phrases in its title, and for
   podcasts and advisories the start of its summary. A positive outlet's
   too: a format, not a subject. On that day's five rounds the URL rules
   and these caught 28 of 35 candidates labelled as not articles, and no
   article.
1. **Its headline reports a death** - one of the language's
   `death_report` phrases (`src/config/lexicons.py`: "dies aged",
   "dies at", "muere", "fallece"...), title only, present tense only
   ("murió" is the tense of history pieces). No model needed.
2. **Nearest meaning.** Its title and summary (bge-m3, through
   `inference/`) are nearer one of nine descriptions of what the
   publication never covers - politics, strikes and protests, crime,
   accidents and disasters, war, celebrity, sport, markets and personal
   finance, service pages - than every one of the 23 topics, by more than
   **0.04**; for politics, by any amount; for markets, service pages,
   labour disputes, disasters and celebrity, by more than 0.02 (`MARGINS`,
   2026-10-09: between 0.02 and 0.04 15 of 16 of those were not worth
   offering, over that day's and 2026-10-06's labels; crime's and war's
   band held a prison-stigma story and history pieces).

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

`POST /ingest/rounds {groups, sources?, perSource, listed?}` finds, per
source, up to `perSource` new articles, each with its feed title (or one
made from the URL's slug, marked as such), summary, time and language,
ranks them all and shows the best `listed` (twenty by default). It reads
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

## The ranking: which twenty are shown

Added 2026-10-06. A round over two or three groups finds 60-80
candidates, and they were listed in the order the sources are named -
20minutos, ABC and BBC first. Now every candidate is scored, and the
round shows the best **twenty** (`LISTED`). **Show more** brings the next
ones into view (`POST /ingest/rounds/{id}/more`, at most `MAX_LISTED`,
forty, in all), and the rest stay in the round as its `reserve`, ranked.
Only what is shown can be chosen, or read by the AI selection, which also
keeps that to two calls (four at forty).

The score (`src/services/selection/ranking.py`) is in [0, 1], from what
the round already holds: no page fetched, no LLM asked.

| Part | Weight | What it is |
|---|---|---|
| The story | 0.51 | How much nearer its title and summary come to a description of positive impact (`IMPACT` in `mission_screen.py`) than to the nearest off-mission one. The screen's embedding pass, one more label |
| The topic | 0.15 | How well it fits the groups the round asked for: its group fit (below), scaled between -0.05 and 0.10. Added 2026-10-09 |
| The source's record | 0.21 | The share of the source's newest items the screen kept this round (`judged`, and `judged - screened` kept), smoothed towards 0.8 with the weight of five items. A positive outlet counts 1 |
| The source's reliability | 0.13 | Its `reliability_index`, the rating its pages get as evidence |

The topic part (2026-10-09): within the group-fit line a story of another
group was ranked on its own merits alone, and an Environment round's first
twenty held the T. rex, a tortoise's longevity and a hospital dog. Over ten
labelled one-group rounds, at 0.15 (the other three keeping their
proportions, 0.6 / 0.25 / 0.15 of the rest) stories of another group in
the first twenties went from 26 to 15 and those worth offering of the
round's own group stayed at 150; at 0.25, 9 and 145; at 0.35, 6 and 141.
The cost is topical hard news: it fits its topic squarely, and the same
Environment round now lists a fishmeal-pollution investigation higher.
That remains the AI selection's and the person's to judge.

**On `/discover`, other topics are another search** (2026-10-09). With a
round on screen the topic buttons still switched, but the only way to
read the feeds again was Refresh, which repeats the round's own topics:
Environment was picked over a Culture round and Refresh brought Culture
three times. Picking other topics now clears the round (it stays under
Recent rounds) and shows the sources for them.

Each candidate keeps its `reading` (the similarities) and its `rank`
(score and parts) in the round, and the round its `ranking.weights`, so
the weights can be refitted from recorded rounds without embedding
anything again. On `/discover` each candidate shows its place, its score
and the three parts.

**Measured 2026-10-06** (`docs/experiments.md`; the labelled set and
every reading in `backend/data/evaluation/experiments/ranking/`): the 117
candidates of the five rounds recorded that day, each read and labelled
by hand before any score existed - 62 not worth offering, 33 worth
offering, 22 clearly positive. Over the 86 today's screen keeps, AUC for
worth offering against not, and clearly positive against the rest: the
story alone 0.75 and 0.81, with the source's record 0.79 and 0.82, the
chosen score 0.78 and 0.81, the app's own AI selection (llama3.2:3b)
0.65 and 0.75. In the rounds: the first twenty of the 11:21 Science and
Society round held 8 stories not worth offering in the sources' order
and 1 ranked, 14 clearly positive instead of 6. The 12:16 Society round,
30 candidates of which about 14 were worth offering, went from 15 not
worth offering in its first twenty to 6.

- **Reliability is in on purpose, with the smallest say.** It does not
  separate a positive story from another (AUC 0.49): Good News Network is
  rated 0.65, a general outlet's election coverage 0.9. It is in because
  how far a source is trusted is part of what the publication offers;
  it costs 0.01 of AUC, inside intervals of about 0.1 either way.
- **Freshness is out.** Within the 30-day limit, newer ranked worse (AUC
  0.30): the day's breaking news is mostly the day's politics.
- **Once the AI has scored, its order wins** on the page (ties in the
  ranking's order), and its picks are ticked as before. On this sample
  the 3B model separated the stories less well than the ranking; the 8B
  model of 2026-10-05 was not measured against it.
- **The words of `IMPACT` are not tuned.** Written before the
  measurement; two other wordings, the AI selector's `DEFINITION` among
  them, did as well within the intervals.
- **One story, once.** Run live on the new code, the same Science and
  Society round put the physics Nobel in 8 of its first twenty places:
  nine outlets in two languages, each rightly scored high. A candidate
  whose embedding is within 0.75 (`SAME_STORY`) of any version of a story
  already placed is marked `sameStoryAs` that story's best-ranked one and
  moved after every distinct story - not dropped. In that round the
  versions paired at 0.68-0.88 and each was within 0.75 of another; the
  nearest two different stories came to 0.69 (two Nature editorials; two
  Muy Interesante pieces on ancient viruses). It grouped exactly the
  eight other physics-Nobel pieces and The Conversation's explainer of
  the medicine Nobel, and the first twenty became twenty stories. The
  vectors are the screen's own, held in memory, never recorded.

**The groups asked for, first** (`fitting_first`, 2026-10-09). A source
names every group it has sections for and its feed is read for all of
them: a Health round listed the chemistry Nobel and a Japanese headband's
symbolism; Environment and Culture both listed Positive News's breakfast
advice. A candidate whose nearest topic in the round's groups trails its
nearest topic elsewhere by more than 0.05 (`GROUP_FIT`) is marked
`otherGroup` and listed after every candidate that fits - moved, never
dropped - and a source's slots go first to what fits. Over 149 labelled
articles of that day's one-group rounds the fit told a story of the
round's group from one of another's with AUC 0.874 [0.81, 0.93]; at -0.05
it moves 18 of the 34 of another group and 10 of the 115 of the round's,
each of those a story whose first group is another. The fit is recorded
with each candidate's reading (`groupFit`).

**What it cannot do**: order is not supply. A round of thirty with
fourteen worth offering still shows six that are not. The labels are an
AI's (Claude's), not yet checked by a person, and the sample is one day.

The page's toolbar - **Refresh** (the same topics, sources and articles
per source, read again: a new round), the AI, the count, **Analyse** -
stays in view while the list scrolls. Refresh used to be "New round" at
the end of the list, then "Find articles" back up in step 2.

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

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
| The story | 0.6 × (1 - emphasis); 0.24 by default | How much nearer its title and summary come to a description of positive impact (`IMPACT` in `mission_screen.py`) than to the nearest off-mission one. The screen's embedding pass, one more label |
| The topic | 0.6 × emphasis; 0.36 by default | How well it fits the groups the round asked for: its group fit (below), scaled between -0.05 and 0.10. Added 2026-10-09 |
| The source's record | 0.25 | The share of the source's newest items the screen kept this round (`judged`, and `judged - screened` kept), smoothed towards 0.8 with the weight of five items. A positive outlet counts 1 |
| The source's reliability | 0.15 | Its `reliability_index`, the rating its pages get as evidence |

The *emphasis* is the person's, per round, 0 to 1 (2026-10-13, "Positive
impact or the topic", below). From 2026-10-09 to 2026-10-13 the weights
were fixed at 0.51 / 0.15 / 0.21 / 0.13; at emphasis 0 they are the
2026-10-06 three-part score.

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

## Positive impact or the topic: the person's call

Added 2026-10-13, asked for by the person running discovery: how much a
round's order weighs a story's positive impact against how well it fits
the topics picked, and, when they look for a topic, the topic first. A
Science round should list science stories first, the positive ones among
them, not the most positive story loosely about science.

**One number, `topicEmphasis`, 0 to 1**, on `POST /ingest/rounds` and as
a control under the topic buttons on `/discover` ("Positive impact ↔
Topic relevance"). It splits the story's 0.6 of the score between its
positive-impact reading and its group fit; the source's record and
reliability keep 0.25 and 0.15 (the 2026-10-06 measurement's) at every
setting. Omitted, it is `DEFAULT_TOPIC_EMPHASIS`, **0.6**: topic 0.36,
positive impact 0.24. A single number rather than four weights because
it is the one trade the person asked to make, and because moving weight
between two parts can never de-normalise the score (below). At any
setting a story nearer another group's topics is still listed after
those that fit (`GROUP_FIT`, above): the control orders what fits.

**No topic, nothing to weigh.** A round with no topic signal - no group
asked for (only `POST /ingest` and the discovery experiment's baseline;
a round requires groups), or nothing read because `inference/` was down -
is ranked at emphasis 0 whatever was asked, and records `applied: null`.
Left at the default, 0.36 of every score would be one constant and the
story would weigh less than its source's record. The control is disabled
until a group is picked and says why; a round with nothing read says its
order is the story's and the source's alone.

**Recorded with the round**, so its order can be explained later without
the code of the day: `ranking.weights` (the four the scores used),
`ranking.topicEmphasis` (`asked`, null for the default; `applied`, null
with no topic signal; `default` that day), `sameStory`, `groupFit`. The
round summary carries `topicEmphasis` (applied) for Recent rounds. The
page sends nothing when the control sits at the default, so a round says
it took the default rather than a number that happened to equal it.

### Where it lives, and the invariants

- **Passed per call** (invariant 1): `rank(reading, standing, fit,
  emphasis)`, `discover_candidates(..., topic_emphasis)`,
  `create_round(..., topic_emphasis)`. `IngestionService` and
  `SelectionService` are singletons shared by every request; a test runs
  two calls with different emphases on one instance and gets two orders,
  and a third call back at the first emphasis gets the first order again.
- **A request parameter, not a `PipelineThresholds` field** (invariant
  2). It is the person's question - what do I want to read first - like
  the round's `groups` and `listed`, and it judges nothing an analysis
  does: admission and the fact-check never see it. `PipelineThresholds`
  is an analysis run's set; the analysis cache keys on every field and
  `Lineage` records overrides on every article, so a field there would
  change every cache key once and stamp onto analyses a knob that never
  touched them. Invariant 2's failure - a value read from `settings` that
  one run cannot override - cannot arise: nothing reads `settings` for it,
  and every round can set it.
- **The weights stay module constants, not `WEIGHT_GROUPS`.** The
  declared exception (ranking and confidence weights environment-only,
  each group summing to 1) is about the fact-checker's `RANKING_*` and
  `CONFIDENCE_*` settings, which a caller setting one member alone would
  de-normalise. The selection ranking's weights were never settings: they
  are measured on labelled rounds and recorded with each round. The
  emphasis only moves weight between the story's two parts, so the sum is
  1 by construction; a test holds it at every emphasis. The default sits
  beside them as a constant (`DEFAULT_TOPIC_EMPHASIS`), like `GROUP_FIT`,
  `SAME_STORY` and `LISTED`.

### Measured 2026-10-13

`uv run python -m src.evaluation.experiments emphasis`
(`docs/experiments.md`; `backend/data/evaluation/experiments/emphasis/`).
Every candidate of the 2026-10-09 alignment rounds, shown or in reserve,
re-scored with the ranking's own `score` and `ordered` from the readings
the rounds recorded - nothing embedded again. The 60 reserve candidates
the 2026-10-09 labels had not covered were labelled first (they rise into
view as the topic weighs more), blind to any score: none of any first
twenty is unlabelled. Over the ten one-group rounds the 2026-10-09 topic
weight was chosen on (200 places in their first twenties):

| Emphasis | Of the group asked for | Worth offering or clearly positive | Worth offering, of the group | Clearly positive, of the group | Not worth offering | First ten: of the group |
|---|---|---|---|---|---|---|
| before (0.51 / 0.15 / 0.21 / 0.13) | 184 | 164 | 154 | 62 | 36 | 94 of 100 |
| 0 (positive impact only) | 174 | 167 | 150 | 61 | 33 | 89 |
| 0.3 | 187 | 162 | 154 | 61 | 38 | 94 |
| 0.5 | 192 | 155 | 150 | 53 | 45 | 98 |
| **0.6 (default)** | **194** | **152** | **150** | **53** | **48** | **100** |
| 0.7 | 194 | 140 | 139 | 46 | 60 | 100 |
| 1 (topic only) | 195 | 137 | 136 | 52 | 63 | 97 |

**Why 0.6.** It is where the group asked for stops gaining: the first ten
all of it (100 of 100; 248 of 250 over all 25 rounds of the day), the
first twenty at its plateau (194 of 200; 478 of 500). Higher gains no more
of it and loses stories worth offering fast (0.7: 139 of the group's,
against 150). Against the weights before, the group's stories worth
offering lose 4 of 154 (7 of 367 over 25 rounds); the 12 stories worth
offering that leave the first twenty are mostly another group's - which
is the point. AUC for a story of the group against another's, 0.706
[0.608, 0.797] before and 0.825 [0.751, 0.891] at 0.6.

**The cost**, already there from about 0.45: clearly positive stories of
the group, 62 → 53. A squarely on-topic story beats a positive one that
also belongs to another group: in the Science round gene therapy restoring
sight (science and health), a physics Nobel and CSIC's spin-offs left the
first twenty for AI policy and a Mars cloud; in Health a roadmap against
hypertension in pregnancy left for an Ebola outbreak and a plague scare.
Within the group, how well the score separates the stories worth offering
falls from 0.757 to 0.619: the ranking now finds the topic; telling good
news from hard news among it is the AI selection's and the person's job.
0.55 is as good within the noise (one more of another group in the first
ten, 7 more of the group's worth offering over 25 rounds); 0.6 is the one
that puts only the group asked for in the first ten, which is what a
person reads first.

**Tried and not adopted: full topic marks earlier.** The topic part is
full at a fit of 0.10, which rewards squareness: a story of two groups
fits less. Full at 0.03 gave back 7 clearly positive stories of the group
at 0.6, but lost 4 worth offering and 4 of the first ten to other groups
(over 25 rounds: 10 more clearly positive, 9 fewer worth offering, 12
fewer of the group in the first ten). Inside the noise either way;
`TOPIC_RANGE` unchanged.

### The AI selection: sees the topic, not the emphasis

`AISelector` already gets the round's topics ("Chosen topics: …") and its
`DEFINITION` scores a story outside them low; that stays. It is not told
the emphasis, by decision. With the topic first, the list it reads is
already the group's stories, and what the emphasis lets in is on-topic
hard news - the outbreak, the plague scare, AI policy. Separating that
from good news is what the AI selection exists for; told to weigh the
topic more, it would promote the same hard news the ranking just let in.
A prompt sentence would be cheap, but its effect cannot be tested here:
no labelled round has AI scores under two prompts, and running the shared
model would compete with the evaluation on the dev stack. The round
records its emphasis, so `blind-ai` can measure the AI against it later.

**What it cannot tell.** The labels are an AI's (Claude's), not yet
checked by a person - the 60 new ones by the same hand, from title and
link. One day, five feeds read five times: the ten rounds are closer to
five, and the 25 are not independent either. The slider's live effect was
checked only where nothing could be read (`inference/` unreachable from
the host): the topic-weighted order itself is covered by tests and by
this replay, not by a live round.

**What it cannot do**: order is not supply. A round of thirty with
fourteen worth offering still shows six that are not. The labels are an
AI's (Claude's), not yet checked by a person, and the sample is one day.

The page's toolbar - **Refresh** (the same topics, sources and articles
per source, read again: a new round), the AI, the count, **Analyse** -
stays in view while the list scrolls. Refresh used to be "New round" at
the end of the list, then "Find articles" back up in step 2.

## Trending: a way in, not a group (2026-10-26)

A round can be **trending** (`trending: true`): its candidates are the
articles behind what is spreading right now (Google's rising searches in
Spain and the US, r/UpliftingNews' top of the day, Upworthy, Know Your
Meme, and a hashtag or link a person typed) instead of the sources of
some groups. The decision, the filters, the ranking with virality in
reliability's place, and what the first live run showed are in
`docs/decisions/trends.md`, "The lens".

What it shares with a topic round: the mission screen, unchanged and
exempting nothing; the ranking's story part and record (the signal's,
not a source's); `SAME_STORY`; the AI selection, told the list is
trending; the queue, which also notes each article's trend for the
writing flow. What it does not: groups are optional and only order what
fits them; nothing is read from the source YAMLs; articles may be a week
old, not a month, and their trend must have started within 72 hours;
betting sites go by domain (`BETTING_DOMAINS`, now part of `off_mission`
for every discovery).

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

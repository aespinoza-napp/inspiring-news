# Editions: Positive and Devastating

Since 2026-10-30 the newsroom runs two editions, chosen with one switch in
the frontend's header (`components/EditionSwitch.tsx`):

- **positive** - Inspiring News, everything as it was before;
- **devastating** - Devastating News: the news that is really bad for
  humanity, with labels of its own and a sardonic, self-important
  narrator.

The request asked for the second edition to skip verification, to frame trends as controversial for reach,
and to be ironic about everything, suicide included. These are the rules
it runs under:

1. **It is not fact-checked; it is reported as its sources report it.**
   First built with the fact-check (unverified stories about real attacks
   and real victims, amplified, are misinformation about real people);
   since 2026-10-30, at the request of the person running it, an admitted
   article goes straight to storage and publishing: no claim selection,
   search or model (`AnalysisService._check`, phase
   `fact_check_skipped`). What still holds: the writer's closed-world
   rules - it states only what the source articles say, citing them - and
   an honest label: the report carries no verdict of ours, UNVERIFIED
   overall with no claim selected, so the reader shows such an article as
   **Not checked**, never as checked. The sources are therefore what
   stands behind its stories: the outlets in the table below.
2. **No invented controversy.** The AI selection scores a story a little
   higher when the public really disputes it (who is to blame, what
   should be done), and the writer sets out each side, cited. Nothing
   manufactures an angle for reach.
3. **The irony aims up and inwards, and stops at suicide.** The narrator's
   vanity is the joke - on the narrator, the powerful, institutions, the
   news cycle - never on victims or anyone for who they are. A story about
   suicide or self-harm drops the persona entirely and follows
   safe-messaging guidance, and the newsroom appends a route to help.

## How an edition travels

One value, `"positive" | "devastating"` (`src/config/editions.py`), passed
per call like a threshold, never read from a setting: the components are
process singletons shared by every request.

| Where | Carried as | What it changes |
|---|---|---|
| An analysis | `PipelineThresholds.edition` (`thresholds.edition` on `/analyze*`) | The classifier's labels; admission's tone gate; whether claims are fact-checked at all (not in the Devastating edition). Part of the analysis cache's key, so neither edition is served the other's result |
| A round (`POST /ingest/rounds`) | `edition`, recorded on the round | Its groups, the sources read, the mission screen, the AI selection's question, the trend signals |
| Queueing a round | the round's own edition | Every pick is analysed in it, whatever the request's thresholds say |
| A draft (`POST /drafts`) | `edition`, else the analysed article's (its topic label is one of that edition's) | The writer's and the rewrite stage's voice |
| The reader (`GET /reader/articles`) | `?edition=` | Only that edition's articles, told by their topic label; omitted, both |
| The catalogue (`GET /ingest/sources`) | `?edition=` | The edition's groups, topics, sources and signals |

The frontend keeps the choice in `lib/edition.tsx` (localStorage, a
convenience) and sends it on every call above. A round or a draft opened
by link brings its own edition with it.

## What each part does in the Devastating edition

**Labels** (`src/config/topics.py`, `DEVASTATING_TOPICS`): eleven topics in
five groups - Violence (terrorism, mass killings, war), Hate (racism, hate
crimes), Despair (suicide & self-harm, addiction & overdoses), Catastrophe
(disasters, famine & epidemics), Abuse of Power (corruption, human rights
abuses) - with Spanish feed words. Separate dicts, so the positive
classifier, the labeller's copy of the five groups and the evaluation's
balance are untouched; the ids are distinct so `editions.ALL_TOPICS` finds
either edition's keywords for the feed filter.

**Classifier**: embeds each edition's labels once per process, the
Devastating ones on its first run.

**Admission** (`services/admission/devastation.py`): `DevastationScorer`,
`PositiveImpactScorer`'s mirror - negative sentiment and societal impact
lead, objectivity adds a little, hope and inspiration cost (0.6 each: at
0.3 the suite's own hopeful article cleared the gate on societal impact
alone). Minimum `DEVASTATION_MIN_SCORE` (0.25), per run as
`devastation_min_score`. The rejection code is `not_devastating`.
**Reasoned, not fitted**: no devastating story has been labelled.

**Sources** (`devastating_groups` in each `data/sources/*.yaml`,
`NewsSource.in_edition`): a source is read for the Devastating edition only
when it names some of its groups, and a source naming only those is never
read for the positive one. The first version read every general outlet;
on 2026-10-30 that meant NASA, ESA, Nature and Mongabay for Terrorism, and
the person saw no source about the subjects at all. Now:

| Group | Sources (2026-10-30) |
|---|---|
| Every group | BBC, CNN, El País, El Mundo, ABC, 20minutos, La Vanguardia, elDiario.es, Infobae (front-page feeds) |
| Added for the edition | Al Jazeera, Human Rights Watch, Amnesty International, ReliefWeb (UN OCHA), ProPublica, The Trace, International Crisis Group, InSight Crime (es), DW Español, RFI Español |
| Also | UN News (all but Despair), WHO (Catastrophe: epidemics) |

Each group has at least 12 sources, in English and Spanish (a test holds
both languages). The ten added feeds were checked live that day; their
reliability ratings are first estimates by Claude, not yet reviewed.
Europa Press is not one: its configured feed is its technology section.
Not found: a reliable feed for the Despair group alone (STAT, KFF Health
News and Filter are health policy or advocacy) - it rests on the general
outlets, InSight Crime and The Trace (gun suicides).

**Discovery**: the edition's keywords narrow a feed. The first lists
matched almost no front-page headline - DW Español, ABC, El Mundo and
Europa Press offered nothing on a live Violence and Hate round, 63 links
found in all - so the verbs and common words went in ("mata", "muere",
"ataque", "violencia"; "kills", "attack", "strike"): 132 found on the same
round. A source naming only Devastating groups, all of them asked for,
needs no keyword (`covers_only`). An article URL ending in an id
(DW's `.../a-79803780`) is now recognised as one (`_headline_slug`). The
crime sections (`CRIME_SECTIONS`, `/sucesos/`) are its subject, not off
mission.

**Mission screen** (`mission_screen.DEVASTATING_OFF_MISSION`,
`DEVASTATING_IMPACT`): off mission are good news, celebrity, sport,
markets, service pages and lifestyle; a death report is the story, not an
obituary to drop. Every margin is `MARGIN`: the positive screen's narrower
ones were fitted to positive rounds. `IngestionService.screen_for` makes
it from the positive screen on first use.

**Ranking**: unchanged code. Its "news" part reads closeness to the
screen's impact description, so it ranks harm first in this edition.

**AI selection**: `DEVASTATING_DEFINITION` - real harm to many people,
backed by something checkable; a little higher when genuinely disputed;
low for outrage with nothing behind it. Laya is refused: it was tuned on
positive picks.

**Trends**: `TrendSignal.devastating` marks a signal read only by this
edition (`data/trends/world_news.yaml`, r/worldnews); `positive` ones are
never read by it; neither flag, both. The constructive-angle step is not
run for its drafts - it looks for constructive angles.

**Writing** (`article_writer.DEVASTATING_NEWSROOM`): the narrator's voice
and rules A-E (E: never the hopeful register, the voice from the first
line), then `CLOSED_WORLD_RULES` word for word.

**Review and rewriting** (`draft_reviewer.review_system_prompt`,
`correction_system_prompt`): the review used to ask every draft for
"Inspiring's voice. Constructive and hopeful", so it scored the narrator
as a fault, the copy editor proposed "a sober, constructive register", and
the rewrite stage - which fixes what the review found - turned a
Devastating draft back into Inspiring's voice. Both now take the draft's
edition: its editor, its style line (irony at victims is a serious fault;
a hopeful tone is not the voice) and, for coverage, `DevastationScorer`.
Every line that holds a fact to its source is the same text. A story touching
suicide or self-harm gets `SAFE_MESSAGING` appended by code
(`with_safe_messaging`), not by the model: a small model may drop it, and
a helpline number written by a model could be wrong - so it names no
number, only the local line. The rewrite stage keeps it.

## The two graphs

Since 2026-10-30 each edition has its own Neo4j: the positive one at
`NEO4J_URI` (`neo4j`, 7474/7687), the Devastating one at
`NEO4J_DEVASTATING_URI` (`neo4j-devastating`, 7475/7688, its own volume).
Neo4j 5 Community holds one user database, so two databases means two
instances; one graph with an `edition` property was not enough, because
the shared nodes - an entity, a topic, a source - would join the two
editions' articles, and "related articles" would cross between them.

- `AnalysisService` writes a Devastating analysis into `devastating_graph`
  only; with `NEO4J_DEVASTATING_URI` empty, into no graph at all - never
  the positive one.
- Every `/graph/*` route takes `?edition=`; the `/graph` page follows the
  header's switch, its Neo4j Browser link included. No Devastating graph
  configured is a 503 that says so.
- `GraphSync` takes `edition`: each lake record goes into its own
  edition's graph (its lineage records `edition`), and the labelled facts
  - the positive edition's evaluation - only into the positive one.
- `/healthz` still asks the positive Neo4j only.

## Not done, and known

- **Until 2026-10-30 no Devastating run reached the lake.** The lineage's
  `threshold_overrides` took numbers only and `edition` is a string, so
  every Devastating run's record failed to start (`store_failed`, fail-
  soft): nothing was stored, so nothing was published, and the Write step
  had nothing to start from. Fixed (`lineage.ThresholdValue`); runs from
  before it must be analysed again with "force refresh" - a plain re-run
  is a cache hit, and a hit is not stored. Their graph writes went into
  the positive graph, before the two were split.

- **The screen's margins are wrong for it.** On the live rounds of
  2026-10-30 it left out a coach arrested for abusing children as "sport"
  and an official's conflict of interest as "good news", and kept a New
  York park raised against the sea. Few, but a sign the descriptions need
  labelled rounds.
- **Nothing in this edition is measured.** The gate's weights and minimum,
  the screen's descriptions and margins, the AI's question: all reasoned.
  Label a few rounds before trusting its order.
- **A URL analysed in both editions at the same moment shares one job**:
  `JobStore` dedupes in-flight jobs by URL alone. One after the other is
  fine (the cache keys on the edition).
- **`POST /ingest`** (no UI since `/discover`) and the labelling batch stay
  positive.
- **The public reader** filters by edition, but both editions' articles
  are in one lake, one graph and one RSS feed (`/reader/feed.xml`).
- The reader's topic names are translated only for the positive topics;
  the Devastating ones show in English.

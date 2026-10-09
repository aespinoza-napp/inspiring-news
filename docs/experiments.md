# Experiments for the paper: the stages before the verdict

The evaluation harness (`src/evaluation/cli.py`, `docs/decisions/evaluation.md`)
measures what the fact-checker concludes. These measure what decides which
articles reach it: discovery, the selection step, admission and the topic
classifier. One command, run from `backend/`:

```bash
uv run python -m src.evaluation.experiments <experiment> [options]
```

Each run writes `result.json` and `report.md` to
`backend/data/evaluation/experiments/<experiment>/<UTC time>/` and prints
the report. Intervals are 95% percentile bootstrap (seed fixed, 2,000
resamples); AUC is the Mann-Whitney probability that a random positive
outranks a random negative, 0.5 being a coin.

| Experiment | Needs | Answers |
|---|---|---|
| `discovery` | network | How much does scoping to topic groups save, and what does it still find? |
| `selection` | recorded rounds | How far does the editor agree with the AI's selection, and does its score separate what they chose? |
| `blind-ai` | the LLM | The same, without the editor having seen the AI's picks first |
| `admission` | the stack (`inference/`) | What do the admission thresholds admit, and how well does the positive-impact score agree with the editor? |
| `topics` | the stack (`inference/`) | How often is the topic classifier right on the labelled facts' articles? |

## discovery

```bash
uv run python -m src.evaluation.experiments discovery \
    --group environment --group science --group culture,health --per-source 3
```

Each `--group` is one setting (several groups comma-separated); without
any, each group alone. A baseline - every source, every topic - runs first
unless `--no-baseline`. Per setting: sources read, discovery attempts (one
per strategy tried), links found, candidates (by language), sources that
found nothing, seconds, and each count relative to the baseline. Nothing
in the lake counts as stored, so the numbers are a setting's yield, not
the day's novelty. Feeds change through the day: compare settings from
the same run, and repeat on a few days for an interval.

First run, 2026-10-05, two candidates per source: Environment read 14 of
34 sources (0.41×) and 153 of 1,536 links (0.10×) in 10 s against 15 s;
Culture + Health read 23 sources (0.68×) and 596 links (0.39×).

## selection and blind-ai

```bash
uv run python -m src.evaluation.experiments selection
uv run python -m src.evaluation.experiments blind-ai --round <round id>
```

`selection` reads every round `/discover` recorded
(`backend/data/lake/stats/selection/`) that has both a finished AI
selection and a selection sent to analysis. Per round: precision (AI picks
the editor kept / AI picks), recall (kept / sent), Jaccard; pooled, the
AUC of the AI's score between the candidates sent and those not. Rounds
are split by mode:

- **assisted** - the editor asked the AI, saw its picks ticked, and
  edited them. Agreement is inflated: an editor anchors on a proposal.
- **blind** - the editor chose and sent first; `blind-ai --round <id>`
  then runs the AI on that round and records its picks marked `blind`.
  This is the number to report as AI-editor agreement.

The protocol for a blind round: on `/discover`, pick topics, find
articles, tick your own choice without pressing *Let the AI choose*,
send it to analysis, copy the round id from the page's URL (`?round=`),
and run `blind-ai`. Every round also keeps the AI's score and reason for
each candidate, so a threshold other than 6/10 can be studied afterwards
without asking the model again.

## admission

```bash
uv run python -m src.evaluation.experiments admission --backend http://127.0.0.1:8000 \
    --topic-min 0.30,0.35,0.40,0.45 --impact-min 0.10,0.20,0.25,0.30
uv run python -m src.evaluation.experiments admission --articles facts
```

Every candidate of the recorded rounds (`--articles rounds`, the default)
or every labelled fact's article (`--articles facts`) is sent once through
the running backend's `POST /enrich` - with the classifier's floor at 0,
so every topic's confidence comes back - and cached in
`experiments/enrich_cache.jsonl`: a re-run, or a different grid, fetches
nothing. Then every (topic minimum, impact minimum) pair is replayed
offline with the pipeline's own `PositiveImpactScorer` and the topic
filter's rule. Below today's classifier floor (0.35) the floor is lowered
with the minimum, so the question becomes what a lower floor would let
through. Reported: admitted and rate per pair; for round candidates, where
the editor's choice is the label, precision and recall of "admitted"
against "chosen", and the AUC of the impact score. Duplicate detection is
not replayed: it depends on what the vector store held at the time.

First run, 2026-10-05, the 41 labelled facts' articles: at the defaults
(0.35, 0.3 from `.env`) 71% would be admitted; at a topic minimum of 0.40,
61% at impact 0.1 and 49% at 0.3. Four articles (10%) have no topic at the
0.35 floor and are rejected whatever the minimum.

## topics

```bash
uv run python -m src.evaluation.experiments topics --backend http://127.0.0.1:8000
```

Each labelled fact's article (its facts' most common topic is the gold
label) against the classifier: top-1 topic, gold in the top three, top-1
group, and how many have no topic at the floor - which the topic filter
rejects. A group confusion table shows where it goes wrong.

First run, 2026-10-05, 41 articles: top-1 topic 0.54 [0.37, 0.68], gold in
top 3 0.78 [0.66, 0.90], group 0.73 [0.59, 0.85], no topic at the floor
0.10 [0.02, 0.20]. Society is the weak group: 5 of its 9 articles were
classified as environment.

## The mission screen's margin (one-off, 2026-10-06)

Not a command yet: run once, inside the backend container (it needs
`inference/`), to choose `MARGIN` in
`src/services/selection/mission_screen.py`. 527 candidates from Culture,
Society and Health rounds at 40 per source; each title and summary
embedded and compared with the 23 topics' descriptions and the seven
off-mission ones, exactly as the screen does, plus the sentiment model.

| Margin above | Left out (all 527) | Left out (484, positive outlets exempt) |
|---|---|---|
| 0.00 | 184 | - |
| 0.02 | 110 | 105 |
| 0.03 | 89 | 85 |
| 0.04 | 70 | 68 |
| 0.05 | 59 | 58 |

Read by hand: above 0.04 nearly all elections, crime, accidents, storms,
market wire items and celebrity interviews; doubtful were four National
Geographic war-history pieces and one data-centre regulation story.
Between 0.03 and 0.04 about 3 of 17 were worth keeping. Good News
Network's curated stories were the main false positives at every margin
(a prison-to-firefighter jobs law as "crime", a diaper drive as
"service"), hence `positive_editorial`. The sentiment model rated stories
of a problem being solved as negative (an endangered primate's birth
0.89, a lost theatre reborn 0.89, restoring hearing 0.62) and was not
used. Re-measure before changing `MARGIN` or any `OFF_MISSION`
description: the numbers above are for those exact texts.

**Second run, the same day**, after a Science and Society round
(11:21 UTC, 3 per source) still listed strikes, ABC's calculators, an
obituary and a drone strike: the 527 above plus that round's 80
candidates and 34 left out (titles only for those), 545 unique from
general outlets, scored under the old descriptions and two proposals.

| Descriptions | Left out above 0.04 | Notes |
|---|---|---|
| The first seven | 80 | |
| + `labour`, `markets`, `obituary` (broad); `politics` widened | 119 | `obituary` left out two SINC pieces on ageing research and the Smithsonian's identified Revolutionary War soldiers |
| `obituary` narrowed, `conflict` widened | 119 | now Unamuno and a poet's letters out, "Jeffrey Archer dies aged 86" in |
| **No `obituary`; `labour`, `markets`, wider `politics` and `conflict`** (kept) | **115** | the 36 new all strikes, union-employer disputes, protests, finance, election politics, the drone strike, an outbreak at a military academy; one back in (a TV reaction to the election call) |

Death reports by headline phrase instead: 6 of 639 titles matched, all
deaths. Politics between 0 and 0.04: 15 items, 14 party politics, hence
politics' margin of 0 (`MARGINS`). The remaining policy and social
stories from the Spanish front pages scored -0.02 to -0.07, among good
stories (a teacher's poetry prize at -0.07): no margin separates them.
Re-run live the same round with all of it: 59 left out instead of 34,
38 dropped as old instead of 7 (link dates).

## The ranking's weights (one-off, 2026-10-06)

Not a command yet either: run once to choose the weights in
`src/services/selection/ranking.py`. The labelled set, every candidate's
readings and the AI's scores are in
`backend/data/evaluation/experiments/ranking/20261006T133348Z/`
(`result.json`, `report.md`), so other weights can be tried without
embedding anything again.

The 117 unique candidates of the five rounds recorded that day (Culture;
Society three times; Science and Society), each read and labelled by
hand before any score was computed (Claude; not yet checked by a person):
22 clearly positive, 33 worth offering, 62 not worth offering. Each title
and summary embedded as the screen does; the app's own AI selection
(llama3.2:3b) run over each round with its topics, writing nowhere but a
file (72 s for all 117). AUC over the 86 today's screen keeps, 95%
bootstrap interval (2,000 resamples, seed 20261005):

| Signal | Worth offering vs not | Clearly positive vs the rest |
|---|---|---|
| **The chosen score** (story 0.6, source record 0.25, reliability 0.15) | **0.778 [0.673, 0.868]** | **0.806 [0.679, 0.916]** |
| Story and source record only (0.75, 0.25) | 0.785 [0.680, 0.876] | 0.822 [0.706, 0.923] |
| The story: nearness to `IMPACT` minus the nearest off-mission | 0.753 [0.647, 0.850] | 0.812 [0.692, 0.917] |
| the same, `IMPACT` worded as the AI selector's `DEFINITION` | 0.718 [0.599, 0.828] | 0.785 [0.660, 0.897] |
| the same, `IMPACT` in one short line | 0.777 [0.669, 0.871] | 0.839 [0.734, 0.928] |
| Source record: share of its items the screen kept | 0.684 [0.556, 0.797] | 0.664 [0.503, 0.808] |
| Source reliability rating | 0.486 [0.356, 0.605] | 0.425 [0.294, 0.566] |
| Nearest topic of the round's groups | 0.582 [0.450, 0.711] | 0.573 [0.442, 0.694] |
| Freshness (newer first) | 0.301 [0.195, 0.416] | 0.420 [0.269, 0.584] |
| The AI selection's 0-10 score (llama3.2:3b) | 0.650 [0.533, 0.759] | 0.755 [0.612, 0.881] |

Not worth offering / clearly positive among each round's first twenty,
today's screen applied, in the sources' order and ranked (the record
from the round's own screening where it had one):

| Round | Topics | Kept today | Sources' order | Ranked |
|---|---|---|---|---|
| 09:43 | Culture | 12 | 1 / 3 | 1 / 3 |
| 10:43 | Society | 15 | 4 / 5 | 4 / 5 |
| 11:19 | Society | 20 | 7 / 7 | 7 / 7 |
| 11:21 | Science, Society | 63 | 8 / 6 | **1 / 14** |
| 12:16 | Society | 30 | 15 / 3 | **6 / 8** |

Rounds of twenty or fewer show everything either way; the ranking only
orders them. Read: the story's own reading carries most of it; the
source's record adds a little; the reliability rating none (it is in on
purpose, `docs/decisions/selection.md`); freshness points the wrong way.
The wording of `IMPACT` was fixed before the measurement and kept: the
short line did better on this sample, inside the same intervals. The 3B
model behind "Let the AI choose" gave 0 to 13 stories labelled not worth
offering and 4 labelled clearly positive, and 9 or 10 to 8 of the former.

**The same round live on the new code** (Science and Society, 3 per
source, 57-66 s): 79 found, 58 left out, 40 too old. Ranked, its first
twenty held the physics Nobel 8 times, from nine outlets in two
languages. All 3,081 pairs of the 79 compared by their embeddings: the
Nobel's versions at 0.68-0.88, each within 0.75 of another; the nearest
two different stories at 0.69. Hence `SAME_STORY` = 0.75, single link
(a version near any already-placed version of a story joins it): it
grouped the eight Nobel repeats and one explainer of the medicine Nobel,
nothing else, and the first twenty became twenty different stories.

## Alignment with the mission and the groups (one-off, 2026-10-09)

Five one-group rounds (three per source) run live, then again after each
of four changes and once more an hour later; 324 candidates labelled by hand from title, summary and
link (Claude; not yet checked by a person) as clearly positive / worth
offering / not worth offering, with the groups each story belongs to and
whether it is an article at all. Everything, every reading included, is in
`backend/data/evaluation/experiments/alignment/20261009T120000Z/`
(`labelled.json`, `runs.json`, `report.md`).

The first twenty of the five rounds (100 candidates):

| Run | Not an article | Another group | Not worth offering | Clearly positive |
|---|---|---|---|---|
| before (ce61d89) | 13 | 21 | 29 | 34 |
| format rules, group fit, sitemap and JSON listings, word-aware keywords | 3 | 13 | 22 | 34 |
| + section pages' headlines, more branded and live markers | 0 | 12 | 19 | 32 |
| + a source's own sections, smaller margins for five categories | 0 | 12 | 19 | 31 |
| + The Optimist Daily, Health for two positive outlets | **0** | **13** | **17** | **34** |
| the same code an hour later (only 6 of 100 new) | 0 | 13 | 16 | 33 |

Health, the weakest round, from 5 / 5 / 10 / 3 to 0 / 2 / 3 / 4. Format
rules: 28 of the 35 non-articles caught, no article. Group fit: AUC 0.874
[0.809, 0.930] over 149 articles. The screen's margin by category: between
0.02 and 0.04, 15 of 16 market, service, labour, disaster and celebrity
candidates not worth offering (both days' labels), so those went to 0.02;
crime and war stayed. Tried and rejected: a description for lifestyle
advice (3 left out at 0.04, all but one caught already). The ranking's own
AUC, worth offering vs not, 0.752 before and 0.749 after; clearly positive
vs the rest 0.720 and 0.628 [0.514, 0.731] - to watch: real headlines
changed the story part's reading. What remains: the Spanish front pages'
politics and economy under the margins, lifestyle advice in Health.

**The topic part of the score** (same day, after a person picked
Environment and got Culture - a page bug, above - and asked that the rating
say how well a story fits the topic picked). Over the ten labelled
one-group rounds of the last two runs, the score with a fourth part, the
group fit scaled between -0.05 and 0.10, at weight w and the other three
scaled by 1-w; first twenty of each:

| w | Of another group | Worth offering, of the round's group | Clearly positive, of the round's group | Not worth offering |
|---|---|---|---|---|
| 0 | 26 | 150 | 61 | 33 |
| 0.10 | 16 | 149 | 59 | 36 |
| **0.15** | **15** | **150** | **60** | **35** |
| 0.20 | 13 | 146 | 57 | 34 |
| 0.25 | 9 | 145 | 57 | 33 |
| 0.35 | 6 | 141 | 53 | 35 |

0.15 is the largest weight that loses none of the round's own stories
worth offering. AUC for a story of the round's group against another's:
0.625 at 0, 0.724 at 0.15; for worth offering against not, 0.749 and
0.730. Live afterwards, an Environment round's first twenty were all
Environment stories but a tortoise's longevity study.

## Thresholds of the fact-check itself

Those belong to the harness, not here: `cli run --thresholds f.json` runs
any per-run threshold set (`docs/decisions/thresholds.md`) over a labelled
set, `--retrieval-only --label <name>` compares retrieval settings without
the LLM, and `cli report --compare` pairs two runs claim by claim.

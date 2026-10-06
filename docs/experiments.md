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

## Thresholds of the fact-check itself

Those belong to the harness, not here: `cli run --thresholds f.json` runs
any per-run threshold set (`docs/decisions/thresholds.md`) over a labelled
set, `--retrieval-only --label <name>` compares retrieval settings without
the LLM, and `cli report --compare` pairs two runs claim by claim.

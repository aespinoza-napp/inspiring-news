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

## Thresholds of the fact-check itself

Those belong to the harness, not here: `cli run --thresholds f.json` runs
any per-run threshold set (`docs/decisions/thresholds.md`) over a labelled
set, `--retrieval-only --label <name>` compares retrieval settings without
the LLM, and `cli report --compare` pairs two runs claim by claim.

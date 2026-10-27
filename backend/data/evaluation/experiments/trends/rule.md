# Five trending rounds: the rule, written before the first

Written 2026-10-26, before day 1 was run or labelled (docs/goals.md,
"Trends", T6). It answers RQ1 with a second way in: does the trending
lens make finding constructive news easier, beyond what the topic rounds
already find?

## What is run, each day

Five days, at most one a day, around the same hour, all on one version of
the code (the 23-topic screen; `internet_culture` was not adopted, T3):

- **One trending round**: every enabled signal, no seed, no news search
  (SearXNG is often rate-limited; Google's own articles are what every
  day has), two articles a trend, no groups, the default emphasis.
- **The day's topic rounds over all five groups**, as /discover makes
  them: Society, Science and Environment in one; Culture and Health in
  another; three articles a source.

`uv run python -m src.evaluation.experiments trends run` makes all three
through the app's own services, with `inference/` up for the screen. They
are saved where /discover keeps its rounds, so a person can open, choose
from and send them like any other. The day's folder holds them, and a
file of the trending round's first twenty to label, **without scores,
ranks, readings or the AI's opinion, in a shuffled order**.

## What is labelled

Each of the trending round's first twenty, from its title, summary,
outlet and trend, before its scores are looked at:

- `hand`: 0 not worth offering, 1 worth offering, 2 clearly positive (the
  scale of 2026-10-06 and 2026-10-09);
- `angle`: `story` (the article is good news in itself), `possible` (a
  constructive angle the article plausibly supports: a solution, a
  discovery, people helping), or `none`;
- `private`: true when the story's subject is a private person or a child
  in a video (the privacy rule of `docs/decisions/trends.md`).

The labels are Claude's until the author checks them, and say so
(`labelledBy`).

## What is reported

Per day and over the days labelled so far:

1. **Precision of the first twenty**: worth offering or clearly positive,
   and clearly positive alone, with a bootstrap interval over the days.
2. **New stories**: of the first twenty worth offering, how many no topic
   round of the same day offered (shown or in reserve), by host and path
   and, with `inference/` up, by `SAME_STORY` similarity of their titles.
3. **By signal**: the first twenty's labels per signal.
4. **The funnel**, as far as it went: trends read -> articles -> kept by
   the screen -> offered -> chosen (the round's queue) -> admitted (the
   lake's analysis) -> published (a draft published from a trend).
5. How many days remain of five.

## What would change what (decided by the five days, not before)

- **The lens stays on /discover** if, over the five days, its first
  twenties hold at least 10 stories worth offering that the same days'
  topic rounds did not find (two a day). Fewer: it is reported as not
  finding what the topic rounds miss, and the author decides.
- **A signal is disabled by default** (`enabled: false`, still in the
  YAML) when at least 80% of its articles in the five first twenties are
  labelled not worth offering, with at least 10 of them labelled.
- **The ranking's trend weights are not refitted** on fewer than 100
  labelled trend candidates; five first twenties are at most 100.

Nothing here is decided by one day.

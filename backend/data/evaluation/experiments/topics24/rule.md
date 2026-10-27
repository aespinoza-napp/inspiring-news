# internet_culture: the rule, written before the re-screen

Written 2026-10-26, before the 24th topic was embedded or any candidate
re-screened (docs/goals.md, "Trends", T3).

## The question

Does a 24th topic, `internet_culture` ("Internet Culture & Trends", in
Culture), change for the worse what the mission screen leaves out, or how
stories fit their groups? The topic is for stories whose subject is a
trend itself (a meme, *farmear aura*). Its risk: a story nearer it than
any off-mission description is kept, and influencer drama sits nearer
"internet culture" than "celebrity".

A topic cannot change the ranking's story part (positive impact against
the nearest off-mission description; no topic enters it). What it can
change is the screen's verdicts (nearest off-mission minus nearest topic)
and the group fit (nearest topic in the round's groups minus nearest
elsewhere). The rule measures those two.

## The data

Every labelled candidate recorded with a title, deduplicated by host and
path:

- 117 from the five rounds of 2026-10-06 (`ranking/20261006T133348Z/`);
- 324 from the alignment rounds of 2026-10-09 (`alignment/20261009T120000Z/labelled.json`);
- 60 reserve candidates of 2026-10-13 (`emphasis/reserve-labels.json`).

Labels: 0 not worth offering, 1 worth offering, 2 clearly positive, by
Claude, before any score, not yet checked by a person. The 9 and 13 Oct
ones also record the groups each story belongs to (`belongsTo`).

## The procedure

Each candidate's title and summary embedded once with bge-m3 (a local
`inference/`), compared as `MissionScreen` compares them with the topics'
descriptions, the off-mission descriptions and IMPACT, under two topic
sets: the 23 of the morning of 2026-10-26 (Entertainment still holding
"viral trend", "internet culture" and "social media trend"), and the 24
with `internet_culture` added and those three keywords moved to it.
Margins as configured (`MARGIN`, `MARGINS`). Outlets marked
`positive_editorial` are exempt, as in the app.

## Adopt the topic if all four hold

1. **Leak.** Of the candidates the 23-topic screen leaves out, at most 2
   come back in with 24 topics while labelled not worth offering.
2. **Loss.** At most 2 candidates labelled worth offering or clearly
   positive are newly left out with 24 topics.
3. **Fit.** Over the candidates with `belongsTo`, the AUC of the group fit
   for a Culture round (a story that belongs to Culture against one that
   does not) does not fall by more than 0.02.
4. **Pull.** At most 3 candidates that do not belong to Culture cross from
   "of another group" to fitting Culture (their fit for a Culture round
   rises past `GROUP_FIT`, -0.05).

Reported beside the rule, deciding nothing: every candidate whose nearest
topic becomes `internet_culture`, with its label; how many change nearest
topic at all.

## What follows

Adopted: the topic stays in `src/config/topics.py`, the labeller's copy
and `TOPIC_KEYWORDS_ES`. Not adopted: it is taken out, the three keywords
go back to Entertainment, and the reason is written in
`docs/decisions/trends.md` and `docs/experiments.md`. Either way, the
labelled candidates predate every trending round: a pass says the topic
does no harm to the rounds there are, not that it helps trending ones.
T6's labelled trending rounds can say that.

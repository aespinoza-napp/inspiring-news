# Ranking: which candidates a round shows first

117 unique candidates from the five rounds recorded on 2026-10-06, each read and labelled by hand (Claude, before any score was computed; not yet checked by a person): 22 clearly positive, 33 worth offering, 62 not worth offering. 86 pass today's mission screen (positive outlets exempt): 54 worth offering, 22 of them clearly positive. Each title and summary embedded as the screen does; the AI selection's score from the app's own model, round by round with the round's topics.

## How well each signal orders the candidates the screen keeps

AUC with 95% bootstrap interval (2000 resamples of the 86, seed 20261005): the probability that a story worth offering (or clearly positive) scores above one that is not. 0.5 is a coin.

| Signal | Worth offering vs not | Clearly positive vs the rest |
|---|---|---|
| Ranking score: news 0.6, source record 0.25, reliability 0.15 (chosen) | 0.778 [0.673, 0.868] | 0.806 [0.679, 0.916] |
| News and source record only (0.75 / 0.25) | 0.785 [0.680, 0.876] | 0.822 [0.706, 0.923] |
| News: nearness to IMPACT minus nearest off-mission | 0.753 [0.647, 0.850] | 0.812 [0.692, 0.917] |
|   the same, IMPACT worded as the AI selector's DEFINITION | 0.718 [0.599, 0.828] | 0.785 [0.660, 0.897] |
|   the same, IMPACT worded in one short line | 0.777 [0.669, 0.871] | 0.839 [0.734, 0.928] |
| Source record: share of the source's items the screen kept | 0.684 [0.556, 0.797] | 0.664 [0.503, 0.808] |
| Source reliability rating (reliability_index) | 0.486 [0.356, 0.605] | 0.425 [0.294, 0.566] |
| Positive outlet (positive_editorial) | 0.593 [0.540, 0.645] | 0.666 [0.564, 0.772] |
| Nearest topic of the round's groups | 0.582 [0.450, 0.711] | 0.573 [0.442, 0.694] |
| Minus the screen's margin | 0.695 [0.579, 0.800] | 0.649 [0.500, 0.789] |
| Freshness (newer first) | 0.301 [0.195, 0.416] | 0.420 [0.269, 0.584] |
| The AI selection's 0-10 score (llama3.2:3b) | 0.650 [0.533, 0.759] | 0.755 [0.612, 0.881] |

The source record is measured here over the day's three screened rounds; a round computes it from its own screening (below).

## The first twenty of each round

Not worth offering / clearly positive among the first twenty. *As shown*: the round as it was listed, sources in name order. Then today's screen applied, in that order and ranked.

| Round | Topics | Screen then | Candidates | As shown | Today's screen, source order | Today's screen, ranked | Source record from |
|---|---|---|---|---|---|---|---|
| fa547e72d0f64d2c 09:43 | culture | none | 18 (12 kept today) | 6 / 3 | 1 / 3 | 1 / 3 | the three screened rounds |
| c9f3f1d298734775 10:43 | society | none | 30 (15 kept today) | 17 / 1 | 4 / 5 | 4 / 5 | the three screened rounds |
| c0f6f92896794ac6 11:19 | society | ok | 31 (20 kept today) | 16 / 2 | 7 / 7 | 7 / 7 | this round |
| 2b3e8feaa3fa4f81 11:21 | science, society | ok | 80 (63 kept today) | 15 / 2 | 8 / 6 | 1 / 14 | this round |
| c5c1680537df4731 12:16 | society | ok | 30 (30 kept today) | 15 / 3 | 15 / 3 | 6 / 8 | this round |

## Chosen

`src/services/selection/ranking.py`: weights {'news': 0.6, 'record': 0.25, 'reliability': 0.15}; news scaled between (-0.11, 0.08) (the 5th and 95th percentiles of the kept candidates); reliability between (0.6, 1.0); the source record smoothed towards 0.8 with the weight of 5 items. Freshness left out: newer ranked worse.

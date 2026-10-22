# manual-train · llama3.2:3b · replayed evidence · verifier-2026-10-22

Run `20c970d87114` · provider `localhost:11434` · harness v1 · thresholds `7df3b6d423ee` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `3155479875c1`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 55 |
| Accuracy | 36.2% [24.6%, 47.8%] | 30.9% [20.0%, 43.6%] |
| Macro-F1 (gold classes) | 0.238 [0.161, 0.316] | 0.209 [0.123, 0.295] |
| Coverage (not UNVERIFIED) | 78.3% [68.1%, 87.0%] | 74.5% [63.6%, 85.5%] |
| Selective accuracy | 44.4% [31.2%, 57.9%] | 39.0% [24.4%, 54.1%] |
| Cohen's kappa vs gold | 0.076 [-0.056, 0.211] | 0.041 [-0.100, 0.181] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 69 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 14 | 28 | 27 | fact009, fact010, fact020, fact036, fact062, fact065, fact089, fact099, fact100, fact118, fact138, fact142, fact146, fact162 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 27 over 24 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 1 (fact127).

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 70.0% | 31.1% | 0.431 | 45 | 20 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 2 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 31.2% | 66.7% | 0.426 | 15 | 32 |
| UNVERIFIED | 6.7% | 16.7% | 0.095 | 6 | 15 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 14 | 2 | 0 | 19 | 10 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 0 | 2 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 3 | 0 | 0 | 10 | 2 |
| UNVERIFIED | 2 | 0 | 0 | 3 | 1 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 33.3% [20.8%, 45.8%] | 0.202 | 79.2% | 42.1% |
| es | 21 | 42.9% [23.8%, 61.9%] | 0.305 | 76.2% | 50.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 50.0% [20.0%, 80.0%] | 0.474 | 90.0% | 55.6% |
| environment | 16 | 37.5% [12.5%, 62.5%] | 0.225 | 100.0% | 37.5% |
| health | 15 | 40.0% [13.3%, 66.7%] | 0.304 | 60.0% | 66.7% |
| science | 17 | 23.5% [5.9%, 47.1%] | 0.154 | 70.6% | 33.3% |
| society | 11 | 36.4% [9.1%, 63.6%] | 0.365 | 72.7% | 37.5% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 37.8% [21.6%, 54.1%] | 0.283 | 78.4% | 48.3% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 100.0% | 33.3% |
| numerical | 29 | 34.5% [17.2%, 51.7%] | 0.253 | 75.9% | 40.9% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 0.0% | n/a |
| primary | 43 | 37.2% [23.3%, 51.2%] | 0.254 | 72.1% | 48.4% |
| reference_media | 25 | 36.0% [20.0%, 56.0%] | 0.209 | 92.0% | 39.1% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 66.7% [40.0%, 86.7%] | 0.800 | 86.7% | 76.9% |
| natural | 54 | 27.8% [16.7%, 40.7%] | 0.186 | 75.9% | 34.1% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 7.5% [1.5%, 13.5%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 26.9% [16.4%, 37.3%] (n=67) |
| Reference domain among cited evidence | 14.9% [7.5%, 23.9%] (n=67) |
| Link MRR (ranked) | 8.1% [2.4%, 14.9%] (n=67) |
| Domain MRR (ranked) | 16.6% [9.2%, 24.9%] (n=67) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=69) |
| Candidates per claim | 17.26 [16.35, 18.17] (n=69) |
| Ranked sources per claim | 4.67 [4.45, 4.84] (n=69) |
| Share cut at ranking (gate, cap) | 4.1% [2.0%, 6.7%] (n=69) |
| Distinct domains among ranked | 4.67 [4.45, 4.84] (n=69) |
| Ranked from rated domains | 6.2% [3.8%, 9.0%] (n=69) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=69) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=69) |
| Ranking seconds per claim | 8.14 [7.79, 8.46] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 8.14 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 204, anchor 127, refutation 81 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 10.4% | 26.9% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 10.9% | 28.3% | 100.0% |
| es | 21 | 21 | 9.5% | 23.8% | 100.0% |

## Stage attribution

44 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=44) | By reference (n=42) |
|---|---|---|
| retrieval | 0 (0.0%) | 28 (66.7%) |
| ranking | 0 (0.0%) | 2 (4.8%) |
| reasoning | 41 (93.2%) | 9 (21.4%) |
| aggregation | 3 (6.8%) | 3 (7.1%) |

Trace only: reasoning (fact009, fact010, fact012, fact015, fact016, fact020, fact037, fact038, fact049, fact062, fact063, fact064, fact066, fact081, fact082, fact086, fact088, fact099, fact100, fact101, fact106, fact107, fact114, fact115, fact122, fact123, fact124, fact125, fact126, fact127, fact128, fact129, fact133, fact139, fact140, fact143, fact144, fact145, fact153, fact169, fact171); aggregation (fact008, fact176, fact178).

By reference: retrieval (fact009, fact010, fact012, fact015, fact016, fact020, fact037, fact062, fact064, fact066, fact081, fact100, fact101, fact107, fact114, fact115, fact122, fact123, fact124, fact125, fact127, fact128, fact133, fact140, fact143, fact144, fact153, fact171); ranking (fact082, fact145); reasoning (fact038, fact063, fact086, fact088, fact106, fact126, fact129, fact139, fact169); aggregation (fact008, fact176, fact178).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (esa.int): 3
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 13, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 9, top 5 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 30 of the 42 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact010 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact082 | reasoning | ranking |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact115 | reasoning | retrieval |
| fact122 | reasoning | retrieval |
| fact123 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact125 | reasoning | retrieval |
| fact127 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact140 | reasoning | retrieval |
| fact143 | reasoning | retrieval |
| fact144 | reasoning | retrieval |
| fact145 | reasoning | ranking |
| fact153 | reasoning | retrieval |
| fact171 | reasoning | retrieval |

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 16 | 23.2% [14.5, 33.3] |
| Confidently wrong (definitive, not gold) | 30 | 43.5% [31.9, 55.1] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.1 | 2.4 | 10.1 | 4.0% |
| Evidence retrieval | 69 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 69 | 2.3 | 3.6 | 5.1 | 4.4% |
| of which: the page fetches | 69 | 2.6 | 10.8 | 40.1 | 8.4% |
| Ranking | 69 | 8.1 | 9.7 | 10.8 | 14.1% |
| The model's verdict (with its wait for a permit) | 69 | 43.4 | 64.9 | 138.9 | 82.0% |
| of which: waiting for the model (another claim's call) | 69 | 15.0 | 28.5 | 105.0 | 31.2% |
| of which: the model's call itself | 69 | 25.9 | 39.8 | 115.7 | 49.7% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 55.0 | 75.7 | 149.0 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 69 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 96992 / 13815 |
| Tokens per claim asked (prompt / completion) | 1405.7 / 200.2 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 25.880 / 39.844 / 115.671 |
| Claim latency, median / p90 (s) | 54.960 / 75.747 |
| Completion tokens per second | 7.0 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`2a4d7dde37b2`, localhost:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 44.9% | 36.2% | -8.7 pts | [-17.4 pts, +0.0 pts] |
| macroF1 | 0.241 | 0.238 | -0.003 | [-0.063, +0.062] |
| coverage | 97.1% | 78.3% | -18.8 pts | [-29.0 pts, -8.7 pts] |
| selectiveAccuracy | 46.3% | 44.4% | -1.8 pts | [-11.0 pts, +7.3 pts] |
| kappa | 0.124 | 0.076 | -0.048 | [-0.147, +0.042] |

Only A right: 8; only B right: 2. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 10.4% | 10.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 7.5% | 7.5% | +0.0 pts [-4.5 pts, +4.5 pts] | 1 / 1 |
| Reference domain among candidates | 67 | 32.8% | 32.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 26.9% | 26.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 16.4% | 14.9% | -1.5 pts [-9.0 pts, +6.0 pts] | 4 / 3 |
| Link MRR (ranked) | 67 | 8.1% | 8.1% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 67 | 16.6% | 16.6% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 69 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 17.26 | 17.26 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 69 | 4.67 | 4.67 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 69 | 4.1% | 4.1% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 69 | 4.67 | 4.67 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 69 | 6.2% | 6.2% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 13.09 | 0.00 | -13.09 [-14.98, -11.46] |  |
| Ranking seconds per claim | 69 | 6.35 | 8.14 | +1.79 [+1.39, +2.17] |  |

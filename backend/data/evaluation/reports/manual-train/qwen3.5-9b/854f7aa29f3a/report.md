# manual-train · qwen3.5:9b · replayed evidence · verifier-2026-10-22-9b-per-source

Run `854f7aa29f3a` · provider `localhost:11434` · harness v1 · thresholds `4f41294f90c7` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `d2ec95f91e90`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 46 |
| Accuracy | 52.2% [40.6%, 63.8%] | 50.0% [34.8%, 63.0%] |
| Macro-F1 (gold classes) | 0.347 [0.263, 0.428] | 0.349 [0.241, 0.446] |
| Coverage (not UNVERIFIED) | 73.9% [62.3%, 84.1%] | 63.0% [50.0%, 76.1%] |
| Selective accuracy | 66.7% [53.6%, 79.2%] | 72.4% [55.2%, 88.0%] |
| Cohen's kappa vs gold | 0.267 [0.120, 0.416] | 0.256 [0.075, 0.432] |

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
| temporalLeak (cited source newer than the claim) | 23 | 29 | 17 | fact009, fact020, fact036, fact037, fact038, fact062, fact066, fact088, fact089, fact099, fact100, fact118, fact128, fact138, fact142, fact143, fact144, fact146, fact159, fact162, fact163, fact174, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 19 over 15 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 84.6% | 48.9% | 0.620 | 45 | 26 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 48.0% | 80.0% | 0.600 | 15 | 25 |
| UNVERIFIED | 11.1% | 33.3% | 0.167 | 6 | 18 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 22 | 0 | 0 | 9 | 14 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 1 | 0 | 0 | 12 | 2 |
| UNVERIFIED | 2 | 0 | 0 | 2 | 2 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 39.6% [25.0%, 54.2%] | 0.253 | 68.8% | 57.6% |
| es | 21 | 81.0% [61.9%, 95.2%] | 0.620 | 85.7% | 83.3% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 70.0% [40.0%, 100.0%] | 0.670 | 100.0% | 70.0% |
| environment | 16 | 25.0% [6.2%, 50.0%] | 0.188 | 62.5% | 40.0% |
| health | 15 | 60.0% [33.3%, 86.7%] | 0.435 | 86.7% | 69.2% |
| science | 17 | 47.1% [23.5%, 70.6%] | 0.301 | 64.7% | 72.7% |
| society | 11 | 72.7% [45.5%, 100.0%] | 0.730 | 63.6% | 85.7% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 62.2% [45.9%, 78.4%] | 0.470 | 78.4% | 79.3% |
| interpretive | 3 | 66.7% [0.0%, 100.0%] | 0.800 | 66.7% | 100.0% |
| numerical | 29 | 37.9% [20.7%, 55.2%] | 0.287 | 69.0% | 45.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 51.2% [37.2%, 65.1%] | 0.356 | 67.4% | 69.0% |
| reference_media | 25 | 52.0% [32.0%, 72.0%] | 0.310 | 84.0% | 61.9% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 80.0% [60.0%, 100.0%] | 0.889 | 86.7% | 92.3% |
| natural | 54 | 44.4% [31.5%, 57.4%] | 0.270 | 70.4% | 57.9% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 7.5% [1.5%, 14.9%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 26.9% [16.4%, 37.3%] (n=67) |
| Reference domain among cited evidence | 13.4% [6.0%, 22.4%] (n=67) |
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
| Ranking seconds per claim | 9.67 [8.95, 10.44] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 8.86 s ranking; 3.00 queries per claim.

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

33 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=33) | By reference (n=31) |
|---|---|---|
| retrieval | 0 (0.0%) | 21 (67.7%) |
| ranking | 0 (0.0%) | 4 (12.9%) |
| reasoning | 33 (100.0%) | 6 (19.4%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact009, fact012, fact015, fact016, fact020, fact021, fact036, fact037, fact038, fact049, fact063, fact064, fact066, fact081, fact082, fact099, fact100, fact101, fact107, fact117, fact122, fact124, fact127, fact128, fact129, fact132, fact133, fact138, fact139, fact145, fact156, fact165, fact169).

By reference: retrieval (fact009, fact012, fact015, fact016, fact020, fact021, fact037, fact064, fact066, fact081, fact100, fact101, fact107, fact122, fact124, fact127, fact128, fact132, fact133, fact138, fact165); ranking (fact036, fact082, fact145, fact156); reasoning (fact038, fact063, fact117, fact129, fact139, fact169).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (esa.int): 3
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 12, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 13, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 9, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 14, top 5 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 25 of the 31 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact021 | reasoning | retrieval |
| fact036 | reasoning | ranking |
| fact037 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact082 | reasoning | ranking |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact122 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact127 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact132 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact145 | reasoning | ranking |
| fact156 | reasoning | ranking |
| fact165 | reasoning | retrieval |

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 21 | 30.4% [20.3, 42.0] |
| Confidently wrong (definitive, not gold) | 17 | 24.6% [14.5, 34.8] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.2 | 2.6 | 10.5 | 1.7% |
| Evidence retrieval | 69 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 69 | 2.3 | 3.6 | 5.1 | 1.8% |
| of which: the page fetches | 69 | 2.6 | 10.8 | 40.1 | 3.5% |
| Ranking | 69 | 8.9 | 15.1 | 19.8 | 6.9% |
| The model's verdict (with its wait for a permit) | 69 | 111.7 | 198.2 | 328.3 | 91.3% |
| of which: waiting for the model (another claim's call) | 69 | 47.2 | 114.1 | 238.0 | 40.6% |
| of which: the model's call itself | 69 | 71.4 | 98.5 | 127.1 | 50.3% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 122.5 | 209.0 | 338.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 322 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 138581 / 9208 |
| Tokens per claim asked (prompt / completion) | 2008.4 / 133.4 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 14.184 / 22.694 / 47.077 |
| Claim latency, median / p90 (s) | 122.453 / 209.041 |
| Completion tokens per second | 1.9 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`2a4d7dde37b2`, localhost:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 44.9% | 52.2% | +7.2 pts | [-5.8 pts, +20.3 pts] |
| macroF1 | 0.241 | 0.347 | +0.106 | [+0.019, +0.192] |
| coverage | 97.1% | 73.9% | -23.2 pts | [-33.3 pts, -14.5 pts] |
| selectiveAccuracy | 46.3% | 66.7% | +20.4 pts | [+7.4 pts, +33.7 pts] |
| kappa | 0.124 | 0.267 | +0.143 | [-0.016, +0.308] |

Only A right: 8; only B right: 13. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 10.4% | 10.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 7.5% | 7.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 67 | 32.8% | 32.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 26.9% | 26.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 16.4% | 13.4% | -3.0 pts [-7.5 pts, +0.0 pts] | 2 / 0 |
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
| Ranking seconds per claim | 69 | 6.35 | 9.67 | +3.32 [+2.60, +4.08] |  |

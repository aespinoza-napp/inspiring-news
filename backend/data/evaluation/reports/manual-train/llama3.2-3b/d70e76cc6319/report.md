# manual-train · llama3.2:3b · replayed evidence · verifier-2026-10-22

Run `d70e76cc6319` · provider `localhost:11434` · harness v1 · thresholds `4f41294f90c7` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `d570ff7af980`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 46 |
| Accuracy | 39.1% [27.5%, 50.7%] | 34.8% [21.7%, 47.8%] |
| Macro-F1 (gold classes) | 0.277 [0.177, 0.376] | 0.252 [0.132, 0.363] |
| Coverage (not UNVERIFIED) | 82.6% [73.9%, 91.3%] | 73.9% [60.9%, 84.8%] |
| Selective accuracy | 43.9% [31.0%, 57.1%] | 41.2% [25.0%, 58.1%] |
| Cohen's kappa vs gold | 0.089 [-0.045, 0.228] | 0.048 [-0.112, 0.209] |

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
| temporalLeak (cited source newer than the claim) | 23 | 29 | 17 | fact009, fact020, fact036, fact037, fact038, fact062, fact065, fact066, fact088, fact089, fact099, fact100, fact118, fact138, fact142, fact143, fact144, fact146, fact159, fact162, fact163, fact174, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 17 over 14 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 72.4% | 46.7% | 0.568 | 45 | 29 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 18 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 40.0% | 26.7% | 0.320 | 15 | 10 |
| UNVERIFIED | 16.7% | 33.3% | 0.222 | 6 | 12 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 21 | 9 | 0 | 6 | 9 |
| PARTIALLY_TRUE | 3 | 0 | 0 | 0 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 4 | 6 | 0 | 4 | 1 |
| UNVERIFIED | 1 | 3 | 0 | 0 | 2 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 35.4% [22.9%, 47.9%] | 0.225 | 81.2% | 43.6% |
| es | 21 | 47.6% [28.6%, 66.7%] | 0.367 | 85.7% | 44.4% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 60.0% [30.0%, 90.0%] | 0.400 | 100.0% | 60.0% |
| environment | 16 | 18.8% [0.0%, 37.5%] | 0.177 | 87.5% | 21.4% |
| health | 15 | 33.3% [13.3%, 60.0%] | 0.196 | 86.7% | 38.5% |
| science | 17 | 41.2% [17.6%, 64.7%] | 0.274 | 70.6% | 58.3% |
| society | 11 | 54.5% [27.3%, 81.8%] | 0.600 | 72.7% | 50.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 51.4% [35.1%, 67.6%] | 0.357 | 81.1% | 63.3% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 66.7% | 50.0% |
| numerical | 29 | 24.1% [10.3%, 41.4%] | 0.245 | 86.2% | 20.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 37.2% [23.3%, 51.2%] | 0.273 | 76.7% | 42.4% |
| reference_media | 25 | 40.0% [20.0%, 60.0%] | 0.259 | 92.0% | 43.5% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 26.7% [6.7%, 53.3%] | 0.421 | 93.3% | 28.6% |
| natural | 54 | 42.6% [29.6%, 55.6%] | 0.278 | 79.6% | 48.8% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 7.5% [1.5%, 13.5%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 26.9% [16.4%, 37.3%] (n=67) |
| Reference domain among cited evidence | 16.4% [7.5%, 25.4%] (n=67) |
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
| Ranking seconds per claim | 7.09 [6.74, 7.40] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 7.52 s ranking; 3.00 queries per claim.

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

42 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=42) | By reference (n=40) |
|---|---|---|
| retrieval | 0 (0.0%) | 23 (57.5%) |
| ranking | 0 (0.0%) | 3 (7.5%) |
| reasoning | 33 (78.6%) | 5 (12.5%) |
| aggregation | 9 (21.4%) | 9 (22.5%) |

Trace only: reasoning (fact009, fact012, fact015, fact016, fact037, fact049, fact062, fact064, fact066, fact081, fact082, fact099, fact100, fact101, fact124, fact126, fact127, fact128, fact129, fact133, fact138, fact145, fact151, fact153, fact156, fact162, fact165, fact169, fact171, fact172, fact174, fact176, fact178); aggregation (fact008, fact020, fact038, fact063, fact086, fact106, fact115, fact125, fact132).

By reference: retrieval (fact009, fact012, fact015, fact016, fact037, fact062, fact064, fact066, fact081, fact100, fact101, fact124, fact127, fact128, fact133, fact138, fact151, fact153, fact162, fact165, fact171, fact174, fact178); ranking (fact082, fact145, fact156); reasoning (fact126, fact129, fact169, fact172, fact176); aggregation (fact008, fact020, fact038, fact063, fact086, fact106, fact115, fact125, fact132).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (esa.int): 3
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 13, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 9, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 14, top 5 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 26 of the 40 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact082 | reasoning | ranking |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact127 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact145 | reasoning | ranking |
| fact151 | reasoning | retrieval |
| fact153 | reasoning | retrieval |
| fact156 | reasoning | ranking |
| fact162 | reasoning | retrieval |
| fact165 | reasoning | retrieval |
| fact171 | reasoning | retrieval |
| fact174 | reasoning | retrieval |
| fact178 | reasoning | retrieval |

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 14 | 20.3% [11.6, 30.4] |
| Confidently wrong (definitive, not gold) | 32 | 46.4% [34.8, 58.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.1 | 3.4 | 10.5 | 6.1% |
| Evidence retrieval | 69 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 69 | 2.3 | 3.6 | 5.1 | 5.8% |
| of which: the page fetches | 69 | 2.6 | 10.8 | 40.1 | 11.2% |
| Ranking | 69 | 7.5 | 8.3 | 9.9 | 16.4% |
| The model's verdict (with its wait for a permit) | 69 | 30.5 | 55.8 | 69.7 | 77.5% |
| of which: waiting for the model (another claim's call) | 69 | 9.3 | 30.8 | 40.2 | 27.3% |
| of which: the model's call itself | 69 | 21.4 | 28.8 | 43.6 | 48.9% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 40.4 | 66.6 | 88.0 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 323 (2) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 138499 / 10918 |
| Tokens per claim asked (prompt / completion) | 2007.2 / 158.2 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 4.075 / 7.110 / 16.870 |
| Claim latency, median / p90 (s) | 40.419 / 66.603 |
| Completion tokens per second | 7.6 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`2a4d7dde37b2`, localhost:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 44.9% | 39.1% | -5.8 pts | [-20.3 pts, +8.7 pts] |
| macroF1 | 0.241 | 0.277 | +0.036 | [-0.069, +0.137] |
| coverage | 97.1% | 82.6% | -14.5 pts | [-24.6 pts, -5.8 pts] |
| selectiveAccuracy | 46.3% | 43.9% | -2.4 pts | [-18.0 pts, +12.7 pts] |
| kappa | 0.124 | 0.089 | -0.036 | [-0.201, +0.120] |

Only A right: 15; only B right: 11. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 10.4% | 10.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 7.5% | 7.5% | +0.0 pts [-4.5 pts, +4.5 pts] | 1 / 1 |
| Reference domain among candidates | 67 | 32.8% | 32.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 26.9% | 26.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 16.4% | 16.4% | +0.0 pts [-6.0 pts, +6.0 pts] | 2 / 2 |
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
| Ranking seconds per claim | 69 | 6.35 | 7.09 | +0.74 [+0.35, +1.11] |  |

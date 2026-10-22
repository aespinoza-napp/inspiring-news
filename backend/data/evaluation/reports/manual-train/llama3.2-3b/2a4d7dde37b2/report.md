# manual-train · llama3.2:3b · verifier-2026-10-22

Run `2a4d7dde37b2` · provider `localhost:11434` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `3155479875c1`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 46 |
| Accuracy | 44.9% [33.3%, 56.5%] | 47.8% [32.6%, 60.9%] |
| Macro-F1 (gold classes) | 0.241 [0.179, 0.300] | 0.251 [0.174, 0.319] |
| Coverage (not UNVERIFIED) | 97.1% [92.8%, 100.0%] | 95.7% [89.1%, 100.0%] |
| Selective accuracy | 46.3% [34.8%, 58.2%] | 50.0% [35.6%, 64.4%] |
| Cohen's kappa vs gold | 0.124 [-0.016, 0.272] | 0.138 [-0.058, 0.325] |

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
| temporalLeak (cited source newer than the claim) | 23 | 18 | 28 | fact009, fact010, fact011, fact020, fact036, fact038, fact062, fact064, fact065, fact066, fact089, fact099, fact100, fact118, fact124, fact128, fact142, fact143, fact144, fact146, fact162, fact163, fact174 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 18 over 16 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 1 (fact122).

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 76.0% | 42.2% | 0.543 | 45 | 25 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 28.6% | 80.0% | 0.421 | 15 | 42 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 6 | 2 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 19 | 0 | 0 | 24 | 2 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 3 | 0 | 0 | 12 | 0 |
| UNVERIFIED | 2 | 0 | 0 | 4 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 39.6% [25.0%, 54.2%] | 0.213 | 95.8% | 41.3% |
| es | 21 | 57.1% [38.1%, 76.2%] | 0.295 | 100.0% | 57.1% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 60.0% [30.0%, 90.0%] | 0.524 | 100.0% | 60.0% |
| environment | 16 | 37.5% [12.5%, 62.5%] | 0.215 | 100.0% | 37.5% |
| health | 15 | 53.3% [26.7%, 80.0%] | 0.375 | 93.3% | 57.1% |
| science | 17 | 41.2% [17.6%, 64.7%] | 0.225 | 94.1% | 43.8% |
| society | 11 | 36.4% [9.1%, 63.6%] | 0.269 | 100.0% | 36.4% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 54.1% [37.8%, 70.3%] | 0.361 | 94.6% | 57.1% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 100.0% | 33.3% |
| numerical | 29 | 34.5% [17.2%, 51.7%] | 0.199 | 100.0% | 34.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| primary | 43 | 44.2% [30.2%, 58.1%] | 0.236 | 97.7% | 45.2% |
| reference_media | 25 | 48.0% [28.0%, 68.0%] | 0.259 | 96.0% | 50.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 80.0% [60.0%, 100.0%] | 0.889 | 100.0% | 80.0% |
| natural | 54 | 35.2% [22.2%, 48.1%] | 0.189 | 96.3% | 36.5% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 7.5% [1.5%, 14.9%] (n=67) |
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
| Retrieval seconds per claim | 13.09 [11.46, 14.98] (n=69) |
| Ranking seconds per claim | 6.35 [5.92, 6.79] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 10.78 s retrieval, 6.17 s ranking; 3.00 queries per claim.

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

38 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=38) | By reference (n=36) |
|---|---|---|
| retrieval | 0 (0.0%) | 28 (77.8%) |
| ranking | 0 (0.0%) | 1 (2.8%) |
| reasoning | 38 (100.0%) | 7 (19.4%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact009, fact010, fact011, fact012, fact015, fact016, fact020, fact037, fact038, fact049, fact062, fact063, fact064, fact066, fact081, fact088, fact099, fact100, fact101, fact107, fact114, fact122, fact123, fact124, fact125, fact126, fact128, fact129, fact133, fact138, fact139, fact140, fact143, fact144, fact145, fact153, fact169, fact171).

By reference: retrieval (fact009, fact010, fact011, fact012, fact015, fact016, fact020, fact037, fact062, fact064, fact066, fact081, fact100, fact101, fact107, fact114, fact122, fact123, fact124, fact125, fact128, fact133, fact138, fact140, fact143, fact144, fact153, fact171); ranking (fact145); reasoning (fact038, fact063, fact088, fact126, fact129, fact139, fact169).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (esa.int): 3
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 9, top 5 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 29 of the 36 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact010 | reasoning | retrieval |
| fact011 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact122 | reasoning | retrieval |
| fact123 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact125 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
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
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 21 | 30.4% [20.3, 42.0] |
| Confidently wrong (definitive, not gold) | 36 | 52.2% [40.6, 63.8] |

Right and definitive but citing no source with a stance: 1 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.2 | 3.8 | 11.2 | 4.2% |
| Evidence retrieval | 69 | 10.8 | 19.9 | 48.8 | 20.3% |
| of which: the web search, every query | 69 | 2.3 | 3.6 | 5.1 | 3.9% |
| of which: the page fetches | 69 | 2.6 | 10.8 | 40.1 | 7.5% |
| Ranking | 69 | 6.2 | 8.2 | 12.5 | 9.8% |
| The model's verdict (with its wait for a permit) | 69 | 39.7 | 58.8 | 146.2 | 65.7% |
| of which: waiting for the model (another claim's call) | 69 | 7.7 | 22.4 | 93.9 | 17.1% |
| of which: the model's call itself | 69 | 27.2 | 42.1 | 119.4 | 47.8% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 62.7 | 83.0 | 172.7 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 69 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 88850 / 13245 |
| Tokens per claim asked (prompt / completion) | 1287.7 / 192.0 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 27.169 / 42.099 / 119.442 |
| Claim latency, median / p90 (s) | 62.716 / 82.982 |
| Completion tokens per second | 6.2 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`340a36ac8972`, localhost:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 50.7% | 44.9% | -5.8 pts | [-14.5 pts, +1.4 pts] |
| macroF1 | 0.267 | 0.241 | -0.026 | [-0.062, +0.009] |
| coverage | 98.6% | 97.1% | -1.4 pts | [-7.2 pts, +2.9 pts] |
| selectiveAccuracy | 51.5% | 46.3% | -5.2 pts | [-12.8 pts, +2.2 pts] |
| kappa | 0.172 | 0.124 | -0.048 | [-0.135, +0.031] |

Only A right: 6; only B right: 2. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [-4.5 pts, +4.5 pts] | 1 / 1 |
| Reference link among ranked evidence | 67 | 9.0% | 10.4% | +1.5 pts [-3.0 pts, +6.0 pts] | 1 / 2 |
| Reference link among cited evidence | 67 | 9.0% | 7.5% | -1.5 pts [-4.5 pts, +0.0 pts] | 1 / 0 |
| Reference domain among candidates | 67 | 34.3% | 32.8% | -1.5 pts [-6.0 pts, +3.0 pts] | 2 / 1 |
| Reference domain among ranked evidence | 67 | 25.4% | 26.9% | +1.5 pts [-6.0 pts, +9.0 pts] | 3 / 4 |
| Reference domain among cited evidence | 67 | 17.9% | 16.4% | -1.5 pts [-9.0 pts, +6.0 pts] | 4 / 3 |
| Link MRR (ranked) | 67 | 8.2% | 8.1% | -0.1 pts [-2.1 pts, +1.2 pts] | 1 / 2 |
| Domain MRR (ranked) | 67 | 17.9% | 16.6% | -1.3 pts [-6.1 pts, +2.9 pts] | 4 / 5 |
| Claims with any ranked evidence | 69 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 17.86 | 17.26 | -0.59 [-1.39, +0.17] |  |
| Ranked sources per claim | 69 | 4.72 | 4.67 | -0.06 [-0.30, +0.16] |  |
| Share cut at ranking (gate, cap) | 69 | 4.0% | 4.1% | +0.2 pts [-2.0 pts, +2.5 pts] |  |
| Distinct domains among ranked | 69 | 4.72 | 4.67 | -0.06 [-0.30, +0.16] |  |
| Ranked from rated domains | 69 | 6.7% | 6.2% | -0.5 pts [-2.5 pts, +1.5 pts] |  |
| Ranked from the internal corpus | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 12.61 | 13.09 | +0.48 [-0.89, +1.96] |  |
| Ranking seconds per claim | 69 | 6.37 | 6.35 | -0.02 [-0.53, +0.49] |  |

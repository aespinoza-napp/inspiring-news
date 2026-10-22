# manual-test · llama3.2:3b · verifier-2026-10-22

Run `66034c5fea72` · provider `localhost:11434` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (1 points)

Dataset sha256 `1ea9a8b72ec3`, 70 rows; 70 run, 0 not run. Commits: `d570ff7af980`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 70 | 51 |
| Accuracy | 51.4% [40.0%, 62.9%] | 45.1% [31.4%, 58.8%] |
| Macro-F1 (gold classes) | 0.212 [0.162, 0.259] | 0.188 [0.132, 0.242] |
| Coverage (not UNVERIFIED) | 98.6% [95.7%, 100.0%] | 98.0% [94.1%, 100.0%] |
| Selective accuracy | 52.2% [40.6%, 63.8%] | 46.0% [32.0%, 60.0%] |
| Cohen's kappa vs gold | 0.143 [-0.021, 0.314] | 0.089 [-0.091, 0.269] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 70 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 19 | 29 | 22 | fact006, fact007, fact013, fact014, fact018, fact030, fact031, fact048, fact050, fact057, fact078, fact080, fact111, fact119, fact121, fact149, fact150, fact161, fact167 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 70 |  |

Ranked but uncited sources newer than the claim: 9 over 9 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 1 (fact001).

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 75.0% | 58.7% | 0.659 | 46 | 36 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 4 | 3 |
| MISLEADING | n/a | 0.0% | 0.000 | 1 | 0 |
| FALSE | 30.0% | 60.0% | 0.400 | 15 | 30 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 4 | 1 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 27 | 2 | 0 | 17 | 0 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 3 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 1 |
| FALSE | 5 | 1 | 0 | 9 | 0 |
| UNVERIFIED | 3 | 0 | 0 | 1 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 51.1% [36.2%, 66.0%] | 0.261 | 100.0% | 51.1% |
| es | 23 | 52.2% [30.4%, 73.9%] | 0.273 | 95.7% | 54.5% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 11 | 54.5% [27.3%, 81.8%] | 0.333 | 100.0% | 54.5% |
| environment | 18 | 50.0% [27.8%, 72.2%] | 0.273 | 100.0% | 50.0% |
| health | 16 | 50.0% [25.0%, 75.0%] | 0.232 | 100.0% | 50.0% |
| science | 16 | 56.2% [31.2%, 81.2%] | 0.286 | 100.0% | 56.2% |
| society | 9 | 44.4% [11.1%, 77.8%] | 0.250 | 88.9% | 50.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 44 | 54.5% [38.6%, 68.2%] | 0.277 | 100.0% | 54.5% |
| interpretive | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| numerical | 24 | 50.0% [29.2%, 70.8%] | 0.255 | 95.8% | 52.2% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 3 | 66.7% [0.0%, 100.0%] | 0.556 | 100.0% | 66.7% |
| primary | 37 | 51.4% [35.1%, 67.6%] | 0.197 | 97.3% | 52.8% |
| reference_media | 30 | 50.0% [33.3%, 66.7%] | 0.266 | 100.0% | 50.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 60.0% [33.3%, 86.7%] | 0.750 | 100.0% | 60.0% |
| natural | 55 | 49.1% [36.4%, 61.8%] | 0.175 | 98.2% | 50.0% |

## Retrieval

70 claims searched (69 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 17.4% [8.7%, 27.5%] (n=69) |
| Reference link among ranked evidence | 8.7% [2.9%, 15.9%] (n=69) |
| Reference link among cited evidence | 7.2% [1.5%, 14.5%] (n=69) |
| Reference domain among candidates | 27.5% [17.4%, 37.7%] (n=69) |
| Reference domain among ranked evidence | 15.9% [7.2%, 24.6%] (n=69) |
| Reference domain among cited evidence | 13.0% [5.8%, 21.7%] (n=69) |
| Link MRR (ranked) | 4.1% [1.1%, 8.3%] (n=69) |
| Domain MRR (ranked) | 8.9% [3.9%, 15.0%] (n=69) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=70) |
| Candidates per claim | 18.97 [18.09, 19.84] (n=70) |
| Ranked sources per claim | 4.96 [4.90, 5.00] (n=70) |
| Share cut at ranking (gate, cap) | 0.9% [0.0%, 2.0%] (n=70) |
| Distinct domains among ranked | 4.96 [4.90, 5.00] (n=70) |
| Ranked from rated domains | 5.9% [3.6%, 8.2%] (n=70) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=70) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 12.62 [11.35, 14.06] (n=70) |
| Ranking seconds per claim | 5.50 [5.30, 5.71] (n=70) |

Medians: 19.50 candidates, 5.00 ranked, 11.31 s retrieval, 5.54 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 207, anchor 128, refutation 72 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: cut by pre-rank funnel (rank 8 of 12, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (space.com): 1
- evidence_retrieval: cut by pre-rank funnel (rank 7 of 18, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (en.wikipedia.org): 1
- evidence_retrieval: cut by pre-rank funnel (rank 8 of 21, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 7 of 16, top 5 kept): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 70 | 69 | 8.7% | 15.9% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 47 | 46 | 13.0% | 21.7% | 100.0% |
| es | 23 | 23 | 0.0% | 4.3% | 100.0% |

## Stage attribution

34 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=34) | By reference (n=33) |
|---|---|---|
| retrieval | 0 (0.0%) | 26 (78.8%) |
| ranking | 0 (0.0%) | 0 (0.0%) |
| reasoning | 32 (94.1%) | 5 (15.2%) |
| aggregation | 2 (5.9%) | 2 (6.1%) |

Trace only: reasoning (fact001, fact002, fact005, fact013, fact014, fact017, fact018, fact024, fact025, fact031, fact034, fact046, fact053, fact055, fact056, fact075, fact079, fact083, fact094, fact111, fact120, fact130, fact131, fact134, fact147, fact148, fact157, fact167, fact168, fact173, fact175, fact177); aggregation (fact028, fact074).

By reference: retrieval (fact001, fact002, fact005, fact013, fact014, fact017, fact018, fact024, fact031, fact034, fact046, fact053, fact055, fact056, fact075, fact079, fact094, fact111, fact120, fact130, fact131, fact134, fact147, fact157, fact168, fact175); reasoning (fact083, fact148, fact167, fact173, fact177); aggregation (fact028, fact074).

Without a reference link to judge by (1): fact025.

The two columns disagree on 26 of the 33 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact001 | reasoning | retrieval |
| fact002 | reasoning | retrieval |
| fact005 | reasoning | retrieval |
| fact013 | reasoning | retrieval |
| fact014 | reasoning | retrieval |
| fact017 | reasoning | retrieval |
| fact018 | reasoning | retrieval |
| fact024 | reasoning | retrieval |
| fact031 | reasoning | retrieval |
| fact034 | reasoning | retrieval |
| fact046 | reasoning | retrieval |
| fact053 | reasoning | retrieval |
| fact055 | reasoning | retrieval |
| fact056 | reasoning | retrieval |
| fact075 | reasoning | retrieval |
| fact079 | reasoning | retrieval |
| fact094 | reasoning | retrieval |
| fact111 | reasoning | retrieval |
| fact120 | reasoning | retrieval |
| fact130 | reasoning | retrieval |
| fact131 | reasoning | retrieval |
| fact134 | reasoning | retrieval |
| fact147 | reasoning | retrieval |
| fact157 | reasoning | retrieval |
| fact168 | reasoning | retrieval |
| fact175 | reasoning | retrieval |

## Journalist effort

Over 70 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 21 | 30.0% [20.0, 41.4] |
| Confidently wrong (definitive, not gold) | 33 | 47.1% [35.7, 58.6] |

Right and definitive but citing no source with a stance: 2 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 70 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 70 | 2.2 | 2.5 | 7.5 | 3.4% |
| Evidence retrieval | 70 | 11.3 | 17.0 | 31.6 | 18.6% |
| of which: the web search, every query | 70 | 2.3 | 3.7 | 5.5 | 3.8% |
| of which: the page fetches | 70 | 3.1 | 8.1 | 20.7 | 6.9% |
| Ranking | 70 | 5.5 | 6.1 | 8.3 | 8.1% |
| The model's verdict (with its wait for a permit) | 70 | 44.9 | 61.9 | 148.2 | 69.8% |
| of which: waiting for the model (another claim's call) | 70 | 12.6 | 22.9 | 110.8 | 20.6% |
| of which: the model's call itself | 70 | 31.0 | 40.6 | 115.5 | 49.1% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 70 | 63.1 | 80.8 | 171.1 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 70 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 94810 / 16903 |
| Tokens per claim asked (prompt / completion) | 1354.4 / 241.5 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 30.952 / 40.577 / 115.518 |
| Claim latency, median / p90 (s) | 63.073 / 80.813 |
| Completion tokens per second | 7.3 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`2605a2c02380`, host.docker.internal:11434); candidate B: this run. Paired over the 70 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 52.9% | 51.4% | -1.4 pts | [-12.9 pts, +10.0 pts] |
| macroF1 | 0.218 | 0.212 | -0.006 | [-0.053, +0.039] |
| coverage | 100.0% | 98.6% | -1.4 pts | [-4.3 pts, +0.0 pts] |
| selectiveAccuracy | 52.9% | 52.2% | -0.7 pts | [-11.6 pts, +10.2 pts] |
| kappa | 0.168 | 0.143 | -0.025 | [-0.190, +0.138] |

Only A right: 8; only B right: 7. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 70 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 69 | 14.5% | 17.4% | +2.9 pts [-4.3 pts, +10.1 pts] | 2 / 4 |
| Reference link among ranked evidence | 69 | 8.7% | 8.7% | +0.0 pts [-5.8 pts, +5.8 pts] | 2 / 2 |
| Reference link among cited evidence | 69 | 5.8% | 7.2% | +1.5 pts [-2.9 pts, +7.2 pts] | 1 / 2 |
| Reference domain among candidates | 69 | 34.8% | 27.5% | -7.2 pts [-15.9 pts, +1.5 pts] | 7 / 2 |
| Reference domain among ranked evidence | 69 | 23.2% | 15.9% | -7.2 pts [-14.5 pts, +0.0 pts] | 6 / 1 |
| Reference domain among cited evidence | 69 | 13.0% | 13.0% | +0.0 pts [-7.2 pts, +7.2 pts] | 4 / 4 |
| Link MRR (ranked) | 69 | 2.9% | 4.1% | +1.2 pts [-1.8 pts, +5.1 pts] | 2 / 4 |
| Domain MRR (ranked) | 69 | 11.8% | 8.9% | -2.9 pts [-7.6 pts, +1.3 pts] | 7 / 5 |
| Claims with any ranked evidence | 70 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 70 | 20.93 | 18.97 | -1.96 [-3.23, -0.76] |  |
| Ranked sources per claim | 70 | 4.87 | 4.96 | +0.09 [-0.03, +0.23] |  |
| Share cut at ranking (gate, cap) | 70 | 13.0% | 0.9% | -12.1 pts [-17.2 pts, -7.5 pts] |  |
| Distinct domains among ranked | 70 | 4.84 | 4.96 | +0.11 [+0.01, +0.24] |  |
| Ranked from rated domains | 70 | 6.4% | 5.9% | -0.6 pts [-3.3 pts, +1.9 pts] |  |
| Ranked from the internal corpus | 70 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 70 | 16.51 | 12.62 | -3.90 [-5.64, -2.31] |  |
| Ranking seconds per claim | 70 | 7.29 | 5.50 | -1.79 [-2.66, -0.99] |  |

# manual-test · llama3.2:3b · replayed evidence · verifier-2026-10-22-majority

Run `e7231c962477` · provider `localhost:11434` · harness v1 · thresholds `4f41294f90c7` · corpus `snapshot` (1 points)

Dataset sha256 `1ea9a8b72ec3`, 70 rows; 70 run, 0 not run. Commits: `d570ff7af980`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 70 | 56 |
| Accuracy | 55.7% [44.3%, 67.1%] | 55.4% [42.9%, 67.9%] |
| Macro-F1 (gold classes) | 0.188 [0.139, 0.242] | 0.197 [0.137, 0.260] |
| Coverage (not UNVERIFIED) | 84.3% [75.7%, 92.9%] | 82.1% [71.4%, 91.1%] |
| Selective accuracy | 66.1% [54.1%, 78.0%] | 67.4% [53.2%, 80.4%] |
| Cohen's kappa vs gold | 0.055 [-0.084, 0.204] | 0.062 [-0.107, 0.236] |

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
| temporalLeak (cited source newer than the claim) | 14 | 34 | 22 | fact006, fact013, fact014, fact030, fact050, fact057, fact078, fact084, fact111, fact119, fact150, fact161, fact167, fact173 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 70 |  |

Ranked but uncited sources newer than the claim: 13 over 13 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 68.5% | 80.4% | 0.740 | 46 | 54 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 4 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 1 | 0 |
| FALSE | 40.0% | 13.3% | 0.200 | 15 | 5 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 4 | 11 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 37 | 0 | 0 | 2 | 7 |
| PARTIALLY_TRUE | 2 | 0 | 0 | 1 | 1 |
| MISLEADING | 1 | 0 | 0 | 0 | 0 |
| FALSE | 10 | 0 | 0 | 2 | 3 |
| UNVERIFIED | 4 | 0 | 0 | 0 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 57.4% [42.6%, 72.3%] | 0.263 | 83.0% | 69.2% |
| es | 23 | 52.2% [34.8%, 73.9%] | 0.182 | 87.0% | 60.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 11 | 72.7% [45.5%, 100.0%] | 0.441 | 100.0% | 72.7% |
| environment | 18 | 50.0% [27.8%, 72.2%] | 0.267 | 77.8% | 64.3% |
| health | 16 | 62.5% [37.5%, 87.5%] | 0.278 | 87.5% | 71.4% |
| science | 16 | 56.2% [31.2%, 81.2%] | 0.188 | 81.2% | 69.2% |
| society | 9 | 33.3% [0.0%, 66.7%] | 0.136 | 77.8% | 42.9% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 44 | 61.4% [47.7%, 75.0%] | 0.289 | 81.8% | 75.0% |
| interpretive | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 50.0% | 0.0% |
| numerical | 24 | 50.0% [29.2%, 70.8%] | 0.171 | 91.7% | 54.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 3 | 33.3% [0.0%, 100.0%] | 0.222 | 66.7% | 50.0% |
| primary | 37 | 51.4% [35.1%, 67.6%] | 0.175 | 81.1% | 63.3% |
| reference_media | 30 | 63.3% [46.7%, 80.0%] | 0.263 | 90.0% | 70.4% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 13.3% [0.0%, 33.3%] | 0.235 | 80.0% | 16.7% |
| natural | 55 | 67.3% [54.5%, 80.0%] | 0.206 | 85.5% | 78.7% |

## Retrieval

70 claims searched (69 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 17.4% [8.7%, 27.5%] (n=69) |
| Reference link among ranked evidence | 8.7% [2.9%, 15.9%] (n=69) |
| Reference link among cited evidence | 8.7% [2.9%, 15.9%] (n=69) |
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
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=70) |
| Ranking seconds per claim | 7.19 [6.91, 7.47] (n=70) |

Medians: 19.50 candidates, 5.00 ranked, 0.00 s retrieval, 7.61 s ranking; 3.00 queries per claim.

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

31 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=31) | By reference (n=30) |
|---|---|---|
| retrieval | 0 (0.0%) | 25 (83.3%) |
| ranking | 0 (0.0%) | 0 (0.0%) |
| reasoning | 31 (100.0%) | 5 (16.7%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact001, fact002, fact013, fact014, fact018, fact025, fact028, fact031, fact034, fact046, fact048, fact052, fact053, fact055, fact075, fact079, fact131, fact148, fact149, fact150, fact152, fact155, fact157, fact160, fact161, fact166, fact167, fact168, fact173, fact175, fact177).

By reference: retrieval (fact001, fact002, fact013, fact014, fact018, fact028, fact031, fact034, fact046, fact048, fact052, fact053, fact055, fact075, fact079, fact131, fact149, fact152, fact155, fact157, fact160, fact161, fact166, fact168, fact175); reasoning (fact148, fact150, fact167, fact173, fact177).

Without a reference link to judge by (1): fact025.

The two columns disagree on 25 of the 30 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact001 | reasoning | retrieval |
| fact002 | reasoning | retrieval |
| fact013 | reasoning | retrieval |
| fact014 | reasoning | retrieval |
| fact018 | reasoning | retrieval |
| fact028 | reasoning | retrieval |
| fact031 | reasoning | retrieval |
| fact034 | reasoning | retrieval |
| fact046 | reasoning | retrieval |
| fact048 | reasoning | retrieval |
| fact052 | reasoning | retrieval |
| fact053 | reasoning | retrieval |
| fact055 | reasoning | retrieval |
| fact075 | reasoning | retrieval |
| fact079 | reasoning | retrieval |
| fact131 | reasoning | retrieval |
| fact149 | reasoning | retrieval |
| fact152 | reasoning | retrieval |
| fact155 | reasoning | retrieval |
| fact157 | reasoning | retrieval |
| fact160 | reasoning | retrieval |
| fact161 | reasoning | retrieval |
| fact166 | reasoning | retrieval |
| fact168 | reasoning | retrieval |
| fact175 | reasoning | retrieval |

## Journalist effort

Over 70 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 31 | 44.3% [32.9, 55.7] |
| Confidently wrong (definitive, not gold) | 20 | 28.6% [18.6, 38.6] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 70 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 70 | 2.2 | 3.7 | 9.6 | 5.9% |
| Evidence retrieval | 70 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 70 | 2.3 | 3.7 | 5.5 | 5.5% |
| of which: the page fetches | 70 | 3.1 | 8.1 | 20.7 | 10.0% |
| Ranking | 70 | 7.6 | 8.3 | 9.0 | 15.4% |
| The model's verdict (with its wait for a permit) | 70 | 34.0 | 57.9 | 73.1 | 78.7% |
| of which: waiting for the model (another claim's call) | 70 | 10.8 | 32.2 | 43.2 | 29.6% |
| of which: the model's call itself | 70 | 22.3 | 31.3 | 41.9 | 49.1% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 70 | 43.8 | 69.9 | 80.7 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 347 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 150330 / 12750 |
| Tokens per claim asked (prompt / completion) | 2147.6 / 182.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 4.207 / 7.198 / 16.445 |
| Claim latency, median / p90 (s) | 43.788 / 69.870 |
| Completion tokens per second | 7.9 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`66034c5fea72`, localhost:11434); candidate B: this run. Paired over the 70 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 51.4% | 55.7% | +4.3 pts | [-8.6 pts, +17.1 pts] |
| macroF1 | 0.212 | 0.188 | -0.024 | [-0.086, +0.038] |
| coverage | 98.6% | 84.3% | -14.3 pts | [-24.3 pts, -5.7 pts] |
| selectiveAccuracy | 52.2% | 66.1% | +13.9 pts | [+0.3 pts, +27.3 pts] |
| kappa | 0.143 | 0.055 | -0.088 | [-0.268, +0.088] |

Only A right: 9; only B right: 12. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 70 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 69 | 17.4% | 17.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 69 | 8.7% | 8.7% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 69 | 7.2% | 8.7% | +1.5 pts [+0.0 pts, +4.3 pts] | 0 / 1 |
| Reference domain among candidates | 69 | 27.5% | 27.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 69 | 15.9% | 15.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 69 | 13.0% | 13.0% | +0.0 pts [-4.3 pts, +4.3 pts] | 1 / 1 |
| Link MRR (ranked) | 69 | 4.1% | 4.1% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 69 | 8.9% | 8.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 70 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 70 | 18.97 | 18.97 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 70 | 4.96 | 4.96 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 70 | 0.9% | 0.9% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 70 | 4.96 | 4.96 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 70 | 5.9% | 5.9% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 70 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 70 | 12.62 | 0.00 | -12.61 [-14.06, -11.35] |  |
| Ranking seconds per claim | 70 | 5.50 | 7.19 | +1.69 [+1.42, +1.96] |  |

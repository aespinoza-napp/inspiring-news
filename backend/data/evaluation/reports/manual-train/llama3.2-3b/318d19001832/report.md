# manual-train · llama3.2:3b · contest-2026-10-22-full

Run `318d19001832` · provider `localhost:11434` · harness v1 · thresholds `22fd994eb2c5` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `67a65c14a325`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 69 |
| Accuracy | 33.3% [21.7%, 44.9%] | 33.3% [21.7%, 44.9%] |
| Macro-F1 (gold classes) | 0.216 [0.137, 0.296] | 0.216 [0.137, 0.296] |
| Coverage (not UNVERIFIED) | 82.6% [73.9%, 91.3%] | 82.6% [73.9%, 91.3%] |
| Selective accuracy | 38.6% [25.9%, 50.9%] | 38.6% [25.9%, 50.9%] |
| Cohen's kappa vs gold | 0.070 [-0.040, 0.184] | 0.070 [-0.040, 0.184] |

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
| temporalLeak (cited source newer than the claim) | 0 | 1 | 68 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 78.6% | 24.4% | 0.373 | 45 | 14 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 25.6% | 73.3% | 0.379 | 15 | 43 |
| UNVERIFIED | 8.3% | 16.7% | 0.111 | 6 | 12 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 11 | 0 | 0 | 27 | 7 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 1 | 1 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 1 | 0 | 0 | 11 | 3 |
| UNVERIFIED | 1 | 0 | 0 | 4 | 1 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 35.4% [22.9%, 50.0%] | 0.238 | 87.5% | 38.1% |
| es | 21 | 28.6% [9.5%, 47.6%] | 0.188 | 71.4% | 40.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 50.0% [20.0%, 80.0%] | 0.495 | 100.0% | 50.0% |
| environment | 16 | 31.2% [12.5%, 56.2%] | 0.249 | 87.5% | 28.6% |
| health | 15 | 40.0% [20.0%, 66.7%] | 0.326 | 66.7% | 60.0% |
| science | 17 | 23.5% [5.9%, 47.1%] | 0.143 | 76.5% | 30.8% |
| society | 11 | 27.3% [0.0%, 54.5%] | 0.206 | 90.9% | 30.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 43.2% [27.0%, 59.5%] | 0.308 | 89.2% | 48.5% |
| interpretive | 3 | 0.0% [0.0%, 0.0%] | 0.000 | 66.7% | 0.0% |
| numerical | 29 | 24.1% [10.3%, 41.4%] | 0.174 | 75.9% | 27.3% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| primary | 43 | 30.2% [16.3%, 44.2%] | 0.208 | 76.7% | 36.4% |
| reference_media | 25 | 40.0% [20.0%, 60.0%] | 0.227 | 92.0% | 43.5% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 73.3% [53.3%, 93.3%] | 0.846 | 80.0% | 91.7% |
| natural | 54 | 22.2% [11.1%, 33.3%] | 0.171 | 83.3% | 24.4% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 9.0% [3.0%, 16.4%] (n=67) |
| Reference link among cited evidence | 7.5% [1.5%, 13.5%] (n=67) |
| Reference domain among candidates | 34.3% [23.9%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 17.9% [9.0%, 26.9%] (n=67) |
| Reference domain among cited evidence | 9.0% [3.0%, 16.4%] (n=67) |
| Link MRR (ranked) | 7.2% [2.0%, 13.4%] (n=67) |
| Domain MRR (ranked) | 12.4% [6.0%, 19.7%] (n=67) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=69) |
| Candidates per claim | 13.07 [12.62, 13.52] (n=69) |
| Ranked sources per claim | 2.96 [2.88, 3.00] (n=69) |
| Share cut at ranking (gate, cap) | 1.5% [0.0%, 3.9%] (n=69) |
| Distinct domains among ranked | 2.96 [2.88, 3.00] (n=69) |
| Ranked from rated domains | 6.3% [2.9%, 10.1%] (n=69) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=69) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 2.56 [2.25, 2.88] (n=69) |
| Ranking seconds per claim | 0.73 [0.67, 0.81] (n=69) |

Medians: 12.00 candidates, 3.00 ranked, 2.21 s retrieval, 0.65 s ranking; 2.00 queries per claim.

Ranked sources found by: proposition 152, anchor 83 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2
- evidence_retrieval: cut by pre-rank funnel (rank 4 of 10, top 3 kept): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 9.0% | 17.9% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 10.9% | 17.4% | 100.0% |
| es | 21 | 21 | 4.8% | 19.1% | 100.0% |

## Stage attribution

46 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=46) | By reference (n=44) |
|---|---|---|
| retrieval | 0 (0.0%) | 27 (61.4%) |
| ranking | 0 (0.0%) | 6 (13.6%) |
| reasoning | 43 (93.5%) | 8 (18.2%) |
| aggregation | 3 (6.5%) | 3 (6.8%) |

Trace only: reasoning (fact008, fact009, fact010, fact011, fact016, fact020, fact021, fact037, fact038, fact049, fact062, fact063, fact064, fact066, fact081, fact082, fact085, fact086, fact099, fact101, fact106, fact107, fact114, fact116, fact117, fact118, fact122, fact124, fact125, fact126, fact127, fact128, fact129, fact132, fact133, fact138, fact139, fact140, fact141, fact143, fact144, fact145, fact169); aggregation (fact153, fact158, fact178).

By reference: retrieval (fact008, fact009, fact016, fact020, fact021, fact037, fact062, fact064, fact066, fact081, fact101, fact107, fact114, fact116, fact118, fact122, fact124, fact125, fact127, fact128, fact132, fact133, fact138, fact140, fact141, fact143, fact144); ranking (fact010, fact038, fact082, fact126, fact139, fact145); reasoning (fact011, fact063, fact085, fact086, fact106, fact117, fact129, fact169); aggregation (fact153, fact158, fact178).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 4
- evidence_retrieval: same domain as a higher-ranked source (whc.unesco.org): 3
- evidence_retrieval: same domain as a higher-ranked source (esa.int): 2
- evidence_retrieval: cut by pre-rank funnel (rank 4 of 8, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 7 of 15, top 3 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (nsidc.org): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 11, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 5 of 8, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 4 of 4, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 5 of 9, top 3 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 33 of the 44 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact010 | reasoning | ranking |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact021 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact038 | reasoning | ranking |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact082 | reasoning | ranking |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact116 | reasoning | retrieval |
| fact118 | reasoning | retrieval |
| fact122 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact125 | reasoning | retrieval |
| fact126 | reasoning | ranking |
| fact127 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact132 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact139 | reasoning | ranking |
| fact140 | reasoning | retrieval |
| fact141 | reasoning | retrieval |
| fact143 | reasoning | retrieval |
| fact144 | reasoning | retrieval |
| fact145 | reasoning | ranking |

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 19 | 27.5% [17.4, 37.7] |
| Confidently wrong (definitive, not gold) | 35 | 50.7% [39.1, 62.3] |

Right and definitive but citing no source with a stance: 3 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.1 | 2.6 | 4.4 | 11.2% |
| Evidence retrieval | 69 | 2.2 | 4.5 | 5.3 | 17.5% |
| of which: the web search, every query | 69 | 1.2 | 2.1 | 3.5 | 9.1% |
| of which: the page fetches | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 69 | 0.6 | 0.9 | 2.4 | 5.0% |
| The model's verdict (with its wait for a permit) | 69 | 9.5 | 12.6 | 15.1 | 66.3% |
| of which: waiting for the model (another claim's call) | 69 | 2.5 | 5.4 | 7.7 | 17.5% |
| of which: the model's call itself | 69 | 7.0 | 8.5 | 11.2 | 48.7% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 14.2 | 17.0 | 21.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 69 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 34841 / 3965 |
| Tokens per claim asked (prompt / completion) | 504.9 / 57.5 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 6.971 / 8.530 / 11.171 |
| Claim latency, median / p90 (s) | 14.186 / 17.038 |
| Completion tokens per second | 8.0 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`340a36ac8972`, localhost:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 50.7% | 33.3% | -17.4 pts | [-30.4 pts, -4.3 pts] |
| macroF1 | 0.267 | 0.216 | -0.051 | [-0.131, +0.034] |
| coverage | 98.6% | 82.6% | -15.9 pts | [-26.1 pts, -7.2 pts] |
| selectiveAccuracy | 51.5% | 38.6% | -12.9 pts | [-26.6 pts, +0.7 pts] |
| kappa | 0.172 | 0.070 | -0.102 | [-0.262, +0.051] |

Only A right: 17; only B right: 5. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [-4.5 pts, +4.5 pts] | 1 / 1 |
| Reference link among ranked evidence | 67 | 9.0% | 9.0% | +0.0 pts [-4.5 pts, +4.5 pts] | 1 / 1 |
| Reference link among cited evidence | 67 | 9.0% | 7.5% | -1.5 pts [-6.0 pts, +3.0 pts] | 2 / 1 |
| Reference domain among candidates | 67 | 34.3% | 34.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 25.4% | 17.9% | -7.5 pts [-14.9 pts, +0.0 pts] | 6 / 1 |
| Reference domain among cited evidence | 67 | 17.9% | 9.0% | -9.0 pts [-17.9 pts, -1.5 pts] | 7 / 1 |
| Link MRR (ranked) | 67 | 8.2% | 7.2% | -1.0 pts [-3.5 pts, +1.0 pts] | 2 / 1 |
| Domain MRR (ranked) | 67 | 17.9% | 12.4% | -5.5 pts [-12.0 pts, +0.2 pts] | 8 / 4 |
| Claims with any ranked evidence | 69 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 17.86 | 13.07 | -4.78 [-5.38, -4.20] |  |
| Ranked sources per claim | 69 | 4.72 | 2.96 | -1.77 [-1.90, -1.59] |  |
| Share cut at ranking (gate, cap) | 69 | 4.0% | 1.5% | -2.5 pts [-5.2 pts, -0.1 pts] |  |
| Distinct domains among ranked | 69 | 4.72 | 2.96 | -1.77 [-1.90, -1.59] |  |
| Ranked from rated domains | 69 | 6.7% | 6.3% | -0.4 pts [-2.4 pts, +1.6 pts] |  |
| Ranked from the internal corpus | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 12.61 | 2.56 | -10.05 [-11.81, -8.61] |  |
| Ranking seconds per claim | 69 | 6.37 | 0.73 | -5.63 [-6.04, -5.24] |  |

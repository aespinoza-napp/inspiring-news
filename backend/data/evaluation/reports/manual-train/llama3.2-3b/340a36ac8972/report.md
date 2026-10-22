# manual-train · llama3.2:3b · contest-2026-10-22-full

Run `340a36ac8972` · provider `localhost:11434` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `67a65c14a325`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 52 |
| Accuracy | 50.7% [39.1%, 62.3%] | 48.1% [34.6%, 61.5%] |
| Macro-F1 (gold classes) | 0.267 [0.205, 0.324] | 0.258 [0.186, 0.324] |
| Coverage (not UNVERIFIED) | 98.6% [95.7%, 100.0%] | 98.1% [94.2%, 100.0%] |
| Selective accuracy | 51.5% [39.7%, 63.2%] | 49.0% [35.3%, 62.7%] |
| Cohen's kappa vs gold | 0.172 [0.016, 0.330] | 0.153 [-0.022, 0.334] |

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
| temporalLeak (cited source newer than the claim) | 17 | 27 | 25 | fact036, fact062, fact065, fact089, fact099, fact100, fact118, fact122, fact128, fact133, fact142, fact143, fact144, fact145, fact146, fact162, fact163 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 14 over 12 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 76.7% | 51.1% | 0.613 | 45 | 30 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 31.6% | 80.0% | 0.453 | 15 | 38 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 6 | 1 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 23 | 0 | 0 | 21 | 1 |
| PARTIALLY_TRUE | 2 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 3 | 0 | 0 | 12 | 0 |
| UNVERIFIED | 2 | 0 | 0 | 4 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 50.0% [35.4%, 64.6%] | 0.263 | 97.9% | 51.1% |
| es | 21 | 52.4% [33.3%, 71.4%] | 0.274 | 100.0% | 52.4% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 50.0% [20.0%, 80.0%] | 0.451 | 100.0% | 50.0% |
| environment | 16 | 56.2% [31.2%, 81.2%] | 0.333 | 93.8% | 60.0% |
| health | 15 | 60.0% [33.3%, 86.7%] | 0.404 | 100.0% | 60.0% |
| science | 17 | 47.1% [23.5%, 70.6%] | 0.247 | 100.0% | 47.1% |
| society | 11 | 36.4% [9.1%, 63.6%] | 0.269 | 100.0% | 36.4% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 59.5% [43.2%, 75.7%] | 0.381 | 100.0% | 59.5% |
| interpretive | 3 | 66.7% [0.0%, 100.0%] | 0.800 | 100.0% | 66.7% |
| numerical | 29 | 37.9% [20.7%, 55.2%] | 0.224 | 96.6% | 39.3% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| primary | 43 | 53.5% [39.5%, 67.4%] | 0.281 | 97.7% | 54.8% |
| reference_media | 25 | 48.0% [28.0%, 68.0%] | 0.254 | 100.0% | 48.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 80.0% [60.0%, 100.0%] | 0.889 | 100.0% | 80.0% |
| natural | 54 | 42.6% [29.6%, 55.6%] | 0.213 | 98.1% | 43.4% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 9.0% [3.0%, 16.4%] (n=67) |
| Reference link among cited evidence | 9.0% [3.0%, 16.4%] (n=67) |
| Reference domain among candidates | 34.3% [23.9%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 25.4% [14.9%, 35.8%] (n=67) |
| Reference domain among cited evidence | 17.9% [9.0%, 26.9%] (n=67) |
| Link MRR (ranked) | 8.2% [2.2%, 14.9%] (n=67) |
| Domain MRR (ranked) | 17.9% [10.0%, 26.5%] (n=67) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=69) |
| Candidates per claim | 17.86 [17.03, 18.72] (n=69) |
| Ranked sources per claim | 4.72 [4.54, 4.87] (n=69) |
| Share cut at ranking (gate, cap) | 4.0% [1.9%, 6.4%] (n=69) |
| Distinct domains among ranked | 4.72 [4.54, 4.87] (n=69) |
| Ranked from rated domains | 6.7% [3.8%, 9.9%] (n=69) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=69) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 12.61 [11.18, 14.38] (n=69) |
| Ranking seconds per claim | 6.37 [5.98, 6.76] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 10.88 s retrieval, 6.42 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 207, anchor 124, refutation 77 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2
- evidence_retrieval: cut by pre-rank funnel (rank 7 of 14, top 5 kept): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 9.0% | 25.4% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 13.0% | 28.3% | 100.0% |
| es | 21 | 21 | 0.0% | 19.1% | 100.0% |

## Stage attribution

34 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=34) | By reference (n=32) |
|---|---|---|
| retrieval | 0 (0.0%) | 22 (68.8%) |
| ranking | 0 (0.0%) | 1 (3.1%) |
| reasoning | 34 (100.0%) | 9 (28.1%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact009, fact010, fact011, fact015, fact016, fact020, fact037, fact049, fact064, fact066, fact081, fact085, fact088, fact099, fact100, fact101, fact107, fact114, fact117, fact123, fact125, fact126, fact128, fact129, fact133, fact138, fact139, fact140, fact143, fact144, fact145, fact153, fact169, fact171).

By reference: retrieval (fact009, fact015, fact016, fact020, fact037, fact064, fact066, fact081, fact100, fact101, fact107, fact114, fact123, fact125, fact128, fact133, fact138, fact140, fact143, fact144, fact153, fact171); ranking (fact117); reasoning (fact010, fact011, fact085, fact088, fact126, fact129, fact139, fact145, fact169).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: cut by pre-rank funnel (rank 7 of 14, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (es.wikipedia.org): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 23 of the 32 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact117 | reasoning | ranking |
| fact123 | reasoning | retrieval |
| fact125 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact140 | reasoning | retrieval |
| fact143 | reasoning | retrieval |
| fact144 | reasoning | retrieval |
| fact153 | reasoning | retrieval |
| fact171 | reasoning | retrieval |

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 23 | 33.3% [23.2, 44.9] |
| Confidently wrong (definitive, not gold) | 33 | 47.8% [36.2, 59.4] |

Right and definitive but citing no source with a stance: 3 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.2 | 2.7 | 9.2 | 3.9% |
| Evidence retrieval | 69 | 10.9 | 17.7 | 49.5 | 19.9% |
| of which: the web search, every query | 69 | 2.3 | 3.5 | 4.8 | 3.9% |
| of which: the page fetches | 69 | 2.3 | 9.2 | 40.9 | 6.8% |
| Ranking | 69 | 6.4 | 8.3 | 10.6 | 10.1% |
| The model's verdict (with its wait for a permit) | 69 | 41.4 | 59.6 | 77.5 | 66.1% |
| of which: waiting for the model (another claim's call) | 69 | 8.5 | 23.8 | 38.6 | 17.1% |
| of which: the model's call itself | 69 | 28.4 | 46.1 | 53.2 | 48.3% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 61.4 | 85.3 | 105.3 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 69 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 90366 / 13419 |
| Tokens per claim asked (prompt / completion) | 1309.7 / 194.5 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 28.391 / 46.109 / 53.173 |
| Claim latency, median / p90 (s) | 61.411 / 85.289 |
| Completion tokens per second | 6.4 |
| Cost | n/a (no price given, or tokens unknown) |

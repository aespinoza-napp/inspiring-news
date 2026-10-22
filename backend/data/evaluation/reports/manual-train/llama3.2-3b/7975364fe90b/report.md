# manual-train · llama3.2:3b · replayed evidence · verifier-2026-10-22-quote-first

Run `7975364fe90b` · provider `localhost:11434` · harness v1 · thresholds `4f41294f90c7` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `d2ec95f91e90`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 41 |
| Accuracy | 47.8% [36.2%, 59.4%] | 46.3% [31.7%, 61.0%] |
| Macro-F1 (gold classes) | 0.264 [0.188, 0.343] | 0.257 [0.147, 0.376] |
| Coverage (not UNVERIFIED) | 82.6% [73.9%, 91.3%] | 78.0% [65.9%, 90.2%] |
| Selective accuracy | 56.1% [43.3%, 68.5%] | 56.2% [38.7%, 73.3%] |
| Cohen's kappa vs gold | 0.108 [-0.045, 0.260] | 0.034 [-0.177, 0.258] |

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
| temporalLeak (cited source newer than the claim) | 28 | 19 | 22 | fact009, fact010, fact020, fact036, fact037, fact038, fact049, fact062, fact065, fact066, fact085, fact088, fact099, fact100, fact101, fact118, fact128, fact133, fact138, fact142, fact143, fact144, fact146, fact159, fact162, fact163, fact174, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 9 over 9 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 77.1% | 60.0% | 0.675 | 45 | 35 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 22.7% | 33.3% | 0.270 | 15 | 22 |
| UNVERIFIED | 8.3% | 16.7% | 0.111 | 6 | 12 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 27 | 0 | 0 | 11 | 7 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 6 | 0 | 0 | 5 | 4 |
| UNVERIFIED | 1 | 0 | 0 | 4 | 1 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 45.8% [31.2%, 60.4%] | 0.233 | 85.4% | 53.7% |
| es | 21 | 52.4% [33.3%, 71.4%] | 0.314 | 76.2% | 62.5% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 70.0% [40.0%, 100.0%] | 0.600 | 100.0% | 70.0% |
| environment | 16 | 56.2% [31.2%, 81.2%] | 0.295 | 100.0% | 56.2% |
| health | 15 | 46.7% [20.0%, 73.3%] | 0.306 | 80.0% | 58.3% |
| science | 17 | 47.1% [23.5%, 70.6%] | 0.225 | 88.2% | 53.3% |
| society | 11 | 18.2% [0.0%, 45.5%] | 0.157 | 36.4% | 25.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 56.8% [40.5%, 73.0%] | 0.365 | 81.1% | 70.0% |
| interpretive | 3 | 66.7% [0.0%, 100.0%] | 0.800 | 100.0% | 66.7% |
| numerical | 29 | 34.5% [17.2%, 51.7%] | 0.235 | 82.8% | 37.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 51.2% [37.2%, 65.1%] | 0.315 | 90.7% | 53.8% |
| reference_media | 25 | 40.0% [20.0%, 60.0%] | 0.212 | 68.0% | 58.8% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 33.3% [13.3%, 60.0%] | 0.500 | 73.3% | 45.5% |
| natural | 54 | 51.9% [38.9%, 64.8%] | 0.291 | 85.2% | 58.7% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 26.9% [16.4%, 37.3%] (n=67) |
| Reference domain among cited evidence | 23.9% [13.4%, 34.3%] (n=67) |
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
| Ranking seconds per claim | 8.15 [7.74, 8.54] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 8.28 s ranking; 3.00 queries per claim.

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

36 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=36) | By reference (n=34) |
|---|---|---|
| retrieval | 0 (0.0%) | 24 (70.6%) |
| ranking | 0 (0.0%) | 2 (5.9%) |
| reasoning | 36 (100.0%) | 8 (23.5%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact008, fact009, fact010, fact012, fact015, fact016, fact037, fact049, fact062, fact063, fact066, fact081, fact086, fact099, fact100, fact101, fact106, fact107, fact114, fact125, fact128, fact129, fact138, fact139, fact144, fact145, fact151, fact153, fact154, fact156, fact159, fact165, fact169, fact172, fact174, fact178).

By reference: retrieval (fact008, fact009, fact010, fact012, fact015, fact016, fact037, fact062, fact066, fact081, fact100, fact101, fact107, fact114, fact125, fact128, fact138, fact144, fact151, fact153, fact159, fact165, fact174, fact178); ranking (fact145, fact156); reasoning (fact063, fact086, fact106, fact129, fact139, fact154, fact169, fact172).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (esa.int): 3
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 9, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 14, top 5 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 26 of the 34 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact010 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact125 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact144 | reasoning | retrieval |
| fact145 | reasoning | ranking |
| fact151 | reasoning | retrieval |
| fact153 | reasoning | retrieval |
| fact156 | reasoning | ranking |
| fact159 | reasoning | retrieval |
| fact165 | reasoning | retrieval |
| fact174 | reasoning | retrieval |
| fact178 | reasoning | retrieval |

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 18 | 26.1% [15.9, 36.2] |
| Confidently wrong (definitive, not gold) | 25 | 36.2% [24.6, 47.8] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 2.2 | 2.6 | 10.8 | 5.1% |
| Evidence retrieval | 69 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 69 | 2.3 | 3.6 | 5.1 | 4.9% |
| of which: the page fetches | 69 | 2.6 | 10.8 | 40.1 | 9.4% |
| Ranking | 69 | 8.3 | 10.1 | 12.2 | 15.8% |
| The model's verdict (with its wait for a permit) | 69 | 37.5 | 61.8 | 87.7 | 79.0% |
| of which: waiting for the model (another claim's call) | 69 | 13.5 | 30.5 | 55.7 | 28.4% |
| of which: the model's call itself | 69 | 25.8 | 32.9 | 42.5 | 49.4% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 48.5 | 73.5 | 99.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 322 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 141886 / 12925 |
| Tokens per claim asked (prompt / completion) | 2056.3 / 187.3 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 5.033 / 8.089 / 17.470 |
| Claim latency, median / p90 (s) | 48.455 / 73.530 |
| Completion tokens per second | 7.4 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`a2b3a553f3c0`, localhost:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 47.8% | 47.8% | +0.0 pts | [-13.0 pts, +13.0 pts] |
| macroF1 | 0.304 | 0.264 | -0.040 | [-0.144, +0.063] |
| coverage | 68.1% | 82.6% | +14.5 pts | [+1.4 pts, +27.5 pts] |
| selectiveAccuracy | 61.7% | 56.1% | -5.6 pts | [-18.8 pts, +7.5 pts] |
| kappa | 0.117 | 0.108 | -0.010 | [-0.192, +0.174] |

Only A right: 11; only B right: 11. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 10.4% | 10.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 7.5% | 10.4% | +3.0 pts [+0.0 pts, +7.5 pts] | 0 / 2 |
| Reference domain among candidates | 67 | 32.8% | 32.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 26.9% | 26.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 16.4% | 23.9% | +7.5 pts [+1.5 pts, +14.9 pts] | 0 / 5 |
| Link MRR (ranked) | 67 | 8.1% | 8.1% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 67 | 16.6% | 16.6% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 69 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 17.26 | 17.26 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 69 | 4.67 | 4.67 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 69 | 4.1% | 4.1% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 69 | 4.67 | 4.67 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 69 | 6.2% | 6.2% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 0.00 | 0.00 | +0.00 [-0.00, +0.00] |  |
| Ranking seconds per claim | 69 | 7.29 | 8.15 | +0.86 [+0.50, +1.22] |  |

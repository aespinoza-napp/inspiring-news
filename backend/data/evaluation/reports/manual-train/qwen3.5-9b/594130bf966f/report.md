# manual-train · qwen3.5:9b · replayed evidence · verifier-2026-10-22

Run `594130bf966f` · provider `localhost:11434` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `d570ff7af980`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 67 | 44 |
| Accuracy | 50.7% [38.8%, 62.7%] | 43.2% [29.5%, 56.8%] |
| Macro-F1 (gold classes) | 0.358 [0.268, 0.443] | 0.310 [0.201, 0.410] |
| Coverage (not UNVERIFIED) | 68.7% [56.7%, 79.1%] | 59.1% [45.5%, 72.7%] |
| Selective accuracy | 67.4% [53.7%, 80.4%] | 65.4% [46.4%, 83.3%] |
| Cohen's kappa vs gold | 0.282 [0.144, 0.425] | 0.226 [0.089, 0.381] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 2 | fact081, fact100 |
| scored | 67 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 23 | 32 | 12 | fact010, fact020, fact021, fact036, fact037, fact038, fact062, fact064, fact066, fact088, fact089, fact099, fact118, fact128, fact142, fact143, fact144, fact146, fact159, fact162, fact163, fact174, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 67 |  |

Ranked but uncited sources newer than the claim: 16 over 13 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 90.9% | 45.5% | 0.606 | 44 | 22 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 2 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 50.0% | 73.3% | 0.595 | 15 | 22 |
| UNVERIFIED | 14.3% | 60.0% | 0.231 | 5 | 21 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 20 | 2 | 0 | 8 | 14 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 11 | 4 |
| UNVERIFIED | 1 | 0 | 0 | 1 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 46 | 43.5% [28.3%, 58.7%] | 0.297 | 65.2% | 63.3% |
| es | 21 | 66.7% [47.6%, 85.7%] | 0.505 | 76.2% | 75.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 80.0% [50.0%, 100.0%] | 0.917 | 90.0% | 88.9% |
| environment | 15 | 26.7% [6.7%, 46.7%] | 0.202 | 66.7% | 40.0% |
| health | 15 | 60.0% [33.3%, 86.7%] | 0.435 | 86.7% | 69.2% |
| science | 16 | 56.2% [31.2%, 81.2%] | 0.385 | 68.8% | 72.7% |
| society | 11 | 36.4% [9.1%, 63.6%] | 0.362 | 27.3% | 66.7% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 54.1% [37.8%, 70.3%] | 0.444 | 67.6% | 80.0% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 66.7% | 50.0% |
| numerical | 27 | 48.1% [29.6%, 66.7%] | 0.372 | 70.4% | 52.6% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 41 | 53.7% [39.0%, 68.3%] | 0.381 | 68.3% | 71.4% |
| reference_media | 25 | 44.0% [24.0%, 64.0%] | 0.315 | 68.0% | 58.8% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 73.3% [46.7%, 93.3%] | 0.846 | 73.3% | 100.0% |
| natural | 52 | 44.2% [30.8%, 57.7%] | 0.293 | 67.3% | 57.1% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 9.0% [3.0%, 16.4%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 26.9% [16.4%, 37.3%] (n=67) |
| Reference domain among cited evidence | 10.4% [4.5%, 17.9%] (n=67) |
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
| Ranking seconds per claim | 8.30 [7.93, 8.65] (n=69) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 8.17 s ranking; 3.00 queries per claim.

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

| Stage | Trace only (n=33) | By reference (n=32) |
|---|---|---|
| retrieval | 0 (0.0%) | 22 (68.8%) |
| ranking | 0 (0.0%) | 4 (12.5%) |
| reasoning | 33 (100.0%) | 6 (18.8%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact008, fact009, fact012, fact015, fact016, fact021, fact036, fact037, fact038, fact062, fact063, fact064, fact066, fact082, fact099, fact101, fact106, fact107, fact114, fact115, fact122, fact124, fact127, fact129, fact132, fact133, fact138, fact139, fact145, fact151, fact154, fact156, fact165).

By reference: retrieval (fact008, fact009, fact012, fact015, fact016, fact021, fact037, fact062, fact064, fact066, fact101, fact107, fact114, fact115, fact122, fact124, fact127, fact132, fact133, fact138, fact151, fact165); ranking (fact036, fact082, fact145, fact156); reasoning (fact038, fact063, fact106, fact129, fact139, fact154).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (esa.int): 3
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 12, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 13, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 9, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 14, top 5 kept): 1

Without a reference link to judge by (1): fact099.

The two columns disagree on 26 of the 32 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact021 | reasoning | retrieval |
| fact036 | reasoning | ranking |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact082 | reasoning | ranking |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact115 | reasoning | retrieval |
| fact122 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact127 | reasoning | retrieval |
| fact132 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact145 | reasoning | ranking |
| fact151 | reasoning | retrieval |
| fact156 | reasoning | ranking |
| fact165 | reasoning | retrieval |

## Journalist effort

Over 67 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 17 | 25.4% [14.9, 35.8] |
| Confidently wrong (definitive, not gold) | 15 | 22.4% [13.4, 32.8] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 67 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 67 | 2.2 | 2.5 | 10.6 | 1.2% |
| Evidence retrieval | 67 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 67 | 2.3 | 3.6 | 5.1 | 1.3% |
| of which: the page fetches | 67 | 2.6 | 11.6 | 40.1 | 2.5% |
| Ranking | 67 | 8.2 | 10.6 | 11.3 | 4.1% |
| The model's verdict (with its wait for a permit) | 67 | 184.8 | 246.6 | 543.0 | 94.7% |
| of which: waiting for the model (another claim's call) | 67 | 83.1 | 160.2 | 205.3 | 45.6% |
| of which: the model's call itself | 67 | 90.5 | 132.4 | 337.2 | 48.8% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 67 | 196.0 | 254.8 | 556.4 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 72 (5) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 86230 / 22758 |
| Tokens per claim asked (prompt / completion) | 1287.0 / 339.7 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 90.510 / 132.415 / 176.463 |
| Claim latency, median / p90 (s) | 196.267 / 258.941 |
| Completion tokens per second | 3.6 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`2a4d7dde37b2`, localhost:11434); candidate B: this run. Paired over the 67 claims both scored; 2 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 46.3% | 50.7% | +4.5 pts | [-10.4 pts, +19.4 pts] |
| macroF1 | 0.247 | 0.358 | +0.111 | [+0.012, +0.213] |
| coverage | 97.0% | 68.7% | -28.4 pts | [-40.3 pts, -16.4 pts] |
| selectiveAccuracy | 47.7% | 67.4% | +19.7 pts | [+4.1 pts, +35.6 pts] |
| kappa | 0.141 | 0.282 | +0.141 | [-0.040, +0.335] |

Only A right: 12; only B right: 15. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 13.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 10.4% | 10.4% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 7.5% | 9.0% | +1.5 pts [+0.0 pts, +4.5 pts] | 0 / 1 |
| Reference domain among candidates | 67 | 32.8% | 32.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 26.9% | 26.9% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 16.4% | 10.4% | -6.0 pts [-13.4 pts, +0.0 pts] | 5 / 1 |
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
| Ranking seconds per claim | 69 | 6.35 | 8.30 | +1.95 [+1.56, +2.33] |  |

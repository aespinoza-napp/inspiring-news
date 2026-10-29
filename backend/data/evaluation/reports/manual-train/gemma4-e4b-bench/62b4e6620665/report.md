# manual-train · gemma4:e4b-bench · replayed evidence

Run `62b4e6620665` · provider `localhost:11434` · harness v1 · thresholds `8467acf4a489` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 20 run, 49 not run. Commits: `ca9f3ddeb88d`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 20 | 14 |
| Accuracy | 45.0% [25.0%, 65.0%] | 50.0% [21.4%, 78.6%] |
| Macro-F1 (gold classes) | 0.348 [0.165, 0.499] | 0.539 [0.231, 0.795] |
| Coverage (not UNVERIFIED) | 55.0% [35.0%, 75.0%] | 42.9% [14.3%, 71.4%] |
| Selective accuracy | 54.5% [23.1%, 83.3%] | 66.7% [25.0%, 100.0%] |
| Cohen's kappa vs gold | 0.179 [-0.024, 0.424] | 0.234 [0.000, 0.556] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 20 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 6 | 11 | 3 | fact009, fact012, fact020, fact038, fact062, fact066 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 20 |  |

Ranked but uncited sources newer than the claim: 6 over 5 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 85.7% | 40.0% | 0.545 | 15 | 7 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 2 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 4 |
| UNVERIFIED | 33.3% | 100.0% | 0.500 | 3 | 9 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 6 | 0 | 0 | 3 | 6 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 0 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 14 | 35.7% [14.3%, 64.3%] | 0.360 | 50.0% | 57.1% |
| es | 6 | 66.7% [33.3%, 100.0%] | 0.600 | 66.7% | 50.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 8 | 37.5% [12.5%, 75.0%] | 0.273 | 62.5% | 60.0% |
| health | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 100.0% | 33.3% |
| science | 5 | 40.0% [0.0%, 80.0%] | 0.333 | 40.0% | 50.0% |
| society | 4 | 75.0% [25.0%, 100.0%] | 0.733 | 25.0% | 100.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 6 | 50.0% [16.7%, 83.3%] | 0.333 | 83.3% | 60.0% |
| interpretive | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 0.0% | n/a |
| numerical | 13 | 46.2% [23.1%, 69.2%] | 0.367 | 46.2% | 50.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 15 | 33.3% [13.3%, 60.0%] | 0.258 | 46.7% | 42.9% |
| reference_media | 5 | 80.0% [40.0%, 100.0%] | 0.667 | 80.0% | 75.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 20 | 45.0% [25.0%, 65.0%] | 0.348 | 55.0% | 54.5% |

## Retrieval

20 claims searched (19 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 5.3% [0.0%, 15.8%] (n=19) |
| Reference link among ranked evidence | 5.3% [0.0%, 15.8%] (n=19) |
| Reference link among cited evidence | 5.3% [0.0%, 15.8%] (n=19) |
| Reference domain among candidates | 36.8% [15.8%, 57.9%] (n=19) |
| Reference domain among ranked evidence | 26.3% [10.5%, 47.4%] (n=19) |
| Reference domain among cited evidence | 10.5% [0.0%, 26.3%] (n=19) |
| Link MRR (ranked) | 5.3% [0.0%, 15.8%] (n=19) |
| Domain MRR (ranked) | 21.1% [5.3%, 39.5%] (n=19) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=20) |
| Candidates per claim | 17.85 [16.25, 19.55] (n=20) |
| Ranked sources per claim | 4.75 [4.50, 4.95] (n=20) |
| Share cut at ranking (gate, cap) | 5.0% [1.0%, 10.0%] (n=20) |
| Distinct domains among ranked | 4.75 [4.50, 4.95] (n=20) |
| Ranked from rated domains | 8.0% [3.0%, 13.0%] (n=20) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=20) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=20) |
| Ranking seconds per claim | 24.26 [21.07, 27.51] (n=20) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 23.80 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 62, anchor 34, refutation 25 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 20 | 19 | 5.3% | 26.3% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 14 | 13 | 7.7% | 15.4% | 100.0% |
| es | 6 | 6 | 0.0% | 50.0% | 100.0% |

## Stage attribution

11 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=11) | By reference (n=11) |
|---|---|---|
| retrieval | 0 (0.0%) | 8 (72.7%) |
| ranking | 0 (0.0%) | 2 (18.2%) |
| reasoning | 11 (100.0%) | 1 (9.1%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact009, fact016, fact021, fact036, fact037, fact038, fact062, fact064, fact066, fact081, fact082).

By reference: retrieval (fact009, fact016, fact021, fact037, fact062, fact064, fact066, fact081); ranking (fact036, fact082); reasoning (fact038).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: cut by pre-rank funnel (rank 13 of 14, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 12, top 5 kept): 1

The two columns disagree on 10 of the 11 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact021 | reasoning | retrieval |
| fact036 | reasoning | ranking |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact082 | reasoning | ranking |

## Journalist effort

Over 20 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 4 | 20.0% [5.0, 40.0] |
| Confidently wrong (definitive, not gold) | 5 | 25.0% [10.0, 45.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 20 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 20 | 3.0 | 4.3 | 9.1 | 1.4% |
| Evidence retrieval | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 20 | 2.6 | 4.7 | 5.2 | 1.3% |
| of which: the page fetches | 20 | 2.4 | 5.1 | 9.0 | 1.4% |
| Ranking | 20 | 23.8 | 31.1 | 42.6 | 11.1% |
| The model's verdict (with its wait for a permit) | 20 | 177.5 | 283.2 | 382.9 | 87.5% |
| of which: waiting for the model (another claim's call) | 20 | 70.9 | 124.9 | 282.7 | 37.4% |
| of which: the model's call itself | 20 | 100.1 | 162.3 | 201.5 | 50.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 20 | 203.9 | 308.1 | 428.3 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 95 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 40520 / 2541 |
| Tokens per claim asked (prompt / completion) | 2026.0 / 127.0 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 18.505 / 39.716 / 73.849 |
| Claim latency, median / p90 (s) | 203.876 / 308.141 |
| Completion tokens per second | 1.2 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`cc053417c0cb`, localhost:11434); candidate B: this run. Paired over the 20 claims both scored; 0 set apart on either side, 49 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 55.0% | 45.0% | -10.0 pts | [-35.0 pts, +15.0 pts] |
| macroF1 | 0.325 | 0.348 | +0.023 | [-0.163, +0.211] |
| coverage | 80.0% | 55.0% | -25.0 pts | [-45.0 pts, -10.0 pts] |
| selectiveAccuracy | 62.5% | 54.5% | -8.0 pts | [-35.8 pts, +19.6 pts] |
| kappa | -0.011 | 0.179 | +0.190 | [-0.141, +0.504] |

Only A right: 4; only B right: 2. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 20 claims both searched (49 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 19 | 36.8% | 36.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 19 | 26.3% | 26.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 19 | 15.8% | 10.5% | -5.3 pts [-15.8 pts, +0.0 pts] | 1 / 0 |
| Link MRR (ranked) | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 19 | 21.1% | 21.1% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 20 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 20 | 17.85 | 17.85 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 20 | 4.75 | 4.75 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 20 | 5.0% | 5.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 20 | 4.75 | 4.75 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 20 | 8.0% | 8.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 20 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 20 | 15.05 | 0.00 | -15.05 [-17.08, -13.00] |  |
| Ranking seconds per claim | 20 | 18.17 | 24.26 | +6.09 [+2.18, +10.02] |  |

# manual-train · granite3.3:8b-bench · replayed evidence

Run `91d96d61a714` · provider `localhost:11434` · harness v1 · thresholds `8467acf4a489` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 20 run, 49 not run. Commits: `ca9f3ddeb88d`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 20 | 14 |
| Accuracy | 60.0% [40.0%, 80.0%] | 57.1% [28.6%, 85.7%] |
| Macro-F1 (gold classes) | 0.438 [0.230, 0.619] | 0.639 [0.294, 0.909] |
| Coverage (not UNVERIFIED) | 95.0% [85.0%, 100.0%] | 92.9% [78.6%, 100.0%] |
| Selective accuracy | 57.9% [35.3%, 78.9%] | 53.8% [27.3%, 81.8%] |
| Cohen's kappa vs gold | 0.263 [0.024, 0.520] | 0.276 [0.000, 0.576] |

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
| temporalLeak (cited source newer than the claim) | 6 | 2 | 12 | fact009, fact012, fact020, fact038, fact062, fact066 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 20 |  |

Ranked but uncited sources newer than the claim: 4 over 3 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 91.7% | 73.3% | 0.815 | 15 | 12 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 2 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 7 |
| UNVERIFIED | 100.0% | 33.3% | 0.500 | 3 | 1 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 11 | 0 | 0 | 4 | 0 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 2 | 1 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 14 | 64.3% [35.7%, 85.7%] | 0.409 | 100.0% | 64.3% |
| es | 6 | 50.0% [16.7%, 83.3%] | 0.489 | 83.3% | 40.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 8 | 87.5% [62.5%, 100.0%] | 0.467 | 100.0% | 87.5% |
| health | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 100.0% | 33.3% |
| science | 5 | 40.0% [0.0%, 80.0%] | 0.267 | 100.0% | 40.0% |
| society | 4 | 50.0% [0.0%, 100.0%] | 0.667 | 75.0% | 33.3% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 6 | 83.3% [50.0%, 100.0%] | 0.455 | 100.0% | 83.3% |
| interpretive | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| numerical | 13 | 46.2% [23.1%, 76.9%] | 0.405 | 92.3% | 41.7% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 15 | 60.0% [33.3%, 86.7%] | 0.476 | 93.3% | 57.1% |
| reference_media | 5 | 60.0% [20.0%, 100.0%] | 0.333 | 100.0% | 60.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 20 | 60.0% [40.0%, 80.0%] | 0.438 | 95.0% | 57.9% |

## Retrieval

20 claims searched (19 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 5.3% [0.0%, 15.8%] (n=19) |
| Reference link among ranked evidence | 5.3% [0.0%, 15.8%] (n=19) |
| Reference link among cited evidence | 5.3% [0.0%, 15.8%] (n=19) |
| Reference domain among candidates | 36.8% [15.8%, 57.9%] (n=19) |
| Reference domain among ranked evidence | 26.3% [10.5%, 47.4%] (n=19) |
| Reference domain among cited evidence | 21.1% [5.3%, 42.1%] (n=19) |
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
| Ranking seconds per claim | 25.59 [22.15, 28.93] (n=20) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 25.13 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 62, anchor 34, refutation 25 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 20 | 19 | 5.3% | 26.3% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 14 | 13 | 7.7% | 15.4% | 100.0% |
| es | 6 | 6 | 0.0% | 50.0% | 100.0% |

## Stage attribution

8 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=8) | By reference (n=7) |
|---|---|---|
| retrieval | 0 (0.0%) | 5 (71.4%) |
| ranking | 0 (0.0%) | 1 (14.3%) |
| reasoning | 8 (100.0%) | 1 (14.3%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact009, fact011, fact016, fact036, fact037, fact049, fact066, fact081).

By reference: retrieval (fact009, fact016, fact037, fact066, fact081); ranking (fact036); reasoning (fact011).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: cut by pre-rank funnel (rank 13 of 14, top 5 kept): 1

Without a reference link to judge by (1): fact049.

The two columns disagree on 6 of the 7 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact036 | reasoning | ranking |
| fact037 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |

## Journalist effort

Over 20 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 7 | 35.0% [15.0, 55.0] |
| Confidently wrong (definitive, not gold) | 8 | 40.0% [20.0, 60.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 20 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 20 | 3.4 | 4.8 | 9.7 | 1.5% |
| Evidence retrieval | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 20 | 2.6 | 4.7 | 5.2 | 1.2% |
| of which: the page fetches | 20 | 2.4 | 5.1 | 9.0 | 1.3% |
| Ranking | 20 | 25.1 | 35.6 | 39.1 | 11.0% |
| The model's verdict (with its wait for a permit) | 20 | 204.0 | 331.8 | 379.6 | 87.5% |
| of which: waiting for the model (another claim's call) | 20 | 71.1 | 170.8 | 211.6 | 37.4% |
| of which: the model's call itself | 20 | 109.5 | 167.5 | 243.2 | 50.1% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 20 | 226.7 | 354.2 | 420.9 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 95 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 46579 / 4835 |
| Tokens per claim asked (prompt / completion) | 2328.9 / 241.8 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 19.922 / 40.210 / 145.907 |
| Claim latency, median / p90 (s) | 226.721 / 354.170 |
| Completion tokens per second | 2.1 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`cc053417c0cb`, localhost:11434); candidate B: this run. Paired over the 20 claims both scored; 0 set apart on either side, 49 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 55.0% | 60.0% | +5.0 pts | [-10.0 pts, +20.0 pts] |
| macroF1 | 0.325 | 0.438 | +0.113 | [-0.002, +0.236] |
| coverage | 80.0% | 95.0% | +15.0 pts | [+0.0 pts, +30.0 pts] |
| selectiveAccuracy | 62.5% | 57.9% | -4.6 pts | [-24.3 pts, +14.4 pts] |
| kappa | -0.011 | 0.263 | +0.274 | [+0.014, +0.487] |

Only A right: 1; only B right: 2. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 20 claims both searched (49 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 19 | 5.3% | 5.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 19 | 36.8% | 36.8% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 19 | 26.3% | 26.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 19 | 15.8% | 21.1% | +5.3 pts [+0.0 pts, +15.8 pts] | 0 / 1 |
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
| Ranking seconds per claim | 20 | 18.17 | 25.59 | +7.42 [+3.13, +11.56] |  |

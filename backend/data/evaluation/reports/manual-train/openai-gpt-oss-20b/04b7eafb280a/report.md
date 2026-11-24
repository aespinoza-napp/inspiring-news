# manual-train · openai/gpt-oss-20b · replayed evidence

Run `04b7eafb280a` · provider `api.groq.com` · harness v1 · thresholds `426710d40887` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 20 run, 49 not run. Commits: `d8842946744c`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 20 | 15 |
| Accuracy | 45.0% [25.0%, 65.0%] | 46.7% [20.0%, 73.3%] |
| Macro-F1 (gold classes) | 0.325 [0.154, 0.472] | 0.481 [0.208, 0.732] |
| Coverage (not UNVERIFIED) | 45.0% [25.0%, 65.0%] | 33.3% [13.3%, 60.0%] |
| Selective accuracy | 66.7% [33.3%, 100.0%] | 80.0% [33.3%, 100.0%] |
| Cohen's kappa vs gold | 0.160 [-0.033, 0.409] | 0.184 [0.000, 0.483] |

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
| temporalLeak (cited source newer than the claim) | 5 | 12 | 3 | fact009, fact012, fact020, fact038, fact066 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 20 |  |

Ranked but uncited sources newer than the claim: 7 over 6 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 85.7% | 40.0% | 0.545 | 15 | 7 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 2 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 2 |
| UNVERIFIED | 27.3% | 100.0% | 0.429 | 3 | 11 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 6 | 0 | 0 | 1 | 8 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 0 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 14 | 35.7% [14.3%, 64.3%] | 0.335 | 35.7% | 80.0% |
| es | 6 | 66.7% [33.3%, 100.0%] | 0.600 | 66.7% | 50.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 8 | 37.5% [12.5%, 75.0%] | 0.273 | 50.0% | 75.0% |
| health | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 66.7% | 50.0% |
| science | 5 | 40.0% [0.0%, 80.0%] | 0.333 | 40.0% | 50.0% |
| society | 4 | 75.0% [25.0%, 100.0%] | 0.733 | 25.0% | 100.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 6 | 50.0% [16.7%, 83.3%] | 0.333 | 66.7% | 75.0% |
| interpretive | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 0.0% | n/a |
| numerical | 13 | 46.2% [23.1%, 69.2%] | 0.348 | 38.5% | 60.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 15 | 33.3% [13.3%, 60.0%] | 0.236 | 33.3% | 60.0% |
| reference_media | 5 | 80.0% [40.0%, 100.0%] | 0.667 | 80.0% | 75.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 20 | 45.0% [25.0%, 65.0%] | 0.325 | 45.0% | 66.7% |

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
| Ranked from rated domains | 9.0% [4.0%, 14.0%] (n=20) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=20) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=20) |
| Ranking seconds per claim | 8.60 [7.28, 10.02] (n=20) |

Medians: 16.00 candidates, 5.00 ranked, 0.00 s retrieval, 7.33 s ranking; 3.00 queries per claim.

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
| Confidently wrong (definitive, not gold) | 3 | 15.0% [0.0, 30.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 20 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 20 | 0.1 | 0.2 | 0.2 | 0.8% |
| Evidence retrieval | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 20 | 2.6 | 4.7 | 5.2 | 20.5% |
| of which: the page fetches | 20 | 2.4 | 5.1 | 9.0 | 21.6% |
| Ranking | 20 | 7.3 | 12.9 | 16.0 | 61.8% |
| The model's verdict (with its wait for a permit) | 20 | 2.7 | 10.3 | 12.8 | 37.4% |
| of which: waiting for the model (another claim's call) | 20 | 0.5 | 8.0 | 8.0 | 21.2% |
| of which: the model's call itself | 20 | 1.9 | 3.1 | 7.7 | 16.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 20 | 14.7 | 17.5 | 19.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 119 (24) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 47578 / 8995 |
| Tokens per claim asked (prompt / completion) | 2378.9 / 449.8 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 0.412 / 0.611 / 5.567 |
| Claim latency, median / p90 (s) | 14.715 / 17.533 |
| Completion tokens per second | 209.2 |
| Cost | 0.0063 USD (0.0313 per 100 claims; price as of 2026-10-29) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`e9c6c7df528d`, localhost:11434); candidate B: this run. Paired over the 20 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 50.0% | 45.0% | -5.0 pts | [-30.0 pts, +20.0 pts] |
| macroF1 | 0.222 | 0.325 | +0.102 | [-0.071, +0.257] |
| coverage | 85.0% | 45.0% | -40.0 pts | [-60.0 pts, -20.0 pts] |
| selectiveAccuracy | 58.8% | 66.7% | +7.8 pts | [-22.2 pts, +38.9 pts] |
| kappa | -0.205 | 0.160 | +0.365 | [+0.079, +0.619] |

Only A right: 4; only B right: 3. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 20 claims both searched (0 only in the baseline, 0 only in the candidate).

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
| Ranked from rated domains | 20 | 9.0% | 9.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 20 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 20 | 0.00 | 0.00 | -0.00 [-0.00, -0.00] |  |
| Ranking seconds per claim | 20 | 8.85 | 8.60 | -0.25 [-1.32, +0.91] |  |

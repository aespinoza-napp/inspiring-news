# manual-train · llama3.2:3b

Run `7bcd048954e5` · provider `host.docker.internal:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (12 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 54 |
| Accuracy | 42.0% [30.4%, 53.6%] | 38.9% [25.9%, 51.9%] |
| Macro-F1 (gold classes) | 0.208 [0.149, 0.264] | 0.195 [0.131, 0.258] |
| Coverage (not UNVERIFIED) | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] |
| Selective accuracy | 42.0% [30.4%, 53.6%] | 38.9% [25.9%, 51.9%] |
| Cohen's kappa vs gold | -0.022 [-0.195, 0.145] | -0.072 [-0.271, 0.123] |

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
| temporalLeak (cited source newer than the claim) | 15 | 29 | 25 | fact020, fact036, fact062, fact065, fact085, fact089, fact099, fact100, fact101, fact124, fact133, fact142, fact146, fact162, fact174 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 15 over 14 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 65.7% | 51.1% | 0.575 | 45 | 35 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 2 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 18.8% | 40.0% | 0.255 | 15 | 32 |
| UNVERIFIED | n/a | 0.0% | 0.000 | 6 | 0 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 23 | 2 | 0 | 20 | 0 |
| PARTIALLY_TRUE | 2 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 9 | 0 | 0 | 6 | 0 |
| UNVERIFIED | 1 | 0 | 0 | 5 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 43.8% [29.2%, 58.3%] | 0.219 | 100.0% | 43.8% |
| es | 21 | 38.1% [19.0%, 57.1%] | 0.182 | 100.0% | 38.1% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 70.0% [40.0%, 100.0%] | 0.600 | 100.0% | 70.0% |
| environment | 16 | 43.8% [18.8%, 68.8%] | 0.213 | 100.0% | 43.8% |
| health | 15 | 40.0% [13.3%, 66.7%] | 0.242 | 100.0% | 40.0% |
| science | 17 | 47.1% [23.5%, 70.6%] | 0.254 | 100.0% | 47.1% |
| society | 11 | 9.1% [0.0%, 27.3%] | 0.067 | 100.0% | 9.1% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 45.9% [29.7%, 62.2%] | 0.263 | 100.0% | 45.9% |
| interpretive | 3 | 66.7% [0.0%, 100.0%] | 0.800 | 100.0% | 66.7% |
| numerical | 29 | 34.5% [17.2%, 51.7%] | 0.200 | 100.0% | 34.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 44.2% [30.2%, 58.1%] | 0.216 | 100.0% | 44.2% |
| reference_media | 25 | 36.0% [16.0%, 56.0%] | 0.185 | 100.0% | 36.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 40.0% [13.3%, 66.7%] | 0.571 | 100.0% | 40.0% |
| natural | 54 | 42.6% [29.6%, 55.6%] | 0.216 | 100.0% | 42.6% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 14.9% [7.5%, 23.9%] (n=67) |
| Reference link among ranked evidence | 11.9% [4.5%, 19.4%] (n=67) |
| Reference link among cited evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference domain among candidates | 35.8% [25.4%, 47.8%] (n=67) |
| Reference domain among ranked evidence | 28.4% [17.9%, 38.8%] (n=67) |
| Reference domain among cited evidence | 22.4% [13.4%, 32.8%] (n=67) |
| Link MRR (ranked) | 10.8% [4.5%, 18.5%] (n=67) |
| Domain MRR (ranked) | 17.1% [9.6%, 25.4%] (n=67) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=69) |
| Candidates per claim | 18.48 [17.59, 19.38] (n=69) |
| Ranked sources per claim | 4.83 [4.71, 4.93] (n=69) |
| Share cut at ranking (gate, cap) | 3.5% [1.5%, 5.8%] (n=69) |
| Distinct domains among ranked | 4.83 [4.71, 4.93] (n=69) |
| Ranked from rated domains | 7.8% [5.2%, 10.7%] (n=69) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=69) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 11.16 [9.88, 12.68] (n=69) |
| Ranking seconds per claim | 5.18 [4.83, 5.55] (n=69) |

Medians: 18.00 candidates, 5.00 ranked, 9.04 s retrieval, 5.08 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 216, anchor 127, refutation 79 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 11.9% | 28.4% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 15.2% | 26.1% | 100.0% |
| es | 21 | 21 | 4.8% | 33.3% | 100.0% |

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.2 | 1.0 | 0.2% |
| Evidence retrieval | 69 | 9.0 | 19.9 | 32.1 | 15.3% |
| Ranking | 69 | 5.1 | 6.9 | 9.7 | 7.1% |
| The model's verdict (with its wait for a permit) | 69 | 55.6 | 77.8 | 88.3 | 77.4% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 72.7 | 94.8 | 103.8 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 69 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 134065 / 12970 |
| Tokens per claim asked (prompt / completion) | 1943.0 / 188.0 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 33.964 / 48.880 / 64.180 |
| Claim latency, median / p90 (s) | 72.707 / 94.808 |
| Completion tokens per second | 5.2 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`ba36c5721e58`, host.docker.internal:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 44.9% | 42.0% | -2.9 pts | [-10.1 pts, +4.3 pts] |
| macroF1 | 0.233 | 0.208 | -0.025 | [-0.064, +0.009] |
| coverage | 97.1% | 100.0% | +2.9 pts | [+0.0 pts, +7.2 pts] |
| selectiveAccuracy | 46.3% | 42.0% | -4.2 pts | [-11.0 pts, +2.2 pts] |
| kappa | 0.056 | -0.022 | -0.078 | [-0.199, +0.022] |

Only A right: 4; only B right: 2. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 11.9% | 14.9% | +3.0 pts [+0.0 pts, +7.5 pts] | 0 / 2 |
| Reference link among ranked evidence | 67 | 9.0% | 11.9% | +3.0 pts [+0.0 pts, +7.5 pts] | 0 / 2 |
| Reference link among cited evidence | 67 | 7.5% | 10.4% | +3.0 pts [+0.0 pts, +7.5 pts] | 0 / 2 |
| Reference domain among candidates | 67 | 32.8% | 35.8% | +3.0 pts [+0.0 pts, +7.5 pts] | 0 / 2 |
| Reference domain among ranked evidence | 67 | 25.4% | 28.4% | +3.0 pts [+0.0 pts, +7.5 pts] | 0 / 2 |
| Reference domain among cited evidence | 67 | 19.4% | 22.4% | +3.0 pts [-3.0 pts, +9.0 pts] | 1 / 3 |
| Link MRR (ranked) | 67 | 7.0% | 10.8% | +3.7 pts [+0.0 pts, +9.0 pts] | 0 / 3 |
| Domain MRR (ranked) | 67 | 16.1% | 17.1% | +1.0 pts [-3.2 pts, +5.5 pts] | 2 / 3 |
| Claims with any ranked evidence | 69 | 98.6% | 100.0% | +1.5 pts [+0.0 pts, +4.3 pts] |  |
| Candidates per claim | 69 | 18.49 | 18.48 | -0.01 [-0.91, +0.86] |  |
| Ranked sources per claim | 69 | 4.74 | 4.83 | +0.09 [-0.04, +0.28] |  |
| Share cut at ranking (gate, cap) | 69 | 4.8% | 3.5% | -1.4 pts [-4.9 pts, +1.0 pts] |  |
| Distinct domains among ranked | 69 | 4.74 | 4.83 | +0.09 [-0.04, +0.28] |  |
| Ranked from rated domains | 68 | 7.1% | 7.9% | +0.9 pts [-0.6 pts, +2.4 pts] |  |
| Ranked from the internal corpus | 68 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 14.35 | 11.16 | -3.19 [-4.65, -1.67] |  |
| Ranking seconds per claim | 69 | 6.40 | 5.18 | -1.21 [-2.08, -0.44] |  |

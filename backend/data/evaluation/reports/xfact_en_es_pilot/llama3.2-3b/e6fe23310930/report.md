# xfact_en_es_pilot · llama3.2:3b

Run `e6fe23310930` · provider `host.docker.internal:11434` · harness v1 · thresholds `4fa9fa08c9d3` · corpus `snapshot` (5 points)

Dataset sha256 `2618068af706`, 64 rows; 64 run, 0 not run. Commits: `bed7a57e82a8`, `d26ba0a04760`, `fd3d547a3acb`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 64 | 43 |
| Accuracy | 29.7% [18.8%, 40.6%] | 23.3% [11.6%, 37.2%] |
| Macro-F1 (gold classes) | 0.168 [0.104, 0.234] | 0.153 [0.071, 0.238] |
| Coverage (not UNVERIFIED) | 95.3% [89.1%, 100.0%] | 93.0% [83.7%, 100.0%] |
| Selective accuracy | 31.1% [20.0%, 43.3%] | 25.0% [12.5%, 39.0%] |
| Cohen's kappa vs gold | 0.070 [-0.028, 0.177] | 0.046 [-0.059, 0.166] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 64 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 16 | 4 | 44 | xf-16a51393f9f8, xf-253c58784d68, xf-653d580b47ae, xf-708ac43fcff5, xf-777c714dd1b5, xf-7c19682d2758, xf-7cc2b9765879, xf-7d05ad57ba03, xf-8f6c11a638b3, xf-90c4fbb5248f, xf-9bf6c9a73d13, xf-ae276f7fabc9, xf-b57f3f4f21a7, xf-c41e15e05b10, xf-c93b20095e0e, xf-f4007ef26c2c |
| verdictLeak (a ranked source is the fact-checker's own site) | 9 | 55 | 0 | xf-3005b1d6af1b, xf-7d05ad57ba03, xf-7d093c407264, xf-996b4a0c6ab5, xf-9bf6c9a73d13, xf-b374ee0b0585, xf-c41e15e05b10, xf-d28faa9b7056, xf-f4007ef26c2c |

Ranked but uncited sources newer than the claim: 38 over 19 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 26.7% | 25.0% | 0.258 | 16 | 15 |
| PARTIALLY_TRUE | 33.3% | 6.2% | 0.105 | 16 | 3 |
| MISLEADING | n/a | 0.0% | 0.000 | 8 | 0 |
| FALSE | 32.6% | 87.5% | 0.475 | 16 | 43 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 8 | 3 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 4 | 0 | 0 | 12 | 0 |
| PARTIALLY_TRUE | 3 | 1 | 0 | 10 | 2 |
| MISLEADING | 4 | 0 | 0 | 3 | 1 |
| FALSE | 2 | 0 | 0 | 14 | 0 |
| UNVERIFIED | 2 | 2 | 0 | 4 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 24 | 41.7% [20.8%, 62.5%] | 0.358 | 100.0% | 41.7% |
| es | 40 | 22.5% [10.0%, 35.0%] | 0.130 | 92.5% | 24.3% |

## By site

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| chequeado.com | 40 | 22.5% [10.0%, 35.0%] | 0.130 | 92.5% | 24.3% |
| politifact.com | 24 | 41.7% [20.8%, 62.5%] | 0.358 | 100.0% | 41.7% |

## Retrieval

64 claims searched (38 with reference links), 0 with search unavailable and 0 errors left out; 73 reference link(s) on the fact-checker's own site removed from the reference set; 24 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 0.0% [0.0%, 0.0%] (n=38) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=38) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=38) |
| Reference domain among candidates | 10.5% [2.6%, 21.1%] (n=38) |
| Reference domain among ranked evidence | 5.3% [0.0%, 13.2%] (n=38) |
| Reference domain among cited evidence | 2.6% [0.0%, 7.9%] (n=38) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=38) |
| Domain MRR (ranked) | 1.4% [0.0%, 3.7%] (n=38) |
| Claims with any ranked evidence | 98.4% [95.3%, 100.0%] (n=64) |
| Candidates per claim | 17.86 [16.67, 19.00] (n=64) |
| Ranked sources per claim | 4.67 [4.45, 4.84] (n=64) |
| Share cut at ranking (gate, cap) | 6.6% [3.1%, 10.9%] (n=64) |
| Distinct domains among ranked | 4.67 [4.45, 4.84] (n=64) |
| Ranked from rated domains | 8.9% [5.3%, 12.7%] (n=63) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=63) |
| Fact-checker's own page ranked (x-fact) | 14.1% [6.2%, 23.4%] (n=64) |
| Retrieval seconds per claim | 18.61 [15.54, 22.61] (n=64) |
| Ranking seconds per claim | 11.26 [9.54, 13.15] (n=64) |

Medians: 17.00 candidates, 5.00 ranked, 14.75 s retrieval, 8.56 s ranking; 2.91 queries per claim.

Ranked sources found by: proposition 162, anchor 122, refutation 69 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| xfact | 64 | 38 | 0.0% | 5.3% | 98.4% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 24 | 0 | n/a | n/a | 100.0% |
| es | 40 | 38 | 0.0% | 5.3% | 97.5% |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 63 (0) |
| Claims the model was not asked about | 1 |
| Prompt / completion tokens | 134890 / 11278 |
| Tokens per claim asked (prompt / completion) | 2141.1 / 179.0 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 5.623 / 9.509 / 14.526 |
| Claim latency, median / p90 (s) | 36.535 / 59.868 |
| Completion tokens per second | 28.3 |
| Cost | 0.0000 USD (0.0000 per 100 claims; price as of 2026-10-02) |

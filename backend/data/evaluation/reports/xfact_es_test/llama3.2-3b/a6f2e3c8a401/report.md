# xfact_es_test · llama3.2:3b

Run `a6f2e3c8a401` · provider `host.docker.internal:11434` · harness v1 · thresholds `4fa9fa08c9d3` · corpus `snapshot` (5 points)

Dataset sha256 `9253cff52feb`, 165 rows; 165 run, 0 not run. Commits: `663e0e4ed72f`, `6a63e30f7339`, `e31cdf6ebfa0`, `unknown`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 165 | 165 |
| Accuracy | 19.4% [13.3%, 25.5%] | 19.4% [13.3%, 25.5%] |
| Macro-F1 (gold classes) | 0.111 [0.079, 0.142] | 0.111 [0.079, 0.142] |
| Coverage (not UNVERIFIED) | 98.2% [95.8%, 100.0%] | 98.2% [95.8%, 100.0%] |
| Selective accuracy | 19.8% [13.8%, 25.9%] | 19.8% [13.8%, 25.9%] |
| Cohen's kappa vs gold | -0.002 [-0.060, 0.055] | -0.002 [-0.060, 0.055] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 165 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 0 | 0 | 165 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 165 | 0 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 30.2% | 32.0% | 0.311 | 50 | 53 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 22 | 2 |
| MISLEADING | n/a | 0.0% | 0.000 | 48 | 0 |
| FALSE | 15.0% | 66.7% | 0.244 | 24 | 107 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 21 | 3 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 16 | 0 | 0 | 33 | 1 |
| PARTIALLY_TRUE | 7 | 0 | 0 | 15 | 0 |
| MISLEADING | 13 | 2 | 0 | 32 | 1 |
| FALSE | 7 | 0 | 0 | 16 | 1 |
| UNVERIFIED | 10 | 0 | 0 | 11 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| es | 165 | 19.4% [13.3%, 25.5%] | 0.111 | 98.2% | 19.8% |

## By site

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| chequeado.com | 165 | 19.4% [13.3%, 25.5%] | 0.111 | 98.2% | 19.8% |

## Retrieval

165 claims searched (146 with reference links), 0 with search unavailable and 0 errors left out; 289 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 7.5% [3.4%, 12.3%] (n=146) |
| Reference link among ranked evidence | 6.9% [2.7%, 11.0%] (n=146) |
| Reference link among cited evidence | 4.8% [1.4%, 8.2%] (n=146) |
| Reference domain among candidates | 17.8% [11.6%, 24.0%] (n=146) |
| Reference domain among ranked evidence | 13.0% [7.5%, 18.5%] (n=146) |
| Reference domain among cited evidence | 7.5% [3.4%, 12.3%] (n=146) |
| Link MRR (ranked) | 4.5% [1.7%, 8.0%] (n=146) |
| Domain MRR (ranked) | 8.0% [4.3%, 12.2%] (n=146) |
| Claims with any ranked evidence | 99.4% [98.2%, 100.0%] (n=165) |
| Candidates per claim | 17.91 [17.25, 18.57] (n=165) |
| Ranked sources per claim | 4.76 [4.65, 4.86] (n=165) |
| Share cut at ranking (gate, cap) | 4.7% [2.8%, 7.0%] (n=165) |
| Distinct domains among ranked | 4.76 [4.65, 4.86] (n=165) |
| Ranked from rated domains | 12.8% [10.6%, 15.1%] (n=164) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=164) |
| Fact-checker's own page ranked (x-fact) | 0.0% [0.0%, 0.0%] (n=165) |
| Retrieval seconds per claim | 12.63 [11.53, 13.90] (n=165) |
| Ranking seconds per claim | 9.01 [8.33, 9.75] (n=165) |

Medians: 16.00 candidates, 5.00 ranked, 10.45 s retrieval, 7.49 s ranking; 2.80 queries per claim.

Ranked sources found by: proposition 424, anchor 321, refutation 173 (a source two queries found counts for both).

References found, then cut:

- evidence_ranking: on-topic but does not address the claim (pertinence 0.17 < 0.25): 1
- evidence_retrieval: same domain as a higher-ranked source (unodc.org): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| xfact | 165 | 146 | 6.9% | 13.0% | 99.4% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| es | 165 | 146 | 6.9% | 13.0% | 99.4% |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 164 (0) |
| Claims the model was not asked about | 1 |
| Prompt / completion tokens | 392993 / 31015 |
| Tokens per claim asked (prompt / completion) | 2396.3 / 189.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 5.561 / 9.181 / 15.920 |
| Claim latency, median / p90 (s) | 28.436 / 42.757 |
| Completion tokens per second | 31.0 |
| Cost | 0.0000 USD (0.0000 per 100 claims; price as of 2026-10-02) |

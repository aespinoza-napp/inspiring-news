# manual-train · llama3.2:3b · contest-2026-10-22

Run `c85d8d088ec4` · provider `localhost:11434` · harness v1 · thresholds `22fd994eb2c5` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 10 run, 59 not run. Commits: `67a65c14a325`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 10 | 10 |
| Accuracy | 20.0% [0.0%, 50.0%] | 20.0% [0.0%, 50.0%] |
| Macro-F1 (gold classes) | 0.148 [0.000, 0.267] | 0.148 [0.000, 0.267] |
| Coverage (not UNVERIFIED) | 80.0% [50.0%, 100.0%] | 80.0% [50.0%, 100.0%] |
| Selective accuracy | 25.0% [0.0%, 57.1%] | 25.0% [0.0%, 57.1%] |
| Cohen's kappa vs gold | 0.024 [-0.111, 0.176] | 0.024 [-0.111, 0.176] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 10 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 0 | 0 | 10 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 10 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 100.0% | 28.6% | 0.444 | 7 | 2 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 1 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 6 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 2 | 2 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 2 | 0 | 0 | 3 | 2 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 2 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 6 | 33.3% [0.0%, 66.7%] | 0.500 | 83.3% | 40.0% |
| es | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 75.0% | 0.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 50.0% | 0.0% |
| health | 2 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| science | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 50.0% | 0.0% |
| society | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 2 | 50.0% [0.0%, 100.0%] | 0.667 | 100.0% | 50.0% |
| numerical | 8 | 12.5% [0.0%, 37.5%] | 0.111 | 75.0% | 16.7% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 7 | 28.6% [0.0%, 57.1%] | 0.286 | 85.7% | 33.3% |
| reference_media | 3 | 0.0% [0.0%, 0.0%] | 0.000 | 66.7% | 0.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 10 | 20.0% [0.0%, 50.0%] | 0.148 | 80.0% | 25.0% |

## Retrieval

10 claims searched (10 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 0.0% [0.0%, 0.0%] (n=10) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference domain among candidates | 30.0% [0.0%, 60.0%] (n=10) |
| Reference domain among ranked evidence | 10.0% [0.0%, 30.0%] (n=10) |
| Reference domain among cited evidence | 10.0% [0.0%, 30.0%] (n=10) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=10) |
| Domain MRR (ranked) | 10.0% [0.0%, 30.0%] (n=10) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=10) |
| Candidates per claim | 13.60 [12.40, 14.80] (n=10) |
| Ranked sources per claim | 3.00 [3.00, 3.00] (n=10) |
| Share cut at ranking (gate, cap) | 0.0% [0.0%, 0.0%] (n=10) |
| Distinct domains among ranked | 3.00 [3.00, 3.00] (n=10) |
| Ranked from rated domains | 16.7% [0.0%, 33.3%] (n=10) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=10) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 2.37 [1.76, 2.96] (n=10) |
| Ranking seconds per claim | 0.62 [0.50, 0.75] (n=10) |

Medians: 13.00 candidates, 3.00 ranked, 2.56 s retrieval, 0.58 s ranking; 2.00 queries per claim.

Ranked sources found by: proposition 25, anchor 10 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 10 | 10 | 0.0% | 10.0% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 6 | 6 | 0.0% | 0.0% | 100.0% |
| es | 4 | 4 | 0.0% | 25.0% | 100.0% |

## Stage attribution

8 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=8) | By reference (n=8) |
|---|---|---|
| retrieval | 0 (0.0%) | 6 (75.0%) |
| ranking | 0 (0.0%) | 1 (12.5%) |
| reasoning | 8 (100.0%) | 1 (12.5%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact008, fact009, fact010, fact011, fact015, fact016, fact020, fact021).

By reference: retrieval (fact008, fact009, fact015, fact016, fact020, fact021); ranking (fact010); reasoning (fact011).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: cut by pre-rank funnel (rank 4 of 8, top 3 kept): 1

The two columns disagree on 7 of the 8 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact010 | reasoning | ranking |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact021 | reasoning | retrieval |

## Journalist effort

Over 10 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 2 | 20.0% [0.0, 50.0] |
| Confidently wrong (definitive, not gold) | 6 | 60.0% [30.0, 90.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 10 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 10 | 2.1 | 2.6 | 4.4 | 12.2% |
| Evidence retrieval | 10 | 2.6 | 3.4 | 3.5 | 16.1% |
| of which: the web search, every query | 10 | 1.1 | 1.2 | 1.8 | 7.8% |
| of which: the page fetches | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 10 | 0.6 | 0.9 | 1.1 | 4.2% |
| The model's verdict (with its wait for a permit) | 10 | 9.8 | 13.2 | 15.0 | 67.5% |
| of which: waiting for the model (another claim's call) | 10 | 2.0 | 5.8 | 8.9 | 19.3% |
| of which: the model's call itself | 10 | 6.9 | 7.9 | 9.9 | 48.2% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 10 | 14.2 | 16.2 | 21.7 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 10 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 5346 / 614 |
| Tokens per claim asked (prompt / completion) | 534.6 / 61.4 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 6.946 / 7.911 / 9.918 |
| Claim latency, median / p90 (s) | 14.237 / 16.197 |
| Completion tokens per second | 8.6 |
| Cost | n/a (no price given, or tokens unknown) |

# manual-train · llama3.2:3b · contest-2026-10-22

Run `7f1480f90bdc` · provider `localhost:11434` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 10 run, 59 not run. Commits: `67a65c14a325`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 10 | 8 |
| Accuracy | 30.0% [0.0%, 60.0%] | 25.0% [0.0%, 62.5%] |
| Macro-F1 (gold classes) | 0.200 [0.000, 0.296] | 0.190 [0.000, 0.308] |
| Coverage (not UNVERIFIED) | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] |
| Selective accuracy | 30.0% [0.0%, 60.0%] | 25.0% [0.0%, 62.5%] |
| Cohen's kappa vs gold | 0.114 [0.000, 0.250] | 0.111 [0.000, 0.273] |

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
| temporalLeak (cited source newer than the claim) | 2 | 4 | 4 | fact020, fact036 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 10 |  |

Ranked but uncited sources newer than the claim: 3 over 2 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 100.0% | 42.9% | 0.600 | 7 | 3 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 1 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 7 |
| UNVERIFIED | n/a | 0.0% | 0.000 | 2 | 0 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 3 | 0 | 0 | 4 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 2 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 6 | 50.0% [16.7%, 83.3%] | 0.667 | 100.0% | 50.0% |
| es | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 2 | 50.0% [0.0%, 100.0%] | 0.667 | 100.0% | 50.0% |
| health | 2 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| science | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| society | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 2 | 50.0% [0.0%, 100.0%] | 0.667 | 100.0% | 50.0% |
| numerical | 8 | 25.0% [0.0%, 62.5%] | 0.190 | 100.0% | 25.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 7 | 42.9% [14.3%, 85.7%] | 0.375 | 100.0% | 42.9% |
| reference_media | 3 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 10 | 30.0% [0.0%, 60.0%] | 0.200 | 100.0% | 30.0% |

## Retrieval

10 claims searched (10 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 0.0% [0.0%, 0.0%] (n=10) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference domain among candidates | 30.0% [0.0%, 60.0%] (n=10) |
| Reference domain among ranked evidence | 20.0% [0.0%, 50.0%] (n=10) |
| Reference domain among cited evidence | 10.0% [0.0%, 30.0%] (n=10) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=10) |
| Domain MRR (ranked) | 15.0% [0.0%, 35.0%] (n=10) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=10) |
| Candidates per claim | 18.10 [15.90, 20.40] (n=10) |
| Ranked sources per claim | 4.90 [4.70, 5.00] (n=10) |
| Share cut at ranking (gate, cap) | 2.0% [0.0%, 6.0%] (n=10) |
| Distinct domains among ranked | 4.90 [4.70, 5.00] (n=10) |
| Ranked from rated domains | 14.0% [2.0%, 28.0%] (n=10) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=10) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 11.20 [9.84, 13.06] (n=10) |
| Ranking seconds per claim | 5.95 [5.22, 6.56] (n=10) |

Medians: 17.00 candidates, 5.00 ranked, 10.27 s retrieval, 6.00 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 35, refutation 16, anchor 16 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 10 | 10 | 0.0% | 20.0% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 6 | 6 | 0.0% | 0.0% | 100.0% |
| es | 4 | 4 | 0.0% | 50.0% | 100.0% |

## Stage attribution

7 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=7) | By reference (n=7) |
|---|---|---|
| retrieval | 0 (0.0%) | 5 (71.4%) |
| ranking | 0 (0.0%) | 0 (0.0%) |
| reasoning | 7 (100.0%) | 2 (28.6%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact008, fact009, fact010, fact011, fact015, fact016, fact020).

By reference: retrieval (fact008, fact009, fact015, fact016, fact020); reasoning (fact010, fact011).

The two columns disagree on 5 of the 7 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |

## Journalist effort

Over 10 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 2 | 20.0% [0.0, 50.0] |
| Confidently wrong (definitive, not gold) | 7 | 70.0% [40.0, 100.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 10 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 10 | 2.2 | 3.0 | 6.8 | 4.8% |
| Evidence retrieval | 10 | 10.3 | 13.0 | 18.2 | 19.7% |
| of which: the web search, every query | 10 | 2.1 | 2.9 | 3.0 | 4.0% |
| of which: the page fetches | 10 | 2.1 | 3.6 | 9.7 | 5.1% |
| Ranking | 10 | 6.0 | 7.2 | 7.4 | 10.5% |
| The model's verdict (with its wait for a permit) | 10 | 38.9 | 45.4 | 50.4 | 65.1% |
| of which: waiting for the model (another claim's call) | 10 | 8.8 | 13.5 | 16.0 | 14.7% |
| of which: the model's call itself | 10 | 28.2 | 35.0 | 41.2 | 50.3% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 10 | 57.2 | 69.2 | 70.9 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 10 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 14103 / 1631 |
| Tokens per claim asked (prompt / completion) | 1410.3 / 163.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 28.249 / 34.969 / 41.200 |
| Claim latency, median / p90 (s) | 57.160 / 69.211 |
| Completion tokens per second | 5.7 |
| Cost | n/a (no price given, or tokens unknown) |

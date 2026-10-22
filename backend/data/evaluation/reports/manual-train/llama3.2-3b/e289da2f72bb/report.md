# manual-train · llama3.2:3b · contest-2026-10-22

Run `e289da2f72bb` · provider `localhost:11434` · harness v1 · thresholds `f8c1f268b5d9` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 10 run, 59 not run. Commits: `67a65c14a325`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 10 | 7 |
| Accuracy | 20.0% [0.0%, 50.0%] | 14.3% [0.0%, 42.9%] |
| Macro-F1 (gold classes) | 0.148 [0.000, 0.267] | 0.133 [0.000, 0.286] |
| Coverage (not UNVERIFIED) | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] |
| Selective accuracy | 20.0% [0.0%, 50.0%] | 14.3% [0.0%, 42.9%] |
| Cohen's kappa vs gold | 0.070 [0.000, 0.205] | 0.067 [0.000, 0.222] |

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
| temporalLeak (cited source newer than the claim) | 3 | 1 | 6 | fact020, fact021, fact036 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 10 |  |

Ranked but uncited sources newer than the claim: 3 over 2 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 100.0% | 28.6% | 0.444 | 7 | 2 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 1 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 8 |
| UNVERIFIED | n/a | 0.0% | 0.000 | 2 | 0 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 2 | 0 | 0 | 5 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 2 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 6 | 33.3% [0.0%, 66.7%] | 0.500 | 100.0% | 33.3% |
| es | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| health | 2 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| science | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| society | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 2 | 50.0% [0.0%, 100.0%] | 0.667 | 100.0% | 50.0% |
| numerical | 8 | 12.5% [0.0%, 37.5%] | 0.111 | 100.0% | 12.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 7 | 28.6% [0.0%, 57.1%] | 0.286 | 100.0% | 28.6% |
| reference_media | 3 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 10 | 20.0% [0.0%, 50.0%] | 0.148 | 100.0% | 20.0% |

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
| Candidates per claim | 18.40 [16.20, 20.80] (n=10) |
| Ranked sources per claim | 5.00 [5.00, 5.00] (n=10) |
| Share cut at ranking (gate, cap) | 0.0% [0.0%, 0.0%] (n=10) |
| Distinct domains among ranked | 5.00 [5.00, 5.00] (n=10) |
| Ranked from rated domains | 16.0% [2.0%, 32.0%] (n=10) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=10) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 9.45 [8.57, 10.30] (n=10) |
| Ranking seconds per claim | 6.25 [5.72, 6.93] (n=10) |

Medians: 18.00 candidates, 5.00 ranked, 9.48 s retrieval, 6.27 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 35, refutation 15, anchor 13 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 10 | 10 | 0.0% | 20.0% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 6 | 6 | 0.0% | 0.0% | 100.0% |
| es | 4 | 4 | 0.0% | 50.0% | 100.0% |

## Stage attribution

8 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=8) | By reference (n=8) |
|---|---|---|
| retrieval | 0 (0.0%) | 6 (75.0%) |
| ranking | 0 (0.0%) | 0 (0.0%) |
| reasoning | 8 (100.0%) | 2 (25.0%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact008, fact009, fact010, fact011, fact015, fact016, fact020, fact021).

By reference: retrieval (fact008, fact009, fact015, fact016, fact020, fact021); reasoning (fact010, fact011).

The two columns disagree on 6 of the 8 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact021 | reasoning | retrieval |

## Journalist effort

Over 10 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 1 | 10.0% [0.0, 30.0] |
| Confidently wrong (definitive, not gold) | 8 | 80.0% [50.0, 100.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 10 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 10 | 2.3 | 4.8 | 8.3 | 8.1% |
| Evidence retrieval | 10 | 9.5 | 10.9 | 11.5 | 23.4% |
| of which: the web search, every query | 10 | 2.0 | 2.2 | 2.6 | 5.1% |
| of which: the page fetches | 10 | 1.6 | 3.0 | 6.4 | 5.6% |
| Ranking | 10 | 6.3 | 6.8 | 8.8 | 15.4% |
| The model's verdict (with its wait for a permit) | 10 | 20.1 | 27.4 | 37.2 | 53.1% |
| of which: waiting for the model (another claim's call) | 10 | 1.8 | 4.8 | 15.5 | 7.3% |
| of which: the model's call itself | 10 | 19.4 | 21.9 | 22.7 | 45.8% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 10 | 39.3 | 45.8 | 58.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 10 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 11272 / 709 |
| Tokens per claim asked (prompt / completion) | 1127.2 / 70.9 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 19.373 / 21.924 / 22.699 |
| Claim latency, median / p90 (s) | 39.314 / 45.769 |
| Completion tokens per second | 3.8 |
| Cost | n/a (no price given, or tokens unknown) |

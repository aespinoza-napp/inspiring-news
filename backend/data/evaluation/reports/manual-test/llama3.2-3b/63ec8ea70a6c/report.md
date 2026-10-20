# manual-test · llama3.2:3b · the annotator's evidence (oracle)

Run `63ec8ea70a6c` · provider `localhost:11434` · harness v1 · thresholds `e1bae39fd2a3` · corpus `snapshot` (0 points)

Dataset sha256 `1ea9a8b72ec3`, 70 rows; 70 run, 0 not run. Commits: `0f70c68f1006`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 70 | 70 |
| Accuracy | 54.3% [42.9%, 65.7%] | 54.3% [42.9%, 65.7%] |
| Macro-F1 (gold classes) | 0.306 [0.210, 0.387] | 0.306 [0.210, 0.387] |
| Coverage (not UNVERIFIED) | 85.7% [77.1%, 92.9%] | 85.7% [77.1%, 92.9%] |
| Selective accuracy | 58.3% [45.5%, 70.5%] | 58.3% [45.5%, 70.5%] |
| Cohen's kappa vs gold | 0.259 [0.093, 0.421] | 0.259 [0.093, 0.421] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 70 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 0 | 69 | 1 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 70 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 83.9% | 56.5% | 0.675 | 46 | 31 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 4 | 2 |
| MISLEADING | n/a | 0.0% | 0.000 | 1 | 0 |
| FALSE | 33.3% | 60.0% | 0.429 | 15 | 27 |
| UNVERIFIED | 30.0% | 75.0% | 0.429 | 4 | 10 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 26 | 1 | 0 | 15 | 4 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 1 |
| MISLEADING | 1 | 0 | 0 | 0 | 0 |
| FALSE | 3 | 1 | 0 | 9 | 2 |
| UNVERIFIED | 0 | 0 | 0 | 1 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 61.7% [48.9%, 74.5%] | 0.436 | 83.0% | 66.7% |
| es | 23 | 39.1% [21.7%, 60.9%] | 0.206 | 91.3% | 42.9% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 11 | 54.5% [27.3%, 81.8%] | 0.382 | 100.0% | 54.5% |
| environment | 18 | 66.7% [44.4%, 88.9%] | 0.502 | 83.3% | 66.7% |
| health | 16 | 62.5% [37.5%, 87.5%] | 0.278 | 87.5% | 71.4% |
| science | 16 | 50.0% [25.0%, 75.0%] | 0.414 | 87.5% | 50.0% |
| society | 9 | 22.2% [0.0%, 55.6%] | 0.125 | 66.7% | 33.3% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 44 | 50.0% [36.4%, 65.9%] | 0.321 | 88.6% | 53.8% |
| interpretive | 2 | 100.0% [100.0%, 100.0%] | 1.000 | 50.0% | 100.0% |
| numerical | 24 | 58.3% [37.5%, 79.2%] | 0.407 | 83.3% | 65.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 3 | 0.0% [0.0%, 0.0%] | 0.000 | 33.3% | 0.0% |
| primary | 37 | 48.6% [32.4%, 64.9%] | 0.274 | 89.2% | 51.5% |
| reference_media | 30 | 66.7% [50.0%, 83.3%] | 0.503 | 86.7% | 69.2% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 60.0% [33.3%, 86.7%] | 0.750 | 86.7% | 69.2% |
| natural | 55 | 52.7% [40.0%, 65.5%] | 0.301 | 85.5% | 55.3% |

## Evidence

No search: each claim was judged on the pages at its own reference links (FactChecker.check_against), every readable one kept, no pertinence gate. A claim with no link, or none readable, reached the model with no evidence and is UNVERIFIED.

## Stage attribution

32 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=32) |
|---|---|
| retrieval | 6 (18.8%) |
| ranking | 0 (0.0%) |
| reasoning | 26 (81.2%) |
| aggregation | 0 (0.0%) |

Trace only: retrieval (fact013, fact017, fact030, fact055, fact150, fact175); reasoning (fact001, fact002, fact003, fact005, fact007, fact018, fact031, fact034, fact035, fact046, fact057, fact058, fact075, fact079, fact080, fact111, fact119, fact121, fact130, fact131, fact147, fact148, fact160, fact164, fact173, fact177).

No reference column: an oracle run's evidence is the annotator's own links, so "found the reference" holds by construction. Retrieval here means none of the claim's links could be read.

## Journalist effort

Over 70 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 35 | 50.0% [38.6, 61.4] |
| Confidently wrong (definitive, not gold) | 25 | 35.7% [24.3, 47.1] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 70 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 70 | 0.2 | 0.4 | 2.9 | 0.3% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 61 | 92.8 | 123.2 | 266.6 | 91.5% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 70 | 94.2 | 131.4 | 279.6 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 61 (0) |
| Claims the model was not asked about | 9 |
| Prompt / completion tokens | 67657 / 8678 |
| Tokens per claim asked (prompt / completion) | 1109.1 / 142.3 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 50.618 / 76.119 / 206.348 |
| Claim latency, median / p90 (s) | 94.195 / 131.413 |
| Completion tokens per second | 2.6 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`038bea7a04be`, localhost:11434); candidate B: this run. Paired over the 70 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 34.3% | 54.3% | +20.0 pts | [+5.7 pts, +34.3 pts] |
| macroF1 | 0.156 | 0.306 | +0.150 | [+0.044, +0.241] |
| coverage | 85.7% | 85.7% | +0.0 pts | [-11.4 pts, +11.4 pts] |
| selectiveAccuracy | 40.0% | 58.3% | +18.3 pts | [+2.5 pts, +33.7 pts] |
| kappa | 0.036 | 0.259 | +0.223 | [+0.003, +0.437] |

Only A right: 8; only B right: 22. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 70 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 69 | 0.0% | 88.4% | +88.4 pts [+81.2 pts, +95.7 pts] | 0 / 61 |
| Reference link among ranked evidence | 69 | 0.0% | 88.4% | +88.4 pts [+81.2 pts, +95.7 pts] | 0 / 61 |
| Reference link among cited evidence | 69 | 0.0% | 87.0% | +87.0 pts [+78.3 pts, +94.2 pts] | 0 / 60 |
| Reference domain among candidates | 69 | 0.0% | 88.4% | +88.4 pts [+81.2 pts, +95.7 pts] | 0 / 61 |
| Reference domain among ranked evidence | 69 | 0.0% | 88.4% | +88.4 pts [+81.2 pts, +95.7 pts] | 0 / 61 |
| Reference domain among cited evidence | 69 | 0.0% | 87.0% | +87.0 pts [+78.3 pts, +94.2 pts] | 0 / 60 |
| Link MRR (ranked) | 69 | 0.0% | 88.4% | +88.4 pts [+81.2 pts, +95.7 pts] | 0 / 61 |
| Domain MRR (ranked) | 69 | 0.0% | 88.4% | +88.4 pts [+81.2 pts, +95.7 pts] | 0 / 61 |
| Claims with any ranked evidence | 70 | 0.0% | 87.1% | +87.1 pts [+78.6 pts, +94.3 pts] |  |
| Candidates per claim | 70 | 0.00 | 1.46 | +1.46 [+1.24, +1.67] |  |
| Ranked sources per claim | 70 | 0.00 | 1.46 | +1.46 [+1.24, +1.67] |  |
| Distinct domains among ranked | 70 | 0.00 | 1.41 | +1.41 [+1.20, +1.63] |  |

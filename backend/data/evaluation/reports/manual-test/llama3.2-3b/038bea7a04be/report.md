# manual-test · llama3.2:3b · no evidence (closed book)

Run `038bea7a04be` · provider `localhost:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (0 points)

Dataset sha256 `1ea9a8b72ec3`, 70 rows; 70 run, 0 not run. Commits: `0f70c68f1006`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 70 | 70 |
| Accuracy | 34.3% [22.9%, 45.7%] | 34.3% [22.9%, 45.7%] |
| Macro-F1 (gold classes) | 0.156 [0.108, 0.203] | 0.156 [0.108, 0.203] |
| Coverage (not UNVERIFIED) | 85.7% [77.1%, 92.9%] | 85.7% [77.1%, 92.9%] |
| Selective accuracy | 40.0% [27.8%, 52.5%] | 40.0% [27.8%, 52.5%] |
| Cohen's kappa vs gold | 0.036 [-0.087, 0.162] | 0.036 [-0.087, 0.162] |

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
| temporalLeak (cited source newer than the claim) | 0 | 70 | 0 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 70 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 75.0% | 32.6% | 0.455 | 46 | 20 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 4 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 1 | 0 |
| FALSE | 22.5% | 60.0% | 0.327 | 15 | 40 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 4 | 10 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 15 | 0 | 0 | 25 | 6 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 1 |
| MISLEADING | 0 | 0 | 0 | 1 | 0 |
| FALSE | 3 | 0 | 0 | 9 | 3 |
| UNVERIFIED | 1 | 0 | 0 | 3 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 31.9% [19.1%, 44.7%] | 0.185 | 80.9% | 39.5% |
| es | 23 | 39.1% [21.7%, 60.9%] | 0.214 | 95.7% | 40.9% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 11 | 27.3% [0.0%, 54.5%] | 0.217 | 72.7% | 37.5% |
| environment | 18 | 38.9% [16.7%, 61.1%] | 0.216 | 88.9% | 43.8% |
| health | 16 | 50.0% [25.0%, 75.0%] | 0.356 | 81.2% | 61.5% |
| science | 16 | 25.0% [6.2%, 50.0%] | 0.134 | 100.0% | 25.0% |
| society | 9 | 22.2% [0.0%, 55.6%] | 0.100 | 77.8% | 28.6% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 44 | 34.1% [20.5%, 47.7%] | 0.187 | 90.9% | 37.5% |
| interpretive | 2 | 50.0% [0.0%, 100.0%] | 0.500 | 100.0% | 50.0% |
| numerical | 24 | 33.3% [16.7%, 54.2%] | 0.200 | 75.0% | 44.4% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 3 | 33.3% [0.0%, 100.0%] | 0.167 | 100.0% | 33.3% |
| primary | 37 | 37.8% [21.6%, 54.1%] | 0.158 | 86.5% | 43.8% |
| reference_media | 30 | 30.0% [13.3%, 46.7%] | 0.176 | 83.3% | 36.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 60.0% [33.3%, 86.7%] | 0.750 | 80.0% | 75.0% |
| natural | 55 | 27.3% [16.4%, 40.0%] | 0.119 | 87.3% | 31.2% |

## Evidence

None: each claim went to the model alone, with no evidence, no search and no pipeline (src/evaluation/closed_book.py). Its accuracy is what the model knows; the gap to a run that searched is what retrieval adds.

Said it remembered a published fact-check of the claim: 1 of 70 answered (fact135).

## Journalist effort

Over 70 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 0 | 0.0% [0.0, 0.0] |
| Confidently wrong (definitive, not gold) | 36 | 51.4% [40.0, 62.9] |

Right and definitive but citing no source with a stance: 24 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 70 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 0 | n/a | n/a | n/a | 0.0% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 70 | 18.9 | 25.6 | 32.2 | 100.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 70 | 18.9 | 25.6 | 32.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 70 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 17821 / 4694 |
| Tokens per claim asked (prompt / completion) | 254.6 / 67.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 9.268 / 13.071 / 17.479 |
| Claim latency, median / p90 (s) | 18.935 / 25.612 |
| Completion tokens per second | 6.8 |
| Cost | n/a (no price given, or tokens unknown) |

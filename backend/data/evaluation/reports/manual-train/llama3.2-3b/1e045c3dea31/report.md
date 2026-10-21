# manual-train · llama3.2:3b · the annotator's evidence (oracle) · igpu-head1500

Run `1e045c3dea31` · provider `localhost:11435` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `eb25b5473a23`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 65 |
| Accuracy | 56.5% [44.9%, 68.1%] | 55.4% [43.1%, 67.7%] |
| Macro-F1 (gold classes) | 0.382 [0.257, 0.486] | 0.374 [0.249, 0.479] |
| Coverage (not UNVERIFIED) | 89.9% [82.6%, 95.7%] | 89.2% [81.5%, 95.4%] |
| Selective accuracy | 58.1% [45.9%, 70.2%] | 56.9% [44.3%, 69.5%] |
| Cohen's kappa vs gold | 0.231 [0.039, 0.415] | 0.215 [0.025, 0.401] |

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
| temporalLeak (cited source newer than the claim) | 4 | 62 | 3 | fact088, fact089, fact146, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 78.4% | 64.4% | 0.707 | 45 | 37 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 1 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 29.2% | 46.7% | 0.359 | 15 | 24 |
| UNVERIFIED | 42.9% | 50.0% | 0.462 | 6 | 7 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 29 | 1 | 0 | 12 | 3 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 7 | 0 | 0 | 7 | 1 |
| UNVERIFIED | 0 | 0 | 0 | 3 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 58.3% [43.8%, 72.9%] | 0.408 | 85.4% | 61.0% |
| es | 21 | 52.4% [33.3%, 71.4%] | 0.257 | 100.0% | 52.4% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 70.0% [40.0%, 100.0%] | 0.600 | 100.0% | 70.0% |
| environment | 16 | 62.5% [37.5%, 87.5%] | 0.486 | 81.2% | 61.5% |
| health | 15 | 60.0% [33.3%, 86.7%] | 0.426 | 80.0% | 75.0% |
| science | 17 | 47.1% [23.5%, 70.6%] | 0.466 | 94.1% | 43.8% |
| society | 11 | 45.5% [18.2%, 72.7%] | 0.238 | 100.0% | 45.5% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 64.9% [48.6%, 81.1%] | 0.366 | 100.0% | 64.9% |
| interpretive | 3 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| numerical | 29 | 41.4% [24.1%, 58.6%] | 0.330 | 75.9% | 40.9% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 46.5% [32.6%, 60.5%] | 0.246 | 90.7% | 51.3% |
| reference_media | 25 | 72.0% [52.0%, 88.0%] | 0.544 | 88.0% | 68.2% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 46.7% [20.0%, 73.3%] | 0.636 | 93.3% | 50.0% |
| natural | 54 | 59.3% [46.3%, 72.2%] | 0.424 | 88.9% | 60.4% |

## Evidence

No search: each claim was judged on the pages at its own reference links (FactChecker.check_against), every readable one kept, no pertinence gate. A claim with no link, or none readable, reached the model with no evidence and is UNVERIFIED.

## Stage attribution

30 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=30) |
|---|---|
| retrieval | 4 (13.3%) |
| ranking | 0 (0.0%) |
| reasoning | 25 (83.3%) |
| aggregation | 1 (3.3%) |

Trace only: retrieval (fact021, fact037, fact138, fact174); reasoning (fact008, fact009, fact010, fact011, fact016, fact038, fact066, fact081, fact088, fact100, fact123, fact125, fact126, fact129, fact139, fact142, fact143, fact144, fact151, fact153, fact154, fact156, fact162, fact169, fact172); aggregation (fact020).

No reference column: an oracle run's evidence is the annotator's own links, so "found the reference" holds by construction. Retrieval here means none of the claim's links could be read.

## Journalist effort

Over 69 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 33 | 47.8% [36.2, 59.4] |
| Confidently wrong (definitive, not gold) | 26 | 37.7% [26.1, 49.3] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.2 | 0.5 | 0.2% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 62 | 54.2 | 78.2 | 109.5 | 90.8% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 58.4 | 81.8 | 116.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 62 (0) |
| Claims the model was not asked about | 7 |
| Prompt / completion tokens | 77354 / 9742 |
| Tokens per claim asked (prompt / completion) | 1247.6 / 157.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 29.935 / 45.420 / 59.507 |
| Claim latency, median / p90 (s) | 58.406 / 81.822 |
| Completion tokens per second | 5.1 |
| Cost | n/a (no price given, or tokens unknown) |

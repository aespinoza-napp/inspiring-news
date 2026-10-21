# manual-train · llama3.2:3b · the annotator's evidence (oracle) · igpu-passages700

Run `08bcab0248c3` · provider `localhost:11435` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `eb25b5473a23`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 68 | 64 |
| Accuracy | 61.8% [50.0%, 73.5%] | 59.4% [46.9%, 71.9%] |
| Macro-F1 (gold classes) | 0.410 [0.286, 0.510] | 0.397 [0.274, 0.500] |
| Coverage (not UNVERIFIED) | 88.2% [79.4%, 95.6%] | 87.5% [78.1%, 95.3%] |
| Selective accuracy | 65.0% [52.5%, 76.8%] | 62.5% [50.0%, 74.6%] |
| Cohen's kappa vs gold | 0.327 [0.147, 0.504] | 0.297 [0.114, 0.474] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 1 | fact081 |
| scored | 68 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 4 | 63 | 1 | fact088, fact089, fact146, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 68 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 83.8% | 70.5% | 0.765 | 44 | 37 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 2 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 38.1% | 53.3% | 0.444 | 15 | 21 |
| UNVERIFIED | 37.5% | 50.0% | 0.429 | 6 | 8 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 31 | 0 | 0 | 9 | 4 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 4 | 2 | 0 | 8 | 1 |
| UNVERIFIED | 1 | 0 | 0 | 2 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 70.2% [57.4%, 83.0%] | 0.482 | 85.1% | 75.0% |
| es | 21 | 42.9% [23.8%, 61.9%] | 0.205 | 95.2% | 45.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 60.0% [30.0%, 90.0%] | 0.400 | 90.0% | 66.7% |
| environment | 16 | 75.0% [50.0%, 93.8%] | 0.560 | 81.2% | 76.9% |
| health | 15 | 60.0% [33.3%, 86.7%] | 0.426 | 80.0% | 75.0% |
| science | 16 | 62.5% [37.5%, 87.5%] | 0.544 | 93.8% | 60.0% |
| society | 11 | 45.5% [18.2%, 72.7%] | 0.300 | 100.0% | 45.5% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 67.6% [51.4%, 81.1%] | 0.397 | 97.3% | 69.4% |
| interpretive | 3 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| numerical | 28 | 50.0% [32.1%, 67.9%] | 0.383 | 75.0% | 52.4% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 42 | 57.1% [42.9%, 71.4%] | 0.304 | 90.5% | 63.2% |
| reference_media | 25 | 68.0% [48.0%, 84.0%] | 0.505 | 84.0% | 66.7% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 53.3% [26.7%, 80.0%] | 0.696 | 93.3% | 57.1% |
| natural | 53 | 64.2% [50.9%, 77.4%] | 0.422 | 86.8% | 67.4% |

## Evidence

No search: each claim was judged on the pages at its own reference links (FactChecker.check_against), every readable one kept, no pertinence gate. A claim with no link, or none readable, reached the model with no evidence and is UNVERIFIED.

## Stage attribution

26 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=26) |
|---|---|
| retrieval | 4 (15.4%) |
| ranking | 0 (0.0%) |
| reasoning | 21 (80.8%) |
| aggregation | 1 (3.8%) |

Trace only: retrieval (fact021, fact037, fact138, fact174); reasoning (fact008, fact009, fact010, fact011, fact016, fact020, fact066, fact100, fact107, fact124, fact125, fact126, fact129, fact143, fact144, fact151, fact153, fact156, fact169, fact171, fact172); aggregation (fact117).

No reference column: an oracle run's evidence is the annotator's own links, so "found the reference" holds by construction. Retrieval here means none of the claim's links could be read.

## Journalist effort

Over 68 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 35 | 51.5% [39.7, 63.2] |
| Confidently wrong (definitive, not gold) | 21 | 30.9% [20.6, 42.6] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 68 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 68 | 0.1 | 0.1 | 0.3 | 0.2% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 61 | 40.4 | 60.0 | 211.2 | 90.4% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 68 | 44.0 | 63.1 | 213.6 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 63 (2) |
| Claims the model was not asked about | 7 |
| Prompt / completion tokens | 53653 / 10264 |
| Tokens per claim asked (prompt / completion) | 879.6 / 168.3 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 22.776 / 33.889 / 42.270 |
| Claim latency, median / p90 (s) | 44.038 / 63.926 |
| Completion tokens per second | 7.1 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`1e045c3dea31`, localhost:11435); candidate B: this run. Paired over the 68 claims both scored; 1 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 57.4% | 61.8% | +4.4 pts | [-4.4 pts, +13.2 pts] |
| macroF1 | 0.387 | 0.410 | +0.023 | [-0.037, +0.083] |
| coverage | 89.7% | 88.2% | -1.5 pts | [-4.4 pts, +0.0 pts] |
| selectiveAccuracy | 59.0% | 65.0% | +6.0 pts | [-4.1 pts, +16.4 pts] |
| kappa | 0.243 | 0.327 | +0.084 | [-0.055, +0.241] |

Only A right: 4; only B right: 7. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 92.5% | 92.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 92.5% | 92.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 92.5% | 91.0% | -1.5 pts [-4.5 pts, +0.0 pts] | 1 / 0 |
| Reference domain among candidates | 67 | 92.5% | 92.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 92.5% | 92.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 92.5% | 91.0% | -1.5 pts [-4.5 pts, +0.0 pts] | 1 / 0 |
| Link MRR (ranked) | 67 | 92.5% | 92.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 67 | 92.5% | 92.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 69 | 89.9% | 89.9% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 1.67 | 1.68 | +0.01 [+0.00, +0.04] |  |
| Ranked sources per claim | 69 | 1.67 | 1.68 | +0.01 [+0.00, +0.04] |  |
| Share cut at ranking (gate, cap) | 62 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 69 | 1.59 | 1.61 | +0.01 [+0.00, +0.04] |  |
| Ranked from rated domains | 62 | 8.1% | 8.1% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 62 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |

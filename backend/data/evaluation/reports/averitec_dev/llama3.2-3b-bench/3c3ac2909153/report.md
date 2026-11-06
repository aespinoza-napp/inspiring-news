# averitec_dev · llama3.2:3b-bench · no evidence (closed book)

Run `3c3ac2909153` · provider `localhost:11434` · harness v1 · thresholds `120a3cd7dbc3` · corpus `none` (0 points)

Dataset sha256 `00cf6537b050`, 500 rows; 100 run, 400 not run. Commits: `693af93167fb`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 100 of 500 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **58.0%** [48.0%, 68.0%] | **0.256** [0.200, 0.311] | 100 |
| Over the claims with a working search and model | 58.0% | 0.256 | 100 |
| Always answering Refuted | 58.0% | 0.184 | 100 |

F1 by class: Supported 0.308, Refuted 0.717, Not Enough Evidence 0.000, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 6 | 22 | 0 | 0 | 0 |
| Refuted | 4 | 52 | 1 | 1 | 0 |
| Not Enough Evidence | 1 | 7 | 0 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 0 | 6 | 0 | 0 | 0 |

### Nothing from after the claim

**Held**: no source given to the model is dated on or after its claim, none is the claim's own fact-check, none is an undated fact-check, and none is a reference page as served today.

| | |
|---|---:|
| Sources given to the model | 0 |
| ... with a date before the claim | 0 |
| ... with no date (kept only under `evidence_undated: keep`) | 0 |
| Refused as published on or after the claim | 0 |
| Refused for having no date | 0 |
| Refused as a reference work rewritten since | 0 |
| Refused as an undated fact-check | 0 |
| Claims left with no evidence at all | 100 |

Not covered by this audit: a page published in time and edited later, and what the model itself remembers from training (see a `--closed-book` run).

### Published on the same split

ClaimCheck (Putta et al., 2025), Table 1. Compare with systems using the same kind of evidence.

| System | Accuracy | Evidence |
|---|---:|---|
| ClaimCheck (Qwen3-4B) | 76.4% | web, before the claim |
| PASS-FC (GPT-4o) | 72.0% | web |
| DEFAME (GPT-4o) | 70.5% | web |
| GPT-4o + web search | 74.6% | web, leaks |
| GPT-4o mini + web search | 70.4% | web, leaks |
| Papelo (GPT-4o mini) | 41.5% | web |
| HerO (Llama 3.1 70B) | 75.2% | knowledge store |
| InFact (GPT-4o) | 72.4% | knowledge store |
| GPT-4o | 53.2% | none |
| Qwen3-4B | 52.0% | none |
| GPT-4o mini | 46.8% | none |

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 100 | 100 |
| Accuracy | 58.0% [48.0%, 68.0%] | 58.0% [48.0%, 68.0%] |
| Macro-F1 (gold classes) | 0.256 [0.200, 0.311] | 0.256 [0.200, 0.311] |
| Coverage (not UNVERIFIED) | 99.0% [97.0%, 100.0%] | 99.0% [97.0%, 100.0%] |
| Selective accuracy | 58.6% [49.0%, 68.0%] | 58.6% [49.0%, 68.0%] |
| Cohen's kappa vs gold | 0.093 [-0.036, 0.235] | 0.093 [-0.036, 0.235] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 100 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 0 | 100 | 0 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 100 | 0 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 54.5% | 21.4% | 0.308 | 28 | 11 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | 0.0% | 0.0% | 0.000 | 6 | 1 |
| FALSE | 59.8% | 89.7% | 0.717 | 58 | 87 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 8 | 1 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 6 | 0 | 0 | 22 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 0 | 0 | 0 | 6 | 0 |
| FALSE | 4 | 0 | 1 | 52 | 1 |
| UNVERIFIED | 1 | 0 | 0 | 7 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 100 | 58.0% [48.0%, 68.0%] | 0.256 | 99.0% | 58.6% |

## Evidence

None: each claim went to the model alone, with no evidence, no search and no pipeline (src/evaluation/closed_book.py). Its accuracy is what the model knows; the gap to a run that searched is what retrieval adds.

Said it remembered a published fact-check of the claim: 5 of 100 answered (averitec-dev-0155, averitec-dev-0177, averitec-dev-0219, averitec-dev-0450, averitec-dev-0469).

## Journalist effort

Over 100 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 0 | 0.0% [0.0, 0.0] |
| Confidently wrong (definitive, not gold) | 41 | 41.0% [31.0, 51.0] |

Right and definitive but citing no source with a stance: 58 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 100 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 0 | n/a | n/a | n/a | 0.0% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| of which: the web search, every query | 0 | n/a | n/a | n/a | 0.0% |
| of which: the page fetches | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 100 | 12.6 | 15.4 | 19.6 | 100.0% |
| of which: waiting for the model (another claim's call) | 0 | n/a | n/a | n/a | 0.0% |
| of which: the model's call itself | 0 | n/a | n/a | n/a | 0.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 100 | 12.6 | 15.4 | 19.6 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 100 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 23752 / 6507 |
| Tokens per claim asked (prompt / completion) | 237.5 / 65.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 6.146 / 8.381 / 11.674 |
| Claim latency, median / p90 (s) | 12.644 / 15.446 |
| Completion tokens per second | 10.3 |
| Cost | n/a (no price given, or tokens unknown) |

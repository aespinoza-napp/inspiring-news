# averitec_dev_balanced · llama3.2:3b-bench · knowledge-store

Run `1ee9810b5fa1` · provider `localhost:11434` · harness v1 · thresholds `d0deef88b2e7` · corpus `none` (0 points)

Dataset sha256 `68a894e2c414`, 140 rows; 20 run, 120 not run. Commits: `d8842946744c`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 20 of 140 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **20.0%** [5.0%, 40.0%] | **0.176** [0.029, 0.329] | 20 |
| Over the claims with a working search and model | 20.0% | 0.176 | 20 |
| Always answering Refuted | 25.0% | 0.100 | 20 |

F1 by class: Supported 0.182, Refuted 0.235, Not Enough Evidence 0.286, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 1 | 4 | 0 | 0 | 0 |
| Refuted | 3 | 2 | 0 | 0 | 0 |
| Not Enough Evidence | 2 | 2 | 1 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 0 | 4 | 1 | 0 | 0 |

### Nothing from after the claim

**Held**: no source given to the model is dated on or after its claim, by its address or its text, none is the claim's own fact-check, none is an undated fact-check, and none is a reference page as served today.

| | |
|---|---:|
| Sources given to the model | 96 |
| ... with a date before the claim | 29 |
| ... with no date (kept only under `evidence_undated: keep`) | 67 |
| ... with no date anywhere, address or text: nothing shows when these were written | 41 |
| Refused as published on or after the claim | 16 |
| Refused for a date in their text on or after the claim | 40 |
| Refused for having no date | 0 |
| Refused as a reference work rewritten since | 10 |
| Refused as an undated fact-check | 37 |
| Claims left with no evidence at all | 0 |

Not covered by this audit: a page with no date anywhere, one edited later without a trace, and what the model itself remembers from training (see a `--closed-book` run).

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
| Claims | 20 | 20 |
| Accuracy | 20.0% [5.0%, 40.0%] | 20.0% [5.0%, 40.0%] |
| Macro-F1 (gold classes) | 0.176 [0.029, 0.329] | 0.176 [0.029, 0.329] |
| Coverage (not UNVERIFIED) | 90.0% [75.0%, 100.0%] | 90.0% [75.0%, 100.0%] |
| Selective accuracy | 16.7% [0.0%, 35.3%] | 16.7% [0.0%, 35.3%] |
| Cohen's kappa vs gold | -0.067 [-0.293, 0.164] | -0.067 [-0.293, 0.164] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 20 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 0 | 2 | 18 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 20 | 0 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 16.7% | 20.0% | 0.182 | 5 | 6 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 5 | 0 |
| FALSE | 16.7% | 40.0% | 0.235 | 5 | 12 |
| UNVERIFIED | 50.0% | 20.0% | 0.286 | 5 | 2 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 1 | 0 | 0 | 4 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 0 | 0 | 0 | 4 | 1 |
| FALSE | 3 | 0 | 0 | 2 | 0 |
| UNVERIFIED | 2 | 0 | 0 | 2 | 1 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 20 | 20.0% [5.0%, 40.0%] | 0.176 | 90.0% | 16.7% |

## Retrieval

20 claims searched (19 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 1 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 10.5% [0.0%, 26.3%] (n=19) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=19) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=19) |
| Reference domain among candidates | 26.3% [10.5%, 47.4%] (n=19) |
| Reference domain among ranked evidence | 0.0% [0.0%, 0.0%] (n=19) |
| Reference domain among cited evidence | 0.0% [0.0%, 0.0%] (n=19) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=19) |
| Domain MRR (ranked) | 0.0% [0.0%, 0.0%] (n=19) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=20) |
| Candidates per claim | 20.55 [19.40, 21.65] (n=20) |
| Ranked sources per claim | 4.80 [4.60, 4.95] (n=20) |
| Share cut at ranking (gate, cap) | 2.0% [0.0%, 5.0%] (n=20) |
| Distinct domains among ranked | 4.80 [4.60, 4.95] (n=20) |
| Ranked from rated domains | 4.0% [1.0%, 8.0%] (n=20) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=20) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 13.77 [11.87, 15.72] (n=20) |
| Ranking seconds per claim | 10.46 [9.55, 11.35] (n=20) |

Medians: 20.50 candidates, 5.00 ranked, 13.36 s retrieval, 10.93 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 56, anchor 45, refutation 13 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 1
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| averitec | 20 | 19 | 0.0% | 0.0% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 20 | 19 | 0.0% | 0.0% | 100.0% |

## Stage attribution

16 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=16) | By reference (n=15) |
|---|---|---|
| retrieval | 0 (0.0%) | 12 (80.0%) |
| ranking | 0 (0.0%) | 3 (20.0%) |
| reasoning | 16 (100.0%) | 0 (0.0%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (averitec-dev-0025, averitec-dev-0026, averitec-dev-0047, averitec-dev-0096, averitec-dev-0115, averitec-dev-0156, averitec-dev-0164, averitec-dev-0175, averitec-dev-0186, averitec-dev-0259, averitec-dev-0281, averitec-dev-0288, averitec-dev-0368, averitec-dev-0404, averitec-dev-0428, averitec-dev-0498).

By reference: retrieval (averitec-dev-0025, averitec-dev-0026, averitec-dev-0047, averitec-dev-0115, averitec-dev-0156, averitec-dev-0175, averitec-dev-0186, averitec-dev-0288, averitec-dev-0368, averitec-dev-0404, averitec-dev-0428, averitec-dev-0498); ranking (averitec-dev-0164, averitec-dev-0259, averitec-dev-0281).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 2
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1

Without a reference link to judge by (1): averitec-dev-0096.

The two columns disagree on 15 of the 15 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0025 | reasoning | retrieval |
| averitec-dev-0026 | reasoning | retrieval |
| averitec-dev-0047 | reasoning | retrieval |
| averitec-dev-0115 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0164 | reasoning | ranking |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0186 | reasoning | retrieval |
| averitec-dev-0259 | reasoning | ranking |
| averitec-dev-0281 | reasoning | ranking |
| averitec-dev-0288 | reasoning | retrieval |
| averitec-dev-0368 | reasoning | retrieval |
| averitec-dev-0404 | reasoning | retrieval |
| averitec-dev-0428 | reasoning | retrieval |
| averitec-dev-0498 | reasoning | retrieval |

## Journalist effort

Over 20 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 3 | 15.0% [0.0, 30.0] |
| Confidently wrong (definitive, not gold) | 15 | 75.0% [55.0, 90.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 20 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 20 | 0.7 | 0.8 | 1.2 | 1.0% |
| Evidence retrieval | 20 | 13.4 | 19.3 | 21.1 | 22.5% |
| of which: the web search, every query | 20 | 1.5 | 2.1 | 3.4 | 2.4% |
| of which: the page fetches | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| Ranking | 20 | 10.9 | 12.9 | 14.1 | 17.1% |
| The model's verdict (with its wait for a permit) | 20 | 37.8 | 46.0 | 54.3 | 59.3% |
| of which: waiting for the model (another claim's call) | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the model's call itself | 20 | 37.8 | 46.0 | 54.3 | 59.3% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 20 | 66.7 | 77.3 | 86.1 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 96 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 41904 / 3362 |
| Tokens per claim asked (prompt / completion) | 2095.2 / 168.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 7.129 / 10.173 / 17.729 |
| Claim latency, median / p90 (s) | 66.674 / 77.334 |
| Completion tokens per second | 4.6 |
| Cost | n/a (no price given, or tokens unknown) |

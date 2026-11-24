# averitec_dev_balanced · llama3.2:3b-bench · knowledge-store

Run `1ee9810b5fa1` · provider `localhost:11434` · harness v1 · thresholds `d0deef88b2e7` · corpus `none` (0 points)

Dataset sha256 `68a894e2c414`, 140 rows; 40 run, 100 not run. Commits: `0163ff2bf81a`, `d8842946744c`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 40 of 140 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **25.0%** [12.5%, 40.0%] | **0.228** [0.108, 0.333] | 40 |
| Over the claims with a working search and model | 25.0% | 0.228 | 40 |
| Always answering Refuted | 25.0% | 0.100 | 40 |

F1 by class: Supported 0.190, Refuted 0.250, Not Enough Evidence 0.471, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 2 | 8 | 0 | 0 | 0 |
| Refuted | 5 | 4 | 1 | 0 | 0 |
| Not Enough Evidence | 3 | 3 | 4 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 1 | 7 | 2 | 0 | 0 |

### Nothing from after the claim

**Held**: no source given to the model is dated on or after its claim, by its address or its text, none is the claim's own fact-check, none is an undated fact-check, and none is a reference page as served today.

| | |
|---|---:|
| Sources given to the model | 193 |
| ... with a date before the claim | 70 |
| ... with no date (kept only under `evidence_undated: keep`) | 123 |
| ... with no date anywhere, address or text: nothing shows when these were written | 71 |
| Refused as published on or after the claim | 22 |
| Refused for a date in their text on or after the claim | 81 |
| Refused for having no date | 0 |
| Refused as a reference work rewritten since | 22 |
| Refused as an undated fact-check | 77 |
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
| Claims | 40 | 38 |
| Accuracy | 25.0% [12.5%, 40.0%] | 23.7% [10.5%, 36.8%] |
| Macro-F1 (gold classes) | 0.228 [0.108, 0.333] | 0.217 [0.099, 0.321] |
| Coverage (not UNVERIFIED) | 82.5% [70.0%, 92.5%] | 81.6% [68.4%, 92.1%] |
| Selective accuracy | 18.2% [6.1%, 32.4%] | 16.1% [3.4%, 30.0%] |
| Cohen's kappa vs gold | 0.000 [-0.176, 0.176] | -0.017 [-0.201, 0.158] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 40 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 0 | 6 | 34 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 2 | 38 | 0 | averitec-dev-0324, averitec-dev-0481 |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 18.2% | 20.0% | 0.190 | 10 | 11 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 10 | 0 |
| FALSE | 18.2% | 40.0% | 0.250 | 10 | 22 |
| UNVERIFIED | 57.1% | 40.0% | 0.471 | 10 | 7 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 2 | 0 | 0 | 8 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 1 | 0 | 0 | 7 | 2 |
| FALSE | 5 | 0 | 0 | 4 | 1 |
| UNVERIFIED | 3 | 0 | 0 | 3 | 4 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 40 | 25.0% [12.5%, 40.0%] | 0.228 | 82.5% | 18.2% |

## Retrieval

40 claims searched (39 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 1 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 10.3% [2.6%, 20.5%] (n=39) |
| Reference link among ranked evidence | 5.1% [0.0%, 12.8%] (n=39) |
| Reference link among cited evidence | 5.1% [0.0%, 12.8%] (n=39) |
| Reference domain among candidates | 28.2% [15.4%, 43.6%] (n=39) |
| Reference domain among ranked evidence | 10.3% [2.6%, 20.5%] (n=39) |
| Reference domain among cited evidence | 7.7% [0.0%, 17.9%] (n=39) |
| Link MRR (ranked) | 2.6% [0.0%, 6.4%] (n=39) |
| Domain MRR (ranked) | 7.7% [1.3%, 16.7%] (n=39) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=40) |
| Candidates per claim | 20.50 [19.57, 21.38] (n=40) |
| Ranked sources per claim | 4.83 [4.67, 4.95] (n=40) |
| Share cut at ranking (gate, cap) | 2.5% [0.5%, 5.5%] (n=40) |
| Distinct domains among ranked | 4.83 [4.67, 4.95] (n=40) |
| Ranked from rated domains | 5.0% [1.5%, 9.0%] (n=40) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=40) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 11.16 [9.89, 12.53] (n=40) |
| Ranking seconds per claim | 8.51 [7.72, 9.35] (n=40) |

Medians: 22.00 candidates, 5.00 ranked, 9.69 s retrieval, 7.38 s ranking; 2.98 queries per claim.

Ranked sources found by: proposition 127, anchor 76, refutation 30 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 1
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| averitec | 40 | 39 | 5.1% | 10.3% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 40 | 39 | 5.1% | 10.3% | 100.0% |

## Stage attribution

30 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=30) | By reference (n=29) |
|---|---|---|
| retrieval | 0 (0.0%) | 21 (72.4%) |
| ranking | 0 (0.0%) | 4 (13.8%) |
| reasoning | 30 (100.0%) | 4 (13.8%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (averitec-dev-0012, averitec-dev-0025, averitec-dev-0026, averitec-dev-0047, averitec-dev-0060, averitec-dev-0068, averitec-dev-0096, averitec-dev-0115, averitec-dev-0148, averitec-dev-0155, averitec-dev-0156, averitec-dev-0164, averitec-dev-0166, averitec-dev-0175, averitec-dev-0186, averitec-dev-0235, averitec-dev-0255, averitec-dev-0259, averitec-dev-0281, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0324, averitec-dev-0366, averitec-dev-0368, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0428, averitec-dev-0498).

By reference: retrieval (averitec-dev-0025, averitec-dev-0026, averitec-dev-0047, averitec-dev-0068, averitec-dev-0115, averitec-dev-0155, averitec-dev-0156, averitec-dev-0166, averitec-dev-0175, averitec-dev-0186, averitec-dev-0235, averitec-dev-0255, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0366, averitec-dev-0368, averitec-dev-0394, averitec-dev-0404, averitec-dev-0428, averitec-dev-0498); ranking (averitec-dev-0164, averitec-dev-0259, averitec-dev-0281, averitec-dev-0406); reasoning (averitec-dev-0012, averitec-dev-0060, averitec-dev-0148, averitec-dev-0324).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 2
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 11, top 5 kept): 1

Without a reference link to judge by (1): averitec-dev-0096.

The two columns disagree on 25 of the 29 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0025 | reasoning | retrieval |
| averitec-dev-0026 | reasoning | retrieval |
| averitec-dev-0047 | reasoning | retrieval |
| averitec-dev-0068 | reasoning | retrieval |
| averitec-dev-0115 | reasoning | retrieval |
| averitec-dev-0155 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0164 | reasoning | ranking |
| averitec-dev-0166 | reasoning | retrieval |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0186 | reasoning | retrieval |
| averitec-dev-0235 | reasoning | retrieval |
| averitec-dev-0255 | reasoning | retrieval |
| averitec-dev-0259 | reasoning | ranking |
| averitec-dev-0281 | reasoning | ranking |
| averitec-dev-0283 | reasoning | retrieval |
| averitec-dev-0288 | reasoning | retrieval |
| averitec-dev-0306 | reasoning | retrieval |
| averitec-dev-0366 | reasoning | retrieval |
| averitec-dev-0368 | reasoning | retrieval |
| averitec-dev-0394 | reasoning | retrieval |
| averitec-dev-0404 | reasoning | retrieval |
| averitec-dev-0406 | reasoning | ranking |
| averitec-dev-0428 | reasoning | retrieval |
| averitec-dev-0498 | reasoning | retrieval |

## Journalist effort

Over 40 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 5 | 12.5% [2.5, 22.6] |
| Confidently wrong (definitive, not gold) | 27 | 67.5% [52.5, 82.5] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 40 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 40 | 0.4 | 0.8 | 1.2 | 1.0% |
| Evidence retrieval | 40 | 9.7 | 18.5 | 21.1 | 22.2% |
| of which: the web search, every query | 40 | 1.2 | 2.1 | 3.4 | 2.8% |
| of which: the page fetches | 40 | 0.0 | 0.0 | 0.0 | 0.0% |
| Ranking | 40 | 7.4 | 12.0 | 14.1 | 16.9% |
| The model's verdict (with its wait for a permit) | 40 | 25.8 | 45.7 | 54.3 | 60.0% |
| of which: waiting for the model (another claim's call) | 40 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the model's call itself | 40 | 25.8 | 45.6 | 54.3 | 59.9% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 40 | 43.4 | 72.4 | 86.1 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 193 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 83855 / 6614 |
| Tokens per claim asked (prompt / completion) | 2096.4 / 165.3 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 5.692 / 9.626 / 17.729 |
| Claim latency, median / p90 (s) | 43.412 / 72.442 |
| Completion tokens per second | 5.5 |
| Cost | n/a (no price given, or tokens unknown) |

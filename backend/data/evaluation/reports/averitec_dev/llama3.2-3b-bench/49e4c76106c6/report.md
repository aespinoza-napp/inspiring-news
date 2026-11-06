# averitec_dev · llama3.2:3b-bench · knowledge-store

Run `49e4c76106c6` · provider `localhost:11434` · harness v1 · thresholds `5198563e7b2e` · corpus `none` (0 points)

Dataset sha256 `00cf6537b050`, 500 rows; 100 run, 400 not run. Commits: `693af93167fb`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 100 of 500 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **54.0%** [44.0%, 64.0%] | **0.339** [0.260, 0.417] | 100 |
| Over the claims with a working search and model | 54.0% | 0.339 | 100 |
| Always answering Refuted | 58.0% | 0.184 | 100 |

F1 by class: Supported 0.444, Refuted 0.690, Not Enough Evidence 0.222, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 12 | 11 | 5 | 0 | 0 |
| Refuted | 11 | 39 | 8 | 0 | 0 |
| Not Enough Evidence | 2 | 3 | 3 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 1 | 2 | 3 | 0 | 0 |

### Nothing from after the claim

**Held**: no source given to the model is dated on or after its claim, by its address or its text, none is the claim's own fact-check, none is an undated fact-check, and none is a reference page as served today.

| | |
|---|---:|
| Sources given to the model | 481 |
| ... with a date before the claim | 149 |
| ... with no date (kept only under `evidence_undated: keep`) | 332 |
| ... with no date anywhere, address or text: nothing shows when these were written | 184 |
| Refused as published on or after the claim | 82 |
| Refused for a date in their text on or after the claim | 162 |
| Refused for having no date | 0 |
| Refused as a reference work rewritten since | 38 |
| Refused as an undated fact-check | 177 |
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
| Claims | 100 | 95 |
| Accuracy | 54.0% [44.0%, 64.0%] | 52.6% [43.2%, 62.1%] |
| Macro-F1 (gold classes) | 0.339 [0.260, 0.417] | 0.329 [0.249, 0.408] |
| Coverage (not UNVERIFIED) | 81.0% [73.0%, 88.0%] | 81.1% [72.6%, 88.4%] |
| Selective accuracy | 63.0% [52.4%, 73.6%] | 61.0% [50.0%, 71.8%] |
| Cohen's kappa vs gold | 0.224 [0.081, 0.369] | 0.200 [0.052, 0.346] |

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
| temporalLeak (cited source newer than the claim) | 0 | 12 | 88 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 5 | 95 | 0 | averitec-dev-0105, averitec-dev-0140, averitec-dev-0450, averitec-dev-0481, averitec-dev-0495 |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 46.2% | 42.9% | 0.444 | 28 | 26 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 6 | 0 |
| FALSE | 70.9% | 67.2% | 0.690 | 58 | 55 |
| UNVERIFIED | 15.8% | 37.5% | 0.222 | 8 | 19 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 12 | 0 | 0 | 11 | 5 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 1 | 0 | 0 | 2 | 3 |
| FALSE | 11 | 0 | 0 | 39 | 8 |
| UNVERIFIED | 2 | 0 | 0 | 3 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 100 | 54.0% [44.0%, 64.0%] | 0.339 | 81.0% | 63.0% |

## Retrieval

100 claims searched (96 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 4 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 12.5% [6.2%, 19.8%] (n=96) |
| Reference link among ranked evidence | 4.2% [1.0%, 8.3%] (n=96) |
| Reference link among cited evidence | 3.1% [0.0%, 7.3%] (n=96) |
| Reference domain among candidates | 22.9% [14.6%, 31.2%] (n=96) |
| Reference domain among ranked evidence | 8.3% [3.1%, 14.6%] (n=96) |
| Reference domain among cited evidence | 4.2% [1.0%, 8.3%] (n=96) |
| Link MRR (ranked) | 3.4% [0.3%, 7.3%] (n=96) |
| Domain MRR (ranked) | 6.3% [2.2%, 11.5%] (n=96) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=100) |
| Candidates per claim | 20.69 [20.08, 21.26] (n=100) |
| Ranked sources per claim | 4.81 [4.71, 4.90] (n=100) |
| Share cut at ranking (gate, cap) | 3.0% [1.4%, 5.0%] (n=100) |
| Distinct domains among ranked | 4.81 [4.71, 4.90] (n=100) |
| Ranked from rated domains | 3.5% [1.8%, 5.4%] (n=100) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=100) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 39.44 [36.21, 42.83] (n=100) |
| Ranking seconds per claim | 26.53 [24.33, 28.81] (n=100) |

Medians: 22.00 candidates, 5.00 ranked, 36.04 s retrieval, 23.28 s ranking; 2.98 queries per claim.

Ranked sources found by: proposition 311, anchor 202, refutation 76 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: published on or after the claim's date (temporal cutoff): 2
- evidence_retrieval: its text states a date on or after the claim's (temporal cutoff): 2
- evidence_retrieval: cut by pre-rank funnel (rank 8 of 15, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 6 of 16, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 16, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 7 of 17, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (indiatimes.com): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| averitec | 100 | 96 | 4.2% | 8.3% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 100 | 96 | 4.2% | 8.3% | 100.0% |

## Stage attribution

46 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=46) | By reference (n=44) |
|---|---|---|
| retrieval | 0 (0.0%) | 33 (75.0%) |
| ranking | 0 (0.0%) | 7 (15.9%) |
| reasoning | 46 (100.0%) | 4 (9.1%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (averitec-dev-0010, averitec-dev-0012, averitec-dev-0026, averitec-dev-0060, averitec-dev-0066, averitec-dev-0096, averitec-dev-0117, averitec-dev-0119, averitec-dev-0137, averitec-dev-0147, averitec-dev-0150, averitec-dev-0155, averitec-dev-0156, averitec-dev-0164, averitec-dev-0166, averitec-dev-0175, averitec-dev-0182, averitec-dev-0215, averitec-dev-0219, averitec-dev-0222, averitec-dev-0235, averitec-dev-0241, averitec-dev-0258, averitec-dev-0262, averitec-dev-0267, averitec-dev-0281, averitec-dev-0283, averitec-dev-0288, averitec-dev-0327, averitec-dev-0336, averitec-dev-0360, averitec-dev-0368, averitec-dev-0370, averitec-dev-0381, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0418, averitec-dev-0428, averitec-dev-0443, averitec-dev-0470, averitec-dev-0478, averitec-dev-0488, averitec-dev-0489, averitec-dev-0495, averitec-dev-0498).

By reference: retrieval (averitec-dev-0026, averitec-dev-0066, averitec-dev-0137, averitec-dev-0147, averitec-dev-0150, averitec-dev-0155, averitec-dev-0156, averitec-dev-0166, averitec-dev-0175, averitec-dev-0182, averitec-dev-0215, averitec-dev-0219, averitec-dev-0222, averitec-dev-0235, averitec-dev-0241, averitec-dev-0258, averitec-dev-0267, averitec-dev-0283, averitec-dev-0288, averitec-dev-0327, averitec-dev-0336, averitec-dev-0368, averitec-dev-0370, averitec-dev-0394, averitec-dev-0404, averitec-dev-0418, averitec-dev-0428, averitec-dev-0443, averitec-dev-0470, averitec-dev-0478, averitec-dev-0488, averitec-dev-0489, averitec-dev-0498); ranking (averitec-dev-0010, averitec-dev-0119, averitec-dev-0164, averitec-dev-0262, averitec-dev-0281, averitec-dev-0406, averitec-dev-0495); reasoning (averitec-dev-0012, averitec-dev-0060, averitec-dev-0117, averitec-dev-0360).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 2
- evidence_retrieval: same domain as a higher-ranked source (service.gov.uk): 2
- evidence_retrieval: cut by pre-rank funnel (rank 15 of 18, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 7 of 17, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 16, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 10 of 16, top 5 kept): 1
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 11, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 15 of 15, top 5 kept): 1

Without a reference link to judge by (2): averitec-dev-0096, averitec-dev-0381.

The two columns disagree on 40 of the 44 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0010 | reasoning | ranking |
| averitec-dev-0026 | reasoning | retrieval |
| averitec-dev-0066 | reasoning | retrieval |
| averitec-dev-0119 | reasoning | ranking |
| averitec-dev-0137 | reasoning | retrieval |
| averitec-dev-0147 | reasoning | retrieval |
| averitec-dev-0150 | reasoning | retrieval |
| averitec-dev-0155 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0164 | reasoning | ranking |
| averitec-dev-0166 | reasoning | retrieval |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0182 | reasoning | retrieval |
| averitec-dev-0215 | reasoning | retrieval |
| averitec-dev-0219 | reasoning | retrieval |
| averitec-dev-0222 | reasoning | retrieval |
| averitec-dev-0235 | reasoning | retrieval |
| averitec-dev-0241 | reasoning | retrieval |
| averitec-dev-0258 | reasoning | retrieval |
| averitec-dev-0262 | reasoning | ranking |
| averitec-dev-0267 | reasoning | retrieval |
| averitec-dev-0281 | reasoning | ranking |
| averitec-dev-0283 | reasoning | retrieval |
| averitec-dev-0288 | reasoning | retrieval |
| averitec-dev-0327 | reasoning | retrieval |
| averitec-dev-0336 | reasoning | retrieval |
| averitec-dev-0368 | reasoning | retrieval |
| averitec-dev-0370 | reasoning | retrieval |
| averitec-dev-0394 | reasoning | retrieval |
| averitec-dev-0404 | reasoning | retrieval |
| averitec-dev-0406 | reasoning | ranking |
| averitec-dev-0418 | reasoning | retrieval |
| averitec-dev-0428 | reasoning | retrieval |
| averitec-dev-0443 | reasoning | retrieval |
| averitec-dev-0470 | reasoning | retrieval |
| averitec-dev-0478 | reasoning | retrieval |
| averitec-dev-0488 | reasoning | retrieval |
| averitec-dev-0489 | reasoning | retrieval |
| averitec-dev-0495 | reasoning | ranking |
| averitec-dev-0498 | reasoning | retrieval |

## Journalist effort

Over 100 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 47 | 47.0% [37.0, 57.0] |
| Confidently wrong (definitive, not gold) | 30 | 30.0% [21.0, 39.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 100 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 100 | 3.7 | 8.8 | 18.1 | 1.8% |
| Evidence retrieval | 100 | 36.0 | 62.6 | 93.7 | 16.3% |
| of which: the web search, every query | 100 | 3.7 | 8.4 | 22.4 | 1.9% |
| of which: the page fetches | 100 | 0.0 | 0.0 | 0.0 | 0.0% |
| Ranking | 100 | 23.3 | 43.3 | 57.5 | 10.9% |
| The model's verdict (with its wait for a permit) | 98 | 107.9 | 349.3 | 630.6 | 70.9% |
| of which: waiting for the model (another claim's call) | 98 | 23.1 | 147.2 | 306.4 | 23.1% |
| of which: the model's call itself | 98 | 82.8 | 228.3 | 324.0 | 47.8% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 100 | 169.2 | 453.8 | 705.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 471 (0) |
| Claims the model was not asked about | 2 |
| Prompt / completion tokens | 205711 / 15197 |
| Tokens per claim asked (prompt / completion) | 2099.1 / 155.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 17.348 / 53.452 / 124.093 |
| Claim latency, median / p90 (s) | 169.185 / 453.752 |
| Completion tokens per second | 1.3 |
| Cost | n/a (no price given, or tokens unknown) |

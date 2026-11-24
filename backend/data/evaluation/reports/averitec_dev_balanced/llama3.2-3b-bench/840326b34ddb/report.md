# averitec_dev_balanced · llama3.2:3b-bench · web-gate

Run `840326b34ddb` · provider `localhost:11434` · harness v1 · thresholds `3dc8629eb0b9` · corpus `none` (0 points)

Dataset sha256 `68a894e2c414`, 140 rows; 40 run, 100 not run. Commits: `0163ff2bf81a`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 40 of 140 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **27.5%** [15.0%, 42.5%] | **0.228** [0.113, 0.338] | 40 |
| Over the claims with a working search and model | 27.5% | 0.228 | 40 |
| Always answering Refuted | 25.0% | 0.100 | 40 |

F1 by class: Supported 0.320, Refuted 0.357, Not Enough Evidence 0.235, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 4 | 3 | 3 | 0 | 0 |
| Refuted | 5 | 5 | 0 | 0 | 0 |
| Not Enough Evidence | 3 | 5 | 2 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 3 | 5 | 2 | 0 | 0 |

### Nothing from after the claim

**Held**: no source given to the model is dated on or after its claim, by its address or its text, none is the claim's own fact-check, none is an undated fact-check, and none is a reference page as served today.

| | |
|---|---:|
| Sources given to the model | 135 |
| ... with a date before the claim | 135 |
| ... with no date (kept only under `evidence_undated: keep`) | 0 |
| ... with no date anywhere, address or text: nothing shows when these were written | 0 |
| Refused as published on or after the claim | 544 |
| Refused for a date in their text on or after the claim | 230 |
| Refused for having no date | 160 |
| Refused as a reference work rewritten since | 108 |
| Refused as an undated fact-check | 494 |
| Claims left with no evidence at all | 2 |

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
| Claims | 40 | 40 |
| Accuracy | 27.5% [15.0%, 42.5%] | 27.5% [15.0%, 42.5%] |
| Macro-F1 (gold classes) | 0.228 [0.113, 0.338] | 0.228 [0.113, 0.338] |
| Coverage (not UNVERIFIED) | 82.5% [70.0%, 92.5%] | 82.5% [70.0%, 92.5%] |
| Selective accuracy | 27.3% [12.5%, 42.9%] | 27.3% [12.5%, 42.9%] |
| Cohen's kappa vs gold | 0.033 [-0.128, 0.203] | 0.033 [-0.128, 0.203] |

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
| temporalLeak (cited source newer than the claim) | 0 | 30 | 10 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 40 | 0 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 26.7% | 40.0% | 0.320 | 10 | 15 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 10 | 0 |
| FALSE | 27.8% | 50.0% | 0.357 | 10 | 18 |
| UNVERIFIED | 28.6% | 20.0% | 0.235 | 10 | 7 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 4 | 0 | 0 | 3 | 3 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 3 | 0 | 0 | 5 | 2 |
| FALSE | 5 | 0 | 0 | 5 | 0 |
| UNVERIFIED | 3 | 0 | 0 | 5 | 2 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 40 | 27.5% [15.0%, 42.5%] | 0.228 | 82.5% | 27.3% |

## Retrieval

40 claims searched (39 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 1 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 7.7% [0.0%, 17.9%] (n=39) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=39) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=39) |
| Reference domain among candidates | 30.8% [17.9%, 46.2%] (n=39) |
| Reference domain among ranked evidence | 5.1% [0.0%, 12.8%] (n=39) |
| Reference domain among cited evidence | 2.6% [0.0%, 7.7%] (n=39) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=39) |
| Domain MRR (ranked) | 3.2% [0.0%, 9.0%] (n=39) |
| Claims with any ranked evidence | 95.0% [87.5%, 100.0%] (n=40) |
| Candidates per claim | 69.53 [65.00, 73.38] (n=40) |
| Ranked sources per claim | 3.38 [2.88, 3.85] (n=40) |
| Share cut at ranking (gate, cap) | 0.5% [0.0%, 1.6%] (n=38) |
| Distinct domains among ranked | 3.38 [2.88, 3.85] (n=40) |
| Ranked from rated domains | 11.1% [4.7%, 18.9%] (n=38) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=38) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 38.17 [33.63, 43.03] (n=40) |
| Ranking seconds per claim | 7.72 [6.20, 9.31] (n=40) |

Medians: 75.00 candidates, 4.00 ranked, 36.06 s retrieval, 5.73 s ranking; 2.98 queries per claim.

Ranked sources found by: proposition 91, anchor 43, refutation 7 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: rewritten continually: its date is not its text's (temporal cutoff): 1
- evidence_retrieval: its text states a date on or after the claim's (temporal cutoff): 1
- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| averitec | 40 | 39 | 0.0% | 5.1% | 95.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 40 | 39 | 0.0% | 5.1% | 95.0% |

## Stage attribution

29 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=29) | By reference (n=28) |
|---|---|---|
| retrieval | 0 (0.0%) | 17 (60.7%) |
| ranking | 1 (3.4%) | 9 (32.1%) |
| reasoning | 28 (96.6%) | 2 (7.1%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: ranking (averitec-dev-0290); reasoning (averitec-dev-0047, averitec-dev-0060, averitec-dev-0068, averitec-dev-0096, averitec-dev-0115, averitec-dev-0142, averitec-dev-0148, averitec-dev-0155, averitec-dev-0156, averitec-dev-0164, averitec-dev-0166, averitec-dev-0175, averitec-dev-0186, averitec-dev-0235, averitec-dev-0259, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0324, averitec-dev-0328, averitec-dev-0354, averitec-dev-0366, averitec-dev-0368, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0428, averitec-dev-0498).

Trace only, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: published on or after the claim's date (temporal cutoff): 22
- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 10
- evidence_retrieval: its text states a date on or after the claim's (temporal cutoff): 8
- evidence_retrieval: no date to show it predates the claim (temporal cutoff): 4
- evidence_retrieval: rewritten continually: its date is not its text's (temporal cutoff): 3
- evidence_retrieval: same domain as a higher-ranked source (tiktok.com): 2
- evidence_retrieval: cut by pre-rank funnel (rank 16 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 17 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 18 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 19 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 20 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 21 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 22 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 23 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 24 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 25 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 26 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 27 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 28 of 29, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 29 of 29, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (aol.com): 1
- evidence_retrieval: same domain as a higher-ranked source (sportingnews.com): 1
- evidence_retrieval: same domain as a higher-ranked source (linkedin.com): 1
- evidence_retrieval: same domain as a higher-ranked source (youtube.com): 1
- evidence_retrieval: same domain as a higher-ranked source (google.com): 1
- evidence_retrieval: same domain as a higher-ranked source (cambridge.org): 1

By reference: retrieval (averitec-dev-0047, averitec-dev-0068, averitec-dev-0115, averitec-dev-0155, averitec-dev-0156, averitec-dev-0166, averitec-dev-0175, averitec-dev-0235, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0328, averitec-dev-0366, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0428); ranking (averitec-dev-0142, averitec-dev-0164, averitec-dev-0186, averitec-dev-0259, averitec-dev-0290, averitec-dev-0324, averitec-dev-0354, averitec-dev-0368, averitec-dev-0498); reasoning (averitec-dev-0060, averitec-dev-0148).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (cdc.gov): 6
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 6
- evidence_retrieval: its text states a date on or after the claim's (temporal cutoff): 4
- evidence_retrieval: same domain as a higher-ranked source (opcw.org): 2
- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 2
- evidence_retrieval: same domain as a higher-ranked source (gov.ng): 1
- evidence_retrieval: cut by pre-rank funnel (rank 25 of 50, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 27 of 50, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 36 of 40, top 5 kept): 1

Without a reference link to judge by (1): averitec-dev-0096.

The two columns disagree on 25 of the 28 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0047 | reasoning | retrieval |
| averitec-dev-0068 | reasoning | retrieval |
| averitec-dev-0115 | reasoning | retrieval |
| averitec-dev-0142 | reasoning | ranking |
| averitec-dev-0155 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0164 | reasoning | ranking |
| averitec-dev-0166 | reasoning | retrieval |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0186 | reasoning | ranking |
| averitec-dev-0235 | reasoning | retrieval |
| averitec-dev-0259 | reasoning | ranking |
| averitec-dev-0283 | reasoning | retrieval |
| averitec-dev-0288 | reasoning | retrieval |
| averitec-dev-0306 | reasoning | retrieval |
| averitec-dev-0324 | reasoning | ranking |
| averitec-dev-0328 | reasoning | retrieval |
| averitec-dev-0354 | reasoning | ranking |
| averitec-dev-0366 | reasoning | retrieval |
| averitec-dev-0368 | reasoning | ranking |
| averitec-dev-0394 | reasoning | retrieval |
| averitec-dev-0404 | reasoning | retrieval |
| averitec-dev-0406 | reasoning | retrieval |
| averitec-dev-0428 | reasoning | retrieval |
| averitec-dev-0498 | reasoning | ranking |

## Journalist effort

Over 40 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 9 | 22.5% [10.0, 35.0] |
| Confidently wrong (definitive, not gold) | 24 | 60.0% [45.0, 75.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 40 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 40 | 0.4 | 2.8 | 7.1 | 1.5% |
| Evidence retrieval | 40 | 36.1 | 59.5 | 83.5 | 50.2% |
| of which: the web search, every query | 40 | 4.2 | 7.0 | 16.1 | 7.2% |
| of which: the page fetches | 40 | 2.9 | 12.2 | 21.0 | 6.9% |
| Ranking | 40 | 5.7 | 15.0 | 22.2 | 10.2% |
| The model's verdict (with its wait for a permit) | 37 | 29.4 | 56.0 | 70.6 | 38.1% |
| of which: waiting for the model (another claim's call) | 37 | 0.0 | 14.5 | 20.8 | 5.1% |
| of which: the model's call itself | 37 | 25.6 | 46.3 | 57.5 | 33.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 40 | 68.9 | 113.8 | 142.1 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 131 (0) |
| Claims the model was not asked about | 3 |
| Prompt / completion tokens | 54791 / 4293 |
| Tokens per claim asked (prompt / completion) | 1480.8 / 116.0 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 5.062 / 16.412 / 29.786 |
| Claim latency, median / p90 (s) | 68.936 / 113.831 |
| Completion tokens per second | 4.3 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`1ee9810b5fa1`, localhost:11434); candidate B: this run. Paired over the 40 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 25.0% | 27.5% | +2.5 pts | [-12.5 pts, +17.5 pts] |
| macroF1 | 0.228 | 0.228 | +0.000 | [-0.130, +0.138] |
| coverage | 82.5% | 82.5% | +0.0 pts | [-17.5 pts, +17.5 pts] |
| selectiveAccuracy | 18.2% | 27.3% | +9.1 pts | [-2.5 pts, +22.4 pts] |
| kappa | 0.000 | 0.033 | +0.033 | [-0.155, +0.235] |

Only A right: 4; only B right: 5. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 40 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 39 | 10.3% | 7.7% | -2.6 pts [-12.8 pts, +7.7 pts] | 3 / 2 |
| Reference link among ranked evidence | 39 | 5.1% | 0.0% | -5.1 pts [-12.8 pts, +0.0 pts] | 2 / 0 |
| Reference link among cited evidence | 39 | 5.1% | 0.0% | -5.1 pts [-12.8 pts, +0.0 pts] | 2 / 0 |
| Reference domain among candidates | 39 | 28.2% | 30.8% | +2.6 pts [-12.8 pts, +17.9 pts] | 4 / 5 |
| Reference domain among ranked evidence | 39 | 10.3% | 5.1% | -5.1 pts [-12.8 pts, +0.0 pts] | 2 / 0 |
| Reference domain among cited evidence | 39 | 7.7% | 2.6% | -5.1 pts [-12.8 pts, +0.0 pts] | 2 / 0 |
| Link MRR (ranked) | 39 | 2.6% | 0.0% | -2.6 pts [-6.4 pts, +0.0 pts] | 2 / 0 |
| Domain MRR (ranked) | 39 | 7.7% | 3.2% | -4.5 pts [-10.9 pts, +0.0 pts] | 3 / 0 |
| Claims with any ranked evidence | 40 | 100.0% | 95.0% | -5.0 pts [-12.5 pts, +0.0 pts] |  |
| Candidates per claim | 40 | 20.50 | 69.53 | +49.02 [+44.32, +53.02] |  |
| Ranked sources per claim | 40 | 4.83 | 3.38 | -1.45 [-1.98, -0.95] |  |
| Share cut at ranking (gate, cap) | 38 | 2.6% | 0.5% | -2.1 pts [-5.3 pts, +0.5 pts] |  |
| Distinct domains among ranked | 40 | 4.83 | 3.38 | -1.45 [-1.98, -0.95] |  |
| Ranked from rated domains | 38 | 4.7% | 11.1% | +6.4 pts [-1.6 pts, +15.0 pts] |  |
| Ranked from the internal corpus | 38 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 40 | 11.16 | 38.17 | +27.01 [+22.46, +31.55] |  |
| Ranking seconds per claim | 40 | 8.51 | 7.72 | -0.79 [-2.52, +0.93] |  |

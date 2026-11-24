# averitec_dev_balanced · qwen3.5:9b-bench · replayed evidence · replay-store

Run `556aa1250597` · provider `localhost:11434` · harness v1 · thresholds `d0deef88b2e7` · corpus `none` (0 points)

Dataset sha256 `68a894e2c414`, 140 rows; 20 run, 120 not run. Commits: `d8842946744c`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 20 of 140 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **25.0%** [10.0%, 45.0%] | **0.212** [0.056, 0.367] | 20 |
| Over the claims with a working search and model | 25.0% | 0.212 | 20 |
| Always answering Refuted | 25.0% | 0.100 | 20 |

F1 by class: Supported 0.364, Refuted 0.286, Not Enough Evidence 0.200, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 2 | 1 | 2 | 0 | 0 |
| Refuted | 1 | 2 | 2 | 0 | 0 |
| Not Enough Evidence | 2 | 2 | 1 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 1 | 4 | 0 | 0 | 0 |

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
| Accuracy | 25.0% [10.0%, 45.0%] | 25.0% [10.0%, 45.0%] |
| Macro-F1 (gold classes) | 0.212 [0.056, 0.367] | 0.212 [0.056, 0.367] |
| Coverage (not UNVERIFIED) | 75.0% [55.0%, 95.0%] | 75.0% [55.0%, 95.0%] |
| Selective accuracy | 26.7% [6.2%, 50.0%] | 26.7% [6.2%, 50.0%] |
| Cohen's kappa vs gold | 0.000 [-0.224, 0.249] | 0.000 [-0.224, 0.249] |

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
| temporalLeak (cited source newer than the claim) | 0 | 1 | 19 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 20 | 0 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 33.3% | 40.0% | 0.364 | 5 | 6 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 5 | 0 |
| FALSE | 22.2% | 40.0% | 0.286 | 5 | 9 |
| UNVERIFIED | 20.0% | 20.0% | 0.200 | 5 | 5 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 2 | 0 | 0 | 1 | 2 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 1 | 0 | 0 | 4 | 0 |
| FALSE | 1 | 0 | 0 | 2 | 2 |
| UNVERIFIED | 2 | 0 | 0 | 2 | 1 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 20 | 25.0% [10.0%, 45.0%] | 0.212 | 75.0% | 26.7% |

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
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=20) |
| Ranking seconds per claim | 8.47 [7.68, 9.28] (n=20) |

Medians: 20.50 candidates, 5.00 ranked, 0.00 s retrieval, 8.19 s ranking; 3.00 queries per claim.

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

15 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=15) | By reference (n=14) |
|---|---|---|
| retrieval | 0 (0.0%) | 11 (78.6%) |
| ranking | 0 (0.0%) | 3 (21.4%) |
| reasoning | 15 (100.0%) | 0 (0.0%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (averitec-dev-0026, averitec-dev-0047, averitec-dev-0096, averitec-dev-0115, averitec-dev-0156, averitec-dev-0175, averitec-dev-0186, averitec-dev-0243, averitec-dev-0259, averitec-dev-0281, averitec-dev-0288, averitec-dev-0368, averitec-dev-0404, averitec-dev-0428, averitec-dev-0498).

By reference: retrieval (averitec-dev-0026, averitec-dev-0047, averitec-dev-0115, averitec-dev-0156, averitec-dev-0175, averitec-dev-0186, averitec-dev-0288, averitec-dev-0368, averitec-dev-0404, averitec-dev-0428, averitec-dev-0498); ranking (averitec-dev-0243, averitec-dev-0259, averitec-dev-0281).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: cut by pre-rank funnel (rank 13 of 13, top 5 kept): 1
- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 1
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1

Without a reference link to judge by (1): averitec-dev-0096.

The two columns disagree on 14 of the 14 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0026 | reasoning | retrieval |
| averitec-dev-0047 | reasoning | retrieval |
| averitec-dev-0115 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0186 | reasoning | retrieval |
| averitec-dev-0243 | reasoning | ranking |
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
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 4 | 20.0% [5.0, 40.0] |
| Confidently wrong (definitive, not gold) | 11 | 55.0% [35.0, 75.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 20 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 20 | 0.4 | 0.6 | 1.0 | 0.3% |
| Evidence retrieval | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 20 | 1.5 | 2.1 | 3.4 | 1.2% |
| of which: the page fetches | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| Ranking | 20 | 8.2 | 10.6 | 13.1 | 6.6% |
| The model's verdict (with its wait for a permit) | 20 | 123.6 | 137.9 | 152.9 | 93.1% |
| of which: waiting for the model (another claim's call) | 20 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the model's call itself | 20 | 123.6 | 137.9 | 152.9 | 93.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 20 | 131.1 | 147.9 | 162.7 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 96 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 42383 / 3019 |
| Tokens per claim asked (prompt / completion) | 2119.2 / 150.9 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 25.425 / 32.270 / 38.575 |
| Claim latency, median / p90 (s) | 131.087 / 147.928 |
| Completion tokens per second | 1.3 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`1ee9810b5fa1`, localhost:11434); candidate B: this run. Paired over the 20 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 20.0% | 25.0% | +5.0 pts | [-10.0 pts, +20.0 pts] |
| macroF1 | 0.176 | 0.212 | +0.037 | [-0.086, +0.164] |
| coverage | 90.0% | 75.0% | -15.0 pts | [-35.0 pts, +5.0 pts] |
| selectiveAccuracy | 16.7% | 26.7% | +10.0 pts | [-9.4 pts, +30.8 pts] |
| kappa | -0.067 | 0.000 | +0.067 | [-0.162, +0.318] |

Only A right: 1; only B right: 2. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 20 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 19 | 10.5% | 10.5% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 19 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 19 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 19 | 26.3% | 26.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 19 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 19 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Link MRR (ranked) | 19 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 19 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 20 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 20 | 20.55 | 20.55 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 20 | 4.80 | 4.80 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 20 | 2.0% | 2.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 20 | 4.80 | 4.80 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 20 | 4.0% | 4.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 20 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 20 | 13.77 | 0.00 | -13.77 [-15.72, -11.86] |  |
| Ranking seconds per claim | 20 | 10.46 | 8.47 | -1.99 [-3.05, -0.98] |  |

# averitec_dev_balanced · openai/gpt-oss-120b · replayed evidence · replay-store

Run `f2980fd00e70` · provider `api.groq.com` · harness v1 · thresholds `d0deef88b2e7` · corpus `none` (0 points)

Dataset sha256 `68a894e2c414`, 140 rows; 40 run, 100 not run. Commits: `0163ff2bf81a`, `d8842946744c`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 40 of 140 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **45.0%** [30.0%, 60.0%] | **0.392** [0.255, 0.505] | 40 |
| Over the claims with a working search and model | 45.0% | 0.392 | 40 |
| Always answering Refuted | 25.0% | 0.100 | 40 |

F1 by class: Supported 0.588, Refuted 0.500, Not Enough Evidence 0.480, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 5 | 3 | 2 | 0 | 0 |
| Refuted | 0 | 7 | 3 | 0 | 0 |
| Not Enough Evidence | 1 | 3 | 6 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 1 | 5 | 4 | 0 | 0 |

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
| Accuracy | 45.0% [30.0%, 60.0%] | 44.7% [28.9%, 60.5%] |
| Macro-F1 (gold classes) | 0.392 [0.255, 0.505] | 0.392 [0.249, 0.505] |
| Coverage (not UNVERIFIED) | 62.5% [47.5%, 77.5%] | 60.5% [44.7%, 76.3%] |
| Selective accuracy | 48.0% [28.6%, 68.0%] | 47.8% [27.3%, 68.8%] |
| Cohen's kappa vs gold | 0.267 [0.079, 0.452] | 0.262 [0.071, 0.455] |

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
| temporalLeak (cited source newer than the claim) | 0 | 10 | 30 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 2 | 38 | 0 | averitec-dev-0324, averitec-dev-0481 |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 71.4% | 50.0% | 0.588 | 10 | 7 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 10 | 0 |
| FALSE | 38.9% | 70.0% | 0.500 | 10 | 18 |
| UNVERIFIED | 40.0% | 60.0% | 0.480 | 10 | 15 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 5 | 0 | 0 | 3 | 2 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 1 | 0 | 0 | 5 | 4 |
| FALSE | 0 | 0 | 0 | 7 | 3 |
| UNVERIFIED | 1 | 0 | 0 | 3 | 6 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 40 | 45.0% [30.0%, 60.0%] | 0.392 | 62.5% | 48.0% |

## Retrieval

40 claims searched (39 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 1 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 10.3% [2.6%, 20.5%] (n=39) |
| Reference link among ranked evidence | 5.1% [0.0%, 12.8%] (n=39) |
| Reference link among cited evidence | 5.1% [0.0%, 12.8%] (n=39) |
| Reference domain among candidates | 28.2% [15.4%, 43.6%] (n=39) |
| Reference domain among ranked evidence | 10.3% [2.6%, 20.5%] (n=39) |
| Reference domain among cited evidence | 10.3% [2.6%, 20.5%] (n=39) |
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
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=40) |
| Ranking seconds per claim | 8.38 [7.36, 9.55] (n=40) |

Medians: 22.00 candidates, 5.00 ranked, 0.00 s retrieval, 7.38 s ranking; 2.98 queries per claim.

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

22 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=22) | By reference (n=21) |
|---|---|---|
| retrieval | 0 (0.0%) | 16 (76.2%) |
| ranking | 0 (0.0%) | 2 (9.5%) |
| reasoning | 22 (100.0%) | 3 (14.3%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (averitec-dev-0026, averitec-dev-0047, averitec-dev-0060, averitec-dev-0096, averitec-dev-0115, averitec-dev-0148, averitec-dev-0156, averitec-dev-0175, averitec-dev-0186, averitec-dev-0235, averitec-dev-0259, averitec-dev-0280, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0324, averitec-dev-0366, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0463, averitec-dev-0498).

By reference: retrieval (averitec-dev-0026, averitec-dev-0047, averitec-dev-0115, averitec-dev-0156, averitec-dev-0175, averitec-dev-0186, averitec-dev-0235, averitec-dev-0280, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0366, averitec-dev-0394, averitec-dev-0404, averitec-dev-0463, averitec-dev-0498); ranking (averitec-dev-0259, averitec-dev-0406); reasoning (averitec-dev-0060, averitec-dev-0148, averitec-dev-0324).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: a fact-check with no date to show it predates the claim (temporal cutoff): 1
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 11, top 5 kept): 1

Without a reference link to judge by (1): averitec-dev-0096.

The two columns disagree on 18 of the 21 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0026 | reasoning | retrieval |
| averitec-dev-0047 | reasoning | retrieval |
| averitec-dev-0115 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0186 | reasoning | retrieval |
| averitec-dev-0235 | reasoning | retrieval |
| averitec-dev-0259 | reasoning | ranking |
| averitec-dev-0280 | reasoning | retrieval |
| averitec-dev-0283 | reasoning | retrieval |
| averitec-dev-0288 | reasoning | retrieval |
| averitec-dev-0306 | reasoning | retrieval |
| averitec-dev-0366 | reasoning | retrieval |
| averitec-dev-0394 | reasoning | retrieval |
| averitec-dev-0404 | reasoning | retrieval |
| averitec-dev-0406 | reasoning | ranking |
| averitec-dev-0463 | reasoning | retrieval |
| averitec-dev-0498 | reasoning | retrieval |

## Journalist effort

Over 40 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 11 | 27.5% [15.0, 42.5] |
| Confidently wrong (definitive, not gold) | 13 | 32.5% [17.5, 47.5] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 40 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 40 | 0.1 | 0.3 | 0.4 | 0.8% |
| Evidence retrieval | 40 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 40 | 1.2 | 2.1 | 3.4 | 10.3% |
| of which: the page fetches | 40 | 0.0 | 0.0 | 0.0 | 0.0% |
| Ranking | 40 | 7.4 | 12.4 | 20.5 | 60.5% |
| The model's verdict (with its wait for a permit) | 40 | 3.6 | 10.1 | 16.5 | 38.7% |
| of which: waiting for the model (another claim's call) | 40 | 0.0 | 6.2 | 12.0 | 11.5% |
| of which: the model's call itself | 40 | 3.2 | 5.9 | 10.5 | 27.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 40 | 12.8 | 20.0 | 25.1 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 218 (25) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 98345 / 19686 |
| Tokens per claim asked (prompt / completion) | 2458.6 / 492.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 0.590 / 1.499 / 5.766 |
| Claim latency, median / p90 (s) | 12.808 / 20.032 |
| Completion tokens per second | 133.5 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`1ee9810b5fa1`, localhost:11434); candidate B: this run. Paired over the 40 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 25.0% | 45.0% | +20.0 pts | [+5.0 pts, +35.0 pts] |
| macroF1 | 0.228 | 0.392 | +0.164 | [+0.021, +0.298] |
| coverage | 82.5% | 62.5% | -20.0 pts | [-37.5 pts, -2.5 pts] |
| selectiveAccuracy | 18.2% | 48.0% | +29.8 pts | [+8.8 pts, +50.1 pts] |
| kappa | 0.000 | 0.267 | +0.267 | [+0.043, +0.494] |

Only A right: 2; only B right: 10. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 40 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 39 | 10.3% | 10.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 39 | 5.1% | 5.1% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 39 | 5.1% | 5.1% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 39 | 28.2% | 28.2% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 39 | 10.3% | 10.3% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 39 | 7.7% | 10.3% | +2.6 pts [+0.0 pts, +7.7 pts] | 0 / 1 |
| Link MRR (ranked) | 39 | 2.6% | 2.6% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 39 | 7.7% | 7.7% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 40 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 40 | 20.50 | 20.50 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 40 | 4.83 | 4.83 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 40 | 2.5% | 2.5% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 40 | 4.83 | 4.83 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 40 | 5.0% | 5.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 40 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 40 | 11.16 | 0.00 | -11.16 [-12.53, -9.89] |  |
| Ranking seconds per claim | 40 | 8.51 | 8.38 | -0.13 [-0.68, +0.47] |  |

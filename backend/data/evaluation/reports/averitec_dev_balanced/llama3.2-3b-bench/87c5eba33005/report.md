# averitec_dev_balanced · llama3.2:3b-bench · web-gate

Run `87c5eba33005` · provider `localhost:11434` · harness v1 · thresholds `00ca480d889e` · corpus `none` (0 points)

Dataset sha256 `68a894e2c414`, 140 rows; 40 run, 100 not run. Commits: `0163ff2bf81a`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## AVeriTeC (the benchmark's own measure)

**Partial: 40 of 140 claims.** A fixed random sample (the rows are in hash order), so not comparable with a figure over the whole split.

Four classes; every claim counts, a claim with no verdict as wrong. Labels are the fact-checkers', reviewed by the dataset's annotators.

| | Accuracy | Macro-F1 | n |
|---|---:|---:|---:|
| **This run** | **30.0%** [17.5%, 45.0%] | **0.240** [0.126, 0.350] | 40 |
| Over the claims with a working search and model | 30.0% | 0.240 | 40 |
| Always answering Refuted | 25.0% | 0.100 | 40 |

F1 by class: Supported 0.222, Refuted 0.438, Not Enough Evidence 0.300, Conflicting Evidence/Cherrypicking 0.000.

Confusion (gold rows, predicted columns; `None` is no verdict):

| gold \ predicted | Supported | Refuted | Not Enough Evidence | Conflicting Evidence/Cherrypicking | None |
|---|---:|---:|---:|---:|---:|
| Supported | 2 | 5 | 3 | 0 | 0 |
| Refuted | 2 | 7 | 1 | 0 | 0 |
| Not Enough Evidence | 4 | 3 | 3 | 0 | 0 |
| Conflicting Evidence/Cherrypicking | 0 | 7 | 3 | 0 | 0 |

### Nothing from after the claim

**Held**: no source given to the model is dated on or after its claim, by its address or its text, none is the claim's own fact-check, none is an undated fact-check, and none is a reference page as served today.

| | |
|---|---:|
| Sources given to the model | 144 |
| ... with a date before the claim | 144 |
| ... with no date (kept only under `evidence_undated: keep`) | 0 |
| ... with no date anywhere, address or text: nothing shows when these were written | 0 |
| Refused as published on or after the claim | 496 |
| Refused for a date in their text on or after the claim | 202 |
| Refused for having no date | 165 |
| Refused as a reference work rewritten since | 102 |
| Refused as an undated fact-check | 67 |
| Claims left with no evidence at all | 1 |

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
| Accuracy | 30.0% [17.5%, 45.0%] | 30.0% [17.5%, 45.0%] |
| Macro-F1 (gold classes) | 0.240 [0.126, 0.350] | 0.240 [0.126, 0.350] |
| Coverage (not UNVERIFIED) | 75.0% [60.0%, 87.5%] | 75.0% [60.0%, 87.5%] |
| Selective accuracy | 30.0% [14.3%, 46.9%] | 30.0% [14.3%, 46.9%] |
| Cohen's kappa vs gold | 0.067 [-0.086, 0.231] | 0.067 [-0.086, 0.231] |

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
| temporalLeak (cited source newer than the claim) | 0 | 32 | 8 |  |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 40 | 0 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 25.0% | 20.0% | 0.222 | 10 | 8 |
| PARTIALLY_TRUE | n/a | n/a | n/a | 0 | 0 |
| MISLEADING | n/a | 0.0% | 0.000 | 10 | 0 |
| FALSE | 31.8% | 70.0% | 0.438 | 10 | 22 |
| UNVERIFIED | 30.0% | 30.0% | 0.300 | 10 | 10 |

Macro-F1 averages over the classes with gold support: TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 2 | 0 | 0 | 5 | 3 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 0 | 0 |
| MISLEADING | 0 | 0 | 0 | 7 | 3 |
| FALSE | 2 | 0 | 0 | 7 | 1 |
| UNVERIFIED | 4 | 0 | 0 | 3 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 40 | 30.0% [17.5%, 45.0%] | 0.240 | 75.0% | 30.0% |

## Retrieval

40 claims searched (39 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 1 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 7.7% [0.0%, 17.9%] (n=39) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=39) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=39) |
| Reference domain among candidates | 33.3% [17.9%, 48.7%] (n=39) |
| Reference domain among ranked evidence | 2.6% [0.0%, 7.7%] (n=39) |
| Reference domain among cited evidence | 2.6% [0.0%, 7.7%] (n=39) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=39) |
| Domain MRR (ranked) | 2.6% [0.0%, 7.7%] (n=39) |
| Claims with any ranked evidence | 97.5% [92.5%, 100.0%] (n=40) |
| Candidates per claim | 64.88 [59.95, 69.78] (n=40) |
| Ranked sources per claim | 3.60 [3.12, 4.05] (n=40) |
| Share cut at ranking (gate, cap) | 0.0% [0.0%, 0.0%] (n=39) |
| Distinct domains among ranked | 3.60 [3.12, 4.05] (n=40) |
| Ranked from rated domains | 7.7% [3.3%, 12.7%] (n=39) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=39) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 41.57 [37.44, 45.81] (n=40) |
| Ranking seconds per claim | 9.91 [8.17, 11.62] (n=40) |

Medians: 66.00 candidates, 4.00 ranked, 39.74 s retrieval, 9.94 s ranking; 3.00 queries per claim.

Ranked sources found by: question-1 61, question-2 50, anchor 32, question-3 13, specifics 4, proposition 2 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: rewritten continually: its date is not its text's (temporal cutoff): 1
- evidence_retrieval: published on or after the claim's date (temporal cutoff): 1
- evidence_retrieval: cut by pre-rank funnel (rank 11 of 50, top 5 kept): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| averitec | 40 | 39 | 0.0% | 2.6% | 97.5% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 40 | 39 | 0.0% | 2.6% | 97.5% |

## Stage attribution

28 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=28) | By reference (n=27) |
|---|---|---|
| retrieval | 0 (0.0%) | 19 (70.4%) |
| ranking | 1 (3.6%) | 7 (25.9%) |
| reasoning | 27 (96.4%) | 1 (3.7%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: ranking (averitec-dev-0290); reasoning (averitec-dev-0025, averitec-dev-0047, averitec-dev-0060, averitec-dev-0068, averitec-dev-0096, averitec-dev-0115, averitec-dev-0142, averitec-dev-0148, averitec-dev-0155, averitec-dev-0156, averitec-dev-0164, averitec-dev-0175, averitec-dev-0235, averitec-dev-0255, averitec-dev-0259, averitec-dev-0282, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0324, averitec-dev-0354, averitec-dev-0366, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0428, averitec-dev-0498).

Trace only, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: published on or after the claim's date (temporal cutoff): 23
- evidence_retrieval: its text states a date on or after the claim's (temporal cutoff): 12
- evidence_retrieval: no date to show it predates the claim (temporal cutoff): 4
- evidence_retrieval: same domain as a higher-ranked source (the-express.com): 3
- evidence_retrieval: same domain as a higher-ranked source (youtube.com): 3
- evidence_retrieval: rewritten continually: its date is not its text's (temporal cutoff): 3
- evidence_retrieval: same domain as a higher-ranked source (tiktok.com): 2
- evidence_retrieval: same domain as a higher-ranked source (aol.com): 2
- evidence_retrieval: cut by pre-rank funnel (rank 16 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 17 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 18 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 19 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 20 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 21 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 22 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 23 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 24 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 25 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 26 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 27 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 28 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 29 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 30 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 31 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 32 of 33, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 33 of 33, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (sportingnews.com): 1
- evidence_retrieval: same domain as a higher-ranked source (google.com): 1
- evidence_retrieval: same domain as a higher-ranked source (frontofficesports.com): 1
- evidence_retrieval: same domain as a higher-ranked source (heavy.com): 1
- evidence_retrieval: same domain as a higher-ranked source (essentiallysports.com): 1
- evidence_retrieval: the article being checked cannot corroborate itself: 1

By reference: retrieval (averitec-dev-0025, averitec-dev-0047, averitec-dev-0068, averitec-dev-0115, averitec-dev-0155, averitec-dev-0156, averitec-dev-0175, averitec-dev-0235, averitec-dev-0259, averitec-dev-0282, averitec-dev-0283, averitec-dev-0288, averitec-dev-0306, averitec-dev-0354, averitec-dev-0366, averitec-dev-0394, averitec-dev-0404, averitec-dev-0406, averitec-dev-0428); ranking (averitec-dev-0142, averitec-dev-0148, averitec-dev-0164, averitec-dev-0255, averitec-dev-0290, averitec-dev-0324, averitec-dev-0498); reasoning (averitec-dev-0060).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: published on or after the claim's date (temporal cutoff): 11
- evidence_retrieval: same domain as a higher-ranked source (cdc.gov): 4
- evidence_retrieval: same domain as a higher-ranked source (opcw.org): 1
- evidence_retrieval: its text states a date on or after the claim's (temporal cutoff): 1
- evidence_retrieval: cut by pre-rank funnel (rank 11 of 50, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 26 of 37, top 5 kept): 1

Without a reference link to judge by (1): averitec-dev-0096.

The two columns disagree on 25 of the 27 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| averitec-dev-0025 | reasoning | retrieval |
| averitec-dev-0047 | reasoning | retrieval |
| averitec-dev-0068 | reasoning | retrieval |
| averitec-dev-0115 | reasoning | retrieval |
| averitec-dev-0142 | reasoning | ranking |
| averitec-dev-0148 | reasoning | ranking |
| averitec-dev-0155 | reasoning | retrieval |
| averitec-dev-0156 | reasoning | retrieval |
| averitec-dev-0164 | reasoning | ranking |
| averitec-dev-0175 | reasoning | retrieval |
| averitec-dev-0235 | reasoning | retrieval |
| averitec-dev-0255 | reasoning | ranking |
| averitec-dev-0259 | reasoning | retrieval |
| averitec-dev-0282 | reasoning | retrieval |
| averitec-dev-0283 | reasoning | retrieval |
| averitec-dev-0288 | reasoning | retrieval |
| averitec-dev-0306 | reasoning | retrieval |
| averitec-dev-0324 | reasoning | ranking |
| averitec-dev-0354 | reasoning | retrieval |
| averitec-dev-0366 | reasoning | retrieval |
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
| Confidently wrong (definitive, not gold) | 21 | 52.5% [37.5, 67.5] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, a person's median minutes per fact (the labeller's `stats` printed it until it was removed on 2026-11-17).

## Response time

Seconds per stage over the 40 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 40 | 1.6 | 2.7 | 5.2 | 1.7% |
| Evidence retrieval | 40 | 39.7 | 59.5 | 69.4 | 44.5% |
| of which: the web search, every query | 40 | 3.1 | 6.8 | 13.1 | 4.2% |
| of which: the page fetches | 40 | 2.4 | 13.8 | 20.4 | 5.5% |
| Ranking | 40 | 9.9 | 16.7 | 18.9 | 10.6% |
| The model's verdict (with its wait for a permit) | 39 | 26.9 | 48.0 | 64.4 | 29.4% |
| of which: waiting for the model (another claim's call) | 39 | 0.0 | 14.5 | 24.1 | 4.3% |
| of which: the model's call itself | 39 | 22.9 | 39.1 | 61.8 | 25.1% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 40 | 93.9 | 126.3 | 133.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 184 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 74772 / 6466 |
| Tokens per claim asked (prompt / completion) | 1869.3 / 161.7 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 4.732 / 14.041 / 31.154 |
| Claim latency, median / p90 (s) | 93.902 / 126.340 |
| Completion tokens per second | 5.3 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b-bench` (`840326b34ddb`, localhost:11434); candidate B: this run. Paired over the 40 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 27.5% | 30.0% | +2.5 pts | [-10.0 pts, +15.0 pts] |
| macroF1 | 0.228 | 0.240 | +0.012 | [-0.103, +0.130] |
| coverage | 82.5% | 75.0% | -7.5 pts | [-25.0 pts, +10.0 pts] |
| selectiveAccuracy | 27.3% | 30.0% | +2.7 pts | [-9.6 pts, +15.4 pts] |
| kappa | 0.033 | 0.067 | +0.033 | [-0.128, +0.203] |

Only A right: 3; only B right: 4. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 40 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 39 | 7.7% | 7.7% | +0.0 pts [-10.3 pts, +10.3 pts] | 2 / 2 |
| Reference link among ranked evidence | 39 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 39 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 39 | 30.8% | 33.3% | +2.6 pts [-10.3 pts, +15.4 pts] | 3 / 4 |
| Reference domain among ranked evidence | 39 | 5.1% | 2.6% | -2.6 pts [-7.7 pts, +0.0 pts] | 1 / 0 |
| Reference domain among cited evidence | 39 | 2.6% | 2.6% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Link MRR (ranked) | 39 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 39 | 3.2% | 2.6% | -0.6 pts [-1.9 pts, +0.0 pts] | 1 / 0 |
| Claims with any ranked evidence | 40 | 95.0% | 97.5% | +2.5 pts [+0.0 pts, +7.5 pts] |  |
| Candidates per claim | 40 | 69.53 | 64.88 | -4.65 [-9.28, -0.20] |  |
| Ranked sources per claim | 40 | 3.38 | 3.60 | +0.23 [-0.28, +0.70] |  |
| Share cut at ranking (gate, cap) | 38 | 0.5% | 0.0% | -0.5 pts [-1.6 pts, +0.0 pts] |  |
| Distinct domains among ranked | 40 | 3.38 | 3.60 | +0.23 [-0.28, +0.70] |  |
| Ranked from rated domains | 38 | 11.1% | 6.6% | -4.6 pts [-11.7 pts, +2.0 pts] |  |
| Ranked from the internal corpus | 38 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 40 | 38.17 | 41.57 | +3.40 [-2.17, +8.86] |  |
| Ranking seconds per claim | 40 | 7.72 | 9.91 | +2.19 [-0.00, +4.26] |  |

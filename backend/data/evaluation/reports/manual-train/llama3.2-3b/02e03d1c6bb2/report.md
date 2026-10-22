# manual-train · llama3.2:3b · contest-2026-10-22-full

Run `02e03d1c6bb2` · provider `localhost:11434` · harness v1 · thresholds `fcc28fd1ec8c` · corpus `snapshot` (0 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `67a65c14a325`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 68 | 52 |
| Accuracy | 33.8% [23.5%, 45.6%] | 32.7% [21.2%, 46.2%] |
| Macro-F1 (gold classes) | 0.182 [0.122, 0.239] | 0.175 [0.108, 0.240] |
| Coverage (not UNVERIFIED) | 98.5% [95.6%, 100.0%] | 98.1% [94.2%, 100.0%] |
| Selective accuracy | 34.3% [23.5%, 45.6%] | 33.3% [21.2%, 46.2%] |
| Cohen's kappa vs gold | 0.075 [-0.016, 0.168] | 0.065 [-0.040, 0.169] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 1 | fact165 |
| scored | 68 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 16 | 36 | 16 | fact016, fact020, fact021, fact036, fact062, fact064, fact065, fact086, fact088, fact089, fact099, fact123, fact139, fact142, fact162, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 68 |  |

Ranked but uncited sources newer than the claim: 11 over 11 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 83.3% | 22.2% | 0.351 | 45 | 12 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 23.6% | 92.9% | 0.377 | 14 | 55 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 6 | 1 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 10 | 0 | 0 | 35 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 2 | 1 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 1 | 0 | 0 | 13 | 0 |
| UNVERIFIED | 1 | 0 | 0 | 5 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 31.9% [19.1%, 44.7%] | 0.169 | 97.9% | 32.6% |
| es | 21 | 38.1% [19.0%, 57.1%] | 0.213 | 100.0% | 38.1% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 70.0% [40.0%, 100.0%] | 0.697 | 100.0% | 70.0% |
| environment | 15 | 26.7% [6.7%, 53.3%] | 0.149 | 100.0% | 26.7% |
| health | 15 | 33.3% [13.3%, 60.0%] | 0.236 | 93.3% | 35.7% |
| science | 17 | 23.5% [5.9%, 47.1%] | 0.117 | 100.0% | 23.5% |
| society | 11 | 27.3% [0.0%, 54.5%] | 0.143 | 100.0% | 27.3% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 40.5% [24.3%, 56.8%] | 0.274 | 100.0% | 40.5% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 100.0% | 33.3% |
| numerical | 28 | 25.0% [10.7%, 42.9%] | 0.142 | 96.4% | 25.9% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| primary | 42 | 31.0% [16.7%, 45.2%] | 0.167 | 97.6% | 31.7% |
| reference_media | 25 | 40.0% [20.0%, 60.0%] | 0.215 | 100.0% | 40.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 14 | 92.9% [78.6%, 100.0%] | 0.963 | 100.0% | 92.9% |
| natural | 54 | 18.5% [9.3%, 29.6%] | 0.119 | 98.1% | 18.9% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 11.9% [4.5%, 19.4%] (n=67) |
| Reference link among ranked evidence | 6.0% [1.5%, 11.9%] (n=67) |
| Reference link among cited evidence | 4.5% [0.0%, 10.4%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 16.4% [7.5%, 25.4%] (n=67) |
| Reference domain among cited evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Link MRR (ranked) | 5.0% [0.5%, 10.4%] (n=67) |
| Domain MRR (ranked) | 12.2% [5.5%, 19.7%] (n=67) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=69) |
| Candidates per claim | 13.17 [12.70, 13.65] (n=69) |
| Ranked sources per claim | 2.96 [2.90, 3.00] (n=69) |
| Share cut at ranking (gate, cap) | 1.5% [0.0%, 3.4%] (n=69) |
| Distinct domains among ranked | 2.96 [2.90, 3.00] (n=69) |
| Ranked from rated domains | 7.2% [3.9%, 11.1%] (n=69) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=69) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 5.44 [4.61, 6.33] (n=69) |
| Ranking seconds per claim | 2.59 [1.01, 5.56] (n=69) |

Medians: 12.00 candidates, 3.00 ranked, 4.81 s retrieval, 0.80 s ranking; 2.00 queries per claim.

Ranked sources found by: proposition 150, anchor 90 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: cut by pre-rank funnel (rank 4 of 13, top 3 kept): 2
- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 6.0% | 16.4% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 6.5% | 15.2% | 100.0% |
| es | 21 | 21 | 4.8% | 19.1% | 100.0% |

## Stage attribution

45 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=45) | By reference (n=43) |
|---|---|---|
| retrieval | 0 (0.0%) | 31 (72.1%) |
| ranking | 0 (0.0%) | 4 (9.3%) |
| reasoning | 45 (100.0%) | 8 (18.6%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact008, fact009, fact010, fact011, fact015, fact016, fact020, fact021, fact037, fact049, fact062, fact064, fact066, fact081, fact082, fact085, fact086, fact088, fact099, fact100, fact101, fact106, fact107, fact114, fact117, fact118, fact122, fact123, fact124, fact125, fact126, fact127, fact128, fact129, fact132, fact133, fact138, fact139, fact140, fact141, fact143, fact144, fact145, fact146, fact163).

By reference: retrieval (fact008, fact009, fact015, fact016, fact020, fact021, fact037, fact062, fact064, fact066, fact081, fact100, fact101, fact107, fact114, fact118, fact122, fact123, fact124, fact125, fact127, fact128, fact132, fact133, fact138, fact140, fact141, fact143, fact144, fact145, fact146); ranking (fact010, fact082, fact126, fact163); reasoning (fact011, fact085, fact086, fact088, fact106, fact117, fact129, fact139).

By reference, why sources were cut on the claims attributed to ranking:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 4
- evidence_retrieval: cut by pre-rank funnel (rank 4 of 8, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 4 of 10, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 5 of 8, top 3 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 4 of 14, top 3 kept): 1

Without a reference link to judge by (2): fact049, fact099.

The two columns disagree on 35 of the 43 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact008 | reasoning | retrieval |
| fact009 | reasoning | retrieval |
| fact010 | reasoning | ranking |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |
| fact021 | reasoning | retrieval |
| fact037 | reasoning | retrieval |
| fact062 | reasoning | retrieval |
| fact064 | reasoning | retrieval |
| fact066 | reasoning | retrieval |
| fact081 | reasoning | retrieval |
| fact082 | reasoning | ranking |
| fact100 | reasoning | retrieval |
| fact101 | reasoning | retrieval |
| fact107 | reasoning | retrieval |
| fact114 | reasoning | retrieval |
| fact118 | reasoning | retrieval |
| fact122 | reasoning | retrieval |
| fact123 | reasoning | retrieval |
| fact124 | reasoning | retrieval |
| fact125 | reasoning | retrieval |
| fact126 | reasoning | ranking |
| fact127 | reasoning | retrieval |
| fact128 | reasoning | retrieval |
| fact132 | reasoning | retrieval |
| fact133 | reasoning | retrieval |
| fact138 | reasoning | retrieval |
| fact140 | reasoning | retrieval |
| fact141 | reasoning | retrieval |
| fact143 | reasoning | retrieval |
| fact144 | reasoning | retrieval |
| fact145 | reasoning | retrieval |
| fact146 | reasoning | retrieval |
| fact163 | reasoning | ranking |

## Journalist effort

Over 68 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 14 | 20.6% [11.8, 30.9] |
| Confidently wrong (definitive, not gold) | 44 | 64.7% [52.9, 76.5] |

Right and definitive but citing no source with a stance: 3 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 68 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 68 | 2.2 | 3.1 | 4.6 | 11.3% |
| Evidence retrieval | 68 | 4.8 | 9.5 | 15.1 | 30.5% |
| of which: the web search, every query | 68 | 1.2 | 2.0 | 3.5 | 7.0% |
| of which: the page fetches | 68 | 2.1 | 8.2 | 13.7 | 17.9% |
| Ranking | 68 | 0.8 | 2.7 | 4.8 | 6.6% |
| The model's verdict (with its wait for a permit) | 68 | 8.8 | 12.9 | 16.0 | 51.6% |
| of which: waiting for the model (another claim's call) | 68 | 0.5 | 4.8 | 8.5 | 9.0% |
| of which: the model's call itself | 68 | 7.4 | 9.2 | 11.5 | 42.5% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 68 | 16.7 | 24.1 | 30.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 68 (0) |
| Claims the model was not asked about | 1 |
| Prompt / completion tokens | 42387 / 3998 |
| Tokens per claim asked (prompt / completion) | 623.3 / 58.8 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 7.445 / 9.236 / 11.488 |
| Claim latency, median / p90 (s) | 16.732 / 24.331 |
| Completion tokens per second | 7.6 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`340a36ac8972`, localhost:11434); candidate B: this run. Paired over the 68 claims both scored; 1 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 50.0% | 33.8% | -16.2 pts | [-27.9 pts, -4.4 pts] |
| macroF1 | 0.261 | 0.182 | -0.079 | [-0.138, -0.023] |
| coverage | 98.5% | 98.5% | +0.0 pts | [-4.4 pts, +4.4 pts] |
| selectiveAccuracy | 50.7% | 34.3% | -16.4 pts | [-28.4 pts, -5.1 pts] |
| kappa | 0.159 | 0.075 | -0.084 | [-0.247, +0.075] |

Only A right: 14; only B right: 3. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 13.4% | 11.9% | -1.5 pts [-4.5 pts, +0.0 pts] | 1 / 0 |
| Reference link among ranked evidence | 67 | 9.0% | 6.0% | -3.0 pts [-9.0 pts, +3.0 pts] | 3 / 1 |
| Reference link among cited evidence | 67 | 9.0% | 4.5% | -4.5 pts [-11.9 pts, +1.5 pts] | 4 / 1 |
| Reference domain among candidates | 67 | 34.3% | 32.8% | -1.5 pts [-4.5 pts, +0.0 pts] | 1 / 0 |
| Reference domain among ranked evidence | 67 | 25.4% | 16.4% | -9.0 pts [-17.9 pts, -1.5 pts] | 7 / 1 |
| Reference domain among cited evidence | 67 | 17.9% | 10.4% | -7.5 pts [-17.9 pts, +1.5 pts] | 8 / 3 |
| Link MRR (ranked) | 67 | 8.2% | 5.0% | -3.2 pts [-8.2 pts, +0.5 pts] | 3 / 1 |
| Domain MRR (ranked) | 67 | 17.9% | 12.2% | -5.7 pts [-12.7 pts, +0.4 pts] | 8 / 5 |
| Claims with any ranked evidence | 69 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 17.86 | 13.17 | -4.68 [-5.30, -4.10] |  |
| Ranked sources per claim | 69 | 4.72 | 2.96 | -1.77 [-1.91, -1.58] |  |
| Share cut at ranking (gate, cap) | 69 | 4.0% | 1.5% | -2.5 pts [-4.9 pts, -0.3 pts] |  |
| Distinct domains among ranked | 69 | 4.72 | 2.96 | -1.77 [-1.91, -1.58] |  |
| Ranked from rated domains | 69 | 6.7% | 7.2% | +0.6 pts [-1.8 pts, +3.0 pts] |  |
| Ranked from the internal corpus | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 12.61 | 5.44 | -7.16 [-8.73, -5.75] |  |
| Ranking seconds per claim | 69 | 6.37 | 2.59 | -3.78 [-5.48, -0.76] |  |

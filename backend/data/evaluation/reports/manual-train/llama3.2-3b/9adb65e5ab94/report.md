# manual-train · llama3.2:3b · replayed evidence · verifier-2026-10-22

Run `9adb65e5ab94` · provider `localhost:11434` · harness v1 · thresholds `a16be0ae70b1` · corpus `snapshot` (1 points)

Dataset sha256 `b261d136c662`, 69 rows; 10 run, 59 not run. Commits: `d570ff7af980`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 10 | 5 |
| Accuracy | 30.0% [0.0%, 60.0%] | 40.0% [0.0%, 80.0%] |
| Macro-F1 (gold classes) | 0.200 [0.000, 0.296] | 0.571 [0.000, 0.889] |
| Coverage (not UNVERIFIED) | 90.0% [70.0%, 100.0%] | 80.0% [40.0%, 100.0%] |
| Selective accuracy | 33.3% [0.0%, 66.7%] | 50.0% [0.0%, 100.0%] |
| Cohen's kappa vs gold | 0.091 [-0.039, 0.250] | 0.000 [0.000, 0.000] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 10 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 5 | 2 | 3 | fact009, fact010, fact011, fact020, fact036 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 10 |  |

Ranked but uncited sources newer than the claim: 5 over 4 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 100.0% | 42.9% | 0.600 | 7 | 3 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 1 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 0.0% | n/a | n/a | 0 | 6 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 2 | 1 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 3 | 0 | 0 | 3 | 1 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 0 | 0 |
| UNVERIFIED | 0 | 0 | 0 | 2 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 6 | 33.3% [0.0%, 66.7%] | 0.500 | 83.3% | 40.0% |
| es | 4 | 25.0% [0.0%, 75.0%] | 0.333 | 100.0% | 25.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| environment | 2 | 50.0% [0.0%, 100.0%] | 0.667 | 100.0% | 50.0% |
| health | 2 | 50.0% [0.0%, 100.0%] | 0.667 | 50.0% | 100.0% |
| science | 2 | 50.0% [0.0%, 100.0%] | 0.500 | 100.0% | 50.0% |
| society | 4 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 2 | 0.0% [0.0%, 0.0%] | 0.000 | 50.0% | 0.0% |
| numerical | 8 | 37.5% [12.5%, 75.0%] | 0.250 | 100.0% | 37.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| primary | 7 | 28.6% [0.0%, 57.1%] | 0.286 | 85.7% | 33.3% |
| reference_media | 3 | 33.3% [0.0%, 100.0%] | 0.333 | 100.0% | 33.3% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| natural | 10 | 30.0% [0.0%, 60.0%] | 0.200 | 90.0% | 33.3% |

## Retrieval

10 claims searched (10 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 0.0% [0.0%, 0.0%] (n=10) |
| Reference link among ranked evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference link among cited evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference domain among candidates | 10.0% [0.0%, 30.0%] (n=10) |
| Reference domain among ranked evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Reference domain among cited evidence | 0.0% [0.0%, 0.0%] (n=10) |
| Link MRR (ranked) | 0.0% [0.0%, 0.0%] (n=10) |
| Domain MRR (ranked) | 0.0% [0.0%, 0.0%] (n=10) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=10) |
| Candidates per claim | 16.60 [13.00, 20.00] (n=10) |
| Ranked sources per claim | 3.80 [2.80, 4.80] (n=10) |
| Share cut at ranking (gate, cap) | 8.0% [0.0%, 20.0%] (n=10) |
| Distinct domains among ranked | 3.80 [2.80, 4.80] (n=10) |
| Ranked from rated domains | 8.0% [0.0%, 20.0%] (n=10) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=10) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 0.00 [0.00, 0.00] (n=10) |
| Ranking seconds per claim | 7.96 [6.37, 9.32] (n=10) |

Medians: 16.50 candidates, 5.00 ranked, 0.00 s retrieval, 8.86 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 29, anchor 14, refutation 14 (a source two queries found counts for both).

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 10 | 10 | 0.0% | 0.0% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 6 | 6 | 0.0% | 0.0% | 100.0% |
| es | 4 | 4 | 0.0% | 0.0% | 100.0% |

## Stage attribution

7 wrong verdict(s) among the scored claims, each given the stage that made it (docs/decisions/evaluation.md §Stage attribution): aggregation when the model's own verdict was gold, else the first of retrieval, ranking, reasoning. Claims set apart above are never attributed.

| Stage | Trace only (n=7) | By reference (n=7) |
|---|---|---|
| retrieval | 0 (0.0%) | 7 (100.0%) |
| ranking | 0 (0.0%) | 0 (0.0%) |
| reasoning | 7 (100.0%) | 0 (0.0%) |
| aggregation | 0 (0.0%) | 0 (0.0%) |

Trace only: reasoning (fact009, fact010, fact011, fact012, fact015, fact016, fact020).

By reference: retrieval (fact009, fact010, fact011, fact012, fact015, fact016, fact020).

The two columns disagree on 7 of the 7 claim(s) both can judge:

| Claim | Trace only | By reference |
|---|---|---|
| fact009 | reasoning | retrieval |
| fact010 | reasoning | retrieval |
| fact011 | reasoning | retrieval |
| fact012 | reasoning | retrieval |
| fact015 | reasoning | retrieval |
| fact016 | reasoning | retrieval |
| fact020 | reasoning | retrieval |

## Journalist effort

Over 10 scored claims (docs/decisions/evaluation.md §Journalist effort).

| | Claims | Share [95% CI] |
|---|---|---|
| Usable without re-checking (gold, definitive, a cited source with a stance, no leak flag) | 2 | 20.0% [0.0, 50.0] |
| Confidently wrong (definitive, not gold) | 6 | 60.0% [30.0, 90.0] |

Right and definitive but citing no source with a stance: 0 (not usable: a person must still look).

No effort estimate: pass `--minutes-per-fact`, the median `python labeller/app.py stats` prints.

## Response time

Seconds per stage over the 10 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine. **A replay**: retrieval was not run (0 s), and the web search and page rows are the replayed run's, said again with its events.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 10 | 2.2 | 3.4 | 10.4 | 5.9% |
| Evidence retrieval | 10 | 0.0 | 0.0 | 0.0 | 0.0% |
| of which: the web search, every query | 10 | 2.3 | 3.3 | 3.7 | 4.9% |
| of which: the page fetches | 10 | 2.7 | 4.8 | 6.7 | 5.4% |
| Ranking | 10 | 8.9 | 10.2 | 10.8 | 15.2% |
| The model's verdict (with its wait for a permit) | 10 | 44.0 | 56.0 | 78.9 | 79.0% |
| of which: waiting for the model (another claim's call) | 10 | 11.4 | 25.2 | 43.6 | 27.4% |
| of which: the model's call itself | 10 | 25.0 | 37.9 | 53.5 | 51.5% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 10 | 56.1 | 65.3 | 96.8 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 10 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 12218 / 1747 |
| Tokens per claim asked (prompt / completion) | 1221.8 / 174.7 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 25.023 / 37.927 / 53.488 |
| Claim latency, median / p90 (s) | 56.100 / 65.297 |
| Completion tokens per second | 6.5 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`2a4d7dde37b2`, localhost:11434); candidate B: this run. Paired over the 10 claims both scored; 0 set apart on either side, 59 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 30.0% | 30.0% | +0.0 pts | [+0.0 pts, +0.0 pts] |
| macroF1 | 0.200 | 0.200 | +0.000 | [+0.000, +0.000] |
| coverage | 90.0% | 90.0% | +0.0 pts | [+0.0 pts, +0.0 pts] |
| selectiveAccuracy | 33.3% | 33.3% | +0.0 pts | [+0.0 pts, +0.0 pts] |
| kappa | 0.091 | 0.091 | +0.000 | [+0.000, +0.000] |

Only A right: 0; only B right: 0. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 10 claims both searched (59 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 10 | 10.0% | 10.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Link MRR (ranked) | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 10 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 10 | 16.60 | 16.60 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 10 | 3.80 | 3.80 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 10 | 8.0% | 8.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 10 | 3.80 | 3.80 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 10 | 8.0% | 8.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 10 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 10 | 12.70 | 0.00 | -12.69 [-14.73, -10.92] |  |
| Ranking seconds per claim | 10 | 6.37 | 7.96 | +1.59 [+1.11, +2.06] |  |

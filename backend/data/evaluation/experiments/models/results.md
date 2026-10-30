# The model benchmark of 29 October: results

2026-10-29, `scripts/bench_models.sh all` (09:43 to 17:24), one model at a
time as `-bench` copies (10 threads, 16k context, thinking off), on the
dev laptop's CPU. Candidates and rules were agreed before any result was
read (`docs/decisions/evaluation.md`, "Choosing the models"). Discussion:
`docs/decisions/evaluation.md`, "The benchmark of 29 October". Logs:
`logs/`; the writing benchmark side by side: `writing-comparison.md`
(`.json`); the verifiers: `data/evaluation/reports/manual-train/models.md`
and each run's `report.md` beside it.

## Verifier: the first 20 train claims, replays of `cc053417c0cb`

The searched `llama3.2:3b-bench` baseline is 47.8% on all of train (63 of
69 with evidence); every candidate reads its evidence, so only the reading
differs. Per-source verifier, about 4.75 model calls a claim.

| Model | Run | Accuracy | vs the 3B on the same 20 [95% CI] | Coverage | Kappa | Median s a model call | Decision |
|---|---|---|---|---|---|---|---|
| `llama3.2:3b` | `cc053417c0cb` | 55.0% | | 80% | -0.01 | **7.2** | **kept** |
| `granite3.3:8b` | `91d96d61a714` | **60.0%** | +5.0 [-10.0, +20.0] | **95%** | **0.26** (+0.27 [+0.01, +0.49]) | 19.9 | not adopted; the one worth all 69 |
| `gemma4:e4b` | `62b4e6620665` | 45.0% | -10.0 [-35.0, +15.0] | 55% (-25 [-45, -10]) | 0.18 | 18.5 | not adopted |
| `qwen3.5:9b` | `b9f985189177` | 35.0% | -20.0 [-45.0, 0.0] | 65% | -0.00 | 28.2 | not adopted |

## Writer: one article, one draft each in en, es and ca

`scripts/try_writer_model.py`, the lithium-and-autism article.

| Model | Seconds en / es / ca | Sentences without a citation | Metadata | Findings | Decision |
|---|---|---|---|---|---|
| `qwen3.5:4b` | **149 / 224 / 209** | 0 / 3 / 0 | all | 52,706 "in no source": 8,842 + 43,864 from the source, added up | **kept** |
| `qwen3.5:9b` | 294 / 320 / 375 | 1 / 2 / 1 | all | 4 passages copied word for word (en) | not adopted |
| `gemma4:e4b` | 183 / failed / 198 | 0 / - / 2 | missing in ca | es unreachable after 156 s | not adopted |
| `qwen3:8b` | 347 / 651 / 458 | 5 / 11 / 8 | all | a 50 in no source (ca) | not adopted |

## Reviewer: the writing benchmark (36 texts), then the seeded drafts

| Model | Format (gate 95%) | Detection [95% CI] | vs the 3B [95% CI] | Defect named | Median s a text | Seeded defects found (of 5) | Corrections offered (of 2) | Seconds a review | Decision |
|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | **94%, fails** (34 of 36) | 95% [90, 100] | +15 [+7, +23] | 87% | 97.2 | **5** | 1 | 282 / 250 | replaced |
| `gemma4:e4b` | 100% | **95%** [90, 100] | **+15 [+7, +23]** | 80% | 79.2 | 3 | **2** | 265 / 195 | **adopted** |
| `granite3.3:8b` | 100% | 83% [75, 92] | +3 [-7, +12] | 57% | 64.7 | 2 | 1 | 222 / 292 | not adopted |
| `llama3.2:3b` | 100% | 80% [72, 88] | | 67% | 27.5 | 2 | 0 | 45 / 58 | baseline |
| `phi4-mini` | 100% | 77% [68, 85] | -3 [-12, +5] | 63% | **19.9** | 2 | 1 | 82 / 73 | not adopted |

`gemma4:e4b` missed the English spelling error (it's for its) and the
changed figure (3 million where [1] says 1.2); every model found the
claim judged FALSE stated as fact.

## What went wrong on the way

- `logs/baseline-llama3.2:3b-bench.log` holds only a Qdrant lock error:
  an earlier baseline (09:29) still held the run's vector store when
  `all` started. That earlier run finished at 10:25 and is the one
  replayed.
- `gemma4:e4b`'s Spanish draft: unreachable after 156 s, one attempt.
- One baseline call: Ollama 500, "token repeat limit reached".
- Groq (`scripts/bench_groq.sh`) was not run that day; two 3-claim smoke
  runs from 11:04 are under `runs/manual-train/` and are not results.

## Groq, 2026-10-30: a 5-claim smoke run

`scripts/bench_groq.sh "" 5`: the first 5 train claims, replays of
`cc053417c0cb` like every verifier above, on the free plan (one call at a
time; 13 rate limits waited out, no call lost, no error). Beside them,
the local candidates' answers on the same 5 claims, from their 20-claim
runs. Not a result: one claim is 20 points.

| Model | Where | Run | Right of 5 | Model s a claim (median) |
|---|---|---|---|---|
| `qwen/qwen3.8-27b` | Groq | `3dd99b7f3805` | **4** | **1.3** |
| `gemma4:e4b` | local | `62b4e6620665` | **4** | 118.2 |
| `openai/gpt-oss-120b` | Groq | `5c4b196910a4` | 3 | 3.0 |
| `openai/gpt-oss-20b` | Groq | `1c27e9536da1` | 3 | 2.5 |
| `llama3.2:3b` | local | `cc053417c0cb` | 3 | 45.7 |
| `granite3.3:8b` | local | `91d96d61a714` | 3 | 157.9 |
| `qwen3.5:9b` | local | `b9f985189177` | 2 | 160.8 |

Every model got the two TRUE claims (fact008, fact012) and none the
PARTIALLY_TRUE one (fact009: FALSE from all six candidates, TRUE from the
3B). fact010 (UNVERIFIED) separates them: both gpt-oss answered FALSE,
confidently wrong; qwen3.8-27b, gemma4, granite and the 3B held back.
fact011 (UNVERIFIED): the 3B said TRUE; gemma4 and the three Groq models
were right. Next: the same 20 claims as the table above, so the Groq rows
pair with the local ones (~35 min on the free plan's rate limit).

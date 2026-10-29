# Writing models compared: texts_en_es

36 texts (sha256 `daca2f8f0f3e`), corrector prompt `281022241263`. The rubric is docs/decisions/evaluation.md §Writing-model benchmark. Detection intervals: percentile 95% bootstrap over pairs, 10000 resamples, seed 2026.

## Rubric

| Model | Provider | Format compliance | Detection [95% CI] | Defect named | Off-target drift | Repeat range | Median s/text | Completion tok/text | Tok/s | Cost per 100 texts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `llama3.2:3b-bench` | localhost:11434 | 100% | 80% [72%, 88%] (30 pairs) | 67% | 11.3 | n/a | 27.5 | 333 | 10.5 | n/a |
| `qwen3.5:9b-bench` | localhost:11434 | 94% | 95% [90%, 100%] (30 pairs) | 87% | 12.6 | n/a | 97.2 | 422 | 3.4 | n/a |
| `granite3.3:8b-bench` | localhost:11434 | 100% | 83% [75%, 92%] (30 pairs) | 57% | 4.8 | n/a | 64.7 | 307 | 3.8 | n/a |
| `phi4-mini:bench` | localhost:11434 | 100% | 77% [68%, 85%] (30 pairs) | 63% | 4.9 | n/a | 19.9 | 192 | 9.1 | n/a |
| `gemma4:e4b-bench` | localhost:11434 | 100% | 95% [90%, 100%] (30 pairs) | 80% | 7.3 | n/a | 79.2 | 316 | 3.8 | n/a |

## Detection per metric (defect scored lower than its clean text)

| Model | grammar | factConsistency | seo | hallucinationIndex | style |
| --- | --- | --- | --- | --- | --- |
| `llama3.2:3b-bench` | 75% (drop 3.8) | 67% (drop 3.3) | 58% (drop 1.7) | 100% (drop 49.7) | 100% (drop 15.8) |
| `qwen3.5:9b-bench` | 100% (drop 37.7) | 75% (drop 7.5) | 100% (drop 20.0) | 100% (drop 80.0) | 100% (drop 61.8) |
| `granite3.3:8b-bench` | 100% (drop 5.8) | 58% (drop 3.3) | 75% (drop 5.0) | 100% (drop 29.2) | 83% (drop 12.5) |
| `phi4-mini:bench` | 92% (drop 8.2) | 58% (drop 1.7) | 58% (drop 1.7) | 100% (drop 17.0) | 75% (drop 5.0) |
| `gemma4:e4b-bench` | 100% (drop 8.3) | 75% (drop 16.7) | 100% (drop 10.0) | 100% (drop 63.0) | 100% (drop 42.5) |

## Clean texts: mean score per metric (calibration)

| Model | grammar | factConsistency | seo | hallucinationIndex | style |
| --- | --- | --- | --- | --- | --- |
| `llama3.2:3b-bench` | 92.5 | 97.5 | 80.0 | 83.0 | 87.5 |
| `qwen3.5:9b-bench` | 96.0 | 100.0 | 85.0 | 91.7 | 91.0 |
| `granite3.3:8b-bench` | 100.0 | 100.0 | 80.8 | 98.3 | 88.3 |
| `phi4-mini:bench` | 97.5 | 100.0 | 85.0 | 100.0 | 90.0 |
| `gemma4:e4b-bench` | 95.0 | 100.0 | 85.0 | 98.0 | 90.0 |

## Against the first run, paired over the pairs both scored

| Model | Baseline | Pairs | Detection B − A | 95% CI |
| --- | --- | --- | --- | --- |
| `qwen3.5:9b-bench` | `llama3.2:3b-bench` | 30 | +15 pts | [+7, +23] pts |
| `granite3.3:8b-bench` | `llama3.2:3b-bench` | 30 | +3 pts | [-7, +12] pts |
| `phi4-mini:bench` | `llama3.2:3b-bench` | 30 | -3 pts | [-12, +5] pts |
| `gemma4:e4b-bench` | `llama3.2:3b-bench` | 30 | +15 pts | [+7, +23] pts |

## Units

- `llama3.2:3b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `qwen3.5:9b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `granite3.3:8b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `phi4-mini:bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `gemma4:e4b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).

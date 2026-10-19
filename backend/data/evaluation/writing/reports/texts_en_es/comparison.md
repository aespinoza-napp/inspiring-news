# Writing models compared: texts_en_es

36 texts (sha256 `daca2f8f0f3e`), corrector prompt `281022241263`. The rubric is docs/decisions/evaluation.md §Writing-model benchmark. Detection intervals: percentile 95% bootstrap over pairs, 10000 resamples, seed 2026.

## Rubric

| Model | Provider | Format compliance | Detection [95% CI] | Defect named | Off-target drift | Repeat range | Median s/text | Completion tok/text | Tok/s | Cost per 100 texts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `llama3.2:3b` | host.docker.internal:11434 | 100% | 80% [72%, 88%] (30 pairs) | 67% | 11.8 | n/a | 28.1 | 337 | 11.8 | n/a |
| `qwen3.5:4b` | host.docker.internal:11434 | 80% | 93% [82%, 100%] (22 pairs) | 69% | 17.1 | n/a | 44.6 | 507 | 8.0 | n/a |

## Detection per metric (defect scored lower than its clean text)

| Model | grammar | factConsistency | seo | hallucinationIndex | style |
| --- | --- | --- | --- | --- | --- |
| `llama3.2:3b` | 83% (drop 5.8) | 67% (drop 3.3) | 67% (drop 3.3) | 92% (drop 46.3) | 92% (drop 18.3) |
| `qwen3.5:4b` | 100% (drop 23.0) | 70% (drop 16.0) | 100% (drop 31.0) | 100% (drop 56.0) | 100% (drop 67.5) |

## Clean texts: mean score per metric (calibration)

| Model | grammar | factConsistency | seo | hallucinationIndex | style |
| --- | --- | --- | --- | --- | --- |
| `llama3.2:3b` | 92.5 | 97.5 | 80.0 | 73.0 | 87.5 |
| `qwen3.5:4b` | 100.0 | 90.8 | 85.0 | 79.2 | 92.5 |

## Against the first run, paired over the pairs both scored

| Model | Baseline | Pairs | Detection B − A | 95% CI |
| --- | --- | --- | --- | --- |
| `qwen3.5:4b` | `llama3.2:3b` | 22 | +14 pts | [+2, +25] pts |

## Units

- `llama3.2:3b`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `qwen3.5:4b`: 35 of 36 ok, 1 unreachable, 0 errors, 1 repeat(s); 8 pairs unscorable (no usable score on one side).

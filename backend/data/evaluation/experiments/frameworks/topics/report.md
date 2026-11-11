# Topic classification: the frameworks side by side

Gold: data/evaluation/experiments/topics/20261020T093630Z/result.json (the annotator's topic per article). Each LLM reads the title and the first 3000 characters; the embedding classifier the whole body. 95% bootstrap intervals.

| Contender | n | Top-1 | Gold in top 3 | Top-1 group | Unusable | Median s / article | Tokens in / out |
|---|---|---|---|---|---|---|---|
| claude-headless-haiku | 56 | 0.73 [0.61, 0.84] | 0.93 [0.86, 0.98] | 0.86 [0.77, 0.95] | 0 | 2.9235 | 148,354 / 8,121 |
| claude-headless-sonnet | 56 | 0.77 [0.66, 0.88] | 0.96 [0.91, 1.00] | 0.89 [0.80, 0.96] | 0 | 2.646 | 147,178 / 1,256 |
| embedding | 56 | 0.66 [0.54, 0.79] | 0.88 [0.79, 0.95] | 0.82 [0.71, 0.91] | 0 | 4.7475 | - |
| llama3.2-3b-bench | 56 | 0.52 [0.38, 0.64] | 0.82 [0.71, 0.91] | 0.61 [0.48, 0.73] | 7 | 13.799 | 70,095 / 751 |
| qwen3.5-4b-bench | 56 | 0.64 [0.52, 0.77] | 0.96 [0.91, 1.00] | 0.80 [0.70, 0.91] | 1 | 24.252 | 69,790 / 758 |

Caveat: many of these topic labels came from an AI pass and none has been reviewed by a person; a Claude contender's agreement with them is not yet accuracy.

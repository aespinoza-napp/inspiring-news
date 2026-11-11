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

# Topics on a standard set: SIB-200

SIB-200 test, 204 sentences per language, the same sentences in English and Spanish, 7 topics. Trained contenders learn from the language's own 701 training sentences. Accuracy with a 95% bootstrap interval.

| Contender | en accuracy | en macro-F1 | es accuracy | es macro-F1 | Unusable | Median s / sentence | Train s | Tokens in / out (both) |
|---|---|---|---|---|---|---|---|---|
| claude-headless-haiku | 0.88 [0.83, 0.92] | 0.8585 | 0.88 [0.83, 0.93] | 0.8647 | 1 | 2.3625 / 2.0345 | - | 274,800 / 35,634 |
| embedding-logreg | 0.89 [0.85, 0.93] | 0.8815 | 0.91 [0.87, 0.95] | 0.8972 | 0 | 0.0995 / 0.1428 | 76.0981 | - |
| embedding-zeroshot | 0.75 [0.68, 0.80] | 0.7394 | 0.74 [0.68, 0.80] | 0.74 | 0 | 0.1014 / 0.1449 | - | - |
| tfidf-logreg | 0.74 [0.67, 0.80] | 0.688 | 0.72 [0.66, 0.78] | 0.6728 | 0 | 0.0003 / 0.0004 | 5.4903 | - |

# Entities on a standard set: CoNLL

A seeded sample (seed 2026) of 300 test sentences each from CoNLL-2003 (en) and CoNLL-2002 (es). Scored as each sentence's set of (type, name) against the annotators', PER/ORG/LOC only, names compared case- and spacing-blind; untyped counts a name found under any type. Micro-averaged.

| Contender | Lang | Precision | Recall | F1 | PER | ORG | LOC | Untyped F1 | Unusable | Median s / sentence | Tokens in / out |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-headless-haiku | en | 0.8257 | 0.8555 | **0.8404** | 0.967 | 0.7754 | 0.7961 | 0.9246 | 0 | 2.259 | 218,262 / 49,741 |
| claude-headless-haiku | es | 0.8868 | 0.8716 | **0.8791** | 0.9655 | 0.8469 | 0.8613 | 0.915 | 0 | 2.496 | 233,130 / 78,722 |
| gliner | en | 0.5024 | 0.7111 | **0.5888** | 0.7025 | 0.3689 | 0.688 | 0.7252 | 0 | 0.0839 | - |
| gliner | es | 0.7101 | 0.7546 | **0.7317** | 0.75 | 0.6735 | 0.7857 | 0.7798 | 0 | 0.1413 | - |
| spacy-sm | en | 0.6364 | 0.5372 | **0.5826** | 0.6054 | 0.3717 | 0.7596 | 0.7099 | 0 | 0.0027 | - |
| spacy-sm | es | 0.5994 | 0.6063 | **0.6028** | 0.6702 | 0.5304 | 0.617 | 0.8026 | 0 | 0.0043 | - |
| xlmr-ner | en | 0.8937 | 0.8916 | **0.8927** | 0.9158 | 0.8477 | 0.9161 | 0.9401 | 0 | 0.041 | - |
| xlmr-ner | es | 0.9059 | 0.9201 | **0.913** | 0.9748 | 0.894 | 0.8961 | 0.9596 | 0 | 0.0837 | - |

# Fact-checking: the verifier on the same evidence

AVeriTeC dev, the first 10 claims. Every replay reads the evidence the knowledge-store run kept; closed-book reads none (what the model already knows). Always answering FALSE gets 7 of 10 here.

| Run | Model | Mode | Right | Accuracy [95% CI] | UNVERIFIED | Median s / claim | Median model s | Tokens in / out |
|---|---|---|---|---|---|---|---|---|
| knowledge-store `49e4c76106c6` | llama3.2:3b-bench | full | 4/10 | 0.40 [0.10, 0.70] | 2 | 149.4752 | 73.449 | 21,304 / 1,545 |
| replay-store-ollama `6ecdeb9012dc` | llama3.2:3b-bench | replay | 4/10 | 0.40 [0.10, 0.70] | 2 | 70.8175 | 41.3825 | 21,304 / 1,545 |
| replay-store `6c8959f38dc4` | claude-headless:sonnet | replay | 5/10 | 0.50 [0.20, 0.80] | 3 | 37.5764 | 21.713 | 57,279 / 1,752 |
| closed-book `f04afdc96a6d` | claude-headless:sonnet | closed_book | 7/10 | 0.70 [0.40, 1.00] | 2 | 3.9683 | None | 8,774 / 1,614 |

| Claim | Gold | llama3.2:3b-bench full | llama3.2:3b-bench replay | claude-headless:sonnet replay | claude-headless:sonnet closed_book |
|---|---|---|---|---|---|
| averitec-dev-0243 | FALSE | FALSE | FALSE | FALSE | FALSE |
| averitec-dev-0164 | FALSE | TRUE | TRUE | UNVERIFIED | FALSE |
| averitec-dev-0072 | FALSE | FALSE | FALSE | FALSE | FALSE |
| averitec-dev-0096 | FALSE | TRUE | TRUE | FALSE | UNVERIFIED |
| averitec-dev-0175 | TRUE | FALSE | FALSE | FALSE | UNVERIFIED |
| averitec-dev-0404 | MISLEADING | UNVERIFIED | UNVERIFIED | FALSE | FALSE |
| averitec-dev-0368 | FALSE | TRUE | TRUE | UNVERIFIED | FALSE |
| averitec-dev-0012 | FALSE | UNVERIFIED | UNVERIFIED | FALSE | FALSE |
| averitec-dev-0290 | TRUE | TRUE | TRUE | TRUE | TRUE |
| averitec-dev-0379 | FALSE | FALSE | FALSE | UNVERIFIED | FALSE |

# Review: the corrector as editor over 36 planted-defect texts

36 texts (sha256 `daca2f8f0f3e`), corrector prompt `281022241263`. The rubric is docs/decisions/evaluation.md §Writing-model benchmark. Detection intervals: percentile 95% bootstrap over pairs, 10000 resamples, seed 2026.

## Rubric

| Model | Provider | Format compliance | Detection [95% CI] | Defect named | Off-target drift | Repeat range | Median s/text | Completion tok/text | Tok/s | Cost per 100 texts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `llama3.2:3b-bench` | localhost:11434 | 100% | 80% [72%, 88%] (30 pairs) | 67% | 11.3 | n/a | 27.5 | 333 | 10.5 | n/a |
| `gemma4:e4b-bench` | localhost:11434 | 100% | 95% [90%, 100%] (30 pairs) | 80% | 7.3 | n/a | 79.2 | 316 | 3.8 | n/a |
| `qwen3.5:9b-bench` | localhost:11434 | 94% | 95% [90%, 100%] (30 pairs) | 87% | 12.6 | n/a | 97.2 | 422 | 3.4 | n/a |
| `granite3.3:8b-bench` | localhost:11434 | 100% | 83% [75%, 92%] (30 pairs) | 57% | 4.8 | n/a | 64.7 | 307 | 3.8 | n/a |
| `phi4-mini:bench` | localhost:11434 | 100% | 77% [68%, 85%] (30 pairs) | 63% | 4.9 | n/a | 19.9 | 192 | 9.1 | n/a |
| `claude-headless:sonnet` | claude.ai subscription (claude -p) | 100% | 100% [100%, 100%] (30 pairs) | 100% | 16.3 | n/a | 10.4 | 1035 | 97.4 | n/a |

## Detection per metric (defect scored lower than its clean text)

| Model | grammar | factConsistency | seo | hallucinationIndex | style |
| --- | --- | --- | --- | --- | --- |
| `llama3.2:3b-bench` | 75% (drop 3.8) | 67% (drop 3.3) | 58% (drop 1.7) | 100% (drop 49.7) | 100% (drop 15.8) |
| `gemma4:e4b-bench` | 100% (drop 8.3) | 75% (drop 16.7) | 100% (drop 10.0) | 100% (drop 63.0) | 100% (drop 42.5) |
| `qwen3.5:9b-bench` | 100% (drop 37.7) | 75% (drop 7.5) | 100% (drop 20.0) | 100% (drop 80.0) | 100% (drop 61.8) |
| `granite3.3:8b-bench` | 100% (drop 5.8) | 58% (drop 3.3) | 75% (drop 5.0) | 100% (drop 29.2) | 83% (drop 12.5) |
| `phi4-mini:bench` | 92% (drop 8.2) | 58% (drop 1.7) | 58% (drop 1.7) | 100% (drop 17.0) | 75% (drop 5.0) |
| `claude-headless:sonnet` | 100% (drop 68.5) | 100% (drop 57.7) | 100% (drop 41.3) | 100% (drop 55.7) | 100% (drop 51.8) |

## Clean texts: mean score per metric (calibration)

| Model | grammar | factConsistency | seo | hallucinationIndex | style |
| --- | --- | --- | --- | --- | --- |
| `llama3.2:3b-bench` | 92.5 | 97.5 | 80.0 | 83.0 | 87.5 |
| `gemma4:e4b-bench` | 95.0 | 100.0 | 85.0 | 98.0 | 90.0 |
| `qwen3.5:9b-bench` | 96.0 | 100.0 | 85.0 | 91.7 | 91.0 |
| `granite3.3:8b-bench` | 100.0 | 100.0 | 80.8 | 98.3 | 88.3 |
| `phi4-mini:bench` | 97.5 | 100.0 | 85.0 | 100.0 | 90.0 |
| `claude-headless:sonnet` | 95.2 | 80.5 | 74.0 | 64.8 | 79.3 |

## Against the first run, paired over the pairs both scored

| Model | Baseline | Pairs | Detection B − A | 95% CI |
| --- | --- | --- | --- | --- |
| `gemma4:e4b-bench` | `llama3.2:3b-bench` | 30 | +15 pts | [+7, +23] pts |
| `qwen3.5:9b-bench` | `llama3.2:3b-bench` | 30 | +15 pts | [+7, +23] pts |
| `granite3.3:8b-bench` | `llama3.2:3b-bench` | 30 | +3 pts | [-7, +12] pts |
| `phi4-mini:bench` | `llama3.2:3b-bench` | 30 | -3 pts | [-12, +5] pts |
| `claude-headless:sonnet` | `llama3.2:3b-bench` | 30 | +20 pts | [+12, +28] pts |

## Units

- `llama3.2:3b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `gemma4:e4b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `qwen3.5:9b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `granite3.3:8b-bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `phi4-mini:bench`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).
- `claude-headless:sonnet`: 36 of 36 ok, 0 unreachable, 0 errors, 1 repeat(s); 0 pairs unscorable (no usable score on one side).


# Resources: what each model needs in order to be used

Measured 2026-11-11 on Intel(R) Core(TM) Ultra 7 165U, 14 threads, 65.3 GB RAM, no GPU used. Each local model in a process of its own: memory once loaded and at its peak over 100 sentences, above the bare interpreter; cores is CPU time over wall time while it worked. Ollama models: the file's size and the memory Ollama reports once loaded.

| Model | What it is | Runs on | Parameters | On disk | RAM loaded | RAM peak | Load s | Cores used |
|---|---|---|---|---|---|---|---|---|
| embedding (bge-m3) | BAAI/bge-m3 | this machine, CPU | 568 M | 4.6 GB | 710 MB | 2.1 GB | 6.9 | 10.5 |
| gliner | urchade/gliner_small-v2.1 | this machine, CPU | 153 M | 611 MB | 1.1 GB | 1.7 GB | 6.2 | 12.0 |
| xlmr-ner | Davlan/xlm-roberta-base-ner-hrl | this machine, CPU | 277 M | 1.1 GB | 735 MB | 1.1 GB | 4.5 | 12.0 |
| spacy-sm en | en_core_web_sm | this machine, CPU | n/a | 15 MB | 310 MB | 313 MB | 1.4 | 1.0 |
| spacy-sm es | es_core_news_sm | this machine, CPU | n/a | 16 MB | 320 MB | 323 MB | 1.2 | 1.0 |
| tfidf-logreg | trained here on SIB-200 (en) | this machine, CPU | 345,261 | 4 MB | 140 MB | 221 MB | 6.5 | 11.0 |
| llama3.2:3b-bench | llama 3.2B Q4_K_M | this machine, CPU | 3.2B | 2.0 GB | 4.1 GB | n/a | 4.0 | n/a |
| qwen3.5:4b-bench | qwen35 4.2B Q4_K_M | this machine, CPU | 4.2B | 3.3 GB | 3.7 GB | n/a | 4.1 | n/a |
| phi4-mini:bench | phi3 3.8B Q4_K_M | this machine, CPU | 3.8B | 2.5 GB | 4.8 GB | n/a | 5.1 | n/a |
| granite3.3:8b-bench | granite 8.2B Q4_K_M | this machine, CPU | 8.2B | 4.9 GB | 7.9 GB | n/a | 10.4 | n/a |
| gemma4:e4b-bench | gemma4 7.5B Q4_K_M | this machine, CPU | 7.5B | 6.6 GB | 2.1 GB | n/a | 9.8 | n/a |
| qwen3.5:9b-bench | qwen35 9.0B Q4_K_M | this machine, CPU | 9.0B | 6.6 GB | 6.7 GB | n/a | 9.1 | n/a |
| claude-headless:haiku | not published | Anthropic's servers, through the claude.ai subscription | n/a | n/a | n/a | n/a | n/a | n/a |
| claude-headless:sonnet | not published | Anthropic's servers, through the claude.ai subscription | n/a | n/a | n/a | n/a | n/a | n/a |

- The embedding model is shared: the topic classifiers (untrained and trained) and the pipeline's duplicate search all use the one loaded bge-m3; the trained classifier adds 7 x 1,024 weights to it. Its folder on disk holds several copies of the weights (about 2.3 GB is the one loaded).
- Claude needs nothing held locally and cannot be run without the network and a plan; its size is not published.
- An Ollama figure is Ollama's own report (`/api/ps`), not a measurement of the process; gemma4's is lower than its file, as reported.

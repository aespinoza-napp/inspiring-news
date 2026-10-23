# Laya: the pipeline's decisions as typed questions

Since 2026-10-23. The experiment's rule (written before any run) and
its results: `backend/data/evaluation/experiments/laya/rule.md` and
`results.md`.

## What it is and why it was tried

Laya (Convai Innovations, Apache-2.0, package `laya` 0.4.13) answers
typed questions about a text in one forward pass and generates nothing:
`choice` (one of named options, each scored at its own marker),
`score` (an ordered scale; the answer is the expected level) and `noul`
(a yes/no probability). Several of this pipeline's steps are exactly
that kind of question: is a candidate worth offering, which group is
an article about, is a sentence checkable, what does a source say about
a claim. Today an LLM call (seconds to minutes on a CPU) or an embedding
heuristic answers them. Laya answers in 0.2-0.4 s on the dev desktop's
CPU.

Its own documentation says the base checkpoints are "a fast base to
specialise, not a zero-shot decision engine", and measured here that is
true: untrained, it answered a source that plainly states a claim as
"supports" 0.48 against "unrelated" 0.52. Every decision is fine-tuned on
this project's labels.

## Where it runs

`inference/`, beside the other transformer models (invariant 13: the
backend never imports `torch`). `POST /decisions` takes a checkpoint name,
a state (or a list of them) and the questions; it knows nothing about
what they mean (`inference/src/decisions.py`). A checkpoint is a
built-in one (`english`, `multilingual`, `typed-decisions`, from the
Hugging Face repo) or the name of a fine-tuned folder under
`DECISION_CHECKPOINTS_DIR` (`inference/checkpoints/`, gitignored, 1.3 GB
each). A name is never a path. It loads on the first request that names
it (~20 s), and at most `DECISION_MAX_LOADED` are held, least recently
used out. Not behind `/healthz`'s warm-up: it needs none of the three
models that does.

The backend reaches it through `InferenceClient.decide` / `decide_many`.
Any failure raises `InferenceUnavailable`, as sentiment and embeddings
do: an empty decision would be read as an answer.

**The questions live in one place**, `backend/src/config/decisions.py`.
A fine-tuned checkpoint has learnt those exact option names and
descriptions, so editing a word there changes what a trained checkpoint
is being asked. Training and the pipeline both read them from that file.

## Training

```bash
cd backend && uv run python -m src.evaluation.decisions build   # the JSONL sets
./scripts/laya_train_all.sh [decision ...]                      # train, answer the test set, score
```

The settings are the rule's: multilingual base (mmBERT, 1,024 tokens,
English and Spanish), RLCD loss, 8 epochs, micro-batch 8 × accumulation 2,
seed 0, CPU. That gives 64-168 optimizer updates on these few hundred
items. Laya's issue #963 saw training collapse at about 20. A decision
took 15-35 minutes to train on the i9-10900 and used ~7.6 GB of RAM:
do not run it beside a timed evaluation.

## What was measured (2026-10-23)

Each decision was tested against what the pipeline already does, on a
test set it never trained on, with a paired bootstrap. Adopted only if the
interval is above zero.

| Decision | Comparator | Laya fine-tuned | Difference [95% CI] | Adopted |
|---|---|---|---|---|
| D1 worth offering (AUC, clearly positive) | 3B AI selection 0.782 | 0.805 | +0.023 [-0.138, +0.176] | no |
| D1, worth offering at all | 0.686 | 0.826 | +0.140 [+0.028, +0.249] | not the primary |
| D2 topic group (accuracy) | bge-m3 classifier 0.824 | 0.824 | 0 [-0.137, +0.137] | no |
| D3 checkable claim (AUC) | the selector's score 0.490 | 0.584 | +0.094 [-0.102, +0.274] | no |

**Nothing became a default.** What exists:

- **D1 as an option on the AI selection**: `POST
  /ingest/rounds/{id}/ai-selection` with `"scorer": "laya"`
  (`backend/src/services/selection/laya_selector.py`). It ties the LLM
  in milliseconds instead of minutes, and needs `inference/` running with
  the `worth_offering` checkpoint. Known blind spot: it called a drug
  trial that cut hospitalisations "not worth offering" at 98%, likely
  because of the question's "product news" criterion.
- **D2 and D3 are trained but not wired.** D2 ties a classifier that
  runs anyway. D3 is not significant.

Every label behind D1-D3 is Claude's (the AI pass's), never checked by a
person: the models learn the AI's judgement and are scored against it.

## Not done yet

- **D4, the source's stance** (supports / contradicts / silent /
  unrelated), the decision that would replace the per-source verifier's
  LLM call per source. Its teacher is the 9B's stances on the train
  half's evidence, and both run folders are on the Windows desktop.
  If it holds up on a replay of the test half, it is the one that
  matters for the 20-second fact-check.
- **Not trained at all**: the verdict itself (69 train claims are too
  few), the pertinence gate (its pages are not judged yet), and the
  weights.
- **Production**: the checkpoints are not in any image. Serving one
  needs a volume mounted at `DECISION_CHECKPOINTS_DIR`.

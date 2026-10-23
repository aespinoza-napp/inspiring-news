# Laya for the pipeline's decisions: the experiment's rule

Written 2026-10-23, the author's request ("a final implementation based
on Laya ... train all the decision models"), before any Laya run on this
project's data. Only a smoke test was run first: one call on an invented
claim, and a fine-tune of 58 invented tickets, to time this CPU.

## What Laya is

An open model (Apache-2.0, `convaiinnovations/laya`, package `laya`
0.4.13) that answers typed questions about a text in one forward pass and
generates nothing: `choice` (one of named options), `score` (an ordered
scale) and `noul` (a yes/no probability). Every option is scored at its
own marker and softmaxed, so a new question needs no new head. It is
fine-tuned from labelled JSONL with `laya-train` (RLCD: a proper-scoring-
rule policy gradient plus a soft cross-entropy), and a run fits one
calibration temperature per question type on a slice it held out.

Measured here, 2026-10-23, on this machine's CPU (14 threads, no GPU):
the multilingual checkpoint answers two questions in ~340 ms; a
fine-tune of 58 short items takes ~25 s an epoch. The verifier's LLM call
for one source takes seconds to tens of seconds.

## Where it runs

Laya needs `torch`, so it lives in `inference/` (invariant 13: the
backend never imports it). `inference/` gains a decision endpoint that
takes a checkpoint name, a state and questions; it knows nothing about
what the questions mean. The questions, the thresholds and what an
answer does are the backend's.

## The base checkpoint

`multilingual` (mmBERT-base, 322M, 1,024 tokens): the claims and articles
are English and Spanish. Chosen before any run; the English checkpoint is
not tried.

## The decisions, their data and their rule

Every label below is **Claude's (AI)**, except the gold verdicts of the 31
hand-labelled facts; none of the candidate labels has been checked by a
person. A model trained on them learns the AI pass's judgement, and is
scored against it.

Each decision has a test set fixed here, never trained on, and a
comparator already in the pipeline, scored on the same items. A Laya
model is **adopted** (its switch made the default) only if the paired
difference against the comparator has a 95% bootstrap interval above zero
on the primary metric; otherwise the comparator stays and the result is
reported. One seed is run; a model that stays at the class prior is run
with two more seeds before it is called unlearnable (Laya's own advice,
`docs/finetune.md`, #963).

### D1. Is a candidate worth offering? (selection)

- **Question**: `score` over three levels, the labels' own scale: not
  worth offering, worth offering, clearly positive. State: the
  candidate's title and summary.
- **Train**: `alignment/20261009T120000Z/labelled.json` (324) and
  `emphasis/reserve-labels.json` (60), 2026-10-09 and 10-13.
- **Test**: `ranking/20261006T133348Z/result.json` (117), 2026-10-06: a
  different day's rounds. A URL in both is dropped from train.
- **Primary metric**: AUC of the expected level for "clearly positive"
  against the rest, the ranking experiment's own metric.
- **Comparator**: the 3B AI selection's score on the same 117 (`ai`,
  AUC 0.65 in that report). Reported beside it: the ranking's story score
  (0.78).
- **Adopted means**: the AI selection on `/discover` scores with Laya
  instead of the LLM (one call per candidate, milliseconds, no LLM).

### D2. Which topic group is an article about? (admission, rounds)

- **Question**: `choice` over the five groups (society, science,
  culture, health, environment), each described by its topics.
- **Train**: the 384 D1 candidates, the target spread evenly over the
  groups each `belongsTo` names (a `gold` distribution).
- **Test**: the topic experiment's articles (`topics/20261020T093630Z`)
  that have a title and claims in the labelling queue: 51 of 58. State:
  the title and the article's proposed claims.
- **Primary metric**: group accuracy.
- **Comparator**: the bge-m3 topic classifier's group on the same 51
  articles (`topGroup` in that result). It read the whole article; Laya
  reads the title and a few sentences. Stated, not corrected.
- **Adopted means**: a per-run switch for the classifier's group; the
  23 topics stay the classifier's.

### D3. Is a proposed sentence a checkable claim? (claim selection)

- **Question**: `noul`, "this sentence states a verifiable fact" -
  labelled = true, skipped (opinion, fragment, trivial, prediction,
  duplicate, other) = false. State: the article's title and the sentence.
- **Train**: the labelling queue's batches of 2026-09-29 to 10-06.
- **Test**: the batches of 2026-10-09, 10-13 and 10-14.
- **Primary metric**: AUC of P(true).
- **Comparator**: the claim selector's own `score` on the same sentences.
- **Adopted means**: proposed claims below a threshold fitted on train
  are not checked (the selector keeps two to four).

### D4. What does a source say about a claim? (the verifier's stance)

- **Question**: `choice` over supports / contradicts / silent /
  unrelated, the per-source verifier's own stances and definitions.
  State: the claim (with its article's subject) and the source's 700
  characters about it.
- **Train**: the train half's evidence (`2a4d7dde37b2`'s
  `evidence.jsonl`) with the 9B's per-source stances as the teacher
  (V5, `854f7aa29f3a`): Laya's own recipe trains on a teacher's
  distribution.
- **Test**: a replay of the test half's evidence (`66034c5fea72`) with
  Laya reading the stances and the same majority rule, against V2b
  (`e7231c962477`) and V5 on the same evidence, by the verifier
  experiment's rule (`../verifier/rule.md`): accuracy, right when it
  commits, confidently wrong, altered claims caught.
- **Blocked**: both run folders are on the Windows desktop
  (`runs/` is gitignored). Nothing of D4 is run until they are here.

## The training settings

Fixed after the zero-shot predictions (`results.md`) and before any
fine-tune, the same for D1-D3: `laya-train --base multilingual --loss
rlcd --epochs 8 --micro-batch 8 --grad-accum 2 --seed 0 --device cpu`
(effective batch 16: ~150-180 optimizer updates on these few hundred
items, where Laya's 4 epochs at 64 would give ~20, the budget its #963
saw collapse), `--shuffle-options` for D2's choice. Laya holds out its
own calibration slice (10%) from the training file; the test files are
never given to it. The fine-tuned checkpoint is answered with
`inference/`'s `python -m src.decisions predict` and scored with
`python -m src.evaluation.decisions score`.

## Not trained

- The verdict itself stays the majority of the per-source stances: 69
  train claims are too few to learn five verdicts from.
- The pertinence gate: its 603 pooled pages are not judged yet.
- The ranking weights and the confidence weights: not decisions of this
  kind; they wait on the checked labels (P2).

## Where the results go

`results.md` beside this file, then `docs/decisions/laya.md`,
`docs/fact-checking-changes.md` (D3, D4), `docs/roadmap.md` and the
build-status page.

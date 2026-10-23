# Laya for the pipeline's decisions: results

By the rule in `rule.md`. Predictions in `predictions/` (one line per test
item: Laya's answers, the comparator's, the seconds); scored with
`uv run python -m src.evaluation.decisions score --decision <d>
--predictions <file>`. Paired 95% bootstrap intervals, 2,000 resamples,
seed 20261005. This machine's CPU (14 threads, no GPU).

## Zero-shot: the multilingual checkpoint untrained (2026-10-23)

| Decision | Test items | Comparator | Laya | Laya - comparator [95% CI] | Laya, median a call |
|---|---|---|---|---|---|
| D1 worth offering: AUC, clearly positive vs rest | 117 | 3B AI selection 0.782 | 0.650 | -0.132 [-0.286, +0.016] | 0.19 s |
| D1, AUC worth offering (1-2) vs not | 117 | 0.686 | 0.738 | +0.052 [-0.079, +0.171] | |
| D2 topic group: accuracy | 51 | bge-m3 classifier 0.824 | 0.451 | -0.373 [-0.510, -0.216] | 0.33 s |
| D3 checkable claim: AUC | 78 | the selector's score 0.490 | 0.612 | +0.122 [-0.068, +0.316] | 0.18 s |

The story's own reading (the ranking's score) on D1: AUC 0.794 [0.669,
0.898].

- The rule quoted the 3B AI selection's AUC as 0.65 from the ranking
  report; scored here on the same 117 candidates against "clearly
  positive" it is 0.782 (0.686 against "worth offering"). The rule's
  comparator is the measured value.
- Untrained, Laya is what its own documentation says it is: "a fast base
  to specialise, not a zero-shot decision engine". Asked whether a source
  that plainly states a claim supports it or is unrelated, it answered
  0.48 against 0.52 (`inference/tests/test_decisions.py`).
- D3's comparator is at chance (0.49): the selector's score ranks how
  load-bearing a sentence is, not whether it is checkable.

## Fine-tuned (2026-10-23)

`scripts/laya_train_all.sh`, the rule's settings, seed 0, one run each;
~35, ~30 and ~15 minutes of training on this CPU. Checkpoints in
`inference/checkpoints/<decision>/` (1.3 GB each, gitignored).

| Decision | Test items | Comparator | Laya fine-tuned | Laya - comparator [95% CI] | Adopted | Laya, median a call |
|---|---|---|---|---|---|---|
| D1 worth offering: AUC, clearly positive vs rest | 117 | 3B AI selection 0.782 | 0.805 | +0.023 [-0.138, +0.176] | no | 0.22 s |
| D1, AUC worth offering (1-2) vs not | 117 | 0.686 | 0.826 | **+0.140 [+0.028, +0.249]** | (not the primary) | |
| D2 topic group: accuracy | 51 | bge-m3 classifier 0.824 | 0.824 | 0.000 [-0.137, +0.137] | no | 0.35 s |
| D3 checkable claim: AUC | 78 | the selector's score 0.490 | 0.584 | +0.094 [-0.102, +0.274] | no | 0.36 s |

**Nothing is adopted.** By the rule, every comparator stays the default.

- **D1.** On the primary metric (is it clearly positive?) the fine-tuned
  model ties the 3B AI selection, at 0.2 s per candidate where the 3B
  takes minutes per round on a CPU. On whether a candidate is worth
  offering at all it is better, with an interval above zero, but that
  metric is not the one the rule named. So it is offered as an option on
  the AI selection (`scorer: "laya"`), and is not the default. Fine-tuning
  moved the primary metric from 0.650 to 0.805.
- **D1, by hand, live through `inference/`** (invented candidates, not
  a measurement): a reforestation story at 1.98 of 2 and a stock-market
  fall, a stabbing at 0.02 - but a drug cutting heart-failure
  hospitalisations by 40% (in English and in Spanish) at 0.03, "not
  worth offering" at 98%, and a football result at 0.99, split between 0
  and 2. Its blind spot is likely the question's own "product news"
  criterion together with few medical positives among the 384 training
  labels. One more reason it stays an option.
- **D2.** It ties the classifier exactly: 42 of 51 each, from the title and the
  proposed claims alone. The two are wrong on different articles (6 that
  only Laya gets right, 6 only the classifier), a hint that combining them
  could help. That would be a new rule, not this one. Not wired: the classifier
  already runs for the 23 topics, so a second model that ties it adds a
  call and no accuracy.
- **D3.** Still not significant. Fine-tuning made it worse than zero-shot
  (0.612). The test set is 78 sentences (46 kept); the training set was 123,
  which was 64 optimizer updates, the fewest of the three. Not wired.
- **No model collapsed to the class prior.** Each spreads its answers (D1
  0.01 to 1.98 on the 0-2 scale; D3 0.03 to 0.998; D2 picks all five groups in
  the test set's own proportions). So by the rule no extra seeds were run.
- **Calibration.** Every run's fitted temperature landed on Laya's
  upper clamp (5) on a calibration slice of 13-36 items. The probabilities
  are over-confident even after it. Use them to rank, not as
  probabilities.
- **D4 (the source's stance)** is not trained yet. Its data is on the Windows desktop.

## The topic group, bge-m3 against Laya, in detail (2026-10-23)

`uv run python -m src.evaluation.decisions compare-topics`
(`predictions/topic_group_comparison.json`). The same 51 articles. The
topic classifier is bge-m3 embeddings against the 23 topics' descriptions
and keywords, reading the whole article. GLiNER takes no part in it. Laya
reads the title and the proposed claims. The gold groups are mostly the
AI labelling pass's.

| | bge-m3 | Laya untrained | Laya fine-tuned |
|---|---|---|---|
| Accuracy | 42 (0.824) | 23 (0.451) | 42 (0.824) |
| vs bge-m3 [95% CI] | | -0.373 [-0.510, -0.216] | 0.000 [-0.137, +0.137] |
| society (8) | 4 | 2 | 4 |
| science (12) | 12 | 12 | 11 |
| environment (13) | 11 | 1 | 11 |
| culture (5) | 3 | 2 | 3 |
| health (13) | 12 | 6 | **13** |
| English (37) | **30** | 14 | 28 |
| Spanish (14) | 12 | 9 | **14** |

- **Untrained, Laya calls almost everything science.** That covers 11 of
  13 environment and 7 of 13 health articles.
- **Fine-tuned, it ties bge-m3 but is not the same model.** They agree on
  38 articles (36 of them right). Of the 13 where they disagree, each is
  right alone on 6, and both are wrong on 3. Either one is right on 48
  of 51. Exact McNemar p = 1.0.
- **Where each is better.** Laya gets every Spanish article right (14 of
  14 against 12) and every health article (13 of 13). bge-m3 is better in
  English (30 against 28). Society is the weak group for both (4 of 8).
- **Laya's right-alone cases**: environment that bge-m3 read as science
  (permafrost drones, the Sycamore Gap tree), society read as health or
  culture (two Spanish articles), the London history story read as
  environment.
- **bge-m3's right-alone cases** are mostly where Laya was unsure: four
  of six at a probability of 0.53-0.57.

**A combination, exploratory.** Where the two disagree, take Laya's group
when its own probability is at least t, else bge-m3's:

| t | 0.5 | 0.7 | 0.8 | 0.9 | 0.95 |
|---|---|---|---|---|---|
| Right of 51 | 42 | 43 | 45 | **46 (0.902)** | 42 |

**This is chosen on the test set, so it cannot be adopted from here.**
With 13 disagreements, the threshold that wins is partly luck: all four
cases at 0.9 or above happen to be Laya's right ones. To test it properly,
write the rule first (t = 0.9, fixed), then score it on articles labelled
after today. The labelling queue grows every day, and the topic
experiment can be rerun on the new facts.

# The verifier's FALSE: the experiment's rule

Written 2026-10-22, after reading the errors of run `340a36ac8972` and
before any of the runs below was made.

## What was found

On the 69 train claims, the thorough pipeline (`340a36ac8972`, 50.7%)
answered FALSE 38 times, 12 of them right (precision 31.6%), and FALSE to
21 of the 45 true claims. Each such FALSE marks exactly one source
"contradicts" and leaves the rest without a stance, for true and false
claims alike. Most of the 21 explain themselves by absence ("the evidence
does not mention ...", "no se menciona ..."); the right FALSEs mostly name
the other value ("3 million, not 300,000"). The prompt
(`llm_verification.SYSTEM_PROMPT`) defines neither TRUE nor FALSE, and has
no stance for a source that is on the subject but says nothing on the
claim's point.

## The question

Does the 3B say FALSE because a detail is missing - and does it stop when
told what each verdict means, or when asked about one source at a time?

## The claims and the evidence

The custom set's train half, all 69 claims (`split.json`). The test half
stays unlooked-at.

A new full run with the thorough defaults (`thorough.json`, label
`verifier-2026-10-22`) keeps every claim's candidates
(`evidence.jsonl`). Every variant is a **replay** of that run
(`--replay`): the same candidates, ranked, judged and scored again. Two
thorough runs on the same claims scored 42.0% and 50.7% because their
searches differed; a replay removes that, so the paired differences below
are the verifier's alone.

## The entries

| Entry | Thresholds | What changes |
|---|---|---|
| B0, baseline | `thorough.json` (the searched run itself) | nothing |
| R0, replayed baseline | `thorough.json`, replayed | nothing: the model's own noise on the same evidence (first 10 claims) |
| V1, stated rules | `stated.json` | the prompt defines TRUE, FALSE and a "silent" stance; the scorer turns a FALSE with no cited contradicting source, or a TRUE with no cited supporting one, into UNVERIFIED |
| V2, one source at a time | `per_source.json` | one short call per source (supports / contradicts / silent / unrelated, with a quote); the verdict follows from the stances by a written rule |

Added at 13:20, after V1's result and before V2's or V3's:

| Entry | Thresholds | What changes |
|---|---|---|
| V3, a larger reader | `thorough.json`, replayed, `qwen3.5:9b` with thinking off (`LLM_REASONING_EFFORT`) | only the model: on the annotator's own pages (19 Oct) it was as accurate as the 3B and far more careful, at three times the time; never run on searched evidence |

Added at 13:50, after V2's result (39.1%, not adopted by the rule) and
before V2b ran anywhere:

| Entry | Thresholds | What changes |
|---|---|---|
| V2b, one source at a time, by majority | `per_source.json`, label `verifier-2026-10-22-majority` | V2 with its verdict the side more outlets take, a tie UNVERIFIED, and no PARTIALLY_TRUE from the scorer for a single dissent |

V2's run made any disagreement PARTIALLY_TRUE (18 of 69, 9 of them true
claims with one stray "contradicts"). Recounted from its own recorded
stances, the majority rule gives 47.8% and 18 confidently wrong, against
B0's 44.9% and 36; a tie going to TRUE would give 52.2%, by leaning on a
set two thirds true, so it is not the rule. Because V2b was chosen
after seeing the train half, the train half cannot confirm it: **V2b is
adopted only if it also meets the rule on the test half**, against a
fresh thorough run there that keeps its evidence, replayed once.

V3 is judged by the same rule.

Added at 15:55, after V2b's adoption and before V4 ran:

| Entry | Thresholds | What changes |
|---|---|---|
| V4, quote first | `per_source.json`, label `verifier-2026-10-22-quote-first` | V2b's per-source prompt with the quote asked before the stance, and one rule: a sentence that gives a different figure, date, place or name for the same thing contradicts the claim |

Why: of the altered claims V2b called TRUE, several had a "supporting"
quote that states the original detail outright (fact162's "68 days" for
the claim's 168; fact171's Jerez for Granada). A rule-based check of
the figures in those quotes was tried on the train records first and
dropped: 5 flags on false claims against 3 on true ones (years in
passing), about one verdict changed. V4 asks the model instead.

Added at 17:25, after V3's result (9B, list verifier, train: 50.7%,
selective 67.4% against 47.7%, kappa 0.282 against 0.141, altered claims
73%, natural 44%; ~90 s a call) and before V4's or V5's:

| Entry | Thresholds | What changes |
|---|---|---|
| V5, the 9B one source at a time | `per_source.json`, `qwen3.5:9b`, thinking off, label `verifier-2026-10-22-9b-per-source` | V3's reader with the per-source question: whichever per-source prompt the train half prefers between V2b's and V4's, decided by V4's train result before V5 starts |

V3 catches altered claims and V2b natural ones; V5 asks whether the
larger reader keeps the first while the per-source question brings the
second. Judged by the same rule on the train half; the test half only if
it meets it there. Its time decides nothing about adoption on this CPU:
like V3, if it wins it is the recommendation for a faster endpoint.

**The test half is not untouched for V4**: its altered-claim misses were
read (their quotes) before V4 was designed. V4 is judged on the train
half against V2b, replayed; its test-half result is reported as seen,
not as a confirmation, and adoption needs the train half to show it and
the test half not to contradict it. Its call takes about three times the
3B's on this CPU, so if it wins it is the recommendation for a faster
endpoint (a GPU or a hosted model), and the app's default on this CPU is
the author's call.

## The rule

1. **Primary: accuracy** on the 69 claims, paired against B0 on the same
   evidence, with its 95% bootstrap interval (`report --compare`).
2. **Secondary: confidently wrong** (a definitive verdict that is not
   gold, the report's journalist-effort table), FALSE precision, TRUE
   recall, and the median time a claim.
3. **Adopted as the default** if its accuracy is at least B0's (point
   estimate) and its confidently-wrong share is lower. A variant that
   loses accuracy but cuts confidently wrong is reported and kept as a
   preset: that trade is the author's, not this experiment's.
4. If R0 differs from B0 on more than one of its ten claims, the model's
   noise on fixed evidence is reported beside every difference.
5. An adopted variant is run once on the test half afterwards, the only
   look at it, with a fresh thorough run on the same evidence as its
   baseline.

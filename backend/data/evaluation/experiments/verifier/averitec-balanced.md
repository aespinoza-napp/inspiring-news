# Every verifier on AVeriTeC's balanced dev sample, on fixed evidence

Started 2026-11-23. The comparison the four measures were written for
(`docs/decisions/evaluation.md`, "One benchmark for every approach"): the 3B,
MiniCheck, the 9B and one Groq model reading the same sources, so they differ
by their reading alone. Dev is read, never tuned on
(`experiments/averitec/protocol.md`). Run with
`scripts/bench_averitec_verifiers.sh N`, ten new claims at a time.

## Setup

- **Claims:** the first N of `averitec_dev_balanced.jsonl` (35 a label, labels
  interleaved, so every N is balanced). The target is 40, ten a label; the
  same commands extend it to 140.
- **Evidence:** the 3B's knowledge-store run `1ee9810b5fa1`
  (`averitec_store.json`). On the 9 claims of the first 10 it shares with the
  5 Nov store run `49e4c76106c6`, it gave back the same sources and the same
  verdicts: the store is fixed and BM25 deterministic, so this is that run's
  evidence, extended to the claims it did not have.
- **Contenders:** `llama3.2:3b-bench` (the pipeline's verifier),
  MiniCheck-FT5 (`averitec_store_minicheck.json`), `qwen3.5:9b-bench` with
  thinking off, and `openai/gpt-oss-120b` on Groq's free plan, chosen by the
  20-claim screen (`experiments/models/results.md`, 23 Nov). Restatement off for
  all four (`backend/.env` turns it on for the app; the protocol judges the
  claim's text alone). One claim and one model call at a time.

## Claims 1-10 (23 Nov)

Labels: 3 Refuted, 3 Supported, 2 Not Enough Evidence, 2 Conflicting.
Always answering Refuted gets 3 (30%, macro-F1 0.115). Every run's temporal
audit says **Held**. No invalid answer, nothing unreachable.

| Verifier | Run | Right of 10 | Macro-F1 | Wrong and definite | vs the 3B [95% CI] | Model s a claim (median) | Whole claim s (median) | Resources | Self-hosted |
|---|---|---|---|---|---|---|---|---|---|
| `llama3.2:3b` | `1ee9810b5fa1` | 3 | 0.268 | 6 | | 44.7 | 72.1 | 3.2B, 2.0 GB disk, 4.1 GB loaded | yes |
| MiniCheck-FT5 | `b9cc0341030d` | 2 | 0.139 | 2 | -10 pts [-30, 0] | 6.8 | 19.0 | 783M, 6.3 GB disk (two copies), 3.5 GB peak | yes |
| `qwen3.5:9b` | `556aa1250597` | 3 | 0.255 | 5 | +0 pts [0, 0] | 114.5 | 123.2 | 9.0B, 6.6 GB disk, 6.7 GB loaded | yes |
| `openai/gpt-oss-120b` | `f2980fd00e70` | **4** | **0.325** | 4 | +10 pts [0, +30] | **3.1** | **15.6** | 117B (5.1B active), Groq's servers | no; open weights, Apache 2.0 |

Ten claims say nothing yet: each accuracy's interval spans 60 points (the
3B's 30% is [0, 60]), and the 9B's [0, 0] means only that it was right and
wrong on the same claims as the 3B. The
reports are `cli report --compare` against the 3B, in
`reports/averitec_dev_balanced/`; resources are `frameworks/resources.json`
(11 Nov). gpt-oss-120b would cost $0.064 per 100 claims if paid (29 Oct prices).
MiniCheck cannot answer FALSE, so its ceiling here was 5 of 10.

**Time.** The 3B and MiniCheck ran at 14:54-15:10 and the 9B at 16:18-16:40,
on an otherwise quiet laptop (Intel Core Ultra 7 165U, 14 threads, no GPU).
gpt-oss-120b ran at 15:25-15:28, while another session's `check.sh` sent its
model tests to the same `inference/`: its model seconds are Groq's and
unaffected, but its whole-claim seconds include slower ranking.

**Void: `qwen3.5-9b-bench/4a0ccd41dd20`.** The 9B's first try ran without
`LLM_REASONING_EFFORT`, so the model thought before answering, spent all 160
tokens of every per-source answer on it and answered nothing: 35 of 35 calls
cut, every verdict invalid. `scripts/bench_models.sh` had always switched it
off; `bench_averitec_verifiers.sh` now does too. Re-run as `556aa1250597`.

## Claims 1-20 (24 Nov)

`scripts/bench_averitec_verifiers.sh 20`: the same four runs, resumed, so
claims 1-10 were not run again and their figures are those above. Labels of
the 20: five of each. Always answering Refuted gets 5 (25%, macro-F1 0.100).
Every run's temporal audit says **Held**; no invalid answer, nothing
unreachable, 20 of 20 claims scored in each.

| Verifier | Run | Right of 20 (1-10 + 11-20) | Macro-F1 | Wrong and definite | vs the 3B [95% CI] | Only it / only the 3B right | Model s a claim (median) | Whole claim s (median) |
|---|---|---|---|---|---|---|---|---|
| `llama3.2:3b` | `1ee9810b5fa1` | 4 (3 + 1) | 0.176 | 15 | | | 37.8 | 66.7 |
| MiniCheck-FT5 | `b9cc0341030d` | 5 (2 + 3) | 0.170 | 4 | +5 pts [-15, +25] | 3 / 2 | 5.9 | 17.1 |
| `qwen3.5:9b` | `556aa1250597` | 5 (3 + 2) | 0.212 | 11 | +5 pts [-10, +20] | 2 / 1 | 123.6 | 131.1 |
| `openai/gpt-oss-120b` | `f2980fd00e70` | **9 (4 + 5)** | **0.391** | 7 | **+25 pts [+5, +45]** | 5 / 0 | **3.1** | **14.6** |

Accuracy with its interval: the 3B 20.0% [5, 40], MiniCheck 25.0% [10, 45],
the 9B 25.0% [10, 45], gpt-oss-120b 45.0% [25, 65]. Kappa against gold:
-0.067, 0.000, 0.000 and +0.267 [+0.007, +0.527]; gpt-oss-120b's over the
3B's, +0.333 [+0.062, +0.640].

**What 20 claims say.** gpt-oss-120b is the first contender whose paired
interval over the 3B leaves out 0: it was right on 5 claims the 3B got wrong
and wrong on none the 3B got right. That is 20 claims of one balanced sample,
read once; it says the difference is unlikely to be resampling noise on
*these* claims, not that it holds at 40 or over the split. The 3B is below
always-Refuted (4 against 5): on claims 11-20 it answered FALSE to 8 of 10
and was right once. MiniCheck and the 9B are not distinguishable from the 3B.
MiniCheck is wrong and definite least (4) because it answers UNVERIFIED to 14
of 20.

**No verifier here can answer Conflicting.** Under `verifier_answer:
per_source` (`averitec_store.json` keeps the default) the verdict is
`verdict_from` in `fact_checker/verification/per_source.py`: TRUE, FALSE or
UNVERIFIED, never MISLEADING or PARTIALLY_TRUE, which are what AVeriTeC's
Conflicting Evidence/Cherrypicking maps to. MiniCheck answers TRUE or
UNVERIFIED only. So the 5 Conflicting claims of the 20 (a quarter of every
balanced N) are wrong for all four, and the ceiling is 75%, MiniCheck's 50%.
This is the setup as the app runs it, not a fault of the run; it is a fixed
handicap the full-split figure (where Conflicting is 7% of claims) barely
feels.

**Time.** Claims 11-20 ran at 09:15-09:51 on a quiet laptop (load 0.96 at
the start, no other job; the load after it was the 9B's own `llama-server`):
the 3B's store run 8 minutes, MiniCheck 2.5, the 9B 23, gpt-oss-120b 2.
gpt-oss-120b's 105 calls include 9 that Groq refused with 429 (the free
plan's per-minute cap); each was waited out and answered, which is its p90
of 6.2 s waiting for the model. Its whole-claim median (14.6 s) is now from a
quiet machine; claims 1-10's ran beside another session's `check.sh`.

Reports: `cli report --compare` against the 3B, rewritten over the 20 in
`reports/averitec_dev_balanced/`.

## Left

Claims 21-40: `scripts/bench_averitec_verifiers.sh 30`, then `40`, about 36
minutes a batch on a quiet machine (the 9B is 23 of them). Then the four
measures on 40 claims, beside the 3B's full-split figure on the first 100 dev
claims (`49e4c76106c6`: 54.0% [44, 64], macro-F1 0.339, always-Refuted 58.0%).

# The 20-second fact-check: the contest's rule

Written 2026-10-22, before any of the four runs below was made.

## The question

Can a claim be checked in about 20 seconds on this machine (Intel i9-10900,
10 cores, no GPU, Ollama 0.40 on the host, `llama3.2:3b`), never past 30,
without paying for a hosted model - and what does it cost in verdicts?

## The claims

The first 10 claims of the custom set's **train** half, in `split.json`
order: fact008, fact009, fact010, fact011, fact012, fact015, fact016,
fact020, fact021, fact036. All ten gold labels are the human annotator's
(none is an AI label). Train, not test: the test half stays unlooked-at
for the thesis.

## The entries

Each run alone on the machine, the same claims, back to back, the same
day, through the harness (`cli run --dataset data/evaluation/manual
--split train --limit 10`), two claims at once and one model call at a
time (`CLAIM_MAX_CONCURRENCY=2`, `LLM_MAX_CONCURRENCY=1`), as production:

| Entry | Thresholds | What changes |
|---|---|---|
| A, baseline | none (today's defaults) | 3 queries, 5 pages, embedding pre-rank, 2,000-character ranking, the full answer with quotes, no deadline |
| B, compact answer | `compact_answer.json` | only the answer: a stance per source and a short reason, no quotes |
| C, fast | `fast.json` | B, plus 2 queries, lexical pre-rank, 3 pages of 400-character passages, ranking on the passages, a 30 s deadline |
| D, fast on snippets | `fast_snippets.json` | C, with no page fetched: the search snippets are the evidence |

Plus Claude (Opus 5.5, in this Claude Code session), checking the same ten
claims by hand, blind to their labels: one web search per claim, a second
only when needed, timed with `date` around each claim.

## The rule

1. **Speed.** An entry qualifies if its median claim (the harness's
   `latency.total`, waiting for the model included) is at most 20 s and
   its 90th percentile at most 30 s.
2. **Verdicts.** Among those that qualify, the winner is the one with the
   most verdicts equal to the gold label; a tie goes to the faster median.
3. **Not worse than today.** The winner becomes the default for the app's
   analyses only if it gets at least as many right as the baseline minus
   one (10 claims cannot tell one verdict from noise: two runs of the
   same model on the train half differ by up to ten points), and no claim
   ends "not checked" because time ran out. Otherwise it stays a preset,
   and the default does not change.
4. Ten claims say nothing firm about accuracy. If the winner is adopted,
   it is run on the whole train half (69 claims) afterwards and compared
   with the 19 Oct runs there; that run decides whether it stays.

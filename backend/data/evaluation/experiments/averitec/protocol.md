# AVeriTeC: the first measurement

Written 2026-11-05, before any verdict on this data existed. Only retrieval had
been looked at (20 train claims, no model) and three dev claims as a smoke test,
which found a leak and were re-run after it was closed.

## Question

How accurate is the fact-checker on AVeriTeC's dev split, measured as ClaimCheck
(arXiv:2510.01226) measures it, with nothing from the claim's date on readable as
evidence?

## Data

The 500 claims of the official dev split, Hugging Face revision
`2ca9dee23a2a6fa64c5bd918e0cd28ed0aa09031`. Rows are in the order of the SHA-256
of their id, so `--limit 100` is a fixed random sample that a later `--limit 500`
extends. The first 100: 58 Refuted, 28 Supported, 8 Not Enough Evidence, 6
Conflicting.

Dev is not tuned on. Anything that changes the pipeline is tried on train first.

## Conditions

All with the pipeline's defaults (`thorough`, per-source verifier), `llama3.2:3b-bench`,
no second look, no internal corpus, and the claim's text alone: no speaker, place or
date goes into the query or the prompt.

| Name | Evidence | Command's difference |
|---|---|---|
| `closed-book` | None. What the model remembers | `--closed-book` |
| `store` | The official knowledge store, BM25 over each claim's pages | `--knowledge-store`, `averitec_store.json` |
| `web` | Live SearXNG through the temporal gate | `averitec_web.json`, `--label web-gate` |

Order (`closed-book` run first; `store` audited first: `averitec/store_audit_dev.json`): 100 claims of each, read, then the rest of `store`, then the rest of `web`
as far as the machine allows. Published comparisons need the 500; 100 is a
preliminary figure and is called one.

## What is reported, whatever it says

1. Accuracy over every claim (a claim with no verdict is wrong), with its 95%
   bootstrap interval, and macro-F1 over the four classes.
2. Beside them, always: **always answering Refuted, on the same claims** (61.0%
   accuracy on the whole split).
3. Per-class F1 and the confusion matrix.
4. The temporal audit. **Any late source, undated fact-check, own fact-check or
   reference page in a run's evidence makes that run invalid**: it is fixed and
   re-run, and its figure is not reported as a result.
5. Set-apart outcomes: searches unavailable, models unreachable.

## How it is read

- A run beats the trivial answer only if its accuracy's interval lies above the
  always-Refuted figure on the same claims. Otherwise: "not distinguishable from
  always answering Refuted", however the number looks.
- `store` is compared with HerO and InFact, `web` with ClaimCheck, PASS-FC and
  DEFAME, and only at 500 claims. `web` also differs from them in the search
  engine, since they had Google's date filter: a gap may be the engine.
- The gap from `closed-book` to the others is what evidence adds; `closed-book`
  over chance is what the model remembers. Llama 3.2's training ended after these
  claims, so that memory can hold the outcome, and no gate reaches it.
- No threshold, prompt or code is changed in response to dev. A finding goes to a
  new try on train, by the iteration loop's rule.

## Corrections

**2026-11-05, the first `store` run is void.** Run `49e4c76106c6` over the first
100 claims gave 50.0% and its audit said Held, which only meant no address was
dated too late. Reading the text of what the model was given afterwards: 33 of
480 sources state a date on or after their claim's (29 of them with no date
anywhere else, on 26 claims), such as AP's and ABC's reports of the claim's own
day. By rule 4 it is not a result. The gate now refuses such a page
(`LATE_IN_TEXT`, `retrieval/temporal.py`), the audit checks for it, and `store`
and `web` start again from the first claim. Leak fixes are the one change rule 4
allows on dev: this one was chosen for what it lets through, not for what it did
to accuracy, and no accuracy on the corrected gate had been seen when it was
written. `closed-book` reads no pages and stands.

**2026-11-06, the `web` condition leaves out the scholarly engines** (`search_science_engines:
drop` in `averitec_web.json`): a result only arXiv, Crossref, Semantic Scholar or PubMed
returned is not evidence. Decided on 10 train claims (`questions-rule.md`), where with the
news cut by the temporal gate Crossref and arXiv gave 1,093 of the 1,538 results counted engine by engine, and filled the
evidence with papers silent on the claim; AVeriTeC's claims are politics and health from
2019-2020. No `web` run on dev had a record when this was written (`5528f7bf5154` was empty
and is run again with `--fresh`), so no dev verdict chose it. `store` does not search the web
and is unchanged; `closed-book` reads no pages.

**2026-11-06, two conditions added**, `store-questions` and `web-questions`
(`questions-rule.md`), by the same rules.

## What this does not say

English only, and mostly politics and health from 2019-2020: nothing about
Spanish or about constructive news, which is what the app checks. Whether the
custom set's figures hold is a separate question this leaves open.

# X-Fact evaluation set (English + Spanish)

The ground-truth set Phase 4 (`docs/roadmap.md`) needs and did not have:
labelled claims with human verdicts, to benchmark `LLMVerifier` against
instead of eyeballing output. Source: X-Fact (Gupta & Srikumar, 2021,
<https://github.com/utahnlp/x-fact>), chosen over FEVER because it is an
open-retrieval benchmark - see
`docs/final_document/sections/evaluation_dataset.tex` for the full
justification, which this repo's paper draft already settled on
independently of this file.

## Files

- **`xfact_en_es.jsonl`** - the full filtered set: 13,037 claims (11,865
  English, 1,172 Spanish), one JSON object per line.
- **`xfact_en_es_pilot.jsonl`** - a 64-claim stratified sample (8 per
  language/label bucket that has enough data, preferring `dev`/`test`
  split claims over `train`), for a first real pass through the pipeline
  without the hours a full run over 13k claims would cost - each claim
  costs roughly a full `/analyze`-claim's worth of real SearXNG search,
  scraping and one LLM call (see `docs/decisions/concurrency.md`'s load
  test: tens of seconds per claim, not milliseconds).

Regenerate either with `scripts/prepare_xfact_eval.py` (full set) and the
inline script in its module docstring history / this README's git blame
(pilot sampling) - both are deterministic (`random.seed(42)`).

## Where this came from, and a real gap in it

`data/x-fact-including-en/` (not the base `data/x-fact/`) is the source,
because English claims only exist in that variant. Within it, **English
claims exist only in `train.all.tsv`** - X-Fact's real held-out languages
are the other 24; English was added purely as a training-time
augmentation and has no `dev`/`test` split of its own. Spanish, by
contrast, is one of the real evaluation languages and has all three
splits (`train`/`dev`/`test` = 894/113/165 claims here).

**English claims also use PolitiFact's native 6-class scale directly**
(`true` / `mostly true` / `half true` / `mostly false` / `false` /
`other`), not the master 7-class taxonomy
(`data/x-fact/label_maps/master_mapping.tsv`) the other languages were
already normalised to. Concretely: **English has no claims mapped to
`MISLEADING` or `UNVERIFIED`** in this set - not a bug in the filtering,
a property of PolitiFact's own label set, which has no equivalent of
X-Fact's `partly true/misleading` or `complicated/hard to categorise`
categories. The pilot sample reflects this honestly (0 English claims in
those two buckets) rather than papering over it.

## Label mapping (X-Fact -> this project's `Verdict`)

There is no clean bijection - X-Fact distinguishes `mostly true` /
`mostly false` from the absolutes and this project's `Verdict` enum
(`backend/src/models/fact_checker/fact_check.py`) does not. The mapping,
documented in `scripts/prepare_xfact_eval.py`:

| X-Fact label | `Verdict` | Why |
|---|---|---|
| `true` | `TRUE` | |
| `mostly true`, `half true` | `PARTIALLY_TRUE` | Central claim holds, a detail doesn't - this project's own definition of `PARTIALLY_TRUE` |
| `partly true/misleading` | `MISLEADING` | X-Fact's own label already names this |
| `mostly false`, `false` | `FALSE` | No intermediate bucket exists on the false side of this project's scale |
| `complicated/hard to categorise` | `UNVERIFIED` | X-Fact's own examples for this bucket: "unverifiable", "not proven", "cannot be checked" |
| `other` | dropped | Satire, corrections, etc. - not a verdict on the claim's truth |

## What this is not

This is data, not a harness. Nothing here runs a claim through
`LLMVerifier` and scores the result yet - that's the next piece of
Phase 4 groundwork, and it's what turns this file from "a dataset exists"
into "verification accuracy is measured." `referenceEvidenceLinks` on
each row are X-Fact's own sources, kept for manual spot-checking a
disagreement - they are deliberately not fed to the pipeline as evidence,
because this project does open-domain retrieval (SearXNG, at
verification time) and handing it the answer's own sources would defeat
the point of the benchmark.

# X-Fact evaluation set (English + Spanish)

The ground-truth set Phase 5 (`docs/roadmap.md`) needs and did not have:
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

- **`manual/factNNN.json`** - the hand-labelled custom set, one file per
  fact (target 150, minimum 100), written by `labeller/`. Empty until the
  first fact is saved. See below.
- **`custom_en_es.jsonl`** - those files joined, once the set is
  finished (`python labeller/app.py join`). Derived: the per-fact files
  are the source.

Regenerate either x-fact file with `scripts/prepare_xfact_eval.py` (full set) and the
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
into "verification accuracy is measured." Its design (record format, run
layout, metrics, what is reported apart) is in
`docs/decisions/evaluation.md`, designed on 2026-10-01 and not built yet. `referenceEvidenceLinks` on
each row are X-Fact's own sources, kept for manual spot-checking a
disagreement - they are deliberately not fed to the pipeline as evidence,
because this project does open-domain retrieval (SearXNG, at
verification time) and handing it the answer's own sources would defeat
the point of the benchmark.

## The custom set (`manual/`, joined into `custom_en_es.jsonl`)

What the paper calls the **custom validation set**
(`docs/final_document/sections/custom_dataset.tex`): claims from
positive-news articles, which x-fact's political statements do not cover.
Labelled by hand with `python labeller/app.py` (standard library only;
`labeller/README.md`), **one file per fact** so each verified fact is
visible in the repository on its own.

**Same format as x-fact, so the same harness scores it.** Every fact
starts with x-fact's ten keys in x-fact's order (a test in
`labeller/test_app.py` holds the order and types to
`xfact_en_es_pilot.jsonl`). Then its own:

| Key | |
|---|---|
| `id` | The file name: `fact001`, `fact002`... |
| `topic` | A `TOPICS` key; balanced over its five groups (society, science, environment, culture, health) |
| `claimType` | `factual` / `numerical` / `interpretive` |
| `sourceTier` | Strongest source used: `primary` > `reference_media` > `press_release` > `social_media` |
| `onlyOwnSource` | Only the organisation the story is about backs it - forces `UNVERIFIED` |
| `evidenceDate` | Newest evidence used; may not be after `claimDate` |
| `articleUrl`, `annotatorNote`, `createdAt` | |
| `review` | The blind second label, for the 20% sample: `label`, `firstLabel`, `agrees` |

`labelRaw` is the guide's label, after AVeriTeC: `supported`,
`partially supported`, `conflicting evidence/cherrypicking`, `refuted`,
`not enough evidence` -> `TRUE`, `PARTIALLY_TRUE`, `MISLEADING`, `FALSE`,
`UNVERIFIED`. `split` is always `test`: nothing is tuned on it.

**Balance.** 5 verdicts x 5 topic groups = 25 cells of 6. The targets
steer labelling; they are not a quota. A short `FALSE` cell is reported
short, not padded.

**Self-agreement.** `ceil(20%)` of the facts - chosen by a hash of their
id, not by hand - are labelled a second time, blind, ideally a week
later. The labeller reports observed agreement and Cohen's kappa on the
*first* label: correcting a fact after its review does not turn a
disagreement into an agreement.

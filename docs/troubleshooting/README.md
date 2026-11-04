# Troubleshooting the fact-checker, part by part

What goes wrong in each part of the pipeline, found by comparing it with a
person-like reader on the same claims. One file per part, upstream first,
because a verdict is only as good as the stage before it (the `debug-verdict`
skill):

| Part | File | The finding in one line |
|---|---|---|
| Knowing what to look for | [01-what-to-look-for.md](01-what-to-look-for.md) | The pipeline never states the point that would settle a claim; every query is built from the sentence's words. **Built 4 Nov, opt-in: `query_plan: checkable`** |
| Query planning | [02-queries.md](02-queries.md) | Figures are stripped from every query, key nouns are lost, the anchor collapses to one entity, and the refutation query finds nothing for news. **Built 4 Nov, opt-in: `query_plan: checkable`** |
| Search results | [03-search-results.md](03-search-results.md) | The source that settled a claim was among the pipeline's candidates for 6 of 20 claims |
| Ranking | [04-ranking.md](04-ranking.md) | The pre-rank funnel keeps five sources by title similarity, so a name's profile pages beat the source with the fact (fact082) |
| Verification | [05-verification.md](05-verification.md) | One off-subject "supports" or "contradicts" decides the verdict when the rest are silent: 6 of the 11 wrong verdicts |

## The first comparison: 20 claims, 4 Nov 2026

**What was done.** The first 20 claims of the custom set's train half (the
iteration loop's screen) were checked by Claude (Opus 5.5, in Claude Code) the
way the 22 Oct contest did, in this order, each step saved before the next was
read:

1. `claims.jsonl`: the claim, its language, date and article link only. No
   label, no reference links, no pipeline record.
2. `plan.jsonl`: for each claim, **what it is looking for** (the checkable
   point), **what would settle it**, and **the queries it would run**, written
   before any search.
3. `claude.jsonl`: the searches actually run (Claude Code's WebSearch, the
   article's own site blocked), what was found, the sources, and a verdict by
   the annotator's rule (a detail that cannot be found makes it UNVERIFIED). A
   second search only where the first left the point open: 4 claims, 24
   searches in all.
4. `comparison.json`: then, and only then, the pipeline's own records for the
   same claims and the gold labels.

All four files are in `backend/data/evaluation/experiments/claude-search/`.
The pipeline's side is two runs:
- `cc053417c0cb`, the searched run of 29 Oct whose evidence every replay uses:
  its queries, candidates and cuts;
- `1d07e163a659`, today's defaults replayed on that evidence: the verdicts and
  stances as the pipeline now gives them. Its seconds were measured under CPU
  contention and are not used.

**Right against the gold label**, on the same 20 claims:

| | Right | Notes |
|---|---:|---|
| Claude, by hand (24 searches) | **16** | missed fact008, fact009, fact016, fact066 |
| The pipeline today (replay, `1d07e163a659`) | **9** | |
| The pipeline on 29 Oct (`cc053417c0cb`) | **11** | before evidence independence (3 Nov) |

The comparison is unequal in one respect: Claude searched a different engine
(its own WebSearch) from the pipeline (SearXNG, 29 Oct, before the 3 Nov search
change). The queries are compared as written, and the sources by whether the
pipeline's candidates held the one that settled the claim.

**Where Claude and the gold label disagree** (worth a second look at the label,
not a correction of it):

- **fact008**, gold TRUE, Claude FALSE: the claim puts the splashdown "frente
  a las costas de Chile". EFE's wire story, copied by the Spanish outlets the
  pipeline found, says so; US outlets (NBC, Axios, CBC, Wikipedia) say the
  ship came down in the contingency zone in the northern Pacific, north of
  Hawaii. Chile was the full-mission zone.
- **fact016**, gold TRUE, Claude UNVERIFIED: the 138,000 and 23,000 figures
  were found, the "10 books in Braille" was not. By the annotator's rule this is
  UNVERIFIED, unless the annotator found it.
- **fact009, fact066**, gold PARTIALLY_TRUE, Claude TRUE: every detail Claude
  checked held. The annotator's note would say which part is partial.

## What it suggests for the iteration loop

Each finding names a change the campaign can measure (`/iterate-fact-check`).
The replayable ones come first, since a replay is exact:

| Change | Part | Replay or search |
|---|---|---|
| A verdict needs a "supports" whose quote carries the claim's figure or key term, or two outlets; an off-subject stance counts as silent | verification | replay (code, behind a new `verifier_answer` value or field) |
| "Contradicts" only when the source is about the same event and period (prompt) | verification | replay (prompt) |
| Raise `evidence_min_pertinence`, so bookshop.org and profile pages never reach the model | ranking | replay (threshold) |
| Keep figures, units and the claim's key noun in the proposition query; drop the refutation query for news claims | queries | searched (code in `query_builder.py`) |
| `claim_restatement: standalone`, the nearest the pipeline has to "what to look for" | what to look for | searched (threshold) |

## Adding to it

Run the same protocol on more claims, train half only (the test half decides
once, at the end):
1. extract the claims without labels, as the script in this session did
   (`select_rows(..., split="train")`, printing id, language, date, link,
   claim);
2. write the plan before searching;
3. search and save;
4. only then join with a run's records.

Add the findings to the part's file, dated, and keep a finding that a later
change fixed, with the date it was fixed.

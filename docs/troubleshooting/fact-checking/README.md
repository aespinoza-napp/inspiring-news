# Troubleshooting the fact-checker, part by part

What goes wrong in each part of the pipeline, found by comparing it with a
person-like reader on the same claims. One file per part, upstream first,
because a verdict is only as good as the stage before it (the `debug-verdict`
skill):

| Part | File | Experiments | The finding in one line |
|---|---|---|---|
| Knowing what to look for | [01-what-to-look-for.md](01-what-to-look-for.md) | [experiments/01-what-to-look-for/](experiments/01-what-to-look-for/README.md) | The pipeline never states the point that would settle a claim; every query is built from the sentence's words. **Built 4 Nov, opt-in: `query_plan: checkable`** |
| Query planning | [02-queries.md](02-queries.md) | [experiments/02-queries/](experiments/02-queries/README.md) | Figures are stripped from every query, key nouns are lost, the anchor collapses to one entity, and the refutation query finds nothing for news. **Built 4 Nov, opt-in: `query_plan: checkable`** |
| Search results | [03-search-results.md](03-search-results.md) | [experiments/03-search-results/](experiments/03-search-results/README.md) | The source that settled a claim was among the pipeline's candidates for 6 of 20 claims |
| Ranking | [04-ranking.md](04-ranking.md) | [experiments/04-ranking/](experiments/04-ranking/README.md) | The pre-rank funnel keeps five sources by title similarity, so a name's profile pages beat the source with the fact (fact082) |
| Verification | [05-verification.md](05-verification.md) | [experiments/05-verification/](experiments/05-verification/README.md) | One off-subject "supports" or "contradicts" decides the verdict when the rest are silent: 6 of the 11 wrong verdicts |

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

## Running it: an agent per part (since 5 Nov 2026)

The same protocol, repeatable on any batch of train claims, one part at a time:
`scripts/troubleshoot.sh` (over `backend/src/evaluation/troubleshoot.py`). The agent is
Claude Code run headless (`claude -p`), with two skills: `what-to-search` (Claude's
blind side) and `troubleshoot-fact-check` (the analyst of one part).

```bash
./scripts/troubleshoot.sh prepare --batch 20261105-next20       # train claims 21-40, blind
./scripts/troubleshoot.sh agent --batch 20261105-next20 --stage 01 --dry-run
./scripts/troubleshoot.sh agent --batch 20261105-next20 --stage 01
./scripts/troubleshoot.sh agent --batch 20261105-next20 --stage 01 --implement
./scripts/troubleshoot.sh status --batch 20261105-next20
./scripts/troubleshoot.sh measure --batch 20261105-next20 --stage 01   # numbers again, no agent
```

What `agent --stage NN` does, and who does each step:

| Step | Who | Writes | Can see |
|---|---|---|---|
| 1. plan: what to look for, what would settle it, the queries (once per batch) | Claude, blind | `plan.jsonl` | `claims.jsonl` only |
| 2. search: the plan's queries, what was found, a verdict (once per batch; stages 03-05) | Claude, blind | `claude.jsonl` | + the web, never the article's site |
| 3. the pipeline's side of the part, offline (01-02) or from the recorded runs (02-05) | the script | `NN-*/pipeline-before.*` | - |
| 4. the comparison and its numbers | the script | `comparison-before.json`, `metrics-before.json`, the experiment file's **Measured** | - |
| 5. findings and one proposed change | Claude, the analyst | the experiment's **Findings** / **Proposed change**, `proposal.json` | everything but the test half |
| 6. (`--implement`) the change, behind a new threshold value, with a test; never committed | Claude | `backend/src`, `backend/tests` | |
| 7. (`--implement`, 01-02) measured again with the change switched on | the script | `*-after.*`, the before/after in **Measured** | - |

Why it can be trusted, or checked:
- **Blind by construction.** Steps 1-2 run with `TROUBLESHOOT_PHASE` set, and
  `.claude/hooks/troubleshoot_blind.py` refuses the run records, the label files, this
  folder, the stage files and a shell. The labels come from the train run's own records,
  read by the script only, after Claude's files are complete.
- **The numbers are the script's.** The analyst cannot edit the measured files (the same
  hook), and the measured section is rewritten on every run. A number in Findings that is
  not in Measured or `comparison-before.json` is the agent's mistake.
- **Every session is logged**: `logs/<step>.jsonl` in the batch directory, the full
  stream of tool calls; the terminal shows one line per call as it runs.
- **Nothing is committed**; with `--implement` the change is in `git diff` for review.

The batch's files: `backend/data/evaluation/experiments/troubleshooting/fact-checking/<batch>/`
(`claims.jsonl`, `plan.jsonl`, `claude.jsonl`, `batch.json`, `logs/`, and one directory per
part). The experiment files: `experiments/<part>/<batch>.md` here.

The measures are approximate and the same for every plan: a decisive detail is
"carried" when its figures, or else its words, appear in the text
(`troubleshoot.carries`). Stages 01-02 are measured offline on the code as it is;
03-05 read the 29 Oct searched run (`cc053417c0cb`) and its 4 Nov replay
(`1d07e163a659`), so a change there is decided by the iteration loop, not here.

Train half only (the test half decides once, at the end). Add a finding to the part's
file, dated, once its experiment is reviewed, and keep a finding that a later change
fixed, with the date it was fixed.

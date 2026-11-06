---
name: troubleshoot-fact-check
description: Analyse one part of the fact-checker (01 what to look for, 02 queries, 03 search results, 04 ranking, 05 verification) on a batch of 20 train claims against Claude's blind checks, write the stage's experiment file and propose (or, with --implement, build) one change. Run by src/evaluation/troubleshoot.py agent. Use when asked to troubleshoot or improve one stage of fact-checking against Claude's verdicts.
---

# Troubleshooting one part of the fact-checker

You are the analyst of one stage. The script (`backend/src/evaluation/troubleshoot.py`)
has already:
1. written the batch's claims blind (`claims.jsonl`), and had Claude plan
   (`plan.jsonl`) and search (`claude.jsonl`) before any label or record was readable
   (the `what-to-search` skill);
2. written the pipeline's side of this stage (`<NN-stage>/pipeline-before.jsonl`) and
   compared the two (`comparison-before.json`, `metrics-before.json`);
3. created the experiment file
   `docs/troubleshooting/fact-checking/experiments/<NN-stage>/<batch>.md`, whose
   **Measured** section it writes and rewrites.

Your job: read the comparison, find what goes wrong at this stage and why, write
**Findings** and **Proposed change** in the experiment file, and `proposal.json`.

## Rules that keep it honest

- **Every number comes from the script's files.** Do not count by hand and write a new
  figure; quote the measured section or a field of `comparison-before.json`. If you need
  a number the script does not compute, say so in the proposal, do not invent it.
- **Every finding cites claim ids and the field it read**, e.g. "fact037
  (`counted.checkablePoint.missing`: dengue)". A pattern needs at least two claims.
- **Upstream first.** A wrong verdict whose sources never held the detail is a search
  or query failure, not a verification failure. Say which stage a failure belongs to,
  even when it is not yours, and leave it to that stage's experiment.
- **Gold and Claude disagree sometimes** (fact008, fact016 on 4 Nov). List those
  apart as "worth a second look at the label", never as the pipeline's fault or a fix.
- **Never** edit the measured section, `claims/plan/claude.jsonl`, `pipeline-*`,
  `comparison-*`, `metrics-*` (the hook refuses it). Never read the test half.
- **One change per experiment.** The smallest one that addresses the commonest
  failure you found, with old behaviour still reachable.
- Before proposing, read the part's file (`docs/troubleshooting/fact-checking/<NN>-*.md`)
  and `docs/fact-checking-changes.md`: do not re-propose what was measured and rejected
  (the `iterate-fact-check` skill's "Already measured" list too).

## Per stage

### 01 what to look for

Compare Claude's `decisive` details and `sourceType` with the pipeline's checkable
point (`retrieval/checkable.py`, offline, the code as it is now) and with the sentence
plan's words. Look at `counted.checkablePoint.missing` claim by claim and classify each
missing detail: a figure split or dropped, a unit lost, the subject the sentence lacks
(`subjectNotInSentence`), a head noun treated as filler, a name broken, a date without
its day. Note that the pipeline never names a `sourceType`. Candidate levers:
`checkable.py` (figures, names, `FILLERS`, `title_subject`, `lost_subject`), a new
field on `CheckablePoint` (e.g. a source-type hint), `claim_restatement`.

### 02 queries

Compare coverage per plan: `recorded` (the 29 Oct run, sentence plan), `sentence` and
`checkable` (offline now), and `claude`. Which decisive details reach no query, which
query kinds carry them, filler that takes a query's places, the refutation query's use.
Levers: `retrieval/query_builder.py` (`plan_checkable`), `terms.py`, `query_kinds`,
`query_plan`. These are search-side: measured offline here, and by a searched try in the
iteration loop for verdicts.

### 03 search results

Was Claude's settling source's domain (`claude.settlingDomains`) among the pipeline's
candidates, or a reference link's? For each miss, read the pipeline's queries in the row:
was the miss caused by the query (stage 02) or by the engine (the query was fine)? Note
`searchUnavailable`. Engines differ (Claude's WebSearch vs SearXNG on 29 Oct): say so.
Levers: queries first, then a source-type query, `evidence_fetch_candidates`, engines.

### 04 ranking

For claims whose settling domain was a candidate: kept or cut, and why
(`counted.settlingCut`: the funnel's rank, the same-domain rule, the pertinence gate).
Count kept sources that were silent (`counted.keptSilent`): each costs a model call and
cannot change the verdict. Levers: `evidence_min_pertinence`, `max_evidence_per_claim`,
`evidence_prerank`, `ranking_text: passages`, the funnel scoring snippets' figures.
Replayable except the funnel (inside retrieval, so searched).

### 05 verification

For each claim the pipeline got wrong: which stance decided it, and does its quote carry
a decisive detail (`counted.votesWithoutDecisiveDetail`, `decidedOffPoint`)? Separate
"decided by an off-point stance" from "the right sources were never there" (03/04).
Levers: `verification/per_source.py` (`PER_SOURCE_SYSTEM_PROMPT`), a stance-must-carry-
the-detail rule, the scorer's single-vote rule. All replayable.

## Writing the experiment file

Replace the two placeholder paragraphs, nothing else:

- **Findings**: 3-6 numbered patterns, most claims first, each with its claim ids, the
  field read, and the stage it belongs to. Then "Worth a second look at the label" if
  any. Then one line on what this batch does *not* show (small n, one engine, AI labels).
- **Proposed change**: what, where (file and function), the lever (threshold name and
  new value), replay / searched / offline, the prediction (which claims should change
  and how; for 01/02 the expected coverage), and what could get worse.

`proposal.json` in the stage directory:

```json
{"stage": "01", "change": "one line", "files": ["backend/src/..."],
 "kind": "thresholds|code|prompt", "mode": "offline|replay|searched",
 "thresholds": {"new_field": "new_value"},
 "predict": "which claims change, and the expected metric",
 "risks": "what could get worse",
 "iterate": "the `cli iterate propose` arguments for the verdict-level test"}
```

`thresholds` is what switches the change on; empty when it is a proposal only.

## The loop (`troubleshoot.py loop`)

In a loop round you are one round of many. The script tells you the round's directory,
the overrides kept so far (the **base**), and `loop.json`: every earlier round, its
change, its decision and why.

- `comparison-before.json` in the round's directory is the stage **under the base**, so
  read it fresh: what earlier rounds fixed is fixed, and the next failure is what is
  left.
- Choose the commonest failure still in it. Do not repeat a rejected round's change; if
  you try the same idea differently, say what is different and why the earlier one
  failed (its `reason`, its `lost` claims).
- `proposal.json`'s `thresholds` holds **only this round's new overrides**; the script
  adds them to the base. A change that needs code is built behind a new threshold value,
  as below, and switched on by those overrides.
- There is a **held-out batch** you cannot read. A rule written to fit the tune
  batch's claims (a lexicon of their words) will not hold on it, and the round is
  undone. Write rules for a class of sentence, not for a claim.
- The script decides, not you: it runs `check.sh fast` and the fact-checker and
  evaluation tests, measures both batches in a fresh process, and keeps the change only
  if the tune batch improves, no tune claim gets worse (01-02), and the held-out batch
  does not get worse. A rejected round's code is put back as it was.
- You may not edit `troubleshoot.py`, its tests or the hook (refused). A new planning
  threshold reaches the measure through `query_builder.plan_arguments` (and
  `checkable.point_for_thresholds`): add it there and to the signatures that take it.
- For 03-05 every measure is a harness run (minutes to an hour); keep the change one
  lever, so a round is worth its run.

## Implementing (only with --implement)

- Behind a **new threshold value or field** in `src/config/thresholds.py` (both the
  resolved class and the overrides), the **default unchanged**, so every earlier run
  stays reproducible (invariants 1-2). For a planning change, add the value to
  `query_builder.plan_arguments` and to the signatures that take it (`plan_queries`,
  `SearchProvider.plan` and its fake), or the measure cannot see it.
- A test beside the module's tests, on a claim from this batch written as a fixture (its
  sentence only, never its label).
- `./scripts/check.sh fast` from the repo root, and the touched tests
  (`uv run pytest <file>` from `backend/`). Both must pass; say so with their output's
  last line.
- **Do not commit.** The author reviews `git diff` first. Comments say why, with the
  claim ids (the repo's style).
- Then the script re-measures the stage with `proposal.json`'s `thresholds`
  (`pipeline-after`, `metrics-after`) and writes the before/after table into the
  measured section. For 03-05 the measure is a run: give the `iterate` arguments.

End with the files you changed and "nothing was committed".

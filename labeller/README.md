# Fact labeller

The tool for hand-labelling the custom validation set. One Python file
and one HTML page, **standard library only**: nothing to install, and it
does not need the backend, Docker or the frontend running.

```bash
python labeller/app.py          # opens http://127.0.0.1:8765
python labeller/app.py join     # when the set is finished
```

Any Python 3.9 or newer, from the repository root or anywhere else.
`--port 9000` changes the port; `--no-browser` does not open one.

## Where the facts go

Every saved fact is its **own file**:

```
backend/data/evaluation/manual/fact001.json
backend/data/evaluation/manual/fact002.json
...
```

Numbered in the order you save them, indented and readable, so each fact
verified by hand shows up in the repository and in a diff on its own.
Editing a fact rewrites its file; to delete one, delete the file. A file
edited by hand is picked up on the next page load (and shown, not
crashed on, if it no longer parses).

Each file has **x-fact's keys, in x-fact's order** (`language`, `site`,
`claimant`, `claim`, `claimDate`, `reviewDate`, `labelRaw`, `label`,
`referenceEvidenceLinks`, `split`), then the custom set's own: `id`,
`topic`, `claimType`, `sourceTier`, `onlyOwnSource`, `evidenceDate`,
`articleUrl`, `annotatorNote`, `createdAt` and `review`. A test holds the
x-fact part to `backend/data/evaluation/xfact_en_es_pilot.jsonl`, so the
code that scores x-fact scores this set unchanged.

## Join

`python labeller/app.py join` re-validates every file and writes them,
in number order, to `backend/data/evaluation/custom_en_es.jsonl` - one
line per fact, beside `xfact_en_es.jsonl`. It refuses (and writes
nothing) if any file is unreadable or breaks a rule. The per-fact files
stay: they are the source, the JSONL is derived. Re-run it after any
later edit.

## What the page does

- **Today**: the day's batch. *Get a new batch* asks the backend
  (`LABELLER_BACKEND_URL`, default `http://127.0.0.1:8000`; `STORAGE_API_KEY`
  is sent if set) for ~10 articles drawn at random from the configured
  sources - one per source, languages alternated, seeded by the date,
  never an article already labelled or proposed, preferring articles from
  the last 60 days and then the topic groups the balance table is short
  of - each with the 1-3 claims the
  pipeline's own claim selector would check. It takes 2-4 minutes; the
  page polls. The batch is saved as `backend/data/evaluation/queue/
  YYYY-MM-DD.json` (then `-2`, `-3` the same day). **Label** fills the form
  from the article and claim and, on save, marks the claim with the fact
  it became; **Skip** records why (opinion, prediction, trivial, fragment,
  duplicate). Labelled / (labelled + skipped) is shown as the precision of
  the pipeline's claim selection - a result for the paper, not just
  progress. This one button needs the backend running (and `inference/`
  for anchor selection; without it claims are ranked by the extractor's
  confidence and say so). Everything else still needs nothing.
- **Label**: the form, a verdict x topic-group balance table (5 x 5
  cells, 6 facts each, 150 total; 100 is the floor), and every fact with
  an Edit button. After a save the article's fields (URL, outlet,
  claimant, date, language, topic) stay filled for its next claim.
- **Review 20%**: `ceil(20%)` of the facts, chosen by a hash of their
  file name, labelled again **blind** (no first label, note or own-source
  flag). Reports observed agreement and Cohen's kappa on the *first*
  label, so correcting a fact afterwards cannot inflate it.

## The rules it enforces

The tie-break rules are fixed before labelling starts; those that can be
checked mechanically are refused on save:

1. Only the organisation's own source backs the claim → `UNVERIFIED`,
   with the source named in the note.
2. Numbers within ±10% relative (or a reasonable rounding) are supported.
   *Not checkable - it is on the page.*
3. Evidence dated after the article's publication date is refused.
4. Source hierarchy: primary > reference media > press release > social
   media. The strongest one used is recorded in `sourceTier`.

Plus: any verdict other than `UNVERIFIED` needs an evidence link. The
method is written up for the paper in
`docs/final_document/chapters/06-experimental-design/03-custom-validation-set/`.

## Tests

```bash
python -m unittest labeller/test_app.py    # also run by ./scripts/check.sh
```

They write to a temporary folder, never to `manual/`.

It listens on 127.0.0.1 only and accepts writes only as
`application/json`, so another website open in the same browser cannot
post facts into the repository through it.

# Fact-checking audit: 4 November 2026

Scope: **the fact-checking pipeline only** (claim → search → ranking → verdict →
article verdict), at `037eccc` on `iterate/20261104-speed`, as it runs today. It
re-checks the fact-checking findings of the 3 Nov audit (`audit-2026-11-03.md`),
and checks claims and an article live. **Not scored**: the nine-dimension score
covers the whole project, and a fact-checking-only score would break that series.

**Written by the same session that wrote some of what it audits.** The iteration
loop (`cli iterate`), `query_plan: checkable` and `docs/troubleshooting/` are this
session's work, so read their findings with that in mind. The pipeline's default
behaviour is not this session's.

## Verdict

**The search is better than the verdicts.** Since 3 Nov the web search finds
on-subject and often primary sources:
- the University of Oslo for the Alzheimer's study;
- the Current Biology paper on ScienceDirect for the chimpanzee claim;
- km3net.org and arXiv for today's telescope article.

Run live on 10 train claims, today's defaults got **7 right**, the same as Claude
by hand (7), where the same pipeline on 29 Oct's evidence had 5. Once the right
page is found, the binding limits are:
- **the 3B's reading** of that page;
- **a verdict rule that lets one outlet decide**, with no guard on a FALSE;
- **worst-claim-wins**, which turns one such misreading into a withheld article.

Two things measured so far are weaker than the app itself:
- the evaluation harness searches without the claims' figures and headlines;
- the labels everything is scored against have not changed since 19 Oct.

## What ran

| Check | Result |
|---|---|
| `./scripts/check.sh backend` with `inference/` up (model tests ran) | 2,359 passed, 3 xfailed |
| `./scripts/check.sh inference` | **5-6 of 23 failed, three runs in a row**, "Cannot copy out of meta tensor", while this session's `inference/` server was running; 23 passed this morning without it; `inference/` unchanged (`839e856`). Probably two loads of one model at once, not proven |
| Frontend typecheck, labeller (43) | Pass |
| `slow`, `graph`, `gcp`, `e2e`, `lake` | **Not run**: outside this audit's scope. Neo4j is down on this machine (`/healthz`: `GraphUnavailable`), so `graph` would fail |
| 10 train claims live, today's defaults (`79d4c2ac724d`) | 7 / 10 right; median 96 s a claim; no search unavailable |
| The same 10, `query_plan: checkable` (`9bae31b05174`) | 7 / 10 right, different claims; median 92 s |
| One real article through the app's own path (local API, `POST /analyze/jobs`) | SINC, "Este telescopio submarino pone a prueba a Einstein...", from today's `/discover` round: 4 claims, all TRUE, overall 0.86, publishable; 5 min 9 s; graph write failed soft (Neo4j down) |
| The first 20 train claims by hand, blind (morning) | Claude 16 / 20; the pipeline on 29 Oct's evidence 9 / 20 (`docs/troubleshooting/`) |
| Search on-subject screen (`scripts/evidence_on_subject.py`) | 29 Oct: 65% of web titles share a claim word, 1% off-subject domains. Today's live runs: 57% / 5% and 63% / 8%. Much of the latter is arXiv/oadoi from one claim (H4); the screen counts arXiv as off-subject even when it is the paper |

The configuration that ran (`backend/.env` and defaults):
- `FACT_CHECK_PROFILE` thorough;
- `llama3.2:3b`, `verifier_answer: per_source`;
- `evidence_independence` on, `claim_restatement` off, `query_plan` sentence;
- second look off, `max_evidence_per_claim` 5;
- 2 claims at once, 1 model call at a time, 180 s timeout.

The live runs' seconds were measured on an otherwise idle machine. The 3 Nov audit's
"~44 s a claim" was on the desktop. This laptop is about twice as slow.

## Since 3 November

Closed or better:
- **H1, the off-subject search**: fixed then. Today's live sources are on the
  subject (above). Still no relevance check beyond the 35% word-coverage rule and
  this rough screen.
- **M1, secrets beside the repo**: `.env.*` is ignored (`.gitignore:156`).
- **Copies of the article counted as confirming outlets**: fixed on 3 Nov
  (`evidence_independence`). Verbatim copies in the same language now drop out.
- **Low items**: `safe_search: 1` in SearXNG; a looping model is no longer read as
  unreachable (`llms.py`, "repeat limit").

Still open:
- **M2, a source quoting the claim marked as contradicting it**: seen again in
  today's article (H2).
- **H2 of 3 Nov, the labels** (M4 here).
- **H3 of 3 Nov, the Devastating edition on the open reader**: unchanged, and
  outside this audit's scope.
- **`robots.txt`**: still not read.

## Findings

### High

**H1: One outlet decides a claim, and a FALSE has no guard.**
`per_source.verdict_from` compares the outlets that support with those that
contradict; silent and unrelated ones do not vote. So one "supports" among five
sources makes a claim TRUE at 0.6, and one "contradicts" makes it FALSE.
`ConfidenceScorer` caps a single-outlet TRUE's confidence at 0.6
(`min_independent_domains`), but has no counterpart for FALSE. Evidence:
- fact037 (212 dengue cases) was FALSE on a 2010 NYT cholera story;
- fact062 was FALSE on two pieces about Hormuz and fuel imports;
- fact010 and fact011 were TRUE on a 1992 pesetas figure and on a ring road in
  **Castellón**.

That is 6 of the pipeline's 11 wrong verdicts on 20 claims
(`docs/troubleshooting/05-verification.md`). With worst-claim-wins, one such FALSE
withholds a whole article.

**H2: The 3B misreads on-subject sources, and that now decides more verdicts than
the search does.** Live today:
- **fact020** (checkable run): the search found the primary study (Biro et al.,
  Current Biology, on ScienceDirect). The 3B marked it *contradicts*, quoting "The
  body is carried dorsally, with Jimato's arm gripped between Jire's shoulder and
  neck". The claim became FALSE.
- **In the telescope article**, scinexx.de was *contradicts* quoting "kein
  auffälliges Signal gefunden" ("no conspicuous signal found"), which supports the
  claim. canariasenpleno.com was *contradicts* while quoting the claim's own
  sentence (3 Nov M2).

The article came out TRUE only because supporting outlets outnumbered these. The
second-look and model benchmarks (29 Oct) found no local model that reads better
in usable time on this CPU.

**H3: The evaluation harness searches with less than the app.**
- **No figures.** `ClaimService.build_claim`, used by `/verify-claim` and every
  `cli run`, leaves `Claim.facts` empty. The anchor query's quoted figures, which
  the app's `ClaimExtractor` fills, never reach a harness search. Today's article
  searched `"1,4" "3"` and `"2026"`, which harness claims never do.
- **No headline.** The harness passes only the article's URL, so a subject that
  only the headline holds ("dengue" for fact037) was never searched.

Every custom-set accuracy figure so far measures this weaker search.
`query_plan: checkable` closes both gaps, opt-in (this session's work, not yet
measured on more than 10 claims). The default keeps the old behaviour, so earlier
runs stay comparable.

### Medium

**M1: Claim selection checked a citation as a claim.** The telescope article's
first claim is the paper's bibliographic reference ("Alba Domi et al.,
'Atmospheric neutrino constraints...', Journal of Cosmology and Astroparticle
Physics"). It was "verified" TRUE at 0.95 against the paper itself: a model call
and five sources spent on a reference.

**M2: A translated copy may count as an independent outlet.** phys.org,
archyde.com and brightsurf.com supported claim 2 of the article with the same
English press-release sentence as the claim's Spanish one. `evidence_independence`
compares a source with the claim's sentence. A translation can't match word for
word, so it likely counts as a separate outlet. **A suspicion**: I did not trace
it in `independence.py`.

**M3: A claim takes 1.5-2.5 minutes here; the target is 20 s.** On this laptop
(14 CPUs, no GPU, the 3B):

| | Seconds a claim |
|---|---|
| Harness, live, median | 92-96 |
| The article's claims | 79, 135, 143, 156 |
| ...of which the model | 60-77 |
| ...of which waiting for the other claim's model call | up to 53 |

Unchanged: the model is ~80% of a claim, one call per source.

**M4: The labels have not moved since 19 Oct** (last commit touching them,
`c333bcf`). The 3 Nov audit counted 108 of 139 as the AI pass's, unreviewed. Not
recounted: this session's test-half guard (`.claude/hooks/sealed_test_half.py`)
blocks reading the label files while the iteration campaign is active.

**M5: Quoting a claim's clock times hurts its search** (this session's code).
Under `checkable`, fact009's "14:49" and "17.58" (Spanish local time) were quoted
in every query. The web gives "12:48 UTC", so the search returned arXiv and oadoi
pages, and a TRUE became UNVERIFIED. Times should not be quoted, or not searched.
To fix before the campaign's searched try.

### Low

- The pertinence gate rarely fires: 4 of 20 claims, 1-2 pages each. Pages that
  cannot answer (bookshop.org, profile pages) reach the model and each cost a call
  (`docs/troubleshooting/04-ranking.md`).
- The refutation query found no refutation in 20 claims, and twice found its own
  words: "Bunk: The Rise of Hoaxes" for Book Bunk, "Florida election myths...
  debunked" (`02-queries.md`).
- The app's subject rule (`terms.subject_terms`) is all or nothing: a claim naming
  "Florida" loses "dengue" even in the app. Fixed only under `checkable`.
- `STORAGE_API_KEY` unset on this machine (the startup warning). Fine on localhost.
- Neo4j down here. The graph write failed soft, as designed.

## What the checks caught, and what they missed

The 2,359 backend tests hold every stage to its contract and the run keys stable;
they caught two tests whose pictures predated this session's new field. They
cannot catch any of the High findings:
- a stance on an off-subject page;
- a misread primary source;
- a harness that searches with less than the app.

All three were found by reading records and checking claims by hand. No check
compares the harness's search with the app's, or asks whether a decisive stance's
quote contains the claim's point.

## If you fix four things

1. **Make a stance show its point, and guard a single-outlet FALSE** (H1). A
   "supports" or "contradicts" counts only if its quote carries the claim's figure
   (rule 1 in `05-verification.md`), and a lone FALSE needs a second outlet. A
   replay can measure both exactly, on the train half.
2. **Make the harness search like the app** (H3): `query_plan: checkable`, times
   unquoted (M5), as a searched try against two same-window baselines
   (`/iterate-fact-check`).
3. **Measure the reader on fixed evidence** (H2): granite3.3:8b, and the hosted
   Qwen 27B as the benchmark's other side, replayed on the campaign's evidence. The
   misreads are now the larger loss.
4. **Review the labels** (M4). Every figure above is against labels mostly the AI
   pass's, and only the author can review them.

## What this audit did not cover

- Admission, the writer, the reader, the graph, deployment and security beyond
  fact-checking.
- The test half: sealed while the campaign is active.
- Any hosted model.
- More than 10 live claims and one live article. The 10-claim comparison of the
  two query plans is an observation, not a measurement: two searches, 10 claims.

# Evaluation

> Referenced from CLAUDE.md's Navigation table. Read it before working on
> the evaluation harness, its metrics, or anything the paper reports a
> number from.

**Status, 2026-10-01: designed, not built.** None of the code below
exists yet. This file fixes the decisions the harness goals share (the
record format, the run layout, what is reported apart, how a wrong
verdict is attributed to a stage) so that seven separately-run goals
agree on them. The goals themselves are in `docs/goals.md`. When a goal
lands, it rewrites its section here in the past tense, with what was
built and what it measured, like every other file in this folder.

## Research questions

Proposed on Sep 29; the first goal settles them (by Oct 13), writes them
into `docs/final_document/sections/research_questions.tex`, and keeps
this table in step with it. Whatever answers none of them is cut or
moved to future work.

| RQ | Question | Answered by | Data |
|---|---|---|---|
| RQ1 | How well does an open-web, low-cost pipeline verify claims from constructive news in Spanish and English, against a temporally sound gold set? | Accuracy and macro-F1 with bootstrap intervals; coverage and accuracy on definitive verdicts | Custom set (headline), x-fact pilot (baseline) |
| RQ2 | Where does it fail: retrieval, ranking or reasoning? | Reference-link recall at each depth; every wrong verdict attributed to a stage | Both sets |
| RQ3 | How much of the verification work does it take off a journalist? | Claim selector's precision; time per fact; share of verdicts usable without re-checking | Labelling queue, labeller timings, custom set |

## How one claim is run

Through `FactChecker.check_claim`, the stage `POST /verify-claim` runs,
so the harness measures the pipeline and not a copy of it. The claim is
built by `ClaimService.build_claim` (the same GLiNER pass, confidence
1.0, as the endpoint).

Two gaps have to close before a single number means anything. Both are
in the harness goal:

- **`check_claim` takes no `language`.** The query builder then falls
  back to English (`query_builder.py`, `(language or "en")`), so the 40
  Spanish pilot claims would be searched with the English lexicon.
- **`check_claim` takes no `context`.** For the custom set, the article
  the claim came from would then be retrieved as evidence for its own
  claim. That incident is why `EvidenceRetriever` drops the article's own
  URL, which it can only do when `context.url` is set.

So `check_claim` gains two optional keyword arguments, `context` and
`language`, passed through to `_check_claim`. Existing callers do not
change. The harness passes:

| Set | `language` | `context` |
|---|---|---|
| Custom | the row's | `ArticleContext(url=articleUrl, title="", lead="", keywords=[], entities={})` |
| x-fact | the row's | none |

x-fact gets no context on purpose. The harness hands the pipeline
nothing from the gold row that the production pipeline would not have,
and the fact-checker's own page is dealt with as a measured leak (below),
not by hinting it away.

**The model** is a constructor argument, not an `.env` edit per run:
`FactChecker(repo, verifier=LLMVerifier(client=LLMClient(model=M)))`.

**Thresholds** default to `PipelineThresholds()`; `--thresholds f.json`
resolves through `PipelineThresholds.resolve`, as a request would. The
effective set is written into the run's manifest.

**The internal corpus** comes from a copy, not from the live store.
`QdrantClient`'s local mode takes an exclusive file lock, held by any
running backend. The live store also grows with every ingestion, so a run
against it cannot be repeated. `--corpus snapshot` (the default) copies
`data/vector_db` into the run directory at start and records its point
count. `--corpus none` opens an empty store: web only, for the ablation.

**Concurrency.** Claims go through `bounded_map` at
`settings.CLAIM_MAX_CONCURRENCY`. The per-service ceilings inside each
client still hold. Each result is written as soon as it finishes, under
a lock, so input order is irrelevant to the file: records are keyed by
id.

## Record format

`results.jsonl` holds one line per claim. No scraped body is stored
(`Evidence.content` is left out), the same rule
`progress.source_summary` follows for events.

| Field | Content |
|---|---|
| `id` | The custom set's `id`. For x-fact, which has none: `xf-` plus the first 12 hex digits of sha1(`language`, `site`, `claim`). That is unique for all 64 pilot rows; the loader refuses a duplicate. |
| `dataset`, `language`, `site`, `claim`, `claimDate`, `label`, `labelRaw`, `referenceEvidenceLinks` | Copied from the row, so a report needs nothing else. `claimDate` is `null` for x-fact's `"none"`. |
| `status`, `error` | `ok` or `error`; on error, the exception type and message. |
| `verdict`, `rawVerdict`, `confidence`, `rawConfidence` | From the `FactCheck`. `raw*` is the LLM's answer before `ConfidenceScorer`. |
| `reachedStage`, `stageNote`, `searchUnavailable`, `llmUnreachable` | From the `FactCheck`. |
| `queries` | `[{text, kind}]`, from the `searching_web` event (anchor / proposition / refutation). |
| `candidates` | Every source seen: `evidence` plus `rejected_sources`, each as `{url, domain, title, origin, stoppedAt, reason, score}`. `stoppedAt` is `ranked` or the stage that dropped it (`evidence_retrieval`: funnel, same domain, own article; `evidence_ranking`: pertinence gate, cap; `llm_verification`: not cited). |
| `evidence` | The ranked list in index order: `{url, domain, title, publishedAt, relevance, semantic, lexical, recency, reliability, reliabilityKnown, pertinence, stance, cited, quote, engines, foundBy}`. |
| `citedIndices`, `evidenceCount`, `independentDomains` | From the `FactCheck`. |
| `events` | The `on_phase` trace: `[{phase, t, data}]`, `t` in seconds since the claim started. |
| `latency` | `total` and per stage, from the events: retrieval (`retrieving_evidence` → `evidence_retrieved`), ranking (→ `evidence_ranked`), LLM (`verifying_claim` → `claim_checked`). |
| `model`, `thresholdsHash`, `harnessVersion`, `gitCommit`, `startedAt`, `finishedAt` | Provenance. |

## Run layout, cache and resume

```
backend/data/evaluation/runs/<dataset-stem>/<model-slug>/<key>/
    run.json        manifest
    results.jsonl   one line per claim
    vector_db/      the corpus snapshot
```

- **`key`** is the first 12 hex digits of sha256(dataset file sha256,
  model, effective thresholds, corpus mode, `HARNESS_VERSION`). The git
  commit is recorded on every record, not keyed: keying it would throw a
  run away on every commit. A change that alters results bumps
  `HARNESS_VERSION`, the same discipline as `AnalysisCache.SCHEMA_VERSION`.
- **The manifest** holds the dataset path and sha256, the model, the
  full thresholds, corpus mode and point count, the git commit at start,
  `HARNESS_VERSION`, `SEARXNG_URL`, `LLM_BASE_URL`, `LLM_TIMEOUT`, the
  concurrency settings and the start time.
- **Resume.** On start, the runner reads `results.jsonl`. Ids with
  `status: ok` are done and are not re-run. Errors are retried. A torn
  last line, from a crash mid-write, is ignored and its claim re-run.
  `--retry-unavailable` also re-runs `searchUnavailable` and
  `llmUnreachable` claims: those are infrastructure outcomes, and the
  search fix exists to change them. `--fresh` starts a new file. Each
  write is one line, then flush, then `os.fsync`.
- **What is committed.** `runs/` is gitignored: it is raw, it holds
  third-party titles and quotes, and the corpus snapshot is large. The
  report (`metrics.json`, `report.md` and a copy of `run.json`) goes to
  `backend/data/evaluation/reports/<dataset-stem>/<model-slug>/<key>/`
  and is committed. Those are the numbers the paper quotes, next to the
  manifest that produced them.

## What is reported apart

Each claim gets exactly one outcome. Only `scored` claims enter the
headline metrics.

1. `error`: the harness or the pipeline crashed. It is retried; any
   still left at report time are listed by id.
2. `searchUnavailable`: no web query was answered. On Sep 25, 68 of 69
   searches came back empty; folded into the error rate, that measures
   SearXNG's uptime.
3. `llmUnreachable`: the model was never reached.
4. `scored`: everything else.

On top of the outcome, two flags. Metrics are reported on all scored
claims and on scored claims without the flagged ones:

- **`temporalLeak`** (the guide's Rule 3): a *cited* source has a
  `publishedAt` after `claimDate`. Ranked-but-uncited newer sources are
  counted, not flagged. The flag is undetermined when either date is
  missing: that is every one of the 40 chequeado.com pilot rows, which
  have no `claimDate`.
- **`verdictLeak`** (x-fact only): a ranked source is on the row's own
  `site`, the fact-checker that published the verdict. All 40 chequeado
  rows list chequeado's own article among their reference links. A
  verdict read off the fact-checker's page is the answer retrieved, not
  a claim verified.

**Not decided: whether to exclude the fact-checkers' domains at
retrieval time.** Measure first: the pilot says how often it happens.
Excluding would be a pipeline change, a per-run `evidence_exclude_domains`
in `PipelineThresholds`, with its own goal and its own cache bump.

## Metrics

- **Classes** are the five `Verdict` values, in this order: `TRUE`,
  `PARTIALLY_TRUE`, `MISLEADING`, `FALSE`, `UNVERIFIED`.
- **Accuracy, macro-F1, and per-class precision, recall, F1 and
  support.** Macro-F1 averages over the classes present in the gold
  labels. A class with no gold support is shown with its predictions, not
  averaged in: the custom set has no `FALSE` yet (27 of 37 facts are
  `TRUE`).
- **Confusion matrix**, gold rows by predicted columns.
- **Coverage and selective accuracy**: the share of definitive verdicts
  (not `UNVERIFIED`), and the accuracy among them. `UNVERIFIED` is the
  system's commonest answer with a small local model, and plain accuracy
  hides that.
- **Bootstrap intervals**: percentile 95% CIs over claims, 10,000
  resamples, seeded, with the seed in the report. Two runs over the same
  claims (model A against B, before and after the search fix) are
  compared with a **paired** bootstrap: the interval of the difference,
  not two intervals that happen to overlap. At 150 claims and 50%
  accuracy, the interval is about ±8 points (`custom_dataset.tex`).
- **Breakdowns**: by language for both sets; by topic group,
  `claimType` and `sourceTier` for the custom set; by site for x-fact.
- **Pure Python.** No new dependency for arithmetic this small. Every
  metric is tested against hand-computed values: a wrong metric is a
  wrong paper (roadmap, testing track, November).

## Retrieval evaluation (RQ2)

Did the system find what the annotator found?

- **URLs are normalised with the retriever's own `_comparable`**
  (`evidence_retriever.py`): host without `www.`, path without a trailing
  slash, lower case, query dropped. It is imported, not copied, so
  "found" means what the pipeline means by it. Domains are compared the
  way `Evidence.domain` is computed.
- **The reference set** is `referenceEvidenceLinks`. For x-fact, links
  on the row's own `site` are removed: they are the verdict, counted as
  `verdictLeak`.
- **Per claim, at three depths** (candidates, ranked, cited): was a
  reference *link* found, and was a reference *domain* found.
- **Reported**: link and domain recall at each depth, by set and
  language. The drop from candidates to ranked is what ranking cut, with
  the cut reasons listed.
- **A miss is not proof of failure.** Another source can be as good as
  the annotator's. That is why domain hits are reported beside link hits,
  and why the stage attribution below says which rule produced it.

## Stage attribution (RQ2)

Each scored claim whose verdict differs from the gold label gets one
stage, the first that matches. It is computed twice, because the
reference links are the better witness but not every row has them (an
`UNVERIFIED` gold label needs none):

| Stage | Reference-based (row has reference links) | Trace only |
|---|---|---|
| retrieval | no reference link or domain among the candidates | no candidates at all |
| ranking | a reference hit among the candidates, none ranked (cut by the funnel, same-domain, the pertinence gate or the cap; the reason is in `candidates`) | candidates, but nothing ranked |
| reasoning | a reference hit is ranked, and `rawVerdict` differs from gold | something ranked, and `rawVerdict` differs from gold |
| aggregation | `rawVerdict` equals gold, the final verdict does not: `ConfidenceScorer` changed it (evidence floor, nothing cited, only unrelated sources cited, a contradiction) | same |

Both columns are reported, with counts, shares and claim ids, and the
claims on which they disagree are listed. Under the reference rule, a
wrong verdict resting on sources other than the reference counts as
retrieval: the decisive source was never found. Claims set apart above
(`searchUnavailable`, `llmUnreachable`, `error`) are never attributed.

Everything here is read from fields the record already holds. No new
pipeline output is needed.

## Journalist effort (RQ3)

- **Claim selector's precision**: labelled / (labelled + skipped) over
  every batch in `backend/data/evaluation/queue/`, by skip reason and by
  language. `labeller/app.py`'s `Queue.stats()` already computes the
  total. The first six facts were chosen by hand before the daily batch
  existed (no batch refers to them) and are excluded.
- **Time per fact**: the labeller records `timing: {openedAt, savedAt,
  activeSeconds}`, from the moment a fact's form opens (Label in Today,
  or New) to its save. Only seconds with the page visible count, or a
  lunch break becomes a one-hour fact. It is kept on re-save, written
  after the existing keys (the labeller's test pins x-fact's ten keys and
  their order, not the tail). Facts saved before the change have none;
  reported as n, median and interquartile range.
- **Usable without re-checking**: the share of scored claims whose
  verdict equals gold, is not `UNVERIFIED`, cites at least one source
  with a stance, and has neither leak flag. Its counterpart,
  **confidently wrong**: a definitive verdict that differs from gold.
  That is what a journalist who trusted the system would publish.
- **Effort estimate**: usable share × median time per fact, in minutes
  saved per 100 claims, beside the confidently-wrong share as the cost of
  trusting it. Stated as an estimate, with its assumptions.

The labeller owns the first two (standard library only, nothing from
`backend/`): `python labeller/app.py stats` prints them as JSON. The
harness report owns the last two, since they need the results.

## Where it runs

The harness needs `inference/`, SearXNG and the LLM, like any analysis.

- **On the host**: `inference/` must be reachable at `INFERENCE_URL`, and
  compose does not publish port 8001. Run `cd inference && uv run
  uvicorn src.main:app --port 8001` first.
- **In compose**: `docker compose run --rm backend uv run python -m
  src.evaluation.cli ...`, which reaches the services on the compose
  network. `data/` is dockerignored and `data/evaluation/` is not in the
  `backend-data` volume, so the pilot goal mounts `backend/data/evaluation`
  into the service.
- **On a CPU**, use the production LLM limits (`LLM_TIMEOUT`,
  `LLM_MAX_CONCURRENCY` in `docker-compose.prod.yml`). The dev limits
  turned 3 of 4 verdicts into `llmUnreachable` (CLAUDE.md, "Known dead").
- **Cost**: the LLM took ~45 s per claim on CPU in the production run, so
  64 claims is roughly an hour at one claim at a time, plus search.
- **Check search first.** Read `/healthz` and the Source health panel on
  `/scraper` before a run, and record what they said in the report.

## Code layout

`backend/src/evaluation/`, a namespace package like the rest of `src/`
(no `__init__.py`, invariant 7):

| Module | Goal | Holds |
|---|---|---|
| `dataset.py` | harness | Loading both formats, ids, duplicate check |
| `record.py` | harness | The record model above, `HARNESS_VERSION` |
| `runner.py` | harness | Building the checker, running, resuming, writing |
| `cli.py` | harness, then each goal | `run`, `report [--compare]` |
| `metrics.py`, `report.py` | metrics | Partitions, metrics, bootstrap, `metrics.json`, `report.md` |
| `retrieval.py` | retrieval | Reference hits and recall |
| `attribution.py` | attribution | The stage table above |
| `effort.py` | effort | Usable and confidently-wrong shares |

Run as `cd backend && uv run python -m src.evaluation.cli run --dataset
data/evaluation/xfact_en_es_pilot.jsonl --model llama3.2:3b [--limit N]
[--thresholds f.json] [--corpus snapshot|none] [--retry-unavailable]
[--fresh]`, then `... report --run <dir> [--compare <dir>]`.

Tests live in `backend/tests/evaluation/` and use only fakes
(`tests/services/fact_checker/fakes.py`; a new shared fake needs its
contract entry, invariant 10) and `tmp_path` (invariant 9). No test
reaches a live service; the pilot is the live run.

## Pilot

Not run yet. The pilot goal records here what it measured, and every
harness bug it found.

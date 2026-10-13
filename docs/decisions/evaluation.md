# Evaluation

> Referenced from CLAUDE.md's Navigation table. Read it before working on
> the evaluation harness, its metrics, or anything the paper reports a
> number from.

**Status, 2026-10-13: the harness (G2), metrics (G3) and retrieval
evaluation (G4) are built, and the pilot (G7) has run them against live
services (§Pilot).** Stage attribution (G5) and journalist effort (G6)
are not built: there is no `attribution.py` or `effort.py` yet.

**Status, 2026-10-01: designed, not built.** None of the code below
existed yet. This file fixes the decisions the harness goals share (the
record format, the run layout, what is reported apart, how a wrong
verdict is attributed to a stage) so that seven separately-run goals
agree on them. The goals themselves are in `docs/goals.md`. When a goal
lands, it rewrites its section here in the past tense, with what was
built and what it measured, like every other file in this folder.

## Research questions

Proposed on Sep 29; the first goal settles them (by Oct 13), writes them
into `docs/final_document/chapters/06-experimental-design/01-research-questions-metrics.tex`, and keeps
this table in step with it. Whatever answers none of them is cut or
moved to future work.

| RQ | Question | Answered by | Data |
|---|---|---|---|
| RQ1 | How well does an open-web, low-cost pipeline verify claims from constructive news in Spanish and English, against a temporally sound gold set? | Accuracy and macro-F1 with bootstrap intervals; coverage and accuracy on definitive verdicts | Custom set (headline), x-fact pilot (baseline) |
| RQ2 | Where does it fail: retrieval, ranking or reasoning? | Reference-link recall at each depth; every wrong verdict attributed to a stage | Both sets |
| RQ3 | How much of the verification work does it take off a journalist? | Claim selector's precision; time per fact; share of verdicts usable without re-checking | Labelling queue, labeller timings, custom set |

## How one claim is run

**Built on 2026-10-02 (G2)**: `backend/src/evaluation/runner.py`,
`dataset.py`, `record.py`, `store.py`, `cli.py`. Tested with the shared
fakes only (`backend/tests/evaluation/`); not yet run against live
services, which is the pilot's job.

Each claim went through `FactChecker.check_claim`, the stage
`POST /verify-claim` runs, so the harness measures the pipeline and not a
copy of it. The claim was built by `ClaimService.build_claim` (the same
GLiNER pass, confidence 1.0, as the endpoint).

Two gaps were closed first, because without them no number would have
meant anything:

- **`check_claim` took no `language`.** The query builder then fell back
  to English (`query_builder.py`, `(language or "en")`), so the 40
  Spanish pilot claims would have been searched with the English lexicon.
- **`check_claim` took no `context`.** For the custom set, the article the
  claim came from would then have been retrievable as evidence for its
  own claim. That incident is why `EvidenceRetriever` drops the article's
  own URL, which it can only do when `context.url` is set.

So `check_claim` gained two keyword-only, optional arguments, `context`
and `language`, passed through to `_check_claim`. `/verify-claim` passes
neither and is unchanged; no fake or contract pinned the signature. The
harness passes:

| Set | `language` | `context` |
|---|---|---|
| Custom | the row's | `ArticleContext(url=articleUrl, title="", lead="", keywords=[], entities={})` |
| x-fact | the row's | none |

x-fact gets no context on purpose. The harness hands the pipeline
nothing from the gold row that the production pipeline would not have,
and the fact-checker's own page is dealt with as a measured leak (below),
not by hinting it away. A test holds each row of this table.

**The model** is a constructor argument, not an `.env` edit per run:
`FactChecker(repo, verifier=LLMVerifier(client=LLMClient(model=M)))`.
**The provider is configuration only**: `LLM_BASE_URL`, `LLM_API_KEY`,
`LLM_TIMEOUT` and `LLM_MAX_CONCURRENCY`, read from the environment or
`backend/.env` as the API reads them. Ollama (the baseline) and Groq
differ by those variables alone; no flag names a provider. Every record
says who served it (`provider`, the host of `LLM_BASE_URL`).

**Thresholds** default to `PipelineThresholds()`; `--thresholds f.json`
resolves through `PipelineThresholds.resolve(ThresholdOverrides(...))`,
as a request would, so an unknown field is an error rather than a
silently ignored typo. The effective set is written into the manifest.

**The internal corpus** comes from a copy, not from the live store.
`QdrantClient`'s local mode takes an exclusive file lock, held by any
running backend, and the live store grows with every ingestion, so a run
against it could not be repeated. `--corpus snapshot` (the default)
copies `data/vector_db` into the run directory once, at the run's first
start, without the live `.lock` file, and records its point count; a
resumed run keeps the copy it started with. `--corpus none` opens an
empty store: web only, for the ablation.

**Concurrency.** Claims go through `bounded_map` at
`settings.CLAIM_MAX_CONCURRENCY`; the per-service ceilings inside each
client still hold. Each result is written as soon as it finishes, under a
lock, so input order is irrelevant to the file: records are keyed by id.

**Stopping.** The first Ctrl-C starts no new claim and lets those in
flight finish and be written; the second aborts. `bounded_map` waits for
every queued item before it returns, so without this a Ctrl-C an hour
into a run would have stopped nothing.

## Record format

`results.jsonl` holds one line per claim (`record.py`, `RECORD_FIELDS`
in write order). No scraped body is stored (`Evidence.content` is left
out), the same rule `progress.source_summary` follows for events. An
error record has every key too, empty, so a report never asks whether a
key exists.

| Field | Content |
|---|---|
| `id` | The custom set's `id`. For x-fact, which has none: `xf-` plus the first 12 hex digits of sha1(`language`, `site`, `claim`). Unique for all 64 pilot rows; the loader refuses a duplicate. |
| `dataset`, `language`, `site`, `claim`, `claimDate`, `label`, `labelRaw`, `referenceEvidenceLinks` | Copied from the row, so a report needs nothing else. `claimDate` is `null` for x-fact's `"none"`. `dataset` is `custom` or `xfact`, decided by whether the row has an `id`. |
| `articleUrl`, `topic`, `topicGroup`, `claimType`, `sourceTier` | Custom set only (`null` for x-fact): what the breakdowns need. `topicGroup` is the labeller's five groups; a test holds the backend's copy equal to the labeller's and every topic in `topics.py` to exactly one group. |
| `status`, `error` | `ok` or `error`; on error, the exception type and message. |
| `verdict`, `rawVerdict`, `confidence`, `rawConfidence`, `explanation` | From the `FactCheck`. `raw*` is the LLM's answer before `ConfidenceScorer`. |
| `invalidOutput` | The model answered but returned nothing usable after the JSON retry (`LLMVerifier`'s `INVALID_OUTPUT_EXPLANATION`). A format failure is a model-quality result, counted per model. |
| `reachedStage`, `stageNote`, `searchUnavailable`, `llmUnreachable` | From the `FactCheck`. |
| `queries` | `[{text, kind}]`, from the `searching_web` event (anchor / proposition / refutation). |
| `candidates` | Every source seen, **once**: `{url, domain, title, origin, stoppedAt, reason, score}`. `stoppedAt` is `ranked`, or the stage that cut it (`evidence_retrieval`: funnel, same domain, own article; `evidence_ranking`: pertinence gate, cap). Rejected sources carry no domain; it is computed with `registrable_domain`, as `Evidence.domain` is. |
| `evidence` | The ranked list in index order: `{url, domain, title, origin, publishedAt, relevance, semantic, lexical, recency, reliability, reliabilityKnown, pertinence, stance, cited, quote, engines, foundBy}`. |
| `citedIndices`, `evidenceCount`, `independentDomains` | From the `FactCheck`. |
| `events` | The `on_phase` trace: `[{phase, t, data}]`, `t` in seconds since the claim started, starting at `extracting_entities`. |
| `latency` | `total`, `entities` (building the claim) and per stage, from the events: `retrieval` (`retrieving_evidence` → `evidence_retrieved`), `ranking` (→ `evidence_ranked`), `llm` (`verifying_claim` → `claim_checked`; `null` when the model was not asked). |
| `usage` | The LLM calls this claim made (`usage.py`): `calls`, `failedCalls`, `promptTokens`, `completionTokens`, `usageMissing`, `latency` and `perCall`. See §Cost, latency and tokens. |
| `model`, `provider`, `thresholdsHash`, `harnessVersion`, `gitCommit`, `startedAt`, `finishedAt` | Provenance. `gitCommit` ends in `-dirty` when the tree had uncommitted changes, and in `-unchecked` when HEAD was read but the dirty check did not answer in time (since the pilot: `git status` over compose's bind mount takes ~5 s, and the old 5 s timeout lost a session's commit). `unknown` when there is no repository: the image alone has no `.git`, which `docker-compose.eval.yml` mounts. |

Changed from the design:

- **`stoppedAt: llm_verification` was dropped.** The design listed "not
  cited" as a stage a candidate stops at. A ranked source the model did
  not cite is still ranked: `FactCheck.rejected_sources` lists it as well,
  and taking both would have counted it twice. It is `ranked` in
  `candidates`, with `cited: false` in `evidence`.
- **Added**: the custom-set fields, `explanation`, `invalidOutput`,
  `usage`, `provider` and `latency.entities`.

## Run layout, cache and resume

```
backend/data/evaluation/runs/<dataset-stem>/<model-slug>/<key>/
    run.json        manifest
    results.jsonl   one line per claim, appended
    vector_db/      the corpus snapshot
```

- **`key`** is the first 12 hex digits of sha256(dataset sha256, model,
  effective thresholds, the environment's scoring weights, corpus mode,
  `HARNESS_VERSION`). The same command therefore resumes; changing any of
  the six starts a new run. The weights (`RANKING_*`, `PERTINENCE_*`,
  `CONFIDENCE_*`, `RANKING_DEFAULT_RELIABILITY`,
  `EVIDENCE_RECENCY_HALF_LIFE_DAYS`) were added to the design's key:
  they are environment-only, read once at import, and change what a run
  produces, so without them a run with a re-tuned weight would have
  "resumed" the run made before the change. The git
  commit is recorded on every record, not keyed: keying it would throw a
  run away on every commit. A change that alters results bumps
  `HARNESS_VERSION` (now 1), the discipline of
  `AnalysisCache.SCHEMA_VERSION`. The dataset sha256 of a directory
  (the custom set before `join`) covers every file's name and bytes, so
  editing a label starts a new run rather than mixing two gold sets.
- **The manifest** holds the key, the dataset (path, stem, sha256, rows,
  kinds), the model and provider, the full thresholds and those that
  differ from the defaults, the scoring weights, corpus mode and point
  count, the git commit
  at start, `HARNESS_VERSION`, the verifier prompt's sha256, `LLM_BASE_URL`
  (credentials stripped), `LLM_TIMEOUT`, `SEARXNG_URL`, `INFERENCE_URL`,
  the DuckDuckGo fallback switch, the concurrency settings and the start
  time. Each start appends a **session** (`startedAt`, `finishedAt`,
  commit, provider, flags, pending, ran, ok, errors, `stopped`,
  `tornLinesDropped`, `unattributedLlmCalls`, and since the pilot its own
  `settings`: endpoints, `LLM_TIMEOUT`, `INFERENCE_TIMEOUT` and the
  concurrency ceilings, none of which is keyed), so a resumed run keeps
  the first session's provenance and says how it was resumed.
- **Resume.** On start, the runner reads `results.jsonl`; the last record
  per id wins. Ids with `status: ok` are done and are not re-run. Errors
  are retried. A torn last line, from a crash mid-write, is cut from the
  file and its claim re-run (the next append would otherwise glue a new
  record onto the fragment). A damaged line that is not the last is not
  a torn write, and the run refuses to guess. `--retry-unavailable` also
  re-runs `searchUnavailable` and `llmUnreachable` claims: those are
  infrastructure outcomes, and the search fix exists to change them.
  `--fresh` moves the old file aside (`results.replaced-<time>.jsonl`)
  rather than deleting hours of model time. Each write is one line, then
  flush, then `os.fsync`, LF on every OS.
- **`--limit N`** is the first N rows of the dataset, not N more claims,
  so the same flag always means the same rows.
- **What is committed.** `runs/` is gitignored: it is raw, it holds
  third-party titles and quotes, and the corpus snapshot is large. The
  report (`metrics.json`, `report.md` and a copy of `run.json`) goes to
  `backend/data/evaluation/reports/<dataset-stem>/<model-slug>/<key>/`
  and is committed. Those are the numbers the paper quotes, next to the
  manifest that produced them.

Proven by `backend/tests/evaluation/test_harness_runner.py`: a run
stopped after claim k resumes without calling the checker for claims
1..k; a torn last line is re-run and cut; Spanish rows reach
`check_claim` with `language='es'`; custom rows pass `articleUrl` as
`context.url` and x-fact rows no context; every field above is filled
by the real retriever, ranker, verifier and scorer over the shared fakes.

## Cost, latency and tokens

**Built on 2026-10-02** (Sprint 6, "log cost/latency/quality trade-offs
per provider"; Phase 5's prerequisite of "a harness that records latency
and cost"): `backend/src/evaluation/usage.py`. Not measured yet: no
provider has been run.

- **Where it hooks in.** `LLMClient.complete_json` returns the parsed
  JSON and nothing else; the provider's `usage` block (prompt and
  completion tokens) is on the raw response, which never leaves the
  method. Rather than fork the client or change what it returns to every
  caller, the harness wraps the OpenAI SDK object the client already
  holds (`metered`). Everything the client decides (`max_retries=0`, the
  timeout, the LLM permit, the JSON retry) stays exactly as production
  has it: the benchmark measures the client the pipeline uses.
- **Per claim.** Claims run on their own threads and a claim's one LLM
  call is made on that thread, so each worker opens a meter block around
  its claim and every call on the thread lands on that claim's record
  (`usage`: calls, failed calls, prompt and completion tokens, calls that
  reported no usage, the provider's answer time, and each call). A call
  made anywhere else is not lost: it is counted in the session's
  `unattributedLlmCalls`, which stays 0 unless the pipeline moves its LLM
  call off the claim's thread. A JSON retry is two calls and is billed as
  two; a model that fails the format costs more, and the record says so.
- **Two latencies, on purpose.** `usage.latency` is the provider's own
  answer time, measured inside the LLM permit; `latency.llm`, from the
  events, also includes waiting for the permit. The gap is a busy model,
  not a slow one.
- **Per run.** `totals` sums any set of records: calls, failed calls,
  tokens (and per claim, over the claims that reported tokens), the LLM's
  seconds, call latency (median, p90, max), claim latency (median, p90,
  total) and completion tokens per second, which is what tells a fast
  provider from a slow one. Each session in `run.json` carries its own
  totals; the report carries the run's.
- **Unknown is not zero.** A server behind an OpenAI-shaped URL may send
  no `usage`; its tokens are `null` and `usageMissing` counts the calls,
  rather than a mean of zeros passing for a cheap model.
- **Cost** is priced at report time from `backend/data/evaluation/prices.json`
  (`--prices`), keyed by model or by `provider/model` when one name is
  served by two hosts. The user fills in a hosted price from the
  provider's page on the day of the run, with `asOf`: per-token prices
  change, and a remembered one is not a price. A `null` price, or unknown
  tokens, gives `n/a`, never 0. The local Ollama models are priced at 0
  explicitly; their cost is the wall time, reported beside it.

**Swapping provider is configuration only.** The same command, two
environments:

```bash
# Baseline: local Ollama, CPU limits from docker-compose.prod.yml
LLM_TIMEOUT=180 LLM_MAX_CONCURRENCY=1 \
  uv run python -m src.evaluation.cli run --dataset <set> --model llama3.2:3b

# Hosted: Groq's OpenAI-compatible endpoint
LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_API_KEY=<key> \
  uv run python -m src.evaluation.cli run --dataset <set> --model <groq model id>
```

`provider` on each record is the host of `LLM_BASE_URL`
(`localhost:11434`, `api.groq.com`). A hosted provider's rate limit
(HTTP 429) reaches `LLMClient` as an API error, so a throttled claim
comes back `llmUnreachable`, is set apart from the scored ones, and is
re-run by `--retry-unavailable`. Verdict JSON uses
`response_format={"type": "json_object"}`, which both Ollama and Groq's
OpenAI-compatible endpoints accept.

## What is reported apart

**Built on 2026-10-02 (G3)**: `backend/src/evaluation/metrics.py`
(`outcome`, `temporal_leak`, `verdict_leak`, `newer_uncited`).

Each claim got exactly one outcome, the first that applies. Only
`scored` claims enter the headline metrics.

1. `error`: the harness or the pipeline crashed. It is retried; any
   still left at report time are listed by id.
2. `searchUnavailable`: no web query was answered. On Sep 25, 68 of 69
   searches came back empty; folded into the error rate, that would have
   measured SearXNG's uptime. A claim whose search failed is set apart
   even when the internal corpus gave it a verdict: the web, which the
   pipeline is about, was never asked.
3. `llmUnreachable`: the model was never reached (a hosted provider's
   rate limit lands here too).
4. `scored`: everything else.

On top of the outcome, two flags. Metrics are reported on all scored
claims and on scored claims without the flagged ones:

- **`temporalLeak`** (the guide's Rule 3): a *cited* source has a
  `publishedAt` after `claimDate`, compared by day (same day is not
  after). Ranked-but-uncited newer sources are counted, not flagged. The
  flag is undetermined when the claim has no date (every one of the 40
  chequeado.com pilot rows) or when a cited source has none and no dated
  one is newer.
- **`verdictLeak`** (x-fact only): a ranked source is on the row's own
  `site` or a subdomain of it, the fact-checker that published the
  verdict. All 40 chequeado rows list chequeado's own article among their
  reference links. A verdict read off the fact-checker's page is the
  answer retrieved, not a claim verified. Not applicable to the custom
  set, whose `site` is the article's publisher.

Also counted, per model, and scored as the `UNVERIFIED` it became:
**`invalidOutput`**, the model answering without usable JSON.

**Whether to exclude the fact-checkers' domains at retrieval time** was
left to the pilot to measure. It did (§Pilot): the row's own
fact-checker was ranked for 9 of 64 claims, all English, and never for a
Chequeado row. The recommendation, not implemented, is in
`xfact-comparison.md`: a per-run `evidence_exclude_domains` in
`PipelineThresholds` for benchmark runs on fact-checker datasets only,
with its own goal and its own cache bump.

## Metrics

**Built on 2026-10-02 (G3)**: `metrics.py` and `report.py`, `cli report
--run <dir> [--compare <dir>] [--prices f] [--seed n] [--resamples n]`
and `cli table --run <dir> --run <dir> ...`. Pure Python, no new
dependency. Not yet run on real results.

- **Classes** are the five `Verdict` values, in this order: `TRUE`,
  `PARTIALLY_TRUE`, `MISLEADING`, `FALSE`, `UNVERIFIED`.
- **Accuracy, macro-F1, and per-class precision, recall, F1, support and
  predicted count.** Macro-F1 averages over the classes present in the
  gold labels. A class with no gold support is shown with its
  predictions (precision, but no recall and no F1), not averaged in: the
  custom set has no `FALSE` yet (27 of 37 facts are `TRUE`). Precision is
  undefined for a class never predicted; F1 is 0 for a class with
  support of which nothing was got right.
- **Cohen's kappa against gold** (added): the labeller's own
  self-agreement statistic, so the system and the annotator are compared
  on one scale. This is the "verdict agreement vs. the human-labelled
  set" of Sprint 7. Undefined when chance agreement is total.
- **Confusion matrix**, gold rows by predicted columns.
- **Coverage and selective accuracy**: the share of definitive verdicts
  (not `UNVERIFIED`), and the accuracy among them.
- **Bootstrap intervals**: percentile 95% CIs over claims, 10,000
  resamples, seeded (default 2026), with the seed in the report. All five
  statistics come from one set of resamples. Records are ordered by id
  before resampling, so the same run gives the same interval however its
  claims finished. The class set macro-F1 averages over is the full
  sample's, so the statistic means the same thing in every resample; a
  resample in which a statistic is undefined (no definitive verdict, for
  selective accuracy) is skipped for it and counted. Percentiles
  interpolate linearly, numpy's default, so the numbers can be
  re-computed with numpy. 10,000 resamples over the 14-claim fixture,
  headline, breakdowns and a comparison, took 0.9 s.
- **Paired comparison** (`--compare <baseline>`): the interval of the
  difference B − A over the claims both runs scored, resampled together:
  model A against B, or before and after the search fix. A claim set
  apart on either side is left out of both and counted, as are claims
  only one run has. Alongside: how many claims only A got right and how
  many only B did. Comparing a run with itself gives exactly 0, interval
  [0, 0], which a test holds.
- **Breakdowns**: by language for both sets; by topic group, `claimType`
  and `sourceTier` for the custom set; by site for x-fact. Each with n,
  accuracy and its interval, macro-F1, coverage and selective accuracy.
- **Several models** (`cli table`): one row per run over the same
  dataset (refused otherwise): accuracy and macro-F1 with intervals,
  coverage, selective accuracy, kappa, invalid outputs, claims set apart,
  median seconds per claim, completion tokens per claim, tokens per
  second and cost per 100 claims, into `reports/<dataset>/models.md`.
  This is the Sprint 7 verification-model comparison, run once per model.
- **Tested** against hand-computed values on a ten-claim fixture built
  with `record.py` (`tests/evaluation/test_harness_metrics.py`, every
  figure worked out in its docstring and comments), plus bootstrap
  determinism under a fixed seed, the paired bootstrap on identical runs
  (difference 0), and `report.md` rendered from a fixture run.

The report (`report.md`, with `metrics.json` and a copy of `run.json`)
has: the headline on all scored claims and without the flagged ones;
what was set apart, by id; the two flags; per class; the confusion
matrix; each breakdown; cost, latency and tokens; and the paired
comparison when asked for.

## Retrieval evaluation (RQ2)

**Built on 2026-10-04** (G4): `backend/src/evaluation/retrieval.py`, a
`## Retrieval` section in every `cli report`, paired retrieval
differences in every `--compare`, and `cli retrieval` for strategies side
by side. Tests: `backend/tests/evaluation/test_retrieval.py`. Not run on
a full set yet.

Did the system find what the annotator found - and, for any set, how
much and how fast did it find anything?

- **URLs are normalised with the retriever's own `_comparable`**
  (`evidence_retriever.py`): host without `www.`, path without a trailing
  slash, lower case, query dropped. It is imported, not copied, so
  "found" means what the pipeline means by it. Domains are compared the
  way `Evidence.domain` is computed (`registrable_domain`).
- **The reference set** is `referenceEvidenceLinks`. For x-fact, links
  on the row's own `site` are removed: they are the verdict. They are
  counted (`selfLinksRemoved`), and ranking one is `verdictLeak`.
- **Per claim, at three depths** (every candidate seen, the ranked
  evidence the model was shown, the evidence it cited): was a reference
  *link* found, and a reference *domain*; and the reciprocal rank of the
  first one in the ranked list (`linkMRR`, `domainMRR`).
- **Without references**, for any set: claims with any ranked evidence,
  candidates and ranked sources per claim, the share cut at ranking (the
  pertinence gate and the cap), distinct domains among the ranked, the
  share from rated domains and from the internal corpus, `verdictLeak`,
  retrieval and ranking seconds, queries per claim, and which query kind
  (anchor, proposition, refutation) found each ranked source.
- **Reported**: each as a mean over claims with a 95% percentile
  bootstrap interval, by set and language, and the cut reasons of
  references that were found and then cut - the drop between depths.
  Claims whose search failed, and errors, are counted and left out.
- **A miss is not proof of failure.** Another source can be as good as
  the annotator's. That is why domain hits are reported beside link hits,
  and why the stage attribution below says which rule produced it.

**Comparing strategies.** A strategy is a run: its thresholds
(`--thresholds`), its corpus (`--corpus snapshot|none`), its environment
(engines, `DUCKDUCKGO_FALLBACK_ENABLED`) or its code at a commit, named
with `--label`. The label is part of the run key, so two code variants
run with the same settings are two runs, not one resumed. Mode and label
enter the key only when set: a full, unlabelled run keeps its old key.

```bash
# Cheap: --retrieval-only stops before the model (a stand-in verifier,
# no call), so a strategy costs its search and fetch time only.
uv run python -m src.evaluation.cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl \
    --retrieval-only --label baseline
uv run python -m src.evaluation.cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl \
    --retrieval-only --label no-gate --thresholds no_gate.json   # {"evidence_min_pertinence": 0.0}
uv run python -m src.evaluation.cli retrieval --run <baseline dir> --run <no-gate dir>
```

`cli retrieval` writes `reports/<set>/retrieval.md` and `.json`: one row
per strategy (what differs: label, mode, overridden thresholds, corpus,
DuckDuckGo fallback, commit), then each later strategy minus the first,
paired over the claims both searched, with its interval and how many
claims only one side found a reference for. A claim whose search failed
on either side is left out of both: an outage is not a strategy. A
retrieval-only run's report has no verdict metrics, and `cli table`
refuses one.

**Live check, 2026-10-04**, on the first 6 pilot claims, two
retrieval-only strategies (`baseline`, and `no-gate`:
`evidence_min_pertinence` 0.0), corpus `none`, with Google and Brave
suspended in SearXNG and the rest answering (70-90 results a query):
0 LLM calls, ~80 s a run. `no-gate` ranked 2.2 more sources and 2.2 more
distinct domains a claim (paired interval +0.8 to +3.3), with a slightly
smaller share from rated domains. Reference recall was 0% for both, and
genuinely so: the 2 PolitiFact rows have only `<LINK NOT AVAILABLE>`
references (now counted as `referencesUnavailable`), and the chequeado
rows' references are mostly Facebook and Twitter posts, which no web
search returns. On the full pilot, expect link recall near zero and read
domain recall and the gold-free metrics instead.

**Found by it:** two Spanish claims' searches returned adult sites
(pornhub, xhamster, xnxx, chaturbate: 16 candidates). One claim's anchor
query was the single word "provincia". The gate and the funnel cut all of
them, so none was ranked, but they took candidate slots a real source
could have had. SearXNG runs with no `safe_search` setting. Two candidate
strategies to measure with this harness rather than adopt untested:
`safesearch=1` on every query, and refusing an anchor query of one word.

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

## Writing-model benchmark

**Built on 2026-10-04** (Phase 5, Sprint 6): `backend/src/evaluation/writing.py`,
tests in `backend/tests/evaluation/test_writing.py`. Not run yet: no
model has been benchmarked.

**What is benchmarked.** The corrector does not write, it judges: five
scores and a summary each (grammar, factConsistency, seo,
hallucinationIndex, style) from one LLM call. Readability and
coverageVerification are deterministic and do not depend on the model.
So a model is benchmarked as an editor, by running the corrector's own
`TextCorrector.llm_metrics`, prompt included; a copy of the call would
measure the copy. The run records the prompt's sha256, and a comparison
refuses runs made with different prompts.

**Why planted defects, not human scores.** A human score for "how good
is this text's SEO" is an opinion per text; a planted defect is a fact.
`backend/data/evaluation/writing/texts_en_es.jsonl` is six short news
texts (three English, three Spanish, written for this set), each in a
clean version and five versions with exactly one defect aimed at one
metric:

| Variant | Targets | The defect |
|---|---|---|
| `grammar` | grammar | agreement, spelling and tense errors |
| `contradiction` | factConsistency | a figure or date that contradicts an earlier one |
| `fabrication` | hallucinationIndex | an invented authority and sweeping claims |
| `seo` | seo | a vague headline; the subject gone from the lead |
| `style` | style | a casual, repetitive, exclamatory register |

Each defect version against its clean text is a pair whose right answer
is known: the targeted score should go down. 30 pairs, 15 per language.

**The rubric**, in the order a model is judged:

1. **Format compliance**: the share of judged texts for which all five
   metrics came back usable. A metric the model left out, or whose score
   is missing or not a number, is *unusable* - the corrector shows
   "Evaluation unavailable" for it - and is never averaged as a 0. A
   model below 95% is out, whatever it scores when it complies: the
   editor would see "unavailable" on one text in twenty. 95% is reasoned,
   not fitted.
2. **Detection**: per pair, 1 when the defect version scored lower on
   the targeted metric, 0.5 on a tie, 0 when higher, so a model that
   gives every text the same score sits at 0.5 (chance), not 0. Reported
   overall with a 95% percentile bootstrap interval over pairs, per
   metric (with the mean drop) and per language. A pair with no usable
   score on either side is *unscorable*, counted, and kept out of the
   mean.
3. **Defect named**: the share of defect texts whose targeted metric's
   summary or issues name the defect, matched against the text's
   `mentions`: whole words or phrases, case-insensitive; a trailing `*`
   makes a stem (`repetit*`); an all-capitals mention (`WHO`, `OMS`) is
   matched as written. A test holds that no mention quoted from a defect
   text also matches its clean text: before that rule, "WHO" matched
   every "who" and "a probado" matched inside the correct "ha probado".
4. **Off-target drift** (lower is better): the mean absolute change, on
   the four metrics a defect was not aimed at. A model that drops
   everything when anything is wrong detects well and diagnoses badly.
5. **Consistency** (lower is better): with `--repeats 2` or more, the
   mean range (max - min) of a text's score across repeats. Temperature
   is 0, and local models still vary.
6. **Calibration**, read rather than ranked: each metric's mean score on
   the clean texts. A model that scores clean, careful copy at 40 is
   harsh, which is a product problem even when it ranks pairs right.
7. **Cost and latency** decide between models the rubric cannot
   separate: median seconds per text, completion tokens per text and per
   second, and cost per 100 texts from `prices.json` (`n/a` without a
   price, never 0).

**Comparing models.** The first `--run` is the baseline (the local
Ollama model). Each later run gets the paired difference in detection
over the pairs both scored, with its interval. Two models whose paired
interval includes 0 are not separated by this set, and the cheaper or
faster one is chosen. With 30 pairs an interval of roughly ±15 points
is expected, so only large differences will show.

**What it does not measure.** Whether a model's scores agree with an
editor's on real copy; whether its summaries are *useful*; the two
deterministic metrics; and anything about writing, since the corrector
writes nothing.

```bash
cd backend
# Baseline, local (CPU limits as for the harness)
LLM_TIMEOUT=180 LLM_MAX_CONCURRENCY=1 \
  uv run python -m src.evaluation.cli writing run --model llama3.2:3b --repeats 2
# Hosted, same command, different environment
LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_API_KEY=<key> \
  uv run python -m src.evaluation.cli writing run --model <groq model id> --repeats 2
# The comparison, baseline first
uv run python -m src.evaluation.cli writing report \
  --run data/evaluation/writing/runs/texts_en_es/<model>/<key> --run ... \
  --prices data/evaluation/prices.json
```

A run is resumable exactly like the harness's: one fsynced line per
(text, repeat), keyed by the text set's sha256, the model, the prompt's
sha256 and `WRITING_VERSION`; units that errored or found the provider
unreachable run again; raising `--repeats` later adds repeats to the same
run. Raw runs go to `data/evaluation/writing/runs/` (gitignored); the
comparison the paper quotes, `comparison.md` and `comparison.json`, to
`data/evaluation/writing/reports/<set>/` (committed).

## Where it runs

The harness needs `inference/`, SearXNG and the LLM, like any analysis.

- **On the host**: `inference/` must be reachable at `INFERENCE_URL`, and
  compose does not publish port 8001. Run `cd inference && uv run
  uvicorn src.main:app --port 8001` first.
- **In compose** (how the pilot ran, 2026-10-13): layer
  `docker/docker-compose.eval.yml` and use `run`, never `up`:

  ```bash
  cd docker
  docker compose -f docker-compose.yml -f docker-compose.eval.yml \
    --env-file ../backend/.env run --rm --no-deps -T backend \
    python -m src.evaluation.cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl \
      --model llama3.2:3b
  ```

  The layer mounts `backend/data/evaluation` (dockerignored, and not in
  the `backend-data` volume), the checkout's `backend/src` (a harness fix
  applies on resume without a rebuild) and the checkout itself read-only
  with `GIT_DIR` pointed at it, because the image has git but no `.git`
  and every record would otherwise say `gitCommit: unknown`. `python`,
  not `uv run python`: the image is synced without the dev group, which
  `uv run` would install first. From Git Bash on Windows, set
  `MSYS_NO_PATHCONV=1` or the container paths get rewritten. The run's
  corpus snapshot is then the live store in `backend-data`, and the
  headless browser the image installs is there, which the host usually
  lacks. Ctrl-C reaches the harness as `docker kill --signal=SIGINT
  <the run container>`.
- **On a CPU**, use the production LLM limits (`LLM_TIMEOUT`,
  `LLM_MAX_CONCURRENCY` in `docker-compose.prod.yml`). The dev limits
  turned 3 of 4 verdicts into `llmUnreachable` (CLAUDE.md, "Known dead").
  The eval layer sets them, and also `INFERENCE_TIMEOUT=120` and
  `CLAIM_MAX_CONCURRENCY=2`: at four claims at once on CPU inference, the
  ranker's embedding calls passed the 30 s default and killed 5 of the
  pilot's first 20 claims (§Pilot). None of these is keyed; each session
  records the values it ran with.
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
| `retrieval.py` | retrieval | Reference recall at three depths, MRR, the gold-free retrieval metrics, paired strategy comparison |
| `attribution.py` | attribution | The stage table above |
| `effort.py` | effort | Usable and confidently-wrong shares |
| `usage.py` | cost | Tokens and latency per LLM call, run totals, prices |
| `writing.py` | writing benchmark | The text set, its runner, the rubric, `writing run` / `writing report` |

Run as `cd backend && uv run python -m src.evaluation.cli run --dataset
data/evaluation/xfact_en_es_pilot.jsonl --model llama3.2:3b [--limit N]
[--thresholds f.json] [--corpus snapshot|none] [--retry-unavailable]
[--fresh]`, then `... report --run <dir> [--compare <dir>]`.

Tests live in `backend/tests/evaluation/` and use only fakes
(`tests/services/fact_checker/fakes.py`; a new shared fake needs its
contract entry, invariant 10) and `tmp_path` (invariant 9). No test
reaches a live service; the pilot is the live run.

## Pilot

**Run on 2026-10-13 (G7)**, in compose (§Where it runs), with
`llama3.2:3b` on the dev laptop's host Ollama (RTX 3050 Laptop, 4 GB:
about 80% of the model in VRAM) and production's LLM limits. Before the
run, `/healthz` answered for all four dependencies (inference 49 ms,
SearXNG 36 ms, LLM 42 ms, Neo4j 1,060 ms) and the source probe's search
check returned 89 results per language, from Bing, Yep, Wikipedia
(English) and four academic indexes, with Google ("access denied") and
Brave ("too many requests") refusing SearXNG. `/metrics` had no runs
yet. A `--limit 3` smoke run got 15-17 web results per claim.

The comparison with the X-Fact paper, the reasons it is not like for
like, and what the years between claim and search do are in
**`xfact-comparison.md`**. What follows is what the pilot says about the
pipeline and the harness.

**Results.** 64 of 64 claims `ok` and scored after four sessions (none
set apart at report time). Report:
`backend/data/evaluation/reports/xfact_en_es_pilot/llama3.2-3b/e6fe23310930/`.

| | n | Accuracy [95% CI] | Macro-F1 [95% CI] |
|---|---|---|---|
| All | 64 | 29.7% [18.8, 40.6] | 0.168 [0.104, 0.234] |
| English (PolitiFact, 3 classes) | 24 | 41.7% [20.8, 62.5] | 0.358 [0.157, 0.554] |
| Spanish (Chequeado, 5 classes) | 40 | 22.5% [10.0, 35.0] | 0.130 [0.061, 0.196] |
| Without either leak flag | 43 | 23.3% [11.6, 37.2] | 0.153 [0.071, 0.238] |

Kappa against gold 0.070 [-0.028, 0.177]; coverage 95.3%. The pipeline
answered `FALSE` to 43 claims (gold: 16) and never `MISLEADING`; the
same model with no evidence answers `FALSE` to 60 of 64
(`scripts/closed_book_probe.py`), and the pipeline beats it by +10.9
accuracy points [+3.1, +20.3], paired. On the Spanish `test` split (165
claims, all scored) the pipeline does no better than chance: accuracy
19.4% [13.3, 25.5], macro-F1 0.111 [0.079, 0.142], kappa -0.002
[-0.060, 0.055], and +3.0 points [-3.0, +9.1] over the closed-book model.
Report: `backend/data/evaluation/reports/xfact_es_test/llama3.2-3b/a6f2e3c8a401/`;
details in `xfact-comparison.md`.

**The partitions.** `searchUnavailable`: 7 claims in the second session,
all within 5 seconds (07:36:17-22 UTC) when every SearXNG engine timed
out at once and SearXNG suspended them; DuckDuckGo's fallback was
challenged as a bot. `llmUnreachable`: 1 claim, which was not an outage:
Ollama answered HTTP 500 "prediction aborted, token repeat limit
reached" twice, the model looping, and `LLMClient` files any API error as
unreachable. All 8 were re-run with `--retry-unavailable` and scored.
`verdictLeak`: 9 claims, **all English**: PolitiFact's own page, 4 of
them from `staging.politifact.com`. **No Chequeado row leaked**: no
Chequeado URL was even a candidate, though all 40 rows link Chequeado's
verdict page and all of those pages still answer. `temporalLeak`: 16
flagged, 4 clear, 44 undetermined (no Spanish row has a date).

**Retrieval** (38 Spanish claims with references; English rows have only
`<LINK NOT AVAILABLE>`): reference link recall 0% at every depth;
reference domain 10.5% among candidates, 5.3% ranked, 2.6% cited. 98.4%
of claims had ranked evidence; 17.9 candidates and 4.7 ranked sources a
claim, 6.6% cut at ranking, 8.9% of ranked sources from rated domains,
none from the internal corpus (5 points). Of the 69 off-Chequeado,
non-social reference links, 51 still answer (9 at a new address), 14 are
gone and 4 refused the check (`reference_links.json`).

**Stage attribution**, computed by `scripts/xfact_time_elapsed.py` with
the table above until G5 builds `attribution.py`, over the 45 wrong
verdicts: trace-only, 44 reasoning and 1 ranking (`xf-954337aa7ed2`,
nothing ranked); by reference, 27 retrieval, 1 ranking, 1 reasoning, and
16 English claims with no reference to judge by. The two columns
disagree on 28 of the 29 claims both can judge (they agree on
`xf-4232cbf2b6df`, reasoning): the trace says the model misread what it
was shown, the references say it was never shown the annotator's
sources. Both are true; the reference rule is the stricter.

**Latency and cost** (the final record of each claim): median 36.5 s a
claim (p90 59.9), of which retrieval 14.8 s and ranking 8.6 s; the LLM
call 5.6 s median (p90 9.5, max 14.5), 2,141 prompt and 179 completion
tokens a claim, 28.3 tokens/s; $0 per token, local. At two claims at
once the second session ran 46 claims in 12.6 minutes, so the 64 take
about 18 minutes on this machine, not the hour §Where it runs estimated
for a CPU.

**Harness and stack problems found**, in the order they appeared:

1. **Every record from compose would have said `gitCommit: unknown`.**
   The image has git but no `.git`. Fixed in configuration, not code:
   `docker/docker-compose.eval.yml` mounts the checkout read-only and
   points `GIT_DIR` at it.
2. **Inference timed out under four concurrent claims.** 5 of the first
   session's 20 claims died with `InferenceUnavailable` (the ranker's
   batched embeddings past the 30 s `INFERENCE_TIMEOUT`, bge-m3 on CPU at
   3,200% CPU), all within 40 seconds; inference answered each one, late.
   The run was stopped and resumed with `INFERENCE_TIMEOUT=120` and two
   claims at once; no error recurred. The production defaults are the
   same 30 s and four claims, so a four-claim article on CPU inference
   can fail the same way: a pipeline finding, not fixed here.
3. **A resumed session's settings were not recorded** (harness bug).
   None of the timeouts and ceilings is keyed, and the manifest kept only
   the first session's, so the run would have claimed the first
   session's values throughout. Fixed: each session in `run.json` carries
   its own `settings`, with `INFERENCE_TIMEOUT` (missing before) and the
   claim concurrency actually used.
   `test_each_session_records_the_environment_it_ran_in`.
4. **A looping model is filed as an unreachable one** (above): an
   `InternalServerError` from a provider that answered. The record's
   `usage.perCall` keeps the error type, so a report could tell the two
   apart; not changed here.
5. **`uv run python` in the container would install the dev group
   first**; the documented command was changed to `python`.
6. **Docker Desktop stopped at 07:56:53 UTC**, 5 minutes into the
   Spanish test run (every container got SIGTERM, then exit 137; not an
   OOM kill). The harness wrote 147 `InferenceUnavailable` error records
   in 14 seconds and exited 1; the same command resumed it after a
   restart, re-running exactly those 147, as designed.
7. **`git status` over the bind mount takes 5.0-5.3 s, against a 5 s
   timeout** (harness bug). The Spanish run's second session lost the
   race and recorded `gitCommit: unknown` for 49 claims (HEAD was
   `e31cdf6`, per `git log`). Fixed: HEAD is kept, `-unchecked` when the
   dirty check does not answer, and the check gets 60 s
   (`test_a_slow_dirty_check_keeps_the_commit`).
8. **The harness process segfaulted twice** in the Spanish run
   (`munmap_chunk(): invalid pointer`, exit 139), after 49 and 41
   claims, both times while pages were being scraped and parsed on the
   scrape threads: heap corruption in a native library. Not located: the
   next two sessions ran with `PYTHONFAULTHANDLER=1` to catch a stack and
   did not crash. Each crash lost only the claims in flight; the same
   command resumed. The pilot never crashed.

The Spanish `test` run took five sessions: 18 ok before Docker stopped,
49 and 41 before each segfault, 57, and 5 `--retry-unavailable` (4
`searchUnavailable` from another all-engines timeout burst, 11:38 UTC,
and 1 more looping model). All 165 scored.

**Recommendation on fact-checker domains**: in `xfact-comparison.md`;
in short, exclude them per run for benchmark runs on fact-checker
datasets, never in production or on the custom set.

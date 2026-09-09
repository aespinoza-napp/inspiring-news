# Incidents

Things that broke, why, and what stops them recurring. Extracted from
CLAUDE.md so this history is read when it is relevant rather than on
every session — it was roughly 3,200 tokens of always-on context.

Each entry ends with **what holds it in place now**. Where that is a
test, changing the code without changing the test fails; where it is a
comment, it is only as strong as the next reader's attention.

---

## The container must build lazily

`src/container.py` builds every service on first use, not at import.

Two independent reasons, both learned the hard way:

1. `NewsEnrichmentPipeline` and `TextCorrector` eagerly load transformer
   models — GLiNER, sentence-transformers, the sentiment classifier —
   which is real seconds of work. `uvicorn --reload` re-imports
   `container.py` in a fresh subprocess on every file save, so eager
   construction re-paid the full model-loading cost before the app could
   serve anything. It was the dominant cost of local iteration.
2. `QdrantClient`'s local mode takes an **exclusive file lock** on
   `settings.QDRANT_PATH`. Eager construction meant every reload — or
   any other process briefly touching that directory — crashed the
   *entire app* on import, not just the feature that needed Qdrant.

Adding a heavy or Qdrant-touching service? Make it lazy the same way.
And do not pass it as an eagerly-evaluated argument:
`background_tasks.add_task(fn, get_x(), ...)` calls `get_x()`
immediately and synchronously, on the request thread. Pass the factory
and call it inside the background function's own try/except, as
`job_runner.py::run_analysis_job` does.

**What holds it in place:** `tests/test_container.py`.

---

## `_lock` must stay an RLock

`get_analysis_service()` acquires `_lock`, then — while still holding it
— calls `get_vector_repository()` and `get_enrichment_pipeline()`, which
acquire it too. A plain `Lock` is not reentrant, so this self-deadlocks
on the very first call.

Reproduced live: a job fired its "initializing" phase and then hung
forever. No error, no timeout, nothing — the thread was blocked waiting
on a lock it already held.

The lock also matters for concurrency. Two `/analyze/jobs` requests
arriving close together (React 18 dev-mode Strict Mode's double-effect
invoke produces exactly this) run in FastAPI's background threadpool and
both race to open Qdrant's exclusive-lock storage path. One fails with
"already accessed by another instance" even though only one process is
involved. Reproduced live: two jobs created ~0 ms apart, one failed on
that error while the other succeeded.

**What holds it in place:** `tests/test_container.py` — one regression
test per failure mode.

---

## The job-polling proxy must not cache

`frontend/src/app/api/jobs/[jobId]/route.ts` must keep
`cache: "no-store"` on its `fetch()` to the backend.

Next.js 14's App Router caches server-side `fetch()` GETs by default, so
every 1-second poll after the first was silently served the same stale
response instead of reaching the backend.

Reproduced live twice: the UI stayed stuck on the first phase forever
even though the backend had finished; and after a backend restart the
proxy kept returning a cached 200 for a job id the backend no longer
recognised at all.

**What holds it in place:** a comment. Nothing tests it.

---

## The polling interval must be guarded by `cancelled`

In `frontend/src/lib/useAnalysisJob.ts`, the `setInterval` created after
the first `await pollOnce(...)` must stay behind a `cancelled` check.

Without it, an effect cleanup firing while that first poll is in flight
— unmount, prop change, or Strict Mode's double-invoke — leaks an
interval nothing will ever clear, polling a finished job forever.

**What holds it in place:** a comment. Nothing tests it.

---

## No test module may call its own test function

A bare `test_x()` at module level runs during pytest *collection*,
before pytest controls execution at all.

This has bitten three times:

1. `tests/scraper/test_scraper.py` did live network scraping just by
   being imported.
2. `tests/nlp/test_pipeline.py` silently overwrote a committed sample
   fixture under `data/processed/` on every collection.
3. Worst: `tests/nlp/{test_claims,test_classifier,test_entities,`
   `test_quality,test_sentiment}.py` all ended with bare calls, and
   because two of those assertions failed, **collection aborted and the
   entire suite refused to run** — 155 unrelated tests included. The
   project had no working test suite and the failure looked like two
   broken NLP tests.

**What holds it in place:**
`tests/test_invariants.py::test_no_test_module_runs_itself_during_collection`.

---

## Tests must not assert against `.env`

`test_related_article` built two vectors 0.970 apart and needed
`0.80 <= 0.970 < DUPLICATE_THRESHOLD`. Someone tuned
`DUPLICATE_THRESHOLD` to `0.96` in their local `.env` — a legitimate
change that breaks nothing in the app — and the test went red for
nobody's mistake.

`.env` is deliberately not in git, so a test asserting against it passes
or fails depending on the machine, and lies to whoever is trying to work
out whether their change broke something.

**What holds it in place:** two things. `tests/conftest.py`'s
`pinned_settings` fixture pins every setting to the default declared in
`Settings` — ignoring both `.env` and the process environment — and
`tests/test_invariants.py::test_no_test_asserts_against_a_threshold_read_from_settings`
catches new ones.

---

## Frozen class attributes made thresholds un-overridable

`MIN_X = settings.MIN_X` in a class body is evaluated once, when the
module is first imported. That froze the value for the life of the
process.

`ClaimSelector.MAX_CLAIMS`, `ConfidenceScorer.MIN_EVIDENCE`,
`DuplicateValidator.DUPLICATE_THRESHOLD`,
`VectorRetriever.RELATEDNESS_THRESHOLD` and the `EvidenceRanker` weights
were all written this way, so per-run overrides had no effect and even
plain env changes were import-order dependent. The giveaway was that
their tests had to reach in and reassign the attribute — so they never
covered the path a real caller takes.

Values are passed **per call** now, because the components are
long-lived singletons shared by every request and a per-run value cannot
live on the instance.

**What holds it in place:**
`tests/test_invariants.py::test_no_settings_are_frozen_into_class_attributes`,
with the ranking/confidence weights declared as explicit exceptions.

---

## The analysis cache served a shape that no longer existed

`AnalysisCache` never expires and a hit never rewrites its entry, so an
entry written before a response-shape change would be served forever —
missing whatever field was added, permanently.

A `SCHEMA_VERSION` stamp was added to fix this, and then the response
grew a `thresholds` key without the version being bumped. The rule was
written in CLAUDE.md and broken in the same week it was written, which
is the whole argument for executable rules.

**What holds it in place:**
`tests/test_invariants.py::test_the_analyze_response_shape_matches_the_cache_schema_version`,
which builds a real response and compares its key set against the shape
recorded for the current version.

---

## The pipeline scored Spanish articles as English

Seven of the twelve configured sources publish in Spanish. Every
keyword heuristic — constructiveness, hopefulness, inspiration,
objectivity, claim reporting-verbs, month names — was an English-only
word set, `textstat` ran the English Flesch formula, and yake ranked
Spanish text against English stopwords.

Measured: the same story scored **0.875** constructiveness in English
and **0.0** in Spanish. Claim sentences scored 0.20 lower and fell below
the extraction threshold, so the fact-checker had nothing to check.

What made it structural rather than a tuning problem:
`enrichment.py` had `language=article.language` commented out, so
`EnrichedArticle.language` was never populated and nothing downstream
*could* branch on it.

Fixed by `src/config/lexicons.py` (per-language word sets, prefix
matching because Spanish is far more inflected) and
`src/processors/nlp/language.py` (stopword-frequency detection).

**What holds it in place:** `tests/nlp/test_language.py`, plus
`tests/test_invariants.py::test_every_configured_source_language_has_a_lexicon`
— adding a source in a third language fails the suite rather than
silently scoring it as English.

---

## The server would fetch any URL it was given

`POST /analyze` took URLs straight from the caller and fetched them
server-side with no validation, and the evidence scraper fetched
whatever SearXNG returned. Since `docker-compose.yml` puts the backend
on a network with Neo4j and SearXNG, `POST /analyze {"urls":
["http://neo4j:7474"]}` read the graph database; on a cloud host the
instance metadata endpoint was one request away.

`src/services/scraper/url_guard.py` now denies by address space, not by
domain allowlist — an allowlist would be wrong for `/analyze`, whose job
is to accept a URL the user found somewhere. DNS is resolved rather than
trusted, because a perfectly ordinary hostname can have an A record of
`127.0.0.1`. Redirects are followed manually so every hop is re-checked;
`requests` would otherwise walk straight past the guard.

**What holds it in place:** `tests/scraper/test_url_guard.py`.

# Backend

Loaded when working under `backend/`. The root `CLAUDE.md` holds the
invariants and the check command; this file is the map.

## Commands

Dependency management is `uv`. Run from `backend/`.

```bash
uv sync                                   # install
uv run uvicorn src.main:app --reload      # http://localhost:8000, /docs
uv run pytest tests/processors/nlp/test_claims.py    # one file
uv run pytest tests/processors/nlp/test_claims.py::test_name -v
```

Prefer `./scripts/check.sh` from the repo root for a full run.

**Running locally now takes two processes.** GLiNER, the sentiment
model and the embedding model live in `inference/`, not here, so the
backend needs that service reachable at `settings.INFERENCE_URL`
(default `http://localhost:8001`, same host-dev default pattern as
`LLM_BASE_URL`):

```bash
cd inference && uv run uvicorn src.main:app --port 8001   # first
cd backend   && uv run uvicorn src.main:app --reload      # then
```

Tests that need real models skip rather than fail when that service
isn't running - see `tests/conftest.py`'s `require_inference`.

`backend/.env` is required (`Settings` reads it via `pydantic-settings`);
`backend/.env-example` lists every key. `NEO4J_PASSWORD` has no default
and raises on startup even though nothing reads Neo4j. `Settings` creates
the `data/*` directories on import as a side effect.

## The pipeline

`src/workflows/enrichment.py` (`NewsEnrichmentPipeline`) runs the NLP
stack in `src/processors/nlp/` — keywords, entities, claims, topic
classifier, sentiment, quality, embeddings — into an `EnrichedArticle`.
Three of those (entities, sentiment, embeddings) are **Adapters over
`inference/`**, not local models: `EntityExtractor`, `SentimentAnalyzer`
and `EmbeddingService` keep their original signatures but delegate to
`src/services/inference_client.py`. Error handling differs per
component on purpose — entities degrade to `{}` (one weak signal among
several in claim scoring), sentiment and embeddings **raise**
`InferenceUnavailable` (they feed the admission gate and duplicate
detection, where a silently empty result corrupts a decision).
`TopicClassifier` also scores each matched topic's own keywords (`src/config/topics.py`) against the article by embedding similarity and counts literal mentions (`TopicPrediction.keywords`); the keyword vectors are embedded once per process in one batched call. `yake` keywords and `textstat` quality stay local — no model to move.
`AnalysisService` then runs two separate modules over it, in order:

- `src/services/admission/` (`AdmissionFilter`) decides whether the
  article is worth checking: `topic_filter`, `positive_impact` and
  `duplicate_detector` (a Qdrant similarity search). All three always
  run, so every reason is reported; a rejected article never reaches
  the fact-checker. `DuplicateDetector.remember` stores an admitted
  article **after** its fact-check — earlier, it would be found as
  internal evidence for its own claims. See its README.
- `src/services/fact_checker/fact_checker.py` (`FactChecker`) knows
  nothing about admission. It orchestrates `claim_selector.py` → then, **per claim and in this
  order**, `retrieval/evidence_retriever.py` (SearXNG web hits via
  `retrieval/search_provider.py` merged with internal corpus hits from
  `retrieval/vector_retriever.py`; `retrieval/scraper.py` fetches full
  text for top web hits) → `ranking/ranking_retrieval.py` →
  `verification/llm_verification.py` →
  `verification/confidence_scorer.py`. Result: a `FactCheckReport`,
  aggregated worst-case-wins (`FALSE > MISLEADING > UNVERIFIED > TRUE`).
- **Claims run concurrently; a claim's own stages do not.** Each stage
  consumes what the previous one produced, so there is nothing to
  overlap inside a claim. Between claims there is nothing shared.
  `docs/decisions/concurrency.md` has the ceilings, the deadlock rule and
  why `bounded_map` preserves input order (evidence indices are what the
  LLM cites by number).
- `retrieval/query_builder.py` plans **three** queries per claim — anchor
  (who and what), proposition (what is being asserted) and refutation —
  run concurrently and fused by reciprocal rank. The anchor query alone
  retrieves the claim's *subject*, which is how a claim mentioning ACME
  came back FALSE at 83% citing pages on the Greek etymology of the word.
  `services/fact_checker/terms.py` is shared by query building and by
  lexical ranking on purpose: one judgement of what a claim is about.
- **The pertinence gate**, in `EvidenceRanker.rank`, cuts a source that
  does not address the claim *before* the LLM sees it, so it cannot be
  cited, counted or corroborated. Per-run
  (`evidence_min_pertinence`) because it is the knob that trades a
  confident wrong answer for an honest `UNVERIFIED`.
  `docs/decisions/retrieval.md`.
- `ConfidenceScorer` **forces `UNVERIFIED`** when no evidence was
  retrieved or the LLM cited nothing, keeping the raw verdict visible.
  This is the guardrail that stops a cheap local model bluffing — don't
  weaken it.
- Every stage takes an optional `on_phase(phase, data)` callback. This
  backs the job-polling API and the Live screen. Claim checking emits,
  in order **within one claim**: `retrieving_evidence`, `searching_web`
  (the queries and what each one asks, **before** the search runs),
  `web_results` (every hit with its engines), `scraping_sources` /
  `sources_scraped`, `evidence_retrieved`, `evidence_ranked` (each
  source's relevance and the four factors behind it), `verifying_claim`,
  `claim_checked` (verdict plus each source's stance, quote and whether
  it was cited). The first, and the events inside
  `EvidenceRetriever.retrieve`, exist because those sub-stages are the
  slowest in the pipeline. Per-source detail goes through
  `fact_checker/progress.py::source_summary`, which never includes a
  scraped body — events are held in memory, polled every second and
  journalled.
- **Across claims those events interleave**, because the claims run at
  once. Two things make a client's life possible and both are
  load-bearing: `claims_selected` carries the whole claim set with
  indices before any check starts, and every per-claim event carries
  `claimIndex` as well as `claim`. The callback itself is serialised for
  you (`FactChecker._serialised`) so the job runner's phase timers and
  the journal's list append keep their single-threaded contract.
- `Evidence.reliability_known` says whether `reliability_score` is a rating
  we hold for that domain or just `RANKING_DEFAULT_RELIABILITY`. Do not
  draw an unrated 0.5 like a real one.

## Language

7 of the 12 sources publish in Spanish, so the NLP stack branches on
language: `src/config/lexicons.py` holds per-language word sets (entries
ending `*` are prefix matches — Spanish is heavily inflected), and
`src/processors/nlp/language.py` detects `en`/`es` by stopword frequency.
`News.language` is set at extraction, carried into `EnrichedArticle`, and
drives `QualityAnalyzer`, `ClaimExtractor`, `KeywordExtractor` (yake) and
the `textstat` readability formula. An unsupported language falls back to
English rather than raising. See `docs/decisions/incidents.md`.

## Entry points (`src/api/routes.py`)

| Endpoint | Notes |
|---|---|
| `POST /analyze` | Synchronous, N URLs. Catches per URL, not per batch. |
| `POST /analyze/jobs` + `GET /analyze/jobs/{id}` | What the frontend uses. `job_store.py` is in-memory, single-process. `job_runner.py` bridges `on_phase` into it and logs per-phase timing at INFO. Every event is also appended to the job journal (`docs/decisions/storage.md`), and `GET /{id}` falls back to it after a restart. |
| `GET /analyze/jobs` | What is running and what ran recently, for the Live screen: active jobs with every event, finished ones as a summary (`events: []`, `result: null`, `eventCount`). In-memory jobs only. Behind `STORAGE_API_KEY` when set — it enumerates every job id, which used to be an unguessable capability. |
| `POST /verify-claim` | One claim, no article. Runs `FactChecker.check_claim()` — the pipeline's own stage made public so the two cannot drift. Skips admission and claim selection: those judge an *article*. Still answers synchronously, but is registered as a `kind: "claim"` job so the Live screen shows it and the journal keeps it. |
| `POST /enrich` | NLP stage alone over supplied text, or over a `url` fetched with the analyzer's own extractor. `extraction` reports the title, author, date and body it started from and where each came from (`supplied` / `extracted` / `missing`). **Side-effect free** — nothing written to the lake. |
| `POST /correct` | `readability` and `coverageVerification` are deterministic; the other 5 come from one LLM call. |
| `POST /ingest` + `GET /ingest/sources` | Discovery over the configured sources, queuing each new article (not already in the lake, at most `perSource`) as an analysis job with purpose `ingestion`. Manual only; behind `STORAGE_API_KEY`. `services/ingestion_service.py`, `docs/decisions/scraping.md`. |
| `GET /scraper/stats` | Every extraction attempt this process (and, via `lake/stats/scraper_requests.json`, previous ones) made, per domain, by outcome and purpose. Recorded in `ExtractorService` into the shared `request_stats`; strategies report *why* through `attempt()`. Behind `STORAGE_API_KEY` when set. |
| `GET /scraper/articles` | Articles stored in the lake, per domain: raw records, unique URLs, how many arrived with a title / author / date, and how many went on to processed / exploitation / publishable. Read from the lake on every call (`services/scraper/article_stats.py`) - no second counter. Behind `STORAGE_API_KEY` when set. |
| `GET /storage/*` | Read the lake. Behind `STORAGE_API_KEY` when set. |

All of these accept per-run `thresholds` overrides —
`docs/decisions/thresholds.md`.

## Storage

Three layers under `settings.LAKE_PATH`, one write per stage as that
stage completes. `docs/decisions/storage.md`.

## Security

`src/services/scraper/url_guard.py` decides whether the server may fetch
a URL: http/https only, DNS resolved rather than trusted, private /
loopback / link-local / reserved addresses denied, infrastructure ports
blocked, redirects followed manually so each hop is re-checked. Disable
only for offline tests (`URL_GUARD_ENABLED=false`).

`STORAGE_API_KEY` gates `/storage/*`, which returns whole article bodies.
Unset leaves them open — fine on localhost, and `src/main.py` warns at
startup so it is never a silent choice.

## Layout

- `src/models/` — subpackages by domain: `core/`, `nlp/`, `scraper/`,
  `admission/`, `fact_checker/`, `corrector/`, `storage/`. No `__init__.py` anywhere.
- `src/container.py` — lazy singletons behind an `RLock`. Read
  `docs/decisions/incidents.md` before changing it; both the laziness
  and the reentrancy are load-bearing.
- `data/sources/*.yaml` — adding a source is a YAML file, not code.
- Two things called "raw" and "processed": the legacy `data/raw` and
  `data/processed` (bare JSON, no lineage, written ad hoc by
  `LocalRepository`) are **not** the lake's layers.

## Tests

`tests/` mirrors `src/` by subsystem. `tests/factories.py` builds
populated models; `tests/services/fact_checker/fakes.py` fakes every
external dependency; Qdrant tests use a temporary on-disk database
(`conftest.py::repository`).

`conftest.py::pinned_settings` pins every setting to its declared default
for the whole suite, so nothing depends on `.env` or the environment.

`tests/test_invariants.py` enforces the root `CLAUDE.md` invariants.

`tests/test_fake_contracts.py` asserts every shared fake accepts what the
real collaborator accepts — five fakes drifted at once when thresholds
became per-call, each found by a `TypeError` days later.

`conftest.py::require_inference` skips any test needing a real model
when `inference/` isn't reachable — the same tradeoff
`tests/database/test_connection.py` already makes for Neo4j. Real
*model* behaviour is tested in `inference/tests/` now; what these still
cover is backend correctly using a real inference service
(`TopicClassifier`'s semantic ranking, `EMBEDDING_DIMENSION` agreement,
the full pipeline handoff). Adapter behaviour itself — right endpoint,
right arguments, degrade-vs-raise — is tested with stubs and needs
nothing running (`tests/processors/nlp/test_entities.py`,
`test_sentiment.py`, `test_embeddings.py`,
`tests/services/test_inference_client.py`).

`tests/database/test_connection.py` skips when Neo4j is not running.
`tests/processors/nlp/test_pipeline.py` skips when `data/raw` is empty —
it enriches whatever real article sorts first there, so it can only
assert what holds for *any* article. Assertions about a specific
article belong in `tests/test_real_pipeline_integration.py`, which uses
committed input. `tests/processors/nlp/test_all_news.py` carries the
`slow` marker (the whole corpus through the full stack) and runs via
`./scripts/check.sh slow` — which now also needs `inference/` up.

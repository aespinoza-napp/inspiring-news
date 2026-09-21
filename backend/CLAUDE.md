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
`src/services/fact_checker/` then validates and checks it:

- `validation_pipeline.py` → `topic_validator`, `positive_impact_validator`,
  `duplicate_validator` (a Qdrant similarity search).
- `fact_checker.py` (`FactChecker`) orchestrates: validate (short-circuit
  on failure) → `claim_selector.py` → `retrieval/evidence_retriever.py`
  (SearXNG web hits via `retrieval/search_provider.py` merged with
  internal corpus hits from `retrieval/vector_retriever.py`;
  `retrieval/scraper.py` fetches full text for top web hits) →
  `ranking/ranking_retrieval.py` → `verification/llm_verification.py` →
  `verification/confidence_scorer.py`. Result: a `FactCheckReport`,
  aggregated worst-case-wins (`FALSE > MISLEADING > UNVERIFIED > TRUE`).
- `ConfidenceScorer` **forces `UNVERIFIED`** when no evidence was
  retrieved or the LLM cited nothing, keeping the raw verdict visible.
  This is the guardrail that stops a cheap local model bluffing — don't
  weaken it.
- Every stage takes an optional `on_phase(phase, data)` callback. This
  backs the job-polling API and the Live screen. Claim checking emits, in
  order: `retrieving_evidence`, `searching_web` (the queries, **before**
  the search runs), `web_results` (every hit with its engines),
  `scraping_sources` / `sources_scraped`, `evidence_retrieved`,
  `evidence_ranked` (each source's relevance and the three factors behind
  it), `verifying_claim`, `claim_checked` (verdict plus each source's
  stance, quote and whether it was cited). The first, and the events inside
  `EvidenceRetriever.retrieve`, exist because those sub-stages are the
  slowest in the pipeline. Per-source detail goes through
  `fact_checker/progress.py::source_summary`, which never includes a
  scraped body — events are held in memory, polled every second and
  journalled.
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
| `POST /verify-claim` | One claim, no article. Runs `FactChecker.check_claim()` — the pipeline's own stage made public so the two cannot drift. Skips the admission filter and claim selection: those judge an *article*. Still answers synchronously, but is registered as a `kind: "claim"` job so the Live screen shows it and the journal keeps it. |
| `POST /enrich` | NLP stage alone over supplied text. **Side-effect free** — nothing written to the lake. |
| `POST /correct` | `readability` and `coverageVerification` are deterministic; the other 5 come from one LLM call. |
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
  `fact_checker/`, `corrector/`, `storage/`. No `__init__.py` anywhere.
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

# Backend

Loaded when working under `backend/`. The root `CLAUDE.md` holds the
invariants and the check command; this file is the map.

## Commands

Dependency management is `uv`. Run from `backend/`.

```bash
uv sync                                   # install
uv run uvicorn src.main:app --reload      # http://localhost:8000, /docs
uv run pytest tests/nlp/test_claims.py    # one file
uv run pytest tests/nlp/test_claims.py::test_name -v
```

Prefer `./scripts/check.sh` from the repo root for a full run.

`backend/.env` is required (`Settings` reads it via `pydantic-settings`);
`backend/.env-example` lists every key. `NEO4J_PASSWORD` has no default
and raises on startup even though nothing reads Neo4j. `Settings` creates
the `data/*` directories on import as a side effect.

## The pipeline

`src/workflows/enrichment.py` (`NewsEnrichmentPipeline`) runs the NLP
stack in `src/processors/nlp/` — keywords, entities, claims, topic
classifier, sentiment, quality, embeddings — into an `EnrichedArticle`.
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
  backs the job-polling API.

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
| `POST /analyze/jobs` + `GET /analyze/jobs/{id}` | What the frontend uses. `job_store.py` is in-memory, single-process. `job_runner.py` bridges `on_phase` into it and logs per-phase timing at INFO. |
| `POST /verify-claim` | One claim, no article. Runs `FactChecker.check_claim()` — the pipeline's own stage made public so the two cannot drift. Skips the admission filter and claim selection: those judge an *article*. |
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
populated models; `tests/fact_checker/fakes.py` fakes every external
dependency; Qdrant tests use a temporary on-disk database
(`conftest.py::repository`).

`conftest.py::pinned_settings` pins every setting to its declared default
for the whole suite, so nothing depends on `.env` or the environment.

`tests/test_invariants.py` enforces the root `CLAUDE.md` invariants.

`tests/test_connection.py` skips when Neo4j is not running.
`tests/nlp/test_pipeline.py` skips when `data/raw` is empty — it enriches
whatever real article sorts first there, so it can only assert what holds
for *any* article. Assertions about a specific article belong in
`tests/test_real_pipeline_integration.py`, which uses committed input.
`tests/nlp/test_all_news.py` is excluded from routine runs.

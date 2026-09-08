# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This is a monorepo with two independent projects:

- `backend/` — Python/FastAPI news scraping, enrichment, and fact-checking pipeline.
- `frontend/` — Next.js 14 (App Router + TypeScript) UI: a news analyzer and a text "corrector".
- `docker/` — `docker-compose.yml` (Neo4j, SearXNG, backend) and `backend.Dockerfile`.

## Backend

### Commands

Run all commands from `backend/`. Dependency management is via `uv`.

```bash
uv sync                                    # install dependencies
uv run uvicorn src.main:app --reload       # run the API (http://localhost:8000)
uv run pytest                              # run the full test suite
uv run pytest tests/nlp/test_claims.py     # run a single test file
uv run pytest tests/nlp/test_claims.py::test_name -v   # run a single test
```

Swagger docs are at `http://localhost:8000/docs`. There is no configured linter/formatter (no ruff/black/mypy config) — don't assume one.

`backend/.env` is required at runtime (`Settings` in `src/config/settings.py` reads it via `pydantic-settings`); see `backend/.env-example` for the required keys (`NEO4J_PASSWORD` has no default and will raise on startup if unset, even though nothing currently uses Neo4j at runtime — see below). `Settings` also creates the `data/{raw,processed,embeddings,fact_checks,graph,cache}` directories on import as a side effect.

### Architecture: one pipeline, two entry points

`src/workflows/enrichment.py` (`NewsEnrichmentPipeline`) runs the real NLP stack in `src/processors/nlp/` (keywords, entities, claims, topic classifier, sentiment, quality, embeddings) to build a `src/models/core/enriched_article.py` (`EnrichedArticle`). This is validated and fact-checked by `src/services/fact_checker/`:

- `validation_pipeline.py` runs `validators/topic_validator.py`, `validators/positive_impact_validator.py`, and `validators/duplicate_validator.py` (the latter does a Qdrant vector-similarity search via `VectorRepository`, gated by `settings.DUPLICATE_THRESHOLD` / `RELATEDNESS_THRESHOLD`).
- `fact_checker.py` (`FactChecker`) is the orchestrator: it calls `ValidationPipeline.validate()` first and short-circuits with `validation_passed=False` if it fails, otherwise runs `claim_selector.py` (`ClaimSelector` — picks top claims by confidence, dedupes near-identical ones by embedding similarity) → `retrieval/evidence_retriever.py` (merges web evidence from `retrieval/search_provider.py`, which queries a self-hosted **SearXNG** instance via `src/services/search.py`'s `SearxngClient`, with internal corpus evidence from `retrieval/vector_retriever.py`, a `VectorRepository`-backed lookup; `retrieval/scraper.py` fetches full text for top web hits by reusing `ExtractorService`) → `ranking/ranking_retrieval.py` (`EvidenceRanker`, scores by semantic similarity + recency + source reliability, weights configurable via `settings.RANKING_*`) → `verification/llm_verification.py` (`LLMVerifier`, calls an LLM via `src/services/llms.py`'s `LLMClient`) → `verification/confidence_scorer.py` (`ConfidenceScorer`, weights configurable via `settings.CONFIDENCE_*` — hard-forces `UNVERIFIED` when no evidence was found or the LLM cites nothing, so a cheap/local model can't hallucinate a confident verdict). Result: a `FactCheckReport` with one `FactCheck` (carries a `Verdict` enum + cited `Evidence`) per checked claim, aggregated with worst-case-wins (`FALSE > MISLEADING > UNVERIFIED > TRUE`).
- Every stage of `FactChecker.run()` (and `AnalysisService.analyze()` around it — scraping/enriching too) accepts an optional `on_phase(phase: str, data: dict)` callback, fired as each phase starts/completes. This is what backs the job-polling API below — don't add a pipeline stage without also calling `on_phase` for it.
- `LLMClient` is a thin OpenAI-SDK wrapper pointed at `settings.LLM_BASE_URL`, defaulting to a **local Ollama** instance — open-source/free by default, no OpenAI API key anywhere in this repo. Swapping to Groq/OpenRouter/Together is a settings-only change (`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`), no code change.
- Vector storage: `src/database/qdrant.py` (`QdrantDatabase`, embedded/local Qdrant at `settings.QDRANT_PATH`) + `src/repositories/vector_repository.py` (`VectorRepository`, collection `"news"`, cosine distance, dimension `settings.EMBEDDING_DIMENSION`).
- Embeddings: `src/services/embeddings/service.py` (`EmbeddingService`, singleton wrapping a `sentence-transformers` model named by `settings.EMBEDDING_MODEL`).
- Running this for real (not under test) requires SearXNG (`docker/docker-compose.yml`'s `searxng` service, JSON API enabled via `docker/searxng/settings.yml` — copy from `settings.yml.example`, it's gitignored since it holds a generated secret) and an LLM endpoint (Ollama running locally by default). All fact-checker tests fake both, so `uv run pytest` needs neither.

Two API surfaces sit on top of the same pipeline (`src/api/routes.py`):

- `POST /analyze` — synchronous, one or more URLs, blocks until every URL's full pipeline run completes. Simple but slow (real scraping + SearXNG + LLM calls per claim).
- `POST /analyze/jobs` (one URL, returns `{jobId}` immediately, FastAPI `BackgroundTasks`) + `GET /analyze/jobs/{jobId}` (poll for phase-by-phase progress and the final result) — this is what the frontend actually uses; see `src/services/job_store.py` (in-memory, thread-safe, single-process only) and `src/services/job_runner.py` (bridges `on_phase` events into the job store, and logs each phase's duration at INFO level — see `src/main.py`'s `logging.basicConfig`, since INFO isn't Python's default level).
- `POST /verify-claim` — one claim, no article. `src/services/claim_service.py` (`ClaimService`) builds a `Claim` from the text (entities via the shared `EntityExtractor`, `confidence=1.0` — the user already chose this claim, so scoring it could only discard it) and hands it to `FactChecker.check_claim()`, which is `_check_claim` made public precisely so the standalone checker and the article pipeline cannot drift apart in what counts as verified. It deliberately skips the admission filter and claim selection: those judge an *article*, and a bare claim has no topic score and nothing to be a duplicate of. Synchronous — one search plus one LLM call, so it does not need the job machinery.
- `POST /enrich` — the NLP stage on its own, over supplied text. `src/services/enrichment_service.py` (`EnrichmentService`) wraps the same `NewsEnrichmentPipeline` singleton the article pipeline uses, so the output matches what a full run would derive. It wraps the text in a synthetic `News` (`source_id="manual"`, `url="about:blank"` — it was never fetched from a configured source and must not look like it was) and returns the embedding's *shape* plus an 8-value preview rather than 1024 floats. **Deliberately side-effect free**: nothing is written to the lake. It is an inspection/tuning tool, and persisting every experiment would fill the raw layer with text nobody ever fetched. Both endpoints accept the same `thresholds` overrides as `/analyze`.
- `POST /correct` — the "corrector": `readability` and `coverageVerification` are deterministic (`QualityAnalyzer`/`PositiveImpactValidator` reused directly), the other 5 metrics (grammar, factConsistency, seo, hallucinationIndex, style) come from one `LLMClient` call. See `src/services/corrector/text_corrector.py`.
### Thresholds: env defaults, per-run overrides

Every tunable threshold lives in `src/config/thresholds.py`, not in the
component that uses it:

- `PipelineThresholds` — the *effective* set for one run. Every field
  defaults from `settings` (i.e. from `.env`).
- `ThresholdOverrides` — the *request* shape, every field optional.
- `PipelineThresholds.resolve(overrides)` merges them: whatever the
  caller set wins, everything else falls back to the environment.

Callers send overrides on the `thresholds` field of `POST /analyze` and
`POST /analyze/jobs`; anything omitted uses the configured default. Jobs
resolve on the request thread, so a bad value is a 422 on the POST rather
than a job that is accepted and then fails where only polling reveals it.
`ThresholdOverrides` is `extra="forbid"` and range-bounded, so a typo'd
knob or a nonsensical value is rejected instead of silently ignored.

**Never write `MIN_X = settings.MIN_X` in a class body.** That is
evaluated once when the module is first imported, which freezes the value
for the life of the process — it is why `ClaimSelector.MAX_CLAIMS`,
`ConfidenceScorer.MIN_EVIDENCE`, `DuplicateValidator.DUPLICATE_THRESHOLD`
and friends could not be overridden at all, and why the tests for them had
to reach in and reassign the attribute (so they never covered the path a
real caller takes). Thresholds are passed **per call** —
`validate(article, thresholds)`, `process(text, threshold)`,
`select(claims, thresholds)`, `run(article, thresholds=...)` — because the
components are long-lived singletons (see `container.py`) shared by every
request, so a per-run value cannot live on the instance. `None` everywhere
means "use the defaults", so every one of those parameters is optional and
existing call sites keep working.

Two consequences worth knowing:

- **The analysis cache keys on the thresholds too** (only those differing
  from the defaults, so a plain run still keys on the URL alone). The same
  URL under a different admission bar is a different analysis; serving the
  default run's cached answer would make it look like the override had
  been applied when it never was.
- **The lake records them.** `Lineage.threshold_overrides` carries exactly
  what a run changed, so a stored record's numbers stay reproducible — the
  same article yields a different verdict under a different bar.

Ranking and confidence *weights* (`RANKING_*`, `CONFIDENCE_*`) are
deliberately environment-only, not per-request: each group must sum to
1.0, and letting a caller set one member alone would silently produce a
scoring function that no longer normalises.

### Storage: three layers with lineage

The pipeline writes into a three-layer lake under `settings.LAKE_PATH`
(`data/lake/`, gitignored) via `src/repositories/datalake_repository.py`
(`DataLakeRepository`) — **one write per stage, as that stage completes**,
not one write of everything at the end:

| Stage | Writes |
|---|---|
| extraction | `raw/` |
| enrichment | `processed/` (metadata + embedding, `fact_check` still null) |
| verification | `exploitation/`, and rewrites `processed/` with the report |

That ordering is the point: a fact-check that crashes (SearXNG down, LLM
timeout) no longer discards an enrichment that already cost the whole NLP
stack, and a failed enrichment no longer discards the fetch. Each write is
independently fail-soft — a failure at one layer is reported as its own
`store_failed` phase and does **not** stop the next layer, which simply
loses its parent link. `persist_all()` still exists for callers that
already hold a finished result (batch re-processing, tests); the live
pipeline does not use it.

The verification stage writes `processed/` a second time to attach the
report. That is not a duplicate record: ids are `uuid5(layer, article,
run)`, so both writes address the same document, while the append-only
manifest logs both — the audit trail reads "written after enrichment,
updated after verification". The full evidence and rejected candidates
live there rather than in `exploitation/`, which stays flat for serving.

The three layers:

- `raw/` — `RawRecord`: the extracted `News` plus fetch metadata. Nothing
  model-derived, so it stays valid when every downstream model changes.
- `processed/` — `ProcessedRecord`: the full `EnrichedArticle` and its
  `FactCheckReport`, rejections included. This is the layer you re-derive
  from, not the one you serve.
- `exploitation/` — `ExploitationRecord`: one flat, denormalised,
  ready-to-serve document. No embedding (it points at the Qdrant point id
  instead), no rejected candidates; the editorial decision is precomputed
  as `publishable` (validation passed and the verdict is not FALSE or
  MISLEADING — UNVERIFIED does *not* block, it is the common outcome with
  a local model).

Every record carries a `Lineage` (`src/models/storage/lineage.py`):
`run_id` (one per `analyze()` call), `article_id`, `content_hash` (sha256
of the body — the join key across layers and the dedupe key across runs),
`parent_layer`/`parent_record_id`, `pipeline_version`, the git revision,
and the model versions in play. Record ids are `uuid5(layer, article,
run)`, so re-running a persist step overwrites its own records instead of
duplicating them — the stage is idempotent and safely retryable.
`DataLakeRepository.trace(article_id)` walks the whole chain, using the
append-only `data/lake/_manifest.jsonl` audit log (one line per write) as
the history, since records themselves only show current state.

Storage is behind an interface (`src/repositories/lake_backend.py`'s
`LakeBackend` protocol; `JsonFileLakeBackend` is the default, with atomic
temp-file + `os.replace` writes because the persist stage runs in
FastAPI's background threadpool). Moving the lake to MongoDB/Postgres/S3
means writing one class with five methods — no pipeline change. `motor`
is already a dependency if MongoDB is the direction.

`AnalysisService` does the staging in `_store_raw`/`_store_processed`/
`_store_verified` (all funnelled through `_store`, which owns the
fail-soft try/except and the phase events). `AnalysisService.lake` has
**no default**, like `fact_checker` and for the
same reason: it is the other collaborator that writes outside the
process, and a default would mean every test constructing an
`AnalysisService` silently wrote into the real data directory. The app
passes the container singleton (`get_datalake_repository()`); `None`
switches the stage off, as does `settings.LAKE_ENABLED=false`. The stage
is **fail-soft** — a storage error is reported as a `store_failed`
phase and logged, and the analysis still completes, because a failed
write must not discard a result that already cost a scrape, an enrichment
and one LLM call per claim. Read it back over
`GET /storage/{layer}`, `GET /storage/{layer}/records/{record_id}` and
`GET /storage/trace/{article_id}`.

Note the lake is deliberately *not* the legacy `data/raw` and
`data/processed` directories: those hold bare `News`/`EnrichedArticle`
JSON written ad hoc by scripts and `LocalRepository`, with no lineage,
and must not be mixed with lake records.

- `AnalysisService` (`src/services/analysis_service.py`) also caches `/analyze` results by URL under `settings.CACHE_PATH` (`AnalysisCache`) — a repeat request for the same URL returns the cached result instantly (`cached: true` in the response) instead of re-running everything; pass `forceRefresh` to bypass it. Cache entries are stamped with `AnalysisCache.SCHEMA_VERSION` and an older stamp is treated as a miss — the cache never expires and a hit never rewrites the entry, so without that an entry written before a response-shape change would be served forever. **Bump `SCHEMA_VERSION` whenever the dict returned by `AnalysisService.analyze()` changes shape.** `POST /analyze` catches per URL, not per batch: `AnalysisService` only handles extraction failures internally, so anything raised later used to discard the completed results for every other URL in the same call.

**Lazy construction, on purpose.** `src/container.py`'s `get_vector_repository()`/`get_enrichment_pipeline()`/`get_fact_checker()`/`get_claim_service()`/`get_enrichment_service()`/`get_analysis_service()`/`get_text_corrector()` all build on first use, not at import time. Two independent reasons this matters, both learned the hard way this project's history: (1) `NewsEnrichmentPipeline`/`TextCorrector` eagerly load transformer models (GLiNER, sentence-transformers, the sentiment classifier) — real seconds of work — and `uvicorn --reload` re-imports `container.py` in a fresh subprocess on every file save, so eager construction meant every single reload re-paid that cost; (2) `QdrantClient`'s local mode takes an *exclusive* file lock on `settings.QDRANT_PATH` — eager construction meant every reload (or literally any other process briefly touching that directory) could crash the *entire app* on import, not just the feature that needed Qdrant. If you add a new heavy/Qdrant-touching service to the container, make it lazy the same way — don't call it directly as an eagerly-evaluated argument either (e.g. `background_tasks.add_task(fn, get_x(), ...)` calls `get_x()` immediately, synchronously, in the request handler; pass the factory itself and call it inside the background function's own try/except, per `job_runner.py::run_analysis_job`).

The lazy-init checks are guarded by `_lock`, a `threading.RLock()` — it must stay reentrant, not a plain `Lock()`. `get_analysis_service()` acquires `_lock` and then, while still holding it, calls `get_vector_repository()`/`get_enrichment_pipeline()`, which also acquire `_lock`; a plain `Lock` self-deadlocks on the very first call (reproduced live: a job stuck forever on "initializing", no error, no timeout). The lock also matters for concurrency: two `/analyze/jobs` requests arriving close together (e.g. React 18 dev-mode Strict Mode's double-effect-invoke) run in FastAPI's background threadpool and can otherwise race to open Qdrant's exclusive-lock storage path at the same time — one fails with "already accessed by another instance" even though only one process is involved. See `tests/test_container.py` for both regression tests.

`get_fact_checker()` is a singleton shared by `/analyze` and `/verify-claim`: it owns the `VectorRepository` (one Qdrant client per process) and an `EmbeddingService`, and two instances would be two chances for the two entry points to reach different verdicts. `get_claim_service()` likewise borrows `get_enrichment_pipeline().entities` rather than loading a second GLiNER.

Neo4j (`src/database/neo4j_client.py`, `docker-compose.yml`) is configured but nothing in the real pipeline uses it — `settings.NEO4J_PASSWORD` is required at startup purely as inherited scaffold config, not because anything reads from Neo4j.

### Models

`src/models/` is organized into subpackages by domain rather than one flat directory: `core/` (`claim`, `news`, `source`, `enriched_article`, `similarity`, `job` — types used across multiple subsystems), `nlp/` (`quality`, `sentiment_result`, `topic_prediction`, `topics` — enrichment output shapes), `scraper/` (`extraction`, `search_query`, `search_result`), `fact_checker/` (`duplicate_result`, `evidence`, `fact_check`, `fact_check_report`, `validation_result` — mirrors `src/services/fact_checker/`'s own layout), `corrector/` (`correction_metric`). No `__init__.py` files anywhere in `src/` — everything is a namespace package, consistent throughout.

### Scraping

`src/services/scraper/scraper.py` (`Scraper`) composes `discovery.py` (`DiscoveryService`, finds article URLs per source/topic via `RSSDiscoveryStrategy`) and `extractor.py` (`ExtractorService`, extracts article content via `TrafilaturaStrategy`). `strategies/beautifulsoup.py` and `strategies/playwright_*.py` are unimplemented placeholder strategies (not wired into `ExtractorService`/`DiscoveryService`, `BeautifulSoupStrategy.extract()` just returns `None`) for JS-rendered sources (`NewsSource.requires_javascript`) — don't assume they do anything yet.

### News sources

Sources are declarative YAML files in `backend/data/sources/*.yaml`, loaded by `src/repositories/source_repository.py` (`SourceRepository`) into `src/models/core/source.py` (`NewsSource`) objects. Adding a new source means adding a YAML file there, not writing code.

### Tests

`backend/tests/` mirrors `src/` roughly by subsystem (`nlp/`, `scraper/`, `fact_checker/`, `services/`, `database/`). `tests/factories.py` (`create_article`, `create_claim`, `create_evidence`) builds fully-populated model instances for tests that need one; `tests/builders/source_builder.py` does the same for sources; `tests/fact_checker/fakes.py` has fakes for every external dependency the fact-checker touches (embeddings, SearXNG, the scraper, the LLM client, source repository) so none of those tests need live services. Tests that touch Qdrant spin up a temporary on-disk database (see `tests/conftest.py`'s `repository` fixture) rather than mocking the client.

No test module in this suite should call its own test function at module level (`test_something()` as a bare statement, outside `if __name__ == "__main__"`) — that runs the test's side effects (including writes) during pytest *collection*, before pytest controls execution at all. This bit twice already: `tests/scraper/test_scraper.py` did live network scraping just by being imported, and `tests/nlp/test_pipeline.py` silently overwrote a committed sample fixture under `data/processed/` on every collection. This bit a third time: `tests/nlp/{test_claims,test_classifier,test_entities,test_quality,test_sentiment}.py` all ended their module with bare `test_x()` calls, and because two of those assertions failed, *collection* aborted and the **entire suite refused to run** — 155 unrelated tests included. All are fixed; if you add a new test file, don't reintroduce the pattern.

The suite is green: `uv run pytest --ignore=tests/nlp/test_all_news.py` passes, with `tests/test_connection.py` skipping (not failing) when no Neo4j is running — Neo4j is unused scaffold, and a permanently red test trains people to ignore the suite. `tests/nlp/test_pipeline.py` skips when `backend/data/raw` is empty: it enriches whatever real scraped article happens to sort first there, so it can only assert what holds for *any* article (it used to assert that topics/claims were found, and failed whenever the first file was, say, a football report matching none of the configured `TOPICS`). Assertions about what a *specific* article must yield belong in `tests/test_real_pipeline_integration.py`, which uses fixed, committed input. `tests/nlp/test_all_news.py` is still excluded from routine runs (`--ignore`) because it depends on `backend/data/raw` already being populated with real scraped articles, which nothing in the current suite populates.

## Frontend

Two pages, both talk to the backend only through Next.js server-side API route handlers under `src/app/api/` (keeps `BACKEND_URL` off the client) — see `.env.local.example` for `BACKEND_URL` (`http://127.0.0.1:8000`, not `localhost`: Node can resolve `localhost` to the IPv6 loopback first, which fails to connect to uvicorn's IPv4-only default).

- `/` (`src/app/page.tsx`) — paste one or more article URLs, each gets its own `JobCard`. `src/lib/useAnalysisJob.ts` is a polling hook: POSTs `/api/jobs` to start a job, then polls `GET /api/jobs/{jobId}` every second until `status` is `done`/`failed`, exposing the growing phase-event list and the eventual result. `src/components/PhaseStepper.tsx` renders that as a 6-stage timeline (Fetch → Enrich → Validate → Fact-check → Store → Done). The Store stage tracks the staged writes: `storing`/`stored_layer` fire per layer (four writes in a clean run — raw, processed, processed again with the report, exploitation), and the final `stored` event carries the editorial outcome, collapsing the backend's fine-grained phases into each stage. **If you touch `useAnalysisJob.ts`**: the interval-creation line after the first `await pollOnce(...)` must stay guarded by a `cancelled` check — without it, an effect cleanup that fires while that first poll is in flight (component unmount, prop change, or React 18 dev-mode Strict Mode's double-invoke) leaks a `setInterval` that nothing will ever clear, polling a finished job forever. This happened once; the guard is the fix, don't remove it. **`src/app/api/jobs/[jobId]/route.ts`'s `fetch()` to the backend must keep `cache: "no-store"`** — Next.js 14's App Router caches server-side `fetch()` GETs by default, so without it every 1s poll after the first was silently served the same stale cached response instead of reaching the backend (reproduced live: the UI stayed stuck on the first phase forever even though the backend had already finished, and after a backend restart the proxy kept returning a cached 200 for a job id the backend no longer recognized at all).
- `/claim` (`src/app/claim/page.tsx`) — paste one claim, get a verdict with its evidence, the sources considered but not used, and (when the confidence scorer overrode the model) what the LLM originally answered.
- `/enrich` (`src/app/enrich/page.tsx`) — paste text, see the enrichment the pipeline would derive: topics, keywords, entities, extracted claims, sentiment, quality and the embedding's shape.
- `/corrector` (`src/app/corrector/page.tsx`) — paste text, get the 7 corrector metrics as score cards.
- `src/lib/types.ts` mirrors the backend's exact response shapes (`AnalysisResult`, `AnalysisJob`, `PhaseEvent`, `CorrectionReport`, ...) — keep it in sync if a backend response shape changes.
- Design system is a single hand-written `src/app/globals.css` (CSS variables, light/dark via `prefers-color-scheme`, `prefers-reduced-motion` respected) — no UI library, no Tailwind, no dependencies beyond `next`/`react`/`react-dom` in `package.json`. Keep it that way unless there's a real reason not to.

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000
npm run build
npm run lint
```

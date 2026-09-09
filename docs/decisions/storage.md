# Storage: three layers with lineage

> Extracted from CLAUDE.md. Read this before touching
> `src/repositories/datalake_repository.py`, `lake_backend.py`, or the
> `_store_*` methods on `AnalysisService`.


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


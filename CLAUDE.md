# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This is a monorepo with two independent projects:

- `backend/` — Python/FastAPI news ingestion, enrichment, and fact-checking pipeline (the active project).
- `frontend/` — Next.js 14 (App Router + TypeScript) UI, currently minimal/early-stage.
- `docker/` — `docker-compose.yml` and `backend.Dockerfile` wiring the backend to a Neo4j container.

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

`backend/.env` is required at runtime (`Settings` in `src/config/settings.py` reads it via `pydantic-settings`); see `backend/.env-example` for the required keys (`NEO4J_PASSWORD` has no default and will raise on startup if unset). `Settings` also creates the `data/{raw,processed,embeddings,fact_checks,graph,cache}` directories on import as a side effect.

### Architecture: two parallel pipelines

The codebase currently contains **two independent, non-interoperating implementations** of the news pipeline. This split is not obvious from directory names alone — check which one you're touching before making changes:

1. **Mock pipeline (currently wired to the API).**
   `src/api/routes.py` → `src/container.py` → `src/workflows/news_pipeline.py` (`NewsPipeline`) uses `src/agents/fact_checker.py` (`FactChecker`, a keyword-based mock: verdict is `"FALSE"` if the claim text contains the word "fake") and the basic `src/processors/nlp/__init__.py` (`NLPProcessor`). This is what actually runs when you `POST /news` or hit `GET /example`. It persists via `src/repositories/local_repository.py` (flat-file JSON storage under `STORAGE_PATH`).

2. **Real enrichment/fact-check pipeline (under active development, not yet wired to the API).**
   `src/workflows/enrichment.py` (`NewsEnrichmentPipeline`) runs the real NLP stack in `src/processors/nlp/` (keywords, entities, claims, topic classifier, sentiment, quality, embeddings — see `src/processors/nlp/processor.py`) to build a `src/models/enriched_article.py` (`EnrichedArticle`). This is validated and fact-checked by `src/services/fact_checker/`:
   - `validation_pipeline.py` runs `validators/topic_validator.py`, `validators/positive_impact_validator.py`, and `validators/duplicate_validator.py` (the latter does a Qdrant vector-similarity search via `VectorRepository`, gated by `settings.DUPLICATE_THRESHOLD` / `RELATEDNESS_THRESHOLD`).
   - `claim_selector.py`, `retrieval/` (evidence retriever, search provider, scraper, vector retriever), `ranking/`, and `verification/` (LLM verification + confidence scoring) are the fact-checking stages proper, in various stages of completion — `fact_checker.py` (the orchestrator meant to tie these together) is currently a design note, not an implementation.
   - Vector storage: `src/database/qdrant.py` (`QdrantDatabase`, embedded/local Qdrant at `settings.QDRANT_PATH`) + `src/repositories/vector_repository.py` (`VectorRepository`, collection `"news"`, cosine distance, dimension `settings.EMBEDDING_DIMENSION`).
   - Embeddings: `src/services/embeddings/service.py` (`EmbeddingService`, singleton wrapping a `sentence-transformers` model named by `settings.EMBEDDING_MODEL`).

   When extending fact-checking, duplicate detection, embeddings, or article validation, work in this pipeline, not `src/agents/fact_checker.py` / `src/workflows/news_pipeline.py`.

Neo4j (`src/database/neo4j_client.py`, config in `docker-compose.yml`) and the scraper agents are set up but not part of either pipeline's main flow yet.

### Scraping

`src/services/scraper/scraper.py` (`Scraper`) composes `discovery.py` (`DiscoveryService`, finds article URLs per source/topic) and `extractor.py` (`ExtractorService`, extracts article content). Multiple extraction strategies live under `src/services/scraper/strategies/` (`rss`, `beautifulsoup`, `trafilatura`, `playwright_discover`, `playwright_extraction`) — Playwright is used for JS-rendered sources (`NewsSource.requires_javascript`).

### News sources

Sources are declarative YAML files in `backend/data/sources/*.yaml`, loaded by `src/repositories/source_repository.py` (`SourceRepository`) into `src/models/source.py` (`NewsSource`) objects. Adding a new source means adding a YAML file there, not writing code.

### Tests

`backend/tests/` mirrors `src/` roughly by subsystem (`nlp/`, `scraper/`, `fact_checker/`, `database/`). `tests/factories.py` (`create_article`) builds a fully-populated `EnrichedArticle` for tests that need one; `tests/builders/source_builder.py` does the same for sources. Tests that touch Qdrant spin up a temporary on-disk database (see `tests/conftest.py`'s `repository` fixture) rather than mocking the client.

## Frontend

`frontend/` is an early-stage Next.js 14 app (App Router, TypeScript). Note the actual code (`frontend/src/app/page.tsx`, a server component fetching `http://localhost:8000/api/health`) does not yet match the design described in `frontend/README.md` (a `/` news analyzer + `/corrector` text-scoring page proxying to `app/api/analyze` and `app/api/correct`) — treat the README as the target design, not the current state, when working here.

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000
npm run build
npm run lint
```

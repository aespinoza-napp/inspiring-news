# Backend

The FastAPI service: scraping and extraction, the NLP enrichment pipeline, the
fact-checking pipeline, the job API and the storage lake.

**The working reference is [`CLAUDE.md`](CLAUDE.md) in this directory** — the
pipeline stages and their entry points, every endpoint, the storage layout, how
to run it and what its tests cover. This README used to describe the original
scaffold (a mocked `NewsPipeline`, an `agents/` layer) that no longer exists, and
was replaced rather than patched.

## Run

```bash
uv sync
uv run uvicorn src.main:app --reload        # http://localhost:8000/docs
```

It needs `inference/` reachable at `INFERENCE_URL` (default `http://localhost:8001`),
SearXNG for evidence, and an OpenAI-compatible LLM endpoint (Ollama by default).
`backend/.env` is required; copy `.env-example`.

## Layout

| Path | What is in it |
|---|---|
| `src/api/routes.py` | Every endpoint |
| `src/workflows/enrichment.py` | The NLP stack that builds an `EnrichedArticle` |
| `src/services/admission/` | Admission: topic filter, positive impact score, duplicate detection |
| `src/services/fact_checker/` | Claim selection, evidence retrieval, ranking, LLM verification |
| `src/services/analysis_service.py` | One URL through everything, and the storage writes |
| `src/services/job_*.py` | The job store, queue, runner and the on-disk journal |
| `src/config/` | Settings, per-run thresholds, topics, language lexicons |
| `src/repositories/` | Qdrant (`vector_repository`) and the three-layer lake |
| `data/sources/` | One YAML per news source |
| `tests/` | Mirrors `src/`; see `tests/README.md` |

## What does not work

Read `CLAUDE.md`'s "Known dead / known broken" before assuming something is
live: there is no ingestion pipeline, the Playwright and BeautifulSoup
strategies are placeholders, and nothing reads Neo4j.

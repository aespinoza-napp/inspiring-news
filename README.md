# Inspiring News

A pipeline that takes a news article, works out whether it is on-topic and
constructive, extracts the claims it makes, and checks each one against
evidence found on the web — with a verdict per claim that names the sources
behind it.

**Where things stand:** the analysis pipeline and its internal tools work end
to end when the supporting services are running. There is no automatic
ingestion (an article enters only when someone posts its URL), no user-facing
app, no graph database in use, and the AI models have not been benchmarked.
The plan and its honest status are in [`docs/roadmap.md`](docs/roadmap.md).

## What it does

```
URL -> extract -> enrich -> admission filter -> select claims -> retrieve evidence
                                                              -> rank -> LLM verdict
                                                              -> recalibrate confidence
```

- **Extract** the article text (Trafilatura).
- **Enrich**: keywords, entities, topics, sentiment, editorial-quality scores,
  claims, and an embedding. English and Spanish.
- **Admission filter**: on-topic, positive impact, not a duplicate.
- **Fact-check**: for the few claims the article rests on, search the web
  (SearXNG) and the stored corpus, rank what comes back, ask an LLM to judge
  each claim citing its sources, then downgrade any verdict the evidence does
  not support.
- **Store** every stage (raw → processed → exploitation) and journal every
  step of every run.

## The parts

| Directory | What it is |
|---|---|
| `backend/` | FastAPI: the pipeline, the job API, storage. See `backend/CLAUDE.md` |
| `inference/` | Model server for entity extraction, sentiment and embeddings |
| `frontend/` | Next.js 14 internal tools: analyzer, live view, claim check, enrichment, corrector |
| `docker/` | Compose stack: Neo4j (unused), SearXNG, inference, backend |
| `docs/` | The roadmap, technical architecture and the reasoning behind design choices |

`CLAUDE.md` at the repo root is the map for working in the code: what must not
be broken, what is known to be dead or broken, and where each subsystem is
documented.

## Running it

Copy the example env files. Every value in them is a working default:

```bash
cp backend/.env-example backend/.env
cp frontend/.env.local.example frontend/.env.local
cp docker/searxng/settings.yml.example docker/searxng/settings.yml
```

`backend/.env`'s `NEO4J_PASSWORD` is required by the settings even though
nothing reads Neo4j. Compose also reads it, so docker commands take
`--env-file ../backend/.env`.

Three things run outside `uv`:

- **SearXNG**, for evidence: `cd docker && docker compose --env-file ../backend/.env up searxng`
- **Ollama**, the default LLM: `ollama pull llama3.2:3b` once, then `ollama serve`.
  Point `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` at a hosted provider instead
  if you prefer.
- **`inference/`**, without which `/analyze` fails with a connection error.

### Local

```bash
cd inference && uv sync && uv run uvicorn src.main:app --port 8001   # first
cd backend   && uv sync && uv run uvicorn src.main:app --reload      # then
cd frontend  && npm install && npm run dev                           # http://localhost:3000
```

### Docker

```bash
./scripts/dev.sh          # compose stack, then the frontend
```

or `cd docker && docker compose --env-file ../backend/.env up --build`. The
first boot can take several minutes while the models download. Ollama stays on
the host. **The `backend` container has been built but never run end to end.**

The API documentation is at `http://localhost:8000/docs`. There is no
`/health` endpoint.

## Checking your work

```bash
./scripts/check.sh          # backend + inference tests + frontend typecheck
./scripts/check.sh fast     # the invariants only, in seconds
```

There is no CI, linter or formatter, and no frontend test runner: the
typecheck is the only frontend gate.

# Docker

`docker-compose.yml` brings up the three services the backend can talk to. Not required for local dev
or for running the test suite (`uv run pytest` fakes everything) — only needed to actually run the
pipeline against a real search engine end-to-end.

| Service | Image | Why |
|---|---|---|
| `searxng` | `searxng/searxng` | Self-hosted search engine the fact-checker queries for web evidence (`src/services/search.py`'s `SearxngClient`). Needs its JSON API enabled — copy `searxng/settings.yml.example` to `searxng/settings.yml` first (gitignored, holds a generated secret) |
| `neo4j` | `neo4j` | Configured but **unused** by the real pipeline — see `CLAUDE.md`: `settings.NEO4J_PASSWORD` is required at startup purely as inherited scaffold config, nothing currently reads from it |
| `backend` | built from `backend.Dockerfile` | The FastAPI app |

The backend also needs an LLM endpoint for fact-check verification — not part of this compose file,
since it defaults to a local Ollama instance running on the host (see `CLAUDE.md`'s `LLMClient` note).

## Running it

```bash
cd docker
cp searxng/settings.yml.example searxng/settings.yml   # first time only
cp ../backend/.env-example ../backend/.env             # first time only, then edit
docker compose up --build
```

Both copy steps are required, not optional: `.env` is listed under `env_file`, and compose refuses to
start at all if it is missing (`env file ... not found`). Neither file is in git — `.env` holds
secrets, `searxng/settings.yml` holds a generated secret key.

The first build downloads torch, transformers and sentence-transformers, so expect it to be slow and
the image to be large. The first *request* is slow too, for a different reason: the transformer
models (GLiNER, the embedding model, the sentiment classifier) download on first use into the
`model-cache` volume. Subsequent starts reuse it.

## Host values that are overridden in the container

Three settings in `backend/.env` are correct when the backend runs on the host and wrong inside a
container, where `localhost` means the container itself. `docker-compose.yml` overrides all three —
if you add another host-pointing URL to `.env`, it needs the same treatment:

| `.env` value | In the container |
|---|---|
| `SEARXNG_URL=http://localhost:8080` | `http://searxng:8080` — compose service DNS name |
| `NEO4J_URI=bolt://localhost:7687` | `bolt://neo4j:7687` — compose service DNS name |
| `LLM_BASE_URL=http://localhost:11434/v1` | `http://host.docker.internal:11434/v1` — Ollama runs on the *host*, not in compose. The `extra_hosts: host-gateway` entry makes that name resolve on plain Linux/WSL engines too, not just Docker Desktop |

## Volumes

Two named volumes, both deliberate:

- `backend-data` → `/app/data`: the local Qdrant collection, the analysis cache, and the three-layer
  lake (`raw`/`processed`/`exploitation`). Without it every `docker compose down` throws away the
  stored corpus, and duplicate detection has nothing left to compare against.
- `model-cache` → `/models` (`HF_HOME`): the downloaded transformer weights, so the multi-GB download
  happens once rather than on every container start.

`docker compose down -v` deletes both — including the lake.

## Known wrinkle

The `neo4j` service hardcodes `NEO4J_AUTH=neo4j/password`, which will not match `NEO4J_PASSWORD` in
your `.env` unless you happen to have set it to `password`. Nothing breaks, because nothing in the
pipeline actually reads from Neo4j — but the credentials genuinely are inconsistent, so don't spend
time debugging it if you notice.

# Docker

`docker-compose.yml` brings up the three services the backend can talk to. Not required for local dev
or for running the test suite (`uv run pytest` fakes everything) — only needed to actually run the
pipeline against a real search engine end-to-end.

| Service | Image | Why |
|---|---|---|
| `searxng` | `searxng/searxng` | Self-hosted search engine the fact-checker queries for web evidence (`src/services/search.py`'s `SearxngClient`). Runs `searxng/settings.yml` exactly as committed (mounted read-only); its secret comes from `SEARXNG_SECRET` in `backend/.env` |
| `neo4j` | `neo4j` | The graph: every finished analysis is written into it, and the frontend's `/graph` page reads it. Browser UI at http://localhost:7474. See `docs/decisions/graph.md` |
| `backend` | built from `backend.Dockerfile` | The FastAPI app |

The backend also needs an LLM endpoint for fact-check verification — not part of this compose file,
since it defaults to a local Ollama instance running on the host (see `CLAUDE.md`'s `LLMClient` note).

## Running it

```bash
cd docker
cp ../backend/.env-example ../backend/.env             # first time only, then edit
python -c "import secrets; print(secrets.token_hex(32))"   # paste as SEARXNG_SECRET in ../backend/.env
docker compose --env-file ../backend/.env up --build
```

The copy step is required, not optional: `.env` is listed under `env_file`, and compose refuses to
start at all if it is missing (`env file ... not found`). It is not in git: it holds every secret
(`NEO4J_PASSWORD`, `SEARXNG_SECRET`, `STORAGE_API_KEY`).

SearXNG's settings are *not* copied any more. `searxng/settings.yml` is committed and mounted
read-only, so the engine list that runs is the one in git. It used to be a gitignored copy of a
committed `.example`, and the copy drifted: the local one ran SearXNG's full default roster for weeks
after the allowlist was measured. A change to the engines is now a commit, then
`docker compose up -d searxng`.

## Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file ../backend/.env up -d --build
```

`docker-compose.prod.yml` is layered on top of this file and changes what a server needs: only the
API and the UI are published, on `127.0.0.1:8000` and `127.0.0.1:3000` (a reverse proxy in front of
them); every service restarts after a crash or reboot and rotates its logs (5 × 10MB);
`STORAGE_API_KEY` is required and the URL guard forced on; the backend logs JSON; and the LLM runs
as an `ollama` service, its model pulled by a one-shot `ollama-pull` before the backend starts, one
request at a time with a 180 s timeout (the dev limits time out on a CPU). Sizing, the measurements
behind each memory limit, the server choice and monitoring: `docs/decisions/deployment.md`.

It also runs the **frontend** as a container (`frontend.Dockerfile`: Next's standalone server, Node
22, ~260 MB), reaching the API as `http://backend:8000` and sending `STORAGE_API_KEY` on every call.
Built from `frontend/` like the backend is from `backend/`; `frontend/.dockerignore` keeps the host's
`node_modules`, `.next` and `.env*` out. On a laptop, `npm run dev` is still the way to work on it.

`GET /healthz` (200, or 503 naming the dependency that is down) is for an uptime monitor; `GET
/metrics` serves the run counters in Prometheus' text format.

## Google Cloud

`docker-compose.gcp.yml` adds Caddy on 80/443 (`caddy/Caddyfile`): `/healthz` to the API, and with a
domain the site to the frontend, over HTTPS, behind a password (user `editor`); without a domain,
`/healthz` alone. It needs `SITE_ADDRESS` and `SITE_PASSWORD_HASH` - the latter single-quoted in
`backend/.env`, or compose expands the `$`s in it. The VM that runs all three files is created by
`deploy/gcp/` (Terraform) and boots through `deploy/gcp/vm/bootstrap.sh`, which renders
`backend/.env`, both of those included, from Secret Manager. `./scripts/check.sh gcp` applies it to
Floci, a local Google Cloud emulator, with nothing but Docker. Everything else, the step-by-step
first deploy included: `docs/decisions/deployment.md`.

The backend image also carries Chromium for the last step of the extraction cascade (the `browser`
extra plus `playwright install --with-deps chromium`, in its own layer). That roughly doubles the
image: 1.43GB without it, 2.91GB with it (measured 2026-09-23). To build without it, drop
`--extra browser` and the `playwright install` line from `backend.Dockerfile`; the cascade then
stops after BeautifulSoup and reports `unavailable` for pages that needed a browser.

The first build downloads torch, transformers and sentence-transformers, so expect it to be slow and
the image to be large.

## Slow rebuilds

With nothing changed, `up --build` should take seconds: every layer is cached, and startup itself is
~25 s (inference loads its models in ~20 s from a warm `model-cache`, then the backend in ~4 s). If it
takes minutes, the build cache has evicted the dependency layers. Measured 2026-10-09: three
back-to-back builds with no change took 291 s, 147 s and 2 s. The build cache held 21.19 GB against
Docker Desktop's default 20 GB cap (`builder.gc.defaultKeepStorage`). Inference's dependency layer
alone is 2.7 GB, and the backend's dependencies plus Chromium are 1.85 GB, so rebuilding either one
evicts the other's cached layers. Re-creating a layer also means re-exporting it, and with Docker
Desktop's containerd image store that dominates: 84 s to compress inference's dependency layer and
17 s to unpack it, on top of 42 s for `uv sync`.

Check with `docker system df` (the `Build Cache` row). The fix is to raise the cap in Docker Desktop
→ Settings → Docker Engine (`"defaultKeepStorage": "60GB"`), then Apply & restart. A uv cache
mount in both Dockerfiles keeps downloaded wheels across builds. A lockfile change then
re-downloads only what changed, but the export cost above stays whenever the dependency layer is
rebuilt. The first *request* is slow too, for a different reason: the transformer
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

Three named volumes, all deliberate:

- `backend-data` → `/app/data`: the local Qdrant collection, the analysis cache, and the three-layer
  lake (`raw`/`processed`/`exploitation`). Without it every `docker compose down` throws away the
  stored corpus, and duplicate detection has nothing left to compare against.
- `model-cache` → `/models` (`HF_HOME`): the downloaded transformer weights, so the multi-GB download
  happens once rather than on every container start.

- `neo4j-data` → `/data`: the graph. It used to be the image's anonymous volume, so a recreated
  container silently started an empty database. The graph can always be rebuilt from the lake and the
  labelled facts (`POST /graph/sync`), but that should be a choice.

`docker compose down -v` deletes all three — including the lake.

## Neo4j credentials

The `neo4j` service takes its password from `NEO4J_PASSWORD` in `backend/.env`, so the two cannot
disagree. Compose only interpolates from the shell or an env file, which is why every command above
passes `--env-file ../backend/.env` — without it compose stops with `set NEO4J_PASSWORD`.

The compose file used to contain the password in plain text, so it is in git history. Whatever value
was committed there is compromised: pick a new one in `backend/.env`, and recreate the Neo4j data
(`NEO4J_AUTH` only applies when the database is first created).

# Docker

`docker-compose.yml` brings up the three services the backend can talk to. Not required for local dev
or for running the test suite (`uv run pytest` fakes everything) — only needed to actually run the
pipeline against a real search engine end-to-end.

| Service | Image | Why |
|---|---|---|
| `searxng` | `searxng/searxng` | Self-hosted search engine the fact-checker queries for web evidence (`src/services/search.py`'s `SearxngClient`). Needs its JSON API enabled — copy `searxng/settings.yml.example` to `searxng/settings.yml` first (gitignored, holds a generated secret) |
| `neo4j` | `neo4j` | Configured but **unused** by the real pipeline — see `CLAUDE.md`: `settings.NEO4J_PASSWORD` is required at startup purely as inherited scaffold config, nothing currently reads from it |
| `backend` | built from `backend.Dockerfile` | The FastAPI app. Gets `SEARXNG_URL` overridden to the container-to-container DNS name (`http://searxng:8080`) — the `.env` default of `localhost` only works when the backend runs on the host, not in a container |

The backend also needs an LLM endpoint for fact-check verification — not part of this compose file,
since it defaults to a local Ollama instance running on the host (see `CLAUDE.md`'s `LLMClient` note).

```bash
cd docker
cp searxng/settings.yml.example searxng/settings.yml   # first time only
docker-compose up --build
```

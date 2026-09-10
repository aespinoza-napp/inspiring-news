# inference

A model server for the transformer models `backend/` used to load
in-process: GLiNER (entities), a sentiment classifier, and a
sentence-transformer (embeddings). It knows nothing about `backend/`'s
business logic - no `TOPICS`, no thresholds, no scoring decisions -
that stays in `backend/`, which calls this service over HTTP through
`backend/src/services/inference_client.py`, the same way it already
calls Ollama through `LLMClient`.

## Commands

```bash
uv sync
uv run uvicorn src.main:app --port 8001
uv run pytest
```

## Endpoints

- `POST /entities` - `{"text", "threshold"?, "labels"?}` → `{"entities": {...}}`
- `POST /sentiment` - `{"text"}` → sentiment fields
- `POST /embeddings` - `{"text"}` or `{"texts": [...]}` → a vector or list of vectors
- `GET /healthz` - 200 only once all three models are loaded; 503
  ("warming_up") until then. Every other route returns 503 the same way
  while warming up, rather than blocking on the model load.

See `docs/decisions/` in the repo root for why this service exists.

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

**Windows:** the first run downloads GLiNER, the sentiment model and the
embedding model into the Hugging Face cache, which symlinks blobs by
default. Creating a symlink needs a privilege a normal account doesn't
have unless Developer Mode is on, so the download can fail with
`OSError: [WinError 1314]` right after the weights finish downloading -
`/healthz` then stays 503 forever. Either turn on Developer Mode
(Settings → Privacy & security → For developers), or skip symlinks
entirely for this cache:
```powershell
$env:HF_HUB_DISABLE_SYMLINKS = "1"
uv run uvicorn src.main:app --port 8001
```

## Endpoints

- `POST /entities` - `{"text", "threshold"?, "labels"?}` → `{"entities": {...}}`
- `POST /sentiment` - `{"text"}` → sentiment fields
- `POST /embeddings` - `{"text"}` or `{"texts": [...]}` → a vector or list of vectors
- `GET /healthz` - 200 only once all three models are loaded; 503
  ("warming_up") until then. Every other route returns 503 the same way
  while warming up, rather than blocking on the model load.

See `docs/decisions/` in the repo root for why this service exists.

# Inference: the models live in their own service

> Read this before touching `backend/src/services/inference_client.py`,
> `backend/src/processors/nlp/{entities,sentiment}.py`,
> `backend/src/services/embeddings/service.py`, or anything under
> `inference/`.

Three transformer models — GLiNER (entities),
`cardiffnlp/twitter-xlm-roberta-base-sentiment`, and the
`BAAI/bge-m3` sentence-transformer — used to load **inside the backend
process**, alongside FastAPI, the fact-checker, Qdrant and all the
business logic. They now live in `inference/`, a separate service and
container, reached over HTTP.

## Why

`backend/` was one process holding an API, orchestration logic, a
vector store client and ~3GB of model weights, with `torch`,
`transformers`, `gliner` and `sentence-transformers` in the same
dependency set as `fastapi` and `playwright`. That had three concrete
costs:

- **Build fragility.** The ML wheels dominated the image build and
  were the single most network-exposed step (see commit `418eb73` —
  the CUDA-toolkit pull that broke `docker compose up --build`
  outright).
- **Startup behaviour.** Models loaded *lazily on first request*
  (`container.py`'s lazy singletons), so the first `/analyze` after a
  cold boot silently paid a 10–15s model load — indistinguishable from
  "the app is broken" to whoever sent it.
- **One resource pool, sized wrong.** CPU-bound inference competed
  with request handling in a single process with no `--workers`, under
  one `mem_limit` — and that limit was **1g**, while the three models
  measure **3.58GiB resident** (`docker stats`, warm and idle, after
  the split). Under that cap the kernel would OOM-kill the backend
  container the moment a request triggered the lazy model load: on the
  first real `/analyze`, not at boot. That matches the reported
  symptom ("the container starts fine and then sometimes doesn't
  work") and is also precisely how Qdrant's exclusive lock gets left
  stale, since an OOM kill is the least graceful shutdown available.
  Not directly observed — the backend container had never been run end
  to end before this change — so treat it as a definite latent bug and
  the strongest candidate for the flakiness, not a confirmed
  diagnosis. After the split: backend 230MiB/512m, inference
  3.58GiB/6g.

The codebase already had the right precedent: `LLMClient`
(`backend/src/services/llms.py`) has always treated a heavy AI
dependency — Ollama — as an external HTTP service. This applies the
same shape to the other three.

## The design

**Adapter, not rewrite.** `EntityExtractor`, `SentimentAnalyzer` and
`EmbeddingService` kept their exact public signatures and simply
delegate to `InferenceClient`. Nothing downstream changed —
`NewsEnrichmentPipeline`, `ClaimExtractor`, `TopicClassifier`,
`TextCorrector` and the fact-checker's retrieval/ranking chain only
ever called `.process()` / `.encode()` / `.similarity()`, never
`.model`. This was verified against every call site before the
refactor, not assumed.

**A dumb model server.** `inference/` knows nothing about `TOPICS`,
`PipelineThresholds`, or any scoring decision. `TopicClassifier` still
owns the topic vocabulary, the threshold and the cosine/softmax maths
(pure numpy — no model needed for arithmetic on vectors you already
have); it just gets its vectors over HTTP now. This keeps tuning inside
backend's existing config and lineage system rather than forking it
across two deploy units.

**One service, not three.** The three models share a dependency stack,
a warm-up lifecycle and a resource pool. Splitting further would
triple the Compose surface for no isolation anyone asked for.

**Qdrant stayed.** `VectorRepository` is a local vector store, not a
transformer. Its actual problem is the exclusive file lock, fixed by
`stop_grace_period` in `docker-compose.yml`, not by relocation — and
moving it would mean abandoning Qdrant's local mode entirely.

## Error handling differs per component, deliberately

| Component | On failure | Why |
|---|---|---|
| `EntityExtractor` | returns `{}` | `ClaimExtractor` already treats "no entities" as one weak signal among several in its scoring — an outage should weaken a sentence's score, not fail the run. Mirrors `LLMClient`'s `None`. |
| `SentimentAnalyzer` | raises `InferenceUnavailable` | `PositiveImpactScorer` (admission) reads `sentiment.positive`/`negative` as core admission inputs. A silently neutral result would corrupt an admission decision. |
| `EmbeddingService` | raises `InferenceUnavailable` | Feeds duplicate detection, evidence ranking and topic classification. A zeroed vector breaks those silently. |

Both raising cases propagate through `AnalysisService`'s existing
per-URL `try/except` and surface as a failed URL. `LLMClient`'s
degrade-to-`None` contract exists because *its* callers were written to
treat "no answer" as a legitimate outcome (an `UNVERIFIED` verdict) —
that is a property of the caller, not a rule about external services.

## Readiness

`GET /healthz` returns 200 **only once all three models are loaded**,
not merely when the process starts. Models warm up in a background
thread so uvicorn accepts connections immediately and can answer 503
honestly, rather than blocking its own startup for minutes. Compose's
`depends_on: inference: { condition: service_healthy }` then holds
backend back until the models are hot — converting the old
first-request stall into an explicit, one-time, up-front wait.

`start_period` is **900s**, and that number is measured, not guessed: a
genuinely cold `model-cache` volume took ~11 minutes to go healthy.
This matters more than a normal healthcheck tuning knob, because
Compose treats a dependency that reports `unhealthy` *before*
`start_period` elapses as failed and refuses to start backend at all.

## Consequences to know about

- **Running locally now takes two processes.** `INFERENCE_URL` defaults
  to `http://localhost:8001` — start `inference/` first.
- **Backend tests that need a real model skip when it isn't running**
  (`backend/tests/conftest.py::require_inference`). Real model behaviour is
  tested in `inference/tests/`; adapter behaviour is tested with stubs
  and needs nothing running.
- **`SENTIMENT_MODEL` / `EMBEDDING_MODEL` in `backend/.env` became
  documentary.** The models load from `inference/src/config.py`. This
  is a genuine trap the split introduced, recorded in CLAUDE.md's
  "Known dead / known broken".
- **Per-call latency now crosses an HTTP boundary.** Not yet measured
  under real load. `EvidenceRetriever._quick_score` encodes candidates
  one at a time in a loop, which is now N sequential round-trips per
  claim; `InferenceClient.encode_many` exists and that loop should be
  batched — a known, deliberate follow-up, not folded into the split.
- **Version pinning is not optional here.** `inference/pyproject.toml`
  pins `transformers==4.57.6` and friends to exactly what `backend`
  resolved before the split. Left as open ranges, `uv lock` picked
  `transformers` 5.x, which breaks GLiNER's tokenizer loading outright
  (`tiktoken` required to read a tiktoken file).

## Why the sentiment model is not quantized (measured 2026-09-28)

int8 through ONNX was tried to cut CPU and memory, and rejected on the
numbers. `cardiffnlp/twitter-xlm-roberta-base-sentiment` exported to
ONNX (opset 17) and quantized with onnxruntime 1.29, scored against the
PyTorch model on 336 real texts (48 articles fresh from the configured
feeds, whole bodies and single sentences, half English, half Spanish):

| Variant | Size | ms/text | Same label | Polarity diff p95 |
|---|---|---|---|---|
| PyTorch fp32 (what runs) | 1061 MB | 58 | - | - |
| ONNX fp32, no quantization | 1061 MB | 54 | 336/336 | 0.000 |
| dynamic int8, per-tensor | 266 MB | 31 | 290 (86%) | 0.32 |
| dynamic int8, best variant* | 266 MB | 32 | 307 (91%) | 0.21 |
| dynamic int8, last 4 layers + head fp32 | 347 MB | 42 | 308 (92%) | 0.17 |
| weight-only int8 (MatMulNBits) | 820 MB | 145 | 331 (98.5%) | 0.025 |

\* MatMul + Gather, per-channel, `reduce_range`. Per-channel alone,
MatMul-only (embeddings left fp32) and excluding the classifier head all
landed between 85% and 92%.

- **The fast variants change the answer, and in one direction.** The
  label flips were mostly neutral → positive (10-23 of them against 1
  the other way). Sentiment feeds the positive-impact admission gate,
  so that is a gate quietly loosened, not noise.
- **The accurate variant costs more than it saves:** 2.5x slower, and
  the 732 MB word-embedding matrix (250k tokens x 768) is most of the
  model and is not what weight-only quantization shrinks.
- **ONNX alone buys nothing:** identical answers, 7% faster, more
  resident memory.

What would actually shrink it: trimming the 250k-token vocabulary to
the tokens English and Spanish use, since that matrix is ~70% of the
weights. And the larger model here is `bge-m3` (~568M parameters), not
this one or GLiNER (`gliner_small`, the smallest of the three) - but
quantizing it changes every stored vector, so it waits for the gold set.

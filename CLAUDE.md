# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

This file is injected into **every session**, so it holds only what is
needed on every session: how to navigate, what must not be broken, and
what is not true. Subsystem detail and the history behind each rule live
in `docs/decisions/`, linked below — read those when you open that area.

## Verify with one command

```bash
./scripts/check.sh           # backend + inference tests + frontend typecheck
./scripts/check.sh fast      # invariants only, seconds, no models loaded
./scripts/check.sh inference # the real models, in their own service
./scripts/check.sh slow      # the whole data/raw corpus, minutes
./scripts/check.sh graph     # the graph against a real Neo4j; fails if it is down
./scripts/check.sh gcp       # deploy/gcp/ applied to Floci (local GCP emulator); Docker only
./scripts/check.sh labeller  # the fact labeller, plain python
```

`make check` / `make fast` / `make slow` do the same. Use these rather
than composing your own: the frontend is typechecked from a different
directory, and the slow tests are excluded by a registered `slow` marker
(`addopts` in `pyproject.toml`) rather than by a path flag nobody
remembers. **`./scripts/check.sh` is the definition of "done".**

Backend tests that need a real model skip when `inference/` isn't
running (`backend/tests/conftest.py::require_inference`) — `check.sh`
does not start it. To actually exercise those, bring it up first:
`docker compose up inference`, or `cd inference && uv run uvicorn
src.main:app --port 8001`.

## Repository layout

- `backend/` — Python/FastAPI scraping, enrichment and fact-checking
  pipeline. See `backend/CLAUDE.md`.
- `inference/` — model server owning GLiNER, the sentiment classifier
  and the embedding model. Backend reaches it over HTTP; it knows
  nothing about topics, thresholds or scoring. See `inference/README.md`.
- `frontend/` — Next.js 14 (App Router + TypeScript) UI. See
  `frontend/CLAUDE.md`.
- `docker/` — compose (Neo4j, SearXNG, inference, backend) and the two
  Dockerfiles; `docker-compose.prod.yml` (+ Ollama) and
  `docker-compose.gcp.yml` (+ Caddy) layer on top.
- `deploy/gcp/` — Terraform for the Google Cloud VM, its secrets,
  network, snapshots and alerts; `vm/bootstrap.sh` is what the VM runs
  on boot. Checked against Floci by `./scripts/check.sh gcp`.
- `labeller/` — the tool for hand-labelling the custom validation set:
  `python labeller/app.py`, standard library only, nothing from
  `backend/`. One file per fact in `backend/data/evaluation/manual/`;
  `join` merges them. Its Today tab gets the day's articles and claims
  from the backend's `POST /labelling/batch` over HTTP and keeps them in
  `backend/data/evaluation/queue/`. See `labeller/README.md`.
- `docs/decisions/` — why things are the way they are.

## Navigation

| Looking for | Go to |
|---|---|
| The plan, and what is actually done | `docs/roadmap.md` |
| Pipeline stages, entry points, container | `backend/CLAUDE.md` |
| What decides whether an article is checked at all | `backend/src/services/admission/README.md` |
| Why the models live in their own service | `docs/decisions/inference.md` |
| Per-run thresholds, how overrides resolve | `docs/decisions/thresholds.md` |
| The three storage layers and lineage | `docs/decisions/storage.md` |
| How claims run in parallel; the resource ceilings | `docs/decisions/concurrency.md` |
| What is searched for; why a source is cut | `docs/decisions/retrieval.md` |
| Why a given rule exists; what broke before | `docs/decisions/incidents.md` |
| The extraction cascade and what it counts | `docs/decisions/scraping.md` |
| The Neo4j graph: schema, write path, console | `docs/decisions/graph.md` |
| Pages, polling hook, API proxies | `frontend/CLAUDE.md` |
| Running the stack | `docker/README.md` |
| Production, Google Cloud, sizing, `/healthz` and `/metrics` | `docs/decisions/deployment.md` |
| The evaluation harness: research questions, record format, metrics, stage attribution | `docs/decisions/evaluation.md` |
| Ready-to-paste `/goal` prompts for the harness, CI and the integration test | `docs/goals.md` |

## Invariants

Broken rules cost more than absent ones, so most of these are enforced by
`backend/tests/test_invariants.py` — that file is the authority, this
list is the summary. When one fails, either change the code or change
the declared exception, deliberately.

1. **Never write `MIN_X = settings.MIN_X` in a class body.** It is
   evaluated once at import and freezes for the life of the process.
   Thresholds are passed **per call** (`admit(article, thresholds)`,
   `process(text, threshold)`, `run(article, thresholds=...)`), because
   the components are long-lived singletons shared by every request.
   `None` always means "use the defaults". *Declared exception:* the
   ranking and confidence **weights**, which are environment-only —
   each group must sum to 1.0, or `Settings` refuses to start
   (`WEIGHT_GROUPS`). Tests see them pinned via `tests/frozen_settings.py`.
2. **Every per-run tunable lives in `src/config/thresholds.py`.** A
   value read straight from `settings` cannot be overridden for one run.
3. **Bump `AnalysisCache.SCHEMA_VERSION` whenever `analyze()` changes
   response shape,** and record the new key set in
   `ANALYZE_RESPONSE_SHAPE`. The cache never expires and a hit never
   rewrites its entry, so a stale shape is served forever.
4. **No test module calls its own test function at module level.** That
   runs during *collection*; it has already taken the whole suite down
   once.
5. **No test asserts against a threshold read from `settings`.** `.env`
   is not in git. `conftest.py`'s `pinned_settings` pins every setting to
   its declared default; pass thresholds explicitly instead.
6. **Don't add a pipeline stage without calling `on_phase` for it,** with
   a string literal — the frontend's `PhaseStepper` matches literals.
7. **No `__init__.py` anywhere in `src/`** — it is a namespace package
   throughout, and the Docker image imports it from the working
   directory rather than installing it.
8. **Both `en` and `es` keep complete lexicons.** Adding a source in a
   third language fails the suite rather than silently scoring it as
   English.
9. **No test saves through a `LocalRepository` over `data/raw` or
   `data/processed`.** Both hold committed sample files; saving there
   rewrites tracked data on every run. Read from them freely; write to
   `tmp_path`.
10. **Every shared fake in `tests/services/fact_checker/fakes.py` has a contract
    entry** in `tests/test_fake_contracts.py`, so a fake cannot drift
    out of signature with the collaborator it stands in for.
11. **Results of a fan-out come back in input order.** Use
    `bounded_map`, not a bare `ThreadPoolExecutor`: an evidence list in
    completion order re-points every LLM citation at a different source,
    which is a wrong answer rather than a crash. *Enforced by*
    `tests/services/test_concurrency.py`.
12. **Concurrency ceilings are `settings`, never `PipelineThresholds`.**
    They cap how hard this process leans on SearXNG, `inference/`, the
    LLM and other people's web servers, all shared by every concurrent
    run - a per-request override lets one caller raise the load everyone
    else is subject to. Same standing as `ANALYSIS_MAX_CONCURRENCY`;
    listed in `NON_THRESHOLD_SETTINGS`.
13. **`backend/src/` never imports `torch`, `transformers`, `gliner` or
    `sentence_transformers`.** Those models live in `inference/` and are
    reached over HTTP. Re-adding a local import silently puts ~2GB of
    wheels and a model load back into the API container — the exact
    thing the split removed.

## Known dead / known broken

The code invites several confident wrong conclusions. It is cheaper to
write them down than to have each be rediscovered.

- **Ingestion runs only when someone asks.** `POST /ingest` (the
  Scraper page's panel) discovers from the configured sources and queues
  each new article as an ordinary analysis job. Nothing runs on a timer.
  Three configured feed URLs (National Geographic, Reuters, SINC) return
  404 and no replacement feed exists: they are discovered from topic
  section pages instead. EFE and Reuters refuse this scraper outright
  (403/401). The topic keywords are English only,
  so Spanish sources are not pre-filtered by topic
  (`docs/decisions/scraping.md`).
- **The headless browser is optional and usually absent locally.**
  `playwright` is the `browser` extra; `./scripts/check.sh` never
  installs it, and without it (or without `playwright install chromium`)
  the last step of the extraction cascade reports `unavailable` and the
  cascade keeps the previous step's answer. The Docker image installs
  both. `docs/decisions/scraping.md`.
- **The graph is written by the pipeline and the sync, not the
  labeller.** Every finished analysis lands in Neo4j (fail-soft, after
  the lake). Hand-labelled facts only get there through `POST
  /graph/sync` (the Sync button on `/graph`): the labeller imports
  nothing from `backend/`. The lake is the record, the graph a view that
  sync rebuilds. `docs/decisions/graph.md`. `motor` (MongoDB) is an
  unused dependency.
- **`TopicPrediction.probability` carries no signal.** It is a softmax
  over raw cosine similarities across ~22 topics, so it comes back
  near-uniform (0.049 top vs 0.044 bottom). Use `confidence`.
- **The containers run full analyses; Google Cloud has never been
  applied.** Since 2026-10-01 a whole analysis has run inside the dev
  stack and inside the production one (`docker-compose.prod.yml`, LLM on
  CPU in its own container). `deploy/gcp/` has only ever been applied to
  Floci, which runs no guest: the VM's boot is unverified
  (`docs/decisions/deployment.md`). `inference`'s port 8001 is not
  published to the host, so backend tests on the host still skip the
  model tests unless a local `inference/` runs.
- **The dev LLM limits are wrong for a CPU.** `LLM_MAX_CONCURRENCY=2`
  and `LLM_TIMEOUT=30` assume the laptop's GPU; on a CPU they turned 3 of
  4 verdicts into "LLM provider was unreachable". The production file
  overrides both. Running Ollama CPU-only locally needs the same.
- **`SENTIMENT_MODEL` and `EMBEDDING_MODEL` in `backend/.env` are
  documentary.** The models load in `inference/`, from
  `inference/src/config.py`'s own defaults. Editing the backend values
  changes nothing — a real trap the split introduced. `EMBEDDING_DIMENSION`
  *is* still live (it sizes the Qdrant collection), which is why
  `tests/services/embeddings/test_embedding_dimension_live.py` exists.

## Concurrency

Claims are fact-checked **concurrently**; each claim's own stages stay
**sequential** (retrieval feeds ranking feeds the LLM). Read
`docs/decisions/concurrency.md` before touching any of it. The three
rules that matter everywhere:

- **A resource permit is only ever held around a leaf call.** The
  ceilings live in `src/services/concurrency.py`, applied inside the
  client that talks to each service. Acquiring one and then waiting on
  work that needs the same resource is the bounded-pool deadlock.
- **`bounded_map` returns results in input order.** Evidence indices are
  what the LLM cites by number and what `cited_evidence_indices` means;
  completion order would silently re-point every citation.
- **`on_phase` is called from several threads and is serialised for
  you** by `FactChecker._serialised`. Per-claim events interleave, and
  every one carries `claimIndex` as well as `claim`.

## Known slow / known unverified

Found by the 2026-09-21 audit; `docs/roadmap.md` tracks them under
Phase 1.

- **The article verdict is worst-claim-wins**, so one `UNVERIFIED` outweighs
  any number of `TRUE`. `overall_confidence` averages across verdicts.
- **`JobStore` never evicts**, and the analysis cache never expires (and caches
  rejections).
- **URLs are compared as plain strings** for duplicate detection.
- **Only the 36 configured domains have a real reliability rating**; every
  other domain gets the default and is flagged `reliability_known: false`.
- **The LLM's accuracy has never been measured** against labelled data — and
  the pertinence gate's default threshold is reasoned, not fitted, for the
  same reason (`docs/decisions/retrieval.md`).
- **Nothing measures whether a source is on-point about the *right*
  subject.** The pertinence gate is embedding and term arithmetic: it
  catches a page about something else, not a page about the same subject
  making a different claim.
- **Web search mostly returns nothing, and it looks like a verdict.**
  Measured 2026-09-25: 68 of 69 SearXNG queries empty, because its
  engines were rate-limited, CAPTCHA'd or timing out. A claim with no
  evidence comes back `UNVERIFIED`, indistinguishable from a real one.
  Check the "Source health" panel on `/scraper` before reading anything
  into a run's verdicts (`docs/decisions/retrieval.md`). Since
  2026-09-30 a claim whose search failed says `searchUnavailable`, and
  a failed query falls back to DuckDuckGo directly - which, the same
  day, challenged every request from this machine as a bot, so do not
  count on the fallback rescuing a run here. On 2026-10-01 every search
  in three runs answered (20-22 results), after compose's SearXNG
  healthcheck stopped sending a real search to every engine every 5
  seconds - likely a cause, not proven. `/metrics` counts empty and
  failed searches (`inspiring_web_searches_total`).
- **The speedup is measured against a simulated network, not the live
  stack.** `scripts/bench_claim_concurrency.py` (2026-10-04): ×3.4 on one
  four-claim article with a fast model, ×1.16 with production's CPU LLM
  at one call at a time, where the model is 180 of the 184 s
  (`docs/decisions/concurrency.md`). The job journal's timestamps make a
  live before/after possible.

## Conventions

- No linter or formatter is configured (no ruff/black/mypy config) —
  don't assume one. Match the surrounding style: generous vertical
  spacing, comments that explain *why*.
- Comments record decisions and incidents, not restatements of the code.
  If a comment says "reproduced live", it happened; keep it.

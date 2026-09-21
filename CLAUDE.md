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
  Dockerfiles.
- `docs/decisions/` — why things are the way they are.

## Navigation

| Looking for | Go to |
|---|---|
| The plan, and what is actually done | `docs/roadmap.md` |
| Pipeline stages, entry points, container | `backend/CLAUDE.md` |
| Why the models live in their own service | `docs/decisions/inference.md` |
| Per-run thresholds, how overrides resolve | `docs/decisions/thresholds.md` |
| The three storage layers and lineage | `docs/decisions/storage.md` |
| Why a given rule exists; what broke before | `docs/decisions/incidents.md` |
| Pages, polling hook, API proxies | `frontend/CLAUDE.md` |
| Running the stack | `docker/README.md` |

## Invariants

Broken rules cost more than absent ones, so most of these are enforced by
`backend/tests/test_invariants.py` — that file is the authority, this
list is the summary. When one fails, either change the code or change
the declared exception, deliberately.

1. **Never write `MIN_X = settings.MIN_X` in a class body.** It is
   evaluated once at import and freezes for the life of the process.
   Thresholds are passed **per call** (`validate(article, thresholds)`,
   `process(text, threshold)`, `run(article, thresholds=...)`), because
   the components are long-lived singletons shared by every request.
   `None` always means "use the defaults". *Declared exception:* the
   ranking and confidence **weights**, which are environment-only —
   each group must sum to 1.0.
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
11. **`backend/src/` never imports `torch`, `transformers`, `gliner` or
    `sentence_transformers`.** Those models live in `inference/` and are
    reached over HTTP. Re-adding a local import silently puts ~2GB of
    wheels and a model load back into the API container — the exact
    thing the split removed.

## Known dead / known broken

The code invites several confident wrong conclusions. It is cheaper to
write them down than to have each be rediscovered.

- **There is no ingestion pipeline.** `Scraper`, `DiscoveryService`,
  `RSSDiscoveryStrategy` and the twelve source YAMLs exist and nothing
  calls them. The only way an article enters the system is a human
  posting a URL to `/analyze`. `Scraper.discover()` passes the `TOPICS`
  dict where `list[str]` is declared and `Scraper.extract()` ignores its
  `topics` argument — unexercised code that has already drifted.
- **The Playwright and BeautifulSoup extraction strategies do not
  work.** `BeautifulSoupStrategy.extract()` returns `None`. Both are
  annotated `Optional[News]` while `ExtractionStrategy.extract` is
  declared `-> ExtractionResult | None`, and Playwright actually
  constructs a `News`. Wiring either into `ExtractorService` raises
  `AttributeError` in `ExtractionValidator.is_valid()` (`.body` vs
  `.content`). They are traps, not placeholders.
- **Nothing reads Neo4j.** `settings.NEO4J_PASSWORD` is required at
  startup as inherited scaffold config only. `motor` (MongoDB) is
  likewise an unused dependency.
- **`TopicPrediction.probability` carries no signal.** It is a softmax
  over raw cosine similarities across ~22 topics, so it comes back
  near-uniform (0.049 top vs 0.044 bottom). Use `confidence`.
- **The `backend` container has not been run.** All build stages
  succeed and it has never been started end to end. The `inference`
  container *has* — built, brought up, reached `healthy`, and served
  real `/entities`, `/sentiment` and `/embeddings` requests.
- **`SENTIMENT_MODEL` and `EMBEDDING_MODEL` in `backend/.env` are
  documentary.** The models load in `inference/`, from
  `inference/src/config.py`'s own defaults. Editing the backend values
  changes nothing — a real trap the split introduced. `EMBEDDING_DIMENSION`
  *is* still live (it sizes the Qdrant collection), which is why
  `tests/services/embeddings/test_embedding_dimension_live.py` exists.

## Known slow / known unverified

Found by the 2026-09-21 audit and not yet fixed; `docs/roadmap.md` lists them
under Phase 1.

- **Claims are verified one at a time**, and each does two searches, up to
  five sequential page scrapes, ~20 single-text embedding calls and one LLM
  call. This is the suspected bottleneck; it has not been measured. The job
  journal's timestamps make that possible.
- **The local Qdrant client has no locking** and is used by up to three job
  threads at once (`ANALYSIS_MAX_CONCURRENCY`). Untested under load.
- **The article verdict is worst-claim-wins**, so one `UNVERIFIED` outweighs
  any number of `TRUE`. `overall_confidence` averages across verdicts.
- **`JobStore` never evicts**, and the analysis cache never expires (and caches
  rejections).
- **URLs are compared as plain strings** for duplicate detection.
- **Only the 12 configured domains have a real reliability rating**; every
  other domain gets the default and is flagged `reliability_known: false`.
- **The LLM's accuracy has never been measured** against labelled data.

## Conventions

- No linter or formatter is configured (no ruff/black/mypy config) —
  don't assume one. Match the surrounding style: generous vertical
  spacing, comments that explain *why*.
- Comments record decisions and incidents, not restatements of the code.
  If a comment says "reproduced live", it happened; keep it.

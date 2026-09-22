# Roadmap

The plan, and what is true of it **today**. Every checkbox below was checked
against the code, not against the plan. `[x]` means done *and* working as
described; anything less is `[ ]` with a note saying exactly how far it got.

- **As of:** 2026-09-21 — Phase 1, Sprint 2 (Sep 15–28).
- **Hours** are the planned budget. There is no time log in the repo, so
  nothing here claims hours actually spent.
- **Verification used for "done"** is `./scripts/check.sh`: 542 backend tests
  passed (11 skipped because they need `inference/` or Neo4j running, 2 slow
  ones deselected), 9 inference tests passed against the real models, and the
  frontend typechecks. The `slow` corpus test was not part of that pass. There
  is no frontend test runner, no CI, and no linter.

Legend: `[x]` done · `[ ]` not done · 🟡 partly done (what is left is stated) ·
⚠️ the original plan had this ticked and it is not fully true.

---

## Phase 0 — Foundations (Jun 1 – Jul 31)

### Sprint 0.1 — Setup & Scraping Core (Jun 1–14) · 80h

- [x] 🗂️ Monorepo structure (`backend/`, `frontend/`, `docker/`) — since then also `inference/`, `docs/`, `scripts/`
- [x] ⚙️ FastAPI skeleton + `pydantic-settings` config
- [x] 🔎 `ExtractorService` (Trafilatura) — used by `/analyze` and by the evidence scraper
- [ ] ⚠️ 🟡 `DiscoveryService` (RSS strategy) — the code and its tests exist, but **nothing calls it**. There is no ingestion: an article enters the system only when a person posts its URL to `/analyze`. Never exercised against live feeds.
- [x] 📄 Declarative YAML news sources (`SourceRepository`) — 12 sources, 7 of them Spanish. `NewsSource.requires_javascript` exists in the model and YAMLs but nothing reads it.
- [x] 🐳 `docker-compose.yml` — Neo4j, SearXNG, `inference`, backend. ⚠️ the `backend` container has been built but never run end to end; Neo4j is unused.

### Sprint 0.2 — Enrichment Pipeline (Jun 15–28) · 80h

- [x] 🏷️ Keyword (yake) / entity (GLiNER) extraction
- [x] 📌 Claims extraction module (English and Spanish lexicons)
- [x] 🗃️ Topic classifier + sentiment + quality scoring — `TopicPrediction.probability` carries no signal (near-uniform softmax); use `confidence`
- [x] 🔢 Embedding service — now `BAAI/bge-m3` in the separate `inference/` service, reached over HTTP
- [x] 🧩 `NewsEnrichmentPipeline` → `EnrichedArticle` model

### Sprint 0.3 — Fact-Checking Pipeline v1 (Jun 29–Jul 12) · 80h

- [x] ✅ Validation pipeline (topic / positive-impact / duplicate validators) — the constructiveness and inspirational hard-fails are deliberately off; the objectivity and negative-sentiment hard-fail is a single setting (`POSITIVE_IMPACT_HARD_FAIL_ENABLED`, overridable per run) and is **off by default** in the current `settings.py`
- [x] 🎯 `ClaimSelector` — now ranks by how load-bearing a claim is and keeps an "anchor band" (`anchor_claims_min`/`max`), rather than the original confidence ranking
- [x] 🌐 Evidence retrieval (SearXNG web + Qdrant internal corpus) — two queries per claim (affirmative + refutation), one source per domain. Searches, scrapes and embedding calls run **one after another**.
- [x] 📈 `EvidenceRanker` (similarity + recency + reliability) — reliability is a real rating only for the 12 configured domains; every other domain gets the default 0.5 and is flagged `reliability_known: false`
- [x] 🤖 `LLMVerifier` + `ConfidenceScorer` (hard UNVERIFIED fallback) — works, but its accuracy has never been measured against labelled data (that is Phase 4)

### Sprint 0.4 — Job API, Frontend v1 & Fixes (Jul 13–31) · 60h

- [x] 🔄 `/analyze` sync + `/analyze/jobs` async + polling (since then also a bulk endpoint)
- [x] ✍️ `/correct` corrector endpoint (7 metrics)
- [x] 🖥️ Frontend v1 (analyzer + corrector pages, `PhaseStepper`)
- [x] 🔒 Lazy container + `RLock` deadlock fix
- [x] 🐛 Test-collection side-effect bugs fixed

---

## 🌴 Vacation Pause (Aug 1 – Aug 31) · 0h

- [x] 😎 Rest, recharge, no dev work logged this month
- [x] 🧾 This pause was already part of the original plan

---

## 🔧 Phase 1 — Pipeline Completion (Sep 1 – Sep 28) · 140h

### Sprint 1 (Sep 1–14) · 70h — Stabilize the core pipeline

- [x] 🧵 Close remaining pipeline edge cases — but see "Found by the Sep 21 audit" below: one serious edge case (a re-analysed URL rejected as a duplicate of itself) was still open and was fixed then.
- [x] 🧯 Review `on_phase` callback coverage across all stages — extended on Sep 21 with per-source events (`searching_web`, `web_results`, `scraping_sources`, `sources_scraped`, `evidence_ranked`)
- [x] 🗃️ Audit `AnalysisCache` correctness (`forceRefresh` behavior) — the key hashes the *effective* thresholds; a cache write that fails no longer fails the job; schema version 6
- [x] 🧪 Expand the fact-checker fakes — `tests/services/fact_checker/fakes.py`, with `tests/test_fake_contracts.py` pinning every fake's signature to the real class
- [x] 📋 Fix pre-existing failing tests — the suite is green. The 11 skips need `inference/` or Neo4j running.

### Sprint 2 (Sep 15–28) · 70h — Testing & bugfixing  ← **current sprint**

- [x] 🧪 Full regression pass — `./scripts/check.sh` (numbers above). The `slow` full-corpus test was not run.
- [x] 🔁 Concurrency test: parallel `/analyze/jobs` requests — job creation, deduplication and the container's lazy construction (`tests/api/test_analysis_jobs_concurrency.py`, `tests/test_container.py`), plus the fan-out itself (`tests/services/test_concurrency.py`, `tests/services/fact_checker/test_fact_checker_concurrency.py`). `VectorRepository` now serialises every call behind its own lock, so the shared local Qdrant client is no longer reached from several threads at once. **Still not load-tested** against a real multi-job run.
- [x] 📉 Load-test `/analyze` sync endpoint (timeouts, long scrapes) — `scripts/load_test_analyze.py` against a live stack (backend on host + `inference/` + SearXNG + Ollama). Concurrency 4: 4/4 succeeded, p50 156s. Concurrency 6: 1/6 exceeded a 240s client timeout, p50 rose to 196s. The per-resource semaphores (`LLM_MAX_CONCURRENCY=2` etc.) held under load with zero `llm_unreachable` claims; `/analyze` itself has no article-level concurrency ceiling, so callers should prefer `/analyze/jobs` for anything beyond a handful of concurrent analyses. Full numbers: `docs/decisions/concurrency.md`.
- [x] 🧰 Harden error handling around `LLMClient` timeouts/failures — `LLM_TIMEOUT` halved to 30s (the new default model is 3B, not 8B), `complete_json` backs off exponentially between retries (`LLM_RETRY_BACKOFF_SECONDS`), and a provider that was never reached at all now raises `LLMUnavailableError` instead of silently returning `None` like a malformed response would. That flag propagates as `FactCheck.llm_unreachable` / API `llmUnreachable`, distinct from a genuine `UNVERIFIED` (cache `SCHEMA_VERSION` bumped to 8 for the new field).
- [x] 📝 Document pipeline architecture (diagram + README updates) — two Mermaid diagrams added to `docs/arquitectura-tecnica.md`: the service/container topology (§2.1) and the seven fact-checking stages including the new `llm_unreachable` branch (§2.4.8).

### Also this sprint (not on the original plan)

- [x] 🦙 Swapped the default LLM from `llama3.1` (8B, ~4.9GB) to `llama3.2:3b` (~2GB) — a resource swap, not a benchmarked upgrade; Phase 4 still owns measuring verification quality. Settings-only change (`LLM_MODEL`), plus `.env`/`.env-example`/README/dev.sh updated and the model pulled and smoke-tested live against Ollama.

### Found by the Sep 21 audit (not on the original plan)

Fixed:
- [x] A re-analysed URL was rejected as a duplicate of itself (and its earlier copy counted as evidence for its own claims) — `docs/decisions/incidents.md`
- [x] Neo4j password committed in `docker-compose.yml` — moved to `backend/.env`. **The old value is still in git history and must be rotated by hand.**
- [x] Job history was lost on restart or failure — every job event is now journalled to disk as it happens, and `/live` shows runs in progress

Also fixed (Sep 21, second pass — `docs/decisions/concurrency.md`, `docs/decisions/retrieval.md`):
- [x] 🐢 **The main bottleneck: claims were verified one at a time.** All three fixes are in, in the order they were worth making: the embedding calls are batched (`encode_many`, which already existed and nothing used), a claim's queries and page fetches run in parallel, and claims run in parallel. Ceilings per external service live in `src/services/concurrency.py` so the fan-out cannot multiply into a stampede. **Not benchmarked:** the tests assert that work overlaps, not how much faster a real run is. The journal's timestamps still make that measurement possible and it has not been taken.
- [x] 🧷 Local Qdrant client used from several threads with no locking — `VectorRepository` holds an `RLock` for the whole of every call. Moving to a Qdrant server is now a scaling decision rather than a correctness one.
- [x] 🎯 **Retrieval asked what a claim was about, never what it said.** A claim mentioning ACME was returned FALSE at 83% citing three pages on the Greek etymology of the word. Now: three queries per claim (anchor / proposition / refutation) fused by reciprocal rank; a lexical term-coverage factor in ranking beside the embedding one; and a per-run **pertinence gate** that cuts a source before the LLM sees it, so that claim comes back `UNVERIFIED` instead. **Unmeasured:** the threshold default is reasoned, not fitted — there is still no labelled set.

Open — best done in this sprint or the next, and **before Phase 4**, because benchmarking runs many claims through the verifier:
- [ ] ⚖️ The article verdict is "worst claim wins", so a single `UNVERIFIED` (the common outcome with a small local model) outweighs any number of `TRUE`; `overall_confidence` averages confidences of different verdicts. Separate "how much could be checked" from "what was found".
- [ ] 🗑️ `JobStore` keeps every job in memory forever (now safe to evict, since the journal has them)
- [ ] ⏳ The analysis cache never expires, and it also caches rejections; fact-check verdicts depend on today's web
- [ ] 🔗 URLs are compared as plain strings, so `?utm_source=` variants and trailing slashes count as different articles
- [ ] 🕸️ Neo4j is a hard start-up dependency of the backend container although nothing uses it

---

## 🧭 Phase 2 — New Strategies & Core Improvements (Sep 29 – Oct 26) · 140h

### Sprint 3 (Sep 29–Oct 12) · 70h — Scraping strategies

- [ ] ➕ **Wire an ingestion path** (not in the original plan) — until something calls `Scraper`/`DiscoveryService`, nothing in this sprint changes what enters the system. `Scraper.discover()` passes a dict where a `list[str]` is declared and `Scraper.extract()` ignores its `topics` argument.
- [ ] 🎭 Implement `PlaywrightStrategy` for JS-rendered sources — the two Playwright files are placeholders; `PlaywrightExtractionStrategy` builds a `News` where an `ExtractionResult` is expected, so wiring it in raises `AttributeError`
- [ ] 🍜 Implement `BeautifulSoupStrategy` — `extract()` returns `None`
- [ ] 🧭 Route sources by `requires_javascript` — the flag exists and is never read
- [ ] ➕ Add new source YAMLs (12 today)
- [ ] 🧪 Unit tests for each new scraping strategy (the existing scraper tests cover discovery, extraction and the URL guard only)

### Sprint 4 (Oct 13–26) · 70h — Enrichment & fact-checking improvements

- [ ] 🟡 🧠 Improve claim selection heuristics — the anchor-claim redesign (rank by how load-bearing a claim is, drop near-duplicates, keep 2–4) is done. Left: tuning the dedupe and confidence thresholds against real data.
- [ ] 🟡 🌐 Alternative evidence retrieval strategies — SearXNG queries are now a planned set (anchor / proposition / refutation) fused by reciprocal rank, and off-target sources are cut by the pertinence gate (`docs/decisions/retrieval.md`). No second *source* of evidence exists yet, and nothing asks the model whether a source is on-point about the right subject.
- [ ] ⚖️ Tune `RANKING_*`, `CONFIDENCE_*` and `EVIDENCE_MIN_PERTINENCE` with real data — no labelled evaluation set exists in the repo. `RANKING_LEXICAL_WEIGHT` was carved out of the other three by reasoning, not measurement.
- [ ] 🟡 🏷️ Improve topic classifier accuracy — keyword coverage was widened from misclassified real articles. There is no labelled set to measure accuracy on.
- [ ] 🧪 Regression tests for new ranking/confidence behavior

---

## 🗄️ Phase 3 — Neo4j Integration & Infrastructure Deployment (Oct 27 – Nov 9) · 70h

### Sprint 5 (Oct 27–Nov 9) · 70h

**Neo4j (configured, unused):**

- [ ] 🔗 Design graph schema (articles, entities, claims, sources relations)
- [ ] 🧩 Wire `neo4j_client.py` into the real pipeline (write path) — the client is dead code today
- [ ] 🔍 Add at least one read use-case (e.g., related-articles graph query)
- [ ] 🧪 Fix/replace `tests/database/test_connection.py` — it skips (does not fail) when Neo4j is down

**Infrastructure Deployment:**

- [ ] ☁️ Choose hosting target (VPS / cloud provider) for backend + Neo4j + SearXNG
- [ ] 🟡 🐳 Production-ready `docker-compose` — healthchecks, named volumes and a shutdown grace period exist; the Neo4j password now comes from env. Left: the rest of the secrets, a hardened SearXNG, and the fact that the backend image has never been run end to end.
- [ ] 🔐 Copy & configure `searxng/settings.yml` (secret) for prod — `settings.yml.example` exists; the real file is gitignored
- [ ] 🟡 🧯 Logging/monitoring — INFO-level phase durations are logged, and every run's events are now journalled with timestamps. No metrics or alerting.
- [ ] 🚦 CI pipeline — none exists (no `.github/`). No linter or formatter is configured either; decide on ruff/black/mypy first.

---

## 🤖 Phase 4 — AI Model Testing (THE BIG ROCK) (Nov 10 – Dec 7) · 140h

> `LLMClient` is a swappable OpenAI-SDK wrapper (Ollama local by default; Groq/OpenRouter/Together via settings only). That part is true. **None of the benchmark machinery exists yet**: no harness, no labelled ground-truth set, no rubric, and no token or cost accounting.
>
> **Prerequisite work, not on the plan:** a labelled set of claims with human verdicts (needed by 3 of the 6 Sprint 7 items), and a harness that runs a model over it and records latency and cost. Per-claim LLM latency can already be read from the journal (`verifying_claim` → `claim_checked`).

### Sprint 6 (Nov 10–23) · 70h — ✍️ Writing / redaction models

- [ ] 🦙 Benchmark local Ollama models (baseline, free)
- [ ] ⚡ Benchmark Groq-hosted models (speed test)
- [ ] 🌐 Benchmark OpenRouter models (variety test)
- [ ] 🤝 Benchmark Together AI models
- [ ] 📏 Compare on the corrector's 5 LLM-based metrics: grammar, factConsistency, seo, hallucinationIndex, style (readability and coverageVerification are deterministic and do not depend on the model)
- [ ] 📊 Build a scoring rubric + comparison table per model
- [ ] 💰 Log cost/latency/quality trade-offs per provider

### Sprint 7 (Nov 24–Dec 7) · 70h — 🕵️ Verification models

- [ ] 🔍 Benchmark models for `LLMVerifier` (claim verification accuracy)
- [ ] 🚫 Stress-test hallucination guardrails — the no-evidence → `UNVERIFIED` rule and the "definitive verdict citing nothing → `UNVERIFIED`" rule are unit-tested with fakes, never against a real model that is trying to bluff
- [ ] 🎯 Compare verdict agreement vs. human-labeled ground truth set
- [ ] 🧮 Re-tune `ConfidenceScorer` weights per best-performing model
- [ ] 🏁 Select final default model(s) + document rationale
- [ ] 📄 Draft results section for the paper (model comparison data)

---

## 💻 Phase 5 — Frontend v2: User-Facing App (Dec 8 – Dec 21) · 60h

Nothing of this phase exists: no accounts, profiles, feed, bookmarks or recommendations. What the frontend has today is an internal tool — five pages (`/` analyzer, `/live`, `/claim`, `/enrich`, `/corrector`).

### Sprint 8 (Dec 8–21) · 60h

- [ ] 🔐 User authentication (sign up / login / sessions)
- [ ] 👤 User profiles (topic preferences, settings)
- [ ] 📰 Topic-based news feed views — needs the missing ingestion path from Sprint 3
- [ ] 💾 Save/bookmark articles per user
- [ ] 🎯 Basic recommendation system v1 (content-based on saved/read topics)
- [ ] 🧪 E2E test: signup → browse → save → get recommendations — the frontend has no test runner; the typecheck is the only gate
- [ ] 🟡 🎨 Extend the existing hand-written CSS design system (no new UI libs) — the system exists and is what `/live` was built on

---

## 📄 Phase 6 — Paper & Final QA (Dec 22 – Dec 31) · 50h

### Sprint 9 (Dec 22–31, ~10 days) · 50h

- [ ] ✍️ Consolidate methodology section (pipeline architecture) — `docs/arquitectura-tecnica.md` is the starting point and was corrected on Sep 21 to match the code
- [ ] 📊 Insert AI model benchmarking results (Phase 4 data)
- [ ] 🧪 Final full regression test suite (backend + frontend)
- [ ] 🐛 Final bugfix pass across all phases
- [ ] 🚀 Final deployment verification (prod smoke test)
- [ ] 📬 Submit / deliver paper draft
- [ ] 🎉 Project wrap-up & retrospective notes

---

## 🧪 Testing Checklist (Cross-Phase)

- [x] ✅ Unit tests per module — `processors/`, `services/scraper/`, `services/fact_checker/`, `services/`, `database/`, `repositories/`, `api/`, `config/`. None for the Playwright/BeautifulSoup strategies, because they do not work.
- [ ] 🟡 🔗 Integration tests: full pipeline run — `tests/test_real_pipeline_integration.py` exists but is skipped unless `inference/` is running
- [ ] 🟡 🧵 Concurrency tests — see Sprint 2; Qdrant client use from several threads is untested
- [ ] 🤖 Model comparison tests (writing + verification, Phase 4)
- [ ] 🗄️ Neo4j read/write tests
- [ ] ☁️ Infra smoke tests (staging + production) — the backend container has never been started end to end
- [ ] 💻 Frontend E2E tests (job polling, corrector, new user app)
- [ ] 📉 Load/performance testing before final deployment

---

## Delivered outside the plan

Real work that is in the repo but not in any sprint above, so the plan does not under-report what exists:

- **`inference/` service** — GLiNER, sentiment and embeddings moved out of the API process into their own service (`docs/decisions/inference.md`)
- **Three-layer storage lake** (raw → processed → exploitation) with lineage and an append-only manifest (`docs/decisions/storage.md`)
- **Per-run thresholds** — every tunable can be overridden for one run, and the analysis cache keys on them (`docs/decisions/thresholds.md`)
- **Job journal + `/live` screen** — a second screen that follows any run: the searches sent, every source found and the engines behind it, the rating each got, and the verdict; every step is saved to disk as it happens
- **Bulk analysis jobs**, `POST /verify-claim` (single claim) and `POST /enrich` (NLP only), with matching frontend pages
- **SSRF guard** on every server-side fetch, English and Spanish lexicons, and a set of invariants enforced as tests (`backend/tests/test_invariants.py`)

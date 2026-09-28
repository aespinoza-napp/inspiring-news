# Roadmap

The plan, and what is true of it **today**. Every checkbox below was checked
against the code, not against the plan. `[x]` means done *and* working as
described; anything less is `[ ]` with a note saying exactly how far it got.

- **As of:** 2026-09-28 — last day of Phase 1, Sprint 2 (Sep 15–28).
- **Hours** are the planned budget. There is no time log in the repo, so
  nothing here claims hours actually spent.
- **Rebalanced on Sep 28**, still 900h: the custom validation set turned
  out to be a 40h task on its own, not something the hours Sprint 3 freed
  could absorb. It gets its own 40h in Sprint 3 (70h → 110h), paid for by
  Sprint 6 (70h → 50h) and Sprint 8 (60h → 40h). Phase 2 is now 180h,
  Phase 4 120h, Phase 5 40h.
- **Verification used for "done"** is `./scripts/check.sh`: on Sep 28, 737
  backend tests passed (11 skipped, 2 slow ones deselected), 9 inference
  tests against the real models, the frontend typechecks, and the fact
  labeller's 19 tests pass. The 11 skips
  are mostly the model tests: `inference/` ran in Docker, and its port is
  not published to the host. The last pass **with** `inference/` reachable
  was Sep 25 (708 passed, 1 skipped: Neo4j) - without it the model tests
  skip rather than run, which is how a failing one went unseen. The `slow`
  corpus test was not part of either pass. There is no frontend test
  runner, no CI, and no linter.

Legend: `[x]` done · `[ ]` not done · 🟡 partly done (what is left is stated) ·
⚠️ the original plan had this ticked and it is not fully true.

---

## Phase 0 — Foundations (Jun 1 – Jul 31)

### Sprint 0.1 — Setup & Scraping Core (Jun 1–14) · 80h

- [x] 🗂️ Monorepo structure (`backend/`, `frontend/`, `docker/`) — since then also `inference/`, `docs/`, `scripts/`
- [x] ⚙️ FastAPI skeleton + `pydantic-settings` config
- [x] 🔎 `ExtractorService` (Trafilatura) — used by `/analyze` and by the evidence scraper
- [x] `DiscoveryService` (RSS strategy) — called by ingestion since Phase 2; exercised against the 12 live feeds on 2026-09-23.
- [x] 📄 Declarative YAML news sources (`SourceRepository`) — 36 sources since Sep 28 (20 English, 16 Spanish; 34 ingested, 2 rated only), up from 12. `NewsSource.requires_javascript` routes a source's articles to the browser first (Phase 2).
- [x] 🐳 `docker-compose.yml` — Neo4j, SearXNG, `inference`, backend. All four come up healthy and serve requests (Sep 23, 25, 28). ⚠️ A full analysis inside the `backend` container is still unverified; Neo4j is unused.

### Sprint 0.2 — Enrichment Pipeline (Jun 15–28) · 80h

- [x] 🏷️ Keyword (yake) / entity (GLiNER) extraction
- [x] 📌 Claims extraction module (English and Spanish lexicons)
- [x] 🗃️ Topic classifier + sentiment + quality scoring — `TopicPrediction.probability` carries no signal (near-uniform softmax); use `confidence`
- [x] 🔢 Embedding service — now `BAAI/bge-m3` in the separate `inference/` service, reached over HTTP
- [x] 🧩 `NewsEnrichmentPipeline` → `EnrichedArticle` model

### Sprint 0.3 — Fact-Checking Pipeline v1 (Jun 29–Jul 12) · 80h

- [x] ✅ Validation pipeline (topic / positive-impact / duplicate validators) — the constructiveness and inspirational hard-fails are deliberately off; the objectivity and negative-sentiment hard-fail is a single setting (`POSITIVE_IMPACT_HARD_FAIL_ENABLED`, overridable per run) and is **off by default** in the current `settings.py`
- [x] 🎯 `ClaimSelector` — now ranks by how load-bearing a claim is and keeps an "anchor band" (`anchor_claims_min`/`max`), rather than the original confidence ranking
- [x] 🌐 Evidence retrieval (SearXNG web + Qdrant internal corpus) — since rebuilt: three queries per claim (anchor / proposition / refutation) fused by reciprocal rank, run concurrently, one source per domain (Sep 21); a repeated query is sent to SearXNG once (Sep 28).
- [x] 📈 `EvidenceRanker` (similarity + recency + reliability) — reliability is a real rating only for the 36 configured domains; every other domain gets the default 0.5 and is flagged `reliability_known: false`
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
- [x] 🗃️ Audit `AnalysisCache` correctness (`forceRefresh` behavior) — the key hashes the *effective* thresholds; a cache write that fails no longer fails the job; schema version 9 today
- [x] 🧪 Expand the fact-checker fakes — `tests/services/fact_checker/fakes.py`, with `tests/test_fake_contracts.py` pinning every fake's signature to the real class
- [x] 📋 Fix pre-existing failing tests — the suite is green. ⚠️ Until 2026-09-25 it was green only because 10 tests skip without `inference/`: with it running, `test_topic_classifier` failed. The classifier had switched `topic` to the display name ("Technology") and the test still compared the TOPICS keys ("technology"). Fixed; not a threshold problem.

### Sprint 2 (Sep 15–28) · 70h — Testing & bugfixing  ← **current sprint, closes today**

- [x] 🧪 Full regression pass — `./scripts/check.sh` (numbers above). The `slow` full-corpus test was not run.
- [x] 🔁 Concurrency test: parallel `/analyze/jobs` requests — job creation, deduplication and the container's lazy construction (`tests/api/test_analysis_jobs_concurrency.py`, `tests/test_container.py`), plus the fan-out itself (`tests/services/test_concurrency.py`, `tests/services/fact_checker/test_fact_checker_concurrency.py`). `VectorRepository` now serialises every call behind its own lock, so the shared local Qdrant client is no longer reached from several threads at once. **Still not load-tested** against a real multi-job run.
- [x] 📉 Load-test `/analyze` sync endpoint (timeouts, long scrapes) — `scripts/load_test_analyze.py` against a live stack (backend on host + `inference/` + SearXNG + Ollama). Concurrency 4: 4/4 succeeded, p50 156s. Concurrency 6: 1/6 exceeded a 240s client timeout, p50 rose to 196s. The per-resource semaphores (`LLM_MAX_CONCURRENCY=2` etc.) held under load with zero `llm_unreachable` claims; `/analyze` itself has no article-level concurrency ceiling, so callers should prefer `/analyze/jobs` for anything beyond a handful of concurrent analyses. Full numbers: `docs/decisions/concurrency.md`.
- [x] 🧰 Harden error handling around `LLMClient` timeouts/failures — `LLM_TIMEOUT` halved to 30s (the new default model is 3B, not 8B), `complete_json` backs off exponentially between retries (`LLM_RETRY_BACKOFF_SECONDS`), and a provider that was never reached at all now raises `LLMUnavailableError` instead of silently returning `None` like a malformed response would. That flag propagates as `FactCheck.llm_unreachable` / API `llmUnreachable`, distinct from a genuine `UNVERIFIED` (cache `SCHEMA_VERSION` bumped to 8 for the new field).
- [x] 📝 Document pipeline architecture (diagram + README updates) — two Mermaid diagrams added to `docs/arquitectura-tecnica.md`: the service/container topology (§2.1) and the seven fact-checking stages including the new `llm_unreachable` branch (§2.4.8).

### Also this sprint (not on the original plan)

- [x] 🦙 Swapped the default LLM from `llama3.1` (8B, ~4.9GB) to `llama3.2:3b` (~2GB) — a resource swap, not a benchmarked upgrade; Phase 4 still owns measuring verification quality. Settings-only change (`LLM_MODEL`), plus `.env`/`.env-example`/README/dev.sh updated and the model pulled and smoke-tested live against Ollama.

### Sep 28: fewer wasted calls, more engines (not on the original plan)

Branch `feature/more-sources-and-weights`. Everything measured before it
was changed; the numbers are in `docs/decisions/retrieval.md` and
`docs/decisions/inference.md`.

- [x] 🤖 **No LLM call for a claim without evidence.** Below the evidence floor the verdict was already forced to `UNVERIFIED`, so the call - the slowest step - was spent on an answer thrown away: 23 of 24 claims on Sep 25. No `verifying_claim` event either, so the UI no longer says "Asking the model" when it is not.
- [x] 🔎 **SearXNG engines.** The allowlist in `settings.yml.example` had never reached the live, gitignored `settings.yml`, which still ran the full default roster - where the DuckDuckGo CAPTCHAs and Wikidata timeouts of Sep 25 came from. Now: Bing, Google, Brave, Yep, Bing News, Wikipedia (which now returns its article, not only an infobox) and four science APIs measured live first: arXiv, Crossref, Semantic Scholar, PubMed, at half weight so web results lead. Timeout 8s → 3s: every remaining engine answered in ≤2.1s.
- [x] 🚦 **Fewer searches at once.** `SEARXNG_MAX_CONCURRENCY` 4 → 2, and `SearxngClient` sends a repeated query once: a concurrent asker waits for the request in flight, and answers with results are kept 10 minutes (empty ones are not - they are usually a rate-limit suspension).
- [x] ⚖️ **Weight groups must sum to 1.0, or the backend refuses to start.** The committed `.env-example` had ranking weights summing to **1.2** since the lexical weight was added, so every setup copied from it inflated evidence scores. The suite had not noticed: the weights are frozen into their classes at import, and the tests never reset those copies (see Sprint 4's regression-test item).
- [x] 🏷️ **Labelling tool for the custom validation set.** `labeller/`: one Python file and one HTML page, standard library only - `python labeller/app.py`, nothing to install, no backend or Docker needed. Each fact is its own file, `backend/data/evaluation/manual/factNNN.json`, so every hand-verified fact is visible in the repo; `python labeller/app.py join` merges them into `custom_en_es.jsonl` when the set is done. Rows are x-fact's exact format (same keys, same order, `split: test`) plus `topic`, `claimType`, `sourceTier`, `onlyOwnSource`, `evidenceDate` and a note. The four tie-break rules are fixed before labelling, and the checkable ones are enforced on save (own source only → `UNVERIFIED`; evidence newer than the article refused). A verdict × topic-group table steers toward 150 facts (25 cells of 6). The Review tab labels a hash-chosen 20% again, blind, and reports agreement and Cohen's kappa on the first label. `./scripts/check.sh labeller` runs its tests. Written up in `docs/final_document/sections/custom_dataset.tex`. No facts yet: labelling is Sprint 3's 40h.
- [x] 🧮 **Sentiment int8 via ONNX: measured and rejected.** On 336 real en/es texts the fast int8 variants agreed with today's model on only 86–92% of labels, flipping mostly neutral → positive (an admission gate); the accurate variant was 2.5x slower. Kept fp32.

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

## 🧭 Phase 2 — New Strategies & Core Improvements (Sep 29 – Oct 26) · 180h

### Sprint 3 (Sep 29–Oct 12) · 110h — Scraping strategies (70h) + custom validation set (40h)

- [x] ➕ **Wire an ingestion path** (not in the original plan) — `POST /ingest` + a panel on `/scraper`: RSS, then trafilatura's feed discovery; article-shape filter that works in Spanish; English-only topic pre-filter; skips what the lake already has; queues full analyses (purpose `ingestion`). Manual only. `Scraper` drift fixed. At the time 9 of 12 sources produced links and 4 feed URLs returned 404; since Sep 28 RTVE's is replaced, and National Geographic, Reuters and SINC have no feed to replace it with (topic pages rescue two of them).
- [x] 🎭 Implement `PlaywrightStrategy` for JS-rendered sources — the last step of the cascade: renders, then reads the result with the same trafilatura/BeautifulSoup parsers. URL guard on every request and redirect hop, `BROWSER_MAX_CONCURRENCY`, never for evidence, optional `browser` extra (installed in Docker). `playwright_discover.py` is still a placeholder.
- [x] 🍜 Implement `BeautifulSoupStrategy` — step two of a cheapest-first cascade, parsing the HTML trafilatura already fetched (no second request); JSON-LD, meta tags, per-source `metadata.selectors`, then the densest paragraph block. It also fills title/author/date trafilatura missed. `docs/decisions/scraping.md`
- [x] 🧭 Route sources by `requires_javascript` — `true` sends articles to the browser first; posted URLs are matched to their configured source by domain so the flag (and `selectors`) apply to `/analyze` too. Every configured source is `false`; `/scraper` flags domains only the browser can read.
- [x] ➕ Add new source YAMLs — 12 → 36 (Sep 28). 24 added, each only after its feed produced links and 2/2 sample articles extracted through the real cascade; RTVE's dead feed replaced. Newtral and Maldita are `enabled: false`: rated for evidence, not ingested (a fact-check quotes the claim it debunks). One source per domain, enforced by a test. `backend/data/sources/README.md`
- [x] 🧪 Unit tests for each new scraping strategy — BeautifulSoup (8), the Playwright step (10), trafilatura (14), the cascade's stop/escalate rules (21 in `test_extractor.py`), discovery (18), and the topic-page strategy (11) and source probe (14) added on Sep 25.
- [x] 🩺 **Topic-page discovery + source probe** (not in the original plan) — discovery's third step reads a source's topic section pages (`/science/`, `/ciencia/`...) when it has no feed; `POST /scraper/probe` and a "Source health" panel on `/scraper` check every source (feed, topic pages, a sample of real extractions) and SearXNG. First run: 6 up, 3 degraded (National Geographic, RTVE, SINC: dead feeds, **rescued by topic pages**, 6/6 extracted each), 3 down (EFE 403, Reuters 401, El País 403 on articles). Topic pages added 1,272 links to the feeds' 395. `docs/decisions/scraping.md`
- [ ] 🏷️ **Hand-label the custom validation set · 40h** (not in the original plan; own budget since the Sep 28 rebalance) — the paper commits to it (`docs/final_document/sections/evaluation_dataset.tex`, "Custom Validation Set") and x-fact cannot replace it: x-fact is political statements, not the interpretive claims of positive-news articles. The tool (`labeller/`), schema and guide are done (Sep 28, Sprint 2), so the 40h is labelling: find and label 100–150 facts with their sources, balanced over verdict × topic group, ~13 min each, 34h; the blind 20% review a week later, 4h; settle the disagreements and report agreement in `custom_dataset.tex`, 2h. Gates Sprint 4's tuning and 3 of Sprint 7's 6 items.

### Sprint 4 (Oct 13–26) · 70h — Enrichment & fact-checking improvements

- [ ] 🟡 🧠 Improve claim selection heuristics — the anchor-claim redesign (rank by how load-bearing a claim is, drop near-duplicates, keep 2–4) is done. Left: tuning the dedupe and confidence thresholds against real data.
- [ ] 🟡 🌐 Alternative evidence retrieval strategies — SearXNG queries are now a planned set (anchor / proposition / refutation) fused by reciprocal rank, and off-target sources are cut by the pertinence gate (`docs/decisions/retrieval.md`). Sep 28: four science APIs (arXiv, Crossref, Semantic Scholar, PubMed) and Wikipedia answer through SearXNG beside the web engines, and still answer when those are rate-limited; the internal Qdrant corpus now grows from 34 ingested sources. Left: an engine with an API key (Brave Search API / Google Programmable Search), a "search unavailable" state apart from `UNVERIFIED`, and asking the model whether a source is on-point about the right subject.
- [ ] ⚖️ Tune `RANKING_*`, `CONFIDENCE_*` and `EVIDENCE_MIN_PERTINENCE` with real data — no labelled evaluation set exists in the repo. `RANKING_LEXICAL_WEIGHT` was carved out of the other three by reasoning, not measurement.
- [ ] 🟡 🏷️ Improve topic classifier accuracy — keyword coverage was widened from misclassified real articles. There is no labelled set to measure accuracy on.
- [x] 🧪 Regression tests for new ranking/confidence behavior — ranking (lexical factor, pertinence gate both ways, run-threshold not env) was already covered. Sep 28: confidence golden values and properties (`test_confidence_weights.py`); the frozen class weights are now pinned for the suite (they had been running on the local `.env`); weight groups that do not sum to 1.0 refuse to start - the committed `.env-example` had ranking at 1.2. Still not *measured*: that is the tuning item above.

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
- [ ] 🟡 🐳 Production-ready `docker-compose` — healthchecks, named volumes and a shutdown grace period exist; the Neo4j password now comes from env. Left: the rest of the secrets, a hardened SearXNG, and a full analysis run inside the backend container, which has come up healthy but never been verified end to end.
- [ ] 🟡 🔐 Copy & configure `searxng/settings.yml` (secret) for prod — `settings.yml.example` now carries the measured engine allowlist (Sep 28); the real file is gitignored and **drifts**: the local copy ran the full default roster for weeks. Left: a generated `secret_key` (the local copy still has the placeholder) and a check that the live file matches the example.
- [ ] 🟡 🧯 Logging/monitoring — INFO-level phase durations are logged, and every run's events are now journalled with timestamps. No metrics or alerting.
- [ ] 🚦 CI pipeline — none exists (no `.github/`). No linter or formatter is configured either; decide on ruff/black/mypy first.

---

## 🤖 Phase 4 — AI Model Testing (THE BIG ROCK) (Nov 10 – Dec 7) · 120h

> `LLMClient` is a swappable OpenAI-SDK wrapper (Ollama local by default; Groq/OpenRouter/Together via settings only). That part is true. **None of the benchmark machinery exists yet**: no harness, no labelled ground-truth set, no rubric, and no token or cost accounting.
>
> **Prerequisite work:** a labelled set of claims with human verdicts (needed by 3 of the 6 Sprint 7 items) — the x-fact set is in the repo, and the custom set has its labelling tool and a 40h labelling budget in Sprint 3 — and a harness that runs a model over them and records latency and cost, which is still not on the plan. Per-claim LLM latency can already be read from the journal (`verifying_claim` → `claim_checked`).

### Sprint 6 (Nov 10–23) · 50h — ✍️ Writing / redaction models

Cut from 70h on Sep 28 to fund the custom validation set. Seven items no longer fit in 50h at the depth planned: decide at sprint start what shrinks. Together AI is the likeliest to drop, since it speaks the same wire format as OpenRouter and adds the least that is new.

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

## 💻 Phase 5 — Frontend v2: User-Facing App (Dec 8 – Dec 21) · 40h

Nothing of this phase exists: no accounts, profiles, feed, bookmarks or recommendations. What the frontend has today is an internal tool — seven pages (`/` analyzer, `/live`, `/claim`, `/enrich`, `/corrector`, `/scraper`, `/sources`).

### Sprint 8 (Dec 8–21) · 40h

Cut from 60h on Sep 28 to fund the custom validation set. Authentication, profiles and a topic feed are the core; bookmarks and recommendations v1 are the first to slip if 40h does not stretch.

- [ ] 🔐 User authentication (sign up / login / sessions)
- [ ] 👤 User profiles (topic preferences, settings)
- [ ] 📰 Topic-based news feed views — the ingestion path now exists (manual `POST /ingest`, 34 sources); the lake has to be filled before a feed has anything to show
- [ ] 💾 Save/bookmark articles per user
- [ ] 🎯 Basic recommendation system v1 (content-based on saved/read topics)
- [ ] 🧪 E2E test: signup → browse → save → get recommendations — the frontend has no test runner; the typecheck is the only gate
- [ ] 🟡 🎨 Extend the existing hand-written CSS design system (no new UI libs) — the system exists and is what `/live` was built on

---

## 📄 Phase 6 — Paper & Final QA (Dec 22 – Dec 31) · 50h

### Sprint 9 (Dec 22–31, ~10 days) · 50h

- [ ] ✍️ Consolidate methodology section (pipeline architecture) — `docs/arquitectura-tecnica.md` is the starting point and was brought back in line with the code on Sep 28 (v1.1)
- [ ] 📊 Insert AI model benchmarking results (Phase 4 data)
- [ ] 🧪 Final full regression test suite (backend + frontend)
- [ ] 🐛 Final bugfix pass across all phases
- [ ] 🚀 Final deployment verification (prod smoke test)
- [ ] 📬 Submit / deliver paper draft
- [ ] 🎉 Project wrap-up & retrospective notes

---

## 🧪 Testing Checklist (Cross-Phase)

- [x] ✅ Unit tests per module — `processors/`, `services/scraper/` (every strategy included), `services/fact_checker/`, `services/`, `database/`, `repositories/`, `api/`, `config/`.
- [ ] 🟡 🔗 Integration tests: full pipeline run — `tests/test_real_pipeline_integration.py` exists but is skipped unless `inference/` is running
- [x] 🧵 Concurrency tests — see Sprint 2: parallel jobs, the fan-out's ordering and ceilings, interleaved per-claim events, and (Sep 28) concurrent identical SearXNG queries sent once. Qdrant contention is prevented by `VectorRepository`'s lock rather than tested around.
- [ ] 🤖 Model comparison tests (writing + verification, Phase 4)
- [ ] 🗄️ Neo4j read/write tests
- [ ] ☁️ Infra smoke tests (staging + production) — no environment exists; locally the backend container comes up healthy, but a full analysis inside it is unverified
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
- **`/sources` health check** — for every source YAML, disabled ones included: does discovery find links, and do two sample articles extract with a title, author and date (`POST /sources/check`)
- **Source probe + scraper stats on `/scraper`** — every request counted per domain with why it failed, and a "Source health" panel that also asks SearXNG which engines answered
- **SSRF guard** on every server-side fetch, English and Spanish lexicons, and a set of invariants enforced as tests (`backend/tests/test_invariants.py`)

# Roadmap

The plan, and what is true of it **today**. Every checkbox below was checked
against the code, not against the plan. `[x]` means done *and* working as
described; anything less is `[ ]` with a note saying exactly how far it got.

- **As of:** 2026-09-30 — week 1 of Sprint 4 (development) and of the validation set (evaluation), run side by side.
- **Hours** are the planned budget. There is no time log in the repo, so
  nothing here claims hours actually spent.
- **Rebalanced on Sep 28**, still 900h: the custom validation set turned
  out to be a 40h task on its own, not something the hours Sprint 3 freed
  could absorb. It gets its own 40h in Sprint 3 (70h → 110h), paid for by
  Sprint 6 (70h → 50h) and Sprint 8 (60h → 40h). Phase 2 is now 180h,
  Phase 4 120h, Phase 5 40h.
- **Rescheduled on Sep 29**, still 900h. Two changes, both about the
  calendar rather than the work:
  1. **The validation set gets its own window, Sep 29 – Oct 30,** inside
     Phase 2. Its 40h are ~10 facts a day for three weeks (daily batches,
     see below), then the blind 20% re-label, which the guide requires at
     least a week after the first pass. Phase 2 therefore ends **Nov 2**,
     not Oct 26, and Sprint 4 (whose tuning needs the labels) runs
     Oct 13 – Nov 2. The week is taken from Phase 3, whose Neo4j half was
     done on Sep 29: Phase 3 is now Nov 3–9.
  2. **Testing is its own transversal track, 50h, heavier towards the
     end** (8h Oct, 12h Nov, 10h Dec 1–21, 20h Dec 22–31) - on top of
     Sprint 2's 70h of testing already spent. Funded by moving testing
     items that were already in other phases into it (CI from Phase 3,
     -5h; the guardrail stress test from Sprint 7, -10h; the final
     regression, bugfix pass and prod smoke test from Phase 6, -15h) and
     by **cutting the user-facing app to a reader view (Phase 5, 40h →
     20h)**: accounts, profiles, bookmarks and recommendations are not
     needed to answer the paper's question. That cut is a scope decision;
     revert it here if you disagree, and take the 20h from elsewhere.
  3. **The evaluation gets its own 40h, Oct 13 – Nov 9** (the harness that
     runs the pipeline over the labelled sets and computes the metrics
     had no hours anywhere, and every Phase 4 result depends on it), and
     **the search fix gets its own 10h inside Sprint 4**, before any
     benchmark. Funded by the writing benchmark (Sprint 6, 50h → 20h: the
     local baseline and one hosted provider; OpenRouter and Together AI
     cut) and by Sprint 4 (70h → 60h: topic-classifier accuracy is on no
     research question's path).

- **Rescheduled on Sep 30**, still 900h. The Sep 29 plan kept the hours
  honest but not the calendar: Phase 3 put 65h into one week while the
  20h reader view had two, and the evaluation was spread over three
  places (the validation set inside Phase 2, the harness on its own,
  model testing in Phase 4). Now:
  1. **Every block's dates follow from its hours**, at the ~30–35h a
     week Phases 0 and 1 ran at. Work already done (Sprint 3, the Neo4j
     half of Phase 3) is dated when it was done and takes no future
     calendar.
  2. **Development and evaluation are two tracks that run side by
     side.** Phase 2 is development only (Sprint 4). **Phase 4 is the
     evaluation groundwork**: the validation set (the labelling), the
     harness, and the tuning against the labels, in the order each needs
     the one before. Sprint 4's two tuning items move into it (-10h /
     +10h): they need the labels and the harness, not the development
     work beside them. **The model testing (Sprints 6 and 7) is its own
     phase, Phase 5**, which starts once Phase 4 has given it labels and
     a harness to run on.
  3. **Neo4j 35h → 20h** (done on Sep 29, in far less than planned);
     infrastructure keeps 30h, over three weeks (Oct 20 – Nov 9) instead
     of one. The 15h go to the interface, **Phase 6, 20h → 35h**: one
     full week, Dec 11–17.
  4. **Testing stays its own transversal track, 50h, and ends Dec 24.**
     Its final window (regression, frontend E2E, bugfix, prod smoke test)
     is the week *before* the paper, not the same days.
  5. **The paper gets the last week, Dec 25–31**, on a system that no
     longer changes.
  6. **Phases from 4 on are renumbered.** Model testing was Phase 4 and
     is Phase 5; the interface was Phase 5 and is Phase 6; the paper was
     Phase 6 and is Phase 7. The Sep 28 and Sep 29 entries above keep the
     numbers they were written with.

  | Bucket | Sep 28 | Sep 29 | Sep 30 |
  |---|---:|---:|---:|
  | Phase 0 · Foundations (Jun 1 – Jul 31) | 300 | 300 | 300 |
  | Phase 1 · Pipeline completion (Sep 1–28) | 140 | 140 | 140 |
  | Phase 2 · Development: scraping + fact-checking (Sep 29 – Oct 19) | 140 | 130 | 120 |
  | Phase 3 · Neo4j (done) + infrastructure (Oct 20 – Nov 9) | 70 | 65 | 50 |
  | Phase 4 · Evaluation: labelling, harness, tuning (Sep 29 – Nov 16) | 40 | 80 | 90 |
  | Phase 5 · AI model testing (Nov 10 – Dec 10) | 120 | 80 | 80 |
  | Phase 6 · Interface: reader view (Dec 11–17) | 40 | 20 | 35 |
  | Testing & QA, transversal (Sep 29 – Dec 24) | 0 | 50 | 50 |
  | Phase 7 · Paper (Dec 25–31) | 50 | 35 | 35 |
  | **Total** | **900** | **900** | **900** |

  The Sep 28 and Sep 29 columns are regrouped into today's buckets (the
  validation set's 40h and the harness's 40h counted under Phase 4, the
  model benchmarks under Phase 5), so all three add up the same way.

  Week by week, in hours:

  | Week | Development | Evaluation (Phase 4) | Model testing (Phase 5) | Testing | Total |
  |---|---|---|---|---:|---:|
  | Sep 29 – Oct 5 | Sprint 4 · 17 | labelling 1–50 · 11 | — | 2 | 30 |
  | Oct 6–12 | Sprint 4 · 17 | labelling 51–100 · 11, research questions · 3 | — | 2 | 33 |
  | Oct 13–19 | Sprint 4 · 16 | labelling 101–150 · 12 | — | 2 | 30 |
  | Oct 20–26 | infrastructure · 10 | harness · 12, re-label · 1 | — | 2 | 25 |
  | Oct 27 – Nov 2 | infrastructure · 10 | harness · 12, re-label, kappa, join · 5 | — | 3 | 30 |
  | Nov 3–9 | infrastructure · 10 | harness · 13 | — | 3 | 26 |
  | Nov 10–16 | — | tuning · 10 | Sprint 6 · 10 | 3 | 23 |
  | Nov 17–23 | — | — | Sprint 6 · 10, Sprint 7 · 18 | 3 | 31 |
  | Nov 24–30 | — | — | Sprint 7 · 18 | 3 | 21 |
  | Dec 1–10 | — | — | Sprint 7 · 24 | 10 | 34 |
  | Dec 11–17 | interface · 35 | — | — | — | 35 |
  | Dec 18–24 | — | — | — | final · 20 | 20 |
  | Dec 25–31 | paper · 35 | — | — | — | 35 |

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
- **Sep 29 (Neo4j pulled forward from Phase 3):** 794 backend passed, 10
  skipped (the model tests - `inference/` not running), 9 deselected (2
  `slow`, 7 `neo4j`); `./scripts/check.sh graph` 7/7 against a real Neo4j;
  frontend typechecks. Inference tests not re-run.
- **Sep 29, later, with `inference/` reachable** (its container run with
  port 8001 on localhost): **819 passed, 0 skipped**, 9 deselected - the
  first pass with the model tests running since Sep 25. Labeller 26/26.

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
- [x] 🐳 `docker-compose.yml` — Neo4j, SearXNG, `inference`, backend. All four come up healthy and serve requests (Sep 23, 25, 28). ⚠️ A full analysis inside the `backend` container is still unverified. Neo4j is in use since Sep 29, with its own named volume.

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
- [x] 🤖 `LLMVerifier` + `ConfidenceScorer` (hard UNVERIFIED fallback) — works, but its accuracy has never been measured against labelled data (that is Phase 5)

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

- [x] 🦙 Swapped the default LLM from `llama3.1` (8B, ~4.9GB) to `llama3.2:3b` (~2GB) — a resource swap, not a benchmarked upgrade; Phase 5 still owns measuring verification quality. Settings-only change (`LLM_MODEL`), plus `.env`/`.env-example`/README/dev.sh updated and the model pulled and smoke-tested live against Ollama.

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

Open — best done in this sprint or the next, and **before Phase 5**, because benchmarking runs many claims through the verifier:
- [ ] ⚖️ The article verdict is "worst claim wins", so a single `UNVERIFIED` (the common outcome with a small local model) outweighs any number of `TRUE`; `overall_confidence` averages confidences of different verdicts. Separate "how much could be checked" from "what was found".
- [ ] 🗑️ `JobStore` keeps every job in memory forever (now safe to evict, since the journal has them)
- [ ] ⏳ The analysis cache never expires, and it also caches rejections; fact-check verdicts depend on today's web
- [ ] 🔗 URLs are compared as plain strings, so `?utm_source=` variants and trailing slashes count as different articles
- [ ] 🕸️ Neo4j is a hard start-up dependency of the backend container (`depends_on: service_healthy`), although since Sep 29 the graph write is fail-soft and the backend runs without it

---

## 🧭 Phase 2 — Development: Scraping Strategies & Fact-Checking Improvements (Sep 29 – Oct 19) · 120h

Development only since Sep 30: the validation set and every other piece
of evaluation moved to Phase 4, which runs beside this. Sprint 3 was
built in September; Sprint 4 is what is left, at ~17h a week beside the
labelling.

### Sprint 3 (built in September) · 70h — Scraping strategies

Every item below is done.

- [x] ➕ **Wire an ingestion path** (not in the original plan) — `POST /ingest` + a panel on `/scraper`: RSS, then trafilatura's feed discovery; article-shape filter that works in Spanish; English-only topic pre-filter; skips what the lake already has; queues full analyses (purpose `ingestion`). Manual only. `Scraper` drift fixed. At the time 9 of 12 sources produced links and 4 feed URLs returned 404; since Sep 28 RTVE's is replaced, and National Geographic, Reuters and SINC have no feed to replace it with (topic pages rescue two of them).
- [x] 🎭 Implement `PlaywrightStrategy` for JS-rendered sources — the last step of the cascade: renders, then reads the result with the same trafilatura/BeautifulSoup parsers. URL guard on every request and redirect hop, `BROWSER_MAX_CONCURRENCY`, never for evidence, optional `browser` extra (installed in Docker). `playwright_discover.py` is still a placeholder.
- [x] 🍜 Implement `BeautifulSoupStrategy` — step two of a cheapest-first cascade, parsing the HTML trafilatura already fetched (no second request); JSON-LD, meta tags, per-source `metadata.selectors`, then the densest paragraph block. It also fills title/author/date trafilatura missed. `docs/decisions/scraping.md`
- [x] 🧭 Route sources by `requires_javascript` — `true` sends articles to the browser first; posted URLs are matched to their configured source by domain so the flag (and `selectors`) apply to `/analyze` too. Every configured source is `false`; `/scraper` flags domains only the browser can read.
- [x] ➕ Add new source YAMLs — 12 → 36 (Sep 28). 24 added, each only after its feed produced links and 2/2 sample articles extracted through the real cascade; RTVE's dead feed replaced. Newtral and Maldita are `enabled: false`: rated for evidence, not ingested (a fact-check quotes the claim it debunks). One source per domain, enforced by a test. `backend/data/sources/README.md`
- [x] 🧪 Unit tests for each new scraping strategy — BeautifulSoup (8), the Playwright step (10), trafilatura (14), the cascade's stop/escalate rules (21 in `test_extractor.py`), discovery (18), and the topic-page strategy (11) and source probe (14) added on Sep 25.
- [x] 🩺 **Topic-page discovery + source probe** (not in the original plan) — discovery's third step reads a source's topic section pages (`/science/`, `/ciencia/`...) when it has no feed; `POST /scraper/probe` and a "Source health" panel on `/scraper` check every source (feed, topic pages, a sample of real extractions) and SearXNG. First run: 6 up, 3 degraded (National Geographic, RTVE, SINC: dead feeds, **rescued by topic pages**, 6/6 extracted each), 3 down (EFE 403, Reuters 401, El País 403 on articles). Topic pages added 1,272 links to the feeds' 395. `docs/decisions/scraping.md`
- [x] 🩺 **Probe re-run on all 34 enabled sources (Sep 29)** — **29 up, 4 degraded, 1 down: 33 of 34 return articles**, 156 of 165 sampled articles extracted (95%); feeds 1,314 links, topic pages +3,604 more. Only Reuters is out (401 on everything). EFE, down on Sep 25 (403), now answers: no feed, but its topic pages give 85 links and 5/5 extract. National Geographic and SINC as before: dead feeds, rescued by topic pages (5/5 each). El País reads 2 of 5: the other 3 answer 403 and the host has the `playwright` package but not Chromium (`uv run playwright install chromium`; the Docker image has it). Positive News' two failures were section pages taken for articles, not the site. SearXNG answered both test queries (74 and 80 results, ~1.2s) from Google, Brave, Bing, Wikipedia, arXiv, Crossref and PubMed; Semantic Scholar (parsing error) and Yep (suspended) did not. One query per language is not a benchmark's load - the Sep 25 failure (68 of 69 empty) happened under load - so Sprint 4's search fix stays.

### Sprint 4 (Sep 29 – Oct 19) · 50h — Enrichment & fact-checking improvements  ← **current sprint**

70h → 60h on Sep 29 (evaluation harness), 60h → 50h on Sep 30: its two
tuning items moved to Phase 4, where the labels and the harness they
need are. What is left is development, and none of it waits on the
labels - so it runs first, and the search is fixed before any benchmark.

- [x] 🔎 **Fix the search before any benchmark · 10h** — an engine with an API key (Brave Search API or Google Programmable Search), which is not rate-limited per IP like the scraped engines, and a **"search unavailable" state** apart from `UNVERIFIED`, as `llm_unreachable` already is for the LLM. Without both, a benchmark measures SearXNG's uptime: on Sep 25, 68 of 69 queries came back empty and every affected claim looked like an honest `UNVERIFIED`. **Sep 30: the state is done** — `searchUnavailable` on every claim (cache v10, graph), set when every query of a claim failed; the trace stops at `evidence_retrieval` and says the web was never asked (`docs/decisions/retrieval.md`). The analyzer's stage timeline shows that note, so the UI already tells the two apart; there is no dedicated badge, as there is none for `llmUnreachable`. **The API-keyed engine is out of scope** since Sep 30 (no paid APIs or credentials); a keyless DuckDuckGo fallback is proposed as future work instead (`docs/final_document/sections/future_work.tex`).

- ↪️ Improve claim selection heuristics — the structural half is done; tuning its thresholds moved to Phase 4 (Nov 10–16), Sep 30.
- [x] 🌐 Alternative evidence retrieval strategies — SearXNG queries are now a planned set (anchor / proposition / refutation) fused by reciprocal rank, and off-target sources are cut by the pertinence gate (`docs/decisions/retrieval.md`). Sep 28: four science APIs (arXiv, Crossref, Semantic Scholar, PubMed) and Wikipedia answer through SearXNG beside the web engines, and still answer when those are rate-limited; the internal Qdrant corpus now grows from 34 ingested sources. Sep 30: a failed search is reported as `searchUnavailable` (item above), and **the model's own on-point judgement is enforced**: it already marks each source `supports` / `contradicts` / `unrelated`, and a citation of a source it called unrelated no longer counts - a definitive verdict resting only on such sources is `UNVERIFIED`, with a note saying why (cache v11). No extra LLM call. Out of scope: an API-keyed engine; the keyless DuckDuckGo fallback is future work (`future_work.tex`).
- ↪️ Tune `RANKING_*`, `CONFIDENCE_*` and `EVIDENCE_MIN_PERTINENCE` with real data — moved to Phase 4 (Nov 10–16), Sep 30.
- [ ] 🟡 🏷️ Improve topic classifier accuracy — **de-scoped on Sep 29 to "only if time"**: on no research question's path (topics steer admission and balance, not verdicts). Keyword coverage was widened from misclassified real articles; there is no labelled set to measure accuracy on. The labelling batch's wrong topic guesses are a free sample of its errors.
- [x] 🧪 Regression tests for new ranking/confidence behavior — ranking (lexical factor, pertinence gate both ways, run-threshold not env) was already covered. Sep 28: confidence golden values and properties (`test_confidence_weights.py`); the frozen class weights are now pinned for the suite (they had been running on the local `.env`); weight groups that do not sum to 1.0 refuse to start - the committed `.env-example` had ranking at 1.2. Still not *measured*: that is the tuning item above.

---

## 🗄️ Phase 3 — Neo4j Integration & Infrastructure Deployment (Neo4j done Sep 29 · infrastructure Oct 20 – Nov 9) · 50h

### Sprint 5 · 50h — Neo4j 20h (done) + infrastructure 30h

Neo4j 35h → 20h on Sep 30: it was done on Sep 29, a month early and in
far less than planned. Infrastructure keeps its 30h, now over three
weeks at ~10h a week beside the harness, instead of squeezed with Neo4j
into one. CI moved to the testing track on Sep 29 (-5h), where it is
needed from October.

**Neo4j** — done early, Sep 29 (`docs/decisions/graph.md`):

- [x] 🔗 Design graph schema — `Article`, `Entity` (+ type label: `:Person`, `:Country`...), `Topic`, `Claim`, `Verdict`, `Evidence`, `Source`; declared once in `src/services/graph/schema.py`. Every relationship carries `method` (`pipeline` / `manual`), so a hand label and the model's verdict on one claim sit side by side.
- [x] 🧩 Wire `neo4j_client.py` into the real pipeline (write path) — `AnalysisService._store_graph`, after the lake, one transaction per article, fail-soft (`graph_failed`). Backfill with `POST /graph/sync`: configured sources, the labeller's facts, the lake's verified runs. Hand labels reach the graph only through the sync.
- [x] 🔍 Add at least one read use-case — `GET /graph/related` (shared claim / evidence / entity / topic, each weight shown), plus the schema with live counts and a read-only Cypher console; all on the frontend's new `/graph` page.
- [x] 🧪 Fix/replace `tests/database/test_connection.py` — replaced by `tests/database/test_neo4j_live.py` (`neo4j` marker, `./scripts/check.sh graph`), which **fails** when Neo4j is down; writer/reader/sync/routes are unit-tested against a recording fake in the default run.
- [ ] 🟡 Measure it at scale — verified on 8 articles (2 analysed, 6 hand-labelled). `PRUNE_ORPHANS` and the fact cleanup scan by label/property without an index; fine now, revisit past a few thousand articles.

**Infrastructure Deployment (Oct 20 – Nov 9) · 30h:**

- [ ] ☁️ Choose hosting target (VPS / cloud provider) for backend + Neo4j + SearXNG
- [ ] 🟡 🐳 Production-ready `docker-compose` — healthchecks, named volumes and a shutdown grace period exist; the Neo4j password now comes from env. Left: the rest of the secrets, a hardened SearXNG, and a full analysis run inside the backend container, which has come up healthy but never been verified end to end.
- [ ] 🟡 🔐 Copy & configure `searxng/settings.yml` (secret) for prod — `settings.yml.example` now carries the measured engine allowlist (Sep 28); the real file is gitignored and **drifts**: the local copy ran the full default roster for weeks. Left: a generated `secret_key` (the local copy still has the placeholder) and a check that the live file matches the example.
- [ ] 🟡 🧯 Logging/monitoring — INFO-level phase durations are logged, and every run's events are now journalled with timestamps. No metrics or alerting.
- ↪️ CI pipeline — moved to the testing track (October), Sep 29.

---

## 🧮 Phase 4 — Evaluation: Labelling & Harness (Sep 29 – Nov 16) · 90h

What every result the paper reports is measured with: the labelled
claims, the harness that runs the pipeline over them, and the tuning
those two make possible. Each part needs the one before it, so the order
is fixed, and it runs beside the development track (Phases 2 and 3)
rather than after it. The model benchmarks that use all three are their
own phase since Sep 30, Phase 5.

### Validation set — the labelling (Sep 29 – Oct 30) · 40h  ← **current, runs beside Sprint 4**

Not in the original plan; own budget since the Sep 28 rebalance, own
window since Sep 29. The paper commits to it
(`docs/final_document/sections/evaluation_dataset.tex`, "Custom Validation
Set") and x-fact cannot replace it: x-fact is political statements, not
the claims of positive-news articles. Gates the tuning below and 3 of
Sprint 7's 6 items.

- [x] 🗓️ **Daily labelling batch** (Sep 29, not in the original plan) — the labeller's **Today** tab asks the backend for ~10 articles, drawn at random (seeded by the day), one per source, languages alternated, never one already labelled or proposed, preferring articles from the last 60 days (to keep the gap between Rule 3's evidence and today's web small) and then topics the balance table is short of; each with the 1–3 claims the pipeline's own `ClaimSelector` would check (extractor confidence when `inference/` is down). **Label** pre-fills the form; **Skip** records why (opinion, prediction, trivial, fragment, duplicate). Removes the search that took most of each fact's time, answers the "selection by the annotator" limitation, and the skip reasons measure the claim selector's precision for the paper. First real batch: 34 sources, 1,491 links, 10 articles (5 en / 5 es), 29 claims, 200s. `backend/src/services/labelling_batch.py`, `POST /labelling/batch`; batches saved in `backend/data/evaluation/queue/`.
- [x] 🐛 **Found by the first batch: the claim splitter ignored line breaks and cut at abbreviations** — a headline, a section label and the first sentence came back as one claim, and "for A.I." ended a sentence. Fixed in `ClaimExtractor._split_sentences`, which the fact-checker uses too.
- [ ] 🏷️ Label facts 1–50 · 11h (Sep 29 – Oct 5) — in progress: 6 labelled by Sep 29, 4 of which break a guide rule (wrong tier, compound claim, label outside the guide's definition) and should be revisited.
- [ ] 🏷️ Label facts 51–100 · 11h (Oct 6–12) — 100 is the floor the paper can report on.
- [ ] 🏷️ Label facts 101–150 · 12h (Oct 13–19) — cells still short after 150 are reported short, not padded.
- [ ] 🔁 Blind re-label of the hash-chosen 20% · 4h (Oct 26–28) — at least a week after the first pass, per the guide.
- [ ] 📐 Settle disagreements, report agreement and Cohen's kappa in `custom_dataset.tex`, `join` into `custom_en_es.jsonl` · 2h (by Oct 30)

### Evaluation harness (research questions by Oct 12 · the rest Oct 20 – Nov 9) · 40h

Added on Sep 29: every result the paper will report comes out of this,
and until then it had no hours. The research questions come first, since
they decide what the harness measures; the build starts once Sprint 4
has fixed the search and the first labelling pass is done, and is proven
on the x-fact pilot before the custom set is settled, so the benchmarks
start on Nov 10 with a working tool.

- [ ] ❓ Fix 2–3 research questions, each with the metric that answers it · 3h (by Oct 13) — suggested: **RQ1** how well an open-web, low-cost pipeline verifies claims from constructive news in Spanish and English, against a temporally sound gold set; **RQ2** where it fails - retrieval, ranking or reasoning; **RQ3** how much of the verification work it takes off a journalist. Whatever answers none of them is cut or moved to future work.
- [ ] 🧰 Harness: run the pipeline's own `check_claim` over a JSONL set (x-fact and the custom set share a format) · 12h — per claim: verdict, raw verdict, confidence, stage reached, the queries sent, every candidate and ranked source, latency; per model, cached and resumable, so a crash at claim 90 does not re-pay claims 1–89
- [ ] 📐 Metrics · 6h — accuracy, macro-F1 and per-class precision/recall, the confusion matrix, bootstrap confidence intervals; search-unavailable runs and evidence newer than the claim (the guide's Rule 3) reported apart rather than folded into the error rate
- [ ] 🔍 Retrieval evaluation · 4h (RQ2) — did the system find the annotator's reference links, or their domains, among its candidates and among the evidence it ranked
- [ ] 🧭 Attribute every wrong verdict to a stage · 5h (RQ2) — retrieval (nothing pertinent found), ranking (it was found and cut), reasoning (it was ranked and misread) or aggregation - from the trace each run already records
- [ ] ⏱️ Journalist-effort metrics · 5h (RQ3) — the claim selector's precision (the labelling batch's skip reasons, recorded since Sep 29), time per fact (to add to the labeller), and the share of verdicts usable without re-checking
- [ ] 🧪 Pilot on the 64-claim x-fact set, end to end · 5h — shakes out the harness before the custom set is ready; its first numbers are the baseline for the fixed search

### Tuning against the labels (Nov 10–16) · 10h

Moved from Sprint 4 on Sep 30: both items need the settled labels
(Oct 30) and the harness (Nov 9), and they fix the defaults every
benchmark after them runs on.

- [ ] 🟡 🧠 Improve claim selection heuristics — the anchor-claim redesign (rank by how load-bearing a claim is, drop near-duplicates, keep 2–4) is done. Left: tuning the dedupe and confidence thresholds against real data.
- [ ] ⚖️ Tune `RANKING_*`, `CONFIDENCE_*` and `EVIDENCE_MIN_PERTINENCE` with real data — no labelled evaluation set exists in the repo. `RANKING_LEXICAL_WEIGHT` was carved out of the other three by reasoning, not measurement.

---

## 🤖 Phase 5 — AI Model Testing (THE BIG ROCK) (Nov 10 – Dec 10) · 80h

Its own phase again since Sep 30 (Phase 4 until then). It starts when
Phase 4 has delivered the labels (Oct 30) and the harness (Nov 9), and
runs the models over them.

> `LLMClient` is a swappable OpenAI-SDK wrapper (Ollama local by default; Groq/OpenRouter/Together via settings only). That part is true. **None of the benchmark machinery exists yet**: no harness, no labelled ground-truth set, no rubric, and no token or cost accounting.
>
> **Prerequisite work:** a labelled set of claims with human verdicts (needed by 3 of the Sprint 7 items) — the x-fact set is in the repo, and the custom set is Phase 4's labelling, Sep 29 – Oct 30 — and a harness that runs a model over them and records latency and cost: Phase 4's evaluation harness, Oct 20 – Nov 9. Per-claim LLM latency can already be read from the journal (`verifying_claim` → `claim_checked`).

### Sprint 6 (Nov 10–23) · 20h — ✍️ Writing / redaction models

70h → 50h on Sep 28 (validation set), 50h → 20h on Sep 29 (evaluation
harness). The writing benchmark serves the paper's question less than the
verification one does, so it shrinks to one comparison: the local
baseline against one hosted provider, on the corrector's metrics. **Cut:**
OpenRouter and Together AI as separate benchmarks - both speak the same
wire format as the providers kept and add the least that is new.

- [ ] 🦙 Benchmark local Ollama models (baseline, free)
- [ ] ⚡ Benchmark one hosted provider (Groq: speed)
- ✂️ OpenRouter and Together AI benchmarks — cut on Sep 29
- [ ] 📏 Compare on the corrector's 5 LLM-based metrics: grammar, factConsistency, seo, hallucinationIndex, style (readability and coverageVerification are deterministic and do not depend on the model)
- [ ] 📊 Build a scoring rubric + comparison table per model
- [ ] 💰 Log cost/latency/quality trade-offs per provider

### Sprint 7 (Nov 17 – Dec 10) · 60h — 🕵️ Verification models

70h → 60h on Sep 29: the guardrail stress test moved to the testing track.

- [ ] 🔍 Benchmark models for `LLMVerifier` (claim verification accuracy)
- ↪️ Stress-test hallucination guardrails — moved to the testing track (November), Sep 29.
- [ ] 🎯 Compare verdict agreement vs. human-labeled ground truth set
- [ ] 🧮 Re-tune `ConfidenceScorer` weights per best-performing model
- [ ] 🏁 Select final default model(s) + document rationale
- [ ] 📄 Draft results section for the paper (model comparison data)

---

## 💻 Phase 6 — Interface: Reader View (Dec 11–17) · 35h

What the frontend has today is an internal tool — eight pages (`/` analyzer, `/live`, `/claim`, `/enrich`, `/corrector`, `/scraper`, `/sources`, `/graph`).

### Sprint 8 (Dec 11–17, one week) · 35h

60h → 40h on Sep 28 (validation set), 40h → 20h on Sep 29 (testing track),
20h → 35h on Sep 30: the 15h Neo4j gave back, so the interface gets one
full week. It comes after the benchmarks, so it shows the final model's
output.

**Cut from scope on Sep 29:** user authentication, profiles, bookmarks and
recommendations v1. The paper is about automating a journalist's
verification work; none of those four answers anything it asks, and each
is a subsystem to build, secure and test. What stays is the output a
journalist or reader actually looks at.

- [ ] 📰 Topic-based feed of publishable articles (read-only) — the ingestion path exists (manual `POST /ingest`, 34 sources); the lake has to be filled before a feed has anything to show
- [ ] 🧾 Article view: the verdict per claim, the evidence and why each source was trusted — most of it exists on `/` and `/live`, for an operator rather than a reader
- [ ] 🟡 🎨 Extend the existing hand-written CSS design system (no new UI libs) — the system exists and is what `/live` and `/graph` were built on
- ↪️ E2E test for the feed — in the testing track's final window (Dec 18–24), the week after

---

## 🧪 Testing & QA — transversal (Sep 29 – Dec 24) · 50h

Its own hours since Sep 29 (before, a checklist with none), weighted
towards the end: testing follows what each phase builds. Since Sep 30 it
ends on Dec 24, so the paper's week is not also a bugfixing week. On top
of Sprint 2's 70h of testing, already spent. `./scripts/check.sh` stays
the definition of done throughout.

### October (Sep 29 – Oct 31) · 8h

- [x] ✅ Unit tests per module — `processors/`, `services/scraper/` (every strategy included), `services/fact_checker/`, `services/`, `database/`, `repositories/`, `api/`, `config/`.
- [x] 🧵 Concurrency tests — see Sprint 2: parallel jobs, the fan-out's ordering and ceilings, interleaved per-claim events, and (Sep 28) concurrent identical SearXNG queries sent once. Qdrant contention is prevented by `VectorRepository`'s lock rather than tested around.
- [x] 🗄️ Neo4j read/write tests — `tests/services/graph/` (no database) and `tests/database/test_neo4j_live.py` (real Neo4j, `./scripts/check.sh graph`)
- [x] 🗓️ Labelling batch and queue tests — 13 backend (`test_labelling_batch.py`, routes), 7 labeller (`QueueTest`), splitter regressions
- [x] 🔬 A full pass with `inference/` reachable — Sep 29: 819 passed, 0 skipped (the model tests had not run since Sep 25)
- [ ] 🚦 CI pipeline (moved from Phase 3) — none exists (no `.github/`). `./scripts/check.sh` is already the one command a job would run; the model tests need `inference/`, so CI runs the rest and the model tests stay a weekly local pass. Decide on ruff/black/mypy first, or explicitly not.
- [ ] 🟡 🔗 Integration test: full pipeline run — `tests/test_real_pipeline_integration.py` covers scrape → enrich → select, not retrieval or the LLM; it ran on Sep 29 with `inference/` up

### November (Nov 1–30) · 12h

- [ ] 🧮 Tests for the benchmark harness itself — scoring, macro-F1, kappa, the temporal-leakage split: a wrong metric is a wrong paper
- [ ] 🤖 Model comparison tests (writing + verification, Phase 5)
- [ ] 🚫 Stress-test hallucination guardrails (moved from Sprint 7) — the no-evidence → `UNVERIFIED` rule and the "definitive verdict citing nothing → `UNVERIFIED`" rule are unit-tested with fakes, never against a real model that is trying to bluff

### December 1–10 · 10h

- [ ] ☁️ Infra smoke tests (staging) — locally the backend container comes up healthy, but a full analysis inside it is unverified
- [ ] 📉 Load/performance testing before final deployment — and the parallel pipeline's speedup, asserted as overlap and never measured

### Final (Dec 18–24) · 20h — after the interface, before the paper

- [ ] 🧪 Final full regression suite, backend + frontend + `slow` + `graph` (moved from the paper phase)
- [ ] 🐛 Final bugfix pass across all phases (moved from the paper phase)
- [ ] 🚀 Final deployment verification — prod smoke test (moved from the paper phase)
- [ ] 💻 Frontend E2E tests — job polling and the reader view (no test runner exists yet; the typecheck is the only gate). Moved here from December 1–21 on Sep 30: the interface is built Dec 11–17.

---

## 📄 Phase 7 — Paper (Dec 25–31) · 35h

### Sprint 9 (Dec 25–31, the final week) · 35h

50h → 35h on Sep 29: its three QA items moved to the testing track. Since
Sep 30 they run the week *before* (Dec 18–24), so the paper is written
about a system that no longer changes. The paper itself is not cut.

- [ ] ✍️ Consolidate methodology section (pipeline architecture) — `docs/arquitectura-tecnica.md` is the starting point and was brought back in line with the code on Sep 28 (v1.1)
- [ ] 📊 Insert AI model benchmarking results (Phase 5 data)
- ↪️ Final regression suite, bugfix pass and prod smoke test — moved to the testing track (Dec 18–24)
- [ ] 📬 Submit / deliver paper draft
- [ ] 🎉 Project wrap-up & retrospective notes

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

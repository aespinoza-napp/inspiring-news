# Fact-checker

The fact-checking pipeline described in `CLAUDE.md` §"Architecture: one pipeline, two entry points",
implemented as a chain of small, independently-testable stages. `fact_checker.py` (`FactChecker`) is the
orchestrator — start there. Everything else in this directory is a stage it calls, in order.

Whether an article is worth checking at all — on topic, of positive impact, not a duplicate — is **not**
decided here: that is the admission module, `src/services/admission/`, which `AnalysisService` runs
first. `FactChecker` assumes the article was admitted.

| Stage | File | What it does |
|---|---|---|
| 1. Claim selection | `claim_selector.py` | Scores each claim for how load-bearing it is (centrality to the article thesis, overlap with its main subjects, specificity), drops near-duplicates by embedding similarity, keeps the top `anchor_claims_max` |
| 2. Evidence retrieval | `retrieval/` | `query_builder.py` (affirmative + refutation queries), `search_provider.py` (SearXNG; http(s) results only), `vector_retriever.py` (internal Qdrant corpus, never the article's own URL), `scraper.py` (full-text fetch for top web hits), orchestrated by `evidence_retriever.py`. Sequential today |
| 3. Evidence ranking | `ranking/ranking_retrieval.py` | Scores by semantic similarity + recency + source reliability (`settings.RANKING_*`) |
| 4. LLM verification | `verification/llm_verification.py` | One `LLMClient` call per claim: a verdict, cited evidence indices, and per source a stance and a quote that is kept only if it appears verbatim in the source |
| 5. Confidence recalibration | `verification/confidence_scorer.py` | Forces `UNVERIFIED` when there's no evidence or nothing was cited — the safeguard that lets a cheap/local model be used without it hallucinating a confident verdict |
| 6. Aggregation | `fact_checker.py::_aggregate_verdict` | Worst-case-wins across a claim's checks (`FALSE > MISLEADING > UNVERIFIED > PARTIALLY_TRUE > TRUE`) |

Every stage records **which claims it rejected and why** (`PipelineStage` enum in
`src/models/fact_checker/pipeline_stage.py`), not just which ones passed — `ClaimSelector.select()`,
`EvidenceRetriever.retrieve()`, and `EvidenceRanker.rank()` all return a `(kept, rejected)` pair rather
than a bare list, and `FactChecker._check_claim` merges those into each `FactCheck.rejected_sources` /
`reached_stage` / `stage_note`. This is what lets the frontend show, per claim, exactly how far it got
and what was discarded along the way (see `StageTimeline`/`SourcesPlot` in the frontend).

Every stage also fires the `on_phase(phase, data)` callback threaded through `FactChecker.run()` — see
`CLAUDE.md`: don't add a stage without also calling it, since that's what backs the job-polling API's
live progress. The events emitted per claim (queries, every source found, per-source ratings, the verdict
with each source's stance) are built by `progress.py::source_summary`, which never includes a scraped
body. They feed the frontend's Live screen and the on-disk job journal.

Tests for this directory live in `backend/tests/services/fact_checker/`, mirroring this layout 1:1, with
fakes for every external dependency in `backend/tests/services/fact_checker/fakes.py` (no live
SearXNG/LLM/Qdrant needed to run them).

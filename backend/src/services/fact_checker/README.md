# Fact-checker

The fact-checking pipeline described in `CLAUDE.md` §"Architecture: one pipeline, two entry points",
implemented as a chain of small, independently-testable stages. `fact_checker.py` (`FactChecker`) is the
orchestrator — start there. Everything else in this directory is a stage it calls, in order:

| Stage | File | What it does |
|---|---|---|
| 1. Admission filter | `validation_pipeline.py` + `validators/` | `topic_validator.py`, `positive_impact_validator.py`, `duplicate_validator.py` — all three must pass before anything else runs |
| 2. Claim selection | `claim_selector.py` | Picks the top claims by confidence, drops near-duplicates by embedding similarity, caps at `settings.MAX_CLAIMS_PER_ARTICLE` |
| 3. Evidence retrieval | `retrieval/` | `search_provider.py` (SearXNG), `vector_retriever.py` (internal Qdrant corpus), `scraper.py` (full-text fetch for top web hits), orchestrated by `evidence_retriever.py` |
| 4. Evidence ranking | `ranking/ranking_retrieval.py` | Scores by semantic similarity + recency + source reliability (`settings.RANKING_*`) |
| 5. LLM verification | `verification/llm_verification.py` | One `LLMClient` call per claim, returns a verdict + cited evidence indices |
| 6. Confidence recalibration | `verification/confidence_scorer.py` | Forces `UNVERIFIED` when there's no evidence or nothing was cited — the safeguard that lets a cheap/local model be used without it hallucinating a confident verdict |
| 7. Aggregation | `fact_checker.py::_aggregate_verdict` | Worst-case-wins across a claim's checks (`FALSE > MISLEADING > UNVERIFIED > TRUE`) |

Every stage records **which claims it rejected and why** (`PipelineStage` enum in
`src/models/fact_checker/pipeline_stage.py`), not just which ones passed — `ClaimSelector.select()`,
`EvidenceRetriever.retrieve()`, and `EvidenceRanker.rank()` all return a `(kept, rejected)` pair rather
than a bare list, and `FactChecker._check_claim` merges those into each `FactCheck.rejected_sources` /
`reached_stage` / `stage_note`. This is what lets the frontend show, per claim, exactly how far it got
and what was discarded along the way (see `StageTimeline`/`SourcesPlot` in the frontend).

Every stage also fires the `on_phase(phase, data)` callback threaded through `FactChecker.run()` — see
`CLAUDE.md`: don't add a stage without also calling it, since that's what backs the job-polling API's
live progress.

Tests for this directory live in `backend/tests/fact_checker/`, mirroring this layout 1:1, with fakes
for every external dependency in `backend/tests/fact_checker/fakes.py` (no live SearXNG/LLM/Qdrant
needed to run them).

# Goals

Ready-to-paste `/goal` prompts for the evaluation harness (roadmap,
Phase 4) and two testing-track items. Prepared on 2026-10-01; nothing
here has been run. The design they all build on is
`docs/decisions/evaluation.md`. Each prompt names that file's section
rather than repeating it, so the seven goals cannot drift apart.

## Order

```
G1 Research questions  ── needs nothing; decides what G3–G6 report
G2 Harness ──┬── G3 Metrics ───────┐
             ├── G4 Retrieval ─────┼── G7 Pilot (live: the only goal that runs the stack)
             ├── G5 Attribution ───┘
             └── G6 Effort (its labeller half needs nothing)
T1 CI, T2 Integration test ── independent of all the above
```

G3, G4 and G5 can run side by side once G2 is merged: each owns its own
module and adds its own section to the report. G7 needs G2 and G3; it is
worth more after G4 and G5.

## Rules every goal follows

These are in each prompt as "the goal rules":

- `./scripts/check.sh` is the definition of done. CLAUDE.md's invariants
  hold: no `__init__.py` in `src/`, thresholds passed per call,
  `bounded_map` for any fan-out, concurrency ceilings stay `settings`,
  no test writes into `data/raw` or `data/processed`, every shared fake
  has a contract entry.
- Nothing reaches a live service (SearXNG, the LLM, `inference/`,
  Neo4j) except G7 and T2's one recorded pass.
- When done: tick the roadmap item with what was verified and how, and
  rewrite the goal's section of `docs/decisions/evaluation.md` in the
  past tense.
- Work on a branch `eval/<goal>` off `dev`, commit there, don't push.

## Phase 4: evaluation harness

### G1 · Research questions · 3h · by Oct 13

```
/goal Fix the paper's 2–3 research questions. Start from the proposed table in docs/decisions/evaluation.md §Research questions (RQ1 accuracy against a temporally sound gold set, RQ2 where it fails, RQ3 journalist effort). Give each one the exact metric, dataset and results table that answers it. Write docs/final_document/sections/research_questions.tex in the style of custom_dataset.tex, and keep the table in evaluation.md identical to it. Then go through every open item in docs/roadmap.md Phases 4–5 and the testing track: mark each with the RQ it serves, or move it to future work (docs/final_document/sections/future_work.tex, plus a ↪️/✂️ line in the roadmap with the date and the reason). The Sprint 6 writing benchmark is the first to check: it serves none of the three as proposed. Write no code and run nothing but ./scripts/check.sh fast. Follow the goal rules in docs/goals.md. Done when the .tex exists, evaluation.md matches it, and every open Phase 4–5 item names an RQ or has been moved.
```

### G2 · Harness · 12h

```
/goal Build the evaluation harness in docs/decisions/evaluation.md §How one claim is run, §Record format and §Run layout, cache and resume. First add optional keyword args `context` and `language` to FactChecker.check_claim, passed through to _check_claim (update any fake or contract that pins its signature; /verify-claim is unchanged). Then backend/src/evaluation/ with no __init__.py: dataset.py, record.py (HARNESS_VERSION), runner.py, cli.py, so that `uv run python -m src.evaluation.cli run --dataset ... --model ... [--limit] [--thresholds] [--corpus snapshot|none] [--retry-unavailable] [--fresh]` works. Gitignore backend/data/evaluation/runs/. Tests go in backend/tests/evaluation/, use only the shared fakes and tmp_path, and prove five things: (1) a run killed after claim k resumes without calling the checker again for claims 1..k; (2) a torn last line is re-run; (3) Spanish rows reach check_claim with language='es'; (4) custom rows pass articleUrl as context.url, and x-fact rows pass no context; (5) every field in §Record format is filled. Do not run against live services; that is G7. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes and those five tests exist and pass.
```

### G3 · Metrics · 6h · needs G2

```
/goal Build the metrics in docs/decisions/evaluation.md §What is reported apart and §Metrics: backend/src/evaluation/metrics.py and report.py, plus `cli report --run <dir> [--compare <dir>]`, which writes metrics.json and report.md (with a copy of run.json) to backend/data/evaluation/reports/<dataset>/<model>/<key>/. Report accuracy, macro-F1 over the gold-present classes, per-class P/R/F1/support, the confusion matrix, and coverage plus selective accuracy. Add seeded percentile bootstrap 95% CIs (10,000 resamples) and a paired bootstrap for the difference between two runs. error, searchUnavailable and llmUnreachable claims and the temporalLeak/verdictLeak flags are reported apart, never in the error rate. Break down by language, and for the custom set by topic group, claimType and sourceTier. Pure Python, no new dependency. Tests check every metric against hand-computed values on a small fixture of records built with record.py, plus bootstrap determinism under a fixed seed and the paired bootstrap on identical runs (difference 0). Runs nothing live. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes and report.md renders from a fixture run.
```

### G4 · Retrieval evaluation (RQ2) · 4h · needs G2

```
/goal Build the retrieval evaluation in docs/decisions/evaluation.md §Retrieval evaluation: backend/src/evaluation/retrieval.py, wired into `cli report` as its own section. Import the retriever's _comparable to normalise URLs (don't copy it), and compare domains the way Evidence.domain is computed. The reference set is referenceEvidenceLinks, minus links on the row's own site for x-fact (count those as verdictLeak instead). For each claim, record link and domain hits among the candidates, the ranked sources and the cited ones. Report recall at each depth by set and language, and list the cut reasons for references that were found and then cut. Tests on fixture records: www/https/trailing-slash/query variants of a link match; a chequeado self-link is excluded from the reference set and flagged; a reference cut by the pertinence gate counts at candidates but not at ranked. Runs nothing live. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes.
```

### G5 · Stage attribution (RQ2) · 5h · needs G2

```
/goal Attribute every wrong verdict to a stage as docs/decisions/evaluation.md §Stage attribution defines: backend/src/evaluation/attribution.py, wired into `cli report` as its own section. For each scored claim whose verdict differs from gold, take the first match of retrieval → ranking → reasoning → aggregation. Compute it twice, reference-based and trace-only, and report both with counts, shares and claim ids, plus the list of claims where the two disagree. The ranking bucket lists the cut reasons. Read only fields the result records already hold: no new pipeline output. Tests: one fixture record per stage under each rule, a reference-based retrieval error that trace-only calls reasoning (it appears among the disagreements), and a searchUnavailable claim that is never attributed. Runs nothing live. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes.
```

### G6 · Journalist effort (RQ3) · 5h · report half needs G3

```
/goal Build the journalist-effort metrics in docs/decisions/evaluation.md §Journalist effort. In the labeller (standard library only, nothing imported from backend/): record `timing: {openedAt, savedAt, activeSeconds}` per fact. openedAt is when the form opens (Label in Today, or New), and activeSeconds counts only while the page is visible. Write it after the existing keys and keep it on re-save. `python labeller/app.py stats` prints JSON: selection precision (labelled/(labelled+skipped)) in total, by skip reason and by language, with the six hand-chosen facts excluded, and time per fact (n, median, IQR). In the backend, backend/src/evaluation/effort.py adds the usable-without-re-checking and confidently-wrong shares and the effort estimate to `cli report`. Tests: labeller/test_app.py (x-fact's key order still pinned; timing survives a re-save; a hidden page adds no seconds where testable) and backend/tests/evaluation/. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes, which includes the labeller tests.
```

### G7 · Pilot on the 64-claim x-fact set · 5h · needs G2, G3 (G4, G5 if merged)

```
/goal Run the 64-claim x-fact pilot end to end and report it. Bring up inference/, SearXNG and the LLM per docs/decisions/evaluation.md §Where it runs, using the production LLM limits on a CPU and mounting backend/data/evaluation into the backend service if you run in compose. Check /healthz and the SearXNG source health first and record what they said. Run `cli run --dataset data/evaluation/xfact_en_es_pilot.jsonl --model llama3.2:3b`. If it crashes, fix the harness, add a test for the bug, and resume; never restart from zero. Then run `cli report` and commit the report directory. Fill docs/decisions/evaluation.md §Pilot and the roadmap with: accuracy and macro-F1 with CIs, the partitions (searchUnavailable, verdictLeak; all 40 chequeado rows link chequeado's own verdict page), retrieval recall, the stage attribution, latency per claim, and every harness bug found. Make a recommendation, without implementing it, on excluding fact-checker domains at retrieval time (§What is reported apart, "Not decided"). Follow the goal rules in docs/goals.md. Done when results.jsonl has 64 ok records (or each missing one is listed with why), the report is committed, and ./scripts/check.sh passes.
```

## Testing track

### T1 · CI pipeline · moved from Phase 3

```
/goal Add CI: .github/workflows/check.yml on every push and pull request. Use three jobs that call the existing targets, not a re-composition of them: (1) `./scripts/check.sh backend` on Python 3.12 with astral-sh/setup-uv and `uv sync` from backend/uv.lock, with NEO4J_PASSWORD set to a dummy env var because backend/.env is not in git (Settings refuses to start without it), and the model tests skipping because inference/ is absent; (2) `./scripts/check.sh frontend` on Node 20 with `npm ci` from frontend/package-lock.json; (3) `./scripts/check.sh labeller` on plain Python 3.12. Cache uv and npm. inference, slow, graph and gcp stay out of CI (models, Neo4j, Docker): say so in a comment in the workflow and in the roadmap item, which also records the linter decision (ruff/black/mypy: none for now, unless I say otherwise). Add a backend test that every check.sh target the workflow calls exists in check.sh's case list. Validate the YAML locally (actionlint if installed, else a YAML parse). Don't push; the first green run on GitHub is mine to trigger. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes and the workflow is committed on its branch.
```

### T2 · Integration test: full pipeline run

```
/goal Close the roadmap item "Integration test: full pipeline run". Today tests/test_real_pipeline_integration.py starts from a hand-built News (no extraction) and stops at claim selection (no retrieval, ranking, LLM or scoring). Add an end-to-end test of the real AnalysisService.analyze from a URL. Extraction reads a saved HTML fixture through a fake fetch (no network). Enrichment is real, over inference/ (require_inference: it skips without it). Admission is real, on a tmp_path Qdrant. The FactChecker is real (EvidenceRetriever, EvidenceRanker, LLMVerifier, ConfidenceScorer), with only the network clients faked from tests/services/fact_checker/fakes.py: SearXNG, the evidence-page fetch, and an LLM returning a canned JSON verdict. A new shared fake needs its contract entry. The lake and the AnalysisCache go to tmp_path (the cache otherwise defaults to the real data/cache), and the graph is off. Assert: each claim's on_phase events name every stage literal in order; a source the canned answer cites survives ranking; the verdict and cited indices match the canned answer; a claim with no evidence comes back UNVERIFIED without an LLM call; the article lands in all three lake layers; the response matches ANALYZE_RESPONSE_SHAPE. Then run it once with inference/ up and record the result in the roadmap. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes with inference/ reachable and the new test ran rather than skipped.
```

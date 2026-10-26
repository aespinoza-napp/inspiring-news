# Goals

Ready-to-paste `/goal` prompts for the evaluation harness (roadmap,
Phase 4) and two testing-track items. Prepared on 2026-10-01. Done since:
every one: G1-G4 and G7 by 2026-10-14, T1 (CI) and T2 (the integration
test) on 2026-10-02, **G5 and G6 on 2026-10-20** (`attribution.py`,
`effort.py` and the labeller's timing and `stats`;
`docs/decisions/evaluation.md`). The prompts stay as the record of what
was asked. The design they all build on is
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
/goal Fix the paper's 2–3 research questions. Start from the proposed table in docs/decisions/evaluation.md §Research questions (RQ1 accuracy against a temporally sound gold set, RQ2 where it fails, RQ3 journalist effort). Give each one the exact metric, dataset and results table that answers it. Write docs/final_document/chapters/06-experimental-design/01-research-questions-metrics.tex in the style of the custom validation set's section (chapters/06-experimental-design/03-custom-validation-set/), and keep the table in evaluation.md identical to it. Then go through every open item in docs/roadmap.md Phases 4–5 and the testing track: mark each with the RQ it serves, or move it to future work (docs/final_document/chapters/09-conclusions/04-future-work/, plus a ↪️/✂️ line in the roadmap with the date and the reason). The Sprint 6 writing benchmark is the first to check: it serves none of the three as proposed. Write no code and run nothing but ./scripts/check.sh fast. Follow the goal rules in docs/goals.md. Done when the .tex exists, evaluation.md matches it, and every open Phase 4–5 item names an RQ or has been moved.
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

## Trends (added 2026-10-26)

Seven goals for the Trending lens: what goes viral, and the good news
in it. The design and the 26 Oct measurements behind it are in the
roadmap artifact's "Trends" section and `docs/decisions/trends.md`. 76 h
on top of the 900-hour plan.

Where they stand on 2026-10-26, all on `feature/trends`: **T1, T2, T4
and T5 done**, each with its live run recorded in `trends.md`. **T3
decided by its rule: not adopted.** **T6 at day 1 of 5**, labelled by
Claude, blind; days 2-5 are the author's, one a day. **T7 written** for
everything that exists, with days 2-5 as `\pending`; the thesis builds.
The e2e target holds T5's "nothing from TikTok before the click", but
the script still needs a POSIX machine. The same checks passed on
Windows, run by hand. T5's live story (a draft and its review from T4's
trial article) is recorded in `trends.md` too. `./scripts/check.sh` on
the branch, on Windows: 2,074 backend tests, the 15 inference tests, the
typecheck and the labeller's 43 pass. `test_container` failed once,
while the live trial held `data/vector_db`, and passed on its own
Qdrant folder (`QDRANT_PATH=<tmp>`). So T5's "including the e2e target"
is met by hand, not yet by the target. The prompts below stay as the
record of what was asked.

```
T1 Signals ── T2 Lens on /discover ── T3 internet_culture ── T6 Five rounds (RQ1)
                                            │
T4 Angle ── T5 Story and embed ─────────────┴── T7 Thesis section
```

T3 comes before T6 rather than after it, as the roadmap first had it:
the rule is that all five rounds run on one version of the screen, and
settling the new topic first keeps that true from the first round.

Rules every trends goal follows, on top of the goal rules above:

- **Free.** No paid API, service or key: public feeds, the project's own
  SearXNG, `inference/` and the local Ollama models only. A route that
  needs a card or an application is listed as not used, with why.
- **TikTok is never scraped.** Its trend listing needs a signed session
  and its terms forbid it. TikTok reaches the system as a hashtag or a
  link a person types, and as oEmbed's player for a link already known.
- Tests read saved feeds (`backend/tests/fixtures/trends/`), never the
  live web. Live runs are T3's re-screen, T6's rounds and T4's trial.
- Virality ranks what is looked at and never enters a verdict, a
  confidence or a source's rating.
- Work on `feature/trends` off `dev`; commit when the author says so;
  never push.

### T1 · Trend signals and a trend's card · 12h

```
/goal Build the trend signals. backend/data/trends/*.yaml, one file per signal (not source YAMLs: trends.google.com is one domain for every country, and one source per domain exists for reliability), loaded into a TrendSignal model: Google Trends' "Trending now" RSS for Spain and the US, r/UpliftingNews' top of the day, Upworthy and Know Your Meme. backend/src/services/trends/ (no __init__.py) reads them through the shared Fetcher (URL guard, timeout) into Trend records: name, signal, language, approximate searches ("2000+" -> 2000) or place in the feed, when it started, its articles (Google's attached news items; for Reddit the article a post links to, never the thread; a self-post has none) and, for each, title, outlet and link. A person's seed is a third kind: a hashtag becomes a trend searched through SearXNG's !news; a TikTok link is kept as the trend's video and its caption read through TikTok's oEmbed when it gives one. Searching a trend's name for more articles uses the SearxngClient with its DuckDuckGo fallback and fails soft (the trend keeps Google's articles and says the search failed). Tests on saved copies of the 26 Oct feeds in backend/tests/fixtures/trends/: ten Spanish trends with 30 articles, the traffic parsed, Reddit's self-post skipped and its 2016 link kept for the age filter to judge, a malformed feed reported and not raised, a seed hashtag and a seed TikTok link, a failed search noted. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes and docs/decisions/trends.md describes the signals as built.
```

### T2 · Trending as a lens on /discover · 16h

```
/goal Make Trending a way into /discover. POST /ingest/rounds takes `trending: true` with optional `signals`, `seed` and 0-3 groups (a round still needs groups when not trending; trending does not count towards the three). The candidates are each trend's articles, filtered as discovery filters links: article shape, off-mission sections and live pages, a new BETTING_DOMAINS list (FanDuel and Dimers came with the 26 Oct tennis trends; the section list has /tenis/ but not /tennis/), not already in the lake (comparable_url), each URL once, and no older than MAX_TREND_AGE, 72 hours, by the trend's time, the article's own or the date in its path. The mission screen runs on them unchanged and nothing is exempt. Ranking (selection/ranking.py): the story's 0.6 as today, split by topic emphasis only when groups were asked for (emphasis 0 otherwise, the existing no-topic path); the signal's record in this round's screen in place of the source's (0.25); virality in place of reliability (0.15), each trend's place among its signal's trends by searches or position, so every signal's top trend is 1; a seed is UNREAD. The weights still sum to 1 at every emphasis (a test) and are recorded with the round. The round keeps `lens: "trending"`, the trends with their counts, and each candidate's trend card. The AI selection is told when a round is trending, with one sentence more in its definition. frontend: a Trending button beside the groups on /discover, the signals to read, a field for a hashtag or TikTok link, the trend card on each candidate; npx tsc passes. docs/decisions/selection.md gets a "Trending" section. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes and a trending round over the saved 26 Oct feeds ranks Madrid's Metro line 10 reopening above the AP-7 lorry crash in a test.
```

### T3 · The internet_culture topic, if a re-screen holds · 6h

```
/goal Decide the internet_culture topic by measurement. Write the adoption rule first, in backend/data/evaluation/experiments/topics24/rule.md, before running anything. Add internet_culture ("Internet Culture & Trends", in Culture) to src/config/topics.py, taking Entertainment's three keywords added for the farmear aura article, with TOPIC_KEYWORDS_ES beside it and the labeller's copy of the groups kept equal (tests). Then re-screen every recorded candidate that has a title (the labelled rounds in backend/data/evaluation/experiments/{ranking,alignment,emphasis}/) with 23 and with 24 topics through a local inference/, and report in result.json and report.md: verdicts that change and in which direction, each newly kept candidate with its label, the ranking's AUC for worth offering before and after, and how many change group fit. Apply the rule. If it fails, take the topic out again and record why; either way docs/experiments.md and docs/decisions/trends.md say what was measured and decided. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes and the rule has been applied to a report.
```

### T6 · Five trend rounds labelled blind (RQ1) · 12h

```
/goal Measure the Trending lens for RQ1. Write the rule first in backend/data/evaluation/experiments/trends/rule.md: what is labelled (each trending round's first twenty: not worth offering, worth offering, clearly positive, and whether a source supports a constructive angle), against what (the same day's topic rounds over all five groups), what is reported (precision of the first twenty, the stories the topic rounds did not find, the funnel trends -> candidates -> kept by the screen -> chosen -> admitted -> published) and what would make the lens an option rather than a default. Add `experiments trends` to src/evaluation/experiments.py: it runs a day's trending round and topic rounds through the real services (inference/ for the screen; SearXNG when up, else Google's own articles only, recorded), writes the candidates to label without their scores, and later reads the labels and writes result.json and report.md. Tests on fixture rounds and labels. Then run day 1 of 5 and label it blind (the labels are Claude's until the author checks them, and say so). Days 2-5 are the author's, one a day, with the command written in the report. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes, the rule and day 1's report are committed to the branch's working tree, and the report says how many days remain.
```

### T4 · The positive angle, found and checked · 14h

```
/goal Find a constructive angle for a trend story only where sources support it. backend/src/services/trends/angles.py: the writer model (WRITER_LLM_MODEL, qwen3.5:4b) reads the analysed article's headline, lead and verdicts and the trend's card and proposes at most angle_max_proposals angles, each a question, a search query and one checkable claim; each claim goes through the fact-checker's own check_claim (the /verify-claim path) and the angle is kept only when the verdict is TRUE and its cited, supporting sources come from at least angle_min_domains domains. Never for an article the screen would call a disaster, a war or a death: the step reads the round's screen and refuses those. The minimums are WriterThresholds fields with settings defaults and overrides (invariants 1-2; test_invariants holds the pair). A trend ledger (lake/stats/trends/articles.json, attached by main.py like the sightings) remembers which article came from which trend when a trending round is queued, so a draft knows it. The kept angles and the ones refused, each with why, are recorded on the draft. Fakes for the LLM and the checker, with a contract entry if shared (invariant 10). Then one live trial on a real trend article with inference/, SearXNG and Ollama up, its time and outcome written into docs/decisions/trends.md. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes and the trial is recorded, whatever it found.
```

### T5 · Writing and publishing from a trend · 10h

```
/goal Write and publish a story from a trend. ArticleDraft gains `trend` (the card, the angles kept and refused, the video) mirrored in frontend/src/lib/drafts.ts; the kept angles' sources join the draft's sources with origin "angle" after the related news, and the writer is told the trend and each angle as an instruction it may follow only with those sources (CLOSED_WORLD_RULES unchanged). The review gains one deterministic check: when an angle was kept, the body cites at least one of its sources, and no sentence that states the angle's claim is uncited. The published snapshot carries the trend's name and the video (provider, id, link, title) through the publisher's allowlist; the reader's story page shows the video behind a click-to-load facade that names TikTok and its cookies, and loads https://www.tiktok.com/player/v1/<id> only after the click; no private person's or minor's details beyond the source. /drafts/[id] shows the trend and the angles. Tests for the check, the snapshot and the shape; npx tsc passes; ./scripts/check.sh e2e checks the facade loads nothing from TikTok before the click. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes, including the e2e target.
```

### T7 · The trends section in the thesis · 6h

```
/goal Put the Trending lens in the thesis. In docs/final_document/: the lens and its signals in candidate selection (chapters/04-proposed-method/04-candidate-selection.tex) and news acquisition (chapters/05-development/02-news-acquisition/), the angle in the writing flow (chapters/05-development/10-writing-flow.tex), the internet_culture decision where the topics are, and T6's design and day-1 numbers under RQ1 (chapters/07-results/02-rq1-finding.tex), each figure with the command that reproduces it and every number still to come marked the way the other placeholders are. Free tools only, and TikTok not scraped, said in one paragraph with why. The thesis compiles with no undefined reference. Follow the goal rules and the trends rules in docs/goals.md. Done when ./scripts/check.sh passes and the PDF builds.
```

## Left to the author (prepared 2026-10-20)

Five goals that need a person, or a model this machine does not yet
serve. In each, Claude does the preparation and the bookkeeping; the
judging, reading and testing stay human. The goal rules above apply,
except that U3 is a live run by design.

```
U1 AI labels ──── kappa and join; U3's verdict accuracy is reported on the joined set
U2 Pooled pages ── needs nothing but time (603 pages)
U3 Model runs ──── needs an LLM the backend container can reach
U4 Native readers ─┐
U5 Five readers ───┴── U5 is worth more after U4
```

### U1 · Check the AI labels (P0.2) · 4h · by Oct 30

```
/goal Close P0.2. The 108 facts in backend/data/evaluation/manual/ labelled by the AI pass are checked by me in the labeller (`python labeller/app.py`): prepare the order (the 15 `adjudicate` claims from the second look first, then by topic group), and after each session report how many are confirmed, changed and left. Then the blind re-label of the 14 recheck facts in the labeller's Review tab, by me; settle each disagreement with me one at a time, recording the reason in the fact's note. Report AI-annotator and first-second-label agreement with Cohen's kappa and intervals in custom_dataset.tex, then `python labeller/app.py join` into custom_en_es.jsonl and check split.json still covers every fact. Never change a label I have not confirmed. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes, the set is joined, and roadmap P0.2 and the "Settle disagreements" item are ticked with the kappas.
```

### U2 · Judge the 603 pooled pages (P1.1) · ~5h

```
/goal Finish the retrieval ablation's relevance judgements. I judge the pages in data/evaluation/judgements/manual-test.jsonl with `cd backend && uv run python -m src.evaluation.cli judge --judgements data/evaluation/judgements/manual-test.jsonl` (it resumes where it stopped); between sessions, say how many are left. When none are, run `cli pooled` over the three retrieval-only runs in data/evaluation/runs/manual-test/retrieval-only/ (all, anchor, anchor_proposition) with the same --judgements, and write precision, recall, MRR and coverage with their paired intervals against the all-queries baseline into reports/manual-test/retrieval.md, the P1.1 roadmap item and the "First ablation, 2026-10-20" paragraph of docs/decisions/evaluation.md. Say plainly whether the default `query_kinds` should change, and change it only if I agree. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes and every page has a judgement.
```

### U3 · The model runs · ~12h of CPU, mostly unattended · needs an LLM

```
/goal Run the model half of the evaluation once an LLM is reachable. Run the harness from the host (`cd backend && uv run python -m src.evaluation.cli ...`), with `LLM_BASE_URL=http://localhost:11434/v1`, `INFERENCE_URL=http://localhost:8001` (a local `inference/`, since compose does not publish 8001) and `SEARXNG_URL=http://localhost:8080`: then Ollama need not listen beyond 127.0.0.1. First confirm the model is pulled (`ollama list`: llama3.2:3b, the baseline) and inference answers `/healthz`; stop and tell me what is missing if not. (Started 2026-10-20 this way: closed-book, full and oracle on the test half.) Use the CPU limits from docker-compose.prod.yml and one model in Ollama at a time (scripts/stack.sh). On the test half: `cli run --closed-book`, a full run and `--oracle`, then `cli report --compare` against the full run and `cli table` over the three. Re-run `cli report` on the existing train, test and oracle runs so they gain the attribution and effort sections, with `--minutes-per-fact` from `labeller/app.py stats` once facts are timed. If the dates allow, the freshness retrieval-only re-runs at day 7 (Oct 27) and day 30 (Nov 19). Record each result with its interval in docs/decisions/evaluation.md and the roadmap, and record any run that failed as failed. A hosted verifier is out of scope unless I name one and its key. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes and the three test-half runs are reported.
```

### U4 · Native readers for the Spanish and Catalan · 2h of theirs

Prepared 2026-10-20: `docs/review/reader-ca.md` and `reader-es.md`, 223 rows each, generated by `node scripts/reader_strings.mjs` (functions rendered with sample values, plurals at 1 and 3). Regenerate after any change to `readerText.ts` and before sending.

```
/goal Get the reader's Spanish and Catalan read by native speakers. Export every es and ca string from frontend/src/lib/readerText.ts, and the guide's text from app/reader/guide/page.tsx, into two review sheets (one per language: key, English, current text, an empty column for the correction) under docs/review/. I send them to a reader of each language and paste back what they return. Apply each correction exactly, keeping the plural and gender agreement of verdictTally and sourcesLine, and keep a short log of what changed and why in the sheet. Nothing is changed without a reader's correction behind it. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh and ./scripts/check.sh e2e pass and the two roadmap items' "native read" is ticked with who read it (initials only).
```

### U5 · Five readers try it (RQ4) · 3h

Prepared 2026-10-20: the protocol and the sheet, `docs/review/reader-test.md`. Two things left to decide before the first session: the three pages (written into its table), and task 2's form - the public reader never shows a FALSE claim, since an article with one is not publishable, so FALSE reaches a reader only through the guide.

```
/goal Run the five-reader test of the reader view. Write the protocol in docs/review/reader-test.md: five people who are not me, the same three tasks each (explain why a given claim was judged as it was; tell a FALSE from a "Not checked"; say whether a given story was written by a person), one fixed article and story per task chosen from what the stack serves, what I say and do not say, and a sheet per reader for success, time and what confused them. I run the sessions and paste back each sheet. Then summarise per task: successes out of 5, median time, and the confusions grouped, with each reader quoted by initials only; record it in the RQ4 section of docs/decisions/evaluation.md and the roadmap item, and file each confusion that needs a change as its own roadmap item rather than fixing it here. Follow the goal rules in docs/goals.md. Done when ./scripts/check.sh passes and all five sheets are summarised.
```

# Fact-checking: every change, and where it stands

> 2026-10-22. What has been modified in the fact-checking pipeline since
> the first commit, in the order it happened, why, and what each change
> was measured to do. Sources: the git history of
> `backend/src/services/fact_checker/`, `search.py`, `duckduckgo.py` and
> `llms.py` (53 commits), and the decision records it links. The detail
> behind each item is in the record named beside it; this page is the map.

## Summary

- **What it does.** An admitted article's 2-4 load-bearing claims are
  checked at once; each is searched on the open web (SearXNG, DuckDuckGo
  when it cannot answer) and in the internal corpus, its sources ranked
  and gated for pertinence, and one call to a local `llama3.2:3b` judges
  it against a numbered list of them; the confidence is recalibrated
  against the evidence, and the article takes its worst claim's verdict.
- **How it got here.** July built the pipeline (section 1). September made
  a verdict mean something: an audit trail, three queries instead of
  one, the claim read inside its article, failed searches and
  unreachable models kept apart from an honest UNVERIFIED, the model's
  own "unrelated" enforced (section 2). October measured it, with a
  harness, a frozen split and model trials (section 3). And from late
  September the time came down call by call (section 4).
- **Where it stands on time.** On this desktop a claim takes 57 s at the
  median with the defaults; the fast profile takes 17.8 s and snippets
  alone 14.2 s, never past a 30 s deadline, and the app now shows the
  seconds of every search, page and model call (section 5). The fast
  profiles cost about 17 points of accuracy on the train half (50.7%
  thorough against 33-34%), so the app stays thorough and the trade-off
  is one line in `backend/.env`.
- **Where it stands on verdicts.** The 3B model is the limit: at chance
  on the custom set's natural claims (kappa -0.013 on the test half), it
  answers FALSE to true claims, and no speed change moved that. Claude,
  checking the same ten claims by hand, got 7 right in 13 s each; every
  pipeline setup got 2-3. The next large gain is a better reader - the
  9B, a GPU, or a hosted model - not a faster or wider search.
- **What is not settled.** 108 of the 139 gold labels are still the AI
  pass's, unchecked; every accuracy figure moves when they are.

## 1. The first pipeline (July)

| Date | Change | Why |
|---|---|---|
| 07-02 | Code structure | `d4b4b67` |
| 07-30 | Sentiment and topic validation, duplicate detection, positive/negative filtering | The checks an article passes before its claims are; later moved out of the fact-checker (09-23) |
| 07-31 | The first fact-checker: claims, a SearXNG search, an LLM verdict (`cf173d9`) | |
| 07-31 | No OpenAI key; ranking and confidence weights in settings | The LLM is a local Ollama behind an OpenAI-compatible endpoint; weights tunable without code (`c488c91`) |
| 07-31 | `/analyze` runs the real pipeline; `on_phase` progress, pollable every second | It was one blocking call with no sign of where it was (`4268cff`) |

## 2. Making a verdict mean something (September)

| Date | Change | Why, and what it fixed |
|---|---|---|
| 09-03 | Every claim records its rejected sources and the stage it reached (`PipelineStage`) | A verdict with no trail cannot be checked (`4708643`) |
| 09-07 | Articles are stored after fact-checking | `VectorRepository.save()` was never called: duplicate detection and internal evidence had always searched an empty collection (`a6ce9ec`) |
| 09-08 | Every pipeline threshold per run (`PipelineThresholds`) | Thresholds frozen at import could not be changed per run (`281550a`; invariants 1, 2) |
| 09-09 | Spanish scored in Spanish | 7 of 12 sources are Spanish and every lexicon was English (`c3cdc58`) |
| 09-15 | Anchor claims and source comparison | Claims were "check-worthy sentences"; now the 2-4 the article's credibility rests on (`96b4ddc`) |
| 09-21 | Three queries a claim: anchor, proposition, refutation; reciprocal rank fusion; the pertinence gate | A claim about ACME came back FALSE at 83% on three pages about the word's Greek etymology (`1187570`; `retrieval.md`) |
| 09-22 | An unreachable LLM is not an UNVERIFIED verdict (`llm_unreachable`); default model `llama3.2:3b` | A dead provider read as "checked, no support" (`624fd1f`) |
| 09-23 | Each claim judged inside its article (headline, opening, subject restored) | A claim about "aura-farming" contests was confirmed by a marathon's prize money (`20379f3`) |
| 09-23 | Admission (topic, positive impact, duplicates) moved out into its own module | It judges an article, not claims (`c0adf73`) |
| 09-28 | No LLM call below the evidence floor | The answer was thrown away anyway: 23 of 24 claims on 09-25 (`8d7f600`) |
| 09-28 | Science engines (arXiv, Crossref, Semantic Scholar, PubMed) and Wikipedia behind SearXNG | They answer when the web engines rate-limit (`8d7f600`) |
| 09-30 | A failed web search is `searchUnavailable`, not UNVERIFIED | 68 of 69 queries came back empty on 09-25 and every claim looked honestly unverified (`cdf63d9`) |
| 09-30 | DuckDuckGo, keyless, when SearXNG cannot answer | A second route; challenged as a bot from the dev machine the same day (`f96dea1`) |
| 09-30 | The model's own "unrelated" judgement is enforced | A citation of a source it had called unrelated still counted as support (`a7fd75f`) |

## 3. Guardrails and measurement (October)

| Date | Change | Why, and what it found |
|---|---|---|
| 10-02 | `check_claim` takes the article's context and language | Lone claims were searched with the English lexicon and could be "confirmed" by their own article (`0f09b80`) |
| 10-02 | The evaluation harness: `check_claim` over a labelled set, resumable, every claim's trace recorded | Nothing had ever measured a verdict (`95479ee`; `evaluation.md`) |
| 10-02 | Guardrail stress test: 83 adversarial answers through the real verifier and scorer | Six ways to bluff past the rules, each closed - e.g. `[0, 0, 0]` took a one-source FALSE from 0.70 to 1.00 confidence (`17aeb4a`) |
| 10-13 | First measurement, x-fact pilot | 29.7% accuracy, kappa 0.07: at chance against professional fact-checkers (`evaluation.md`) |
| 10-19 | The custom set's frozen 50/50 split; the second look; model trials per role | Train 44.9%, test 52.9%; the second look fired on 17 test claims for +0.0 points at ~2 min each, so it stays off; `llama3.2:3b` stays the verifier, `qwen3.5:9b` more careful at 3x the time (`fa9f9f9`) |
| 10-20 | Closed-book and oracle modes, stage attribution, query-kind ablation | The model alone 34.3%; with the annotator's own pages 54.3% (+20.0 points): retrieval costs about ten points, the model's lean more (`b0bf646`, `eb25b54`) |

## 4. Time and resources

| Date | Change | Measured |
|---|---|---|
| 09-21 | A process-wide ceiling per external service | Fan-out multiplied to 96 simultaneous requests from a default setup (`efada46`; `concurrency.md`) |
| 09-21 | An article's claims checked concurrently, each reported as it lands | A four-claim article took four times as long as it needed to (`80fc87a`); worth x3.4 with a fast model, x1.16 with one CPU model call at a time (10-04) |
| 09-28 | A query sent once, shared by claims asking it at once, kept 10 minutes | Claims of one article share their anchor query (`8d7f600`) |
| 10-01 | One LLM call at a time on a CPU, 180 s timeout (production, eval) | Four at once: 90-103 s each, 3 of 4 claims "unreachable" |
| 10-16 | `inference/` sends one request at a time; enrichment embeds the article once | The ranker's request 9.4 -> 6.8 s (`5278379`) |
| 10-21 | The verifier reads the passages about the claim, not each page's opening (700 characters) | Prompt -29.5%, the call 24% faster, accuracy +4.4 points [-4.4, +13.2] on the same pages (`978b314`) |
| 10-21 | The answer capped at 1,024 tokens, a capped answer not asked again | One looping call had held the model for 360 s (`8b9f441`) |
| 10-21 | Embeddings batched by length (`inference/`) | Snippets 12.6 -> 6.5 s, topic keywords 17.9 -> 4.4 s (`b1796d9`) |
| 10-21 | Evidence pages parsed one at a time; each fetched once an hour per process | 200 pages 58.4 -> 41.5 s; the slowest 39.6 -> 16.8 s (`5a8db31`) |
| 10-22 | **This branch**: below |  |

## 5. This branch: the 20-second fact-check (2026-10-22, `perf/fast-fact-check`)

The author asked for the fact-check to take less time and fewer
resources, for the time each search takes to be visible per article, for
each claim in about 20 seconds tried on the first ten claims and
compared with Claude, and for this report. Detail and every number:
`docs/decisions/performance.md`, "The 20-second fact-check".

| Change | Where | What it does |
|---|---|---|
| Time per query, page, stage and model call, on every claim's events | `evidence_retriever.py`, `search_provider.py`, `search.py` (`last_route`), `scraper.py`, `fact_checker.py`, `llms.py` (`last_call`) | Each query's seconds, results and how it was answered; each page's seconds and outcome; ranking; the wait for the model and its call, with tokens; the claim's total. No new phase, no response-shape change |
| The timing in the app | `frontend/src/components/TimingBreakdown.tsx`, `lib/liveTrace.ts`, `/live`, `/` | An article's stages as one bar; per claim a "Time" block with the queries and pages tables |
| The timing in the harness | `evaluation/record.py`, `report.py` | `latency.search`, `pages`, `llmWait`, `llmCall`; four more rows in every report's response-time table |
| A compact answer (`verifier_answer`) | `llm_verification.py` | A stance per source and a short reason, no quotes, a 200-token cap: half the tokens written |
| A lexical pre-rank (`evidence_prerank`) | `evidence_retriever.py` | The pages to fetch chosen by the claim's terms, without embedding ~20 snippets |
| Ranking on the passages (`ranking_text`) | `ranking_retrieval.py` | The ranker and the pertinence gate judge what the model will read |
| Snippets only (`fetch_evidence_pages`) | `evidence_retriever.py` | No page fetched or parsed |
| A claim deadline (`claim_deadline_seconds`) | `deadline.py`, `concurrency.py` (`bounded_map` and permit timeouts), `llms.py` | Pages waited for until half of it, the model given the rest; out of time is "not checked", never a verdict |
| Profiles (`FACT_CHECK_PROFILE`) | `thresholds.py`, `data/evaluation/thresholds/{fast,fast_snippets,thorough}.json` | One setting chooses an environment's defaults: `thorough` (as before), `fast`, `fast_snippets` |
| The app on the chosen verifier | `backend/.env` (local) | It named the 8B `llama3.1` with GPU limits; now `llama3.2:3b`, one call at a time, 180 s |
| Measured, not built: a thread-tuned model | `scripts/bench_ollama.py` | No thread count beat Ollama's default on this CPU |

**The contest** (the first ten train claims, rule written first,
`backend/data/evaluation/experiments/speed/`):

| | Median a claim | p90 | Right of 10 |
|---|---:|---:|---:|
| A, today's defaults | 57.2 s | 69.2 s | 3 |
| B, compact answer | 39.3 s | 45.8 s | 2 |
| C, fast | 17.8 s | 21.0 s | 2 |
| D, fast on snippets | 14.2 s | 16.2 s | 2 |
| Claude, by hand | 13.1 s | 16.9 s | 7 |

By the rule D wins on the ten claims. Every pipeline setup
said FALSE to true claims; Claude got the seven TRUE ones and missed the
three whose gold is not TRUE.

**On the whole train half** (69 claims): D 14.2 s a claim (p90 17.0,
slowest 21.2), accuracy 33.3% [21.7, 44.9]; C 16.7 s (p90 24.1), 33.8%
[23.5, 45.6], one claim stopped by the deadline at 30.2 s. Paired against
the 19 Oct thorough run (42.0%): -8.7 [-23.2, +5.8] and -7.4 [-20.6, +5.9]
points. But the thorough pipeline on the same 69 claims the same day
scored **50.7%** [39.1, 62.3], and paired against it D is **-17.4 points
[-30.4, -4.3]** and C -16.2 [-27.9, -4.4]: measurably worse. By the rule
the default stays `thorough`; `fast` and `fast_snippets` are one line in
`backend/.env` for whoever wants ~15 s a claim at that cost.

**What to do next, by what it would buy:** find which part of the fast
profile costs the points (the compact answer alone, entry B, on the 69
claims; then five sources at 700 characters) and keep the rest; a better
reader (the 9B, a GPU or a hosted model), since the 3B's FALSE lean is
untouched by any of this;
then fit the pertinence gate and the confidence weights on the train half
once the 108 AI labels are checked; then a "thorough" toggle on `/` (the
per-run overrides it would send exist; no page sends them yet).

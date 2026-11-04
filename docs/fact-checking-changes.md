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
- **Where it stands on verdicts.** The 3B answered FALSE to about half
  of the true claims, mostly because a detail was missing from its
  sources, and no speed change moved that (Claude, checking ten claims by
  hand: 7 right; every pipeline setup 2-3). On 22 Oct afternoon the
  verifier was changed to ask about one source at a time and take the
  side more outlets take (section 6): on the test half, on the same
  evidence, natural claims 49.1 -> 67.3% and confidently wrong verdicts
  47 -> 29%, at 44 s a claim instead of 63 - but claims with one altered
  detail 60 -> 13%. A better reader (the 9B, a GPU, a hosted model) is
  still the larger gain; the 9B's run on the same evidence is in
  section 6.
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

## 6. Iterating on the verdict (2026-10-22, afternoon)

The author's priority after the speed work: the fact-check itself. Every
number here is on fixed evidence: a run keeps each claim's retrieval and
`--replay` judges it again, because the same pipeline searched twice moved
by 6-9 points. Rules written before each run:
`backend/data/evaluation/experiments/verifier/rule.md`; the detail is
`docs/decisions/evaluation.md`, "The verifier's FALSE".

| Change | Where | What it did |
|---|---|---|
| Replay: a run keeps its evidence, another verifier judges it again | `evaluation/replay.py`, `cli run --replay` | Verifiers compared on identical sources; the 3B, replayed, gave 10 of 10 identical verdicts |
| Stated rules: each verdict defined by what a source states, a `silent` stance, the scorer holding the verdict to the stances | `verifier_rules=stated`; `confidence_scorer.holds_to_stances` | Train -8.7 points [-17.4, 0.0]: the 3B's stances do not match its own verdicts, and the check removed right FALSEs as readily as wrong ones. Kept as an option, off |
| One source at a time | `verifier_answer=per_source`; `verification/per_source.py` | One short call per source, the verdict the side more outlets take, a tie UNVERIFIED. Train 44.9 -> 47.8%, test 51.4 -> 55.7% (+4.3 [-8.6, +17.1]); right when it commits +13.9 [+0.3, +27.3]; confidently wrong 47 -> 29%; natural claims 49 -> 67%, altered ones 60 -> 13%. **The default since** |
| A file is not a page | `scraper/fetcher.py`, `NotAPage` | A PDF's bytes had become a 167-million-character evidence page for two claims; refused before the body is read |
| A larger reader, `qwen3.5:9b` (V3) | the list verifier, replayed | Train 50.7%, right when it commits 67.4% against 47.7% (+19.7 [+4.1, +35.6]), kappa 0.141 -> 0.282, altered claims 11 of 15 and FALSE to only 8 true claims - at ~90 s a call here. The case for a GPU or hosted endpoint |
| Quote first (V4) | the per-source prompt | Ties V2b on train (47.8%) with more FALSE to true claims (11 against 6). Not adopted |

**What to do next:** catch the altered detail without bringing back FALSE
for true claims - the per-source prompt comparing the claim's figures,
dates and names with the source's, one by one, or the larger reader on
the per-source question; and the 9B's result on the same evidence
(section 6 of the decision record) decides whether a GPU or hosted model
is the next step.

## 7. Every pulled model, and a hosted one (2026-10-29)

The author's request: benchmark the models this laptop has pulled, per
role, and Groq's hosted ones against them on the verdicts. The lists, and
why each other model is left out, were agreed before any result was read
(`scripts/bench_models.sh`, `scripts/bench_groq.sh`). The verifiers
replay one searched `llama3.2:3b` run (`cc053417c0cb`, 47.8% on train,
63 of 69 claims with evidence), so only the reading differs.

| Change | Where | What it did |
|---|---|---|
| The benchmark, one model at a time, as "-bench" copies (10 threads, 16k context) | `scripts/bench_models.sh` | Verifier screen on 20 train claims, writer in en/es/ca, reviewer on the planted defects and the seeded drafts. Not in parallel: on the 165U the answer is bound by memory bandwidth and 15 W, so two models at once each take about twice as long and every recorded time is the other's waiting too |
| Groq's verifiers on the same evidence | `scripts/bench_groq.sh` | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`; the two Llama models answer `model_not_found` on this key |
| Room above the answer cap for a model that reasons first | `LLM_REASONING_TOKENS`; `llms.py` | gpt-oss's reasoning counts against `max_tokens`: at the per-source 160 it came back `json_validate_failed`, empty, 20 calls in 20 at Groq's default and 9 in 20 at `low`; with 2,048 above the cap, 0 in 15. In the run key, like the effort |
| A rate limit waited out, not lost | `llms.py`, `RateLimitError` | Groq's free plan allows 8,000 tokens a minute per model; a 429 counted as a failure was a source never weighed. Now its `retry-after` is waited out outside the LLM permit, up to 60 s and 10 times a call; a longer wait (a daily cap) or none fails as before. Ollama never answers 429, so local runs are unchanged |

**Result for the verifier: `llama3.2:3b` stays.** On the first 20 train
claims none of `granite3.3:8b` (+5.0 [-10.0, +20.0]), `gemma4:e4b`
(-10.0) or `qwen3.5:9b` (-20.0) gains with an interval above zero, so
the faster model is kept (7.2 s a model call; granite 19.9). Granite is
the one to run on all 69 (coverage 95%, kappa +0.27 [+0.01, +0.49]).
Groq's run was not made then; a 5-claim smoke run was, on 2026-10-30
(section 8). `data/evaluation/experiments/models/results.md`.

## 8. Two editions, and Groq tried (2026-10-30)

| Change | Where | What it did |
|---|---|---|
| The Devastating edition is not fact-checked | `AnalysisService._check`, phase `fact_check_skipped` | At the request of the person running it: an admitted article of that edition is stored and published with no claim selection, search or model call. Its report carries no verdict of ours (UNVERIFIED, no claim selected), so the reader shows it as **Not checked**. The positive edition is checked exactly as before. `docs/decisions/editions.md` |
| A run's lineage records any threshold, not numbers only | `lineage.ThresholdValue` | `threshold_overrides` was `int \| float`, so a string override (`edition`) failed to start the lake record: no Devastating run was stored, published or writable. A string switch such as `verifier_answer`, or `query_kinds`, overridden per run would have failed the same way |
| Groq's three verifiers, a 5-claim smoke run | `scripts/bench_groq.sh "" 5` | Replays of `cc053417c0cb`, like the local candidates. Every call answered (13 rate limits waited out, none lost). On the 5 claims all models share: `qwen/qwen3.8-27b` 4 of 5 at 1.3 s a claim's model time, as `gemma4:e4b` (4, 118 s); both gpt-oss 3 (FALSE on an UNVERIFIED claim), the 3B 3 at 46 s. Five claims decide nothing; the 20-claim screen is next |


## 9. The web search had stopped searching (2026-11-03)

Found from one article, Gavi's "South Africa's HPV vaccination drive ...
is working": four claims, all UNVERIFIED at 5-10%, every cited source an
arXiv paper, a DOI record or a dictionary. The model did run (about 70 s a
claim, a stance per source), and correctly found that nothing it was given
addressed the claim. Two causes, both upstream of it:

- **Bing searched only the first word.** Through SearXNG, from this
  machine, Bing answered "cervical cancer vaccination Africa" with pages
  about neck pain and "Gene therapy restores sight..." with the Wikipedia
  page "Gene", in Spanish whatever `language` said, on the pinned image
  and on the newest alike. Google, Brave and Yep were suspended at the
  same time, so no general web engine was really answering. Fixed in
  configuration: measured engine by engine on three claims
  (`docker/searxng/settings.yml`, "2026-11-03"), Bing out (1 of 30
  on-topic), DuckDuckGo (25/29), Startpage (25/30), Mojeek and Yahoo in,
  Bing News kept; the SearXNG image 2026.9.8 -> 2026.11.2, on which
  Startpage and Yahoo parse again. The same HPV query then returned the
  South African health department's single-dose recommendation and the
  news of the 2024 switch.
- **Acronyms never reached a query.** A content word had to be 4+ letters,
  and GLiNER had not tagged "HPV", so the anchor query was
  `South Africa "2024" 2024` and no query named the subject. Acronyms
  (2-6 capitals) are now anchors (`terms.acronyms`) and, at 2-3 letters,
  content words that bypass the stopword list (WHO, US); a year that is
  both a figure and a date is asked once. `test_acronym_terms.py`.

**What it means for the numbers.** Both change retrieval, so a run after
today is not comparable with one before it without a replay (`cli run
--replay`). Nothing says when Bing started answering this way: the source
probe counts results, not whether they are on the subject, which is how it
went unnoticed. Check the queries on `/live` before trusting a batch of
UNVERIFIED verdicts.

## 10. What exactly is checked: restating a claim (2026-11-03)

"Samuda argued Jamaica was different because, although the country had
'conquered our crime monster', it had 'spent 30 years being in the top
three most murderous countries on the planet'" was searched as
`Samuda Jamaica "30"` and judged as a quotation. Two things in it can be
checked - that a minister said it, and that Jamaica spent thirty years
among the three highest murder rates - and only the second is the fact the
article rests on.

`claim_restatement=standalone` (a threshold; `CLAIM_RESTATEMENT`, **off by
default**) adds one model call per claim before retrieval
(`services/fact_checker/restatement.py`): from the headline, the opening
and the sentence, the model answers its kind (fact / attributed / opinion),
the speaker, the sentence made self-contained, the one statement to check
(for reported speech, the fact inside the quote) and one or two questions.
The statement is then what is searched, ranked and judged; the check keeps
the sentence as its `claim` and the restatement beside it
(`FactCheck.restatement`, the `claim_restated` event, `restatement` in the
response - cache schema 14 - and `checkedAs` on the reader).

The answer is held to the sentence, deterministically: no number the
article does not contain; a plain statement, never a question or a topic;
every number of the sentence kept; at least one of its content words. When
the checkable statement fails, the model's own standalone sentence is tried
under the same rules; otherwise the sentence is checked as written, with a
note saying why. A sentence carrying a figure is never taken for an
opinion. Under a claim deadline it is skipped, like the second look.

Measured only by hand, on the Jamaica article's four selected claims with
`llama3.2:3b`. Before the rules on statements and figures, the model
restated the Samuda sentence as "Jamaica's ranking in the most murderous
countries on the planet" (a topic, the 30 years gone), and in a second run
called it an opinion; after them: "Jamaica has spent 30 years being in the
top three most murderous countries on the planet". Tourism: "Tourism is the
largest foreign exchange earner and the main source of income for nearly
200,000 Jamaicans", found quoted and judged TRUE. The swim sentence lost
its "11" and was checked as written. `gemma4:e4b` (`reviewer`) took 80-145 s
a sentence and ran out of its 400-token answer; `qwen3.5:4b` (`writer`)
about 90 s: neither is usable for this on the CPU. **Not adopted**: whether
it helps is a retrieval question - the reference-evidence recall of a
retrieval-only run with and without it on the train half - and that is
the measurement to make before turning it on for the harness.

## 11. Whether a source says anything of its own (2026-11-03)

The two real articles above showed sources that were not sources:
`thenote.app`, `newsminimalist.com` and `lipstickalley.com` "supporting"
the Guardian's sentence by repeating it, and the 3B marking `theconversation.com`
as *contradicting* a sentence it quoted from that same page. On the train
half (run `cc053417c0cb`, labels unreviewed): 12 of 69 claims had such a page,
17 of 303 judged sources, 15 of them "supports".

`fact_checker/independence.py` (`evidence_independence`, **on by default**,
`false` in `thresholds/thorough.json`), inside `_judge`, so replays and second
looks go through it. Word-level, no model:

- **A page repeating the sentence is not evidence**: taken out, with its reason
  among the rejected sources.
- **The same sentence with one detail changed contradicts it**: "68" where the
  claim says "168", "summer" for "spring". The claim is FALSE and the model
  is not asked, since this is what it reliably misses. Unless a page also repeats
  the sentence word for word: then outlets disagree, and the model judges.

**Replayed on the train half**, same evidence, same model (`c4da4471418d`
against `cc053417c0cb`, labels unreviewed): accuracy 47.8 -> 46.4%, paired
**-1.4 points [-7.2, +4.3]**, no detectable difference; natural 29 -> 26 of 54,
altered 4 -> 6 of 15, confidently wrong 20 -> 20; 13 copies removed. Two natural
claims were TRUEs resting only on a copy of their own sentence, and became
UNVERIFIED. A third, `fact010`, is the cost a simulation on recorded stances
missed (it said 47.8% and 19): a removed copy frees its slot, another source
gets judged, and `es.wikipedia.org` turned a right UNVERIFIED into TRUE. **So
this was not adopted for accuracy, which it does not raise.** It was adopted
because a verdict resting on a page repeating the claim was never evidence.

**Read the altered figure with care.** The set's altered claims were made by
changing a detail of a real sentence, which is exactly what this detects, so
the gain on them overstates what it finds in the wild. The figure to trust is
its false alarms: 0 on the 54 natural train claims, and none on the two real
articles. The test half has not been looked at.

The HPV article, the same evidence sources: "Since October 2024, South Africa
has adopted a single-dose HPV vaccination" was FALSE (the 3B reading a copy of
the sentence as contradicting it) and is TRUE at 93%, on The Lancet. Still FALSE,
wrongly as far as can be told: two claims where the 3B cites an unrelated
sentence as contradicting ("96% diagnosed" against "7.9 million living with
HIV"), which withholds both articles under worst-claim-wins. So:

**Tried and not adopted.** Requiring a contradicting source's quote to overlap
with the claim. It does not separate good contradictions from bad ("nació en
Jerez" scores 0.14; a wrong one 0.57). At 0.5, true claims called FALSE fall
7 -> 1 and altered claims caught fall 6 -> 3: a policy choice on thin data, not
a fix. Requiring a quote at all: altered 4 -> 2.

Also on 3 Nov:

- **An off-subject answer is no answer** (`search.py`, `MIN_QUERY_COVERAGE`,
  0.35). If the best web result holds under 35% of a query's words, the search
  counts as failed: DuckDuckGo next, then "not checked", never UNVERIFIED.
  Measured on 12 proposition queries: Bing's best 0-29%, the fixed engines'
  44-100%. The source probe reports it (`offSubject`, `queryCoverage`, and two
  longer probe queries: "renewable energy" could not tell the difference).
- **Outlets are counted as outlets** (`fact_checker/outlets.py`): `en.` and
  `es.wikipedia.org` are one voice, `bbc.com` and `bbc.co.uk` one, in the
  verdict's count, the independent domains and the funnel's one-page-per-domain.
  `abc.es` and `abc.net.au` stay two. Closes the 28 Oct audit's N7 too.
- **A looping model is not an unreachable one** (`llms.py`): Ollama's "token
  repeat limit" now reads as no usable answer, and is not asked again.
- **SearXNG `safe_search: 1`**: adult sites were taking candidate slots.

## 12. What a claim turns on, and the queries built from it (2026-11-04)

Found by checking the first 20 train claims by hand against the pipeline
(`docs/troubleshooting/`, `backend/data/evaluation/experiments/claude-search/`):
Claude got 16 right, the pipeline today 9. Upstream of every wrong verdict was a
search that could not find the point. **Built, opt-in, not yet measured.**

- **Harness claims had no figures.** `ClaimService.build_claim` (`POST
  /verify-claim`, and so every evaluation-harness run) makes a `Claim` with no
  `facts`, so the anchor query's quoted figures, which the article pipeline's
  `ClaimExtractor` fills, were empty. The harness has been measuring a weaker
  search than the app runs. Not changed under the default, so earlier runs stay
  comparable.
- **`query_plan: checkable`** (`QUERY_PLAN`, default `sentence`):
  `fact_checker/retrieval/checkable.py` reads a claim's checkable point from the
  sentence, with no model:
  - identifiers kept whole (`SE-20`, where the old pattern kept `20`), times
    (`14:49`) and counts with their noun (`11-set`);
  - figures, most distinctive first, with their scale (`25 millones`,
    `0.001 per cent`);
  - day-month dates (`12 September`);
  - names as runs of capitalised words (`James Michael Roe`, `Ignacio Calvo de
    Mora`);
  - the assertion's words without the filler ("Meanwhile", "been", "Indeed").

  `query_builder.plan_checkable` asks the three questions from that point.
  When the claim carries a distinctive figure, an identifier or a day, a
  **specifics** query (`QueryKind.SPECIFICS`, switched by the `refutation`
  kind) replaces "fact check OR debunked OR false". That query found no
  refutation in 20 claims and twice found its own words. The point goes out
  in `searching_web.checkablePoint`.
- fact037, for instance: `Florida` / `Florida been total known travel related
  cases` / `Florida fact check OR debunked OR false` became `Florida "212" 2026`
  / `Florida "212" travel related cases` / `Florida "212" 2026 travel related
  cases`.
- **The subject the sentence lost** ("dengue" in fact037, said only by the
  headline). Under `checkable` the harness gives each custom-set claim its
  article's headline from the labeller's batches (`dataset.article_titles`) in
  `ArticleContext.search_title`, which only the search reads. The subject is
  the headline's words that the article's other sentences repeat. And the
  app's own rule (`terms.subject_terms`) was found to be all or nothing: a
  sentence naming one subject word ("Florida") lost the rest ("dengue").
  `checkable.lost_subject` restores each missing one.
- **Not yet measured.** A searched try in the iteration campaign
  (`/iterate-fact-check`, `query_plan` is in `SEARCH_SIDE`), against two
  searched baselines in the same window. The default stays `sentence` until it
  holds there and on the test half once.

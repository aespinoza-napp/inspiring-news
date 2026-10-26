# Roadmap

The plan, and what is true of it **today**. Every checkbox below was checked
against the code, not against the plan. `[x]` means done *and* working as
described; anything less is `[ ]` with a note saying exactly how far it got.

- **Oct 26 (trends, branch `feature/trends`, `docs/decisions/trends.md`, the author's request; 76h added on top of the 900, free tools only):** a **Trending lens on `/discover`**: Google Trends (Spain, US), r/UpliftingNews' top of the day, Upworthy, Know Your Meme and a hashtag or link a person types, read as public feeds with no key - TikTok itself is never scraped (its listing answered 40101 "no permission"; its terms forbid it). A trend's articles go through the same filters (betting sites added by domain), the unchanged mission screen and the ranking with virality in reliability's place; the AI selection is told the list is trending. Live round: 53 trends, 92 articles, 39 candidates in 13.4 s. **`internet_culture` measured and not adopted** (480 labelled candidates re-screened; Culture's group-fit AUC -0.023, 13 other groups' stories pulled in). **Five trend rounds labelled blind (RQ1): day 1** - 12 of the first 20 worth offering, 5 clearly positive, all 12 found by no topic round that day; r/UpliftingNews 9 of 10, Google Trends 1 of 4. **The positive angle, found never invented**: proposed by the writer model, kept only when the fact-check finds it TRUE from 2 other domains; live, 131 s for 3 angles on a microplastics story, one kept on weak ground (Wikipedia and a dictionary page). Drafts carry the trend; the review checks an angle's citations; a published story shows the TikTok video only after a click (0 connections to TikTok before it, checked). Thesis sections written; 153 pages.
- **Oct 22, afternoon (the verifier, `data/evaluation/experiments/verifier/`, `docs/decisions/evaluation.md` "The verifier's FALSE"):** the 3B answered FALSE to 21-24 of the 45 true train claims, mostly for want of a detail. Runs now keep their evidence and `cli run --replay` judges it again (the same pipeline searched twice moved 6-9 points; replayed, the 3B gave 10 of 10 identical verdicts). Rules written first. Stated rules (`verifier_rules=stated`): -8.7 points [-17.4, 0.0], not adopted. **One source at a time, the side more outlets take (`verifier_answer=per_source`), adopted as the default**: test half 51.4 -> 55.7% (+4.3 [-8.6, +17.1]), right when it commits +13.9 [+0.3, +27.3], confidently wrong 47 -> 29%, natural claims 49 -> 67%, a claim 63 -> 44 s - but claims with one altered detail 60 -> 13%, and kappa 0.14 -> 0.06. A PDF's raw bytes had been an evidence page (167 million characters): the fetcher refuses files now. Running: `qwen3.5:9b` on the same train evidence.
- **Oct 22 (the 20-second fact-check, branch `perf/fast-fact-check`, `docs/decisions/performance.md`):** every claim's time now shows in the app per query, page, stage and model call (`TimingBreakdown` on `/live` and `/`; the harness keeps `search`, `pages`, `llmWait`, `llmCall`). Speed switches per run (`verifier_answer`, `evidence_prerank`, `ranking_text`, `fetch_evidence_pages`) and a claim deadline (`claim_deadline_seconds`: out of time is "not checked"), chosen together by `FACT_CHECK_PROFILE`. A contest on the first ten train claims, rule written first (`experiments/speed/`): a claim 57.2 s at the median with the defaults, 39.3 compact answer, **17.8 fast, 14.2 on snippets**; 2-3 of 10 right in every setup; **Claude by hand 13.1 s, 7 of 10**. On all 69 train claims, the same day: thorough 50.7% [39.1, 62.3] (~60 s a claim), D (snippets) 33.3% at 14.2 s (**-17.4 points [-30.4, -4.3]**), C (fast) 33.8% at 16.7 s (-16.2 [-27.9, -4.4]): the fast profiles are measurably less accurate, so by the rule the app stays `thorough` and the trade-off is one line in `backend/.env`. Which part costs the points is the next run (the compact answer alone, then five sources at 700). `backend/.env` had the verifier on the 8B `llama3.1`: now `llama3.2:3b` with the CPU limits. Every change to fact-checking since July: `docs/fact-checking-changes.md`.
- **Oct 21 (performance, `docs/decisions/performance.md`):** where the time goes, measured on the dev laptop: the model is three quarters of a claim, and of a call most is *reading the prompt* (49 tok/s on this CPU). **The verifier reads the passages about the claim** (`verifier_excerpt=passages`, 700 characters a source) instead of each page's first 1,500: on the train half's oracle, same pages, same day, accuracy +4.4 points [-4.4, +13.2], prompt -29.5% a call, a call 29.9 → 22.8 s, a claim 58.4 → 44.0 s (`08bcab0248c3` against `1e045c3dea31`). Its answer capped at 1,024 tokens and an answer cut at a cap no longer retried (one call had looped to the timeout twice). `inference/` batches embeddings by length (the 163 topic keywords 17.9 → 4.4 s, a claim's snippets 12.6 → 6.5 s, same vectors). The rewrite loop skips a correction the next round replaces. Dev laptop: Ollama's default threads halve its answer speed (`num_thread` 10: 6 → 13 tok/s), and its integrated GPU reads prompts ~3x faster - the verifier's call 64 → 22 s - but crashes the Qwen 3.5 models at the default batch (`num_batch` 128); `scripts/ollama_igpu.sh` turns it on (sudo, not applied). Evidence pages are parsed one at a time (eight threads parsing at once thrashed the GIL: 200 real pages 58.4 → 41.5 s, the slowest 39.6 → 16.8 s) and fetched once per process and hour. The review's correction as edits was tried and left off: half the time on a seeded draft, 65% more tokens on one the writer wrote. Claude verifying the same 8 test claims by hand took ~14 s a claim with 1.1 searches against the pipeline's 434 s, at 4 of 8 right against 5 (`last_chat.txt`). **Proposed, not done:** a GPU or hosted endpoint for production's model (~20 articles an hour is the CPU VM's ceiling whatever else changes), a base URL per role, fewer claims per article, stopping retrieval early when the first query settles a claim.
- **Oct 19 (the author's four goals):** the custom set **split 50/50** and frozen (69 train / 70 test; grouped by article, stratified by verdict x language and topic group; `split.json`), P0.4 done. The blind 20% re-label now a fifth of the test half (14 facts), and the same 14 **run twice through the pipeline**: 13 of 14 verdicts the same, kappa 0.84 [0.44, 1], the one change the web's. **The second look** (a second search for a verdict in doubt) and **the tuning loop** built; on train it fixed 9 of 38 disagreements, found 8 retrieval misses and 15 claims for a person, and its trigger gained +2.9 points [-2.9, +8.7] - left off; on test +0.0. **The test half, first pass: 52.9% [41.4, 64.3]; natural claims kappa -0.013**, the 3B model's FALSE lean. Writer models: Qwen3.5 4B/9B pulled and tried with thinking off per model (`LLM_REASONING_EFFORT`): both cite every sentence and state neither withheld claim (llama3.2:3b: no citation, 3 of 4); **`qwen3.5:4b` recommended** - ~3 min a draft on the CPU, 3.7 GB, the better Catalan (the 9B wrote "litigi" for *liti*); one model in Ollama at a time in production, every configured model pulled before the backend starts, `scripts/stack.sh` per activity on the dev machine. This machine has no GPU: every LLM call 40-75 s.
- **Oct 19, afternoon (models by measurement, response time, the hours):** each role's model tried, each alone on the CPU, by a rule written before any result (`evaluation.md`, "Choosing the models"). **Verifier: `llama3.2:3b` stays.** On the train half `qwen3.5:4b` (thinking off) scored 30.4% to its 44.9% with its own search and 34.8% to 55.1% on the annotator's own pages (`run --oracle`, new: the same evidence for every model; -20.3 [-34.8, -5.8]), slower too; two runs of the 3B differ by -2.9 [-10.1, +4.3] (87% the same verdict), the noise floor. `qwen3.5:9b` on the same pages was as accurate (+1.4) and far more careful - right on 72.9% of the verdicts it committed to against 55.6% (+17.4 [+2.7, +32.0]), FALSE to 6 true claims against 14 - at three times the time: **the rule keeps the 3B; whether a wrong verdict costs more than an honest UNVERIFIED is the author's call**, and the 9B with its own search the run that would settle it. **Writer: `qwen3.5:4b`** (the morning's trial). **Reviewer: `qwen3.5:9b`** - all 10 planted defects of the seeded drafts and every metric parsed, against 6 and 5 for the 4B and the 3B (`scripts/try_reviewer_model.py`), ~3.5 min a review. **Response time** is now a metric of every report (each stage's median, p90 and share; `/evaluation` shows the seconds a claim took): the 3B alone, a claim 73 s, 77% of it the model. Found on the way: the corrector read only top-level JSON, and `qwen3.5:4b` nests each metric inside the one before (`WRITING_VERSION` 2); the production pull script now serves the reviewer at 16k too (`CORRECTOR_LLM_BASE`). **Hours rebalanced** (below): the reader 10 -> 30h, the paper 35 -> 55h.
- **Oct 16, afternoon (performance):** measured on the dev CPU, `docs/decisions/inference.md` §"Where the CPU time went": bge-m3 now encodes one text at a time (`EMBEDDING_BATCH_SIZE=1`; the ranker's 8-page request 9.4 → 6.8 s, 7.3 → 4.2 s with real lengths, same vectors); enrichment embeds the article once (the topic classifier re-embedded it); the claim extractor's 37 entity requests per article are one (2.7 → 1.5 s, same claims); the corpus search reuses the retriever's claim vector; sightings are not rewritten when nothing is new. **Fixed, an error:** GLiNER truncated a whole article to its first 384 tokens (5 entities found where its sentences hold 52); long texts are now read in sentence chunks. Enrichment of a 5,700-character article 17.2 → 14.1 s while reading all of it. 1,760 backend tests pass with `inference/` up.
- **Oct 15 (outside the freeze, the author's decision):** the writing flow - write a new article from a publishable one (related news, its sources and fact-checks, closed world, Catalan/Spanish/English), review it on nine grounded metrics, rewrite it towards targets, publish it to the reader with the AI disclosed. `docs/decisions/writing.md`. `llama3.2:3b` measured unfit as writer (no citation in 4 of 4 drafts, an `UNVERIFIED` claim stated as fact in 3); a larger openly licensed model recommended, not measured. P1.3's evaluation (FActScore, ALCE) is not done.
- **Oct 16 (audit, `docs/audit-2026-10-16.md`):** the thesis compiles for the first time (MiKTeX; every `tabularx` had failed on a `colortbl`/`array` mismatch), 135 pages, 60 of its 88 placeholders written from the repo's own records and 28 left, each naming the run or the fact it waits for; the results chapter follows the four RQs; bibliography 12 → 43. Fixed: 8 AI-labelled facts (fact094-107) without their `[AI label:` prefix, counted as human by `/evaluation`; production's inference limits (`INFERENCE_TIMEOUT=120`, `CLAIM_MAX_CONCURRENCY=2`, the pilot's finding); stale counts in the thesis (37 sources, 33 enabled) and in `evaluation.md`'s RQ table. Full check passes.
- **As of:** 2026-10-14 — **feature freeze; the thesis priorities below replace the calendar where they disagree.** Oct 14: the custom set cut to its domain (39 off-mission facts to `excluded/`, 109 left), the labelling batch leaves out articles with no topic of ours. Before that, 2026-10-06 — week 2 of Sprint 4 (development) and of the validation set (evaluation), run side by side. Oct 5 added discovery by topic, the selection step, the newsroom flow, and an 18h block of experiments on the stages before the verdict (Phase 4, not yet funded). Oct 6 kept discovery to the mission (an age limit, a mission screen), disabled EFE and Reuters, and ranked a round's candidates (twenty shown, forty on request).
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

- **Rebalanced on Oct 19**, still 900h, the author's request ("add some
  hours to the reader and rebalance"). The build-status page has carried
  the budget since Oct 6 (evaluation 153h, the reader 10h after its four
  tasks were built early); this rebalance is made on that budget:

  | Bucket | Before | After | Why |
  |---|---:|---:|---|
  | Phase 6 · Reader view | 10 | 30 | +20, the author's decision: the reader in Catalan and Spanish (8), stories and checked articles in one feed with RSS and a sitemap (4), a reader's guide to the verdicts (2), an accessibility pass (3), five readers trying it (3). **Reverses the Oct 14 cut of "any further reader-view work".** |
  | Phase 7 · Paper | 35 | 55 | +20, a new block Nov 17 – Dec 10: reading, owning and revising the 145 drafted pages before the draft goes to the director |
  | Phase 5 · Sprint 7, verification models | 60 | 35 | -25: harness, split, second look and consistency built; the first model comparison ran Oct 19. Left: the test half, P0.5's three evidence conditions (10h, now a task here), one hosted model |
  | Phase 5 · Sprint 6, writing models | 20 | 10 | -10: writer and reviewer tried Oct 19; left: one hosted provider |
  | Phase 4 · Validation set | 60 | 55 | -5: the blind re-label is 14 facts (a fifth of the test half), 7h -> 2h |
  | **Total** | **900** | **900** | |

  From Oct 20, 233h remain planned: development 35 (infrastructure 15,
  reader 20), evaluation 60, model testing 39, paper 55, testing 44.

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

## Thesis priorities (Oct 14 – Dec 31)

Set on Oct 14, when the thesis was still without a result on the question
it asks: 109 facts, 78 of them labelled by the AI pass and none checked,
no FALSE claim, the research questions unfixed, and about a third of the
document written - most of it on scraping. **Feature freeze from today:**
nothing new is built unless an item below needs it. The phases further
down keep their history; where their dates disagree with this list, this
list wins. Deadline: a full draft to the director by ~Dec 10 (check
FIB's deposit date and the director's reading time), the last weeks for
corrections.

**The thesis, in one sentence:** an end-to-end pipeline that reads news,
treats and transforms it (acquisition, extraction cascade, three-layer
lake, enrichment), finds and ranks what is worth publishing on the
topics asked for, and verifies its claims on the open web - evaluated
stage by stage, against a person wherever a person takes the same
decision. The pipeline is the artefact; the evaluation is the
contribution.

**Research questions - fixed by the author on Oct 14** (thesis §1.5,
metrics in §6.1; they replace the proposal this section first carried):

- **RQ1 - finding.** Can a retriever that reads the open web, scoped to
  a chosen set of topics, simplify a journalist's task of finding
  constructive news on those topics? *(discovery and the ranked round:
  sources and links read against the every-topic baseline, precision of
  the first k, AUC of the score)*
- **RQ2 - verifying.** Can the claims of the news it retrieves be
  verified by the pipeline built here, and how can that be quantified?
  *(accuracy, macro-F1, kappa against the gold set, natural and
  synthetic apart; closed-book / retrieved / oracle evidence; evidence
  recall; stage attribution)*
- **RQ3 - person and model.** Given the same news and evidence, how close
  does an LLM come to a person, choosing what to publish and deciding
  whether a claim is supported? *(kappa: editor vs AI selection, blind
  rounds; annotator vs the AI labelling pass; annotator vs the pipeline;
  the annotator's own re-label as the ceiling)*. The author's sentence
  was cut off after "after getting the"; "the same news and evidence"
  completes it and is to be confirmed.
- **RQ4 - the system.** Joined, to what extent can it take over a
  journalist's work - finding, selecting, verifying - and where is a
  person still needed? *(asked as extent, since "replace" is not
  measurable: claim-selector precision, 0.64 over 214 proposals;
  coverage and selective accuracy; time per article)*

Writing news from sources (P1.3 below) answers none of the four: it
moves to P2, and the conclusions name it as future work if it is not
built.

### P0 - without these there is no thesis

1. [x] ❓ **Fix the RQs and their metrics** in §1.5 and §6.1 · 3h · Oct 14 -
   the author's four questions, written up with a metric table; the
   AI-assisted labelling disclosed in §6.3's annotation procedure.
2. [ ] 🏷️ **Human-adjudicate the gold set** · 10h · by Oct 31 - check every
   AI label in `manual/` (78), keep or change it, and **report agreement
   between the AI pass and the annotator** (Cohen's kappa): a gold set an
   LLM labelled, used to judge an LLM, is the first thing a committee
   attacks; measured, it is a finding. From now on the annotator labels
   a batch first and the AI second, so each new fact adds to that number.
   Then the blind 20% re-label (Oct 26-28 rule: a week later) - that is
   *intra*-annotator agreement and is named so; a second person on ~30
   facts would give inter-annotator agreement.
3. [x] ❌ **A FALSE class** · 6h · Oct 14 - 30 synthetic FALSE facts
   (fact149-178), six per group, 9 in Spanish, each a substitution of
   what a TRUE fact's claim asserts (12 number, 8 date, 6 entity, 4
   relation), with its source's article, date and evidence: FEVER's
   mutation (Thorne et al. 2018) and SciFact's refuted claims (Wadden et
   al. 2020), without negation, which let a claim-only model guess
   FEVER's labels (Schuster et al. 2019). The labeller records
   `mutatedFrom` / `mutation`, refuses a source that is not a natural
   TRUE, keeps the provenance through form edits, and lists mutations
   whose source is relabelled (`staleMutations`); `python labeller/app.py
   mutate factNNN --kind ... --claim ...` makes one. Every harness record
   carries `origin` (natural / mutated) and every report breaks down by
   it. Thesis §6.3 "Synthetic Refuted Claims". **Proposed by the AI
   pass: part of P0.2's review.** Set: 139 - 91 TRUE, 30 FALSE, 10
   UNVERIFIED, 7 PARTIALLY_TRUE, 1 MISLEADING.
4. [x] ✂️ **Freeze a tuning/test split before any run** · 1h · Oct 19 -
   **50/50, not ~1/3-2/3: the author's decision** (the pipeline learns
   nothing from the facts; the tuning half needs disagreements to
   decide on). `python labeller/app.py split`: grouped by article (a
   synthetic FALSE with its source), stratified by verdict x language
   and by topic group (the first draw, on verdict x language alone, put
   all 21 culture facts in test), ties by hash, frozen in
   `split.json`: 69 train / 70 test. The blind re-label sample is now a
   fifth of the test half, 14 facts, run through the pipeline twice too
   (`cli consistency`). Harness: `--split`, `--sample recheck`.
   `docs/decisions/evaluation.md`, "The split"; thesis §6.3.
4b. [x] 🔁 **The second look and its tuning loop** · Oct 19 (outside the
   freeze, the author's request) - a second, wider search for a verdict
   in doubt (`second_look.py`, off by default), decided on the train
   half by `run --loop` (second look on every disagreement, then the
   annotator's own pages: `fixed` / `retrieval` / `adjudicate` /
   `reasoning`), measured on the test half. Built, tested and run
   (Oct 19): +2.9 points [-2.9, +8.7] on train, +0.0 on test - **off by
   default**. The 15 `adjudicate` claims feed P0.2; the 8 `retrieval`
   ones say where search misses; the loop's diagnosis points at the 3B
   verifier, not the search (`evaluation.md`, "The second look").
5. [ ] 🧪 **The RQ1 runs on the test split** · 10h · Nov 1-15 - three
   conditions, one model: no evidence (closed-book), the pipeline's own
   retrieval, and **oracle evidence** (the annotator's reference links
   given to the verifier directly, no search). The first gap is what
   retrieval adds; the second, what better retrieval could still add -
   the standard way to put a number on a retriever (FEVER's and
   AVeriTeC's gold-evidence conditions). The oracle mode is new (~3h of
   the 10): `check_claim` with a fixed evidence list - and the same mode
   is what P1.3 evaluates writing with. **Oct 20: all three are harness
   modes** - `run --oracle` (Oct 19) and now `run --closed-book`
   (`src/evaluation/closed_book.py`, the probe's prompt moved into the
   harness), so the three conditions pair claim by claim in
   `cli report --compare` and `cli table`. 8 tests. **Oct 20, the runs
   started** (from the host, against the host's Ollama, `llama3.2:3b`;
   the 19 Oct runs' `results.jsonl` went with the backend's emptied
   volume, so the full run is made again too): **closed-book
   `038bea7a04be`: 34.3% [22.9, 45.7]**, macro-F1 0.156, kappa 0.036
   [-0.087, 0.162]; natural 27.3%, synthetic FALSE 60%; FALSE to 40 of 70;
   remembered a published fact-check for 1. **Oracle `63ec8ea70a6c`:
   54.3% [42.9, 65.7]**, macro-F1 0.306, kappa 0.259 [0.093, 0.421];
   natural 52.7%; paired against closed-book **+20.0 points [+5.7,
   +34.3]** (22 claims only the oracle right, 8 only closed-book). The
   full run `2605a2c02380` (8 of 70; its harness segfaulted once while
   fetching pages, exit 139, as in the pilot) is resumable: rerun the
   same command (`docs/goals.md`, U3). This CPU gives llama.cpp 2 threads
   and a claim ~3.5 min (`deployment.md`, "Threads on a hybrid CPU").
6. [ ] 🟡 🧭 **Stage attribution (RQ2)** · 5h · Nov 1-15 - already planned in
   Phase 4; every wrong verdict to retrieval / ranking / reasoning /
   aggregation, from the trace. **Oct 20: built** - `src/evaluation/
   attribution.py`, a "Stage attribution" section in every `cli report`,
   both columns (by reference, trace only) with counts, shares, ids, the
   ranking bucket's cut reasons and the claims the columns disagree on;
   aggregation tested first (the model's own verdict was gold), an
   oracle run without the reference column. 13 tests on fixture records
   (`tests/evaluation/test_attribution.py`); `./scripts/check.sh` passes.
   **Left:** `cli report` over the train, test and oracle runs, whose
   `results.jsonl` are not in git and not on this machine, and the table
   into the thesis.
7. [ ] ✍️ **Write, starting this week, beside everything else** · ~140h -
   state of the art 25h (8 references today; 40+ needed - automated
   fact-checking, retrieval evaluation, LLM verifiers, grounded
   generation, constructive journalism); proposed method 20h (on Guo et
   al. 2022's four-stage architecture: claim detection, evidence
   retrieval, verdict prediction, justification); development 20h
   (scraping cut from 6.7k words to ~2k, the rest to an appendix);
   experimental design 10h; results 20h; discussion and threats to
   validity 10h; introduction, conclusions, abstract 10h; sustainability
   and ethics 8h (required by FIB); revision 15h.

### P1 - what makes it a good thesis

1. [ ] 🟡 🔎 **Retrieval as an ablation, not as a version history** · 12h ·
   by Nov 22 - the versions in git cannot be re-run on today's web, and
   a changelog is not a measurement; switching each component off on the
   same frozen claims, in one window, is. Needs one switch that does not
   exist yet (which query kinds `plan_queries` sends: anchor only, +
   proposition, + refutation; the pertinence gate is already per run).
   Run `--retrieval-only` per variant; report recall of the annotator's
   links and domains at candidates / ranked / cited and MRR (built, G4),
   and **pooled relevance judgements** (TREC's method: pool every
   variant's top 5, judge each document once, score every variant on the
   same judgements - reusable for any later variant). Searches are not
   reproducible: interleave the variants on the same days and report
   `searchUnavailable` apart.
   **Oct 20: the switch is built** - `query_kinds`, a per-run threshold
   (anchor / proposition / refutation, any non-empty subset; a typo is
   refused), sent by the search and announced by the live view alike;
   variants as `data/evaluation/thresholds/queries_anchor.json` and
   `queries_anchor_proposition.json`. Runs made before it keep their
   keys (`keyed_thresholds`). 11 tests (`tests/services/fact_checker/
   retrieval/test_query_kinds.py`, the run key in `test_harness_runner.py`).
   **Oct 20, later: the pooled relevance judgements are built too** -
   `cli pool` (every variant's top 5 per claim, each page once, earlier
   judgements kept), `cli judge` (a person, page by page, in the
   terminal) and `cli pooled` (precision@5, recall of the pool's
   relevant, MRR and judged coverage per run, paired against the first);
   8 tests. **Oct 20, first ablation run** on the test half (70 claims,
   three variants in one window, `reports/manual-test/retrieval.md`):
   anchor only loses a reference domain among the candidates for 18.8
   pts of claims [−29.0, −10.1]; adding the proposition recovers nearly
   all of it; the refutation query adds no measurable gain on a set with
   no natural FALSE claim, for 2.7 s a claim. 603 pages pooled
   (`data/evaluation/judgements/manual-test.jsonl`). **Left:** judging the
   pool, repeat windows on other days, and the table into the thesis.

2. [ ] 🟡 🕰️ **How new is too new: evidence against the age of the claim** ·
   6h, spread - start this week, it needs calendar time. Re-run
   retrieval-only on the same recent claims at day 0, 7 and 30 and plot
   the evidence rate against age; add, from the set itself, the gap
   between each claim and its earliest evidence (`claimDate` -
   `evidenceDate`). Puts a number on "news that is new" (FreshQA, Vu et
   al. 2024; RealTime QA, Kasai et al. 2023), and on Rule 1's cases: a
   new study often has only its own press release on day 0.
   **Oct 20: the set's half is built and measured** - `cli freshness`
   (`src/evaluation/freshness.py`): the newest evidence's age at each
   claim (`evidenceDate` is the newest the annotator used, not the
   earliest), and, joined to any run by id, verdicts by that age and by
   the claim's age when checked. On the 103 natural dated facts: median
   22 days, 14.6% same day, 27.2% 1-7 days, 25.2% over a year
   (`reports/manual/freshness.md`); 74 of the 103 dates are the AI
   pass's. 15 tests. **Left:** the day 0 / 7 / 30 retrieval-only re-runs
   (live), and `--run` over the existing runs where they are.

3. [ ] ✍️ **Writing from verified sources, closed-world** · 35h - **moved
   to P2 on Oct 14**: none of the author's four RQs asks it. Kept here
   for its design; build it only if every P0 and P1 item is done. The same story from 2-3 outlets (the ranking already
   groups them) → a short constructive piece citing its sources → its
   claims by the pipeline's own `ClaimExtractor` → each verified against
   the given sources only, with P0.5's oracle mode (no web: no search
   noise). Supported-claim rate (FActScore, Min et al. 2023), citation
   precision and recall (ALCE, Gao et al. 2023), and a hand check of 20.
   The pipeline's verifier becomes the evaluator of its own writer -
   validated by that hand check, not assumed.
4. [ ] 🤖 **Two more verifier models** on the test split · 15h · Nov 22 - Dec
   5 - a local 8B and one hosted; `cli table`. Replaces Sprint 7's
   broader plan. **Oct 19, the local half done early, on the train half**
   (the split exists, so models are chosen there and only the chosen one
   is reported on test): `qwen3.5:4b` and `qwen3.5:9b` against
   `llama3.2:3b`, with each one's search and on the annotator's own
   pages; the 3B stays by the rule, the 9B more careful at three times
   the time. Left: a hosted model, and the 9B with its own search if the
   author weighs a wrong verdict above an unverified one.
5. [ ] 🗳️ **Person against model in selection (RQ3)** · 5h · Oct 20 - Nov 15
   - ten blind rounds (choose and send, then `blind-ai --round <id>`) and
   ten assisted ones; precision, recall, Jaccard, the AI score's AUC.
   Was in P2; RQ3 needs it.
6. [ ] 🔎 **The discovery numbers (RQ1)** · 5h · by Nov 15 - `discovery`
   per group on five days against the every-topic baseline, and the
   ranking's precision of the first 20 and AUC on hand-labelled rounds
   (the Oct 9 rounds' labels were the AI's: the person labels at least
   two rounds). Was in P2's pre-verdict experiments; RQ1 needs it.

### P2 - only if time is left

- Tune `RANKING_*`, `CONFIDENCE_*`, `EVIDENCE_MIN_PERTINENCE` on the
  tuning split.
- The other pre-verdict experiments (weekly source health, admission
  thresholds); discovery and the blind selection rounds moved to P1.
- The writing-model benchmark on the corrector's metrics (Sprint 6), and
  writing from verified sources (P1.3).

### Cut, or future work

The real Google Cloud deploy (it stays "designed and applied to an
emulator"); reader-view work beyond the five tasks the Oct 19 rebalance funded; Neo4j at scale;
`JobStore` eviction, cache expiry and URL normalisation unless one blocks
a run; new discovery or selection features; frontend E2E tests; the
topic classifier. Each is listed in the conclusions as future work, not
left as an open checkbox.

| Weeks | P0 | P1 | Writing |
|---|---|---|---|
| Oct 14-19 | RQs, split | freshness day 0 | state of the art |
| Oct 20-31 | adjudication, FALSE set | freshness day 7 | state of the art, method |
| Nov 1-15 | RQ1 runs, stage attribution | ablation switch, freshness day 30 | experimental design, development |
| Nov 16-30 | - | ablation runs, models; blind rounds and discovery numbers finished | results |
| Dec 1-10 | - | - | discussion, threats, intro, conclusions, ethics: **draft to director** |
| Dec 11-31 | fixes the review asks for | - | revision, figures, slides |

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
- [x] 🏷️ **Labelling tool for the custom validation set.** `labeller/`: one Python file and one HTML page, standard library only - `python labeller/app.py`, nothing to install, no backend or Docker needed. Each fact is its own file, `backend/data/evaluation/manual/factNNN.json`, so every hand-verified fact is visible in the repo; `python labeller/app.py join` merges them into `custom_en_es.jsonl` when the set is done. Rows are x-fact's exact format (same keys, same order, `split: test`) plus `topic`, `claimType`, `sourceTier`, `onlyOwnSource`, `evidenceDate` and a note. The four tie-break rules are fixed before labelling, and the checkable ones are enforced on save (own source only → `UNVERIFIED`; evidence newer than the article refused). A verdict × topic-group table steers toward 150 facts (25 cells of 6). The Review tab labels a hash-chosen 20% again, blind, and reports agreement and Cohen's kappa on the first label. `./scripts/check.sh labeller` runs its tests. Written up in `docs/final_document/chapters/06-experimental-design/03-custom-validation-set/`. No facts yet: labelling is Sprint 3's 40h.
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
- [x] ⚖️ The article verdict is "worst claim wins", so a single `UNVERIFIED` (the common outcome with a small local model) outweighs any number of `TRUE`; `overall_confidence` averages confidences of different verdicts. Separate "how much could be checked" from "what was found". — **Oct 20, at the user's request:** added, not replaced. `factCheck` carries `foundVerdict` (the worst among claims with a definitive verdict, null when none) and `claimsJudged` / `claimsUnverified` / `claimsNotChecked` (search or model failed); `overallVerdict` keeps its meaning, since the reader's admission and the thesis's numbers rest on it. Cache schema 13; shown on the Analyze page. 4 tests. `overall_confidence` still averages across verdicts.
- [x] 🗑️ `JobStore` keeps every job in memory forever (now safe to evict, since the journal has them) — **Oct 20, at the user's request (it was on the Oct 14 cut list):** with a journal attached, finished jobs past `JOB_STORE_KEEP_FINISHED` (200) leave memory, oldest first, journalled ones only, and still answer by id from the journal; active jobs never. 4 tests.
- [x] ⏳ The analysis cache never expires, and it also caches rejections; fact-check verdicts depend on today's web — **Oct 20 (same):** entries carry `cachedAt` and expire after `ANALYSIS_CACHE_TTL_HOURS` (a week; 0 keeps the old behaviour), rejections included; an unstamped entry counts as expired. No shape change, so no schema bump. 4 tests.
- [x] 🔗 URLs are compared as plain strings, so `?utm_source=` variants and trailing slashes count as different articles — **Oct 20 (same):** the job store's in-flight dedupe, the analysis cache key and the vector store use host and path (`comparable_url`, as ingestion and the reader already did). The vector store's was a correctness bug: an earlier copy saved under a tracking parameter was not excluded from its own article's evidence. Points carry `url_key`; old points are still matched by exact URL. Assumes no source names articles by query string (none of the 37 does). 5 tests; the cache's keys changed, so existing entries miss once.
- [x] 🕸️ Neo4j is a hard start-up dependency of the backend container (`depends_on: service_healthy`), although since Sep 29 the graph write is fail-soft and the backend runs without it — **Oct 20 (same):** removed from the backend's `depends_on`; a full `up` still starts it, `up backend` no longer drags it in. A deployment test holds it; the dev, prod and eval compose files validate.

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

- [x] 🔎 **Fix the search before any benchmark · 10h** — an engine with an API key (Brave Search API or Google Programmable Search), which is not rate-limited per IP like the scraped engines, and a **"search unavailable" state** apart from `UNVERIFIED`, as `llm_unreachable` already is for the LLM. Without both, a benchmark measures SearXNG's uptime: on Sep 25, 68 of 69 queries came back empty and every affected claim looked like an honest `UNVERIFIED`. **Sep 30: the state is done** — `searchUnavailable` on every claim (cache v10, graph), set when every query of a claim failed; the trace stops at `evidence_retrieval` and says the web was never asked (`docs/decisions/retrieval.md`). The analyzer's stage timeline shows that note, so the UI already tells the two apart; there is no dedicated badge, as there is none for `llmUnreachable`. **Also Sep 30: a keyless second route** - a query SearXNG cannot answer is sent to DuckDuckGo's HTML page directly (`src/services/duckduckgo.py`), and a claim is `searchUnavailable` only when both fail. Measured the same day, DuckDuckGo challenged every keyless request from this machine (3 of 3): the client recognises the challenge and pauses 5 minutes, and recovers evidence only where DuckDuckGo lets the IP through. **The API-keyed engine (Brave Search API) is future work** (`docs/final_document/chapters/09-conclusions/04-future-work/`): no paid APIs or credentials for now.

- ↪️ Improve claim selection heuristics — the structural half is done; tuning its thresholds moved to Phase 4 (Nov 10–16), Sep 30.
- [x] 🌐 Alternative evidence retrieval strategies — SearXNG queries are now a planned set (anchor / proposition / refutation) fused by reciprocal rank, and off-target sources are cut by the pertinence gate (`docs/decisions/retrieval.md`). Sep 28: four science APIs (arXiv, Crossref, Semantic Scholar, PubMed) and Wikipedia answer through SearXNG beside the web engines, and still answer when those are rate-limited; the internal Qdrant corpus now grows from 34 ingested sources. Sep 30: a failed search is reported as `searchUnavailable` (item above), and **the model's own on-point judgement is enforced**: it already marks each source `supports` / `contradicts` / `unrelated`, and a citation of a source it called unrelated no longer counts - a definitive verdict resting only on such sources is `UNVERIFIED`, with a note saying why (cache v11). No extra LLM call. Beside SearXNG, a keyless DuckDuckGo fallback (item above). Future work: an API-keyed engine (`future_work.tex`).
- ↪️ Tune `RANKING_*`, `CONFIDENCE_*` and `EVIDENCE_MIN_PERTINENCE` with real data — moved to Phase 4 (Nov 10–16), Sep 30.
- [ ] 🟡 🏷️ Improve topic classifier accuracy — **de-scoped on Sep 29 to "only if time"**: on no research question's path (topics steer admission and balance, not verdicts). Keyword coverage was widened from misclassified real articles; there is no labelled set to measure accuracy on. The labelling batch's wrong topic guesses are a free sample of its errors.
- [x] 🧪 Regression tests for new ranking/confidence behavior — ranking (lexical factor, pertinence gate both ways, run-threshold not env) was already covered. Sep 28: confidence golden values and properties (`test_confidence_weights.py`); the frozen class weights are now pinned for the suite (they had been running on the local `.env`); weight groups that do not sum to 1.0 refuse to start - the committed `.env-example` had ranking at 1.2. Still not *measured*: that is the tuning item above.
- [x] 🎯 **Discovery by topic group** (not in the original plan, Oct 5) — pick up to 3 of the 5 groups (society, science, environment, culture, health); only the sources whose YAML names one are read, and only for those groups' topics. One backend definition of the groups (`src/config/topics.py`), a `groups:` list in every source YAML (each group has an English and a Spanish source, held by a test). Discovery now drops off-mission sections (sport, celebrity, horoscopes, lotteries, weather), links filed under a topic not asked for unless they mention one that was, section-page navigation, and - when scoped - Spanish items without a topic word in their title (`TOPIC_KEYWORDS_ES`). Live, Oct 5: Environment read 14 of 34 sources and 10% of the baseline's links; El País kept 18 of 159 items instead of all, election coverage gone. `docs/decisions/selection.md`
- [x] 🗳️ **Choose up to 20 before analysing, by a person or the AI** (not in the original plan, Oct 5) — a candidate round lists what was found with its feed title and summary; the AI selection (LLM over titles and summaries, ten per call, in the background) scores each 0-10 for positive impact with a reason and ticks its picks; the editor keeps or changes them; only those become analysis jobs. Every round is recorded (`lake/stats/selection/`) with who chose and how far the AI's proposal was kept. Live on llama3.1: 26 candidates, 3 calls, 167 s, every election story and the comedy-photo awards at 0. Its own timeout (`AI_SELECTION_TIMEOUT`): the dev `LLM_TIMEOUT` failed every selection. `POST /ingest/rounds/*`, `src/services/selection/`
- [x] 🧭 **One newsroom flow in the frontend** (not in the original plan, Oct 5) — the nav in two groups, newsroom (Discover → Analyze → Live → Reader, with a step bar on each) and lab (the per-stage tools); a `/discover` page for the two items above, its round in the URL so a reload resumes; the Scraper page's one-shot ingest panel removed in its favour; one `safeHref` instead of three copies.
- [x] 🧹 **Discovery keeps to the mission** (not in the original plan, Oct 6) — a Culture round had listed election polls, a 2022 tanker crash and celebrity interviews. Now: items older than 30 days are not offered (a feed with nothing newer falls through to section pages: RTVE's has been frozen since June 2022); a section page keeps only its own section's links when it has any (ABC's `/cultura/` listed `/espana/` election pieces); `/icon/` and `/sucesos/` are off-mission; and a **mission screen** leaves out, before the per-source cap, candidates whose title and summary are nearer politics, crime, disasters, war, celebrity, sport or service pages than any topic (bge-m3). Measured on 527 live candidates: 68 of the 484 from general outlets left out at margin 0.04, nearly all clear cases; the sentiment model rated solved problems as negative and was not used. Outlets with `positive_editorial` skip it; what was left out is listed on `/discover`; with `inference/` down nothing is left out and the round says so. Widened the same day after a Science and Society round: strikes and protests, markets and personal finance, politics held to no margin, death reports by headline (en/es), and links dated by their path, live coverage, opinion and index pages dropped - 59 left out instead of 34 on the same feeds. What it cannot tell apart, the front pages' housing policy from good news, is the AI selection's. **EFE and Reuters disabled**: no answer in two weeks (403 / 401); they still rate evidence. `docs/decisions/selection.md`
- [x] 🏅 **Candidates ranked, twenty shown** (not in the original plan, Oct 6) — a round's 60-80 candidates were read in the order the sources are named. Each is now scored from its own title and summary (nearer positive impact than anything off-mission, 0.6), its source's record in the round's screen (0.25) and the source's reliability rating (0.15); the best 20 are shown, 40 on request, the rest kept ranked in the round. Measured on 117 hand-labelled candidates of the day's five rounds: AUC 0.78 [0.67, 0.87] against 0.65 for the 3B AI selection; a Science and Society round's first twenty went from 8 stories not worth offering to 1. Reliability carries no signal for the mission (0.49) and has the smallest say; freshness pointed the wrong way and was left out. The same story from several outlets is offered once before any story twice (live, the physics Nobel had taken 8 of the first twenty places). `/discover` shows each candidate's place, score and parts, and one sticky toolbar holds Refresh, the AI, the count and Analyse. `docs/decisions/selection.md`, `docs/experiments.md`
- [x] 🧭 **Rounds aligned with the mission and the groups** (not in the original plan, Oct 9) — measured on five live one-group rounds and 318 hand-labelled candidates (AI labels): of the first twenty of all five, not articles 13 → 0, of another group 21 → 13, not worth offering 29 → 17, clearly positive 34 → 34; Health's not-worth 10 → 3. What changed: pages that are not articles left out (podcasts, roundups, quizzes, galleries, advisories, promotions, shopping, branded content, recipes; 28 of 35 caught, no article), candidates nearer another group's topics listed after the rest and a source's slots given first to what fits (AUC 0.874), markets/service/labour/disaster/celebrity held to margin 0.02, English topic keywords matched as words (85 of 419 matches were substrings like "ai" in "said"), section pages' links titled with their headlines, WHO read from its news API and CNN from its news sitemap (both feeds frozen), a source's own sections (Smithsonian), The Optimist Daily added and Health given to two positive outlets. **Found on the way:** trafilatura's discovery step had not run since Oct 4 (it inherited the feed step's reader, as the topic-page step had); run for real it was worse than section pages, so it is last. **The labelling batch now goes through the same age limit and mission screen** - its own discovery had neither, and the Oct 9 batch drew a radio-awards nominee list, an August phone tip and a media advisory. `/healthz` no longer reports the LLM down for a model named without its `:latest` tag. `docs/experiments.md`, `docs/decisions/selection.md`
- [x] 🎚️ **Positive impact or the topic: the person's call** (not in the original plan, Oct 13) — asked for: looking for a topic, the topic must weigh more. A round's order now takes a topic emphasis, 0 (all positive impact) to 1 (all topic), per round (`topicEmphasis` on `POST /ingest/rounds`, passed per call, recorded with the round) and from a "Positive impact ↔ Topic relevance" control on `/discover`; it splits the story's 0.6 of the score, the source's record and rating keep theirs; with no topic to weigh it does not apply and the round says so. Default 0.6, measured by a new `emphasis` experiment that re-scores every candidate of the Oct 9 rounds (60 reserve candidates labelled for it): over ten rounds the first twenty hold 194 of 200 stories of the group asked for (184 before), the first ten 100 of 100 (94), the group's stories worth offering 150 (154); the cost is clearly positive ones, 62 → 53, replaced by on-topic hard news - the AI selection's to sort, and not told the emphasis by decision. `docs/decisions/selection.md`, `docs/experiments.md`
- [x] 🐛 **Found Oct 9: claims cut at abbreviations and taken from headings** — "...on Monday, Oct." and "15, to preview..." were two claims; a list entry ("Gustavo Sylvestre (Mañana Sylvestre – Radio 10)") and a photo credit were claims. A sentence now has to end ("." "!" "?" and closing quotes): over the labelling batches, claims without end punctuation were labelled 1 time in 6, whole sentences 79 in 116. Months, titles, a.m./p.m. and initials no longer end one. `ClaimExtractor`, which the fact-checker uses too.
- [x] 🐛 **Found Oct 5: topic-page discovery re-read the dead feed** — since Oct 4's feed times, discovery asked every strategy for items, and the topic-page step inherited the RSS strategy's feed reader: National Geographic, Reuters and SINC found nothing for a day. Fixed, with a test that runs the step through `DiscoveryService`.
- [x] ⏱️ Time to reception (not in the original plan, Oct 4) — how long an article takes to reach us after it is published. The RSS strategy now keeps each item's publication time (all 1,248 URLs from 29 live feeds had one), the extractor keeps the page's own `article:published_time` for stored articles (6 of 7 live pages stated it to the second), and ingestion records when it first saw each URL (`lake/stats/sightings.json`). `GET /scraper/freshness` and a Time to reception panel on `/scraper`: per source, hours from publication to first seen, to fetched and to the reader, between precise times only; date-only articles in days, apart. `docs/decisions/scraping.md`. The numbers start with the next ingestion: older lake records have neither time.

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

Done early, Oct 1-2, except what needs a billed Google Cloud project
and a domain (`docs/decisions/deployment.md`):

- [x] ☁️ Choose hosting target — **Google Cloud, one Compute Engine VM** (`e2-standard-4`, 16 GB, Madrid, ~$115/month on demand) running the same compose stack; not Cloud Run (Qdrant's file lock, in-memory jobs, background threads, ~6 GiB of warm models). Sized from measurements: ~9.6 GiB resident across the production stack, the LLM ~45 s per claim on CPU. `deploy/gcp/` (Terraform) creates the VM, its secrets, network, snapshots and alerts, and is applied to **Floci**, a local Google Cloud emulator, by `./scripts/check.sh gcp`.
- [x] 🐳 Production-ready `docker-compose` — `docker-compose.prod.yml`: only the API published (loopback), every secret required, restart policies, log rotation, memory caps from measurements, the LLM as an `ollama` service. A full analysis ran inside the dev stack (75 s) and the production one (184 s). The production run found the dev LLM limits turn CPU verdicts into timeouts (3 of 4 claims); fixed there.
- [x] 🔐 SearXNG for prod — the committed `settings.yml` is mounted read-only (no copy left to drift), the secret comes from `SEARXNG_SECRET`, the image is pinned. The healthcheck no longer sends a real search to every engine every 5 s.
- [x] 🧯 Logging/monitoring — JSON logs (`LOG_FORMAT=json`), `GET /metrics` (Prometheus text: stages, outcomes, verdicts, empty/failed searches), `GET /healthz` (every dependency). On Google Cloud: Ops Agent to Cloud Logging and managed Prometheus, an uptime check and a search-health alert by email.
- [ ] 🚀 First real `terraform apply`, then the search check from the VM's IP, then one analysis there — needs a project with billing. Floci runs no guest, so the VM's boot is unverified until then. The step-by-step runbook (commands, what to check first, what the bootstrap prints) is in `deployment.md`, "The first real deploy, step by step" (Oct 2).
- [ ] 🟡 🌐 Where the frontend runs, and a domain for HTTPS — **on the VM, behind Caddy; not Cloud Run** (Oct 2): it would need the API off loopback and onto the VPC, Cloud Run has no domain mappings in Madrid (a load balancer instead), and it would add a second deploy path for nothing to scale. Built: the frontend image (`docker/frontend.Dockerfile`, standalone, 259 MB, 121 MiB peak) as a `docker-compose.prod.yml` service; the API key on every endpoint but `/healthz`, `/metrics` and job polling (`tests/api/test_api_key.py` asks every route); and, because the frontend's routes attach that key, **a password on the whole site** (Caddy `basic_auth`, generated by Terraform, only its bcrypt hash on the VM), served **only over HTTPS**. `domain` gets Caddy a certificate; without one only `/healthz` is public and the site is behind an IAP tunnel (`terraform output ui_tunnel`). Verified: the image built and ran against a stub API (the key reached it from every proxy tried); the compose service came up healthy; the Caddyfile run with `caddy:2.10.2` in both modes (HTTPS via Caddy's internal CA on `localhost`); `./scripts/check.sh gcp` (32 resources, the rendered hash opens the generated password, empty second plan); `test_deployment_config.py` holds it all. Found on the way: Windows checkouts had the shell scripts as CRLF, which broke the Floci check and would have broken the VM's startup script (`.gitattributes`). **Left:** a domain pointed at `external_ip`, and seeing Caddy obtain a real certificate - both in the first real deploy above.
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
(`docs/final_document/chapters/06-experimental-design/02-evaluation-dataset/`, "Custom Validation
Set") and x-fact cannot replace it: x-fact is political statements, not
the claims of positive-news articles. Gates the tuning below and 3 of
Sprint 7's 6 items.

- [x] 🗓️ **Daily labelling batch** (Sep 29, not in the original plan) — the labeller's **Today** tab asks the backend for ~10 articles, drawn at random (seeded by the day), one per source, languages alternated, never one already labelled or proposed, preferring articles from the last 60 days (to keep the gap between Rule 3's evidence and today's web small) and then topics the balance table is short of; each with the 1–3 claims the pipeline's own `ClaimSelector` would check (extractor confidence when `inference/` is down). **Label** pre-fills the form; **Skip** records why (opinion, prediction, trivial, fragment, duplicate). Removes the search that took most of each fact's time, answers the "selection by the annotator" limitation, and the skip reasons measure the claim selector's precision for the paper. First real batch: 34 sources, 1,491 links, 10 articles (5 en / 5 es), 29 claims, 200s. `backend/src/services/labelling_batch.py`, `POST /labelling/batch`; batches saved in `backend/data/evaluation/queue/`.
- [x] 🐛 **Found by the first batch: the claim splitter ignored line breaks and cut at abbreviations** — a headline, a section label and the first sentence came back as one claim, and "for A.I." ended a sentence. Fixed in `ClaimExtractor._split_sentences`, which the fact-checker uses too.
- [ ] 🏷️ Label facts 1–50 · 11h (Sep 29 – Oct 5) — in progress: 6 labelled by Sep 29, 4 of which break a guide rule (wrong tier, compound claim, label outside the guide's definition) and should be revisited.
- [ ] 🏷️ Label facts 51–100 · 11h (Oct 6–12) — 100 is the floor the paper can report on. **Oct 13: 138 facts on file**, fact052-138 labelled by the AI pass (Claude), not yet checked by hand - marked so in each note except fact093-110, whose notes lack the `[AI label:` prefix the /evaluation page sorts on; 116 TRUE, 8 PARTIALLY_TRUE, 1 MISLEADING, 13 UNVERIFIED, **no FALSE** - positive-news outlets rarely publish a refutable claim, so the FALSE column will need claims from elsewhere (x-fact) or be reported empty. The claim selector's precision over all batches, 0.65 (126 labelled, 68 skipped; fragments the largest reason, 21), no claim left pending.
- [ ] 🏷️ Label facts 101–150 · 12h (Oct 13–19) — cells still short after 150 are reported short, not padded. **Oct 14:** fact139-148 from the day's batch (AI labels, prefixed; 9 TRUE, 1 PARTIALLY_TRUE, 10 claims skipped: precision over all batches 0.64, 136 labelled / 78 skipped). Then **39 facts of 17 off-mission articles moved to `data/evaluation/excluded/`** by the mission screen's own categories (party politics, war, crime, sport, a monitor review, a puzzle, a roundup, an awards list, a protest march; 6 human, 33 AI; the rule and every decision in its README): **109 in the set** - 91 TRUE, 10 UNVERIFIED, 7 PARTIALLY_TRUE, 1 MISLEADING, 0 FALSE; 74 en / 35 es; **31 labelled by hand, 78 by the AI pass, none checked yet**. The batch now also leaves out an article the classifier places under none of our topics (the day drew a procés court ruling with no topic, past the screen); an Aemet forecast filed under `climate` still got through - weather is the screen's `service` kind, and no change was made to it under the freeze.
- [ ] 🔁 Blind re-label of the hash-chosen 20% · 4h (Oct 26–28) — at least a week after the first pass, per the guide.
- [ ] 📐 Settle disagreements, report agreement and Cohen's kappa in `custom_dataset.tex`, `join` into `custom_en_es.jsonl` · 2h (by Oct 30)

### Evaluation harness (research questions by Oct 12 · the rest Oct 20 – Nov 9) · 40h

Added on Sep 29: every result the paper will report comes out of this,
and until then it had no hours. The research questions come first, since
they decide what the harness measures; the build starts once Sprint 4
has fixed the search and the first labelling pass is done, and is proven
on the x-fact pilot before the custom set is settled, so the benchmarks
start on Nov 10 with a working tool.

**Oct 1: designed, not built.** `docs/decisions/evaluation.md` fixes
what the items below share: the record format, the run layout and its
resume rules, what is reported apart from the error rate, and the stage
attribution table. Each item has a ready `/goal` in `docs/goals.md`
(G1–G7). Found while designing it, from the code and the data:

- `check_claim` takes no `language`, so Spanish claims would be searched
  with the English lexicon. It takes no `context` either, so a custom-set
  claim could be "verified" by its own article. G2 fixes both before the
  harness produces a single number.
- All 40 chequeado.com rows of the pilot list chequeado's own verdict
  page among their reference links, and none of them has a `claimDate`.
  Searching today's web will find the verdicts themselves. The harness
  flags this as `verdictLeak` instead of hiding it. Rule 3 cannot be
  checked for those 40 rows.
- The custom set so far (37 facts) is 27 `TRUE`, 0 `FALSE`: macro-F1 is
  averaged over the classes the gold labels contain, and the empty ones
  are shown, not averaged.

- [x] ❓ Fix 2–3 research questions, each with the metric that answers it · 3h (by Oct 13) — **done Oct 14 by the author** (four questions; Thesis priorities P0.1, thesis §1.5 and §6.1); this box was left unticked until Oct 20 — suggested: **RQ1** how well an open-web, low-cost pipeline verifies claims from constructive news in Spanish and English, against a temporally sound gold set; **RQ2** where it fails - retrieval, ranking or reasoning; **RQ3** how much of the verification work it takes off a journalist. Whatever answers none of them is cut or moved to future work.
- [x] 🧰 Harness: run the pipeline's own `check_claim` over a JSONL set (x-fact and the custom set share a format) · 12h — per claim: verdict, raw verdict, confidence, stage reached, the queries sent, every candidate and ranked source, latency; per model, cached and resumable, so a crash at claim 90 does not re-pay claims 1–89. **Oct 2 (G2):** `check_claim` takes `context` and `language`; `backend/src/evaluation/` (`dataset`, `record`, `runner`, `store`, `cli`) runs `uv run python -m src.evaluation.cli run --dataset ... --model ...`, keyed by dataset/model/thresholds/corpus, resumable (torn last line cut and re-run, errors retried, `--retry-unavailable`, `--fresh` sets aside), corpus snapshotted per run, first Ctrl-C stops cleanly. Loads the 64-row pilot and the `manual/` directory as they stand. Verified by `backend/tests/evaluation/` with the shared fakes only (G2's five proofs, plus the store, dataset, CLI and usage tests); **not yet run against live services** — that is the pilot.
- [x] 📐 Metrics · 6h — accuracy, macro-F1 and per-class precision/recall, the confusion matrix, bootstrap confidence intervals; search-unavailable runs and evidence newer than the claim (the guide's Rule 3) reported apart rather than folded into the error rate. **Oct 2 (G3):** `metrics.py`, `report.py`; `cli report --run <dir> [--compare <dir>]` writes `metrics.json`, `report.md` and `run.json` to `data/evaluation/reports/<dataset>/<model>/<key>/`. Also Cohen's kappa against gold, coverage and selective accuracy, seeded percentile bootstrap (10,000) and a paired bootstrap of B − A; error / searchUnavailable / llmUnreachable by id and `temporalLeak` / `verdictLeak` flags apart; breakdowns by language, topic group, claim type, tier and site; `cli table` for several models. Verified against hand-computed values on a ten-claim fixture built with `record.py`, bootstrap determinism, identical runs differing by exactly 0, and `report.md` rendered from a fixture run. Not yet run on real results.
- [x] 🔍 Retrieval evaluation · 4h (RQ2) — did the system find the annotator's reference links, or their domains, among its candidates and among the evidence it ranked — **Oct 4 (G4):** `evaluation/retrieval.py`. Link and domain recall at three depths (candidates, ranked, cited) and MRR against the references (x-fact self-links removed and counted); for any set, evidence rate, candidates and ranked per claim, the share the gate cut, distinct and rated domains, corpus share, verdict leak, which query kind found each source, retrieval seconds; all with bootstrap intervals, by set and language. In every `cli report`; `--compare` adds the paired differences. **Strategies:** `cli run --retrieval-only --label <name>` (no LLM call, so a strategy costs search time only; the label is in the run key) and `cli retrieval --run A --run B ...` for the side-by-side and each paired against the first. Live check on 6 pilot claims (`evaluation.md` §Retrieval evaluation): it found that weak one-word queries return adult sites, which the gate cut. Left: the full pilot.
- [ ] 🟡 🧭 Attribute every wrong verdict to a stage · 5h (RQ2) — retrieval (nothing pertinent found), ranking (it was found and cut), reasoning (it was ranked and misread) or aggregation - from the trace each run already records. **Oct 20: built** (`attribution.py`, in every report; see Thesis priorities P0.6). Left: re-running `cli report` on the real runs.
- [ ] 🟡 ⏱️ Journalist-effort metrics · 5h (RQ3) — the claim selector's precision (the labelling batch's skip reasons, recorded since Sep 29), time per fact (to add to the labeller), and the share of verdicts usable without re-checking. **Oct 20: built (G6)** - `python labeller/app.py stats` (precision 0.636 overall, 0.695 en / 0.521 es; time per fact as visible and wall seconds), `timing` on every new fact, and `effort.py` in every report (usable, confidently wrong, the estimate with `--minutes-per-fact`); 5 labeller tests, 7 backend. Left: timed facts (none yet - every fact so far predates the timer) and `cli report` over the real runs.
- [x] 🧪 Pilot on the 64-claim x-fact set, end to end · 5h — shakes out the harness before the custom set is ready; its first numbers are the baseline for the fixed search. **Oct 13 (G7):** run live in compose (`docker/docker-compose.eval.yml`) with `llama3.2:3b` on the dev GPU, after `/healthz` (all four up) and the source probe's search check (89 results per language; Google and Brave refusing SearXNG). 64/64 scored over four sessions: accuracy 29.7% [18.8, 40.6], macro-F1 0.168 [0.104, 0.234], kappa 0.07 [-0.03, 0.18]; English 41.7% / 0.358 (3 classes), Spanish 22.5% / 0.130; answers `FALSE` to 43 of 64. `verdictLeak` 9 (all PolitiFact, 4 via `staging.politifact.com`; no Chequeado URL ever a candidate), `temporalLeak` 16 of 20 decidable; reference link recall 0%; median 36.5 s a claim. Same model with no evidence: 18.8%, `FALSE` 60 of 64; the pipeline beats it by +10.9 points [+3.1, +20.3]. Found and fixed: each session now records its own settings (`test_each_session_records_the_environment_it_ran_in`); `gitCommit` from the container via the compose layer, and kept when `git status` over the bind mount (5.0-5.3 s) outlasts its old 5 s timeout (`test_a_slow_dirty_check_keeps_the_commit`). Found, not fixed: `INFERENCE_TIMEOUT` 30 s fails at four concurrent claims on CPU inference (5 of 20 claims); a looping model (Ollama 500 "token repeat limit") is filed as `llmUnreachable`; the harness process segfaulted twice in the Spanish run (`munmap_chunk(): invalid pointer`, scraping threads, not located); SearXNG had two all-engines timeout bursts. Plus the Spanish `test` split (165, α1): 19.4% [13.3, 25.5], macro-F1 0.111 [0.079, 0.142], kappa -0.002, no gain over the closed-book model, against the paper's 38.2-41.9 (7 labels, supervised); the X-Fact paper's Tables 3-4 beside ours, why they are not comparable, and what the years between claim and search do (verdict and temporal leakage, drift, link rot, recency, the model's memory): `docs/decisions/xfact-comparison.md`. Recommendation, not implemented: a per-run `evidence_exclude_domains` for x-fact runs only.

### Experiments on the stages before the verdict (Oct 6 – Nov 16) · 18h — **new on Oct 5, not yet funded**

The harness measures verdicts; these measure what decides which articles
get one - discovery, selection, admission, the topic classifier - and
give the paper its numbers on cost and on the editor's effort (RQ3). One
command, `uv run python -m src.evaluation.experiments <name>`, each run
writing `result.json` and `report.md` to
`backend/data/evaluation/experiments/`; how to run and read each is in
`docs/experiments.md`. The 18h are on top of the 900h: take them from
somewhere, or accept the overrun.

- [x] 🧰 Experiment tools · Oct 5 — `discovery` (sources, attempts, links, candidates and time per topic-group setting against the every-topic baseline), `selection` (editor against AI: precision, recall, Jaccard, AUC of the AI score; blind and assisted rounds apart), `blind-ai` (the AI run on a round already sent, so it cannot anchor the editor), `admission` (each candidate through `/enrich` once, cached; the topic and impact thresholds replayed offline with the pipeline's own classes), `topics` (the classifier against the labelled facts' articles). 9 tests on hand-built data. First runs: Environment reads 0.41× the sources and 0.10× the links; the classifier gets the group right 0.73 [0.59, 0.85] of the time and leaves 10% of articles with no topic at its 0.35 floor.
- [ ] 🔎 Scraping — discovery yield per topic group · 2h — `discovery` with each group, three useful pairs and the baseline, on five different days (feeds change through the day): the reduction in sources and links with an interval, and the language balance of what is left. **Oct 20: day 1 of 5** (`discovery/20261020T122152Z/`, the protocol in `docs/experiments.md`): one group alone reads 0.27-0.67× the sources and 0.14-0.29× the links of the baseline (33 sources, 1,369 links), a pair 0.40-0.50× the links; Environment's candidates 30 en / 6 es. Left: four more days, then the interval.
- [ ] 🩺 Scraping — source health and extraction · 3h — the source probe (`/scraper` → Source health) once a week for four weeks, plus `/sources`: up / degraded / down per source, extraction success per strategy, and the time-to-reception medians, as one table. **Oct 20: week 1 of 4** - `experiments sources` (new: the probe, `/scraper/freshness` and every earlier week in one report; 1 test): 30 up, 3 degraded (El País 403 on 3 of 5 politics pages, past the browser too; National Geographic and SINC feedless, as known), 157 of 165 extracted, all by trafilatura. Time to reception has 1 article: the backend's lake was emptied since. Left: weeks 2-4 (Oct 27, Nov 3, Nov 10).
- [ ] 🗳️ Selection — the AI against the editor · 5h — ten **blind** rounds (choose and send first, then `blind-ai --round <id>`) and ten assisted ones: precision, recall and Jaccard of the AI's picks, the AUC of its score, blind against assisted. A journalist-effort measure for RQ3, beside the claim selector's precision.
- [ ] 🚪 Admission thresholds · 3h — `admission` over at least 100 round candidates the editor chose for or against: admission rate, precision and recall over topic minimum 0.30–0.45 × impact minimum 0.10–0.30, and the AUC of the positive-impact score (it ranked a match report above a decarbonisation analysis on Oct 5). Feeds the defaults chosen in the tuning below.
- [x] 🏷️ Topic classifier · 1h — **Oct 20, at 139 facts (58 articles): top-1 0.67 [0.55, 0.79], top-3 0.88, group 0.83 [0.72, 0.91], no topic 2%; the threshold stays at 0.35** (`docs/experiments.md`, "topics"; the gold topics are mostly the AI pass's). Planned: `topics` again at 100 and at 150 facts: top-1, top-3, group accuracy, the no-topic rate and the group confusion; decide whether `TOPIC_CLASSIFIER_THRESHOLD` stays at 0.35. Replaces the de-scoped "improve topic classifier accuracy" item's missing measurement.
- [ ] ⏲️ Time per stage · 2h — over the pilot and one ingestion round: enrichment, admission, retrieval, ranking and the LLM, from `/metrics` and the job journal, on the dev GPU and on the production CPU - the cost side of every result.
- [ ] 📝 The tables into the paper · 2h — discovery, selection, admission and topics, in the evaluation section, each with the command that reproduces it.

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

- [ ] 🟡 🦙 Benchmark local Ollama models (baseline, free) — **Oct 4: one command**: `cli writing run --model llama3.2:3b --repeats 2`, with the production CPU limits (`docs/decisions/evaluation.md` §Writing-model benchmark). Resumable like the harness. Left: the run.
- [ ] 🟡 ⚡ Benchmark one hosted provider (Groq: speed) — **Oct 4**: the same command with `LLM_BASE_URL`/`LLM_API_KEY` pointed at Groq. Left: a key, the run, and Groq's price entered in `prices.json` on the day.
- ✂️ OpenRouter and Together AI benchmarks — cut on Sep 29
- [ ] 🟡 📏 Compare on the corrector's 5 LLM-based metrics: grammar, factConsistency, seo, hallucinationIndex, style (readability and coverageVerification are deterministic and do not depend on the model) — **Oct 4: built.** The model is benchmarked as the editor it is: 6 news texts (3 en, 3 es), each clean and with 5 planted defects, one per metric (`data/evaluation/writing/texts_en_es.jsonl`), so each of the 30 pairs has a known right answer: the targeted score should drop. The corrector's own `llm_metrics` runs, prompt included. Two corrector bugs fixed on the way: `"issues": null` lost all five metrics, and a missing or non-numeric score counted as a 0 judgement. Left: the runs.
- [x] 📊 Build a scoring rubric + comparison table per model — Oct 4: the rubric is `docs/decisions/evaluation.md` §Writing-model benchmark (format compliance as a gate, then detection with a bootstrap interval, defect named, off-target drift, repeat consistency, clean-text calibration, cost and latency); `cli writing report --run A --run B ...` writes `comparison.md`/`.json` with each model paired against the first. 22 tests (`tests/evaluation/test_writing.py`), the rubric checked against scores worked out by hand.
- [ ] 🟡 💰 Log cost/latency/quality trade-offs per provider — **Oct 2: the logging is built**: every harness and writing-benchmark record carries its LLM calls, tokens and latency (metered under `LLMClient`, so the client measured is production's), summed per session in `run.json` and per run in each report, priced from `data/evaluation/prices.json` (`--prices`). Provider swap stays `LLM_BASE_URL`/`LLM_API_KEY` only. Left: the runs (Ollama, then Groq, same commands with a different environment), the Groq price filled in on the day, and reading the trade-off off `cli table` / `cli writing report`.

### Sprint 7 (Nov 17 – Dec 10) · 60h — 🕵️ Verification models

70h → 60h on Sep 29: the guardrail stress test moved to the testing track.

- [ ] 🟡 🔍 Benchmark models for `LLMVerifier` (claim verification accuracy) — **Oct 2: one command per model**: `cli run --dataset <set> --model <m>` (resumable), then `cli table --run <dir> --run <dir> ...` for the side-by-side and `cli report --run B --compare A` for the paired difference. Left: the runs, once the labels are settled (Oct 30).
- ↪️ Stress-test hallucination guardrails — moved to the testing track (November), Sep 29.
- [ ] 🟡 🎯 Compare verdict agreement vs. human-labeled ground truth set — **Oct 2: computed by every report**: accuracy, macro-F1, Cohen's kappa against gold (the labeller's own agreement statistic), the confusion matrix, with intervals. Left: running it on the joined custom set, `cli run --dataset data/evaluation/custom_en_es.jsonl --model <m>` then `cli report`.
- [ ] 🧮 Re-tune `ConfidenceScorer` weights per best-performing model — needs real runs. The data: one `cli run` per candidate `CONFIDENCE_*` pair set in the environment (the run key includes the weights since Oct 2, so each is its own run), compared with `cli report --run B --compare A`.
- [ ] 🏁 Select final default model(s) + document rationale — needs real runs: `cli table` over the verification runs and `cli writing report` over the writing runs are the evidence.
- [ ] 📄 Draft results section for the paper (model comparison data) — needs real runs; the numbers will come from the committed `data/evaluation/reports/` (`report.md`, `models.md`, `comparison.md`).

---

## 💻 Phase 6 — Interface: Reader View (Dec 11–17) · 30h (Oct 19)

Before this sprint the frontend was an internal tool — eight pages (`/` analyzer, `/live`, `/claim`, `/enrich`, `/corrector`, `/scraper`, `/sources`, `/graph`). Since Oct 2, ahead of its week, it also has the reader view: `/reader` and `/reader/[id]`, over `GET /reader/articles` and `GET /reader/articles/{id}`.

### Sprint 8 (Dec 11–17, one week) · 30h (Oct 19)

60h → 40h on Sep 28 (validation set), 40h → 20h on Sep 29 (testing track),
20h → 35h on Sep 30: the 15h Neo4j gave back, so the interface gets one
full week. It comes after the benchmarks, so it shows the final model's
output. 35h → 10h on the build-status page's Oct 6 rebalance, its four
tasks built on Oct 2-4; **10h → 30h on Oct 19**, the author's request,
for the five new tasks below (the week the director reads the draft).

**Cut from scope on Sep 29:** user authentication, profiles, bookmarks and
recommendations v1. The paper is about automating a journalist's
verification work; none of those four answers anything it asks, and each
is a subsystem to build, secure and test. What stays is the output a
journalist or reader actually looks at.

- [x] 📰 Topic-based feed of publishable articles (read-only) — Oct 2. `GET /reader/articles` (`services/reader/`): the newest run of each article the pipeline marked publishable, keyed by host and path so a re-analysis keeps its link and a re-check that turns FALSE withdraws it; topic and language filters with facet counts, paging, and the lake's analysed / publishable counts so an empty feed says why. A request lists the exploitation layer's file stamps and re-reads only records that changed (tested by counting reads). `/reader` shows it. Verified by tests (`tests/services/reader/`, `tests/api/test_reader_routes.py`) and by looking: headless Chrome over the dev stack's lake (8 runs, 2 articles, 1 publishable) and a synthetic lake (25 published, every claim outcome), plus an empty lake, a lake with nothing publishable, and the backend down. Still true: the real lake holds one publishable article, so the feed has little to show until ingestion runs
- [x] 🧾 Article view: the verdict per claim, the evidence and why each source was trusted — Oct 2. `GET /reader/articles/{id}` and `/reader/[id]`: each claim's verdict and confidence, the model's reasoning, the model's own answer when a guardrail overrode it, and its sources (cited or not, stance, quoted passage, site reliability or "unrated" and the assumed default, how well it addresses the claim, relevance and its factors, which search found it). A claim whose search or model failed reads "Not checked" and is counted apart from the verdicts; an article none of whose claims was judged shows NOT_CHECKED instead of UNVERIFIED. The lead and a link, never the body or a scraped page (tested). Seen rendered on both lakes above
- [x] 🎨 Extend the existing hand-written CSS design system (no new UI libs) — Oct 2: a reader section in `globals.css`, through its variables only, reusing `.trace-*`, `.badge`, `.claim-verdict-*`; no new dependency. Measured with playwright in the system Chrome: no horizontal overflow at 375px on either page, light or dark; animations off under `prefers-reduced-motion`. The header's nav now wraps on a phone instead of running off it
- [x] 🌍 The reader view is public (Oct 4) — Caddy serves `/reader`, `/reader/<id>`, their `/api/reader/*` proxies and the static bundles without the site password (on plain HTTP too when there is no domain); every other page still asks for it. On a reader page the nav's operator links no longer prefetch, or each visit would send nine requests answering 401. Checked in real `caddy:2.10.2` in both modes; `test_only_the_reader_view_is_served_without_the_password` holds the list.
- ↪️ E2E test for the feed — in the testing track's final window (Dec 18–24), the week after
- [ ] 🟡 🌐 The reader in Catalan and Spanish, not only English · 8h — the stories are written in ca/es/en and the page around them is English only (`<html lang="en">`, "Checked articles", the verdict names): labels per language, `lang` from the story's language, a switch kept in the URL like the filters; a dictionary per language, no i18n library. **Oct 20: built** - `lib/readerText.ts` (three dictionaries behind one interface: a missing string fails the typecheck), `LanguageSwitch`, `useReaderLang`; `?lang=`, else the content's language, else the browser's; `<html lang>` follows; dates in UTC with the page's locale (found and fixed on the way: a source dated `2026-09-12T00:00:00` showed the 11th east of Greenwich). Verified with `next build` and headless Chrome against a stub backend: the feed, an article and a story in each language, the links carrying `?lang`, the operator pages still English. **Left:** a native reader of Catalan and of Spanish to read the strings - written by the AI, unreviewed, like the drafts' Catalan. **Oct 20: the sheets are ready**, `docs/review/reader-{ca,es}.md` (223 rows each, `node scripts/reader_strings.mjs`, every function rendered as read, plurals at 1 and 3), with a log for the corrections applied.
- [ ] 🟡 📡 Stories and checked articles in one feed, with RSS and a sitemap · 4h — today they are listed apart; an RSS feed of the stories, a sitemap of the public pages, and metadata for `/reader/[id]` (the stories already have `generateMetadata`). **Oct 20: built** - `/reader/feed.xml` (RSS 2.0, stories and checked articles in one list newest first, each article with its verdict line, in ca/es/en by `?lang=`), `/reader/sitemap.xml` (every public page with its language alternates), and `/reader/[id]/layout.tsx` for the article's title, description and Open Graph tags; `PUBLIC_SITE_URL` or the forwarded host for absolute links. Checked against a stub backend behind fake `X-Forwarded-*` headers: both files parse as XML, the links are absolute and carry `?lang`. **Left:** the page itself still shows our stories and the checked articles in two sections - a merged list on the page is a design decision for the author; and a `robots.txt` naming the sitemap, which would sit outside `/reader/` and behind the password.
- [ ] 🟡 📖 A reader's guide to the verdicts · 2h — what each label means here, why "Not checked" is not `UNVERIFIED`, what a confidence is and is not; linked from every badge; the measured accuracy once the labels are checked. **Oct 20: built** - `/reader/guide` (server-rendered, in ca/es/en like the rest of the reader): the five verdicts in the verifier's own terms, Not checked, the article's worst-claim-wins verdict, what a confidence is (the model's certainty blended with the evidence's relevance, citation and quantity - checked against `ConfidenceScorer`) and is not, the sources; every badge on the reader's pages links to its own section (`VerdictBadge guide`), with an accessible name. Verified in headless Chrome. **Left:** the accuracy, deliberately unpublished until the labels are checked (P0.2), and a native read of the es/ca text.
- [ ] 🟡 ♿ Accessibility pass on the public pages (WCAG 2.1 AA) · 3h — keyboard and focus, verdict colours' contrast in both themes, names for badges and stance icons, 375 px with the language switch; checked in a browser's accessibility tree. **Oct 20: contrast fixed, the rest checked** - computed every verdict colour against WCAG's 4.5:1: in light mode Partly true (3.79) and Misleading (3.43) failed, in dark mode all five badges failed (white on bright fills, 2.2-3.4), and so did the global button text on the dark accent (2.42); now light fills `#6d7c1c` / `#a56108` (4.62 / 4.87, and 4.66 for warnings on a card) and theme-aware text (`--badge-fg`, `--accent-fg`: 5.5-8.6 in dark mode). Every badge on the reader is a link with a name ("True: what this verdict means"); stances are words, not icons; the switch is a named `nav` with `aria-pressed`/`aria-current` and each language marked with its own `lang`; a global `:focus-visible` ring (accent, 5.2 / 7.8 against the background). Screenshots at 375 px in both themes: the switch and back link share a line, nothing overflows. **Left:** a run with a real screen reader and with axe (no dependency added for it), and the five readers below.
- [ ] 🧑‍🤝‍🧑 Five readers try it · 3h — five people who are not the author, three tasks each (why was this claim judged so; a FALSE against a "Not checked"; was this story written by a person): success, time, what confused them. **Oct 20: the protocol is written** (`docs/review/reader-test.md`: who, what is said, the three tasks with what counts as success, a sheet per reader, the analysis), the pages to choose and task 2's form to decide: the public reader never shows a FALSE claim (an article with one is not publishable), so FALSE reaches a reader only through the guide. RQ4 from the reader's side

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
- [x] 🚦 CI pipeline (moved from Phase 3) — Oct 2: `.github/workflows/check.yml`, on every push and pull request, three jobs each calling one `check.sh` target: `backend` (Python 3.12, `uv sync` from the lock, a dummy `NEO4J_PASSWORD`; the model tests skip, nothing listens on `INFERENCE_URL`), `frontend` (Node 20, `npm ci`) and `labeller`; uv and npm cached. **Stays local**, said in the workflow's header: `inference` (the models), `slow` (the corpus), `graph` (Neo4j), `gcp` (Docker, Floci). **No linter**: none is configured, and that is the decision for now. `scripts/check.sh` is now executable in git (it was 100644, refused on a Linux runner). Verified: YAML parsed (no `actionlint` installed), and `tests/test_ci_workflow.py` holds the workflow to `check.sh` (every target it calls is in the case list, none of the local-only ones, the dummy password set; the executable-bit check skips on Windows). Not yet run on GitHub: the first push is the user's.
- [x] 🔗 Integration test: full pipeline run — Oct 2: `tests/test_full_pipeline_integration.py` runs the real `AnalysisService.analyze` from a URL: the real extraction cascade over a saved page (`tests/fixtures/seagrass_article.html`, served by a new `FakeFetcher`), real enrichment over `inference/`, real admission on a temporary Qdrant, the real `FactChecker` (retriever, scraper, ranker with its pertinence gate, `LLMVerifier`, `ConfidenceScorer`); only SearXNG, the page fetches and the LLM (a canned JSON verdict) are fake. The lake and the cache go to a temp dir, the graph is off. Ten tests: every per-claim stage literal in order, cited sources survive ranking, the canned verdict and citations come through, a no-evidence claim is `UNVERIFIED` with no LLM call, the article can't corroborate itself, all three lake layers with lineage, `ANALYZE_RESPONSE_SHAPE`, and a cache hit returns the same answer. **Ran, not skipped**, with `inference/` reachable on 127.0.0.1:8001 (the dev stack's): 10 passed in 26 s (one analysis per module; per test it took 156 s). With `INFERENCE_URL` pointed at a closed port, all 10 skip in 4 s.

### November (Nov 1–30) · 12h

- [x] 🧮 Tests for the benchmark harness itself — scoring, macro-F1, kappa, the temporal-leakage split: a wrong metric is a wrong paper — Oct 2–4, with the harness: `backend/tests/evaluation/` (10 modules, 103 tests). Each metric against a value worked out by hand (accuracy, per-class precision/recall/F1, macro-F1 over gold classes only, coverage, selective accuracy, Cohen's kappa and when it is undefined, the confusion matrix), the temporal and verdict leaks, the bootstrap (deterministic under a seed, brackets its estimate, undefined resamples counted), the paired bootstrap (identical runs differ by exactly 0), resume after a crash, and CRLF checkouts hashing like LF ones (a different run key per OS before Oct 4).
- [x] 🤖 Model comparison tests (writing + verification, Phase 5) — Oct 4: verification, `test_harness_report.py` (two runs paired over the claims both scored, a run against itself differs by 0, the models table refuses mixed datasets, priced runs); writing, `test_writing.py` (the rubric against scores worked out by hand, runs paired against the first, runs over different text sets refused). And `/evaluation`'s runs panel is held to a report the harness writes (`test_evaluation_summary.py`): it had guessed the format, and every guess missed.
- [x] 🚫 Stress-test hallucination guardrails (moved from Sprint 7) — Oct 2: `tests/services/fact_checker/verification/test_guardrail_stress.py`, 83 scenarios plus 3 strict xfails. A fake *model* (raw text behind the real `LLMClient`) bluffs through the real `FactChecker.check_claim` → `LLMVerifier` → `ConfidenceScorer`: definitive verdicts citing nothing, citations out of range / negative / strings / floats / bools / repeated / not a list, citing only sources it called unrelated, fabricated, swapped, one-word-changed, headline-stitched and newline-split quotes, verdicts outside the enum, confidences of 5, -3, 1e308, ±Infinity, NaN, "high", null, and twelve kinds of malformed or empty JSON, and no evidence at floors 0, 1 and 3. **Six bluffs found and fixed**, each with a regression test that failed before the fix: repeated citations inflated the confidence (a one-source FALSE went 0.70 → 1.00); `[true]` cited source 1; `"cited_evidence": null` or `0`, and valid JSON that was not an object (`"TRUE"`, `[]`, `42`), raised and failed the whole article; a quote stitched from a headline and its body passed as verbatim; a per-run `min_evidence_for_verdict=0` sent a no-evidence claim to the model. **Still bluffable**, pinned as strict xfails because each needs a policy rather than a fix: a source the model calls both "supports" and "unrelated" still grounds its citation (first assessment wins); a FALSE whose every cited source "supports" stands; a TRUE whose every cited source "contradicts" becomes PARTIALLY_TRUE. Fakes only; a real model trying to bluff remains untested.

### December 1–10 · 10h

- [ ] 🟡 ☁️ Infra smoke tests (staging) — locally the backend container comes up healthy, but a full analysis inside it is unverified — **Oct 4: `scripts/smoke.sh <url> <key> [--claim]`**, the one the deploy runbook calls: `/healthz` (naming what is down), `/metrics`, the key refused without it and accepted with it (or flagged OFF), the reader and job polling open, `/evaluation/summary` served (a 404 is an image not rebuilt), and with `--claim` one real claim to a verdict with evidence, no `llmUnreachable`, no `searchUnavailable`. curl and grep only, for Git Bash on Windows. `tests/test_smoke_script.py` runs it against the real app under uvicorn (9 tests). Left: running it on the VM, the runbook's step 7. (A full analysis inside the containers has run since Oct 1 - CLAUDE.md.)
- [ ] 🟡 📉 Load/performance testing before final deployment — and the parallel pipeline's speedup, asserted as overlap and never measured — **Oct 4: the speedup is measured** (`scripts/bench_claim_concurrency.py`, the real `FactChecker.run` over a simulated network at the declared ceilings): ×3.4 on a four-claim article with a fast model; ×1.16 with production's CPU LLM one call at a time, where the model is 180 of the 184 s - the simulation's 184 s matches the production stack's real run. Every ceiling held at exactly its value. `tests/test_bench_claim_concurrency.py` keeps it runnable (3 tests, ~1 s). Left: sustained load on `/analyze/jobs` on the VM, before the final deploy.

### Final (Dec 18–24) · 20h — after the interface, before the paper

- [ ] 🧪 Final full regression suite, backend + frontend + `slow` + `graph` (moved from the paper phase)
- [ ] 🐛 Final bugfix pass across all phases (moved from the paper phase)
- [ ] 🚀 Final deployment verification — prod smoke test (moved from the paper phase)
- [ ] 🟡 💻 Frontend E2E tests — job polling and the reader view (no test runner exists yet; the typecheck is the only gate). Moved here from December 1–21 on Sep 30: the interface is built Dec 11–17. **Oct 20, at the user's request (it was on the Oct 14 cut list):** `./scripts/check.sh e2e` (`scripts/e2e.py`, standard library and headless Chrome, no new frontend dependency) builds the frontend, serves it against a stub backend and checks 15 things: `/api/jobs/<id>` reaches the backend on every poll (mutation-checked: without `no-store` it fails), the reader's feed, article, guide and story in all three languages, a real 404, the feed and sitemap XML, and an operator page in English. Not in `all` (a build, and Chrome). **Oct 20, later: the `cancelled` guard too** - Chrome driven over the DevTools protocol on a pipe (standard library still): a job started on `/`, its first poll held three seconds by the stub, the page left for `/reader` meanwhile; no poll may follow. Mutation-checked: without the guard, 4 polls after leaving. The same for bulk mode (`useBatchAnalysisJobs`' guard, also caught when removed). 17 checks; nothing left of this item but a test runner, which the frontend still does not have.

---

## 📄 Phase 7 — Paper (Dec 25–31) · 35h

### Sprint 9 (Dec 25–31, the final week) · 35h

50h → 35h on Sep 29: its three QA items moved to the testing track. Since
Sep 30 they run the week *before* (Dec 18–24), so the paper is written
about a system that no longer changes. The paper itself is not cut.

- [ ] ✍️ Consolidate methodology section (pipeline architecture) — `docs/arquitectura-tecnica.md` is the starting point and was brought back in line with the code on Sep 28 (v1.1). **Oct 20:** the thesis brought up to the day's code and results - the three evidence conditions as harness modes, stage attribution (built, aggregation first) and the effort measures (built), the query-kinds switch and pooled judgements (TREC, `voorhees2005trec` added), the first ablation (RQ2), the classifier on 58 articles, discovery day 1 and source health week 1, the found verdict and coverage counts, the reader in three languages, its guide, feed and contrast, the e2e target, and a 20 Oct paragraph in the deviations. Not compiled here (no LaTeX on this machine); braces and environments checked balanced.
- [ ] 📊 Insert AI model benchmarking results (Phase 5 data)
- ↪️ Final regression suite, bugfix pass and prod smoke test — moved to the testing track (Dec 18–24)
- [ ] 📬 Submit / deliver paper draft
- [ ] 🎉 Project wrap-up & retrospective notes

---

## 📈 Trends — what goes viral, and the good news in it (Nov 3 – Dec 24) · 76h · added Oct 26, on top of the 900

The author's request on Oct 26 (`docs/decisions/trends.md`; goals in `docs/goals.md`, "Trends"). Free tools only; TikTok never scraped. Built ahead of its weeks on Oct 26, on `feature/trends`.

- [x] **T1 · Trend signals and a trend's card** (12h) — `backend/data/trends/*.yaml` (Google Trends ES and US, r/UpliftingNews top of the day, Upworthy, Know Your Meme), `src/services/trends/` (readers, seeds, the news search, `TrendService`), saved feeds as fixtures. 36 tests.
- [x] **T2 · Trending as a lens on /discover** (16h) — `trending: true` rounds (`TrendingDiscovery`), `BETTING_DOMAINS` in `off_mission`, 72 h a trend and a week an article, the unchanged screen, `trend_rank` (virality and the signal's record), the AI told it is trending, `TrendLedger` on queue, the button, step 2 and the trend card on `/discover`. Live: 53 trends, 92 articles, 39 candidates in 13.4 s; its order not yet good (advice and human interest at the top). With the real screen, El País's metro reopening was left out as a service page (0.024).
- [x] **T3 · `internet_culture`, if a re-screen holds** (6h) — **not adopted** by its rule (`experiments/topics24/`): fit and pull failed. 23 topics stand.
- [ ] 🟡 **T6 · Five trend rounds labelled blind (RQ1)** (12h) — rule written first, `experiments trends run|report`; **day 1 of 5 done** (Claude's labels, blind): 12/20 worth offering, 5 clearly positive, 12 new. Days 2-5 are the author's, one a day.
- [x] **T4 · The positive angle** (14h) — `AngleFinder`: proposed by the writer model, checked by `check_claim`, kept only TRUE from 2 other domains; refused for disasters, war, crime, death, or when the screen cannot say. `WriterThresholds.angle_*`. Live trial recorded (`experiments/trends/angle-trial-2026-10-26.json`).
- [x] **T5 · Writing and publishing from a trend** (10h) — the writer told the trend and the confirmed angles; `apply_angle_check` in the review; `PublishedStory.trend`; `TikTokVideo` behind a click; "From a trend" on `/drafts/[id]`. e2e checks added (the script still needs POSIX; the same checks passed on Windows by hand: 0 connections to TikTok before the click).
- [ ] 🟡 **T7 · The trends section in the thesis** (6h) — written into candidate selection, news acquisition (`06b-trend-signals.tex`), the topics, the writing flow and RQ1; days 2-5 left as `\pending`. Builds: 153 pages, no undefined reference.

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
- **Docker rebuilds that reuse their cache** (Oct 9) — a no-change rebuild took 291 s: the build cache sat at Docker Desktop's 20 GB cap and evicted the 2.7 GB dependency layer of one image whenever the other was rebuilt. The cap raised to 60 GB, and uv's download cache kept between builds (`docker/README.md`, "Slow rebuilds"). A rebuild after a code change: ~30 s.
- **SSRF guard** on every server-side fetch, English and Spanish lexicons, and a set of invariants enforced as tests (`backend/tests/test_invariants.py`)

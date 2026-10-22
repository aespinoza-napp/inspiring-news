# Performance: where the time goes, and what to do about it

> Read this before trying to make anything faster, before choosing
> hardware for the language model, and before changing what the
> verifier, the writer or the reviewer is sent. Measured 2026-10-21 on
> the dev laptop (Intel Core Ultra 7 165U: 2 performance cores, 8
> efficient, 2 low-power; Intel Arc integrated GPU; 62 GB; no discrete
> GPU), Ollama 0.40.6, everything else stopped - except the antivirus,
> which took up to 130% CPU. Single measurements on this machine move by
> a factor of two; every comparison here is interleaved or paired.

## The one fact everything follows from

**The language model is the work, and the model's calls are serial.**
Every role - verifier, AI selection, writer, reviewer - takes the
process's one LLM permit (`LLM_MAX_CONCURRENCY=1` on a CPU, because on a
CPU parallel calls only slow each other: `concurrency.md`, 2026-10-01).
So the pipeline's throughput is `seconds per model call x calls`, and
everything else either hides behind the model or is small next to it.

Where one analysed article's time went (journal of 2026-10-20, four
claims; the harness's response-time section for the per-claim split):

| Stage | Seconds | Notes |
|---|---:|---|
| Fetch the article | 1 | |
| Enrichment | 8-26 | bge-m3 over the whole article is the largest part (3-6 s); 18 s more in the first article after a restart (fixed below) |
| Claim selection | 3.5 | |
| Search + fetch the pages, all claims at once | 15-30 | two searches at a time on purpose: SearXNG's engines suspend a client that asks faster (`retrieval.md`) |
| Ranking | 5-8 a claim | embeddings over `inference/`, one request at a time |
| **The verifier, one call a claim** | **30-65 a claim, one claim at a time** | **three quarters of a claim** (`evaluation.md`, "Response time of the verifier") |
| Graph | 4 | |

And of one model call, **most is reading the prompt, not writing the
answer** (`scripts/bench_ollama.py`, a verifier-shaped call of 1,421
prompt and ~103 answer tokens, `llama3.2:3b`): 29 s reading at 49
tokens a second, 16 s writing at 6.4. Ollama keeps the last prompt's
prefix, so the verifier's system prompt (407 tokens) is read once and
then reused (`cached n_tokens = 407` in its log) - but every source
excerpt is new every time.

So there are exactly three ways to make the pipeline faster, in order
of what they buy:

1. **Faster hardware for the model** - the only order-of-magnitude lever.
2. **Fewer tokens per call** - fewer to read, fewer to write.
3. **Fewer calls.**

## What was changed (2026-10-21)

### 1. The verifier reads the passages about the claim, not the page's opening

`PipelineThresholds.verifier_excerpt` (`passages` | `head`) and
`verifier_excerpt_chars`, default `passages` at 700
(`backend/src/services/fact_checker/verification/excerpts.py`). Until
now each source reached the model as its first 1,500 characters: the
headline block, the standfirst, a cookie notice - rarely the paragraph
that says what the claim says. Now: the sentences that carry the
claim's terms, best first, then the page's opening with whatever budget
is left, in page order, with ` … ` between sentences that are not
neighbours. The terms are `terms.py`'s, the same that built the queries
and that the pertinence gate cuts on. A page that mentions none of
them gets its head, as before.

**Measured on the train half, oracle mode** (`run --oracle`: the
annotator's own pages, no search, so the two runs read the same
sources), `llama3.2:3b` on the integrated GPU, same day, back to back.
Rule written before either result was read: adopt if the paired
accuracy difference's interval includes zero or is positive, and the
prompt shrinks by 30% or more.

| | A: head, 1,500 (`1e045c3dea31`) | B: passages, 700 (`08bcab0248c3`) |
|---|---|---|
| Accuracy (68 paired) | 57.4% | 61.8%: **+4.4 points [-4.4, +13.2]** |
| Macro-F1 / kappa | 0.387 / 0.243 | 0.410 / 0.327 (+0.084 [-0.055, +0.241]) |
| Coverage (not UNVERIFIED) | 89.7% | 88.2% (-1.5 [-4.4, 0.0]) |
| Only this run right | 4 claims | 7 claims |
| Prompt tokens a call | 1,248 | **880 (-29.5%)** |
| Model call, median / p90 | 29.9 / 45.4 s | **22.8 / 33.9 s** |
| A claim, median / p90 | 58.4 / 81.8 s | **44.0 / 63.9 s** |

Not worse, and a quarter faster. The prompt fell 29.5% a call (30.6%
in total tokens), half a point short of the bar: adopted anyway, and
said so here, because the bar stood for "fast enough to matter" and the
model's time fell 24%. One claim (fact081) in B never finished its
answer and hit `LLM_TIMEOUT` twice (360 s); rebuilt by hand, both modes
answered in under a minute, so it is a model loop, not the excerpt - and
it is what change 2 is for.

Evaluation runs made before this keep their keys and resume
(`evaluation/runner.py`, `keyed_thresholds`): the excerpt enters a
run's key only when it is not the old head at 1,500. To resume such a
run under the new code: `--thresholds
data/evaluation/thresholds/verifier_head_1500.json`. The analysis cache
keys on every threshold, so cached analyses are recomputed once.

### 2. A verdict's answer is capped, and a capped answer is not asked for again

`MAX_ANSWER_TOKENS = 1024` on the verifier's call (`llm_verification.py`):
the longest of 196 answers in four runs was 328 tokens. And
`LLMClient.complete_json` no longer retries an answer the server cut at
`max_tokens` (`finish_reason == "length"`): the retry asked the same
question at temperature 0 with the cut answer appended, and a model
that looped once loops again - a second cap's worth of the one permit
for the same `None`. This applies to the writer's 4,096-token cap too.

### 3. `inference/` batches embeddings by length, not one at a time

`EMBEDDING_BATCH_TOKENS=2048` (`inference/src/config.py`): texts sorted
by length and batched while the padded batch stays within 2,048
tokens. One at a time (`EMBEDDING_BATCH_SIZE=1`, 2026-10-16) was right
for long pages, which a batch pads to its longest, and wrong for short
texts, which pad nothing. Same vectors (to 2e-7):

| Request | One at a time | Batched by length |
|---|---:|---:|
| The 163 topic keywords (once per backend process, in the first article) | 17.9 s | **4.4 s** |
| A claim's 21 search snippets (the retriever's funnel) | 12.6 s | **6.5 s** |
| 8 evidence pages + 3 snippets (the ranker) | 16.7 s | 16.9 s |

The keyword call used to take the first article after every restart
past `INFERENCE_TIMEOUT`'s 30 s whenever the machine was busy
(reproduced here once).

### 4. The rewrite loop does not ask for a correction it is about to replace

A review is two calls: the scores, then a proposed correction - the
whole article written out again, the longer of the two. In a rewrite
loop, a review followed by another round had its proposal thrown away
by that round's rewrite. Now `DraftReviewer.review(propose_if=...)`
skips it exactly when the loop's own test says another round follows (a
round left and a scored metric below its target). If that next rewrite
is then refused, the draft keeps a review without a proposal; reviewing
it again proposes one. Saves one long call per extra round; nothing for
`maxRounds=1`, the default.

### 5. The dev laptop's model on its integrated GPU (optional, one command)

`./scripts/ollama_igpu.sh on` (sudo; restarts the system Ollama with
`OLLAMA_IGPU_ENABLE=1 OLLAMA_VULKAN=1`). Measured with
`scripts/bench_ollama.py` and the writer's real prompt, the same calls
on each backend:

| | Prompt read | Answer written | One call |
|---|---:|---:|---:|
| **Verifier** `llama3.2:3b`, 1,421 in / ~105 out | | | |
| CPU, Ollama's default threads | 31-46 tok/s | 5.9-6.3 | 48-65 s |
| CPU, `num_thread` 10 | 41-66 | 11.8-14.0 | 32-46 s |
| Integrated GPU | **120-152** | 8.9-9.1 | **22-28 s** |
| **Writer** `qwen3.5:4b`, a Spanish draft, 2,194 in / ~1,100-1,300 out | | | |
| CPU, default threads | 15.8 | 4.4 | 381 s |
| CPU, `num_thread` 10 | 23.9 | **6.7** | **298 s** |
| Integrated GPU (`num_batch` 128) | **38.1** | 4.4 | 312 s |
| **Reviewer** `qwen3.5:9b`, the same prompt, 200 out | | | |
| CPU, `num_thread` 10 | 13.8 | **4.1** | 215 s |
| Integrated GPU (`num_batch` 128) | **38.3** | 3.1 | 129 s |

What it says:

- **Reading a prompt is 2.5-3x faster on the integrated GPU; writing is
  fastest on the CPU with the right thread count.** The verifier (long
  prompt, short answer) gains most: ~2.9x over the default. The writer
  (short prompt, long answer) gains nothing over 10 CPU threads.
- **Ollama's default thread count is wrong on this hybrid CPU**: it
  spreads over the two 2.1 GHz low-power cores, and every token waits
  for them. 10 threads doubles the answer speed. It is set per model
  (`PARAMETER num_thread 10` in a Modelfile) - the OpenAI endpoint the
  backend speaks ignores request options.
- **The Qwen 3.5 models crash the integrated GPU at Ollama's default
  batch** (`vk::DeviceLostError`, every long prompt): a 512-token batch
  through their layers outlasts the driver's hang check. `num_batch`
  128 runs. `llama3.2:3b` is fine at the default. So on the integrated
  GPU, the writer's and reviewer's Modelfiles need `PARAMETER num_batch
  128` beside their `num_ctx`.
- On the integrated GPU Ollama counts shared memory as VRAM and serves a
  **32k context by default**, not 4k: a long writer prompt is no longer
  cut silently (`writing.md`, "The model").

Not applied by this change, because it needs sudo and restarts a
system service: run it, and check `./scripts/ollama_igpu.sh status`.
Production has no GPU at all (below).

### 6. Scraping: pages are parsed one at a time, and fetched once

**Parsing in parallel threads was 20x slower than in turn.** Evidence
pages are fetched eight at a time (`SCRAPE_MAX_CONCURRENCY`), and each
thread then parsed its page - trafilatura, BeautifulSoup, htmldate,
dateparser: pure Python, holding the GIL. Threads parsing at once do
not share it, they thrash it: eight extractions of one 2.6 MB page took
**239-304 s side by side and 14.3 s in turn**; two at once were already
slower than two in turn (3.1 s against ~2.6). Now a process-wide permit
of one (`concurrency.py`, `PARSE`) is held around the parse only, after
the fetch, so downloads stay concurrent. Over 200 real evidence pages
(the URLs the evaluation runs recorded, through the real cascade, eight
at a time; two runs minutes apart on the live web):

| | Before | After |
|---|---:|---:|
| All 200 pages | 58.4 s | 41.5 s |
| A page, p50 / p90 | 0.95 / 3.3 s | 0.96 / 4.0 s |
| A page, p99 / slowest | 39.1 / 39.6 s | 11.2 / 16.8 s (a slow NASA server) |

The five pages that took 30-40 s were not slow sites: each fetched in
0.1-2 s and parsed in under 1.3 s alone. The p90 rises a little because
a page now waits its turn to be parsed; the tail is what a claim waits
for, since a claim's pages are fetched together and it waits for the
last. (The first parse in a process also loads dateparser's locale data,
~2.5 s once.)

**An evidence page is fetched once per process and hour**
(`retrieval/scraper.py`, `PageCache`): claims of one article are checked
at once and find the same pages (2 of 20 fetches in the 2026-10-20
journal), and so do a second look, the stories of one discovery round,
and an evaluation run's related claims. A claim asking for a page
another claim is fetching waits for that fetch - before taking a
`SCRAPE` permit, so no permit is held while waiting. Failures are kept
five minutes, not the hour.

**Discovery** was measured and left alone: all 33 enabled sources in
15 s, four at once (25 s one by one), 7 s of it CPU; National
Geographic's section pages are the slowest at 7-10 s.

### 7. Writing and reviewing: the model's threads, and the correction as edits

**The writer's and reviewer's models take a thread count and a batch
size** in production (`OLLAMA_NUM_THREAD`, `OLLAMA_NUM_BATCH`, passed by
`docker-compose.prod.yml` to `pull-models.sh`, which writes them into the
variants' Modelfile; unset is Ollama's own choice, as before). Measured
for the writer (table in 5): 381 s a draft at Ollama's default threads,
298 s at 10, on the dev laptop. Machine facts, so set from
`scripts/bench_ollama.py` on the machine, not copied from here.

A draft's other steps - related news searched in the corpus and on the
web, and fetched - go through the same extractor, so the parse permit
and the page cache above apply to them too.

**The review's correction can be asked for as edits**
(`REVIEW_CORRECTION=edits`, `draft_reviewer.py`): the title, the subtitle
and `{find, replace}` pairs instead of the body written out again. An
edit applies only where its passage occurs exactly once in the body;
the result goes through `read_proposal`'s checks like any proposal, so
the rules (no new figure, no moved or dropped citation, same language,
about the same length) hold unchanged.

**Measured, and left off: the default stays `rewrite`.** `qwen3.5:9b`
on the CPU, reasoning off, each mode reviewing the same draft:

| | Draft | Correction call | Tokens in / out | Offered |
|---|---|---:|---:|---|
| rewrite | seeded, en / ca (~900 chars) | 155 / 195 s | 1,031 / 1,070 out | yes / yes |
| edits | seeded, en / ca | **79 / 98 s** | 902 / 971 out | refused (a new figure) / yes |
| rewrite | the writer's own, es, 3,278 chars | **357 s** | 1,355 / **838** | yes |
| edits | the same draft | 522 s | 1,441 / **1,384** | yes |

On the seeded drafts - a handful of planted defects, so a handful of
edits - the correction took half the time. On a draft the writer
actually wrote it took 65% more tokens: a copy editor touches nearly
every sentence, and each edit copies its sentence twice, once to find
it and once to replace it. Edits win only when there is little to
correct, which is when the correction matters least. The first call
(the scores, identical in both modes) took 266 s in one run and 133 s
in the other: hence tokens, not seconds, as the measure here.

## The 20-second fact-check (2026-10-22)

The author asked for each claim checked in about 20 seconds, never past
30, without paying for a hosted model, measured on the first ten claims
of the custom set's train half and compared with Claude checking the same
ten by hand. Measured on the desktop the work now runs on - **Intel
i9-10900 (10 cores, 20 threads), UHD 630, 32 GB, no discrete GPU**,
Ollama on the Windows host - which is two to three times faster than the
laptop the sections above measured: the same verifier-shaped call (973
prompt tokens, ~115 answer tokens) reads at 116-149 tokens a second and
writes at 11-12: 19-22 s a call once the model is loaded (`bench_ollama.py`).

### What was built

1. **Every claim says where its seconds went, in the app.** Each query's
   seconds, results and how it was answered (SearXNG, the DuckDuckGo
   fallback, memory, another claim's identical request); the claim's
   embedding, the search, the internal corpus and the pre-rank; each
   page's seconds and outcome (read, snippet only, already read, too
   slow); the ranking; the wait for the model and the model's call with
   its tokens; the claim's total. Fields on the existing events
   (`backend/CLAUDE.md`), drawn per article and per claim by
   `TimingBreakdown` on `/live` and `/`. The harness record keeps
   `search`, `pages`, `llmWait` and `llmCall`, and every report's
   response-time table shows them.
2. **Speed switches, per run** (`PipelineThresholds`; each default is the
   old behaviour, so earlier runs keep their keys):
   - `verifier_answer: compact` - a stance per source and a short reason,
     no quotes (`COMPACT_SYSTEM_PROMPT`, 200-token cap). The stance stays
     because the scorer needs it; the quote goes.
   - `evidence_prerank: lexical` - the pages to fetch chosen by the
     claim's terms alone, without embedding ~20 snippets.
   - `ranking_text: passages` - the ranker and the pertinence gate judge
     what the verifier will read, not 2,000 characters of each page.
   - `fetch_evidence_pages: false` - snippets only.
   - `claim_deadline_seconds` - the claim's budget (`deadline.py`):
     pages waited for until half of it, the model given the rest
     (permit wait included), out of time is "not checked", never a
     verdict; no second look under a deadline.
   Combined in `data/evaluation/thresholds/fast.json` (with two queries
   instead of three, three sources of 400 characters) and
   `fast_snippets.json`.
3. **The app's own settings.** `backend/.env` (not in git) named
   `llama3.1`, the 8B model, as the verifier: everything above was
   measured on `llama3.2:3b`, the model chosen on 19 Oct, and the app was
   not running it. It also had the GPU-sized limits (2 calls at once,
   30 s), which turned verdicts into "unreachable" on a CPU on 1 Oct. Now
   `llama3.2:3b`, one call at a time, 180 s, two claims at once.
4. **Measured and not built: a thread-tuned verifier.** `bench_ollama.py`
   at Ollama's default and at 6, 8, 10 and 16 threads, interleaved, twice:
   no setting beat the default on this CPU (prompt 98-149 tok/s, answer
   10.9-12.4 tok/s across all of them). The laptop's gain came from its
   hybrid cores, which this desktop does not have. No Modelfile variant.

### The contest

The rule, written before any run: `backend/data/evaluation/experiments/speed/rule.md`.
Four entries on the same ten claims (fact008-012, 015, 016, 020, 021, 036;
all ten gold labels the annotator's), back to back, alone on the machine,
two claims at once and one model call at a time as in production; and
Claude, the same ten by hand, blind to the labels, timed.

**Seconds a claim, median, and verdicts** (runs `7f1480f90bdc`,
`e289da2f72bb`, `391bc7c6958e`, `c85d8d088ec4` in
`runs/manual-train/llama3.2-3b/`, label `contest-2026-10-22`):

| | A, baseline | B, compact answer | C, fast | D, fast on snippets | Claude, by hand |
|---|---:|---:|---:|---:|---:|
| **A claim, median** | **57.2** | **39.3** | **17.8** | **14.2** | **13.1** |
| A claim, p90 / slowest | 69.2 / 70.9 | 45.8 / 58.5 | 21.0 / 25.0 | 16.2 / 21.7 | 16.9 / 26.4 |
| Retrieval | 10.3 | 9.5 | 3.3 | 2.6 | - |
| of which the web search | 2.1 | 2.0 | 1.1 | 1.1 | 1.1 searches |
| of which the pages | 2.1 | 1.6 | 1.1 | none | none |
| Ranking | 6.0 | 6.3 | 0.7 | 0.6 | - |
| The model, with its wait | 38.9 | 20.1 | 10.0 | 9.8 | - |
| of which waiting for the other claim's call | 8.8 | 1.8 | 2.3 | 2.0 | - |
| of which the call itself | 28.2 | 19.4 | 7.9 | 6.9 | - |
| Prompt / answer tokens a call | 1,308 / 131 | 1,092 / 74 | 660 / 52 | 521 / 58 | - |
| **Right against the gold label** | **3 of 10** | **2** | **2** | **2** | **7 of 10** |
| Not checked (out of time) | - | - | 0 | 0 | - |

Where the seconds went, from A to C: the answer's format took the call
from 28 to 19 s (B: half the tokens written); fewer and shorter sources
from 19 to 8 s (C: half the prompt); the lexical pre-rank and the
passage ranking took retrieval and ranking from 16 to 4 s (the ~20
snippet embeddings and the 2,000-character pages were most of it). The
deadline was never reached: the slowest claim of C took 25 s.

**By the rule**, C and D qualify on speed (median 20 s or less, p90 30 or
less), tie on verdicts (2 each), and D is faster: D wins. It is not worse
than the baseline beyond one verdict (2 against 3) and no claim ran out of
time, so it was to become the app's default, pending the whole train half
- which overturned it (below).

**What the verdicts say.** Ten claims cannot tell 2 from 3; what they show
is the same failure in every entry: the 3B answers FALSE to true claims
(A 7 FALSE of 10, B and C 8, D 6 and 2 UNVERIFIED), the lean measured on
19 Oct (FALSE to 14 of 45 TRUE claims on the train half). Speed did not
cause it and does not fix it. Claude, by hand, got all seven TRUE claims
right and missed the other three the same way: it called TRUE a claim the
annotator marked PARTIALLY_TRUE (fact009) and two marked UNVERIFIED
(fact010, fact011) - in both of those its own note said a detail (the
2028 date, the Calonge junction) could not be found, and the annotator's
rule makes that UNVERIFIED. So the gap to Claude is the model's reading,
not the search or the time: Claude read one search's results and its own
knowledge in 13 s; the fast pipeline reads three snippets or passages in
14-18 s and still says FALSE.

| Claim | Gold | Claude | A | B | C | D |
|---|---|---|---|---|---|---|
| fact008 | TRUE | TRUE, 16 s | FALSE, 37 s | FALSE, 37 s | FALSE, 15 s | UNVERIFIED, 16 s |
| fact009 | PARTIALLY_TRUE | TRUE, 14 s | FALSE, 66 s | FALSE, 58 s | FALSE, 25 s | FALSE, 22 s |
| fact010 | UNVERIFIED | TRUE, 26 s (2 searches) | FALSE, 57 s | FALSE, 44 s | FALSE, 21 s | FALSE, 13 s |
| fact011 | UNVERIFIED | TRUE, 14 s | FALSE, 58 s | FALSE, 42 s | FALSE, 19 s | FALSE, 12 s |
| fact012 | TRUE | TRUE, 13 s | TRUE, 71 s | TRUE, 34 s | TRUE, 16 s | TRUE, 13 s |
| fact015 | TRUE | TRUE, 12 s | FALSE, 69 s | FALSE, 41 s | FALSE, 19 s | FALSE, 15 s |
| fact016 | TRUE | TRUE, 11 s | FALSE, 50 s | FALSE, 43 s | FALSE, 19 s | FALSE, 14 s |
| fact020 | TRUE | TRUE, 11 s | FALSE, 51 s | FALSE, 38 s | FALSE, 15 s | UNVERIFIED, 14 s |
| fact021 | TRUE | TRUE, 11 s | TRUE, 52 s | FALSE, 37 s | FALSE, 15 s | FALSE, 14 s |
| fact036 | TRUE | TRUE, 13 s | TRUE, 58 s | TRUE, 30 s | TRUE, 17 s | TRUE, 15 s |

Claude's side: Opus 5.5 in this Claude Code session, the claim, its
language, its date and its article's URL only (no label, no reference
link), the article's own site blocked from the search; one web search,
a second only when the first left a detail open (fact010); timed with
`date` around each claim, its own thinking included. Its sources are in
`backend/data/evaluation/experiments/speed/claude.jsonl`. No paid API was
used.

### The whole train half (69 claims), as the rule requires

The winner and the runner-up on all 69 train claims, the same day, each
paired claim by claim against the 19 Oct run made alone on the CPU
(`7bcd048954e5`: 42.0%, the thorough pipeline as it then was, page heads
of 1,500 characters) with `cli report --compare`:

| | D, fast on snippets (`318d19001832`) | C, fast (`02e03d1c6bb2`) |
|---|---:|---:|
| A claim, median / p90 / slowest | **14.2 / 17.0 / 21.2 s** | 16.7 / 24.1 / 30.2 s |
| The whole half | 8 min 36 s | 11 min 17 s |
| Retrieval, ranking, the model's call (median) | 2.2, 0.6, 7.0 s | 4.8, 0.8, 7.4 s |
| Accuracy | 33.3% [21.7, 44.9] | 33.8% [23.5, 45.6] |
| Paired against 19 Oct | -8.7 points [-23.2, +5.8] | -7.4 [-20.6, +5.9] |
| Kappa (19 Oct: -0.022) | 0.070 [-0.040, 0.184] | 0.075 [-0.016, 0.168] |
| Coverage (not UNVERIFIED) | 82.6% | 98.5% |
| Not checked, out of time | 0 | 1 (fact165, at 30.2 s) |

Retrieval and ranking alone, paired: D -8.6 s [-10.1, -7.3] and -4.5 s
[-4.8, -4.1] a claim. C's slowest claim met the deadline and was reported
"not checked", as designed: a page that took 13.7 s is C's tail, and why
D, which reads none, never came near 30 s.

Against 19 Oct both intervals include zero, but that comparison is three
days, the web and a code version apart. **The thorough pipeline on the
same 69 claims, the same day** (`340a36ac8972`, `--thresholds
data/evaluation/thresholds/thorough.json`) settles it:

| | Thorough, same day | D, paired | C, paired |
|---|---:|---:|---:|
| Accuracy | **50.7%** [39.1, 62.3] | 33.3%: **-17.4 points [-30.4, -4.3]** | 33.8%: **-16.2 [-27.9, -4.4]** |
| Macro-F1 | 0.267 | 0.216 (-0.051 [-0.131, +0.034]) | 0.182 (-0.079 [-0.138, -0.023]) |
| Kappa | 0.172 [0.016, 0.330] | 0.070 | 0.075 |
| Coverage | 98.6% | 82.6% (-15.9 [-26.1, -7.2]) | 98.5% |
| A claim, median / p90 | 61.4 / 85.3 s | 14.2 / 17.0 s | 16.7 / 24.1 s |

(The thorough run shared the CPU with the test suite for part of its 37
minutes, so its seconds are a little high; the clean figure is entry A's
57.2 s. Its accuracy is the point.)

**The decision, by the rule.** Both fast profiles are measurably less
accurate than the thorough pipeline on the same claims the same day -
intervals entirely below zero - so neither becomes the default: the app
stays `thorough`, and `fast` / `fast_snippets` are one line in
`backend/.env` away. Ten claims had not been able to show it (2 against
3). It is a real trade-off and the author's to make: about 15 s a claim
and never past 30, at some 17 points of accuracy, or about 60 s at 50.7%.

Which of the profile's parts costs the points is not yet measured: the
compact answer (no quotes to ground the stance), three sources instead of
five, 400 characters instead of 700, two queries instead of three, or the
lexical pre-rank. Entry B (the compact answer alone) on the 69 claims,
then the profile with five sources at 700, would say - about 45 and 20
minutes of runs.

What none of this changes: on ten claims or on 69, the 3B's verdicts are
near chance and lean FALSE, whatever it is given to read and however
fast. Speed is now the cheap part; the reader is the limit (`evaluation.md`,
"Choosing the models": the 9B on the same pages was right on 73% of the
verdicts it committed to, against the 3B's 56%, at three times the time;
by that ratio its call on the fast profile's prompt would be some 20 s on
this desktop - an estimate, not measured).

## What was looked at and left alone

- **Search concurrency** (`SEARXNG_MAX_CONCURRENCY=2`). Raising it is the
  obvious speedup and the documented cause of engines suspending us
  (`settings.py`, 2026-09-28). SearXNG's own timeouts are already 3 s.
- **Enrichment.** 7-8 s for a 3,000-character article on this CPU, most
  of it bge-m3 over the whole article, whose vector the duplicate
  detector and the corpus compare against stored ones: truncating it
  would change every comparison with what is stored.
- **A smaller embedding model.** bge-m3 is ~570M parameters; a small
  multilingual model would embed several times faster, but changes
  `EMBEDDING_DIMENSION` (the Qdrant collection), every stored vector and
  every threshold fitted or reasoned on bge-m3's similarities. A
  re-index and a re-tuning, for seconds per article next to the model's
  minutes.
- **AI selection** already scores ten candidates per call.
- **Several claims in one model call.** Shares the article block, but a
  3B model loses the thread of a prompt that asks several things
  (`writing.md`, why the review is two calls), and one bad answer would
  lose every claim in it.

## Proposals, by what they would buy

### For scale: the model's hardware (decision for the author)

On the production VM (`e2-standard-4`, 4 vCPU, no GPU) a verdict took
31-53 s and a whole four-claim analysis 184 s, of which the model was
180 (`concurrency.md`). That is about **20 articles an hour, at most,
whatever else is done**: every analysis queues behind one CPU running
one model call at a time, and a draft (minutes) pauses all of them.
Nothing in the code changes that; only where the model runs does:

1. **A GPU for Ollama.** A data-centre GPU reads prompts in the
   thousands of tokens a second and writes in the hundreds - a verdict
   in a second or two instead of 30-50 - and serves several calls at
   once (`OLLAMA_NUM_PARALLEL` above 1, `LLM_MAX_CONCURRENCY` with it),
   which a CPU cannot. It also makes `qwen3.5:9b` affordable as the
   verifier, which `evaluation.md` found far more careful (selective
   accuracy +17.4 points) at three times a CPU's time. A configuration
   change (`deploy/gcp/` machine type with an accelerator, the NVIDIA
   runtime in `docker-compose.prod.yml`), not code.
2. **A hosted OpenAI-compatible endpoint** for the verifier: `LLMClient`
   already speaks the OpenAI wire format, so it is `LLM_BASE_URL`,
   `LLM_API_KEY` and `LLM_MODEL` in `.env`. Out of scope until the
   author names a provider and a key (`docs/goals.md`); it is also the
   one option that sends article text to a third party.
3. **A base URL per role** (`WRITER_LLM_BASE_URL`,
   `CORRECTOR_LLM_BASE_URL`, None meaning `LLM_BASE_URL`), with a permit
   per server rather than one per process. Then a draft stops pausing
   fact-checking, the verifier can run where reading is fast (a GPU, or
   this laptop's integrated GPU) and the writer where writing is (a
   CPU at the right thread count), and Salamandra can be served by
   llama.cpp as `writing.md` wants. A small change to `container.py`
   and `concurrency.py`; not made, because it splits a permit
   `concurrency.md` reasons about as one.
4. **Then, and only then, more processes.** The job store is in memory,
   one process (`job_store.py`); a queue (Redis, RQ) and several workers
   buy nothing while they all wait on one model server with one slot.

### Fewer model calls (decision for the author)

An article costs one verifier call per claim checked:
`ANCHOR_CLAIMS_MAX=4` (`ANCHOR_CLAIMS_MIN=2`). Each claim dropped is a
quarter of an article's model time. Whether three load-bearing claims
are enough is an editorial judgement and an evaluation question (how
often is the fourth claim the one that is FALSE?), not a performance
one.

### Scraping: connection reuse

`Fetcher.get` opens a new connection (TCP and TLS) for every request.
Evidence pages are nearly all on different hosts, so a pooled session
would buy little there; discovery and ingestion read many pages of one
host and would save a handshake each. Not measured, not done.

## Reproducing

- One call, split into reading and writing:
  `cd backend && uv run python ../scripts/bench_ollama.py --model llama3.2:3b [--url ...] [--options '{"num_thread": 10}'] [--repeats 3]`.
  On the production VM, run it at `num_thread` 2, 3 and 4 before
  trusting Ollama's default there.
- The excerpt comparison: `cli run --dataset data/evaluation/manual
  --split train --oracle --model llama3.2:3b --label <name>
  [--thresholds data/evaluation/thresholds/verifier_head_1500.json]`,
  then `cli report --run B --compare A`
  (`backend/data/evaluation/reports/manual-train/llama3.2-3b/08bcab0248c3/`).

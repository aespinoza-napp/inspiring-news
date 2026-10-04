# Concurrency in the fact-checking pipeline

Read this before changing anything that fans work out, adds a call to an
external service, or touches `on_phase`.

## What changed, and why it was worth doing

Fact-checking one article was strictly sequential end to end. Per claim:
two SearXNG searches one after another, five page fetches one after
another, around twenty single-text embedding calls one at a time, and one
LLM call. Then the next claim. A four-claim article spent minutes doing
nothing but waiting, and none of that waiting was on the CPU.

Three changes, in the order they were worth making:

1. **Batch the embedding calls.** `encode()` inside a list comprehension
   in `EvidenceRetriever._quick_scores`, again in `EvidenceRanker.rank`,
   and twice per claim in `ClaimSelector`. `encode_many` already existed
   and nothing in fact-checking used it. This was the largest avoidable
   wait and it needed no concurrency at all — each call on its own is
   fast, which is exactly why nobody saw it.
2. **Parallelise inside a claim.** The claim's queries, and the page
   fetches. The web search and the internal-corpus lookup, which are
   independent and used to run one behind the other for no reason.
3. **Parallelise across claims.** Claims share nothing.

## The one structural rule

**A claim's own stages stay sequential.** Retrieval feeds ranking,
ranking feeds the LLM, and the LLM's answer is what confidence
recalibration operates on. There is nothing to overlap inside a claim,
and an implementation that tried would be reordering a pipeline whose
order is its meaning.

The concurrency is *between* calls to `FactChecker._check_claim`, never
inside one.

## Threads, not asyncio

Everything reachable from the pipeline is synchronous: `httpx.Client`,
trafilatura, the embedded Qdrant client, the OpenAI SDK. Going async
would mean rewriting `InferenceClient`, `LLMClient`, `SearxngClient`,
`ExtractorService` and the routes above them, for a workload that is
pure I/O waiting and where threads are already the right tool. The
rewrite would have been most of the risk of this change and none of the
benefit.

## Why the limits live with the resource

Fan-out multiplies. `ANALYSIS_MAX_CONCURRENCY` articles ×
`CLAIM_MAX_CONCURRENCY` claims × `SCRAPE_MAX_CONCURRENCY` pages is 96
simultaneous outbound requests from a default local setup — enough for
SearXNG's upstream engines to start rate-limiting it, and enough to put
`inference/` behind its own backlog.

So the fan-out numbers in the pipeline are chosen for *clarity* — how
many claims is it sensible to watch at once — and the real ceiling is a
semaphore per external service in `src/services/concurrency.py`, applied
once per process inside the client that talks to it. A semaphore is the
right shape because the limit belongs to the resource: SearXNG does not
care whether four requests came from one article or four.

These are `settings`, not `PipelineThresholds`, and
`tests/test_invariants.py` records why: a per-request override would let
one caller decide how hard this process leans on a service every other
caller shares.

### The rule that keeps it deadlock-free

**A permit is only ever held around a leaf call.** Never acquire one and
then wait on work that needs a permit from the same resource — every
worker would hold what every other worker is waiting for.

In practice the clients (`SearxngClient`, `InferenceClient`,
`LLMClient`, `EvidenceScraper._enrich_one`) acquire around their own
single request and nothing else, and no pipeline code that fans out holds
one. `bounded_map` deliberately takes no resource for this reason: the
permit belongs inside `fn`, not around the pool.

## Ordering is not cosmetic

`bounded_map` returns results in **input order**. The evidence list's
indices are what the LLM cites by number, what `cited_evidence_indices`
refers to afterwards, and what the API response, the cache entry and the
lake record all carry. Results in completion order would silently
re-point every citation at a different source — a wrong answer, not a
crash. `tests/services/test_concurrency.py` pins it.

The same applies to the claim list in the report, which is why the
`repository.save(article)` call after the fan-out is a barrier and not
one more parallel task: the article must not be visible to its own
claims' internal-evidence lookups.

## `on_phase` is called from several threads

`FactChecker.run` wraps the callback in a lock (`_serialised`) so only
one thread is inside it at a time. Every caller that writes one would
otherwise have to be thread-safe, and none of them are: the job runner's
callback keeps per-phase timers in a closure, and the journal appends to
a list. Serialising in one place keeps their existing single-threaded
contract instead of pushing a new requirement out to everyone who passes
a callback. It serialises the *reporting*, not the work — a dict and a
list append.

`VectorRepository` holds its own lock for the same reason: the embedded
Qdrant client is file-backed with no locking of its own, and is now
reached from several claim threads and several job threads at once.

## What this means for a client reading the events

Per-claim events **interleave**. One claim can be judged while another is
still searching. Two things make that legible rather than jumpy, and both
are load-bearing:

- `claims_selected` carries the whole set of claim texts, with indices,
  before any claim has been checked. A client that learned each claim's
  text from its first event would reshuffle its own rows as the run
  progressed.
- Every per-claim event carries `claimIndex` as well as `claim`.

`frontend/src/lib/liveTrace.ts` reads the index first and falls back to
the claim text, because journalled runs from before the index exists
must still render.

`PhaseStepper` was already order-insensitive (it works from the *set* of
phases seen and counts `claim_checked` events), which is the only reason
this did not break it. Its one ordered read — the status line, taken
from the last event — now switches to "checking N claims, M done" while
claims are in flight, because during that window the last event belongs
to whichever claim happened to emit most recently and describes nothing.

## Load test: `/analyze` under real concurrency (2026-09-22)

First real measurement against a live stack — backend on the host (`uv
run uvicorn`, not the untested Docker image), `inference/` and SearXNG
up, Ollama serving `llama3.2:3b`. `scripts/load_test_analyze.py` fires N
concurrent `POST /analyze` calls against distinct real articles from the
outlet's own site, `forceRefresh=true` so every call does the full
pipeline instead of hitting the cache.

| Concurrency | Requests | Failed | p50 | p95 | max | wall clock |
|---|---|---|---|---|---|---|
| 4 | 4 | 0 | 156s | 160s | 163s | 163s |
| 6 | 6 | 1 (client-side 240s timeout) | 196s | 211s | 215s+ | 242s |

Findings:

- **The per-service semaphores hold.** At concurrency 4, every request
  succeeded with zero `llm_unreachable` claims — `LLM_MAX_CONCURRENCY=2`
  and `SEARXNG_MAX_CONCURRENCY=4` queued the excess work instead of
  failing it, exactly as designed (see "Why the limits live with the
  resource" above).
- **Latency degrades hard past 4 concurrent analyses.** p50 went from
  156s to 196s between concurrency 4 and 6, and one request exceeded the
  load tester's own 240s client timeout (not confirmed to have failed
  server-side — it may simply have still been running). `/analyze` is
  fully synchronous per request, so a client waiting on it inherits
  every claim's worth of queueing behind `LLM_MAX_CONCURRENCY=2`. This is
  the argument for steering real traffic toward `/analyze/jobs` (async +
  polling) rather than raising the sync endpoint's concurrency ceiling.
- **No article-level ceiling exists on `/analyze` itself.**
  `ANALYSIS_MAX_CONCURRENCY` bounds the bulk/job fan-out, not concurrent
  calls to the sync endpoint — each HTTP request runs independently and
  only meets the other requests at the shared per-resource semaphores.
  Six concurrent callers is six full pipelines competing for those
  semaphores at once, which is exactly what produced the latency jump
  above.
- **Not yet measured:** sustained load (this was two short bursts, not a
  soak test), and the async `/analyze/jobs` path under the same
  concurrency — worth a follow-up now that the sync path has a baseline.

## The LLM on a CPU (2026-10-01)

The load test above ran against the dev machine's Ollama, partly on its
GPU. The first analysis on the production stack - Ollama in a container,
CPU only - sent four claims' LLM calls at once under
`LLM_MAX_CONCURRENCY=2`, with Ollama running parallel slots of its own.
Sharing the same cores, each call took 90-103 s; `LLM_TIMEOUT=30` cut
three of them off twice, and those claims came back `UNVERIFIED` as "LLM
provider was unreachable". The semaphore held, as designed; the timeout
was sized for a GPU.

`docker-compose.prod.yml` sets `LLM_MAX_CONCURRENCY=1`,
`LLM_TIMEOUT=180` and `OLLAMA_NUM_PARALLEL=1`: on a CPU, parallel calls
only slow each other, and one at a time each takes the 31-53 s it needs.
The wait for the permit does not count against the timeout - the permit
is taken before the request is sent (`LLMClient.complete_json`). Same
article, re-run: four real verdicts, 184 s. The defaults in `settings`
stay as they are for a machine with a GPU.

## What the concurrency buys, measured (2026-10-04)

Until now the parallel pipeline was only *asserted*, as overlap in
tests. `scripts/bench_claim_concurrency.py` measures it: the real
`FactChecker.run` and everything under it (query planner, SearXNG
client, retriever, scraper and extraction cascade over real HTML,
ranker with its pertinence gate, verifier, `LLMClient`, scorer), with
the real permits rebuilt at the ceilings `Settings` declares. Only what
is past a socket is simulated, each call a fixed time: a search, a page,
an `/embeddings` call, a model's answer. "Sequential" swaps
`bounded_map` for a plain loop in every module that fans out. One
article, four claims, which per article was 12 searches, 20 page
fetches, 16 embedding calls and 4 LLM calls.

`cd backend && uv run python ../scripts/bench_claim_concurrency.py --scale 0.2`
(search 1 s, page 0.8 s, embeddings 0.1 s, LLM 3 s, all × 0.2; median of 3):

| Mode | Seconds | Speedup |
|---|---:|---:|
| Sequential (every fan-out a plain loop) | 8.62 | — |
| One claim at a time, concurrent inside | 5.14 | ×1.68 |
| Concurrent, declared ceilings | 2.53 | ×3.40 |
| Concurrent, `LLM_MAX_CONCURRENCY=1` | 3.09 | ×2.79 |

The same with the LLM at the 45 s a claim takes on the production CPU
(`--llm 45 --scale 0.1`, one run each; × 10 for real seconds):

| Mode | Seconds (× 10) | Speedup |
|---|---:|---:|
| Sequential | 212.7 | — |
| One claim at a time, concurrent inside | 194.8 | ×1.09 |
| Concurrent, declared ceilings | 96.9 | ×2.19 |
| Concurrent, `LLM_MAX_CONCURRENCY=1` (production) | 183.7 | ×1.16 |

What this says:

- **With a fast model, the concurrency is worth ×3.4** on one article,
  and every ceiling held: peak in flight was 2 searches, 8 fetches, 4
  embedding calls and 2 LLM calls, each exactly its ceiling.
- **On a CPU it is worth ×1.16, because the model is the work.** Four
  verdicts one at a time are 180 s of the 184 s; everything else now
  overlaps them. The "declared ceilings" row (×2.19) assumes two model
  calls run side by side at full speed each, which a GPU with parallel
  slots does and a CPU does not - the 2026-10-01 incident above. The
  simulated 184 s matches the production stack's real 184 s for the same
  shape of article, which is the best evidence the simulation is honest.
- So on the production VM the speedup is in the search and fetch time
  hidden behind the LLM, and an analysis is bounded by
  `claims × LLM seconds`. A faster model, not more threads, is what
  would make it faster.

Not measured: the live stack's before/after (the journal's timestamps
make that possible), and sustained load on `/analyze/jobs`.
`tests/test_bench_claim_concurrency.py` keeps the script runnable and
checks every ceiling through the whole pipeline at 10 ms latencies.

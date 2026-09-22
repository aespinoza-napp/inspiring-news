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

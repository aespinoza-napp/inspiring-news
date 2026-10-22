"""
Process-wide limits on the slow, shared things the pipeline reaches out
to, and the one helper that fans work out across them.

Why this exists at all
----------------------

Fact-checking an article is I/O all the way down: a SearXNG search, a
handful of page fetches, a burst of calls to inference/, one LLM call -
per claim. Those used to run strictly one after another, so an article
with four claims spent minutes doing nothing but waiting. Running them
concurrently is free latency, but only if something bounds the result:
fan-out *multiplies*. ANALYSIS_MAX_CONCURRENCY articles, each with
CLAIM_MAX_CONCURRENCY claims, each scraping SCRAPE_MAX_CONCURRENCY pages
is 3 x 4 x 8 = 96 simultaneous outbound requests from a default local
setup - enough to get SearXNG's upstream engines to rate-limit it, and
enough to queue inference/ behind its own backlog.

So the fan-out numbers are chosen for *clarity* (how many claims is it
sensible to watch at once) and the real ceiling is set here, per
resource, once per process. A semaphore is the right shape because the
limit belongs to the resource - SearXNG does not care whether the four
requests hitting it came from one article or four.

The rule that keeps this deadlock-free
--------------------------------------

**A permit is only ever held around a leaf call.** Never acquire one and
then wait on work that needs a permit from the same resource - that is
the classic bounded-pool deadlock, where every worker holds the thing
every other worker is waiting for. In practice: the clients in
`src/services/` (SearxngClient, InferenceClient, LLMClient) acquire
around their own single HTTP request and nothing else, and the pipeline
code that fans out never holds one. Keep it that way.

`bounded_map` deliberately does NOT take a resource for the same reason:
the permit belongs inside `fn`, not around the pool.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from typing import Callable, Iterable, TypeVar

from src.config.settings import settings

T = TypeVar("T")
R = TypeVar("R")


class PermitTimeout(TimeoutError):
    """
    A permit was not free within the time the caller had left. Raised
    only when the caller passed a timeout: a claim with a deadline would
    rather say "not checked" than queue past it.
    """


class BoundedResource:
    """
    A named ceiling on how many threads may be inside one external
    service at a time.

    `limit <= 0` means unbounded, which is what tests want: a fake
    collaborator has no capacity problem, and a semaphore around one
    would only add a way for a test to hang.
    """

    def __init__(self, name: str, limit: int):

        self.name = name
        self.limit = limit
        self._semaphore = threading.Semaphore(limit) if limit > 0 else None

    @contextmanager
    def permit(self, timeout: float | None = None):
        """
        Held for the `with` block. `timeout` is how long to wait for it
        before PermitTimeout; None waits as long as it takes, as every
        caller did before claims had a deadline.
        """

        if self._semaphore is None:
            yield
            return

        if not self._semaphore.acquire(timeout=timeout):
            raise PermitTimeout(f"no {self.name} permit within {timeout:.1f} s")

        try:
            yield
        finally:
            self._semaphore.release()


# One instance per external dependency, built from settings at import
# time. These are *infrastructure* limits (how much load the process may
# put on another service), not per-run pipeline thresholds - the same
# distinction that keeps ANALYSIS_MAX_CONCURRENCY in settings rather than
# in PipelineThresholds. A request cannot be allowed to raise them: that
# would let one caller decide how hard to hit a service shared by every
# other caller.

SEARXNG = BoundedResource("searxng", settings.SEARXNG_MAX_CONCURRENCY)

# Asked only after SearXNG has failed, and after its permit is released:
# nothing holding SEARXNG ever waits on this one.
DUCKDUCKGO = BoundedResource("duckduckgo", settings.DUCKDUCKGO_MAX_CONCURRENCY)

SCRAPE = BoundedResource("scrape", settings.SCRAPE_MAX_CONCURRENCY)

INFERENCE = BoundedResource("inference", settings.INFERENCE_MAX_CONCURRENCY)

LLM = BoundedResource("llm", settings.LLM_MAX_CONCURRENCY)

# Held only around the render itself, inside PlaywrightExtractionStrategy.
# Often acquired while an evidence scrape already holds SCRAPE: that is a
# different resource, and nothing holding BROWSER ever waits on SCRAPE, so
# the nesting cannot close into the bounded-pool deadlock.
BROWSER = BoundedResource("browser", settings.BROWSER_MAX_CONCURRENCY)

# Parsing a fetched page (trafilatura, BeautifulSoup): one at a time in
# the process, while the fetches around it stay concurrent. Parsing is
# pure Python on the CPU and holds the GIL, and threads parsing at once
# do not share it - they thrash it: eight extractions of one 2.6 MB page
# took 239-304 s side by side and 14.3 s one after another (2026-10-21,
# docs/decisions/performance.md); two at once were already slower than
# in turn. Not a setting: nothing past this process waits on it, and 1
# is what was measured best. Held around the parse only - after the
# fetch, inside SCRAPE or BROWSER's holders - and nothing holding it
# waits on any other resource.
PARSE = BoundedResource("parse", 1)


def bounded_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    max_workers: int,
    thread_name_prefix: str = "pipeline",
    timeout: float | None = None,
    late: Callable[[T], R] | None = None,
) -> list[R]:
    """
    `fn` over `items`, concurrently, **results in input order**.

    Order matters more than it looks: the evidence list's indices are
    what the LLM cites by number and what `cited_evidence_indices` refers
    to afterwards, so a set of results that came back in completion order
    would silently re-point every citation at a different source.

    Exceptions propagate, as they would from a list comprehension - the
    callers here already handle failure per item where a failure is
    expected (EvidenceScraper) rather than pushing it up.

    `timeout`, with `late`: stop waiting after that many seconds, and put
    `late(item)` in the place of every item not finished by then - still
    in input order. The unfinished calls are not stopped (a thread cannot
    be), they finish in the background and their results are dropped;
    what they hold (a SCRAPE permit, a page fetch) ends with them. A claim
    with a deadline uses this so one slow host cannot take the claim past
    it (docs/decisions/performance.md, "The 20-second fact-check").
    """

    materialised = list(items)

    if timeout is not None and late is None:
        raise ValueError("bounded_map: a timeout needs `late`, what stands in for an unfinished item")

    # A pool for zero or one item is pure overhead, and - more usefully -
    # keeps the single-claim and single-source paths exercising plain
    # synchronous code in tests. Not with a timeout: one slow item is
    # exactly what it is for.
    if len(materialised) <= 1 and timeout is None:
        return [fn(item) for item in materialised]

    if not materialised:
        return []

    workers = max(1, min(max_workers, len(materialised)))

    if timeout is None:
        with ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix=thread_name_prefix,
        ) as executor:
            return list(executor.map(fn, materialised))

    executor = ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix=thread_name_prefix,
    )

    try:
        futures = [executor.submit(fn, item) for item in materialised]
        wait(futures, timeout=max(0.0, timeout))
        return [
            future.result() if future.done() else late(item)
            for future, item in zip(futures, materialised)
        ]
    finally:
        # Not `with`: its exit waits for every thread, which is the wait
        # the timeout is there to cut. Queued items never start.
        executor.shutdown(wait=False, cancel_futures=True)

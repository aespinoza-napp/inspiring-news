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
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Callable, Iterable, TypeVar

from src.config.settings import settings

T = TypeVar("T")
R = TypeVar("R")


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
    def permit(self):

        if self._semaphore is None:
            yield
            return

        self._semaphore.acquire()

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

SCRAPE = BoundedResource("scrape", settings.SCRAPE_MAX_CONCURRENCY)

INFERENCE = BoundedResource("inference", settings.INFERENCE_MAX_CONCURRENCY)

LLM = BoundedResource("llm", settings.LLM_MAX_CONCURRENCY)


def bounded_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    max_workers: int,
    thread_name_prefix: str = "pipeline",
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
    """

    materialised = list(items)

    # A pool for zero or one item is pure overhead, and - more usefully -
    # keeps the single-claim and single-source paths exercising plain
    # synchronous code in tests.
    if len(materialised) <= 1:
        return [fn(item) for item in materialised]

    workers = max(1, min(max_workers, len(materialised)))

    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix=thread_name_prefix,
    ) as executor:
        return list(executor.map(fn, materialised))

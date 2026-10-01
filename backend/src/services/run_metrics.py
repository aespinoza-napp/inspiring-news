"""
What the analysis runs of this process have cost and produced, as
numbers a monitor can scrape (GET /metrics, Prometheus' text format).

The job runner already logged every phase with its duration, and the
journal kept every event - but a log line is something to read after
the fact, not something to graph or alert on. This turns the same
events into counters, with no new dependency: the text format is a few
lines of string formatting, not a reason to add a client library.

Durations are measured per *stage* - from the phase that starts one to
the phase that ends it - not between consecutive events. Claims run
concurrently, so consecutive events interleave across claims: the
job runner's "+4.66s" before a `web_results` is time since *any*
claim's last event, not how long that search took. Per-claim stages are
paired by `claimIndex`, which every per-claim event carries for this
reason (docs/decisions/concurrency.md).

In-process and in-memory, like JobStore: a restart starts from zero,
which is what Prometheus counters are allowed to do.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

# end phase -> (stage, start phase). Only phases AnalysisService and the
# fact-checker really emit; a stage whose end never arrives (a failed
# run) is simply not observed.
STAGES = {
    "scraped": ("scrape", "scraping"),
    "enriched": ("enrich", "enriching"),
    "validated": ("admission", "validating"),
    "claims_selected": ("select_claims", "selecting_claims"),
    "web_results": ("web_search", "searching_web"),
    "sources_scraped": ("scrape_sources", "scraping_sources"),
    "evidence_retrieved": ("retrieve_evidence", "retrieving_evidence"),
    "claim_checked": ("verify_claim", "verifying_claim"),
    "graph_stored": ("store_graph", "graph_storing"),
    "graph_failed": ("store_graph", "graph_storing"),
}

STARTS = {start for _, start in STAGES.values()}

OUTCOMES = {"done": "done", "cache_hit": "cache_hit", "failed": "failed"}


class RunMetrics:

    def __init__(self):

        # Shared by every concurrent run (ANALYSIS_MAX_CONCURRENCY), so
        # every write takes the lock.
        self._lock = threading.Lock()

        self._stage_seconds = defaultdict(float)
        self._stage_count = defaultdict(int)

        self._run_seconds = defaultdict(float)
        self._run_count = defaultdict(int)

        self._claims = defaultdict(int)
        self._searches = defaultdict(int)

        self._started = time.time()

    def observe_stage(self, stage: str, seconds: float) -> None:
        with self._lock:
            self._stage_seconds[stage] += seconds
            self._stage_count[stage] += 1

    def observe_run(self, outcome: str, purpose: str, seconds: float) -> None:
        with self._lock:
            self._run_seconds[(outcome, purpose)] += seconds
            self._run_count[(outcome, purpose)] += 1

    def observe_claim(self, verdict: str) -> None:
        with self._lock:
            self._claims[verdict] += 1

    def observe_search(self, result: str) -> None:
        with self._lock:
            self._searches[result] += 1

    def render(self) -> str:
        """Prometheus text exposition format, version 0.0.4."""

        with self._lock:
            stage_seconds = dict(self._stage_seconds)
            stage_count = dict(self._stage_count)
            run_seconds = dict(self._run_seconds)
            run_count = dict(self._run_count)
            claims = dict(self._claims)
            searches = dict(self._searches)

        lines = [
            "# HELP inspiring_up_since_seconds Unix time this process started counting.",
            "# TYPE inspiring_up_since_seconds gauge",
            f"inspiring_up_since_seconds {self._started:.0f}",
            "# HELP inspiring_runs_total Analysis runs finished, by outcome and purpose.",
            "# TYPE inspiring_runs_total counter",
        ]
        lines += [
            f'inspiring_runs_total{{outcome="{o}",purpose="{p}"}} {n}'
            for (o, p), n in sorted(run_count.items())
        ]

        lines += [
            "# HELP inspiring_run_seconds Wall time of finished analysis runs.",
            "# TYPE inspiring_run_seconds summary",
        ]
        for (o, p), n in sorted(run_count.items()):
            labels = f'outcome="{o}",purpose="{p}"'
            lines.append(f"inspiring_run_seconds_sum{{{labels}}} {run_seconds[(o, p)]:.3f}")
            lines.append(f"inspiring_run_seconds_count{{{labels}}} {n}")

        lines += [
            "# HELP inspiring_stage_seconds Time spent in each pipeline stage, per claim where the stage is per claim.",
            "# TYPE inspiring_stage_seconds summary",
        ]
        for stage, n in sorted(stage_count.items()):
            lines.append(f'inspiring_stage_seconds_sum{{stage="{stage}"}} {stage_seconds[stage]:.3f}')
            lines.append(f'inspiring_stage_seconds_count{{stage="{stage}"}} {n}')

        lines += [
            "# HELP inspiring_claims_checked_total Claims that reached a verdict, by verdict.",
            "# TYPE inspiring_claims_checked_total counter",
        ]
        lines += [
            f'inspiring_claims_checked_total{{verdict="{v}"}} {n}'
            for v, n in sorted(claims.items())
        ]

        # The number to alert on. A search that answers nothing still
        # ends in a verdict (UNVERIFIED), indistinguishable from a real
        # one - this is where an empty or failed search shows up.
        lines += [
            "# HELP inspiring_web_searches_total Per-claim web searches, by what came back: results, empty, or unavailable (the search itself failed).",
            "# TYPE inspiring_web_searches_total counter",
        ]
        lines += [
            f'inspiring_web_searches_total{{result="{r}"}} {n}'
            for r, n in sorted(searches.items())
        ]

        return "\n".join(lines) + "\n"


class RunClock:
    """
    One run's view of its own events: pairs each stage's start with its
    end and reports the finished ones to `metrics`. Called from the job
    runner's on_phase, which the fact-checker serialises
    (FactChecker._serialised), so this keeps no lock of its own.
    """

    def __init__(self, metrics: RunMetrics, purpose: str, clock=time.monotonic):

        self._metrics = metrics
        self._purpose = purpose
        self._clock = clock
        self._start = clock()
        self._open: dict[tuple[str, object], float] = {}

    def observe(self, phase: str, data: dict) -> None:

        now = self._clock()
        claim = data.get("claimIndex") if isinstance(data, dict) else None

        if phase in STARTS:
            self._open[(phase, claim)] = now

        if phase in STAGES:
            stage, start_phase = STAGES[phase]
            started = self._open.pop((start_phase, claim), None)
            if started is not None:
                self._metrics.observe_stage(stage, now - started)

        if phase == "web_results":
            self._metrics.observe_search(_search_result(data))

        if phase == "claim_checked" and data.get("verdict"):
            # The event carries the Verdict enum itself, whose str() is
            # "Verdict.TRUE" - which is what the first production run's
            # /metrics showed.
            verdict = data["verdict"]
            self._metrics.observe_claim(str(getattr(verdict, "value", verdict)))

        if phase in OUTCOMES:
            self._metrics.observe_run(OUTCOMES[phase], self._purpose, now - self._start)


def _search_result(data: dict) -> str:
    if data.get("searchUnavailable"):
        return "unavailable"
    return "results" if data.get("webCount") else "empty"


# One per process, like request_stats: every job runner writes here and
# GET /metrics reads it.
run_metrics = RunMetrics()

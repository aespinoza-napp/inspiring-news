"""
scripts/bench_claim_concurrency.py, kept runnable - and, while it runs,
the per-service ceilings checked through the whole real pipeline rather
than one client at a time.

The benchmark itself is a script (minutes of simulated waiting, numbers
to read rather than assert). This runs it with every latency at 10 ms,
so it costs about a second, and fails the day a constructor it wires
changes under it - which would otherwise be found the next time someone
wanted the numbers.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bench_claim_concurrency.py"

_spec = importlib.util.spec_from_file_location("bench_claim_concurrency", SCRIPT)
bench = importlib.util.module_from_spec(_spec)
# Registered before it runs: its dataclass looks its own module up.
sys.modules[_spec.name] = bench
_spec.loader.exec_module(bench)

LATENCY = bench.Latency(search=1.0, fetch=1.0, embed=1.0, llm=1.0)

# What the simulated network counts, against the ceiling meant to bound it.
BOUNDED_BY = {
    "search": "SEARXNG_MAX_CONCURRENCY",
    "fetch": "SCRAPE_MAX_CONCURRENCY",
    "embed": "INFERENCE_MAX_CONCURRENCY",
    "llm": "LLM_MAX_CONCURRENCY",
}


def test_every_ceiling_holds_through_the_whole_pipeline():

    result = bench.run_once("concurrent", 4, LATENCY, scale=0.01, overrides={})

    for kind, ceiling in BOUNDED_BY.items():
        assert result["peak"][kind] <= result["ceilings"][ceiling], (kind, result["peak"])

    # Every claim reached the model, so the run measured a whole check.
    assert result["calls"]["llm"] == 4


def test_a_lowered_ceiling_is_the_one_in_force():

    result = bench.run_once(
        "concurrent", 4, LATENCY, scale=0.01, overrides={"LLM_MAX_CONCURRENCY": 1},
    )

    assert result["peak"]["llm"] == 1


def test_the_sequential_baseline_never_overlaps():

    result = bench.run_once("sequential", 2, LATENCY, scale=0.01, overrides={})

    assert set(result["peak"].values()) == {1}
    assert result["calls"]["llm"] == 2

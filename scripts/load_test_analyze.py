#!/usr/bin/env python3
"""
Load-test POST /analyze (the sync endpoint) with concurrent requests
against a running backend, and report latency/error stats.

This is the Sprint 2 item that was "never started" (see docs/roadmap.md):
the pipeline fans out across claims, queries and page fetches now (see
docs/decisions/concurrency.md), and this is the first thing that exercises
those per-service ceilings (src/services/concurrency.py) against a real
backlog of concurrent /analyze calls, rather than against a test's single
barrier.

Requires a live backend + inference + SearXNG + Ollama - point it at the
same stack `scripts/dev.sh` brings up, or run backend/inference directly:

    cd inference && uv run uvicorn src.main:app --port 8001
    cd backend && uv run uvicorn src.main:app --port 8000

Usage:
    python scripts/load_test_analyze.py --concurrency 4
    python scripts/load_test_analyze.py --concurrency 8 --urls-file urls.txt
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import httpx

# Real, previously-analyzed articles from the outlet's own site - see
# backend/data/lake/raw/*.json. Distinct URLs so concurrent requests do
# real, independent scraping/enrichment/fact-check work rather than all
# converging on one cached or duplicate-detected article.
DEFAULT_URLS = [
    "https://inspiringnews.ai/buenas-de-la-semana/buenas-noticias-de-la-semana-7-al-11-septiembre/",
    "https://inspiringnews.ai/buenas-de-la-semana/spider-man-brand-new-day/",
    "https://inspiringnews.ai/ciencia/nanoplasticos-flor-magnetica/",
    "https://inspiringnews.ai/cultura/farmear-aura/",
    "https://inspiringnews.ai/medio-ambiente/francisco-vera-activista-climatico/",
    "https://inspiringnews.ai/sociedad/kandy-garcia-de-91-anos-ha-viajado-sola-a-70-paises/",
    "https://inspiringnews.ai/sociedad/terremoto-colombia-ayuda/",
    "https://inspiringnews.ai/sociedad/toldos-crochet-combatir-calor/",
]


@dataclass
class Result:
    url: str
    ok: bool
    status: int | None
    seconds: float
    error: str | None = None
    claims_checked: int = 0
    llm_unreachable_claims: int = 0


@dataclass
class Summary:
    results: list[Result] = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)

    def report(self) -> str:
        ok = [r for r in self.results if r.ok]
        failed = [r for r in self.results if not r.ok]
        latencies = sorted(r.seconds for r in ok)

        lines = [
            f"requests:            {len(self.results)}",
            f"succeeded:           {len(ok)}",
            f"failed:              {len(failed)}",
        ]

        if latencies:
            lines += [
                f"latency min:         {latencies[0]:.2f}s",
                f"latency p50:         {statistics.median(latencies):.2f}s",
                f"latency p95:         {latencies[int(len(latencies) * 0.95) - 1 if len(latencies) > 1 else 0]:.2f}s",
                f"latency max:         {latencies[-1]:.2f}s",
                f"latency mean:        {statistics.mean(latencies):.2f}s",
            ]

        unreachable = sum(r.llm_unreachable_claims for r in ok)
        if unreachable:
            lines.append(
                f"llm_unreachable claims: {unreachable} "
                "(provider never reached - see LLMUnavailableError)"
            )

        for r in failed:
            lines.append(f"  FAILED {r.url}: {r.error}")

        return "\n".join(lines)


def _one_request(base_url: str, url: str, force_refresh: bool, timeout: float) -> Result:

    started = time.monotonic()

    try:
        response = httpx.post(
            f"{base_url}/analyze",
            json={"urls": [url], "forceRefresh": force_refresh},
            timeout=timeout,
        )
    except httpx.TimeoutException as exc:
        return Result(url=url, ok=False, status=None, seconds=time.monotonic() - started, error=f"timeout: {exc}")
    except httpx.HTTPError as exc:
        return Result(url=url, ok=False, status=None, seconds=time.monotonic() - started, error=str(exc))

    elapsed = time.monotonic() - started

    if response.status_code != 200:
        return Result(url=url, ok=False, status=response.status_code, seconds=elapsed, error=response.text[:300])

    try:
        body = response.json()
        claims = body["results"][0].get("claims", [])
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        return Result(url=url, ok=False, status=response.status_code, seconds=elapsed, error=f"unexpected body: {exc}")

    unreachable = sum(1 for c in claims if c.get("llmUnreachable"))

    return Result(
        url=url, ok=True, status=response.status_code, seconds=elapsed,
        claims_checked=len(claims), llm_unreachable_claims=unreachable,
    )


def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0, help="per-request timeout, seconds")
    parser.add_argument("--force-refresh", action="store_true", default=True)
    parser.add_argument("--no-force-refresh", dest="force_refresh", action="store_false")
    parser.add_argument("--urls-file", type=str, default=None, help="one URL per line; defaults to DEFAULT_URLS")
    args = parser.parse_args()

    if args.urls_file:
        urls = [line.strip() for line in open(args.urls_file) if line.strip()]
    else:
        urls = DEFAULT_URLS

    # Cycle the URL pool so --concurrency can exceed the sample size -
    # each request still does independent work because force_refresh
    # bypasses the analysis cache.
    batch = [urls[i % len(urls)] for i in range(args.concurrency)]

    print(f"POST {args.base_url}/analyze x{args.concurrency} concurrent (force_refresh={args.force_refresh})")

    summary = Summary()
    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(_one_request, args.base_url, url, args.force_refresh, args.timeout)
            for url in batch
        ]
        for future in as_completed(futures):
            r = future.result()
            summary.add(r)
            tag = "OK " if r.ok else "ERR"
            print(f"  [{tag}] {r.seconds:6.2f}s  claims={r.claims_checked:<2} unreachable={r.llm_unreachable_claims}  {r.url}")

    wall = time.monotonic() - started

    print()
    print(f"wall clock:          {wall:.2f}s")
    print(summary.report())

    return 0 if all(r.ok for r in summary.results) else 1


if __name__ == "__main__":
    sys.exit(main())

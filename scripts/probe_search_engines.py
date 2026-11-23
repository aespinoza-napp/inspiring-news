#!/usr/bin/env python3
"""
Each web search engine on its own, on the same queries: which answer, how
fast, how much of what they return is on the subject, and whether they find
the pages a fact-checker cited. Retrieval only - no model, no verdict - so it
moves no figure of the thesis (2026-11-23).

The queries are the ones the pipeline itself sent: the `proposition` query
(what the claim asserts) of every claim in two recorded train runs -
AVeriTeC's train split in English (dev is never tuned on, `protocol.md`) and
the custom set's train half in Spanish, never the test half.

    cd backend && PYTHONPATH=. uv run python ../scripts/probe_search_engines.py \\
        --searxng http://127.0.0.1:8090 --out ../research/search-engines/data/probe-2026-11-23.jsonl

The instance needs SearXNG's full default roster, not the project's allowlist,
which unloads every engine it leaves out (`keep_only`: an unknown name in
`engines=` is ignored and the default engines answer instead). A throwaway one
does: `use_default_settings: true`, the json format, the project's timeouts and
its Wikipedia override (research/search-engines/README.md). One engine per
request, and one request at a time per engine with a pause between them,
because measuring an engine is also what gets an address rate-limited by it.
"""

import argparse
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from src.services.search import best_query_coverage
from src.services.fact_checker.retrieval.temporal import looks_like_fact_check, site_of


BACKEND = Path(__file__).resolve().parents[1] / "backend"

# The two recorded train runs whose queries are reused. Their records carry the
# claim, its queries by kind and, for AVeriTeC, the pages the fact-checkers cited.
RUNS = {
    "averitec-train": BACKEND / "data/evaluation/runs/averitec_train-train/retrieval-only/c5762cf541db/results.jsonl",
    "custom-train-es": BACKEND / "data/evaluation/runs/manual-train-idsd455b7b3/minicheck-ft5/90654e84cb05/results.jsonl",
}

# The allowlist's web engines (the science ones are left out: they answer any
# query with some paper, and the fact-checker weighs them at half).
ROSTER = ["duckduckgo", "startpage", "mojeek", "yahoo", "google", "brave", "yep", "bing news", "wikipedia"]

# What a default SearXNG 2026.9.8 also offers for the general and news
# categories, minus the engines for one country's language (baidu, naver,
# seznam, sogou, quark, 360search...) and the wrappers of a dictionary or a
# translator.
CANDIDATES = [
    "bing", "qwant", "duckduckgo web", "mwmbl", "privacywall", "gmx", "fireball", "tusksearch",
    "crowdview", "ayo", "encyclosearch", "resulthunter", "yandex",
    "google news", "duckduckgo news", "startpage news", "brave.news", "qwant news",
    "mojeek news", "reuters", "wikinews", "fireball news", "tusksearch news",
]

PAUSE_SECONDS = 2.0
TOP = 10


def normalised(url: str) -> str:
    """The page, whatever the scheme, `www.`, trailing slash or query string."""

    parts = urlsplit((url or "").strip())

    return parts.netloc.lower().removeprefix("www.") + parts.path.rstrip("/")


def queries() -> list[dict]:
    """One query per claim: its `proposition`, in the run's own language."""

    found = []
    seen_articles = set()

    for source, path in RUNS.items():

        for line in path.read_text().splitlines():

            record = json.loads(line)
            text = next((q["text"] for q in record.get("queries") or [] if q.get("kind") == "proposition"), None)

            if not text:
                continue

            # Several custom-set claims come from one article: keep one each,
            # so an article does not count twice for "found the story".
            article = record.get("articleUrl")

            if source == "custom-train-es":
                if article in seen_articles:
                    continue
                seen_articles.add(article)

            found.append({
                "set": source,
                "id": record["id"],
                "language": record.get("language") or "en",
                "query": text,
                "claim": record["claim"],
                # AVeriTeC: the pages its annotators cited. The custom set: the
                # article the claim was taken from.
                "gold": record.get("referenceEvidenceLinks") or ([article] if article else []),
            })

    return found


def ask(base_url: str, engine: str | None, item: dict) -> dict:
    """One request, as SearxngClient sends it, but to one engine."""

    params = {"q": item["query"], "format": "json", "language": item["language"]}

    if engine:
        params["engines"] = engine

    started = time.monotonic()

    try:
        response = httpx.get(f"{base_url}/search", params=params, timeout=15,
                             headers={"User-Agent": "InspiringNewsBot/1.0 (engine probe)"})
        seconds = time.monotonic() - started
        response.raise_for_status()
        data = response.json()
    except Exception as error:  # noqa: BLE001 - every failure is a row of the result
        return {"status": "error", "reason": f"{type(error).__name__}: {error}"[:200],
                "seconds": round(time.monotonic() - started, 2), "results": []}

    results = data.get("results") or []
    unresponsive = data.get("unresponsive_engines") or []
    reason = "; ".join(f"{name}: {why}" for name, why in unresponsive)

    if results:
        status = "ok"
    elif unresponsive:
        status = "error"
    else:
        status = "empty"

    gold = {normalised(url) for url in item["gold"]}
    gold_sites = {site_of(url) for url in item["gold"]}
    top = results[:TOP]

    return {
        "status": status,
        "reason": reason,
        "seconds": round(seconds, 2),
        "count": len(results),
        # The app's own test of whether a search answered: the best result holds
        # 35% of the query's words (search.MIN_QUERY_COVERAGE).
        "bestCoverage": best_query_coverage(item["query"], results),
        "onTopic": sum(1 for r in top if (best_query_coverage(item["query"], [r]) or 0) >= 0.35),
        "goldPage": any(normalised(r.get("url")) in gold for r in results),
        "goldSite": any(site_of(r.get("url") or "") in gold_sites for r in top),
        "factChecks": sum(1 for r in top if looks_like_fact_check(r.get("url") or "", r.get("title"))),
        "dated": sum(1 for r in top if r.get("publishedDate")),
        "results": [{"url": r.get("url"), "title": r.get("title"), "engines": r.get("engines"),
                     "publishedDate": r.get("publishedDate")} for r in top],
    }


def probe(base_url: str, engine: str | None, items: list[dict], out, lock) -> None:

    # No engine named is what the app sends: every engine the instance loads, together.
    name = engine or "(all together)"

    for index, item in enumerate(items):

        if index:
            time.sleep(PAUSE_SECONDS + random.random())

        row = {"engine": name, "inRoster": name in ROSTER, "set": item["set"], "id": item["id"],
               "language": item["language"], "query": item["query"], **ask(base_url, engine, item)}

        with lock:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{name:18} {item['id']:24} {row['status']:5} {row.get('count', 0):3} "
                  f"{row['seconds']:5.1f}s {row.get('reason', '')[:60]}", flush=True)


def main() -> None:

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--searxng", required=True, help="an instance with the full default roster")
    parser.add_argument("--engines", help="comma-separated, instead of the allowlist and the candidates")
    parser.add_argument("--mix", action="store_true",
                        help="then ask with no engine named, as the app does (point --searxng at the app's settings)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    items = queries()
    engines = args.engines.split(",") if args.engines else ROSTER + CANDIDATES

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    print(f"{len(items)} queries x {len(engines)} engines", file=sys.stderr)

    with out_path.open("a") as out, ThreadPoolExecutor(max_workers=len(engines)) as pool:
        for future in [pool.submit(probe, args.searxng, engine, items, out, lock) for engine in engines]:
            future.result()

        # Last, so it does not add to the load the single engines are measured under.
        if args.mix:
            probe(args.searxng, None, items, out, lock)


if __name__ == "__main__":
    main()

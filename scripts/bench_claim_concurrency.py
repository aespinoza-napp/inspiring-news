#!/usr/bin/env python3
"""
Benchmark the fact-checker's concurrency: sequential vs concurrent wall
time for one article, at the real concurrency ceilings, against a
simulated network with fixed latencies.

The parallel pipeline (docs/decisions/concurrency.md) was only ever
*asserted*, as overlap in tests/services/test_concurrency.py and
test_fact_checker_concurrency.py. This measures what it buys.

What is real and what is not
----------------------------

Real: `FactChecker.run` and everything under it - the query planner, the
`SearchProvider` and `SearxngClient`, the `EvidenceRetriever` with its
web-and-corpus split, the `EvidenceScraper` and the extraction cascade
(trafilatura, BeautifulSoup) over real HTML, the `EvidenceRanker` with its
pertinence gate, the `LLMVerifier`, the `LLMClient` and the
`ConfidenceScorer`. And the ceilings: each simulated call waits *inside*
the same permit the real client takes (`SEARXNG`, `INFERENCE`, `LLM`,
`SCRAPE`), rebuilt at the limits `Settings` declares, not `.env`'s.

Simulated: only what is past a socket. A SearXNG answer, a page, an
`/embeddings` response and a model's answer each take a fixed time
(`--search`, `--fetch`, `--embed`, `--llm`) and come back canned. The
embeddings are bag-of-words hashes, so a page that restates a claim is
similar to it and survives the pertinence gate, as a real one would.
Claim selection is skipped (every claim is checked): it is what decides
*which* claims, not how long checking them takes.

"Sequential" swaps `bounded_map` for a plain loop in every module that
fans out - claims, queries, web-vs-corpus, page fetches - which is the
pipeline as it was before the change, minus nothing else. The batched
embedding calls (that change's first item) stay batched in both modes:
this isolates the concurrency.

No request leaves this process: no SearXNG, no inference/, no LLM, no
outlet's web server.

Usage (from backend/, so `src` and its virtualenv resolve):

    cd backend && uv run python ../scripts/bench_claim_concurrency.py
    cd backend && uv run python ../scripts/bench_claim_concurrency.py --scale 0.2
    cd backend && uv run python ../scripts/bench_claim_concurrency.py --llm 40 --scale 0.1

`--scale` multiplies every latency, for a quicker run; the table reports
wall time as measured, in seconds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parent.parent / "backend"

sys.path.insert(0, str(BACKEND))

# Settings refuses to start without it, and backend/.env is not in git.
# Nothing here talks to Neo4j.
os.environ.setdefault("NEO4J_PASSWORD", "benchmark-unused")

import httpx  # noqa: E402
import pytest  # noqa: E402  (MonkeyPatch, to undo every patch per run)
from pydantic_core import PydanticUndefined  # noqa: E402

from src.config.settings import settings  # noqa: E402
from src.config.thresholds import PipelineThresholds  # noqa: E402
from src.database.qdrant import QdrantDatabase  # noqa: E402
from src.models.core.claim import Claim  # noqa: E402
from src.models.core.enriched_article import EnrichedArticle  # noqa: E402
from src.models.fact_checker.fact_check import Verdict  # noqa: E402
from src.models.nlp.quality import Quality  # noqa: E402
from src.models.nlp.sentiment_result import SentimentResult  # noqa: E402
from src.repositories.vector_repository import VectorRepository  # noqa: E402
from src.services import concurrency, inference_client, llms, search  # noqa: E402
from src.services.concurrency import BoundedResource  # noqa: E402
from src.services.embeddings.service import EmbeddingService  # noqa: E402
from src.services.fact_checker import fact_checker as fact_checker_module  # noqa: E402
from src.services.fact_checker.claim_selector import ClaimSelectionResult  # noqa: E402
from src.services.fact_checker.fact_checker import FactChecker  # noqa: E402
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker  # noqa: E402
from src.services.fact_checker.retrieval import evidence_retriever, scraper, search_provider  # noqa: E402
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever  # noqa: E402
from src.services.fact_checker.retrieval.scraper import EvidenceScraper  # noqa: E402
from src.services.fact_checker.retrieval.search_provider import SearchProvider  # noqa: E402
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer  # noqa: E402
from src.services.fact_checker.verification.llm_verification import LLMVerifier  # noqa: E402
from src.services.inference_client import InferenceClient  # noqa: E402
from src.services.llms import LLMClient  # noqa: E402
from src.services.scraper.extractor import ExtractorService  # noqa: E402
from src.services.scraper.fetcher import FetchedPage  # noqa: E402
from src.services.scraper.request_stats import RequestStats  # noqa: E402
from src.services.scraper.strategies.beautifulsoup import BeautifulSoupStrategy  # noqa: E402
from src.services.scraper.strategies.trafilatura import TrafilaturaStrategy  # noqa: E402


# One distinct subject per claim, so each claim's searches find pages
# about it and nothing else (`about` routes a query by shared words). Four: CLAIM_MAX_CONCURRENCY's default.
CLAIMS = [
    ("zostera", "Volunteer divers replanted 4,200 square metres of Zostera marina seagrass in the Sado estuary since 2021."),
    ("kenya", "Solar microgrids brought electricity to 12,000 homes in rural Kenya during 2024."),
    ("andalusia", "A reforestation programme planted 3 million native trees across Andalusia in 2023."),
    ("copenhagen", "Researchers in Copenhagen recovered 95% of the lithium from used electric car batteries."),
    ("patagonia", "Rangers counted 1,800 huemul deer in Patagonia national parks in 2025, double the 2015 figure."),
    ("kerala", "Kerala's coastal villages cut plastic waste on beaches by 70% in two years of community clean-ups."),
    ("rotterdam", "Rotterdam's floating farm produced 800 litres of milk a day from 40 cows in 2024."),
    ("bhutan", "Bhutan's forests absorbed three times the carbon dioxide the country emitted in 2022."),
]

PLACES = {
    "zostera": "Sado estuary", "kenya": "Kenya", "andalusia": "Andalusia",
    "copenhagen": "Copenhagen", "patagonia": "Patagonia", "kerala": "Kerala",
    "rotterdam": "Rotterdam", "bhutan": "Bhutan",
}

# The ceilings, by the names Settings declares them. Each is rebuilt from
# its declared default, so the numbers do not depend on a local .env.
CEILINGS = [
    "CLAIM_MAX_CONCURRENCY",
    "QUERY_MAX_CONCURRENCY",
    "SEARXNG_MAX_CONCURRENCY",
    "SCRAPE_MAX_CONCURRENCY",
    "INFERENCE_MAX_CONCURRENCY",
    "LLM_MAX_CONCURRENCY",
]

# Where each permit is looked up at call time: the clients import it by
# name, so patching src.services.concurrency alone would reach none of them.
PERMITS = {
    "SEARXNG": ("SEARXNG_MAX_CONCURRENCY", [concurrency, search]),
    "INFERENCE": ("INFERENCE_MAX_CONCURRENCY", [concurrency, inference_client]),
    "LLM": ("LLM_MAX_CONCURRENCY", [concurrency, llms]),
    "SCRAPE": ("SCRAPE_MAX_CONCURRENCY", [concurrency, scraper]),
}

# Every module that fans out, for the sequential baseline.
FAN_OUTS = [fact_checker_module, evidence_retriever, scraper, search_provider]

HITS_PER_QUERY = 8

WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Latency:
    search: float
    fetch: float
    embed: float
    llm: float


class Network:
    """
    Every simulated socket. Each call waits its fixed latency and is
    counted, with the most that were ever in flight at once - which is
    how the run shows the ceilings held.
    """

    def __init__(self, latency: Latency, scale: float, dimension: int):

        self.latency = latency
        self.scale = scale
        self.dimension = dimension

        self.calls: Counter = Counter()
        self.peak: Counter = Counter()

        self._in_flight: Counter = Counter()
        self._lock = threading.Lock()

    def wait(self, kind: str) -> None:

        with self._lock:
            self.calls[kind] += 1
            self._in_flight[kind] += 1
            self.peak[kind] = max(self.peak[kind], self._in_flight[kind])

        try:
            time.sleep(getattr(self.latency, kind) * self.scale)
        finally:
            with self._lock:
                self._in_flight[kind] -= 1

    # --- SearXNG: replaces httpx.get inside src.services.search -------

    def searxng_get(self, url, params=None, timeout=None, headers=None):

        self.wait("search")

        query = (params or {}).get("q", "")

        subject = about(query)

        digest = hashlib.sha1(query.encode()).hexdigest()[:8]

        results = [
            {
                "url": f"https://outlet{n}.example/{subject}/{digest}-{n}",
                "title": f"{subject.title()} report {n}",
                "content": claim_text(subject),
                "engines": ["bing"],
            }
            for n in range(HITS_PER_QUERY)
        ]

        return httpx.Response(
            200,
            json={"results": results, "unresponsive_engines": []},
            request=httpx.Request("GET", url),
        )

    # --- inference/: the transport under a real InferenceClient --------

    def inference(self, request: httpx.Request) -> httpx.Response:

        self.wait("embed")

        body = json.loads(request.content or b"{}")

        if "texts" in body:
            payload = {"embeddings": [self.vector(text) for text in body["texts"]]}
        else:
            payload = {"embedding": self.vector(body.get("text", ""))}

        return httpx.Response(200, json={**payload, "dimension": self.dimension})

    def vector(self, text: str) -> list[float]:
        """Bag of hashed words: texts that share words point the same way."""

        vector = [0.0] * self.dimension

        for word in WORD.findall(text.lower()):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimension] += 1.0

        norm = sum(value * value for value in vector) ** 0.5 or 1.0

        return [value / norm for value in vector]

    # --- the evidence pages: a Fetcher under the real strategies -------

    def get(self, url: str) -> FetchedPage:

        self.wait("fetch")

        subject = url.split("/")[3]

        text = claim_text(subject)

        html = (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{subject.title()} report</title></head><body><main><article>"
            f"<h1>{subject.title()} report</h1>"
            f"<p>{text}</p>"
            f"<p>Officials confirmed the figures this week. {text} The project's "
            "organisers said the result was well above what earlier attempts had "
            "achieved, and published the full monitoring data alongside it.</p>"
            "<p>Local residents welcomed the news, and two more regions plan to "
            "follow the same approach next year. Independent experts who reviewed "
            "the data said the method was sound and the measurements consistent "
            "with earlier surveys carried out in the same area.</p>"
            "<p>The organisers will publish a second report at the end of the year, "
            "with the costs of the project and what other groups would need to "
            "repeat it elsewhere.</p>"
            "</article></main></body></html>"
        )

        return FetchedPage(url=url, status=200, html=html)

    # --- the model: the OpenAI SDK's shape, under a real LLMClient -----

    @property
    def chat(self):
        return SimpleNamespace(completions=self)

    def create(self, **kwargs):

        self.wait("llm")

        content = json.dumps({
            "verdict": "TRUE",
            "confidence": 0.8,
            "explanation": "The first source reports it.",
            "cited_evidence": [0],
            "assessments": [{"index": 0, "stance": "supports", "quote": ""}],
        })

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def about(query: str) -> str:
    """The claim a query is about: the one it shares the most words with."""

    words = set(WORD.findall(query.lower()))

    return max(CLAIMS, key=lambda claim: len(words & set(WORD.findall(claim[1].lower()))))[0]


def claim_text(subject: str) -> str:

    return next((text for key, text in CLAIMS if key == subject), "Nothing to report.")


class SelectAll:
    """Every claim is checked: selection decides which, not how long."""

    def select(self, claims, thresholds=None, context=None):
        return ClaimSelectionResult(selected=list(claims))


def sequential_map(fn, items, max_workers=1, thread_name_prefix="pipeline"):
    return [fn(item) for item in items]


def declared(name: str):

    return type(settings).model_fields[name].default


def article(claims: int, dimension: int) -> EnrichedArticle:

    return EnrichedArticle(
        id="00000000-0000-0000-0000-00000000be0c",
        source_id="benchmark",
        url="https://benchmark.example/article",
        title="Good news from around the world",
        body=" ".join(text for _, text in CLAIMS[:claims]),
        language="en",
        published_at=datetime.now(),
        keywords=[],
        entities={},
        topics=[],
        # An entity each, as GLiNER would find: a claim without one is
        # searched by the article's headline, and every claim here would
        # then share one anchor query - which SearxngClient sends once.
        claims=[
            Claim(text=text, entities={"LOC": [PLACES[key]]}, confidence=0.9)
            for key, text in CLAIMS[:claims]
        ],
        sentiment=SentimentResult(
            label="positive", positive=0.8, neutral=0.15, negative=0.05,
            polarity=0.6, subjectivity=0.3, confidence=0.9, emotional_intensity=0.4,
        ),
        quality=Quality(
            readability=0.8, objectivity=0.8, constructiveness=0.8,
            inspirational_score=0.8, hopefulness=0.8, societal_impact=0.8, novelty=0.5,
        ),
        # Saved into the corpus after the claims are checked: a zero vector
        # has no direction to compare by.
        embedding=[1.0] + [0.0] * (dimension - 1),
        embedding_model="benchmark",
        embedding_dimension=dimension,
    )


def run_once(
    mode: str,
    claims: int,
    latency: Latency,
    scale: float,
    overrides: dict[str, int],
) -> dict:
    """One article through FactChecker.run; its wall time and what it did."""

    dimension = settings.EMBEDDING_DIMENSION

    network = Network(latency, scale, dimension)

    with pytest.MonkeyPatch.context() as patch, tempfile.TemporaryDirectory() as qdrant_dir:

        # Thresholds at their declared defaults, as the suite pins them:
        # how many candidates are fetched and kept decides how much work
        # a claim is, and that must not depend on a local .env.
        for name in (field.upper() for field in PipelineThresholds.model_fields):
            field = type(settings).model_fields.get(name)
            if field is not None and field.default is not PydanticUndefined:
                patch.setattr(settings, name, field.default)

        ceilings = {name: overrides.get(name, declared(name)) for name in CEILINGS}

        if mode == "sequential":
            ceilings = {name: 1 for name in CEILINGS}
            for module in FAN_OUTS:
                patch.setattr(module, "bounded_map", sequential_map)

        for name, value in ceilings.items():
            patch.setattr(settings, name, value)

        for resource, (setting, modules) in PERMITS.items():
            permit = BoundedResource(resource.lower(), ceilings[setting])
            for module in modules:
                patch.setattr(module, resource, permit)

        patch.setattr(search.httpx, "get", network.searxng_get)

        # A fresh singleton over the simulated transport, built before
        # anything that asks for one.
        patch.setattr(EmbeddingService, "_instance", None)
        embeddings = EmbeddingService()
        embeddings._client = InferenceClient(
            client=httpx.Client(
                base_url="http://inference.benchmark",
                transport=httpx.MockTransport(network.inference),
            )
        )

        extractor = ExtractorService(stats=RequestStats(), sources=[])
        extractor.strategies = [TrafilaturaStrategy(network), BeautifulSoupStrategy(network)]

        database = QdrantDatabase(path=qdrant_dir)

        try:
            repository = VectorRepository(database)

            checker = FactChecker(
                repository,
                claim_selector=SelectAll(),
                evidence_retriever=EvidenceRetriever(
                    repository,
                    search_provider=SearchProvider(client=search.SearxngClient()),
                    scraper=EvidenceScraper(extractor),
                ),
                ranker=EvidenceRanker(),
                verifier=LLMVerifier(client=LLMClient(client=network)),
                confidence_scorer=ConfidenceScorer(),
            )

            started = time.perf_counter()

            report = checker.run(article(claims, dimension), thresholds=PipelineThresholds())

            seconds = time.perf_counter() - started

        finally:
            database.client.close()

    verdicts = Counter(check.verdict for check in report.claim_checks)

    # The benchmark means nothing if a claim skipped the LLM (no evidence
    # survived ranking) or the run was cut short somewhere.
    if network.calls["llm"] != claims or verdicts[Verdict.TRUE] != claims:
        raise SystemExit(
            f"{mode}: expected {claims} LLM calls and TRUE verdicts, got "
            f"{network.calls['llm']} calls and {dict(verdicts)}"
        )

    return {
        "seconds": seconds,
        "calls": dict(network.calls),
        "peak": dict(network.peak),
        "ceilings": ceilings,
    }


def measure(label, mode, claims, latency, scale, overrides, repeat) -> dict:

    runs = [run_once(mode, claims, latency, scale, overrides) for _ in range(repeat)]

    seconds = [run["seconds"] for run in runs]

    result = {**runs[-1], "label": label, "median": statistics.median(seconds), "all": seconds}

    print(
        f"  {label:<44} {result['median']:7.2f} s   "
        f"(runs: {', '.join(f'{s:.2f}' for s in seconds)})",
        flush=True,
    )

    return result


def main() -> None:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--claims", type=int, default=4, help="claims in the article (max %d)" % len(CLAIMS))
    parser.add_argument("--search", type=float, default=1.0, help="seconds per SearXNG query")
    parser.add_argument("--fetch", type=float, default=0.8, help="seconds per evidence page")
    parser.add_argument("--embed", type=float, default=0.1, help="seconds per /embeddings call")
    parser.add_argument("--llm", type=float, default=3.0, help="seconds per LLM call")
    parser.add_argument("--scale", type=float, default=1.0, help="multiplies every latency")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    claims = max(1, min(args.claims, len(CLAIMS)))

    latency = Latency(args.search, args.fetch, args.embed, args.llm)

    print(
        f"{claims} claims; latency x{args.scale}: search {args.search}s, fetch {args.fetch}s, "
        f"embed {args.embed}s, LLM {args.llm}s; median of {args.repeat}\n"
    )

    results = [
        measure("sequential (every fan-out a plain loop)", "sequential", claims, latency, args.scale, {}, args.repeat),
        measure("one claim at a time, concurrent inside", "concurrent", claims, latency, args.scale,
                {"CLAIM_MAX_CONCURRENCY": 1}, args.repeat),
        measure("concurrent, declared ceilings", "concurrent", claims, latency, args.scale, {}, args.repeat),
        measure("concurrent, LLM_MAX_CONCURRENCY=1 (prod)", "concurrent", claims, latency, args.scale,
                {"LLM_MAX_CONCURRENCY": 1}, args.repeat),
    ]

    baseline = results[0]["median"]

    print("\n  speedup over sequential:")
    for result in results[1:]:
        print(f"    {result['label']:<42} x{baseline / result['median']:.2f}")

    concurrent = results[2]

    print(f"\n  calls per article: {concurrent['calls']}")
    print(f"  peak in flight:    {concurrent['peak']}")
    print(f"  ceilings:          {concurrent['ceilings']}")


if __name__ == "__main__":
    main()

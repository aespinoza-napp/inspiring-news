"""
The official AVeriTeC knowledge store as the pipeline's search.

The dataset's authors searched Google for each claim and scraped what came
back: about a thousand pages per claim, fixed, in one zip. HerO and InFact are
measured on it. For this harness it does what the live web cannot:

- **Repeatable.** The same search returns the same pages, so two runs differ
  only by what changed. Live, the same pipeline differs by 6-9 points from the
  web alone.
- **Fixed, then checked.** It was collected for the task, and
  the temporal gate still refuses any page whose address is dated too late
  (`cli averitec audit-store` counts them first). The pages carry no dates, so
  the run says `evidence_undated: keep`: the store is what vouches for them.
  That is a real weakness and the report must carry it. The authors found a leak
  in the *test* store and replaced it (Nov 2024, their README), and the dev
  store held a claim's own fact-check under another address (fact-check gate,
  retrieval/temporal.py, found on the third claim tried).
- **Offline.** No engine rate-limits it and no stranger's server is asked.

The pipeline's own stages all run: the query plan, the funnel, the ranker, the
pertinence gate, the verifier, the scorer. Only two collaborators change, and
behind their own interfaces: "search" is BM25 over this claim's pages, and
"fetch" reads the text the store already holds. So a run measures everything but
the search engine, which is the honest limit of the figure: it says nothing about
how well SearXNG finds evidence.

Pages are ranked whole by BM25 over their first `MAX_PAGE_CHARS`. The official
baseline ranks sentences; the pipeline judges pages, and picks the sentences
itself (verification/excerpts.py).
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
import zipfile
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.retrieval import temporal
from src.services.fact_checker.retrieval.query_builder import PlannedQuery, plan_arguments
from src.services.fact_checker.retrieval.search_provider import SearchProvider, registrable_domain

# Enough for the verifier's excerpts and the ranker; a few pages in the store
# run to megabytes of scraped boilerplate.
MAX_PAGE_CHARS = 60_000

# Claims are run two at a time and their queries share one index.
CACHED_CLAIMS = 3

SNIPPET_SENTENCES = 3

_WORD = re.compile(r"[^\W_]+", re.UNICODE)

# BM25's usual constants.
_K1 = 1.5
_B = 0.75


def tokens(text: str) -> list[str]:

    return [word.lower() for word in _WORD.findall(text)]


@dataclass
class Page:

    url: str

    sentences: list[str]

    counts: Counter

    length: int


class ClaimIndex:
    """One claim's pages, ranked by BM25 for a query."""

    def __init__(self, pages: list[Page]):

        self.pages = pages

        self.average = sum(page.length for page in pages) / len(pages) if pages else 0.0

        self.frequency: Counter = Counter()

        for page in pages:
            self.frequency.update(page.counts.keys())

    def search(self, query: str, limit: int) -> list[Page]:

        terms = list(dict.fromkeys(tokens(query)))

        total = len(self.pages)

        scored = []

        for position, page in enumerate(self.pages):

            score = 0.0

            for term in terms:

                seen = page.counts.get(term, 0)

                if not seen:
                    continue

                documents = self.frequency[term]

                idf = math.log(1 + (total - documents + 0.5) / (documents + 0.5))

                score += idf * seen * (_K1 + 1) / (
                    seen + _K1 * (1 - _B + _B * page.length / (self.average or 1))
                )

            if score > 0:
                # Position breaks ties, so the order never depends on a sort's
                # mood: a replay needs the same list every time.
                scored.append((-score, position, page))

        scored.sort(key=lambda item: item[:2])

        return [page for _, _, page in scored[:limit]]


def snippet_of(page: Page, query: str) -> str:
    """The sentences sharing the most words with the query, in page order."""

    terms = set(tokens(query))

    ranked = sorted(
        range(len(page.sentences)),
        key=lambda index: (-len(terms & set(tokens(page.sentences[index]))), index),
    )

    return " ".join(page.sentences[index] for index in sorted(ranked[:SNIPPET_SENTENCES]))


def title_of(page: Page) -> str:
    """The store keeps no titles: the page's first real line stands in."""

    for sentence in page.sentences:

        if len(tokens(sentence)) >= 3:
            return sentence[:150]

    return urlsplit(page.url).netloc


class KnowledgeStore:
    """
    The zip as published, read a claim at a time: unpacked it would take several
    times its 11.5 GB for what one run reads once per claim. The member for a
    claim is `<anything>/<index>.json`, one JSON object per line, with its `url`
    and `url2text`, the page's sentences.
    """

    def __init__(self, path: Path):

        self.path = Path(path)

        with zipfile.ZipFile(self.path) as archive:

            self.members: dict[int, str] = {}

            for name in archive.namelist():

                match = re.search(r"(\d+)\.jsonl?$", name)

                if match:
                    self.members[int(match.group(1))] = name

        self._lock = threading.Lock()

        self._indexes: OrderedDict[int, ClaimIndex] = OrderedDict()

    def raw_pages(self, index: int) -> list[dict]:
        """Every line stored for a claim, as written. [] for a claim it lacks."""

        member = self.members.get(index)

        if member is None:
            return []

        with zipfile.ZipFile(self.path) as archive, archive.open(member) as handle:

            lines = []

            for line in handle:

                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    # A truncated line in a scrape of a thousand pages loses
                    # that page, not the claim.
                    continue

            return lines

    def index_for(self, index: int) -> ClaimIndex:

        with self._lock:

            cached = self._indexes.get(index)

            if cached is not None:
                self._indexes.move_to_end(index)
                return cached

        built = ClaimIndex(_pages_of(self.raw_pages(index)))

        with self._lock:

            self._indexes[index] = built

            while len(self._indexes) > CACHED_CLAIMS:
                self._indexes.popitem(last=False)

        return built


def _pages_of(lines: list[dict]) -> list[Page]:
    """Each address once, and only those with text."""

    pages: dict[str, Page] = {}

    for line in lines:

        url = line.get("url")

        sentences = [str(sentence).strip() for sentence in line.get("url2text") or [] if str(sentence).strip()]

        if not url or not sentences or url in pages:
            continue

        kept, size = [], 0

        for sentence in sentences:

            if size >= MAX_PAGE_CHARS:
                break

            kept.append(sentence)
            size += len(sentence)

        words = tokens(" ".join(kept))

        if words:
            pages[url] = Page(url=url, sentences=kept, counts=Counter(words), length=len(words))

    return list(pages.values())


class KnowledgeStoreProvider(SearchProvider):
    """
    `SearchProvider` with the store as its engine. The plan, the fusion and the
    event timings are the parent's, so what a run records reads like a live one.
    Which claim's pages to search comes from the claim's own text, since the
    store is per claim and the provider is shared.
    """

    def __init__(self, store: KnowledgeStore, index_by_claim: dict[str, int]):

        # Never asked: an object the parent can hold in place of a SearXNG
        # client, so a run cannot reach the live web even by mistake.
        super().__init__(client=_NoLiveSearch())

        self.store = store

        self.index_by_claim = index_by_claim

    def search(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
        context: ArticleContext | None = None,
        language: str | None = None,
        timings: list[dict] | None = None,
    ) -> list[Evidence]:

        thresholds = thresholds or PipelineThresholds()

        index = self.index_by_claim.get(claim.text)

        if index is None:
            raise KeyError(f"not in the knowledge store's claims: {claim.text[:80]!r}")

        store_index = self.store.index_for(index)

        plan = self.plan(claim, context, language, *plan_arguments(thresholds))

        results = []

        for query in plan:

            started = time.perf_counter()

            hits = [
                self._evidence(page, query)
                for page in store_index.search(query.text, thresholds.evidence_fetch_candidates)
            ]

            results.append(hits)

            if timings is not None:
                timings.append({
                    "kind": query.kind.value,
                    "query": query.text,
                    "seconds": round(time.perf_counter() - started, 3),
                    "results": len(hits),
                    "via": "knowledge-store",
                    "error": None,
                })

        return self._fuse(plan, results)

    def search_queries(self, queries, thresholds=None, language=None, timings=None):
        # A second look plans queries with no claim attached, and the store
        # cannot be searched without one. `cli run` refuses the combination;
        # this is what would catch it reaching here anyway.
        raise ValueError("a second look cannot search the knowledge store")

    @staticmethod
    def _evidence(page: Page, query: PlannedQuery) -> Evidence:

        return Evidence(
            url=page.url,
            title=title_of(page),
            snippet=snippet_of(page, query.text),
            content=" ".join(page.sentences),
            published_at=None,
            origin=EvidenceOrigin.WEB,
            domain=registrable_domain(page.url),
            engines=["knowledge-store"],
            found_by=[query.label],
        )


class _NoLiveSearch:

    def search(self, *args, **kwargs):

        raise RuntimeError("a knowledge-store run asked the live web")


class KnowledgeStoreScraper:
    """Stands in for EvidenceScraper: the page's text is already on the Evidence."""

    def enrich(self, evidence: list[Evidence], wait: float | None = None, timings: list[dict] | None = None) -> list[Evidence]:

        if timings is not None:
            timings.extend({"url": item.url, "seconds": 0.0, "outcome": "store"} for item in evidence)

        return list(evidence)


def audit(store: KnowledgeStore, claims: list[dict]) -> dict:
    """
    What the store holds for each claim against the rule, before a run trusts
    it: pages whose own address dates them on or after the claim, and the claim's
    own fact-check. `claims`: {"index", "id", "claimDate", "factCheckUrl"}.
    Most pages have no date in their address, so this finds leaks, it does not
    prove there are none.
    """

    pages = dated = 0
    late: list[dict] = []
    fact_checks: list[dict] = []
    fact_check_like = 0
    own_site = 0
    late_claims: set[str] = set()
    missing: list[str] = []

    def comparable(url: str) -> str:

        parts = urlsplit(temporal.unarchived(url or "").strip().lower())

        return f"{parts.netloc.removeprefix('www.')}{parts.path.rstrip('/')}"

    for claim in claims:

        lines = store.raw_pages(claim["index"])

        if not lines:
            missing.append(claim["id"])
            continue

        cutoff = date.fromisoformat(claim["claimDate"])

        own = comparable(claim.get("factCheckUrl") or "")

        for line in lines:

            url = line.get("url") or ""

            pages += 1

            day = temporal.date_in_url(url)

            if day:
                dated += 1

                if day >= cutoff:
                    late.append({"id": claim["id"], "url": url, "claimDate": claim["claimDate"]})
                    late_claims.add(claim["id"])

            sentences = line.get("url2text") or [""]

            if temporal.looks_like_fact_check(url, str(sentences[0])[:200]):
                fact_check_like += 1

            if claim.get("factCheckUrl") and temporal.site_of(url) == temporal.site_of(claim["factCheckUrl"]):
                own_site += 1

            if own and comparable(url) == own:
                fact_checks.append({"id": claim["id"], "url": url})

    return {
        "claims": len(claims),
        "missing": missing,
        "pages": pages,
        "pagesWithADateInTheirAddress": dated,
        "lateCount": len(late),
        "claimsWithALatePage": len(late_claims),
        # The best estimate of how much of the undated rest is late too: the
        # share of those whose address does say, and they are not a random
        # sample of the store (news addresses date themselves).
        "lateShareOfDated": round(len(late) / dated, 4) if dated else None,
        "factCheckLike": fact_check_like,
        "onTheClaimsFactCheckSite": own_site,
        "late": late[:200],
        "factCheckCount": len(fact_checks),
        "factChecks": fact_checks[:200],
    }

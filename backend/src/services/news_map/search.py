"""
Searching the news map for an article or a name (docs/goals.md, N3).

Three ways in, in this order:

1. **Names**, from every entity a published article names: folded (case,
   accents, spaces, punctuation), a whole-word or prefix match first,
   then character-trigram similarity, so "Barça" finds "barca" and
   "lovelace" finds "Ada Lovelace".
2. **Words**, in titles (every word of the query a prefix of a title's
   word) and in topics: a query naming a topic's keyword, in English or
   in its Spanish stem (src/config/topics.py, TOPIC_KEYWORDS_ES; both
   lexicons stay complete, CLAUDE.md invariant 8), finds that topic's
   articles.
3. **Meaning**: the query embedded by inference/ and compared with every
   published article's vector, which the map index holds in memory. Not
   Qdrant: its collection holds every analysed article, published or
   not, and only the published may come back.

The third is the one that costs: one embedding of the query in
inference/, shared with the pipeline. So it is bounded (MAX_QUERY,
SEMANTIC_PER_MINUTE per client, a cache by folded query) and optional:
the type-ahead never asks for it, and when inference/ is down the search
still answers by name and word and says so.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from logging import getLogger
from typing import Callable

import numpy as np

from src.config.topics import TOPIC_KEYWORDS_ES, TOPICS
from src.services.inference_client import InferenceUnavailable
from src.services.news_map.layout import anchors
from src.services.rate_limit import RateLimited, RateLimiter

logger = getLogger(__name__)

MAX_QUERY = 200

# Per client, per minute. Meaning costs an embedding in inference/;
# names and words are in memory, and the type-ahead asks on keystrokes.
SEMANTIC_PER_MINUTE = 30
TEXT_PER_MINUTE = 300

CACHE_SECONDS = 3600
CACHE_ENTRIES = 2000

MAX_ENTITIES = 5
MAX_ARTICLES = 10
MAX_SEMANTIC = 10

# A name this similar by character trigrams (Jaccard) still matches.
TRIGRAM_FLOOR = 0.35

# bge-m3 cosine at which an article counts as close in meaning. Reasoned,
# not fitted: no labelled search set exists. On the 139 hand-labelled
# claims two random ones average 0.34 (measured 29 Oct), so 0.45 is
# above chance for any pair.
SEMANTIC_FLOOR = 0.45


def fold(text: str) -> str:
    """Lower case, no accents, punctuation as space, single spaces."""

    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()

    return " ".join(re.sub(r"[^\w\s]", " ", plain).split())


def trigrams(text: str) -> set[str]:

    padded = f"  {text} "

    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def similarity(a: str, b: str) -> float:

    x, y = trigrams(a), trigrams(b)

    return len(x & y) / len(x | y) if x and y else 0.0


def _topic_terms() -> list[tuple[str, str, bool]]:
    """(folded term, topic key, is a stem): each topic's own words, its keywords, its Spanish stems."""

    terms = []

    for key, topic in TOPICS.items():
        terms.append((fold(topic.name), key, False))
        terms.extend((fold(keyword), key, False) for keyword in topic.keywords)
        terms.extend((fold(stem), key, True) for stem in TOPIC_KEYWORDS_ES.get(key, ()))

    return [term for term in terms if term[0]]


TOPIC_TERMS = _topic_terms()


@dataclass(frozen=True)
class SearchContext:
    """What one search reads from the map index, taken under its lock."""

    version: str
    articles: list  # MapArticle
    entity_rows: list  # (Entity, article ids)
    matrix: np.ndarray | None  # unit vectors, one row per id in `matrix_ids`
    matrix_ids: list[str]


class MapSearch:

    def __init__(self, index, embed: Callable[[str], np.ndarray] | None = None, clock: Callable[[], float] = time.monotonic):

        self.index = index
        self.embed = embed
        self.clock = clock
        self.semantic_limit = RateLimiter(SEMANTIC_PER_MINUTE, clock=clock)
        self.text_limit = RateLimiter(TEXT_PER_MINUTE, clock=clock)
        self._cache: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()
        self._lock = threading.Lock()

    def search(self, query: str, client: str, semantic: bool = True) -> dict:
        """
        Raises ValueError for a query past MAX_QUERY and RateLimited when
        this client has asked too often.
        """

        if len(query) > MAX_QUERY:
            raise ValueError(f"A search is at most {MAX_QUERY} characters.")

        folded = fold(query)

        (self.semantic_limit if semantic else self.text_limit).check(client)

        if not folded:
            return {"query": query, "results": [], "semantic": "skipped"}

        context = self.index.search_context()
        key = (context.version, folded, semantic)
        now = self.clock()

        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < CACHE_SECONDS:
                self._cache.move_to_end(key)
                return {**cached[1], "query": query}

        result = self._search(folded, context, semantic)

        # A failed embedding is not cached: the next search may reach inference/.
        if result["semantic"] != "unavailable":
            with self._lock:
                self._cache[key] = (now, result)
                while len(self._cache) > CACHE_ENTRIES:
                    self._cache.popitem(last=False)

        return {**result, "query": query}

    # ------------------------------------------------------------------

    def _search(self, folded: str, context: SearchContext, semantic: bool) -> dict:

        results = self._names(folded, context) + self._words(folded, context)
        listed = {row["id"] for row in results if row["kind"] == "article"}

        status = "skipped"

        if semantic and self.embed is not None and context.matrix is not None:
            try:
                results += self._meaning(folded, context, listed)
                status = "used"
            except InferenceUnavailable:
                logger.warning("Map search: inference/ unavailable, answering by name and word only")
                status = "unavailable"

        return {"results": results, "semantic": status}

    def _names(self, folded: str, context: SearchContext) -> list[dict]:

        scored = []

        for entity, ids in context.entity_rows:

            name = fold(entity.name)
            words = name.split()

            if name == folded:
                score = 1.0
            elif name.startswith(folded) or any(word.startswith(folded) for word in words) or f" {folded}" in f" {name}":
                score = 0.9
            else:
                score = similarity(name, folded)
                if score < TRIGRAM_FLOOR:
                    continue

            scored.append((score, -len(ids), entity.name, entity, ids))

        scored.sort(key=lambda row: (-row[0], row[1], row[2]))

        by_id = {article.id: article for article in context.articles}
        rows = []

        for score, _, _, entity, ids in scored[:MAX_ENTITIES]:
            placed = [by_id[i] for i in ids if i in by_id]
            if not placed:
                continue
            rows.append({
                "kind": "entity",
                "key": entity.key,
                "name": entity.name,
                "type": entity.type,
                "articles": len(placed),
                "x": round(sum(a.x for a in placed) / len(placed), 4),
                "y": round(sum(a.y for a in placed) / len(placed), 4),
                "score": round(score, 3),
                "reason": "the name" if score >= 0.9 else "a similar name",
            })

        return rows

    def _words(self, folded: str, context: SearchContext) -> list[dict]:

        tokens = [token for token in folded.split() if len(token) >= 2]

        topics = {
            key
            for term, key, stem in TOPIC_TERMS
            if (folded.startswith(term) if stem else term == folded) or (not stem and len(term) > 3 and term in tokens)
        }

        scored = []

        for article in context.articles:

            words = fold(article.title).split()
            in_title = tokens and all(any(word.startswith(token) for word in words) for token in tokens)
            on_topic = [key for key, _ in article.topics if key in topics]

            if in_title:
                scored.append((2, article.sort_at, article, "in the title"))
            elif on_topic:
                scored.append((1, article.sort_at, article, f"about {anchors()[on_topic[0]].name}"))

        scored.sort(key=lambda row: (-row[0], -row[1], row[2].id))

        return [self._article_row(article, reason) for _, _, article, reason in scored[:MAX_ARTICLES]]

    def _meaning(self, folded: str, context: SearchContext, listed: set[str]) -> list[dict]:

        vector = np.asarray(self.embed(folded), dtype=np.float32).ravel()
        norm = float(np.linalg.norm(vector))

        if norm == 0.0 or vector.size != context.matrix.shape[1]:
            return []

        scores = context.matrix @ (vector / norm)
        order = np.argsort(-scores)
        by_id = {article.id: article for article in context.articles}

        rows = []

        for position in order:

            score = float(scores[position])

            if score < SEMANTIC_FLOOR or len(rows) >= MAX_SEMANTIC:
                break

            article_id = context.matrix_ids[position]

            if article_id in listed or article_id not in by_id:
                continue

            rows.append(self._article_row(by_id[article_id], f"close in meaning ({score:.2f})", score))

        return rows

    @staticmethod
    def _article_row(article, reason: str, score: float | None = None) -> dict:

        row = {
            "kind": "article",
            "id": article.id,
            "title": article.title,
            "x": round(article.x, 4),
            "y": round(article.y, 4),
            "reason": reason,
        }

        if score is not None:
            row["score"] = round(score, 3)

        return row

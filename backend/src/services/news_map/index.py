"""
The news map's view of the published articles.

Built on the reader's index (ReaderIndex.published), which decides which
run of an article is current and whether it is published; this adds what
the map needs of each: its place (layout.place), its day, its entities
and topics, the claims and evidence pages that relate it to others, and
its embedding. Each record is read once - its exploitation record and,
for the vector, the claims and the body, its processed one - and kept
until the reader drops it, so a request after the first costs no read.

Only what /reader may show leaves this module: no body, no lineage, no
scraped page (docs/goals.md, the news-map rules). The body is read to
rank entities by mention and then dropped.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from logging import getLogger

import numpy as np

from src.models.storage.lineage import DataLayer, build_record_id
from src.services.graph.graph_writer import claim_id, entity_key
from src.services.news_map.days import publication_day, zone_of
from src.services.news_map.layout import GROUP_ORDER, LAYOUT_VERSION, anchors, frame, place, topic_key
from src.services.news_map.search import SearchContext
from src.services.reader.views import card

logger = getLogger(__name__)

# How much one shared thing relates two articles: the graph's own weights
# (src/services/graph/graph_reader.py, RELATED_ARTICLES), so the map and
# /graph/related agree. Hand-set and explainable, not fitted. A test holds
# these to the query's literals.
CLAIM_WEIGHT = 3.0
EVIDENCE_WEIGHT = 1.5
ENTITY_WEIGHT = 2.0  # divided by the number of articles mentioning it
TOPIC_WEIGHT = 0.3

# What an article shows of its entities on the map.
TOP_ENTITIES = 5

# GLiNER's entity types, in the order a tie between two entities with the
# same mentions is broken: who before what.
ENTITY_TYPE_ORDER = ("person", "organization", "company", "country", "city", "location", "event", "product")


@dataclass(frozen=True)
class Entity:
    key: str
    name: str
    type: str


@dataclass(frozen=True)
class MapArticle:
    id: str
    record_id: str
    title: str
    language: str | None
    day: str | None
    source: str
    verdict: str | None
    group: str | None
    # Topic keys with their confidence, highest first.
    topics: tuple[tuple[str, float], ...]
    # Every entity it mentions, most mentioned first; the map shows the
    # first TOP_ENTITIES.
    entities: tuple[Entity, ...]
    # Claim id -> the claim's text, as /reader shows it.
    claims: dict[str, str]
    evidence: frozenset[str]
    x: float
    y: float
    approximate: str | None
    sort_at: float
    vector: np.ndarray | None


def _proper_name(name: str) -> bool:
    """
    GLiNER's spans include "D", "J" and "universidad" as people and
    companies (first record read, 29 Oct). A name needs two characters
    and a capital to be shown as one.
    """

    stripped = name.strip()

    return len(stripped) >= 2 and any(ch.isupper() for ch in stripped)


def ranked_entities(entities: dict | None, title: str, body: str) -> tuple[Entity, ...]:
    """
    The lake's {type: [names]} as Entity, most relevant first: named in
    the title, then by mentions in the title and body, then by type
    (ENTITY_TYPE_ORDER), then by name. One entry per key.
    """

    text = f"{title}\n{body}".casefold()
    title_folded = title.casefold()

    scored: dict[str, tuple] = {}

    for entity_type, names in (entities or {}).items():

        if not isinstance(names, list):
            continue

        type_rank = ENTITY_TYPE_ORDER.index(entity_type) if entity_type in ENTITY_TYPE_ORDER else len(ENTITY_TYPE_ORDER)

        for name in names:

            if not isinstance(name, str) or not _proper_name(name):
                continue

            shown = " ".join(name.split())
            key = entity_key(entity_type, shown)
            folded = shown.casefold()
            rank = (-(folded in title_folded), -text.count(folded), type_rank, folded)

            if key not in scored or rank < scored[key][0]:
                scored[key] = (rank, Entity(key=key, name=shown, type=entity_type))

    return tuple(entity for _, entity in sorted(scored.values(), key=lambda item: item[0]))


def _spelling(names: Counter) -> str:
    """
    How an entity named several ways is shown: the spelling most articles
    use; on a tie the one with more capitals ("Ada Lovelace" over "Ada
    lovelace"), then the first alphabetically.
    """

    return min(names, key=lambda name: (-names[name], -sum(ch.isupper() for ch in name), name))


def _vector(article: dict) -> np.ndarray | None:

    embedding = article.get("embedding")

    if not isinstance(embedding, list) or not embedding:
        return None

    try:
        vector = np.asarray(embedding, dtype=np.float32)
    except (TypeError, ValueError):
        return None

    return vector if vector.ndim == 1 and np.isfinite(vector).all() else None


def build_article(entry, exploitation: dict, processed: dict | None, names, countries: dict[str, str]) -> MapArticle:
    """One published article's map entry, from its two records."""

    article = (processed or {}).get("article") or {}
    fact_check = (processed or {}).get("fact_check") or {}

    shown = card(exploitation, processed, names)
    title = shown.get("headline") or ""

    vector = _vector(article)

    placement = place(entry.reader_id, exploitation.get("topics"), vector, exploitation.get("primary_topic"))

    checks = [check for check in fact_check.get("claim_checks") or [] if isinstance(check, dict)]

    claims = {claim_id(check["claim"]): str(check["claim"]) for check in checks if check.get("claim")}

    evidence = frozenset(
        str(item.get("url"))
        for check in checks
        for item in check.get("evidence") or []
        if isinstance(item, dict) and item.get("url")
    )

    confidences = {}

    for item in exploitation.get("topics") or []:
        if isinstance(item, dict):
            key = topic_key(item.get("topic"))
            if key and isinstance(item.get("confidence"), (int, float)):
                confidences.setdefault(key, round(float(item["confidence"]), 4))

    source_id = exploitation.get("source_id")

    day = publication_day(
        exploitation.get("published_at"),
        (exploitation.get("lineage") or {}).get("produced_at"),
        zone_of(countries.get(source_id or "")),
    )

    return MapArticle(
        id=entry.reader_id,
        record_id=entry.record_id,
        title=title,
        language=exploitation.get("language"),
        day=day.isoformat() if day else None,
        source=(shown.get("source") or {}).get("name") or "",
        verdict=(shown.get("verdict") or {}).get("display"),
        group=placement.group,
        topics=tuple((key, confidences.get(key, 0.0)) for key in placement.topics),
        entities=ranked_entities(exploitation.get("entities"), title, str(article.get("body") or "")),
        claims=claims,
        evidence=evidence,
        x=placement.x,
        y=placement.y,
        approximate=placement.approximate,
        sort_at=entry.sort_at,
        vector=vector,
    )


class MapIndex:

    def __init__(self, lake, reader, names, countries: dict[str, str] | None = None):

        self.lake = lake
        self.reader = reader
        self.names = names
        self.countries = countries or {}

        self._lock = threading.Lock()

        self._version: tuple[str, ...] | None = None
        self._by_record: dict[str, MapArticle] = {}

        # Rebuilt with the set of articles.
        self._articles: list[MapArticle] = []
        self._by_id: dict[str, MapArticle] = {}
        self._mentions: dict[str, set[str]] = {}
        self._with_claim: dict[str, set[str]] = {}
        self._with_evidence: dict[str, set[str]] = {}
        self._with_topic: dict[str, set[str]] = {}
        self._entities: dict[str, Entity] = {}

        # Serialised payloads, by ETag: the same set of articles and the
        # same filter give the same bytes.
        self._payloads: dict[str, bytes] = {}

        # Every vector as a unit row, for search by meaning (search.py).
        self._matrix: np.ndarray | None = None
        self._matrix_ids: list[str] = []

    # ------------------------------------------------------------------
    # Keeping in step
    # ------------------------------------------------------------------

    def refresh(self) -> None:

        entries = self.reader.published()
        version = tuple(entry.record_id for entry in entries)

        with self._lock:

            if version == self._version:
                return

            kept: dict[str, MapArticle] = {}

            for entry in entries:

                current = self._by_record.get(entry.record_id)

                if current is None:
                    current = self._read(entry)

                if current is not None:
                    kept[entry.record_id] = current

            self._by_record = kept
            self._version = version
            self._rebuild([kept[entry.record_id] for entry in entries if entry.record_id in kept])

    def _read(self, entry) -> MapArticle | None:

        exploitation = self.lake.get(DataLayer.EXPLOITATION, entry.record_id)

        if exploitation is None:
            return None

        processed = self.lake.get(
            DataLayer.PROCESSED,
            build_record_id(DataLayer.PROCESSED, entry.article_id, entry.run_id),
        )

        try:
            return build_article(entry, exploitation, processed, self.names, self.countries)
        except Exception:  # noqa: BLE001 - one odd record must not empty the map
            logger.warning("News map skips record %s", entry.record_id, exc_info=True)
            return None

    def _rebuild(self, articles: list[MapArticle]) -> None:
        """Caller holds the lock."""

        mentions: dict[str, set[str]] = defaultdict(set)
        with_claim: dict[str, set[str]] = defaultdict(set)
        with_evidence: dict[str, set[str]] = defaultdict(set)
        with_topic: dict[str, set[str]] = defaultdict(set)
        spellings: dict[str, Counter] = defaultdict(Counter)
        kinds: dict[str, str] = {}

        for article in articles:

            for entity in article.entities:
                mentions[entity.key].add(article.id)
                spellings[entity.key][entity.name] += 1
                kinds.setdefault(entity.key, entity.type)

            for claim in article.claims:
                with_claim[claim].add(article.id)

            for url in article.evidence:
                with_evidence[url].add(article.id)

            for key, _ in article.topics:
                with_topic[key].add(article.id)

        self._articles = articles
        self._by_id = {article.id: article for article in articles}
        self._mentions = dict(mentions)
        self._with_claim = dict(with_claim)
        self._with_evidence = dict(with_evidence)
        self._with_topic = dict(with_topic)
        self._entities = {
            key: Entity(key=key, name=_spelling(names), type=kinds[key]) for key, names in spellings.items()
        }
        self._payloads = {}

        with_vectors = [a for a in articles if a.vector is not None and a.vector.size]
        sizes = {a.vector.size for a in with_vectors}

        if with_vectors and len(sizes) == 1:
            matrix = np.vstack([a.vector for a in with_vectors]).astype(np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._matrix = matrix / norms
            self._matrix_ids = [a.id for a in with_vectors]
        else:
            # None at all, or two embedding sizes (a model change half
            # way through the lake): meaning is not searched until one
            # size is left, rather than compared across models.
            self._matrix = None
            self._matrix_ids = []

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def articles(self, day: str | None = None) -> list[MapArticle]:

        self.refresh()

        with self._lock:
            articles = list(self._articles)

        return [article for article in articles if day is None or article.day == day]

    def entity(self, key: str) -> Entity | None:
        """A name some published article mentions, by the graph's key."""

        self.refresh()

        with self._lock:
            return self._entities.get(key)

    def get(self, article_id: str) -> MapArticle | None:

        self.refresh()

        with self._lock:
            return self._by_id.get(article_id)

    def search_context(self):
        """What one search reads, taken together under the lock (search.py)."""

        self.refresh()

        with self._lock:
            return SearchContext(
                version=hashlib.sha256(json.dumps(list(self._version or ())).encode()).hexdigest()[:16],
                articles=list(self._articles),
                entity_rows=[(self._entities[key], sorted(ids)) for key, ids in self._mentions.items()],
                matrix=self._matrix,
                matrix_ids=list(self._matrix_ids),
            )

    def etag(self, *parts: str) -> str:

        self.refresh()

        with self._lock:
            version = self._version or ()

        digest = hashlib.sha256(
            json.dumps([LAYOUT_VERSION, list(version), list(parts)]).encode("utf-8")
        ).hexdigest()[:24]

        return f'"{digest}"'

    def payload(self, kind: str, build, *parts: str) -> tuple[str, bytes]:
        """(ETag, gzipped JSON) for a payload, built once per set of articles and filter."""

        tag = self.etag(kind, *parts)

        with self._lock:
            cached = self._payloads.get(tag)

        if cached is None:
            body = json.dumps(build(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            # Level 4, not 6: on 10k stories, 21 ms against 185 ms for an
            # output 6% larger (254 KB against 239 KB), measured 29 Oct.
            cached = gzip.compress(body, compresslevel=4, mtime=0)

            with self._lock:
                self._payloads[tag] = cached

        return tag, cached

    def articles_document(self, day: str | None = None) -> dict:
        """
        The articles as columns: one list per field, the same index across
        lists. Smaller than one object per article and decoded straight
        into typed arrays (docs/goals.md, N8). Entities and sources as
        indices into tables in the same document.
        """

        articles = self.articles(day)
        topic_index = {key: index for index, key in enumerate(anchors())}

        sources: dict[str, int] = {}
        entities: dict[str, int] = {}
        entity_rows: list[dict] = []

        def source_ref(name: str) -> int:
            return sources.setdefault(name, len(sources))

        def entity_ref(entity: Entity) -> int:
            if entity.key not in entities:
                entities[entity.key] = len(entity_rows)
                entity_rows.append({"k": entity.key, "n": entity.name, "t": entity.type})
            return entities[entity.key]

        columns: dict[str, list] = {
            "id": [], "title": [], "lang": [], "day": [], "src": [], "g": [],
            "t": [], "e": [], "v": [], "x": [], "y": [], "approx": [],
        }

        for article in articles:
            columns["id"].append(article.id)
            columns["title"].append(article.title)
            columns["lang"].append(article.language)
            columns["day"].append(article.day)
            columns["src"].append(source_ref(article.source))
            columns["g"].append(GROUP_ORDER.index(article.group) if article.group else -1)
            columns["t"].append([topic_index[key] for key, _ in article.topics])
            columns["e"].append([entity_ref(entity) for entity in article.entities[:TOP_ENTITIES]])
            columns["v"].append(article.verdict)
            columns["x"].append(round(article.x, 4))
            columns["y"].append(round(article.y, 4))
            columns["approx"].append(article.approximate)

        return {
            **frame(),
            "day": day,
            "count": len(articles),
            "sources": list(sources),
            "entities": entity_rows,
            "articles": columns,
        }

    def entities_document(self, limit: int = 500) -> dict:
        """
        The entities of more than one published article, most mentioned
        first, each at the mean of its articles' places.
        """

        self.refresh()

        with self._lock:
            mentions = {key: set(ids) for key, ids in self._mentions.items() if len(ids) > 1}
            by_id = dict(self._by_id)
            table = dict(self._entities)

        rows = []

        for key, ids in sorted(mentions.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]:

            placed = [by_id[article_id] for article_id in ids if article_id in by_id]

            if not placed:
                continue

            rows.append({
                "k": key,
                "n": table[key].name,
                "t": table[key].type,
                "c": len(placed),
                "x": round(sum(a.x for a in placed) / len(placed), 4),
                "y": round(sum(a.y for a in placed) / len(placed), 4),
            })

        return {"layout": LAYOUT_VERSION, "count": len(rows), "entities": rows}

    def links(self, article_id: str, limit: int = 10) -> dict | None:
        """
        One article's topics, entities and related articles, scored as
        /graph/related scores them but from the lake, so the map's links
        work whether or not Neo4j is up.
        """

        self.refresh()

        with self._lock:
            article = self._by_id.get(article_id)

            if article is None:
                return None

            by_id = self._by_id
            mentions = self._mentions
            with_claim = self._with_claim
            with_evidence = self._with_evidence
            with_topic = self._with_topic

            via: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)

            def add(other: str, kind: str, label: str, weight: float) -> None:
                if other == article.id:
                    return
                previous = via[other].get((kind, label), 0.0)
                via[other][(kind, label)] = max(previous, weight)

            for claim, text in article.claims.items():
                for other in with_claim.get(claim, ()):
                    add(other, "claim", text, CLAIM_WEIGHT)

            for url in article.evidence:
                for other in with_evidence.get(url, ()):
                    add(other, "evidence", url, EVIDENCE_WEIGHT)

            for entity in article.entities:
                sharing = mentions.get(entity.key, set())
                for other in sharing:
                    add(other, "entity", entity.name, ENTITY_WEIGHT / len(sharing))

            for key, _ in article.topics:
                for other in with_topic.get(key, ()):
                    add(other, "topic", anchors()[key].name, TOPIC_WEIGHT)

            entity_counts = {entity.key: len(mentions.get(entity.key, ())) for entity in article.entities}

        scored = sorted(
            ((sum(reasons.values()), other, reasons) for other, reasons in via.items() if other in by_id),
            key=lambda item: (-item[0], item[1]),
        )[:limit]

        return {
            "id": article.id,
            "title": article.title,
            "x": round(article.x, 4),
            "y": round(article.y, 4),
            "topics": [
                {"key": key, "name": anchors()[key].name, "confidence": confidence}
                for key, confidence in article.topics
            ],
            "entities": [
                {"key": e.key, "name": e.name, "type": e.type, "articles": entity_counts.get(e.key, 1)}
                for e in article.entities[:TOP_ENTITIES]
            ],
            "related": [
                {
                    "id": other,
                    "title": by_id[other].title,
                    "x": round(by_id[other].x, 4),
                    "y": round(by_id[other].y, 4),
                    "score": round(score, 4),
                    "via": [
                        {"kind": kind, "via": label, "weight": round(weight, 4)}
                        for (kind, label), weight in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
                    ],
                }
                for score, other, reasons in scored
            ],
        }

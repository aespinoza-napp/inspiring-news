"""
The news map read from the positive graph instead of the lake: every
article the graph holds, checked or not, or those of one `source_id`.
Asked for on 2026-11-17, to show the 187 posts of the WordPress import
(inspiringnews-buenasnoticias.WordPress.2026-11-03.xml,
`wordpress:inspiringnews.ai`), which the lake never publishes - an import
is stored, never publishable - so the lake's map can never show them
(docs/decisions/news-map.md, "Reading from the graph").

The default since 2026-11-23, by the author's request ("I just want to use
the full data based on the one provided by the knowledge graph"): the
import and every analysis the pipeline wrote, 199 stories that day.
`MAP_SOURCE=lake` is the published articles' map; `MAP_GRAPH_SOURCE_ID`
narrows the graph to one set. Only `NEO4J_URI`, the positive graph: the
Devastating edition's graph is not read, by request.

Everything after the read is the lake map's own: `place` puts each
article, `ranked_entities` orders its names, and MapIndex serves the
payloads, links, search and For you from the same MapArticle. What the
graph does not hold is left out rather than made up:

- **No vector.** The graph keeps no embedding, so an article sits at its
  topic's anchor with the offset its id gives (`approx: "no_vector"`), and
  search by meaning answers by name and word only.
- **The verdict the graph recorded, and only that.** The import was not
  checked, so its posts say "not checked". An article the pipeline
  checked shows its `overall_verdict` as the graph holds it (worst claim
  wins), and nothing else of the check: an article out of the graph shows
  no verdict rather than a wrong one. Until 2026-11-23 the map read only
  the import and showed no verdict at all.
- **No evidence.** Claims are nodes shared by every article with the same
  sentence, so a claim's CHECKED_AGAINST pages may belong to another
  article's check. Related articles are joined by shared claims, names
  and topics only.
- **Entities ranked without the body.** The lake map counts a name's
  mentions in the body, which the graph does not keep; here they are
  counted in the title and the article's claims, which are its sentences.

Two additions of 17 Nov, asked for by the author:

- **More names.** Every name an article has, up to TOP_ENTITIES, leaves
  the server, not the lake map's five, so the universe's network shows
  every name two stories share rather than only their top five.
- **The WordPress labels** (`MAP_GRAPH_LABELS`, optional): the research
  notebook's `wordpress-labels.json` (research/wordpress-import/), each
  post's WordPress section, categories and tags and the topics of ours
  they point to. Our classifier's topics still decide where a story goes.
  A story it gave no topic goes to its closest topic from WordPress
  (`approx: "wordpress_topic"`) instead of the rim, and every story's links
  carry its WordPress labels. The graph keeps no WordPress taxonomy, so
  they come from the dump, read by the notebook.

And one of 20 Nov, asked for by the author ("the photography is so
important in the news"): **each story's photos**. The graph keeps an
article's lead photo since then (Article.image_url, the featured photo of
an imported post), a link to the site. With `MAP_IMAGES_DIR`, the folder
scripts/wordpress_images.py downloads a post's photos into, the map serves
those copies instead (GET /map/images/{name}): the 768 px size and the
thumbnail, and every photo of the post's text in its panel. A story whose
photo was not downloaded shows the site's; one with none, none.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime
from logging import getLogger
from pathlib import Path

from src.database.neo4j_client import GraphUnavailable
from src.services.news_map.days import publication_day, zone_of
from src.services.news_map.index import MapArticle, MapIndex, ranked_entities
from src.services.news_map.layout import anchors, place, topic_key
from src.services.reader.views import reader_id

logger = getLogger(__name__)

# How long a read of the graph is served before the next one. The import
# does not change; a new analysis written to the graph shows up within it.
REFRESH_SECONDS = 30.0

READ_TIMEOUT = 10.0

# How many of an article's names the map sends. The import's posts name 14
# at the median and 50 at most (research/wordpress-import/).
TOP_ENTITIES = 40

# One row per article; pattern comprehensions rather than CALL subqueries,
# so the same text runs on Neo4j 4 and 5. Only what MapArticle needs.
# `$source` null reads every article: the pipeline's analyses carry
# `source_id` null, "web" or a configured source's id, never one value.
ARTICLES = """
MATCH (a:Article)
WHERE $source IS NULL OR a.source_id = $source
RETURN a.id AS graph_id, a.url AS url, a.title AS title, a.language AS language,
       a.published_at AS published_at, a.analyzed_at AS analyzed_at, a.run_id AS run_id,
       a.source_id AS source_id, a.image_url AS image_url, a.image_alt AS image_alt,
       a.overall_verdict AS verdict,
       [(a)-[:PUBLISHED_BY]->(s:Source) | coalesce(s.name, s.domain)][0] AS source,
       [(a)-[r:ABOUT]->(t:Topic) | {topic: t.name, confidence: r.confidence}] AS topics,
       [(a)-[:MENTIONS]->(e:Entity) | {name: e.name, type: e.type}] AS entities,
       [(a)-[:CONTAINS_CLAIM]->(c:Claim) | {id: c.id, text: c.text}] AS claims
"""


# The verdicts an article's node may hold (models/fact_checker/fact_check.py's
# Verdict). Anything else is shown as no verdict: the label becomes a CSS
# class in the universe, so it must be one the page knows.
VERDICTS = frozenset({"TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING", "UNVERIFIED"})


# What a downloaded photo's file may be called (scripts/wordpress_images.py
# names them "<attachment id>-<size>.<ext>"): nothing with a path in it.
IMAGE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.(?:png|jpe?g|webp|gif|avif)$")

# The size a story is shown at, and the size of its thumbnail, by
# WordPress's names: the first one downloaded of each list. The WebP copies
# scripts/optimize_map_photos.py makes come first (2026-11-23: the PNGs
# made the universe slow to load, 212 KB at the median for the 768 px one
# against 35 KB as WebP); without them, the PNGs as before.
SHOWN_SIZES = ("medium_large_webp", "medium_large", "large", "full")
THUMB_SIZES = ("thumbnail_webp", "thumbnail", "medium", "medium_large")
# 480 px wide, for the hover card and the selected story's photo in space:
# what the map document carries (`img`), so a pointer crossing stories asks
# for 17 KB each, not the panel's 768 px.
SMALL_SIZES = ("small_webp",)
FULL_SIZES = ("full_webp", "full")


def _web_address(url) -> str | None:
    """A photo the graph names by address: only http(s), never another scheme into an <img>."""

    return url if isinstance(url, str) and url.startswith(("https://", "http://")) else None


def served_photo(photo: dict) -> dict:
    """
    One photo of the images manifest as the universe shows it: the
    downloaded size closest to 768 px and the thumbnail, as paths under the
    map, else the site's address.
    """

    files = {size: name for size, name in (photo.get("files") or {}).items() if isinstance(name, str) and IMAGE_FILE.match(name)}

    shown = next((files[size] for size in SHOWN_SIZES if size in files), None)
    thumb = next((files[size] for size in THUMB_SIZES if size in files), None)
    small = next((files[size] for size in SMALL_SIZES if size in files), None)
    full = next((files[size] for size in FULL_SIZES if size in files), None)
    address = _web_address(photo.get("url"))

    return {
        "src": f"/images/{shown}" if shown else address,
        "small": f"/images/{small}" if small else None,
        "thumb": f"/images/{thumb}" if thumb else None,
        # The original, for a reader who opens the photo: the copy, else the site's.
        "full": f"/images/{full}" if full else address,
        "alt": photo.get("alt"),
        "caption": photo.get("caption"),
        "featured": bool(photo.get("featured")),
    }


def _timestamp(value) -> float:

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def article_from_graph(row: dict, countries: dict[str, str], labels: dict | None = None,
                       photos: list[dict] | None = None) -> MapArticle:
    """
    One graph Article, with its topics, names and claims, as the map shows
    it. `labels` is its entry in the WordPress labels, if any: its closest
    topic places it when our classifier gave it none. `photos` are its
    downloaded photos (served_photo), the featured one first; without them,
    the photo the graph links to.
    """

    url = str(row["url"])
    article_id = reader_id(url)
    title = row.get("title") or ""

    topics = [
        {"topic": item.get("topic"), "confidence": item.get("confidence")}
        for item in row.get("topics") or []
        if isinstance(item, dict)
    ]

    from_wordpress = False

    if not any(topic_key(item["topic"]) for item in topics) and topic_key((labels or {}).get("closest_topic")):
        # No confidence: the classifier did not give it; WordPress's labels did.
        topics = [{"topic": labels["closest_topic"], "confidence": 0.0}]
        from_wordpress = True

    placement = place(article_id, topics, None)

    confidences: dict[str, float] = {}

    for item in topics:
        key = topic_key(item["topic"])
        if key and isinstance(item["confidence"], (int, float)):
            confidences.setdefault(key, round(float(item["confidence"]), 4))

    claims = {
        str(item["id"]): str(item["text"])
        for item in row.get("claims") or []
        if isinstance(item, dict) and item.get("id") and item.get("text")
    }

    names: dict[str, list[str]] = defaultdict(list)

    for item in row.get("entities") or []:
        if isinstance(item, dict) and item.get("type") and isinstance(item.get("name"), str):
            names[item["type"]].append(item["name"])

    day = publication_day(
        row.get("published_at"),
        row.get("analyzed_at"),
        zone_of(countries.get(row.get("source_id") or "")),
    )

    main = (photos or [None])[0] or {
        "src": _web_address(row.get("image_url")), "thumb": None, "alt": row.get("image_alt"),
    }

    return MapArticle(
        id=article_id,
        record_id=f"graph:{row.get('graph_id')}:{row.get('run_id')}",
        title=title,
        language=row.get("language"),
        day=day.isoformat() if day else None,
        source=row.get("source") or "",
        verdict=row.get("verdict") if row.get("verdict") in VERDICTS else None,
        group=placement.group,
        topics=tuple((key, confidences.get(key, 0.0)) for key in placement.topics),
        entities=ranked_entities(dict(names), title, "\n".join(sorted(claims.values()))),
        claims=claims,
        evidence=frozenset(),
        x=placement.x,
        y=placement.y,
        z=placement.z,
        approximate="wordpress_topic" if from_wordpress else placement.approximate,
        sort_at=_timestamp(row.get("published_at") or row.get("analyzed_at")),
        vector=None,
        # The 480 px copy when there is one: the map's columns carry the size
        # the hover card and the photo in space show; the panel asks for its
        # 768 px through the story's links.
        image=main.get("small") or main["src"],
        thumb=main["thumb"],
        image_alt=main.get("alt") or row.get("image_alt"),
        url=url,
    )


class GraphMapIndex(MapIndex):
    """
    MapIndex over the graph's articles: all of them, or one source_id's.
    Reads them all at most every REFRESH_SECONDS, outside the index's lock, so a request
    during a read is answered from the last one.

    Neo4j down: the last read is served and the next is tried after
    REFRESH_SECONDS. Down before any read succeeded, GraphUnavailable goes
    to the route, which answers 503 - an empty map would read as "nothing
    was imported".
    """

    top_entities = TOP_ENTITIES

    # The import is never published and the analyses are not all: the
    # newsroom's reader page would answer 404 for most of these stories.
    reader_pages = False

    def __init__(self, graph, source_id: str | None = None, countries: dict[str, str] | None = None, clock=time.monotonic,
                 labels_path: str | None = None, images_dir: str | None = None):

        super().__init__(lake=None, reader=None, names=None, countries=countries)

        self.graph = graph
        # Empty or None: every article of the graph.
        self.source_id = source_id or None
        self.clock = clock
        self.labels_path = labels_path or None

        self._fetched_at: float | None = None
        self._fetch_lock = threading.Lock()

        # The WordPress labels by map id, rebuilt with the articles.
        self._labels: dict[str, dict] = {}

        # The downloaded photos (MAP_IMAGES_DIR): each story's, by map id,
        # and every file the manifest lists - the only ones served.
        self.images_dir = Path(images_dir) if images_dir else None
        self._photos: dict[str, list[dict]] = {}
        self._image_files: frozenset[str] = frozenset()

    def _read_labels(self) -> tuple[str, dict[str, dict]]:
        """(a stamp of the file, its entries by URL). A missing or broken file is no labels, said once per read."""

        if not self.labels_path:
            return "", {}

        try:
            stamp = str(os.stat(self.labels_path).st_mtime_ns)
            entries = json.loads(open(self.labels_path, encoding="utf-8").read()).get("articles") or {}
        except (OSError, ValueError, AttributeError):
            logger.warning("News map: the WordPress labels at %s could not be read", self.labels_path, exc_info=True)
            return "unreadable", {}

        return stamp, {str(url): entry for url, entry in entries.items() if isinstance(entry, dict)}

    def _read_images(self) -> tuple[str, dict[str, list[dict]], frozenset[str]]:
        """
        (a stamp of the manifest, each post's photos by URL as served, the
        files it lists that are there). No folder is no photos of ours; a
        missing or broken manifest is the same, said once per read.
        """

        if not self.images_dir:
            return "", {}, frozenset()

        manifest = self.images_dir / "manifest.json"

        try:
            stamp = str(manifest.stat().st_mtime_ns)
            posts = json.loads(manifest.read_text(encoding="utf-8")).get("posts") or {}
        except (OSError, ValueError, AttributeError):
            logger.warning("News map: the images manifest at %s could not be read", manifest, exc_info=True)
            return "unreadable", {}, frozenset()

        photos: dict[str, list[dict]] = {}
        files: set[str] = set()

        for url, entry in posts.items():

            listed = [photo for photo in (entry or {}).get("images") or [] if isinstance(photo, dict)] if isinstance(entry, dict) else []

            for photo in listed:
                for name in (photo.get("files") or {}).values():
                    if isinstance(name, str) and IMAGE_FILE.match(name) and (self.images_dir / name).is_file():
                        files.add(name)

            # A file the manifest names but the folder lacks is not served,
            # so a photo shows the site's address for it instead.
            photos[str(url)] = [
                served_photo({**photo, "files": {k: v for k, v in (photo.get("files") or {}).items() if v in files}})
                for photo in listed
            ]

        return stamp, photos, frozenset(files)

    def image_path(self, name: str) -> Path | None:
        """A downloaded photo the manifest lists, or None: nothing else in the folder is served."""

        # The last read's list, not a fresh one: a refresh reads the graph,
        # and every photo asked for while it ran waited on it (2026-11-23).
        # A photo's name comes from a document of that same read.
        if self._version is None:
            self.refresh()

        if not self.images_dir or not IMAGE_FILE.match(name):
            return None

        with self._lock:
            listed = name in self._image_files

        return self.images_dir / name if listed else None

    def photos(self, article: MapArticle) -> list[dict]:
        """Every downloaded photo of the post, the featured one first; else the one the graph links to."""

        with self._lock:
            photos = self._photos.get(article.id)

        return [photo for photo in photos if photo["src"]] if photos else super().photos(article)

    def _fresh(self) -> bool:
        return self._fetched_at is not None and self.clock() - self._fetched_at < REFRESH_SECONDS

    def refresh(self) -> None:

        if self._fresh():
            return

        with self._fetch_lock:

            if self._fresh():
                return

            try:
                rows = self.graph.read(ARTICLES, {"source": self.source_id}, timeout=READ_TIMEOUT).rows
            except GraphUnavailable:
                if self._version is None:
                    raise
                logger.warning("News map: Neo4j unreachable, serving the last read of %s", self.source_id or "the graph", exc_info=True)
                self._fetched_at = self.clock()
                return

            stamp, labels_by_url = self._read_labels()
            images_stamp, photos_by_url, image_files = self._read_images()
            by_id: dict[str, tuple[float, MapArticle]] = {}
            labels: dict[str, dict] = {}
            photos: dict[str, list[dict]] = {}

            for row in rows:
                url = str(row.get("url"))
                try:
                    article = article_from_graph(row, self.countries, labels_by_url.get(url), photos_by_url.get(url))
                except Exception:  # noqa: BLE001 - one odd node must not empty the map
                    logger.warning("News map skips graph article %s", row.get("url"), exc_info=True)
                    continue

                # Two nodes for one host and path: the later analysis wins,
                # as the reader keeps an article's newest run.
                analysed = _timestamp(row.get("analyzed_at"))
                kept = by_id.get(article.id)
                if kept is None or analysed > kept[0]:
                    by_id[article.id] = (analysed, article)
                    if url in labels_by_url:
                        labels[article.id] = labels_by_url[url]
                    if url in photos_by_url:
                        photos[article.id] = photos_by_url[url]

            articles = sorted((article for _, article in by_id.values()), key=lambda a: (-a.sort_at, a.id))
            # The labels move stories (a closest topic) and the photos change
            # what each shows, so both are part of the version, and of the ETag.
            version = tuple(sorted(a.record_id for a in articles)) + (f"labels:{stamp}", f"images:{images_stamp}")

            with self._lock:
                if version != self._version:
                    self._version = version
                    self._by_record = {a.record_id: a for a in articles}
                    self._labels = labels
                    self._photos = photos
                    self._image_files = image_files
                    self._rebuild(articles)

            self._fetched_at = self.clock()

    def articles_document(self, day: str | None = None) -> dict:
        """
        The lake map's columns, and with the WordPress labels loaded, every
        category and tag as a table (`labels`, each its name `n` and kind
        `k`) with each story's as indices into it (`wp`), so the universe
        can show a label's stories when one is clicked (2026-11-23).
        Without labels, the document is the lake map's.
        """

        document = super().articles_document(day)

        with self._lock:
            labels = dict(self._labels)

        if not labels:
            return document

        table: dict[tuple[str, str], int] = {}

        def ref(kind: str, name) -> int | None:
            if not isinstance(name, str) or not name.strip():
                return None
            return table.setdefault((kind, name.strip()), len(table))

        column = []

        for article_id in document["articles"]["id"]:
            own = labels.get(article_id) or {}
            refs = [ref("category", c) for c in own.get("categories") or []] + [ref("tag", t) for t in own.get("tags") or []]
            column.append(list(dict.fromkeys(r for r in refs if r is not None)))

        document["labels"] = [{"n": name, "k": kind} for (kind, name) in table]
        document["articles"]["wp"] = column

        return document

    def links(self, article_id: str, limit: int = 10) -> dict | None:
        """The lake map's links, and the story's WordPress labels when there are any."""

        found = super().links(article_id, limit)

        if found is None:
            return None

        with self._lock:
            labels = self._labels.get(article_id)

        if labels:
            table = anchors()
            found["wordpress"] = {
                "section": labels.get("section"),
                "categories": [str(c) for c in labels.get("categories") or []],
                "tags": [str(t) for t in labels.get("tags") or []],
                "topics": [
                    {"key": key, "name": table[key].name}
                    for key in labels.get("topics_wordpress") or []
                    if key in table
                ],
                "topicFrom": labels.get("topic_from"),
            }

        return found

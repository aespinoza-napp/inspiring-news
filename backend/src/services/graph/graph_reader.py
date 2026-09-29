import re
import time

from neo4j.graph import Node, Path, Relationship

from src.database.neo4j_client import GraphClient
from src.services.graph.schema import declared_schema


class QueryRejected(ValueError):
    """A console query refused before it reached Neo4j."""


# The READ transaction is the real guarantee: Neo4j refuses CREATE, MERGE,
# SET and DELETE in one (GraphClient.read). What it does *not* refuse are
# reads with side effects outside the graph - LOAD CSV fetches any URL
# the server can reach (the same SSRF url_guard.py exists to stop), and
# dbms.* procedures and the admin SHOW commands list configuration, users
# and running transactions, and USE reaches the system database. Those
# are refused here, before the query is sent. SHOW INDEXES / CONSTRAINTS
# / PROCEDURES stay allowed: they describe this graph and nothing else.
FORBIDDEN = re.compile(
    r"\bLOAD\s+CSV\b|\bdbms\s*\.|\bapoc\s*\.|\bgds\s*\.|\bUSE\s+\w|\bTERMINATE\b"
    r"|\bSHOW\s+(?:CURRENT\s+)?(?:USERS?|ROLES?|PRIVILEGES|SETTINGS|SERVERS|"
    r"TRANSACTIONS|DATABASES?|ALIASES)\b",
    re.IGNORECASE,
)

STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`")

QUERY_TIMEOUT_SECONDS = 10.0

MAX_ROWS = 500


# How much one shared thing says two articles are related. Hand-set and
# explainable rather than fitted - there is no labelled "related" set to
# fit against. A shared claim is the strongest link (the same sentence,
# checked); a shared evidence page next (two claims resting on the same
# source); an entity counts less the more articles mention it, since
# "Spain" in forty articles says little about any two of them; a topic,
# of ~22, least.
RELATED_ARTICLES = """
MATCH (a:Article {url: $url})
CALL (a) {
    MATCH (a)-[:CONTAINS_CLAIM]->(c:Claim)<-[:CONTAINS_CLAIM]-(b:Article)
    WHERE b <> a
    RETURN b, 'claim' AS kind, c.text AS via, 3.0 AS weight
    UNION ALL
    MATCH (a)-[:CONTAINS_CLAIM]->(:Claim)-[:CHECKED_AGAINST]->(e:Evidence)
          <-[:CHECKED_AGAINST]-(:Claim)<-[:CONTAINS_CLAIM]-(b:Article)
    WHERE b <> a
    RETURN b, 'evidence' AS kind, coalesce(e.title, e.url) AS via, 1.5 AS weight
    UNION ALL
    MATCH (a)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(b:Article)
    WHERE b <> a
    WITH b, e, COUNT { (e)<-[:MENTIONS]-(:Article) } AS n
    RETURN b, 'entity' AS kind, e.name AS via, 2.0 / n AS weight
    UNION ALL
    MATCH (a)-[:ABOUT]->(t:Topic)<-[:ABOUT]-(b:Article)
    WHERE b <> a
    RETURN b, 'topic' AS kind, t.name AS via, 0.3 AS weight
}
WITH b, kind, via, max(weight) AS weight
WITH b, sum(weight) AS score, collect({kind: kind, via: via, weight: weight}) AS shared
OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(s:Source)
RETURN b.url AS url, b.title AS title, s.name AS source, b.overall_verdict AS verdict,
       round(score, 3) AS score, shared
ORDER BY score DESC, url
LIMIT $limit
"""

ARTICLES = """
MATCH (a:Article)
WHERE $search IS NULL
   OR toLower(coalesce(a.title, '')) CONTAINS toLower($search)
   OR toLower(a.url) CONTAINS toLower($search)
OPTIONAL MATCH (a)-[:PUBLISHED_BY]->(s:Source)
RETURN a.url AS url, a.title AS title, s.name AS source, a.language AS language,
       a.overall_verdict AS verdict, a.analyzed_at AS analyzedAt,
       coalesce(a.labelled, false) AS labelled,
       COUNT { (a)-[:CONTAINS_CLAIM]->() } AS claims,
       COUNT { (a)-[:MENTIONS]->() } AS entities
ORDER BY coalesce(a.analyzed_at, '') DESC, a.url
LIMIT $limit
"""


# The query console's starting points. Each is a real query over the
# declared schema - tests/services/graph/ checks every label and
# relationship type they use is one GraphWriter writes.
PRESETS: list[dict] = [
    {
        "id": "overview",
        "title": "A sample of the whole graph",
        "description": "Articles and everything directly attached to them.",
        "view": "graph",
        "cypher": (
            "MATCH (a:Article)-[r]->(n)\n"
            "RETURN a, r, n\n"
            "LIMIT 150"
        ),
    },
    {
        "id": "article-neighbourhood",
        "title": "One article, two hops out",
        "description": "Its entities, topics, claims, their verdicts and evidence.",
        "view": "graph",
        "params": [{"name": "url", "label": "Article URL"}],
        "cypher": (
            "MATCH (a:Article {url: $url})\n"
            "OPTIONAL MATCH p1 = (a)-[:MENTIONS|ABOUT|PUBLISHED_BY]->()\n"
            "OPTIONAL MATCH p2 = (a)-[:CONTAINS_CLAIM]->(:Claim)-[:HAS_VERDICT|CHECKED_AGAINST]->()\n"
            "RETURN a, p1, p2\n"
            "LIMIT 300"
        ),
    },
    {
        "id": "claims-with-verdicts",
        "title": "Claims and their verdicts",
        "description": "Pipeline and hand-labelled verdicts side by side.",
        "view": "table",
        "cypher": (
            "MATCH (a:Article)-[:CONTAINS_CLAIM]->(c:Claim)-[r:HAS_VERDICT]->(v:Verdict)\n"
            "RETURN c.text AS claim, v.name AS verdict, r.method AS method,\n"
            "       round(r.confidence, 2) AS confidence, a.url AS article\n"
            "ORDER BY claim, method\n"
            "LIMIT 200"
        ),
    },
    {
        "id": "pipeline-vs-manual",
        "title": "Where the pipeline disagrees with a hand label",
        "description": "Claims with both a manual and a pipeline verdict that differ.",
        "view": "table",
        "cypher": (
            "MATCH (m:Verdict)<-[:HAS_VERDICT {method: 'manual'}]-(c:Claim)\n"
            "      -[:HAS_VERDICT {method: 'pipeline'}]->(p:Verdict)\n"
            "WHERE m <> p\n"
            "RETURN c.text AS claim, m.name AS manual, p.name AS pipeline\n"
            "LIMIT 200"
        ),
    },
    {
        "id": "verdict-distribution",
        "title": "Verdicts by method",
        "description": "How many claims each verdict holds, per method.",
        "view": "table",
        "cypher": (
            "MATCH (:Claim)-[r:HAS_VERDICT]->(v:Verdict)\n"
            "RETURN v.name AS verdict, r.method AS method, count(*) AS claims\n"
            "ORDER BY method, claims DESC"
        ),
    },
    {
        "id": "claim-evidence",
        "title": "Verified claims and their sources",
        "description": "Each claim, the pages it was checked against, and who published them.",
        "view": "graph",
        "cypher": (
            "MATCH p = (:Claim)-[:CHECKED_AGAINST]->(:Evidence)-[:PUBLISHED_BY]->(:Source)\n"
            "RETURN p\n"
            "LIMIT 150"
        ),
    },
    {
        "id": "top-entities",
        "title": "Most mentioned entities",
        "description": "Entities by how many articles mention them.",
        "view": "table",
        "cypher": (
            "MATCH (e:Entity)<-[:MENTIONS]-(a:Article)\n"
            "RETURN e.name AS entity, e.type AS type, count(DISTINCT a) AS articles\n"
            "ORDER BY articles DESC, entity\n"
            "LIMIT 50"
        ),
    },
    {
        "id": "shared-entities",
        "title": "Entities shared by several articles",
        "description": "The entities that actually connect articles to each other.",
        "view": "graph",
        "cypher": (
            "MATCH (e:Entity)<-[:MENTIONS]-(a:Article)\n"
            "WITH e, collect(a) AS articles\n"
            "WHERE size(articles) > 1\n"
            "UNWIND articles AS a\n"
            "MATCH p = (a)-[:MENTIONS]->(e)\n"
            "RETURN p\n"
            "LIMIT 200"
        ),
    },
    {
        "id": "entities-by-type",
        "title": "Entities by type",
        "description": "Countries, people, organisations... and how many of each.",
        "view": "table",
        "cypher": (
            "MATCH (e:Entity)\n"
            "RETURN e.type AS type, count(*) AS entities\n"
            "ORDER BY entities DESC"
        ),
    },
    {
        "id": "cited-sources",
        "title": "Most used evidence sources",
        "description": "Publishers claims were checked against, and whether we rate them.",
        "view": "table",
        "cypher": (
            "MATCH (c:Claim)-[r:CHECKED_AGAINST]->(:Evidence)-[:PUBLISHED_BY]->(s:Source)\n"
            "RETURN s.domain AS source, s.reliability AS reliability,\n"
            "       s.configured AS configured, count(DISTINCT c) AS claims,\n"
            "       sum(CASE WHEN r.cited THEN 1 ELSE 0 END) AS cited\n"
            "ORDER BY claims DESC\n"
            "LIMIT 50"
        ),
    },
    {
        "id": "articles-per-source",
        "title": "Articles per source",
        "description": "Where the analysed and labelled articles come from.",
        "view": "table",
        "cypher": (
            "MATCH (a:Article)-[:PUBLISHED_BY]->(s:Source)\n"
            "RETURN s.name AS source, s.domain AS domain, s.configured AS configured,\n"
            "       count(a) AS articles\n"
            "ORDER BY articles DESC"
        ),
    },
    {
        "id": "topic-cooccurrence",
        "title": "Topics that appear together",
        "description": "Pairs of topics sharing an article.",
        "view": "table",
        "cypher": (
            "MATCH (t1:Topic)<-[:ABOUT]-(a:Article)-[:ABOUT]->(t2:Topic)\n"
            "WHERE t1.name < t2.name\n"
            "RETURN t1.name AS topic, t2.name AS alsoAbout, count(DISTINCT a) AS articles\n"
            "ORDER BY articles DESC\n"
            "LIMIT 50"
        ),
    },
]


def to_json(value):
    """
    A driver value as plain JSON. Nodes and relationships keep their
    element id, so the frontend can draw a relationship between two nodes
    returned in different rows.
    """

    if isinstance(value, Node):
        return {
            "kind": "node",
            "id": value.element_id,
            "labels": sorted(value.labels),
            "properties": {k: to_json(v) for k, v in value.items()},
        }

    if isinstance(value, Relationship):
        return {
            "kind": "relationship",
            "id": value.element_id,
            "type": value.type,
            "start": value.start_node.element_id if value.start_node else None,
            "end": value.end_node.element_id if value.end_node else None,
            "properties": {k: to_json(v) for k, v in value.items()},
        }

    if isinstance(value, Path):
        return {
            "kind": "path",
            "nodes": [to_json(node) for node in value.nodes],
            "relationships": [to_json(rel) for rel in value.relationships],
        }

    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # neo4j.time types, spatial points.
    iso = getattr(value, "iso_format", None)

    return iso() if callable(iso) else str(value)


def collect_graph(rows: list[dict]) -> dict:
    """Every node and relationship anywhere in the rows, once each."""

    nodes: dict[str, dict] = {}
    relationships: dict[str, dict] = {}

    def visit(value):
        if isinstance(value, dict):
            kind = value.get("kind")
            if kind == "node":
                nodes[value["id"]] = value
                return
            if kind == "relationship":
                relationships[value["id"]] = value
                return
            if kind == "path":
                for node in value["nodes"]:
                    nodes[node["id"]] = node
                for rel in value["relationships"]:
                    relationships[rel["id"]] = rel
                return
            for inner in value.values():
                visit(inner)
        elif isinstance(value, list):
            for inner in value:
                visit(inner)

    for row in rows:
        visit(row)

    # A relationship whose endpoint the query did not return cannot be
    # drawn; say so by dropping it rather than inventing a blank node.
    drawable = [
        rel for rel in relationships.values()
        if rel["start"] in nodes and rel["end"] in nodes
    ]

    return {"nodes": list(nodes.values()), "relationships": drawable}


def check_query(cypher: str) -> None:

    if not cypher or not cypher.strip():
        raise QueryRejected("The query is empty.")

    # Literals stripped first, so a search for the text "LOAD CSV" is not
    # mistaken for the clause.
    bare = STRING_LITERAL.sub("''", cypher)

    match = FORBIDDEN.search(bare)

    if match:
        raise QueryRejected(
            f"'{match.group(0).strip()}' is not allowed from the console: "
            "it reaches outside the graph (files, URLs, server configuration)."
        )


class GraphReader:

    def __init__(self, client: GraphClient):
        self.client = client

    def query(self, cypher: str, params: dict | None = None) -> dict:
        """The query console. Read-only, time-limited, row-limited."""

        check_query(cypher)

        started = time.perf_counter()

        result = self.client.read(
            cypher,
            params or {},
            timeout=QUERY_TIMEOUT_SECONDS,
            max_rows=MAX_ROWS,
        )

        rows = [{key: to_json(value) for key, value in row.items()} for row in result.rows]

        return {
            "columns": result.columns,
            "rows": rows,
            "graph": collect_graph(rows),
            "truncated": result.truncated,
            "notices": result.notices,
            "maxRows": MAX_ROWS,
            "elapsedMs": round((time.perf_counter() - started) * 1000),
        }

    def schema(self) -> dict:
        """
        The declared schema, with what the database actually holds next to
        it: node counts per label, and every (from)-[type]->(to) pattern
        present with its count. A pattern present but undeclared, or
        declared but absent, is visible rather than assumed.
        """

        label_rows = self.client.read(
            "MATCH (n) UNWIND labels(n) AS label "
            "RETURN label, count(*) AS count ORDER BY count DESC",
            timeout=QUERY_TIMEOUT_SECONDS,
        ).rows

        pattern_rows = self.client.read(
            "MATCH (a)-[r]->(b) "
            "WITH [l IN labels(a) WHERE l IN $base][0] AS from, type(r) AS type, "
            "     [l IN labels(b) WHERE l IN $base][0] AS to "
            "RETURN from, type, to, count(*) AS count ORDER BY count DESC",
            {"base": [node["label"] for node in declared_schema()["nodes"]]},
            timeout=QUERY_TIMEOUT_SECONDS,
        ).rows

        method_rows = self.client.read(
            "MATCH ()-[r]->() WHERE r.method IS NOT NULL "
            "RETURN type(r) AS type, r.method AS method, count(*) AS count",
            timeout=QUERY_TIMEOUT_SECONDS,
        ).rows

        return {
            **declared_schema(),
            "live": {
                "labels": {row["label"]: row["count"] for row in label_rows},
                "patterns": [dict(row) for row in pattern_rows],
                "methods": [dict(row) for row in method_rows],
            },
        }

    def related_articles(self, url: str, limit: int = 10) -> dict:

        found = self.client.read(
            "MATCH (a:Article {url: $url}) RETURN a.title AS title",
            {"url": url},
            timeout=QUERY_TIMEOUT_SECONDS,
        ).rows

        if not found:
            return {"url": url, "found": False, "title": None, "related": []}

        rows = self.client.read(
            RELATED_ARTICLES,
            {"url": url, "limit": limit},
            timeout=QUERY_TIMEOUT_SECONDS,
        ).rows

        return {
            "url": url,
            "found": True,
            "title": found[0]["title"],
            "related": [to_json(row) for row in rows],
        }

    def articles(self, search: str | None = None, limit: int = 50) -> list[dict]:

        rows = self.client.read(
            ARTICLES,
            {"search": search or None, "limit": limit},
            timeout=QUERY_TIMEOUT_SECONDS,
        ).rows

        return [to_json(row) for row in rows]

    @staticmethod
    def presets() -> list[dict]:
        return PRESETS

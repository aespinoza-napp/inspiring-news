import re

import pytest

from src.database.neo4j_client import ReadResult
from src.services.graph.graph_reader import (
    MAX_ROWS,
    PRESETS,
    QUERY_TIMEOUT_SECONDS,
    RELATED_ARTICLES,
    GraphReader,
    QueryRejected,
    check_query,
    collect_graph,
)
from src.services.graph.schema import ENTITY_TYPE_LABELS, NODE_KEYS, RELATIONSHIPS

from tests.services.graph.fake_graph_client import RecordingGraphClient


@pytest.mark.parametrize("cypher", [
    "LOAD CSV FROM 'http://169.254.169.254/latest' AS line RETURN line",
    "load  csv with headers from 'file:///etc/passwd' as l return l",
    "CALL dbms.listConfig()",
    "CALL apoc.load.json('http://internal/')",
    "SHOW USERS",
    "show current user",
    "SHOW SETTINGS YIELD *",
    "USE system SHOW DATABASES",
    "TERMINATE TRANSACTIONS 'neo4j-transaction-1'",
    "   ",
])
def test_the_console_refuses_queries_that_reach_outside_the_graph(cypher):

    with pytest.raises(QueryRejected):
        check_query(cypher)


@pytest.mark.parametrize("cypher", [
    "MATCH (a:Article) RETURN a LIMIT 5",
    # The words inside a string are data, not the clause.
    "MATCH (c:Claim) WHERE c.text CONTAINS 'LOAD CSV' RETURN c",
    "SHOW INDEXES",
    "SHOW CONSTRAINTS",
    "CALL db.labels()",
])
def test_the_console_allows_ordinary_reads(cypher):

    check_query(cypher)


def test_a_console_query_is_time_and_row_limited():

    client = RecordingGraphClient(reads=[ReadResult(["n"], [{"n": 1}], True, ["a notice"])])

    result = GraphReader(client).query("MATCH (n) RETURN 1 AS n", {"x": 1})

    made = client.reads_made[0]
    assert made["timeout"] == QUERY_TIMEOUT_SECONDS
    assert made["max_rows"] == MAX_ROWS
    assert made["params"] == {"x": 1}

    assert result["columns"] == ["n"]
    assert result["rows"] == [{"n": 1}]
    assert result["truncated"] is True
    assert result["notices"] == ["a notice"]


def test_a_refused_query_never_reaches_the_database():

    client = RecordingGraphClient()

    with pytest.raises(QueryRejected):
        GraphReader(client).query("LOAD CSV FROM 'x' AS l RETURN l")

    assert client.reads_made == []


def node(id, *labels, **props):
    return {"kind": "node", "id": id, "labels": list(labels), "properties": props}


def rel(id, type, start, end):
    return {"kind": "relationship", "id": id, "type": type, "start": start, "end": end, "properties": {}}


def test_the_drawable_graph_holds_each_node_once_across_rows_and_paths():

    a, s = node("1", "Article"), node("2", "Source")
    r = rel("r1", "PUBLISHED_BY", "1", "2")

    rows = [
        {"a": a, "r": r, "s": s},
        {"p": {"kind": "path", "nodes": [a, s], "relationships": [r]}},
        {"nested": [{"inner": a}]},
    ]

    graph = collect_graph(rows)

    assert sorted(n["id"] for n in graph["nodes"]) == ["1", "2"]
    assert [x["id"] for x in graph["relationships"]] == ["r1"]


def test_a_relationship_whose_endpoint_was_not_returned_is_not_drawn():

    graph = collect_graph([{"a": node("1", "Article"), "r": rel("r1", "ABOUT", "1", "99")}])

    assert graph["relationships"] == []


def test_related_articles_says_when_the_article_is_not_in_the_graph():

    client = RecordingGraphClient(reads=[ReadResult(["title"], [], False, [])])

    result = GraphReader(client).related_articles("https://nowhere.example/")

    assert result == {"url": "https://nowhere.example/", "found": False, "title": None, "related": []}
    # The expensive query is not run for an article that is not there.
    assert len(client.reads_made) == 1


def test_related_articles_runs_the_related_query_with_the_limit():

    client = RecordingGraphClient(reads=[
        ReadResult(["title"], [{"title": "T"}], False, []),
        ReadResult(["url"], [{"url": "https://b/", "score": 1.0, "shared": []}], False, []),
    ])

    result = GraphReader(client).related_articles("https://a/", limit=3)

    assert client.reads_made[1]["query"] == RELATED_ARTICLES
    assert client.reads_made[1]["params"] == {"url": "https://a/", "limit": 3}
    assert result["related"] == [{"url": "https://b/", "score": 1.0, "shared": []}]


LABEL = re.compile(r"\(\s*\w*\s*:(\w+)")


def test_every_preset_and_the_related_query_use_only_declared_names():
    """
    A preset naming a relationship nobody writes returns nothing, and
    looks exactly like an empty graph. Checked against schema.py, which
    test_graph_writer.py checks the writer against.
    """

    labels = set(NODE_KEYS) | set(ENTITY_TYPE_LABELS.values())
    types = {r["type"] for r in RELATIONSHIPS}

    for cypher in [p["cypher"] for p in PRESETS] + [RELATED_ARTICLES]:

        for label in LABEL.findall(cypher):
            assert label in labels, f"undeclared label :{label} in {cypher[:60]}"

        for rel_type in re.findall(r"\[\s*\w*\s*:([A-Z_|]+)", cypher):
            for one in rel_type.split("|"):
                assert one in types, f"undeclared relationship :{one} in {cypher[:60]}"


def test_presets_have_unique_ids_and_declare_their_parameters():

    ids = [p["id"] for p in PRESETS]
    assert len(ids) == len(set(ids))

    for preset in PRESETS:
        used = set(re.findall(r"\$(\w+)", preset["cypher"]))
        declared = {param["name"] for param in preset.get("params", [])}
        assert used == declared, preset["id"]
        assert preset["view"] in ("graph", "table")

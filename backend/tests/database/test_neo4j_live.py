"""
The graph against a real Neo4j: `./scripts/check.sh graph`.

Replaces test_connection.py, which *skipped* when Neo4j was down - so the
one test of the database passed, in every run, whether or not a database
existed. These carry the `neo4j` marker instead, which pyproject's addopts
excludes like `slow`: the default suite needs no Neo4j (the writer, the
reader and the routes are covered there against a recording fake), and
when you do ask for these, a missing Neo4j is a failure that says so.

They write into the developer's own graph - Neo4j Community has one
database - so everything they create carries a per-run token in its URL,
name or text, and is deleted afterwards whether the test passed or not.
"""

import uuid

import pytest

from src.config.settings import settings
from src.database.neo4j_client import GraphClient, GraphUnavailable
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.services.graph.graph_reader import GraphReader
from src.services.graph.graph_writer import GraphWriter, claim_id

from tests.factories import create_article, create_claim, create_evidence

pytestmark = pytest.mark.neo4j


@pytest.fixture(scope="module")
def client():

    client = GraphClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD.get_secret_value(),
    )

    try:
        client.verify_connection()
    except GraphUnavailable as exc:
        client.close()
        pytest.fail(
            f"Neo4j is not reachable at {settings.NEO4J_URI}: {exc}\n"
            "Start it: cd docker && docker compose --env-file ../backend/.env up -d neo4j"
        )

    yield client

    client.close()


@pytest.fixture
def token(client):

    token = f"graphtest{uuid.uuid4().hex[:12]}"

    yield token

    client.write([(
        "MATCH (n) WHERE any(key IN keys(n) WHERE toString(n[key]) CONTAINS $token) "
        "DETACH DELETE n",
        {"token": token},
    )])


def article_about(token, name, entity, claim_text, evidence_url):

    claim = create_claim(text=claim_text, entities={"person": [entity]})

    article = create_article(
        url=f"https://{token}.example/{name}",
        title=f"{token} {name}",
        entities={"person": [entity]},
        topics=[],
        claims=[claim],
    )

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        overall_verdict=Verdict.TRUE,
        claim_checks=[FactCheck(
            claim=claim_text,
            verdict=Verdict.TRUE,
            explanation="",
            confidence=0.9,
            evidence=[create_evidence(url=evidence_url, title=f"{token} evidence")],
            cited_evidence_indices=[0],
        )],
    )

    return article, report


def test_the_database_answers(client):

    client.verify_connection()


def test_an_analysis_round_trips_through_the_graph(client, token):

    writer = GraphWriter(client)
    reader = GraphReader(client)

    article, report = article_about(
        token, "one", f"{token} Ada", f"{token} claim one.", f"https://{token}.example/ev"
    )

    writer.write_analysis(article, report)

    rows = reader.query(
        "MATCH (a:Article {url: $url})-[:CONTAINS_CLAIM]->(c:Claim)-[v:HAS_VERDICT]->(verdict:Verdict), "
        "(c)-[e:CHECKED_AGAINST]->(:Evidence)-[:PUBLISHED_BY]->(s:Source), "
        "(a)-[:MENTIONS]->(p:Person) "
        "RETURN c.id AS claim, verdict.name AS verdict, v.method AS method, "
        "e.cited AS cited, s.domain AS source, p.name AS person",
        {"url": article.url},
    )["rows"]

    assert rows == [{
        "claim": claim_id(f"{token} claim one."),
        "verdict": "TRUE",
        "method": "pipeline",
        "cited": True,
        "source": f"{token}.example",
        "person": f"{token} Ada",
    }]


def test_writing_the_same_analysis_twice_changes_nothing(client, token):

    writer = GraphWriter(client)

    article, report = article_about(
        token, "one", f"{token} Ada", f"{token} claim.", f"https://{token}.example/ev"
    )

    count = (
        "MATCH (n) WHERE any(key IN keys(n) WHERE toString(n[key]) CONTAINS $token) "
        "OPTIONAL MATCH (n)-[r]-() RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS rels"
    )

    writer.write_analysis(article, report)
    first = client.read(count, {"token": token}).rows

    writer.write_analysis(article, report)
    second = client.read(count, {"token": token}).rows

    assert first == second


def test_two_articles_sharing_an_entity_are_related(client, token):

    writer = GraphWriter(client)

    shared = f"{token} Ada"

    one, report_one = article_about(token, "one", shared, f"{token} one.", f"https://{token}.example/e1")
    two, report_two = article_about(token, "two", shared, f"{token} two.", f"https://{token}.example/e2")

    writer.write_analysis(one, report_one)
    writer.write_analysis(two, report_two)

    related = GraphReader(client).related_articles(one.url)

    assert related["found"] is True
    assert [r["url"] for r in related["related"]] == [two.url]
    assert {"kind": "entity", "via": shared} in [
        {"kind": s["kind"], "via": s["via"]} for s in related["related"][0]["shared"]
    ]


def test_a_hand_label_and_a_pipeline_verdict_sit_side_by_side(client, token):

    writer = GraphWriter(client)

    article, report = article_about(
        token, "one", f"{token} Ada", f"{token} claim.", f"https://{token}.example/ev"
    )

    writer.write_analysis(article, report)

    writer.write_labelled_fact({
        "id": f"{token}fact",
        "claim": f"{token} claim.",
        "label": "MISLEADING",
        "articleUrl": article.url,
        "referenceEvidenceLinks": [f"https://{token}.example/ref"],
    })

    rows = GraphReader(client).query(
        "MATCH (c:Claim {id: $id})-[r:HAS_VERDICT]->(v:Verdict) "
        "RETURN r.method AS method, v.name AS verdict ORDER BY method",
        {"id": claim_id(f"{token} claim.")},
    )["rows"]

    assert rows == [
        {"method": "manual", "verdict": "MISLEADING"},
        {"method": "pipeline", "verdict": "TRUE"},
    ]


def test_the_console_cannot_write(client, token):
    """Enforced by Neo4j (a READ transaction), not by our keyword filter."""

    from neo4j.exceptions import ClientError

    with pytest.raises(ClientError, match="(?i)read"):
        GraphReader(client).query(f"CREATE (:Article {{url: '{token}'}})")


def test_the_schema_view_reports_what_was_written(client, token):

    writer = GraphWriter(client)

    article, report = article_about(
        token, "one", f"{token} Ada", f"{token} claim.", f"https://{token}.example/ev"
    )

    writer.write_analysis(article, report)

    live = GraphReader(client).schema()["live"]

    patterns = {(p["from"], p["type"], p["to"]) for p in live["patterns"]}

    assert ("Article", "CONTAINS_CLAIM", "Claim") in patterns
    assert ("Claim", "HAS_VERDICT", "Verdict") in patterns
    assert ("Evidence", "PUBLISHED_BY", "Source") in patterns
    assert live["labels"]["Person"] >= 1

"""
Neo4j is configured scaffold only - nothing in the real pipeline reads
from it (see CLAUDE.md). This test therefore skips, rather than fails,
when no Neo4j is running: an unrelated red test in every local run
trains people to ignore the suite.
"""
import pytest

from src.config.settings import settings
from src.database.neo4j_client import GraphClient


@pytest.fixture(scope="session")
def graph_client():

    client = GraphClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD.get_secret_value(),
    )

    try:
        client.verify_connection()
    except Exception as exc:
        client.close()
        pytest.skip(f"Neo4j is not reachable at {settings.NEO4J_URI}: {exc}")

    yield client

    client.close()


def test_db_connection(graph_client):

    graph_client.verify_connection()

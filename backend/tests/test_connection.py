import pytest
from src.database.neo4j_client import GraphClient
from src.config.settings import settings


@pytest.fixture(scope="session")
def graph_client():
    client = GraphClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD.get_secret_value(),
    )
    yield client
    client.close()

def test_db_connection(graph_client):
    graph_client.verify_connection()
"""
def test_db_connection():
    client = GraphClient(
        uri=settings.NEO4J_URI,
        username=settings.NEO4J_USERNAME,
        password=settings.NEO4J_PASSWORD.get_secret_value(),
    )    
    try:
        client.verify_connection()
        connected = True
    except:
        connected = False
    assert connected is True

"""
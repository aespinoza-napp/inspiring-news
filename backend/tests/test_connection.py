import pytest
from src.database.neo4j_client import GraphClient

def test_db_connection():
    client = GraphClient("bolt://localhost:7687", "neo4j", "password123")
    try:
        client.verify_connection()
        connected = True
    except:
        connected = False
    assert connected is True
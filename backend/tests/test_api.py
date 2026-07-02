from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_example_endpoint():
    response = client.get("/example")

    assert response.status_code == 200

    body = response.json()

    assert "claims" in body
    assert "fact_checks" in body
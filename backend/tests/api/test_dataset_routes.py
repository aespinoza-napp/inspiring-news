from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app
from src.repositories.custom_fact_repository import CustomFactRepository
from src.services.custom_dataset import CustomDatasetService

client = TestClient(app)

FACT = {
    "claim": "Spain's rooftop solar capacity grew 30% in 2024.",
    "language": "en",
    "site": "pv-magazine.com",
    "claimDate": "2025-01-20",
    "label": "PARTIALLY_TRUE",
    "referenceEvidenceLinks": ["https://www.ree.es/en/press-office"],
    "topic": "energy",
    "claimType": "numerical",
    "sourceTier": "primary",
}


def use_tmp_dataset(monkeypatch, tmp_path):

    # Never the committed backend/data/evaluation file.
    service = CustomDatasetService(CustomFactRepository(tmp_path / "custom.jsonl"))
    monkeypatch.setattr(routes, "get_custom_dataset_service", lambda: service)

    return service


def test_a_fact_is_created_and_listed_with_the_balance(monkeypatch, tmp_path):

    use_tmp_dataset(monkeypatch, tmp_path)

    created = client.post("/dataset/facts", json=FACT)

    assert created.status_code == 201
    assert created.json()["labelRaw"] == "partially supported"

    overview = client.get("/dataset").json()

    assert [f["id"] for f in overview["facts"]] == [created.json()["id"]]
    assert overview["summary"]["matrix"]["PARTIALLY_TRUE"]["environment"] == 1
    assert overview["schema"]["targets"]["total"] == 150
    assert {t["id"] for t in overview["schema"]["topics"]} >= {"energy", "medicine"}


def test_a_guide_rule_is_a_422(monkeypatch, tmp_path):

    use_tmp_dataset(monkeypatch, tmp_path)

    response = client.post("/dataset/facts", json={**FACT, "referenceEvidenceLinks": []})

    assert response.status_code == 422


def test_edit_review_and_delete(monkeypatch, tmp_path):

    use_tmp_dataset(monkeypatch, tmp_path)

    fact_id = client.post("/dataset/facts", json=FACT).json()["id"]

    edited = client.put(f"/dataset/facts/{fact_id}", json={**FACT, "label": "TRUE"})
    assert edited.json()["label"] == "TRUE"

    queue = client.get("/dataset/review").json()
    assert queue["sampleSize"] == 1
    assert "label" not in queue["sample"][0]

    reviewed = client.post(f"/dataset/facts/{fact_id}/review", json={"label": "TRUE"})
    assert reviewed.json()["review"]["agrees"] is True
    assert client.get("/dataset/review").json()["agreement"]["observed"] == 1

    assert client.delete(f"/dataset/facts/{fact_id}").status_code == 204
    assert client.delete(f"/dataset/facts/{fact_id}").status_code == 404
    assert client.put(f"/dataset/facts/{fact_id}", json=FACT).status_code == 404

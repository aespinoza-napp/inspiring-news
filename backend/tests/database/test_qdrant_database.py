import pytest

from src.database import qdrant as qdrant_module
from src.database.qdrant import QdrantDatabase


class FakeClient:
    def __init__(self, path):
        self.path = path


def test_connect_succeeds_immediately(tmp_path, monkeypatch):

    monkeypatch.setattr(qdrant_module, "QdrantClient", FakeClient)

    db = QdrantDatabase(path=tmp_path)

    assert isinstance(db.client, FakeClient)


def test_connect_retries_on_lock_race(tmp_path, monkeypatch):

    calls = {"count": 0}

    def flaky_client(path):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError(
                "Storage folder ... is already accessed by another "
                "instance of Qdrant client."
            )
        return FakeClient(path)

    monkeypatch.setattr(qdrant_module, "QdrantClient", flaky_client)
    monkeypatch.setattr(qdrant_module.time, "sleep", lambda _: None)

    db = QdrantDatabase(path=tmp_path)

    assert calls["count"] == 3
    assert isinstance(db.client, FakeClient)


def test_connect_gives_up_after_max_attempts(tmp_path, monkeypatch):

    def always_locked(path):
        raise RuntimeError("already accessed by another instance of Qdrant client.")

    monkeypatch.setattr(qdrant_module, "QdrantClient", always_locked)
    monkeypatch.setattr(qdrant_module.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="already accessed"):
        QdrantDatabase(path=tmp_path)


def test_connect_reraises_unrelated_runtime_errors(tmp_path, monkeypatch):

    def other_error(path):
        raise RuntimeError("some unrelated failure")

    monkeypatch.setattr(qdrant_module, "QdrantClient", other_error)

    with pytest.raises(RuntimeError, match="unrelated failure"):
        QdrantDatabase(path=tmp_path)

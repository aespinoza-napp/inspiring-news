"""
EmbeddingService is now an Adapter over InferenceClient - the real
sentence-transformer moved to inference/tests/test_embeddings.py. This
tests the adapter and EmbeddingProcessor's thin wrapper over it, with a
stub client so it stays fast and needs nothing running.

EMBEDDING_DIMENSION agreement with the real model is checked separately
in tests/services/embeddings/test_embedding_dimension_live.py, which needs a real,
reachable inference service and skips when there isn't one - a stub
here can't meaningfully assert that agreement.

EmbeddingService is a process-wide singleton (see service.py's
`__new__`), so every test below uses monkeypatch on the shared instance
rather than constructing a "fresh" one - monkeypatch's teardown restores
the original `_client`/`_dimension` automatically, so a stub used here
can't leak into a later test that needs the real service.
"""

from src.processors.nlp.embeddings import EmbeddingProcessor
from src.services.embeddings.service import EmbeddingService


class _StubClient:

    def __init__(self, vector=None, dimension=8):
        self.vector = vector or [0.1] * dimension
        self.dimension = dimension
        self.calls = []

    def encode(self, text):
        self.calls.append(text)
        return self.vector, self.dimension

    def encode_many(self, texts):
        self.calls.append(texts)
        return [self.vector for _ in texts], self.dimension


def test_encode_delegates_to_the_client_and_returns_a_numpy_array(monkeypatch):

    service = EmbeddingService()
    stub = _StubClient(vector=[0.1, 0.2, 0.3], dimension=3)
    monkeypatch.setattr(service, "_client", stub)
    monkeypatch.setattr(service, "_dimension", None)

    embedding = service.encode("hello")

    assert list(embedding) == [0.1, 0.2, 0.3]
    assert stub.calls == ["hello"]


def test_dimension_is_cached_from_the_last_encode_call(monkeypatch):

    service = EmbeddingService()
    stub = _StubClient(dimension=5)
    monkeypatch.setattr(service, "_client", stub)
    monkeypatch.setattr(service, "_dimension", None)

    service.encode("hello")

    assert service.dimension == 5


def test_dimension_triggers_one_call_when_nothing_encoded_yet(monkeypatch):

    service = EmbeddingService()
    stub = _StubClient(dimension=5)
    monkeypatch.setattr(service, "_client", stub)
    monkeypatch.setattr(service, "_dimension", None)

    assert service.dimension == 5
    assert len(stub.calls) == 1


def test_similarity_is_pure_arithmetic_with_no_client_call(monkeypatch):

    service = EmbeddingService()
    stub = _StubClient()
    monkeypatch.setattr(service, "_client", stub)

    similarity = service.similarity([1.0, 0.0], [1.0, 0.0])

    assert similarity == 1.0
    assert stub.calls == []


def test_embedding_processor_delegates_to_the_shared_service(monkeypatch):

    service = EmbeddingService()
    stub = _StubClient(vector=[0.5, 0.5], dimension=2)
    monkeypatch.setattr(service, "_client", stub)
    monkeypatch.setattr(service, "_dimension", None)

    processor = EmbeddingProcessor()

    embedding = processor.process("hello")

    assert list(embedding) == [0.5, 0.5]
    assert processor.dimension == 2

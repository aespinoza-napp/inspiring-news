"""
Moved from backend/tests/processors/nlp/test_embeddings.py - this is
where the real sentence-transformer lives now.
"""

from src.embeddings import EmbeddingModel


def test_embedding_model_reports_a_real_dimension():
    """
    backend/tests/services/embeddings/test_embedding_dimension_live.py is what
    actually cross-checks this dimension against EMBEDDING_DIMENSION - a
    concern this service doesn't own. This just confirms the model loads
    and reports something sane.
    """

    model = EmbeddingModel()
    model.load()

    assert model.dimension > 100


def test_encode_returns_a_real_vector():

    model = EmbeddingModel()
    model.load()

    text = "Scientists developed a revolutionary treatment against Alzheimer's disease."

    embedding = model.encode(text)

    assert isinstance(embedding, list)
    assert len(embedding) == model.dimension
    assert len(embedding) > 100


def test_encode_many_batches_correctly():

    model = EmbeddingModel()
    model.load()

    texts = ["First article about medicine.", "Second article about climate."]

    embeddings = model.encode_many(texts)

    assert len(embeddings) == 2
    assert all(len(vector) == model.dimension for vector in embeddings)


class _Recorder:
    """Stands in for SentenceTransformer: no tokenizer, a vector that names its text."""

    def __init__(self):
        self.batches = []

    def encode(self, texts, **kwargs):
        import numpy as np

        assert kwargs["batch_size"] == len(texts)
        self.batches.append(list(texts))
        return np.array([[float(len(text)), 0.0, 1.0] for text in texts])


def _model_with(recorder):
    model = EmbeddingModel()
    model._model = recorder
    return model


def test_short_texts_share_a_batch_and_a_long_one_goes_alone(monkeypatch):
    """
    One text at a time was fastest for long pages, which a batch pads to
    its longest (2026-10-16), and slowest for short ones, which pad
    nothing: 163 topic keywords 17.9 s one by one, 4.5 s batched by
    length (2026-10-21, config.py). Needs no model.
    """

    from src.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_BATCH_TOKENS", 100)
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 64)

    recorder = _Recorder()
    long_page = "x" * 400  # ~100 tokens at four characters a token
    texts = ["aaaaaaaa", long_page, "bbbbbbbbbbbb", "cccc"]  # 2, ~100, 3 and 1 tokens

    vectors = _model_with(recorder).encode_many(texts)

    # Input order, whatever order the batches ran in.
    assert [vector[0] for vector in vectors] == [float(len(text)) for text in texts]
    assert recorder.batches == [["cccc", "aaaaaaaa", "bbbbbbbbbbbb"], [long_page]]


def test_a_zero_budget_is_one_text_at_a_time(monkeypatch):

    from src.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_BATCH_TOKENS", 0)

    recorder = _Recorder()

    _model_with(recorder).encode_many(["a", "b", "c"])

    assert recorder.batches == [["a"], ["b"], ["c"]]


def test_the_batch_size_caps_the_texts_in_one_batch(monkeypatch):

    from src.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_BATCH_TOKENS", 10_000)
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 2)

    recorder = _Recorder()

    _model_with(recorder).encode_many(["a", "b", "c"])

    assert [len(batch) for batch in recorder.batches] == [2, 1]

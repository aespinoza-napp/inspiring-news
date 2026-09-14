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

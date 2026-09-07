from src.config.settings import settings
from src.processors.nlp.embeddings import EmbeddingProcessor
from src.services.embeddings.service import EmbeddingService


def test_embedding_service_dimension_matches_configured_dimension():
    """
    settings.EMBEDDING_MODEL and settings.EMBEDDING_DIMENSION are two
    independently-set values - nothing enforces that they actually agree,
    and VectorRepository sizes the Qdrant collection from
    EMBEDDING_DIMENSION alone (see _create_collection), not from the
    model's real output size. The two config values only happen to agree
    today because .env sets both together for BAAI/bge-m3 (1024-dim); the
    settings.py *default* for EMBEDDING_MODEL is a 384-dim model, so a
    fresh checkout without a matching .env would silently create a
    wrongly-sized collection and every article.save() would fail with a
    Qdrant vector-size mismatch. This guards against that drift.
    """

    assert EmbeddingService().dimension == settings.EMBEDDING_DIMENSION


def test_embedding_processor():

    processor = EmbeddingProcessor()

    text = """
    Scientists developed a revolutionary treatment
    against Alzheimer's disease.
    """

    embedding = processor.process(text)

    print()

    print("Embedding dimension:", len(embedding))

    print("First values:", embedding[:10])

    assert embedding.ndim == 1

    assert len(embedding) > 100
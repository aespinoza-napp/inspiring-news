from src.processors.nlp.embeddings import EmbeddingProcessor


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
from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository

from tests.factories import create_article


def test_save_article():

    repository = VectorRepository(
        QdrantDatabase()
    )

    repository.clear()

    article = create_article(
        id="test"
    )

    repository.save(article)

    assert repository.exists("test")

    assert repository.count() == 1

def test_get_article():

    repository = VectorRepository(
        QdrantDatabase()
    )

    repository.clear()

    article = create_article(
        id="test"
    )

    repository.save(article)

    saved = repository.get("test")

    assert saved is not None

    assert saved.id == article.id

    assert saved.title == article.title

    assert saved.url == article.url

    assert saved.embedding == article.embedding

def test_delete_article():

    repository = VectorRepository(
        QdrantDatabase()
    )

    repository.clear()

    article = create_article()

    repository.save(article)

    repository.delete(article.id)

    assert not repository.exists(article.id)

    assert repository.count() == 0

def test_search_returns_article():

    repository = VectorRepository(
        QdrantDatabase()
    )

    repository.clear()

    article = create_article()

    repository.save(article)

    results = repository.search(
        article.embedding,
        limit=1,
    )

    assert len(results) == 1

    assert results[0].id == article.id
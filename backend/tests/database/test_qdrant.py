from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository

from tests.factories import create_article

import tempfile
import pytest

from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository


def test_save_article(repository):

    article = create_article(
        id="11111111-1111-1111-1111-111111111111"
    )

    repository.save(article)

    assert repository.exists("11111111-1111-1111-1111-111111111111")

    assert repository.count() == 1

def test_get_article(repository):

    repository.clear()

    article = create_article(
        id="11111111-1111-1111-1111-111111111111"
    )

    repository.save(article)

    saved = repository.get("11111111-1111-1111-1111-111111111111")
    
    assert saved is not None

    assert saved.id == article.id

    assert saved.title == article.title

    assert saved.url == article.url

    assert len(saved.embedding) == len(article.embedding)


def test_search_returns_article(repository):

    repository.clear()

    article = create_article()

    repository.save(article)

    results = repository.search(
        article.embedding,
        limit=1,
    )
    print(results[0].article.id)
    print(article.id)
    assert len(results) == 1

    assert results[0].article.id == article.id

def test_delete_article(repository):

    repository.clear()

    article = create_article()

    repository.save(article)

    repository.delete(article.id)

    assert not repository.exists(article.id)

    assert repository.count() == 0
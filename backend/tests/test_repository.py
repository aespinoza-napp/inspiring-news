from src.repositories.local_repository import LocalRepository


def test_repository(tmp_path, example_news):
    repo = LocalRepository(tmp_path)

    repo.save(example_news)

    stored = repo.list()

    assert len(stored) == 1
    assert stored[0].title == example_news.title
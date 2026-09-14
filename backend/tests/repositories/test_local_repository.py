from src.models.core.news import News
from src.repositories.local_repository import LocalRepository


def test_repository(tmp_path, example_news):

    repo = LocalRepository(model=News, folder=tmp_path)

    repo.save(example_news)

    stored = repo.list()

    assert len(stored) == 1
    assert stored[0].title == example_news.title


def test_load_and_delete_round_trip(tmp_path, example_news):

    repo = LocalRepository(model=News, folder=tmp_path)

    repo.save(example_news)

    assert repo.count() == 1
    assert repo.load(example_news.id).id == example_news.id

    repo.delete(example_news.id)

    assert repo.count() == 0
    assert repo.first() is None


def test_list_skips_unreadable_files(tmp_path, example_news):
    """
    A single corrupt file must not take down the whole listing - the
    repository logs it and keeps going.
    """

    repo = LocalRepository(model=News, folder=tmp_path)

    repo.save(example_news)

    (tmp_path / "corrupt.json").write_text("{not json", encoding="utf-8")

    assert len(repo.list()) == 1

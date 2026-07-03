from src.database.source_repository import SourceRepository


def test_source_repository():

    repository = SourceRepository()

    cnn = repository.get("cnn")

    assert cnn is not None
    assert cnn.id == "cnn"
    assert cnn.name == "CNN"
    assert cnn.language == "en"
    assert cnn.country == "US"
    assert cnn.reliability_index == 0.72


def test_list_sources():

    repository = SourceRepository()

    sources = repository.list()
    print(sources)
    assert len(sources) >= 4

    ids = {source.id for source in sources}

    assert ids == {
        "cnn",
        "bbc",
        "reuters",
        "nasa",
    }

def test_get_unknown_source():

    repository = SourceRepository()

    assert repository.get("does_not_exist") is None
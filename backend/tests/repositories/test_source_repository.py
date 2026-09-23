from src.repositories.source_repository import SourceRepository


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

    assert len(sources) >= 4

    ids = {source.id for source in sources}

    # A superset assertion, not equality: adding a source is a YAML file
    # under data/sources/, and an equality check turned every such
    # addition into a spurious test failure.
    assert {"cnn", "bbc", "reuters", "nasa"} <= ids

    # Ids must be unique - two YAML files claiming the same id would
    # silently shadow each other in SourceRepository.get().
    assert len(ids) == len(sources)

def test_get_unknown_source():

    repository = SourceRepository()

    assert repository.get("does_not_exist") is None


def test_source_names_are_read_as_utf_8_on_every_platform():
    """
    open() without an encoding uses the platform's, and on Windows that
    showed "El País" as "El PaÃ­s" on the ingestion panel.
    """

    repository = SourceRepository()

    assert repository.get("el_pais").name == "El País"
    assert "El País" in {source.name for source in repository.list()}

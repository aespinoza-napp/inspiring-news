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


def test_no_two_sources_share_a_domain():
    """
    Both lookups that start from a URL key sources by domain: the
    evidence ranker's reliability map (the later YAML silently overwrites
    the earlier one's rating) and configured_source_for (a posted BBC
    Mundo URL would resolve to "bbc" and be scored as English). A second
    edition of an outlet on the same domain - bbc.com/mundo,
    theconversation.com/es - was left out for this reason.
    """

    from collections import defaultdict
    from urllib.parse import urlsplit

    by_domain = defaultdict(list)

    for source in SourceRepository().list():
        by_domain[urlsplit(str(source.base_url)).netloc.lower().removeprefix("www.")].append(source.id)

    shared = {domain: ids for domain, ids in by_domain.items() if len(ids) > 1}

    assert shared == {}


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

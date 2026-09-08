import json

from src.models.storage.lineage import DataLayer
from src.repositories.lake_backend import JsonFileLakeBackend


def make_document(article_id="a1", run_id="r1", produced_at="2024-01-01T00:00:00"):

    return {
        "record_id": f"{article_id}-{run_id}",
        "lineage": {
            "run_id": run_id,
            "article_id": article_id,
            "layer": "raw",
            "source_url": "https://example.com/a",
            "content_hash": "hash",
            "produced_at": produced_at,
            "parent_layer": None,
            "parent_record_id": None,
            "code_revision": "abc1234",
        },
    }


def test_write_creates_every_layer_directory(tmp_path):

    JsonFileLakeBackend(tmp_path)

    for layer in DataLayer:
        assert (tmp_path / layer.value).is_dir()


def test_write_then_read_round_trip(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    document = make_document()

    backend.write(DataLayer.RAW, "rec1", document)

    assert backend.read(DataLayer.RAW, "rec1") == document


def test_read_returns_none_for_unknown_record(tmp_path):

    assert JsonFileLakeBackend(tmp_path).read(DataLayer.RAW, "nope") is None


def test_write_leaves_no_temp_file_behind(tmp_path):
    """
    Writes go through a temp file + os.replace so a concurrent reader
    never sees a half-written record. The temp file must not survive.
    """

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "rec1", make_document())

    assert list((tmp_path / "raw").glob("*.tmp")) == []
    assert (tmp_path / "raw" / "rec1.json").exists()


def test_write_is_idempotent_for_the_same_record_id(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "rec1", make_document())
    backend.write(DataLayer.RAW, "rec1", make_document())

    assert len(backend.list(DataLayer.RAW)) == 1
    # ...but both writes are still visible in the audit log.
    assert len(backend.manifest()) == 2


def test_list_is_newest_first(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "old", make_document(produced_at="2024-01-01T00:00:00"))
    backend.write(DataLayer.RAW, "new", make_document(produced_at="2025-01-01T00:00:00"))

    assert [d["record_id"] for d in backend.list(DataLayer.RAW)] == [
        "a1-r1",
        "a1-r1",
    ]

    produced = [d["lineage"]["produced_at"] for d in backend.list(DataLayer.RAW)]
    assert produced == sorted(produced, reverse=True)


def test_list_respects_limit(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    for index in range(5):
        backend.write(DataLayer.RAW, f"rec{index}", make_document(article_id=f"a{index}"))

    assert len(backend.list(DataLayer.RAW, limit=2)) == 2


def test_list_of_empty_layer_is_empty(tmp_path):

    assert JsonFileLakeBackend(tmp_path).list(DataLayer.EXPLOITATION) == []


def test_list_skips_a_corrupt_record_instead_of_failing(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "good", make_document())

    (tmp_path / "raw" / "corrupt.json").write_text("{not json", encoding="utf-8")

    assert len(backend.list(DataLayer.RAW)) == 1


def test_find_by_article_filters_on_lineage(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "one", make_document(article_id="wanted"))
    backend.write(DataLayer.RAW, "two", make_document(article_id="other"))

    found = backend.find_by_article(DataLayer.RAW, "wanted")

    assert len(found) == 1
    assert found[0]["lineage"]["article_id"] == "wanted"


def test_manifest_records_one_append_only_entry_per_write(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "rec1", make_document(article_id="a1", run_id="r1"))
    backend.write(DataLayer.PROCESSED, "rec2", make_document(article_id="a1", run_id="r1"))

    entries = backend.manifest()

    assert [entry["layer"] for entry in entries] == ["raw", "processed"]
    assert all(entry["article_id"] == "a1" for entry in entries)
    assert all(entry["run_id"] == "r1" for entry in entries)
    assert all(entry["code_revision"] == "abc1234" for entry in entries)


def test_manifest_is_empty_before_any_write(tmp_path):

    assert JsonFileLakeBackend(tmp_path).manifest() == []


def test_manifest_survives_a_torn_final_line(tmp_path):
    """
    A process killed mid-append leaves a partial JSON line. That must
    cost the one entry, not the whole audit log.
    """

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.RAW, "rec1", make_document())

    with (tmp_path / backend.MANIFEST_NAME).open("a", encoding="utf-8") as handle:
        handle.write('{"layer": "raw", "record_id": "tor')

    assert len(backend.manifest()) == 1


def test_manifest_respects_limit_and_keeps_the_most_recent(tmp_path):

    backend = JsonFileLakeBackend(tmp_path)

    for index in range(5):
        backend.write(DataLayer.RAW, f"rec{index}", make_document(run_id=f"r{index}"))

    entries = backend.manifest(limit=2)

    assert len(entries) == 2
    assert [entry["run_id"] for entry in entries] == ["r3", "r4"]


def test_records_are_stored_as_readable_json(tmp_path):
    """
    The layers are meant to be inspectable with an ordinary text editor -
    that is much of the point of a file-backed lake.
    """

    backend = JsonFileLakeBackend(tmp_path)

    backend.write(DataLayer.EXPLOITATION, "rec1", make_document())

    stored = json.loads(
        (tmp_path / "exploitation" / "rec1.json").read_text(encoding="utf-8")
    )

    assert stored["lineage"]["article_id"] == "a1"

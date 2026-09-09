import json
from src.config.thresholds import PipelineThresholds
from src.services.analysis_cache import AnalysisCache


def test_get_returns_none_when_not_cached(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    assert cache.get("https://example.com/a") is None


def test_set_then_get_roundtrips(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    cache.set("https://example.com/a", {"url": "https://example.com/a", "title": "Test"})

    assert cache.get("https://example.com/a") == {
        "url": "https://example.com/a",
        "title": "Test",
    }


def test_different_urls_use_different_cache_entries(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    cache.set("https://example.com/a", {"title": "A"})
    cache.set("https://example.com/b", {"title": "B"})

    assert cache.get("https://example.com/a") == {"title": "A"}
    assert cache.get("https://example.com/b") == {"title": "B"}


def test_get_returns_none_on_corrupt_cache_file(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    cache._path("https://example.com/a").write_text("not valid json", encoding="utf-8")

    assert cache.get("https://example.com/a") is None


def test_entry_written_by_an_older_schema_is_treated_as_a_miss(tmp_path):
    """
    The cache never expires, so without a version stamp an entry written
    before a response-shape change would be served forever - and a hit
    never rewrites the entry, so it could never heal.
    """

    cache = AnalysisCache(directory=tmp_path)

    cache.set("https://example.com/a", {"title": "Fresh"})

    assert cache.get("https://example.com/a") == {"title": "Fresh"}

    path = cache._path("https://example.com/a")

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["schemaVersion"] = cache.SCHEMA_VERSION - 1
    path.write_text(json.dumps(entry), encoding="utf-8")

    assert cache.get("https://example.com/a") is None


def test_a_raw_pre_versioning_payload_is_treated_as_a_miss(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    cache._path("https://example.com/a").write_text(
        json.dumps({"title": "Written by the old, unversioned cache"}),
        encoding="utf-8",
    )

    assert cache.get("https://example.com/a") is None


def test_a_non_object_payload_is_treated_as_a_miss(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    cache._path("https://example.com/a").write_text("[1, 2, 3]", encoding="utf-8")

    assert cache.get("https://example.com/a") is None


# ----------------------------------------------------------------------
# Thresholds are part of the key
# ----------------------------------------------------------------------


def test_a_run_with_different_thresholds_does_not_read_the_default_entry(tmp_path):
    """
    The same URL analysed against a different admission threshold is a
    different analysis. Serving the default run's cached answer would
    silently ignore the caller's override - the result would look like
    the thresholds had been applied when they never were.
    """

    cache = AnalysisCache(directory=tmp_path)

    cache.set("https://example.com/a", {"title": "Default run"}, PipelineThresholds())

    tuned = PipelineThresholds(positive_impact_min_score=0.9)

    assert cache.get("https://example.com/a", tuned) is None


def test_a_tuned_run_does_not_overwrite_the_default_entry(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    tuned = PipelineThresholds(positive_impact_min_score=0.9)

    cache.set("https://example.com/a", {"title": "Default run"}, PipelineThresholds())
    cache.set("https://example.com/a", {"title": "Tuned run"}, tuned)

    assert cache.get("https://example.com/a", PipelineThresholds())["title"] == "Default run"
    assert cache.get("https://example.com/a", tuned)["title"] == "Tuned run"


def test_the_same_thresholds_hit_the_same_entry(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    tuned = PipelineThresholds(max_claims_per_article=2)

    cache.set("https://example.com/a", {"title": "Tuned"}, tuned)

    assert cache.get(
        "https://example.com/a",
        PipelineThresholds(max_claims_per_article=2),
    )["title"] == "Tuned"


def test_thresholds_equal_to_the_defaults_key_the_same_as_no_thresholds(tmp_path):
    """
    `None` and an unmodified PipelineThresholds are the same run, so they
    must reach the same entry - the key is built from the effective
    values either way.
    """

    cache = AnalysisCache(directory=tmp_path)

    cache.set("https://example.com/a", {"title": "Default run"})

    assert cache.get("https://example.com/a", PipelineThresholds()) is not None


def test_changing_an_env_default_invalidates_the_entry(tmp_path, monkeypatch):
    """
    The hole the effective-value key closes.

    Keying on the *deviation* from the defaults meant a default run
    before an .env change and a default run after it both recorded "no
    overrides" and hashed identically - so the second was served an
    answer computed under the old threshold, with nothing in the
    response saying so. The response shape had not changed, so
    SCHEMA_VERSION could not catch it either.
    """

    from src.config.settings import settings

    cache = AnalysisCache(directory=tmp_path)

    monkeypatch.setattr(settings, "DUPLICATE_THRESHOLD", 0.90)
    cache.set("https://example.com/a", {"computed_under": 0.90}, PipelineThresholds())

    monkeypatch.setattr(settings, "DUPLICATE_THRESHOLD", 0.96)

    assert cache.get("https://example.com/a", PipelineThresholds()) is None


def test_a_forced_refresh_rewrites_the_entry_for_its_own_key(tmp_path):
    """
    force_refresh bypasses the *read*, not the write - the point is to
    replace a stale entry, not to stop caching.
    """

    cache = AnalysisCache(directory=tmp_path)

    tuned = PipelineThresholds(max_claims_per_article=2)

    cache.set("https://example.com/a", {"run": "first"}, tuned)
    cache.set("https://example.com/a", {"run": "second"}, tuned)

    assert cache.get("https://example.com/a", tuned)["run"] == "second"


def test_two_different_overrides_get_two_different_entries(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    first = PipelineThresholds(positive_impact_min_score=0.4)
    second = PipelineThresholds(positive_impact_min_score=0.6)

    cache.set("https://example.com/a", {"which": "first"}, first)
    cache.set("https://example.com/a", {"which": "second"}, second)

    assert cache.get("https://example.com/a", first)["which"] == "first"
    assert cache.get("https://example.com/a", second)["which"] == "second"

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

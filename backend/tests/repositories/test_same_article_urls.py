"""
One article, however its URL is spelled (Sep 21 audit: "URLs are compared
as plain strings"): a tracking parameter, a trailing slash or `www.` no
longer makes a second article in the vector store, the job store or the
analysis cache.
"""

from __future__ import annotations

from qdrant_client.models import PointStruct

from src.services.analysis_cache import AnalysisCache
from src.services.job_store import JobStore

from tests.factories import create_article

PLAIN = "https://www.bbc.com/news/seagrass"
TRACKED = "https://bbc.com/news/seagrass/?utm_source=twitter"


def test_a_reanalysis_under_a_tracking_parameter_replaces_the_earlier_copy(repository):

    repository.save(create_article(id="11111111-1111-1111-1111-111111111111", url=PLAIN))
    repository.save(create_article(id="22222222-2222-2222-2222-222222222222", url=TRACKED))

    assert repository.count() == 1
    assert repository.get("22222222-2222-2222-2222-222222222222").url == TRACKED


def test_the_article_is_excluded_from_its_own_evidence_however_spelled(repository):
    """Its earlier copy must not come back as corroboration of itself."""

    repository.save(create_article(id="11111111-1111-1111-1111-111111111111", url=PLAIN))
    repository.save(create_article(id="33333333-3333-3333-3333-333333333333", url="https://other.org/x"))

    found = repository.search([0.1] * 1024, limit=5, exclude_url=TRACKED)

    assert [hit.article.url for hit in found] == ["https://other.org/x"]


def test_a_point_saved_before_url_key_existed_is_still_excluded_by_its_exact_url(repository):

    legacy = create_article(id="44444444-4444-4444-4444-444444444444", url=PLAIN)

    # As points were written before 2026-10-20: the article's fields only.
    repository.client.upsert(
        collection_name=repository.COLLECTION,
        wait=True,
        points=[PointStruct(id=legacy.id, vector=legacy.embedding, payload=legacy.model_dump(mode="json"))],
    )

    assert repository.search([0.1] * 1024, limit=5, exclude_url=PLAIN) == []
    # And it still reads back as an article.
    assert repository.get(legacy.id).url == PLAIN


def test_two_requests_for_one_article_share_one_job():

    store = JobStore()

    first, reused_first = store.get_or_create(PLAIN)
    second, reused_second = store.get_or_create(TRACKED)

    assert (reused_first, reused_second) == (False, True)
    assert second.job_id == first.job_id

    store.complete(first.job_id, {})

    third, reused = store.get_or_create(TRACKED)
    assert not reused and third.job_id != first.job_id


def test_the_cache_serves_one_article_under_any_spelling(tmp_path):

    cache = AnalysisCache(directory=tmp_path)

    cache.set(PLAIN, {"title": "Seagrass"})

    assert cache.get(TRACKED) == {"title": "Seagrass"}
    assert cache.get("https://bbc.com/news/other") is None

from src.models.storage.lineage import DataLayer
from src.services.scraper.article_stats import article_stats


class FakeLake:
    """Just the `list(layer)` article_stats reads."""

    def __init__(self, raw=(), processed=(), exploitation=()):
        self.layers = {
            DataLayer.RAW: list(raw),
            DataLayer.PROCESSED: list(processed),
            DataLayer.EXPLOITATION: list(exploitation),
        }

    def list(self, layer, limit=None):
        return self.layers[layer]


def raw(url, *, title=None, author=None, published_at=None, language="es",
        content_hash="h1", produced_at="2026-09-22T10:00:00", length=1000):

    return {
        "lineage": {
            "source_url": url,
            "content_hash": content_hash,
            "produced_at": produced_at,
        },
        "article": {
            "url": url,
            "title": title,
            "author": author,
            "published_at": published_at,
            "language": language,
        },
        "content_length": length,
    }


def downstream(url, **fields):
    return {"lineage": {"source_url": url}, **fields}


def test_articles_are_counted_per_domain():

    stats = article_stats(FakeLake(raw=[
        raw("https://www.a.com/1"),
        raw("https://a.com/2", content_hash="h2"),
        raw("https://b.com/1"),
    ]))

    assert stats["totals"]["scraped"] == 3
    assert stats["totals"]["domains"] == 2
    assert [row["domain"] for row in stats["domains"]] == ["a.com", "b.com"]


def test_a_re_analysed_url_is_one_unique_article():
    """
    Every analysis writes a new raw record, so a URL analysed three
    times is three scrapes of one article - with or without a trailing
    slash or a tracking parameter.
    """

    stats = article_stats(FakeLake(raw=[
        raw("https://a.com/story"),
        raw("https://a.com/story/"),
        raw("https://a.com/story?utm_source=x"),
    ]))

    [row] = stats["domains"]
    assert row["scraped"] == 3
    assert row["uniqueUrls"] == 1
    assert row["uniqueContents"] == 1


def test_missing_metadata_is_counted():
    """The gap that hid every title in the lake for weeks."""

    stats = article_stats(FakeLake(raw=[
        raw("https://a.com/1", title="A headline", author="Someone", published_at="2026-08-31"),
        raw("https://a.com/2", title="", author=None),
    ]))

    [row] = stats["domains"]
    assert (row["withTitle"], row["withAuthor"], row["withDate"]) == (1, 1, 1)


def test_what_became_of_the_articles_is_counted_from_the_later_layers():

    stats = article_stats(FakeLake(
        raw=[raw("https://a.com/1"), raw("https://a.com/2", content_hash="h2")],
        processed=[downstream("https://a.com/1"), downstream("https://a.com/2")],
        exploitation=[
            downstream("https://a.com/1", publishable=True),
            downstream("https://a.com/2", publishable=False),
        ],
    ))

    [row] = stats["domains"]
    assert (row["processed"], row["stored"], row["publishable"], row["rejected"]) == (2, 2, 1, 1)


def test_the_daily_series_skips_empty_days_and_is_oldest_first():

    stats = article_stats(FakeLake(raw=[
        raw("https://a.com/1", produced_at="2026-09-22T10:00:00"),
        raw("https://a.com/2", produced_at="2026-09-08T09:00:00"),
        raw("https://a.com/3", produced_at="2026-09-22T18:00:00"),
    ]))

    assert stats["daily"] == [
        {"date": "2026-09-08", "scraped": 1},
        {"date": "2026-09-22", "scraped": 2},
    ]

    [row] = stats["domains"]
    assert (row["firstScraped"], row["lastScraped"]) == ("2026-09-08", "2026-09-22")


def test_an_empty_lake_is_all_zeros():

    stats = article_stats(FakeLake())

    assert stats["totals"]["scraped"] == 0
    assert stats["domains"] == []
    assert stats["daily"] == []

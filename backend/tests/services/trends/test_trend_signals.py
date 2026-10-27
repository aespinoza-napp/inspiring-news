"""
The trend signals (docs/decisions/trends.md): the YAMLs, the readers over
the feeds saved on 2026-10-26, a person's seed, and the news search -
never the live web.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from src.models.core.trend_signal import TrendSignal
from src.repositories.trend_signal_repository import TrendSignalRepository
from src.services.scraper.fetcher import FetchedPage
from src.services.scraper.request_stats import RequestStats
from src.services.search import SearchUnavailableError
from src.services.trends import readers
from src.services.trends.seeds import SeedError, hashtag_words, parse_seed
from src.services.trends.trend_service import TrendService
from src.services.trends.trends import trend_id

BACKEND = Path(__file__).resolve().parents[3]
FIXTURES = BACKEND / "tests" / "fixtures" / "trends"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def signal(**fields) -> TrendSignal:

    defaults = {
        "id": "google_trends_es",
        "name": "Google Trends · Spain",
        "kind": "google_trends",
        "url": "https://trends.google.com/trending/rss?geo=ES",
        "language": "es",
        "country": "ES",
    }

    return TrendSignal(**{**defaults, **fields})


REDDIT = signal(
    id="uplifting_news", name="r/UpliftingNews", kind="ranked_feed",
    url="https://www.reddit.com/r/UpliftingNews/top/.rss?t=day", language="en", country=None, positive=True,
)


# ----------------------------------------------------------------------
# The configured signals
# ----------------------------------------------------------------------


def test_every_configured_signal_loads_once_and_is_free_to_read():

    signals = TrendSignalRepository(str(BACKEND / "data" / "trends")).list()

    assert {s.id for s in signals} == {
        "google_trends_es", "google_trends_us", "uplifting_news", "upworthy", "know_your_meme",
    }
    assert len({s.id for s in signals}) == len(signals)

    # Public feeds over https, none needing a key in its address.
    for configured in signals:
        assert str(configured.url).startswith("https://")
        assert "key=" not in str(configured.url).lower()


def test_tiktok_is_not_a_signal():
    """Its listing needs a signed session and its terms forbid scraping: it reaches us as seeds."""

    signals = TrendSignalRepository(str(BACKEND / "data" / "trends")).list()

    assert not any("tiktok" in str(s.url).lower() for s in signals)


def test_a_signal_in_a_language_without_a_lexicon_is_refused():

    with pytest.raises(ValueError, match="no lexicon"):
        signal(language="fr")


# ----------------------------------------------------------------------
# Google Trends
# ----------------------------------------------------------------------


def test_spains_ten_trends_of_26_october_with_their_thirty_articles():

    trends = readers.read_google_trends(fixture("google_trends_es_2026-10-26.xml"), signal())

    assert len(trends) == 10
    assert sum(len(trend.articles) for trend in trends) == 30
    assert [trend.position for trend in trends] == list(range(1, 11))

    by_name = {trend.name: trend for trend in trends}

    regenta = by_name["ester expósito"]
    assert regenta.traffic == 2000
    assert regenta.started_at == datetime(2026, 10, 26, 13, 20, tzinfo=timezone.utc)
    assert regenta.language == "es"
    assert regenta.link.startswith("https://trends.google.com/trends/explore?q=ester%20exp")
    assert "&geo=ES" in regenta.link
    assert regenta.articles[0].outlet == "ABC"
    assert "La Regenta" in regenta.articles[0].title

    # Entities unescaped: "Rosalía también conquista "La Voz"".
    voz = by_name["antena 3 directo"]
    assert '"La Voz"' in voz.articles[1].title

    metro = by_name["línea 10"]
    assert metro.articles[0].outlet == "EL PAÍS"
    assert metro.articles[0].url.startswith("https://elpais.com/espana/madrid/2026-10-26/")


def test_the_us_trends_read_the_same_way():

    trends = readers.read_google_trends(
        fixture("google_trends_us_2026-10-26.xml"),
        signal(id="google_trends_us", language="en", country="US"),
    )

    assert len(trends) == 10
    assert {trend.language for trend in trends} == {"en"}
    assert max(trend.traffic for trend in trends) == 10000


@pytest.mark.parametrize("text, number", [
    ("500+", 500), ("2000+", 2000), ("2,000+", 2000), ("10K+", 10000), ("1M+", 1_000_000),
    (" 200+ ", 200), ("", None), (None, None), ("lots", None),
])
def test_approximate_searches_are_read_as_numbers(text, number):

    assert readers.parse_traffic(text) == number


def test_a_page_that_is_not_the_feed_is_a_feed_error():

    with pytest.raises(readers.FeedError):
        readers.read_google_trends("<html><body>Sorry, unusual traffic</body></html>", signal())

    with pytest.raises(readers.FeedError):
        readers.read_google_trends("not xml at all", signal())


def test_the_same_trend_read_twice_has_the_same_id():

    assert trend_id("google_trends_es", "Ester Expósito") == trend_id("google_trends_es", "ester exposito")
    assert trend_id("google_trends_es", "ester expósito") != trend_id("google_trends_us", "ester expósito")


# ----------------------------------------------------------------------
# Ranked feeds
# ----------------------------------------------------------------------


def test_a_reddit_post_is_the_article_it_links_to_never_the_thread():

    trends, skipped = readers.read_ranked_feed(fixture("reddit_upliftingnews_2026-10-26.xml"), REDDIT)

    # 25 posts; the moderators' "Quick 2nd Update" is a self-post.
    assert (len(trends), skipped) == (24, 1)

    for trend in trends:
        [article] = trend.articles
        assert "reddit.com" not in article.url and "redd.it" not in article.url
        assert trend.link.startswith("https://www.reddit.com/r/UpliftingNews/comments/")
        # The poster's words and time are not the article's.
        assert article.snippet is None and article.published is None

    assert len({trend.articles[0].url.split("/")[2] for trend in trends}) == 20
    assert [trend.position for trend in trends] == list(range(1, 25))
    assert all(trend.positive for trend in trends)


def test_a_post_from_2016_is_kept_for_the_age_limit_to_judge():
    """The reader does not decide what is old: the round does, by the post's time and the link's date."""

    trends, _ = readers.read_ranked_feed(fixture("reddit_upliftingnews_2026-10-26.xml"), REDDIT)

    dolly = next(trend for trend in trends if trend.name.startswith("Dolly Parton"))

    assert dolly.started_at.year == 2016
    assert "/2016/07/" in dolly.articles[0].url


def test_an_outlets_own_feed_gives_each_item_as_its_article_with_its_time():

    upworthy = signal(id="upworthy", name="Upworthy", kind="ranked_feed", url="https://www.upworthy.com/feed/",
                      language="en", country=None, positive=True)

    trends, skipped = readers.read_ranked_feed(fixture("upworthy_2026-10-26.xml"), upworthy)

    assert (len(trends), skipped) == (10, 0)
    assert trends[0].articles[0].url == trends[0].link
    assert trends[0].articles[0].published == datetime(2026, 10, 26, 3, 37, 21, tzinfo=timezone.utc)
    assert trends[0].articles[0].snippet


def test_know_your_meme_reads_too():

    kym = signal(id="know_your_meme", name="Know Your Meme", kind="ranked_feed",
                 url="https://knowyourmeme.com/newsfeed.rss", language="en", country=None)

    trends, _ = readers.read_ranked_feed(fixture("knowyourmeme_2026-10-26.xml"), kym)

    assert len(trends) == 5
    assert any("Goats" in trend.name for trend in trends)


def test_garbage_is_not_a_ranked_feed():

    with pytest.raises(readers.FeedError):
        readers.read_ranked_feed("<html><body>Too many requests</body></html>", REDDIT)


# ----------------------------------------------------------------------
# The service: fetching, failing soft, counting
# ----------------------------------------------------------------------


class FakeFetcher:
    """Answers each URL from `pages` (text or an exception); records what was asked."""

    def __init__(self, pages: dict):
        self.pages = pages
        self.asked = []

    def get(self, url):
        self.asked.append(url)
        for prefix, answer in self.pages.items():
            if url.startswith(prefix):
                if isinstance(answer, Exception):
                    raise answer
                return FetchedPage(url=url, status=200, html=answer)
        raise requests.ConnectionError(f"nothing canned for {url}")


class FakeSearch:

    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.queries = []

    def search(self, query, max_results=None, language=None):
        self.queries.append((query, language))
        if self.error:
            raise self.error
        return self.results


def trend_service(pages, search=None, signals=None):

    return TrendService(
        signals=signals or [signal(), REDDIT],
        fetcher=FakeFetcher(pages),
        search=search or FakeSearch(),
        stats=RequestStats(),
    )


def test_each_signal_is_read_and_counted_under_trends():

    service = trend_service({
        "https://trends.google.com/": fixture("google_trends_es_2026-10-26.xml"),
        "https://www.reddit.com/": fixture("reddit_upliftingnews_2026-10-26.xml"),
    })

    spain, reddit = service.read()

    assert (len(spain.trends), spain.error) == (10, None)
    assert (len(reddit.trends), reddit.skipped) == (24, 1)
    assert reddit.to_dict()["articles"] == 24

    domains = {row["domain"]: row for row in service.stats.snapshot()["domains"]}
    assert set(domains) >= {"trends.google.com", "reddit.com"}
    assert domains["trends.google.com"]["purposes"] == {"trends": 1}


def test_a_signal_that_fails_is_reported_not_raised():

    service = trend_service({
        "https://trends.google.com/": "<html>unusual traffic</html>",
        "https://www.reddit.com/": requests.ConnectionError("refused"),
    })

    spain, reddit = service.read()

    assert spain.trends == [] and "not an RSS feed" in spain.error
    assert reddit.trends == [] and "refused" in reddit.error


def test_only_the_signals_asked_for_are_read():

    service = trend_service({"https://www.reddit.com/": fixture("reddit_upliftingnews_2026-10-26.xml")})

    [only] = service.read(["uplifting_news"])

    assert only.signal.id == "uplifting_news"
    assert all("trends.google.com" not in url for url in service.fetcher.asked)


def test_a_disabled_signal_is_never_read():

    service = trend_service({}, signals=[signal(enabled=False)])

    assert service.read() == []


def test_a_trends_news_search_adds_articles_after_the_signals_own_once_each():

    search = FakeSearch(results=[
        {"url": "https://www.abc.es/play/series/noticias/netflix-adaptara-regenta-ester-exposito-20261023142856-nt.html",
         "title": "Netflix adaptará 'La Regenta'"},
        {"url": "https://www.rtve.es/cultura/20261026/la-regenta-netflix/", "title": "La Regenta, en Netflix",
         "content": "La novela de Clarín...", "publishedDate": "2026-10-26T09:00:00"},
        {"url": "javascript:alert(1)", "title": "not a page"},
        {"url": "https://example.com/untitled"},
    ])

    service = trend_service(
        {"https://trends.google.com/": fixture("google_trends_es_2026-10-26.xml")}, search=search,
    )

    [spain] = service.read(["google_trends_es"])
    regenta = next(trend for trend in spain.trends if trend.name == "ester expósito")
    before = len(regenta.articles)

    service.search_articles([regenta], per_trend=3)

    assert search.queries == [("!news ester expósito", "es")]
    # ABC's page was already Google's; RTVE's is new; the rest are not pages.
    assert len(regenta.articles) == before + 1
    added = regenta.articles[-1]
    assert (added.found_by, added.url) == ("search", "https://www.rtve.es/cultura/20261026/la-regenta-netflix/")
    assert added.published == datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)


def test_a_search_that_cannot_be_answered_leaves_a_note_and_the_signals_articles():

    service = trend_service(
        {"https://trends.google.com/": fixture("google_trends_es_2026-10-26.xml")},
        search=FakeSearch(error=SearchUnavailableError("every engine suspended")),
    )

    [spain] = service.read(["google_trends_es"])
    metro = next(trend for trend in spain.trends if trend.name == "línea 10")

    service.search_articles([metro])

    assert len(metro.articles) == 3
    assert "could not be answered" in metro.notes[0]


# ----------------------------------------------------------------------
# A person's seed
# ----------------------------------------------------------------------


@pytest.mark.parametrize("tag, words", [
    ("FarmearAura", "Farmear Aura"), ("farmear_aura", "farmear aura"), ("farmearaura", "farmearaura"),
])
def test_a_hashtag_becomes_words_to_search_for(tag, words):

    assert hashtag_words(tag) == words


def test_a_seed_hashtag_is_a_trend_to_search():

    trend = trend_service({}).seed("#FarmearAura #fyp")

    assert (trend.name, trend.seed, trend.signal) == ("Farmear Aura", True, "seed")
    assert trend.articles == [] and trend.video is None


def test_a_seed_tiktok_link_keeps_the_video_and_reads_oembed_once():

    service = trend_service({"https://www.tiktok.com/oembed": fixture("tiktok_oembed_2026-10-26.json")})

    trend = service.seed("#dogs https://www.tiktok.com/@scout2015/video/6718335390845095173")

    assert trend.name == "dogs"
    assert trend.video == {
        "provider": "tiktok",
        "id": "6718335390845095173",
        "url": "https://www.tiktok.com/@scout2015/video/6718335390845095173",
        "title": None,
        "author": None,
    }
    # The video page itself is never fetched: only oEmbed.
    assert len(service.fetcher.asked) == 1
    assert service.fetcher.asked[0].startswith("https://www.tiktok.com/oembed?url=https%3A%2F%2Fwww.tiktok.com")


def test_a_tiktok_link_alone_is_named_by_its_caption():

    service = trend_service({"https://www.tiktok.com/oembed": (
        '{"provider_name": "TikTok", "embed_product_id": "7350000000000000001", '
        '"title": "Abuelos bailando en la plaza #farmearaura #fyp", "author_name": "plaza mayor"}'
    )})

    trend = service.seed("https://www.tiktok.com/@plaza/video/7350000000000000001")

    assert trend.name == "farmearaura"
    assert trend.video["title"].startswith("Abuelos bailando")
    assert trend.video["author"] == "plaza mayor"


def test_when_oembed_is_limited_the_seed_keeps_the_link_and_says_so():

    service = trend_service({"https://www.tiktok.com/oembed": requests.HTTPError("429")})

    trend = service.seed("#dogs https://www.tiktok.com/@scout2015/video/6718335390845095173")

    assert trend.video["id"] == "6718335390845095173"
    assert "oEmbed did not answer" in trend.notes[0]


def test_a_link_with_nothing_to_search_for_is_refused():

    service = trend_service({"https://www.tiktok.com/oembed": requests.HTTPError("429")})

    with pytest.raises(SeedError, match="nothing to search for"):
        service.seed("https://vm.tiktok.com/ZMabc123/")

    with pytest.raises(SeedError):
        parse_seed("   ")


def test_a_news_link_typed_with_a_seed_is_its_first_article():

    trend = trend_service({}).seed("farmear aura https://www.20minutos.es/noticia/farmear-aura-plazas/")

    assert trend.name == "farmear aura"
    assert [(a.url, a.found_by) for a in trend.articles] == [
        ("https://www.20minutos.es/noticia/farmear-aura-plazas/", "seed"),
    ]

import feedparser
import pytest

from src.services.scraper.strategies.rss import RSSDiscoveryStrategy

from tests.builders.source_builder import build_source


def make_source(**kwargs):

    kwargs.setdefault("rss_url", "https://example.com/rss.xml")

    return build_source(**kwargs)


def entry(link: str, title: str, summary: str = "") -> feedparser.FeedParserDict:

    return feedparser.FeedParserDict(link=link, title=title, summary=summary)


class FakeFeed:

    def __init__(self, entries):
        self.entries = entries


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """
    The strategy fetches the feed itself now (feedparser's own HTTP has no
    timeout and skips the URL guard). These tests replace feedparser.parse
    with canned entries, so the fetch only has to return something.
    """

    from src.services.scraper.fetcher import FetchedPage, Fetcher

    monkeypatch.setattr(
        Fetcher,
        "get",
        lambda self, url: FetchedPage(url=url, status=200, html="<rss></rss>"),
    )


def test_discover_matches_by_topic_keyword(monkeypatch):

    entries = [
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
        entry("https://example.com/sport/football-final", "Football final result"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://example.com/space/nasa-launch"]


def test_discover_matches_by_url_pattern_even_without_keyword(monkeypatch):

    entries = [
        entry("https://example.com/space/some-headline", "Some headline"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://example.com/space/some-headline"]


def test_discover_ignores_unrelated_topics(monkeypatch):

    entries = [
        entry("https://example.com/sport/football-final", "Football final result"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == []


def test_discover_ignores_non_article_links(monkeypatch):

    entries = [
        entry("https://example.com/about-us", "space mission announced"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == []


def test_discover_deduplicates_links(monkeypatch):

    entries = [
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://example.com/space/nasa-launch"]


def test_discover_returns_empty_without_rss_url():

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(rss_url=None), topics=["space"])

    assert urls == []


def test_discover_with_no_topics_returns_empty_instead_of_crashing(monkeypatch):
    """
    `topics` defaults to None in the method signature, so it must be a
    genuinely supported input, not just an unused default - calling this
    directly (bypassing Scraper.discover(), which happens to always
    substitute a real topic list) used to raise
    `TypeError: 'NoneType' object is not iterable`.
    """

    entries = [
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    assert strategy.discover(make_source(), topics=None) == []


def test_discover_matches_bbc_style_flat_article_urls(monkeypatch):
    """
    BBC's current RSS feed links to /news/articles/<opaque-id> - no topic
    segment in the path at all. Verified live against the real feed: every
    single BBC article failed the generic "looks like an article" gate
    before this pattern was added, so BBC discovery always returned 0 URLs
    regardless of which topics were requested.
    """

    entries = [
        entry(
            "https://www.bbc.co.uk/news/articles/cy4zejgz3z9o?at_medium=RSS",
            "NASA confirms new Mars mission timeline",
        ),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://www.bbc.co.uk/news/articles/cy4zejgz3z9o?at_medium=RSS"]


def test_discover_excludes_video_pages_even_with_matching_url_segment(monkeypatch):
    """
    Some sources (e.g. CNN) nest video URLs under the same category
    segments as real articles (.../videos/world/...). An unqualified
    substring match on "/world/" let those through, and video pages
    extract as player/caption UI chrome rather than article prose -
    verified live: ClaimExtractor scored a caption fragment at 0.90
    confidence as if it were a real claim.
    """

    entries = [
        entry(
            "https://www.cnn.com/videos/space/2023/04/02/nasa-launch-vpx.cnn",
            "NASA launches new telescope",
        ),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    # Same topic/keyword match as test_discover_matches_by_topic_keyword
    # above - proving it's specifically the "/videos/" segment, not a
    # topic/keyword mismatch, that excludes this one.
    assert strategy.discover(make_source(), topics=["space"]) == []


# ----------------------------------------------------------------------
# Article shape in any language, and a topic filter only where it works
# ----------------------------------------------------------------------


import pytest as _pytest


@_pytest.mark.parametrize("url", [
    "https://www.elmundo.es/internacional/2026/09/23/6ab35dc6e9cf4aed758b458c.html",
    "https://elpais.com/espana/madrid/2026-09-23/maricarmen-se-queda.html",
    "https://www.lavanguardia.com/internacional/20260923/11641410/xi-jinping.html",
    "https://science.nasa.gov/earth/earth-observatory/boom-year-for-desert-blooms/",
])
def test_articles_are_recognised_by_date_or_headline_slug_in_any_language(url):
    """Every one of these was dropped by the English section-name patterns."""

    assert RSSDiscoveryStrategy()._is_article(url)


@_pytest.mark.parametrize("url", [
    "https://www.abc.es/",
    "https://elpais.com/espana/",
    "https://www.bbc.co.uk/news/videos/cjp306113l0wo",
])
def test_homepages_sections_and_videos_are_not_articles(url):

    assert not RSSDiscoveryStrategy()._is_article(url)


def test_a_spanish_feed_is_not_filtered_by_english_keywords(monkeypatch):
    """
    Every TOPICS keyword is English; against a Spanish feed they kept 5 of
    El País's 149 entries, at random. Asked for every topic - ingestion
    without groups, the labelling batch - a Spanish feed keeps every
    article, and topic is left to the admission filter.
    """

    from src.config.topics import TOPICS

    entries = [
        entry("https://elpais.com/espana/2026-09-23/una-donante-anonima-paga-el-alquiler.html",
              "Una donante anónima se ofrece a pagar el alquiler"),
        entry("https://elpais.com/espana/2026-10-05/sanchez-adelanta-las-elecciones.html",
              "Sánchez adelanta las elecciones al 29 de noviembre"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda text: FakeFeed(entries))

    urls = RSSDiscoveryStrategy().discover(make_source(language="es"), topics=list(TOPICS))

    assert urls == [item.link for item in entries]


def test_a_narrowed_spanish_feed_is_filtered_by_spanish_keywords(monkeypatch):
    """
    2026-10-05: an Environment round listed El País's and elDiario's
    election coverage, because Spanish feeds were never filtered.
    """

    from src.config.topics import TOPIC_GROUPS

    elections = entry("https://elpais.com/espana/2026-10-05/sanchez-adelanta-las-elecciones.html",
                      "Sánchez adelanta las elecciones al 29 de noviembre")
    birds = entry("https://elpais.com/2026-10-05/el-delta-recupera-sus-colonias.html",
                  "El delta del Ebro recupera aves que no anidaban desde 1990")
    wind = entry("https://www.eldiario.es/economia/2026-10-05/record-eolico.html",
                 "La energía eólica cubrió la mitad de la demanda")
    speech = entry("https://www.eldiario.es/politica/2026-10-05/discurso.html",
                   "Lee el discurso completo sobre las elecciones anticipadas",
                   summary="... las renovables, la cosecha, el medioambiente y la energía ...")

    monkeypatch.setattr(feedparser, "parse", lambda text: FakeFeed([elections, birds, wind, speech]))

    urls = RSSDiscoveryStrategy().discover(make_source(language="es"), topics=TOPIC_GROUPS["environment"])

    # The wind record is filed under /economia/ but speaks of energy: kept.
    # The speech only mentions energy in its summary, which is not read.
    assert urls == [birds.link, wind.link]


def test_a_spanish_section_of_a_topic_asked_for_needs_no_keyword(monkeypatch):

    link = "https://elpais.com/clima-y-medio-ambiente/2026-10-05/un-informe-sin-palabras-clave.html"
    monkeypatch.setattr(feedparser, "parse", lambda text: FakeFeed([entry(link, "Un informe")]))

    assert RSSDiscoveryStrategy().discover(make_source(language="es"), topics=["climate"]) == [link]


def test_spanish_keywords_start_words_and_short_ones_are_whole_words():

    from src.services.scraper.strategies.rss import _mentions

    arts = {"arte ", "museo"}

    assert _mentions(entry("https://x.es/a", "El arte urbano llega al barrio"), arts)
    assert not _mentions(entry("https://x.es/a", "Una parte del presupuesto"), arts)
    assert _mentions(entry("https://x.es/a", "La energía eólica"), {"energ"})
    assert not _mentions(entry("https://x.es/a", "Sinergias políticas"), {"energ"})


def test_an_english_feed_is_still_filtered_by_topic(monkeypatch):

    entries = [
        entry("https://example.com/2026/09/23/football-final-result", "Football final result"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda text: FakeFeed(entries))

    assert RSSDiscoveryStrategy().discover(make_source(language="en"), topics=["space"]) == []


# ----------------------------------------------------------------------
# Off-mission sections, sections of another topic, and what a candidate
# list shows (src/services/ingestion_service.py's candidate rounds)
# ----------------------------------------------------------------------


def test_an_off_mission_section_is_dropped_whatever_was_asked(monkeypatch):
    """2026-10-05: a /deportes/ match report reached the labelling batch."""

    entries = [
        entry("https://www.lavanguardia.com/deportes/futbol-femenino/20261005/11651238/claudia-pina.html", "Claudia Pina"),
        entry("https://www.lavanguardia.com/natural/20261005/11651300/rewilding-the-ebro-delta.html", "Rewilding"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    urls = RSSDiscoveryStrategy().discover(make_source(language="es"), topics=None)

    assert urls == ["https://www.lavanguardia.com/natural/20261005/11651300/rewilding-the-ebro-delta.html"]


def test_a_fitness_section_is_not_mistaken_for_sport(monkeypatch):

    link = "https://www.example.es/deporte-y-salud/20261005/caminar-diez-mil-pasos.html"
    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed([entry(link, "Caminar")]))

    assert RSSDiscoveryStrategy().discover(make_source(language="es"), topics=["fitness"]) == [link]


def test_a_link_filed_under_a_topic_not_asked_for_is_dropped(monkeypatch):
    """
    A Spanish feed is not keyword-filtered (the keywords are English),
    so its section names are what narrow it to the groups picked.
    """

    science = "https://elpais.com/ciencia/2026-10-05/un-telescopio-descubre-agua.html"
    climate = "https://elpais.com/clima-y-medio-ambiente/2026-10-05/el-delta-recupera-aves.html"
    unfiled = "https://elpais.com/2026-10-05/una-historia-sin-seccion-en-la-ruta.html"

    entries = [
        entry(science, "Un telescopio descubre agua"),
        entry(climate, "x"),
        entry(unfiled, "Vuelven las aves al delta"),
    ]
    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    urls = RSSDiscoveryStrategy().discover(make_source(language="es"), topics=["climate", "nature"])

    assert urls == [climate, unfiled]

    from src.services.scraper.strategies.rss import filed_under

    assert filed_under(climate) == {"climate"} and filed_under(unfiled) == set()


def test_asking_for_every_topic_drops_nothing_for_its_section(monkeypatch):

    science = "https://elpais.com/ciencia/2026-10-05/un-telescopio-descubre-agua.html"
    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed([entry(science, "x")]))

    from src.config.topics import TOPICS

    assert RSSDiscoveryStrategy().discover(make_source(language="es"), topics=list(TOPICS)) == [science]


def test_items_carry_the_feeds_title_and_a_plain_text_summary(monkeypatch):

    link = "https://example.com/environment/2026/10/05/mangroves-cut-storm-waves"
    summary = "<p>Mangroves cut storm waves by <b>59%</b> &amp; more.</p>" + " word" * 200

    monkeypatch.setattr(
        feedparser, "parse", lambda url: FakeFeed([entry(link, "Mangroves &amp; waves", summary)])
    )

    [item] = RSSDiscoveryStrategy().discover_items(make_source(), topics=["climate"])

    assert item.title == "Mangroves & waves"
    assert item.summary.startswith("Mangroves cut storm waves by 59% & more.")
    assert len(item.summary) <= 401 and item.summary.endswith("…")

import requests

from src.services.scraper.fetcher import FetchedPage
from src.services.scraper.strategies.topic_pages import TopicPageDiscoveryStrategy

from tests.builders.source_builder import build_source


def http_error(status: int) -> requests.HTTPError:

    return requests.HTTPError(str(status), response=type("R", (), {"status_code": status})())


class FakeFetcher:
    """Pages by URL; anything not listed is a 404. Records every request."""

    def __init__(self, pages: dict):
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str) -> FetchedPage:

        self.requested.append(url)

        page = self.pages.get(url, http_error(404))

        if isinstance(page, Exception):
            raise page

        return FetchedPage(url=url, status=200, html=page)


def anchors(*hrefs: str) -> str:

    return "<html><body>" + "".join(f'<a href="{href}">x</a>' for href in hrefs) + "</body></html>"


HOME = "https://news.example/"
SCIENCE = "https://news.example/science/"

ARTICLE = "https://news.example/science/2026/09/23/telescope-finds-water"
OTHER_ARTICLE = "https://news.example/science/rover-lands-safely-on-the-moon"


def strategy(pages: dict, **kwargs) -> tuple[TopicPageDiscoveryStrategy, FakeFetcher]:

    fetcher = FakeFetcher(pages)

    return TopicPageDiscoveryStrategy(fetcher=fetcher, **kwargs), fetcher


def source(**kwargs):

    kwargs.setdefault("base_url", HOME)
    kwargs.setdefault("language", "en")

    return build_source(**kwargs)


def test_sections_the_homepage_links_to_are_read_for_article_links():

    discovery, _ = strategy({
        HOME: anchors("/science/", "/about-us"),
        SCIENCE: anchors(ARTICLE, "/science/rover-lands-safely-on-the-moon"),
    }, max_sections=1)

    assert discovery.discover(source(), topics=["research"]) == [ARTICLE, OTHER_ARTICLE]


def test_advertised_sections_are_read_before_any_guess():

    discovery, fetcher = strategy({
        HOME: anchors("/science/"),
        SCIENCE: anchors(ARTICLE),
    }, max_sections=1)

    result = discovery.crawl(source(), topics=["research"])

    assert [section.url for section in result.sections] == [SCIENCE]
    assert result.sections[0].advertised is True
    assert fetcher.requested == [HOME, SCIENCE]


def test_a_section_is_guessed_when_the_homepage_links_none():

    discovery, _ = strategy({
        HOME: anchors("/about-us"),
        "https://news.example/space/": anchors("https://news.example/space/2026/09/23/launch-day"),
    })

    result = discovery.crawl(source(), topics=["space"])

    [section] = [s for s in result.sections if s.links]

    assert section.url == "https://news.example/space/"
    assert section.advertised is False
    assert result.urls == ["https://news.example/space/2026/09/23/launch-day"]


def test_a_guess_that_404s_is_reported_and_costs_nothing_else():

    discovery, _ = strategy({HOME: anchors()})

    result = discovery.crawl(source(), topics=["space"])

    [section] = result.sections

    assert section.outcome == "http_error"
    assert section.status == 404
    assert result.urls == []


def test_nothing_is_guessed_when_the_homepage_itself_is_refused():
    """EFE and Reuters refused the homepage and then every guess the same way."""

    discovery, fetcher = strategy({HOME: http_error(403)})

    result = discovery.crawl(source(), topics=["space", "research"])

    assert result.homepage_status == 403
    assert result.homepage_outcome == "http_error"
    assert result.sections == []
    assert fetcher.requested == [HOME]


def test_links_to_other_sites_sections_and_the_page_itself_are_dropped():

    discovery, _ = strategy({
        HOME: anchors("/science/"),
        SCIENCE: anchors(
            ARTICLE,
            "https://ads.elsewhere.com/2026/09/23/buy-this-great-thing-now",
            "/science/",          # the page itself
            "/health/",           # a sibling section
            "/contact",           # not article-shaped
            "#top",
        ),
    }, max_sections=1)

    assert discovery.discover(source(), topics=["research", "medicine"]) == [ARTICLE]


def test_a_subdomain_of_the_source_counts_as_the_same_site():
    """NASA's science sections live on science.nasa.gov."""

    discovery, _ = strategy({
        HOME: anchors("https://science.news.example/astrophysics/"),
        "https://science.news.example/astrophysics/": anchors(
            "https://science.news.example/astrophysics/webb-sees-the-first-galaxies",
        ),
    }, max_sections=1)

    assert discovery.discover(source(), topics=["space"]) == [
        "https://science.news.example/astrophysics/webb-sees-the-first-galaxies",
    ]


def test_spanish_sources_are_guessed_in_spanish():
    """El País files science under /ciencia/; /science/ there is a 404."""

    discovery, fetcher = strategy({HOME: anchors()}, max_sections=2)

    discovery.crawl(source(language="es"), topics=["research"])

    assert "https://news.example/ciencia/" in fetcher.requested
    assert SCIENCE not in fetcher.requested


def test_a_spanish_section_linked_from_the_homepage_is_recognised():

    discovery, _ = strategy({
        HOME: anchors("/ciencia/"),
        "https://news.example/ciencia/": anchors("/ciencia/2026-09-25/un-telescopio-encuentra-agua.html"),
    }, max_sections=1)

    assert discovery.discover(source(language="es"), topics=["research"]) == [
        "https://news.example/ciencia/2026-09-25/un-telescopio-encuentra-agua.html",
    ]


def test_the_number_of_sections_read_is_capped():

    discovery, fetcher = strategy({HOME: anchors()}, max_sections=3)

    result = discovery.crawl(source())

    assert len(result.sections) == 3
    assert len(fetcher.requested) == 1 + 3


def test_an_empty_section_says_so():

    discovery, _ = strategy({HOME: anchors("/science/"), SCIENCE: anchors("/contact")}, max_sections=1)

    [section] = discovery.crawl(source(), topics=["research"]).sections

    assert section.outcome == "ok"
    assert section.links == []
    assert section.error == "no article links on the page"


def test_through_discovery_the_sections_are_crawled_not_the_feed():
    """
    DiscoveryService asks for items. The strategy inherits a feed reader
    from RSSDiscoveryStrategy; from 2026-10-04 to 2026-10-05 that is what
    answered, re-reading the dead feed instead of crawling a section.
    """

    from src.services.scraper.discovery import DiscoveryService
    from src.services.scraper.request_stats import RequestStats

    topic_pages, fetcher = strategy({HOME: anchors("/science/"), SCIENCE: anchors(ARTICLE)})

    result = DiscoveryService([topic_pages], stats=RequestStats()).run(
        source(rss_url="https://news.example/dead-feed.xml"), topics=["research"]
    )

    assert result.urls == [ARTICLE]
    assert "https://news.example/dead-feed.xml" not in fetcher.requested


def test_links_in_an_off_mission_section_are_not_kept():
    """A science section's sidebar still links the match reports."""

    match_report = "https://news.example/sport/2026/10/05/a-seven-nil-win"

    topic_pages, _ = strategy({HOME: anchors("/science/"), SCIENCE: anchors(ARTICLE, match_report)})

    assert topic_pages.discover(source(), topics=["research"]) == [ARTICLE]


def test_a_section_that_files_its_articles_under_itself_keeps_only_those():
    """2026-10-06: ABC's /cultura/ page linked the day's election stories under /espana/."""

    top_story = "https://news.example/politics/2026/10/05/the-election-is-called"

    topic_pages, _ = strategy({HOME: anchors("/science/"), SCIENCE: anchors(ARTICLE, top_story, OTHER_ARTICLE)})

    assert topic_pages.discover(source(), topics=["research"]) == [ARTICLE, OTHER_ARTICLE]


def test_a_section_whose_articles_carry_no_section_keeps_every_article_link():
    """SINC files every article under /Noticias/, whatever its section."""

    flat = [
        "https://news.example/Noticias/la-obesidad-activa-un-mecanismo-del-corazon",
        "https://news.example/2026/10/05/rover-lands-safely",
    ]

    topic_pages, _ = strategy({HOME: anchors("/science/"), SCIENCE: anchors(*flat)})

    assert topic_pages.discover(source(), topics=["research"]) == flat


def test_a_section_pages_own_navigation_is_not_an_article():
    """2026-10-05: BBC's section pages gave /culture/music as a candidate."""

    navigation = ["https://news.example/science/space", "https://news.example/science/strategy/"]
    article = "https://news.example/science/articles/c0abc123"

    topic_pages, _ = strategy({HOME: anchors("/science/"), SCIENCE: anchors(*navigation, article, ARTICLE)})

    assert topic_pages.discover(source(), topics=["research"]) == [article, ARTICLE]




def test_a_section_pages_links_are_titled_with_their_headlines():
    """
    Until 2026-10-09 a section page's candidates were titled from their
    slugs ("Aniversario bizum cambio nuestra forma pagar cumple anos").
    The page links each with its headline; an image link has none.
    """

    from src.services.scraper.strategies.topic_pages import TopicPageDiscoveryStrategy

    section = """<html><body>
      <a href="/noticias/20261009/aniversario-bizum-cumple-10-anos/17258658.shtml"><img src="x.jpg"></a>
      <a href="/noticias/20261009/aniversario-bizum-cumple-10-anos/17258658.shtml">Noticia: Bizum cumple diez años: así cambió nuestra forma de pagar</a>
      <a href="/noticias/20261009/otro-articulo-sin-titular-largo/17258659.shtml">Leer más</a>
    </body></html>"""

    class Pages:
        def get(self, url):
            html = '<a href="/cultura/">Cultura</a>' if url.rstrip("/").endswith("rtve.es") else section
            return type("Page", (), {"url": url, "status": 200, "html": html})()

    from tests.builders.source_builder import build_source

    items = TopicPageDiscoveryStrategy(fetcher=Pages()).discover_items(
        build_source(id="rtve", base_url="https://www.rtve.es", language="es"), topics=["arts"],
    )

    titles = {item.url.rsplit("/", 2)[-2]: item.title for item in items}
    assert titles["aniversario-bizum-cumple-10-anos"] == "Bizum cumple diez años: así cambió nuestra forma de pagar"
    assert titles["otro-articulo-sin-titular-largo"] is None



def test_a_source_that_names_its_sections_is_read_there_not_where_topic_names_guess():
    """Smithsonian: a guessed /food/ gave food travel as Environment; its section is /science-nature/."""

    from src.services.scraper.strategies.topic_pages import TopicPageDiscoveryStrategy
    from tests.builders.source_builder import build_source

    asked = []

    class Pages:
        def get(self, url):
            asked.append(url)
            return type("Page", (), {"url": url, "status": 200, "html": "<html></html>"})()

    smithsonian = build_source(
        id="smithsonian", base_url="https://www.smithsonianmag.com",
        groups=["environment", "culture"],
        sections={"environment": ["/science-nature/"], "culture": ["/arts-culture/", "/history/"]},
    )

    TopicPageDiscoveryStrategy(fetcher=Pages()).crawl(smithsonian, topics=["climate", "nature", "energy", "sustainability", "food"])

    assert asked == ["https://www.smithsonianmag.com/", "https://www.smithsonianmag.com/science-nature/"]


def test_a_section_for_an_unknown_group_is_refused():

    import pytest
    from pydantic import ValidationError
    from tests.builders.source_builder import build_source

    with pytest.raises(ValidationError, match="unknown topic group"):
        build_source(sections={"sports": ["/sport/"]})

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


def test_lifestyle_and_crime_sections_are_off_mission():
    """2026-10-06: El País's ICON gave a Brad Pitt stunt double as a Culture candidate."""

    from src.services.scraper.strategies.rss import off_mission

    assert off_mission("https://elpais.com/icon/2026-10-06/joel-el-espanol-que-ha-doblado-las-escenas-de-riesgo-de-brad-pitt.html")
    assert off_mission("https://www.lavanguardia.com/sucesos/20261005/11651111/detenido-en-cornella.html")
    assert not off_mission("https://elpais.com/cultura/2026-10-06/norman-foster-en-vivienda.html")


@pytest.mark.parametrize("url", [
    # 2026-10-06, a Science and Society round: election night and student protests, live.
    "https://elpais.com/espana/2026-10-06/elecciones-generales-del-29-n-en-directo.html",
    "https://www.france24.com/es/francia/20261006-en-directo-sindicatos-se-suman-a-protestas-estudiantiles",
    "https://www.bbc.co.uk/news/live/c4g0yq9l2zpt",
    "https://elpais.com/opinion/2026-10-06/si-ya-dicen-lo-que-dicen.html",
    "https://www.theguardian.com/commentisfree/2026/oct/06/a-column",
])
def test_live_coverage_and_opinion_are_off_mission(url):

    from src.services.scraper.strategies.rss import off_mission

    assert off_mission(url)


@pytest.mark.parametrize("url", [
    # 2026-10-09: the live pages that got through, each with its own marker.
    "https://www.20minutos.es/nacional/ultimas-noticias-maricarmen-vivienda-acampadas-sol-campana-electoral-29-n-directo_7046881_6.html",
    "https://www.rtve.es/noticias/20261009/premio-nobel-paz-2026-ganador-directo-video-cronica/17259964.shtml",
    "https://www.rtve.es/noticias/20261009/elecciones-ultima-hora-espana-directo-hoy-cronica/17259683.shtml",
    "https://www.france24.com/en/france/20261009-live-141-french-high-schools-closed-as-student-protests-continue-for-fifth-day",
    "https://www.rtve.es/noticias/20261008/premio-nobel-literatura-2026-directo-cronica/17258339.shtml",
    "https://www.rtve.es/noticias/20261010/directo-hoy-dia-mundial-salud-mental-2026-cronica/17259451.shtml",
])
def test_live_pages_are_told_by_their_slugs_too(url):

    from src.services.scraper.strategies.rss import off_mission

    assert off_mission(url)


@pytest.mark.parametrize("url", [
    # "live" is a verb in headlines, and "directo" a word: neither alone marks a live page.
    "https://www.france24.com/en/europe/20261009-where-people-live-longest-in-europe",
    "https://elpais.com/economia/2026-10-09/el-pago-directo-a-los-agricultores-llega-antes.html",
])
def test_live_and_directo_inside_a_headline_are_not_live_coverage(url):

    from src.services.scraper.strategies.rss import off_mission

    assert not off_mission(url)


@pytest.mark.parametrize("url", [
    # Every one a candidate on 2026-10-09.
    "https://www.theguardian.com/science/audio/2026/oct/07/all-the-news-and-science-from-the-2026-nobel-prizes-podcast",
    "https://edition.cnn.com/audio/podcasts/all-there-is-with-anderson-cooper",
    "https://science.nasa.gov/image-article/apod-2026-october-9-stickney-crater/",
    "https://www.eldiario.es/edcreativo/descarbonizar-reutilizar-digitalizar-cambiando-gestion-agua_1_13532481.html",
    "https://www.lavanguardia.com/comprar/mas-valorados/20260429/11524304/mejores-telescopios-comparativa-mkt-eo.html",
    "https://muyinteresante.okdiario.com/bazar/roborock-planta-cara-a-irobot-con-una-potente-rebaja-en-su-robot-aspirador-qrevo-2-prox.html",
    "https://elpais.com/gastronomia/el-comidista/2026-10-09/calamares-de-campo-la-receta-de-posguerra-que-sigue-estando-buenisima.html",
    "https://www.eldiario.es/sociedad/fotos-espana-sale-calle-maricarmen-imagenes_3_13573853.html",
    "https://www.20minutos.es/bc/dos-alternativas-movilidad-eficiente-kia-stonic-ev3_7046665_5.html",
    # A slug before an id: RTVE's.
    "https://www.rtve.es/television/20261006/receta-quiche-salmon-santiago-segura-masterchef-celebrity-legends/17254090.shtml",
    # CNN's news sitemap lists its shopping deals.
    "https://www.cnn.com/cnn-underscored/deals/best-amazon-prime-day-deals-2026-10-09",
])
def test_podcasts_galleries_branded_shopping_and_recipes_are_not_articles(url):

    from src.services.scraper.strategies.rss import article_shaped

    assert not article_shaped(url)
    assert not RSSDiscoveryStrategy()._is_article(url)


@pytest.mark.parametrize("url", [
    # MIT News ends its slugs with the date: four words with it.
    "https://news.mit.edu/2026/supporting-systems-success-1008",
    # "Recetas" as a metaphor, not a recipe: only a slug that starts "receta-" is one.
    "https://www.eldiario.es/economia/recetas-responsable-economico-vox-rumbo-privatizacion-pensiones-irpf-medida-ricos_1_13572527.html",
    "https://www.agenciasinc.es/Noticias/La-receta-electronica-llega-a-todas-las-farmacias",
])
def test_headlines_that_only_resemble_those_formats_are_articles(url):

    from src.services.scraper.strategies.rss import article_shaped

    assert article_shaped(url)
    assert RSSDiscoveryStrategy()._is_article(url)


@pytest.mark.parametrize("url", [
    "https://www.agenciasinc.es/Especiales/Incendios-forestales-en-Espana",
    "https://www.xatakaciencia.com/categoria/no-te-lo-creas",
    "https://news.example/tag/climate-change-and-the-oceans",
    "https://news.example/author/maria-lopez-garcia-ruiz",
])
def test_index_pages_are_not_articles_however_their_slugs_read(url):

    from src.services.scraper.strategies.rss import article_shaped

    assert not article_shaped(url)
    assert not RSSDiscoveryStrategy()._is_article(url)


@pytest.mark.parametrize("url, day", [
    ("https://www.abc.es/economia/cuentas-corrientes/calcula-hipoteca-20260525124640-nt.html", "2026-05-25"),
    ("https://www.rtve.es/television/20260623/preparate-para-noche-magica/17128523.shtml", "2026-06-23"),
    ("https://elpais.com/clima/2026-10-05/el-delta-del-ebro-recupera-aves.html", "2026-10-05"),
    ("https://www.elmundo.es/espana/2026/10/05/6ac3cf9121efa09b738b459c.html", "2026-10-05"),
    ("https://www.bbc.co.uk/news/articles/cq203mymlvkeo", None),
    # WHO dates its links day first; its dead feed's 2025 items read as undated.
    ("https://www.who.int/news/item/06-03-2025-strengthening-public-health-across-lebanon-with-eib-global", "2025-03-06"),
    # Not a date: an id that happens to start with 20.
    ("https://news.example/story/20261399887766-a-long-headline-here", None),
])
def test_a_link_can_carry_its_own_date(url, day):

    from src.services.scraper.strategies.rss import date_from_url

    found = date_from_url(url)

    assert (found.date().isoformat() if found else None) == day


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

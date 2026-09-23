import json

from src.services.scraper.fetcher import FetchedPage
from src.services.scraper.strategies.beautifulsoup import BeautifulSoupStrategy

from tests.builders.source_builder import build_source

URL = "https://example.com/story"

PARAGRAPH = (
    "Hay algo que los jóvenes están haciendo en las plazas de México y "
    "España que los adultos llevamos años sin hacer."
)


class NoNetwork:
    """The cascade hands BeautifulSoup a page; it must never fetch one."""

    def get(self, url):
        raise AssertionError(f"BeautifulSoup fetched {url} instead of reading the page it was given")


def parse(html: str, **source):

    strategy = BeautifulSoupStrategy(fetcher=NoNetwork())

    return strategy.attempt(
        build_source(**source),
        URL,
        FetchedPage(url=URL, status=200, html=html),
    )


def test_the_page_it_is_handed_is_read_without_fetching():

    attempt = parse(f"<html><body><article><p>{PARAGRAPH}</p></article></body></html>")

    assert attempt.outcome == "ok"
    assert attempt.sent == 0


def test_an_article_declared_in_json_ld_is_used_whole():
    """
    Sites that show a teaser often put the full text in the JSON-LD -
    exactly the page trafilatura's heuristics give up on.
    """

    declared = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "name": "Not this"},
            {
                "@type": "NewsArticle",
                "headline": "Farmear aura: qué es",
                "author": [{"@type": "Person", "name": "Natalia Soto"}],
                "datePublished": "2026-08-31T09:00:00+02:00",
                "articleBody": PARAGRAPH * 3,
            },
        ],
    }

    attempt = parse(
        "<html><head>"
        f'<script type="application/ld+json">{json.dumps(declared)}</script>'
        "</head><body><p>Suscríbete para leer más.</p></body></html>"
    )

    result = attempt.result

    assert result.title == "Farmear aura: qué es"
    assert result.author == "Natalia Soto"
    assert str(result.published_at.date()) == "2026-08-31"
    assert result.body.startswith("Hay algo")


def test_meta_tags_fill_the_metadata():

    attempt = parse(
        "<html><head>"
        '<meta property="og:title" content="A headline">'
        '<meta name="author" content="Someone">'
        '<meta property="article:published_time" content="2026-09-01T10:00:00Z">'
        '<meta property="og:image" content="https://example.com/a.jpg">'
        f"</head><body><main><p>{PARAGRAPH}</p></main></body></html>"
    )

    result = attempt.result

    assert (result.title, result.author) == ("A headline", "Someone")
    assert str(result.published_at.date()) == "2026-09-01"
    assert result.lead_image == "https://example.com/a.jpg"


def test_a_sources_own_selectors_win():
    """`metadata.selectors` in a source's YAML, for layouts nothing guesses."""

    attempt = parse(
        "<html><body>"
        f"<div class='promo'><p>{'Promo text that is long enough to count. ' * 3}</p></div>"
        f"<div class='cuerpo'><p>{PARAGRAPH}</p></div>"
        "<span class='firma'>Ana Pérez</span>"
        "</body></html>",
        metadata={"selectors": {"body": ".cuerpo", "author": ".firma"}},
    )

    assert attempt.result.body == PARAGRAPH
    assert attempt.result.author == "Ana Pérez"


def test_without_a_known_container_the_densest_block_of_paragraphs_wins():

    attempt = parse(
        "<html><body>"
        "<div id='sidebar'><p>Lo más leído hoy en la portada del periódico digital.</p></div>"
        f"<div id='x1'><p>{PARAGRAPH}</p><p>{PARAGRAPH}</p><p>{PARAGRAPH}</p></div>"
        "</body></html>"
    )

    assert attempt.result.body == "\n\n".join([PARAGRAPH] * 3)


def test_navigation_scripts_and_captions_are_not_the_article():

    attempt = parse(
        "<html><body>"
        f"<nav><p>{'Inicio · Sociedad · Cultura · Ciencia · Deportes · Opinión' * 2}</p></nav>"
        "<script>var tracking = 'a very long script body that must never be text';</script>"
        f"<article><p>Foto: EFE</p><p>{PARAGRAPH}</p></article>"
        "</body></html>"
    )

    assert attempt.result.body == PARAGRAPH


def test_a_page_with_no_article_is_no_content():

    attempt = parse("<html><body><p>Cookies.</p></body></html>")

    assert attempt.result is None
    assert attempt.outcome == "no_content"


def test_a_malformed_date_is_left_empty_rather_than_guessed():

    attempt = parse(
        '<html><head><meta property="article:published_time" content="ayer"></head>'
        f"<body><article><p>{PARAGRAPH}</p></article></body></html>"
    )

    assert attempt.result.published_at is None

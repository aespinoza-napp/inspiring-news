"""Reading a WordPress export (services/imports/wordpress.py)."""

import pytest

from src.services.imports.wordpress import NotAnExport, html_to_text, parse

AUTHOR = """<wp:author><wp:author_login><![CDATA[nsoto]]></wp:author_login>
<wp:author_email><![CDATA[nsoto@example.com]]></wp:author_email>
<wp:author_display_name><![CDATA[Natalia Soto]]></wp:author_display_name></wp:author>"""


def item(wp_id, title, body, status="publish", kind="post", date="2026-10-30 10:47:23", link=None):

    return f"""<item>
<title><![CDATA[{title}]]></title>
<link>{link or f"https://inspiringnews.ai/sociedad/p{wp_id}/"}</link>
<dc:creator><![CDATA[nsoto]]></dc:creator>
<content:encoded><![CDATA[{body}]]></content:encoded>
<wp:post_id>{wp_id}</wp:post_id>
<wp:post_date_gmt><![CDATA[{date}]]></wp:post_date_gmt>
<wp:status><![CDATA[{status}]]></wp:status>
<wp:post_type><![CDATA[{kind}]]></wp:post_type>
<category domain="category" nicename="sociedad"><![CDATA[SOCIEDAD]]></category>
<category domain="post_tag" nicename="lo-mas-leido"><![CDATA[Lo más leído]]></category>
</item>"""


def export(*items: str) -> bytes:

    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
 xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:wp="http://wordpress.org/export/1.2/">
<channel><title>Inspiring News - Buenas noticias</title><link>https://inspiringnews.ai</link>
<language>es</language><wp:wxr_version>1.2</wp:wxr_version>
<wp:base_site_url>https://inspiringnews.ai</wp:base_site_url>
{AUTHOR}
{"".join(items)}
</channel></rss>""".encode("utf-8")


BODY = """<!-- wp:paragraph --><p>Olga Moraga analiza&nbsp;los peligros de la sobreinformación.</p><!-- /wp:paragraph -->
<figure><img src="x.jpg"/><figcaption>Foto: EFE</figcaption></figure>
<p>Según el <a href="https://www.copclm.com/">Colegio</a>, el teléfono <strong>no ha dejado</strong> de sonar.
Lee también <a href="https://inspiringnews.ai/otra/">otra noticia</a>.</p>
[elementor-template id="12"]"""


def test_a_post_becomes_the_text_a_reader_sees_with_its_sources():

    (post,) = parse(export(item(7332, "La línea de ayuda", BODY))).posts

    assert post.text == (
        "Olga Moraga analiza los peligros de la sobreinformación.\n\n"
        "Según el Colegio, el teléfono no ha dejado de sonar. Lee también otra noticia."
    )
    # Its own site's links are not its sources; an outside page is.
    assert post.sources == ["https://www.copclm.com/"]
    assert post.published_at == "2026-10-30T10:47:23+00:00"
    assert post.categories == ["SOCIEDAD"] and post.tags == ["Lo más leído"]
    assert post.author == "Natalia Soto"
    assert len(post.content_hash) == 64


def test_no_author_email_is_kept():

    found = parse(export(item(1, "Uno", BODY)))

    assert "nsoto@example.com" not in str([post.row() for post in found.posts])


def test_only_the_statuses_asked_for_and_no_attachments():

    data = export(
        item(1, "Publicada", BODY),
        item(2, "Privada", BODY + " privada", status="private"),
        item(3, "Borrador", BODY + " borrador", status="draft", date="0000-00-00 00:00:00"),
        item(4, "foto.jpg", "", status="inherit", kind="attachment"),
    )

    assert [post.wp_id for post in parse(data).posts] == [1]

    every = parse(data, ("publish", "private", "draft")).posts
    assert sorted(post.wp_id for post in every) == [1, 2, 3]
    # A draft's zero date is no date, and sorts last.
    assert every[-1].wp_id == 3 and every[-1].published_at is None


def test_a_repeated_post_is_marked_never_dropped():

    posts = parse(export(
        item(1, "Monos que bromean", BODY, date="2024-02-15 12:20:14"),
        item(2, "Monos que bromean", BODY + " otra versión", date="2024-03-01 09:00:00"),
        item(3, "Otra cosa", BODY, date="2024-04-01 09:00:00"),
    )).posts

    assert [(post.wp_id, post.duplicate_of) for post in posts] == [(1, None), (2, 1), (3, 1)]


@pytest.mark.parametrize("data, message", [
    (b"<html><body>no</body></html>", "Not a WordPress export"),
    (b"<rss><channel>", "Not well-formed"),
    (b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "aaaa">]><rss/>', "DOCTYPE"),
])
def test_what_is_not_an_export_is_refused(data, message):

    with pytest.raises(NotAnExport, match=message):
        parse(data)


def test_an_unknown_status_is_refused():

    with pytest.raises(NotAnExport, match="Unknown post status"):
        parse(export(), ("published",))


def test_a_classic_editor_post_is_split_where_wordpress_would():

    text, _ = html_to_text("Primer párrafo,\nsu segunda línea.\n\nSegundo párrafo.")

    assert text == "Primer párrafo,\n\nsu segunda línea.\n\nSegundo párrafo."


def test_scripts_and_styles_are_not_text():

    text, links = html_to_text("<style>p{}</style><p>Hola</p><script>alert(1)</script><p>mundo</p>")

    assert text == "Hola\n\nmundo" and links == []

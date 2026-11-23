"""Reading a WordPress export (services/imports/wordpress.py)."""

import hashlib

import pytest

from src.services.imports.wordpress import NotAnExport, html_to_text, parse

AUTHOR = """<wp:author><wp:author_login><![CDATA[nsoto]]></wp:author_login>
<wp:author_email><![CDATA[nsoto@example.com]]></wp:author_email>
<wp:author_display_name><![CDATA[Natalia Soto]]></wp:author_display_name></wp:author>"""


def item(wp_id, title, body, status="publish", kind="post", date="2026-10-30 10:47:23", link=None, meta=None):

    postmeta = "".join(
        f"<wp:postmeta><wp:meta_key><![CDATA[{key}]]></wp:meta_key><wp:meta_value><![CDATA[{value}]]></wp:meta_value></wp:postmeta>"
        for key, value in (meta or {}).items()
    )

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
{postmeta}
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


# ---------------------------------------------------------------------------
# The list of sources a post ends with, cut from its text (2026-11-20)
# ---------------------------------------------------------------------------

STORY = """<p>En Hawái puedes llevarte un perro prestado a la playa.</p>
<p>La Kauaʻi Humane Society lo empezó en 2016, y muchos acaban adoptándolo.</p>"""


def only_post(body: str):

    (post,) = parse(export(item(6644, "Perros prestados", body))).posts

    return post


def test_a_list_of_sources_is_cut_from_the_text_and_kept_beside_it():
    """
    "Fuentes" read as text was a person to GLiNER (5 posts of 2026-11-03),
    and every outlet in the list one of the story's names.
    """

    post = only_post(STORY + """<p><strong>Fuentes:</strong></p>
<ul><li><a href="https://kauaihumane.org/fieldtrip/">Kauaʻi Humane Society</a></li>
<li>- NPR.</li></ul>""")

    assert post.text.endswith("muchos acaban adoptándolo.")
    assert "Fuentes" not in post.text and "NPR" not in post.text
    assert post.source_list == [
        {"text": "Kauaʻi Humane Society", "url": "https://kauaihumane.org/fieldtrip/"},
        {"text": "NPR", "url": None},
    ]
    # Still among the outside pages it links to.
    assert post.sources == ["https://kauaihumane.org/fieldtrip/"]
    # The hash is of the text the pipeline reads.
    assert post.content_hash == hashlib.sha256(post.text.encode("utf-8")).hexdigest()


def test_one_source_on_the_heading_s_line_is_cut_wherever_it_is():

    url = "https://www.billboard.com/music/pop/lewis-capaldi-donates-734000-hours-free-therapy-1236015556/"
    post = only_post(STORY + f'<p><em><strong>Fuente original:</strong> <a href="{url}">{url}</a></em></p>')

    assert "Fuente" not in post.text
    assert post.source_list == [{"text": "billboard.com", "url": url}]


def test_a_post_ending_in_links_to_other_sites_ends_in_its_sources():

    post = only_post(STORY + """<p>Si te ha gustado esta noticia, descubre más <a href="https://inspiringnews.ai/noticias/">aquí</a>.</p>
<ul><li><a href="https://earthlymission.com/marine-fossils/">Earthly Mission</a></li>
<li><a href="https://www.iflscience.com/marine-fossils-72096">IFL Science</a></li></ul>""")

    assert post.text.endswith("descubre más aquí.")
    assert [item["text"] for item in post.source_list] == ["Earthly Mission", "IFL Science"]


def test_a_sentence_about_sources_is_the_story_s_own():

    body = "<p>Fuentes de la catedral resaltan que Sant Sever es uno de los pocos ejemplos.</p>" + STORY
    post = only_post(body)

    assert post.text.startswith("Fuentes de la catedral") and post.source_list == []


def test_a_heading_with_a_paragraph_after_it_is_not_the_end_of_the_post():

    paragraph = "Un párrafo largo de la noticia que sigue, " * 8
    post = only_post(STORY + f"<p>Fuentes</p><p>{paragraph}</p>")

    assert paragraph.strip() in post.text and post.source_list == []


# ---------------------------------------------------------------------------
# Its photos (2026-11-20)
# ---------------------------------------------------------------------------

METADATA = (
    'a:6:{s:5:"width";i:1344;s:6:"height";i:768;s:4:"file";s:23:"2025/02/tmpnjt92rgc.png";s:8:"filesize";i:1271448;'
    's:5:"sizes";a:2:{s:9:"thumbnail";a:5:{s:4:"file";s:23:"tmpnjt92rgc-150x150.png";s:5:"width";i:150;s:6:"height";i:150;'
    's:9:"mime-type";s:9:"image/png";s:8:"filesize";i:39474;}s:12:"medium_large";a:5:{s:4:"file";s:23:"tmpnjt92rgc-768x439.png";'
    's:5:"width";i:768;s:6:"height";i:439;s:9:"mime-type";s:9:"image/png";s:8:"filesize";i:411677;}}}'
)


def attachment(wp_id: int, url: str, alt: str = "", caption: str = "", metadata: str = "") -> str:

    return f"""<item>
<title><![CDATA[foto]]></title>
<link>https://inspiringnews.ai/?attachment_id={wp_id}</link>
<excerpt:encoded><![CDATA[{caption}]]></excerpt:encoded>
<wp:post_id>{wp_id}</wp:post_id>
<wp:status><![CDATA[inherit]]></wp:status>
<wp:post_type><![CDATA[attachment]]></wp:post_type>
<wp:attachment_url><![CDATA[{url}]]></wp:attachment_url>
<wp:postmeta><wp:meta_key><![CDATA[_wp_attachment_metadata]]></wp:meta_key><wp:meta_value><![CDATA[{metadata}]]></wp:meta_value></wp:postmeta>
<wp:postmeta><wp:meta_key><![CDATA[_wp_attachment_image_alt]]></wp:meta_key><wp:meta_value><![CDATA[{alt}]]></wp:meta_value></wp:postmeta>
</item>"""


def test_a_post_keeps_its_featured_photo_with_its_sizes():

    (post,) = parse(export(
        attachment(267, "https://inspiringnews.ai//wp-content/uploads/2025/02/tmpnjt92rgc.png", alt="Monos que bromean", metadata=METADATA),
        item(250, "Monos que bromean", BODY, meta={"_thumbnail_id": "267"}),
    )).posts

    # BODY's own <img src="x.jpg"> is no address anyone can fetch: not one of its photos.
    (photo,) = post.images

    # One slash where the export has two: one photo, one address.
    assert photo == {
        "url": "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc.png",
        "alt": "Monos que bromean",
        "caption": None,
        "width": 1344,
        "height": 768,
        "attachment_id": 267,
        "featured": True,
        "sizes": {
            "thumbnail": {"url": "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc-150x150.png", "width": 150, "height": 150},
            "medium_large": {"url": "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc-768x439.png", "width": 768, "height": 439},
        },
    }
    assert post.image_url == photo["url"]


def test_a_photo_in_the_text_keeps_its_caption_and_its_attachment_s_sizes():

    body = STORY + """<figure class="wp-block-image size-full"><img src="https://inspiringnews.ai//wp-content/uploads/2025/12/2-3.png" alt=""
 class="wp-image-5814"/><figcaption class="wp-element-caption">Participantes del Spogomi 2025.</figcaption></figure>
<p>Y el texto sigue.</p>"""

    (post,) = parse(export(
        attachment(5814, "https://inspiringnews.ai//wp-content/uploads/2025/12/2-3.png", alt="Spogomi", metadata=METADATA),
        attachment(7345, "https://inspiringnews.ai/wp-content/uploads/2026/10/portada.png"),
        item(6000, "Spogomi", body, meta={"_thumbnail_id": "7345"}),
    )).posts

    featured, inline = post.images

    assert featured["featured"] and featured["url"].endswith("/portada.png")
    assert inline["featured"] is False
    assert inline["caption"] == "Participantes del Spogomi 2025."
    # The tag has no alt; its attachment does.
    assert inline["alt"] == "Spogomi" and inline["attachment_id"] == 5814
    assert set(inline["sizes"]) == {"thumbnail", "medium_large"}
    # The caption is the photo's, not a sentence of the story.
    assert "Spogomi 2025" not in post.text and post.text.endswith("Y el texto sigue.")


def test_the_featured_photo_shown_again_in_the_text_is_one_photo():

    url = "https://inspiringnews.ai/wp-content/uploads/2026/10/portada.png"

    (post,) = parse(export(
        attachment(7345, url),
        item(6000, "Portada", STORY + f'<figure><img src="{url}" class="wp-image-7345"/></figure>', meta={"_thumbnail_id": "7345"}),
    )).posts

    assert [image["url"] for image in post.images] == [url]


def test_a_post_with_no_photo_has_none():

    post = only_post(STORY)

    assert post.images == [] and post.image_url is None

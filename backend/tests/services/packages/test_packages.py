"""
Ready-to-post packages (src/services/packages/): what each channel gets,
that text never leaves a frame's safe margins, the captions, the
WordPress files and sending them only as a draft.
"""

import json
import zipfile
import io
import xml.etree.ElementTree as ElementTree

import pytest
from PIL import Image
from pydantic import SecretStr

from src.config.settings import settings
from src.models.writer.draft import DraftContent, DraftMetadata
from src.services.packages import cards, content, video, wordpress
from src.services.packages.builder import NotPackageable, PackageBuilder, PackageNotFound
from tests.factories import create_draft
from tests.services.corrector.test_grounding_index import new_heart

SITE = "https://inspiring.example"

BODY = (
    "The meadow in the bay of Girona has doubled its area since 2015 [1].\n\n"
    "Fish counts in the restored meadow rose by 40 percent in five years [2].\n\n"
    "## Why it matters\n\n"
    "Seagrass stores carbon and shelters young fish, the report found [1]."
)


def approved(**changes):

    draft = create_draft(
        content=DraftContent(
            title="Seagrass meadows return to the bay",
            subtitle="Ten years of replanting doubled the meadow's area",
            body=BODY,
        ),
        metadata=DraftMetadata(slug="seagrass-returns", tags=["seagrass", "ocean restoration"], keywords=["Girona"]),
    )

    return draft.model_copy(update={"status": "approved", **changes})


@pytest.fixture
def builder(tmp_path, monkeypatch):

    # No ffmpeg unless a test says so: the suite never shells out.
    monkeypatch.setattr(video, "available", lambda: False)

    return PackageBuilder(tmp_path / "packages", SITE)


# ----------------------------------------------------------------------
# What is packaged
# ----------------------------------------------------------------------


def test_only_an_approved_or_published_draft_that_is_not_busy_is_packaged(builder):

    with pytest.raises(NotPackageable):
        builder.build(approved(status="draft"))

    with pytest.raises(NotPackageable):
        builder.build(approved(busy="reviewing"))

    assert builder.build(approved()).draft_status == "approved"


def test_every_channel_gets_its_files_at_its_size(builder):

    manifest = builder.build(approved())

    assert [channel.channel for channel in manifest.channels] == ["wordpress", "instagram", "stories", "tiktok"]

    sizes = {"instagram": (1080, 1350), "stories": (1080, 1920), "tiktok": (1080, 1920)}

    folder = builder.root / manifest.draft_id / manifest.id

    for entry in manifest.files:

        assert (folder / entry.path).is_file()

        if entry.path.endswith(".png"):
            with Image.open(folder / entry.path) as image:
                assert image.size == sizes[entry.channel] == (entry.width, entry.height)

    carousel = [entry for entry in manifest.files if entry.channel == "instagram" and entry.kind == "card"]
    assert 3 <= len(carousel) <= 9


def test_the_manifest_is_written_and_read_back(builder):

    manifest = builder.build(approved(), ["instagram"])

    assert builder.get(manifest.draft_id, manifest.id) == manifest
    assert [item.id for item in builder.list(manifest.draft_id)] == [manifest.id]
    assert manifest.content_hash == content.content_hash(approved())


def test_only_the_channels_asked_for_are_built(builder):

    manifest = builder.build(approved(), ["stories"])

    assert [channel.channel for channel in manifest.channels] == ["stories"]
    assert {entry.channel for entry in manifest.files} == {"stories"}


# ----------------------------------------------------------------------
# Safe margins
# ----------------------------------------------------------------------


def outside_is_empty(path, form: cards.Format) -> bool:
    """Every pixel outside the safe box is the background: no text there."""

    with Image.open(path) as image:

        pixels = image.convert("RGB").load()
        box = form.safe

        for y in range(0, form.height, 3):
            for x in range(0, form.width, 3):
                inside = box.left <= x < box.right and box.top <= y < box.bottom
                if not inside and pixels[x, y] != cards.BACKGROUND:
                    return False

    return True


@pytest.mark.parametrize("channel, form", [("stories", cards.STORY), ("tiktok", cards.TIKTOK), ("instagram", cards.CAROUSEL)])
def test_text_stays_inside_the_safe_margins(builder, channel, form):

    long_title = "A very long headline about seagrass meadows that keep growing back " * 2

    draft = approved(content=DraftContent(title=long_title.strip(), subtitle="A standfirst " * 8, body=BODY))

    manifest = builder.build(draft, [channel])
    folder = builder.root / manifest.draft_id / manifest.id

    frames = [entry.path for entry in manifest.files if entry.path.endswith(".png")]

    assert frames
    assert all(outside_is_empty(folder / path, form) for path in frames)


def test_a_point_too_long_for_a_card_is_left_out_never_cut():

    long = "The restored meadow " + "kept growing across the bay in every season " * 8 + "[1]."

    draft = approved(content=DraftContent(title="t", subtitle="s", body=f"{long}\n\nFish counts rose by 40 percent in five years [2]."))

    points = content.read(draft, SITE).points

    assert [point.text for point in points] == ["Fish counts rose by 40 percent in five years."]


# ----------------------------------------------------------------------
# What the text says
# ----------------------------------------------------------------------


def test_a_point_names_its_sources_instead_of_numbering_them():

    points = content.read(approved(), SITE).points

    assert points[0].text == "The meadow in the bay of Girona has doubled its area since 2015."
    assert points[0].sources == ["example.org"]


def test_an_uncited_point_names_the_source_that_says_it():

    draft, _ = new_heart()

    points = content.read(draft, SITE).points

    named = [point for point in points if "New Heart" in point.text]

    assert named and named[0].sources == ["elmundo.es"]


def test_the_link_is_the_public_page_only_once_published():

    assert content.read(approved(), SITE).link is None
    assert content.read(approved(status="published"), None).link is None
    assert content.read(approved(status="published"), SITE).link.startswith(f"{SITE}/reader/stories/")


def test_captions_carry_the_disclosure_the_link_and_fit_the_limit(builder):

    manifest = builder.build(approved(status="published"), ["instagram", "tiktok"])

    for channel in manifest.channels:

        assert len(channel.caption) <= content.CAPTION_LIMIT
        assert "Written with AI" in channel.caption
        assert manifest.link in channel.caption
        assert "#Seagrass" in channel.caption and "#OceanRestoration" in channel.caption


def test_an_unpublished_draft_says_where_its_link_will_be(builder):

    manifest = builder.build(approved(), ["instagram", "stories"])

    assert manifest.link is None
    assert any("No public link" in note for note in manifest.notes)
    assert "added when the article is published" in manifest.channels[0].caption


def test_a_long_caption_drops_points_never_a_sentence():

    text = content.read(approved(), SITE)
    text.points = [content.Point(text="A point that is a whole sentence. " * 12)] * 10

    caption = content.caption(text, 10, "Link in bio")

    assert len(caption) <= content.CAPTION_LIMIT
    assert caption.count("•") < 10
    assert text.disclosure in caption


def test_hashtags_are_camel_case_once_each_and_capped():

    tags = content.hashtags(["ocean restoration", "Ocean Restoration", "salud cardíaca", "x", *[f"tag {n} a" for n in range(20)]])

    assert tags[:2] == ["#OceanRestoration", "#SaludCardíaca"]
    assert len(tags) == content.MAX_HASHTAGS


# ----------------------------------------------------------------------
# TikTok's video
# ----------------------------------------------------------------------


def test_no_ffmpeg_no_video_and_the_manifest_says_so(builder):

    manifest = builder.build(approved(), ["tiktok"])

    assert not any(entry.kind == "video" for entry in manifest.files)
    assert any("ffmpeg" in note for note in manifest.notes)


def test_with_ffmpeg_the_video_is_in_the_package(builder, monkeypatch):

    def slideshow(frames, out):
        out.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return out

    monkeypatch.setattr(video, "slideshow", slideshow)

    manifest = builder.build(approved(), ["tiktok"])

    assert "tiktok/video.mp4" in manifest.channels[0].files
    assert any(entry.kind == "video" and entry.width == 1080 for entry in manifest.files)


# ----------------------------------------------------------------------
# WordPress
# ----------------------------------------------------------------------


def test_post_json_is_a_draft_with_linked_citations_and_sources(builder):

    manifest = builder.build(approved(status="published"), ["wordpress"])
    post = builder.post_for(manifest.draft_id, manifest.id)

    assert post["status"] == "draft"
    assert post["slug"] == "seagrass-returns"
    assert '<sup><a href="#source-1">[1]</a></sup>' in post["content"]
    assert '<li id="source-2">' in post["content"]
    assert "<h2>Why it matters</h2>" in post["content"]
    assert "Written with AI" in post["content"]


def test_post_xml_is_one_draft_item_the_importer_reads(builder):

    manifest = builder.build(approved(), ["wordpress"])
    path, _ = builder.file(manifest.draft_id, manifest.id, "wordpress/post.xml")

    root = ElementTree.parse(path).getroot()
    namespace = {"wp": "http://wordpress.org/export/1.2/", "content": "http://purl.org/rss/1.0/modules/content/"}

    items = root.findall("./channel/item")

    assert len(items) == 1
    assert items[0].find("wp:status", namespace).text == "draft"
    assert "#source-1" in items[0].find("content:encoded", namespace).text
    assert [tag.text for tag in items[0].findall("category")] == ["seagrass", "ocean restoration"]


def test_html_in_the_draft_is_escaped():

    draft = approved(content=DraftContent(title="t", subtitle="s", body="A <script>x</script> line that says 2015 [1]."))

    assert "<script>" not in wordpress.body_html(draft, content.read(draft))


class FakeResponse:

    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


class FakeSession:

    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


@pytest.fixture
def site(monkeypatch):

    monkeypatch.setattr(settings, "WORDPRESS_URL", "https://news.example/")
    monkeypatch.setattr(settings, "WORDPRESS_USER", "editor")
    monkeypatch.setattr(settings, "WORDPRESS_APP_PASSWORD", SecretStr("abcd efgh"))


def test_nothing_is_sent_without_the_sites_keys(monkeypatch):

    monkeypatch.setattr(settings, "WORDPRESS_URL", None)

    assert not wordpress.configured()

    with pytest.raises(wordpress.WordPressNotConfigured):
        wordpress.send_draft({"title": "t"}, FakeSession(FakeResponse(201, {"id": 1})))


def test_a_post_is_always_sent_as_a_draft(site):

    session = FakeSession(FakeResponse(201, {"id": 42, "status": "draft"}))

    delivery = wordpress.send_draft({"title": "t", "status": "publish"}, session)

    url, kwargs = session.calls[0]

    assert url == "https://news.example/wp-json/wp/v2/posts"
    assert json.loads(kwargs["data"])["status"] == "draft"
    assert kwargs["auth"] == ("editor", "abcd efgh")
    assert delivery.post_id == 42 and delivery.status == "draft"


def test_a_site_that_refuses_is_reported(site):

    with pytest.raises(wordpress.WordPressRefused, match="401: Sorry"):
        wordpress.send_draft({"title": "t"}, FakeSession(FakeResponse(401, {"message": "Sorry"})))


def test_an_application_password_is_never_sent_over_plain_http(site, monkeypatch):

    monkeypatch.setattr(settings, "WORDPRESS_URL", "http://news.example")

    with pytest.raises(wordpress.WordPressRefused, match="https"):
        wordpress.send_draft({"title": "t"}, FakeSession(FakeResponse(201, {"id": 1})))


# ----------------------------------------------------------------------
# Reading a package back
# ----------------------------------------------------------------------


def test_the_zip_holds_the_manifest_and_every_file(builder):

    manifest = builder.build(approved())

    with zipfile.ZipFile(io.BytesIO(builder.zip(manifest.draft_id, manifest.id))) as archive:
        names = set(archive.namelist())

    assert names == {"manifest.json", *(entry.path for entry in manifest.files)}


def test_only_a_file_the_manifest_names_is_served(builder):

    manifest = builder.build(approved(), ["wordpress"])

    with pytest.raises(PackageNotFound):
        builder.file(manifest.draft_id, manifest.id, "../../../etc/passwd")

    with pytest.raises(PackageNotFound):
        builder.file(manifest.draft_id, manifest.id, "manifest.json")

    with pytest.raises(PackageNotFound):
        builder.get(manifest.draft_id, "../" + manifest.id)

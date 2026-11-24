"""
The news map read from the graph (MAP_SOURCE=graph): the WordPress
import's articles, which the lake never publishes, placed and linked as
the lake's are. Against RecordingGraphClient: no database.
"""

import json

import pytest
from fastapi.testclient import TestClient

import src.api.map_routes as map_routes
from src.config.topics import TOPICS
from src.database.neo4j_client import GraphUnavailable, ReadResult
from src.main import app
from src.services.news_map import graph_source
from src.services.news_map.graph_source import ARTICLES, GraphMapIndex, article_from_graph
from src.services.news_map.layout import GROUP_OF
from src.services.reader.views import reader_id

from tests.services.graph.fake_graph_client import RecordingGraphClient

SOURCE = "wordpress:inspiringnews.ai"


def row(slug: str, topic: str = "climate", entities=(), claims=(), analyzed_at="2026-11-03T14:23:48", **extra) -> dict:
    return {
        "graph_id": f"g-{slug}",
        "url": f"https://inspiringnews.ai/medio-ambiente/{slug}/",
        "title": extra.pop("title", f"Una historia sobre {slug}"),
        "language": "es",
        "published_at": extra.pop("published_at", "2025-02-26T11:46:10+00:00"),
        "analyzed_at": analyzed_at,
        "run_id": f"run-{slug}",
        "source_id": SOURCE,
        "source": "inspiringnews.ai",
        "topics": [{"topic": TOPICS[topic].name, "confidence": 0.41}] if topic else [],
        "entities": [{"name": name, "type": kind} for name, kind in entities],
        "claims": [{"id": f"c-{i}", "text": text} for i, text in enumerate(claims)],
        **extra,
    }


def result(*rows) -> ReadResult:
    return ReadResult(columns=list(rows[0]) if rows else [], rows=list(rows), truncated=False, notices=[])


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_it_reads_only_the_source_it_was_given_from_the_positive_graph():

    graph = RecordingGraphClient(reads=[result(row("lobos"))])
    index = GraphMapIndex(graph, SOURCE)

    articles = index.articles()

    assert [read["params"] for read in graph.reads_made] == [{"source": SOURCE}]
    assert graph.reads_made[0]["query"] == ARTICLES
    assert "a.source_id = $source" in ARTICLES
    assert [a.id for a in articles] == [reader_id("https://inspiringnews.ai/medio-ambiente/lobos/")]


@pytest.mark.parametrize("source_id", ["", None])
def test_with_no_source_it_reads_every_article_of_the_graph(source_id):
    """
    The default since 2026-11-23 (MAP_GRAPH_SOURCE_ID empty): the import and
    every analysis the pipeline wrote, whose source_id is null, "web" or a
    configured source's - so no one value could name them all.
    """

    analysed = row("guardian", source_id=None, source="The Guardian", verdict="FALSE",
                   url="https://www.theguardian.com/world/2026/oct/31/jamaica-beaches")
    graph = RecordingGraphClient(reads=[result(row("lobos"), analysed)])

    articles = GraphMapIndex(graph, source_id).articles()

    assert [read["params"] for read in graph.reads_made] == [{"source": None}]
    assert "$source IS NULL" in ARTICLES
    assert {a.source for a in articles} == {"inspiringnews.ai", "The Guardian"}


def test_the_settings_read_every_article_of_the_graph_by_default():

    from src.config.settings import Settings

    fields = Settings.model_fields
    assert fields["MAP_SOURCE"].default == "graph"
    assert fields["MAP_GRAPH_SOURCE_ID"].default == ""


def test_an_article_is_placed_by_its_topic_with_no_vector_and_no_verdict():

    article = article_from_graph(row("lobos", topic="nature"), {})

    assert article.group == GROUP_OF["nature"]
    assert article.topics == (("nature", 0.41),)
    assert article.approximate == "no_vector"
    assert article.vector is None
    assert article.verdict is None
    assert article.evidence == frozenset()
    assert article.day == "2025-02-26"


def test_a_checked_article_shows_the_verdict_the_graph_recorded():

    assert article_from_graph(row("lobos", verdict="FALSE"), {}).verdict == "FALSE"
    assert article_from_graph(row("lobos", verdict="PARTIALLY_TRUE"), {}).verdict == "PARTIALLY_TRUE"
    # Not checked (the import): no verdict, which the universe says as "not checked".
    assert article_from_graph(row("lobos", verdict=None), {}).verdict is None


def test_a_verdict_the_page_does_not_know_is_no_verdict():
    """The label becomes a CSS class in the universe: only Verdict's own values pass."""

    assert article_from_graph(row("lobos", verdict='TRUE" onmouseover="x'), {}).verdict is None
    assert article_from_graph(row("lobos", verdict="true"), {}).verdict is None


def test_an_article_with_no_topic_goes_on_the_rim():

    assert article_from_graph(row("suelto", topic=None), {}).approximate == "no_topic"


def test_names_are_ranked_by_title_then_by_mentions_in_the_claims_and_common_nouns_hidden():

    article = article_from_graph(row(
        "lobos",
        title="Nacen ocho lobos en Karnataka",
        entities=[("India", "country"), ("Karnataka", "city"), ("Bankapur", "location"), ("investigadores", "person")],
        claims=["Bankapur está en India.", "El santuario de Bankapur protege lobos."],
    ), {})

    assert [e.name for e in article.entities] == ["Karnataka", "Bankapur", "India"]


def test_two_articles_naming_the_same_entity_are_related():

    graph = RecordingGraphClient(reads=[result(
        row("lobos", entities=[("Karnataka", "city")]),
        row("tigres", entities=[("Karnataka", "city")]),
        row("ballenas", topic="energy", entities=[("Noruega", "country")]),
    )])
    index = GraphMapIndex(graph, SOURCE)

    lobos = reader_id("https://inspiringnews.ai/medio-ambiente/lobos/")
    tigres = reader_id("https://inspiringnews.ai/medio-ambiente/tigres/")

    links = index.links(lobos)

    assert links["related"][0]["id"] == tigres
    assert {via["kind"] for via in links["related"][0]["via"]} == {"entity", "topic"}

    document = index.articles_document()
    assert document["count"] == 3
    assert set(document["articles"]["v"]) == {None}
    assert set(document["articles"]["approx"]) == {"no_vector"}


def test_the_graph_is_read_again_only_after_the_refresh_interval():

    clock = Clock()
    graph = RecordingGraphClient(reads=[result(row("lobos")), result(row("lobos"), row("tigres"))])
    index = GraphMapIndex(graph, SOURCE, clock=clock)

    assert len(index.articles()) == 1
    clock.now += graph_source.REFRESH_SECONDS - 1
    assert len(index.articles()) == 1
    assert len(graph.reads_made) == 1

    clock.now += 2
    assert len(index.articles()) == 2
    assert len(graph.reads_made) == 2


def test_neo4j_down_before_the_first_read_is_an_error_and_after_it_the_last_read_is_served():

    with pytest.raises(GraphUnavailable):
        GraphMapIndex(RecordingGraphClient(down=True), SOURCE).articles()

    clock = Clock()
    graph = RecordingGraphClient(reads=[result(row("lobos"))])
    index = GraphMapIndex(graph, SOURCE, clock=clock)
    assert len(index.articles()) == 1

    graph.down = True
    clock.now += graph_source.REFRESH_SECONDS + 1
    assert len(index.articles()) == 1


def test_two_nodes_for_one_article_keep_the_later_analysis():

    graph = RecordingGraphClient(reads=[result(
        row("lobos", title="Primera lectura", analyzed_at="2026-11-03T10:00:00"),
        row("lobos", title="Segunda lectura", analyzed_at="2026-11-03T12:00:00"),
    )])

    assert [a.title for a in GraphMapIndex(graph, SOURCE).articles()] == ["Segunda lectura"]


def test_the_route_answers_503_when_the_graph_was_never_reachable(monkeypatch):

    index = GraphMapIndex(RecordingGraphClient(down=True), SOURCE)
    monkeypatch.setattr(map_routes, "get_map_index", lambda: index)

    response = TestClient(app).get("/map/articles")

    assert response.status_code == 503
    assert "MAP_SOURCE=graph" in response.json()["detail"]


def test_the_route_serves_the_graphs_articles(monkeypatch):

    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"), row("tigres"))]), SOURCE)
    monkeypatch.setattr(map_routes, "get_map_index", lambda: index)

    response = TestClient(app).get("/map/articles")

    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["sources"] == ["inspiringnews.ai"]


def test_every_name_of_a_story_leaves_the_server_not_only_five():

    names = [(f"Lugar {i}", "city") for i in range(12)]
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos", entities=names))]), SOURCE)

    document = index.articles_document()

    assert len(document["articles"]["e"][0]) == 12
    assert len(index.links(document["articles"]["id"][0])["entities"]) == 12


def labels_file(tmp_path, entries: dict) -> str:
    path = tmp_path / "wordpress-labels.json"
    path.write_text(json.dumps({"articles": entries}), encoding="utf-8")
    return str(path)


def test_a_story_with_no_topic_of_ours_goes_to_its_closest_topic_from_wordpress(tmp_path):

    url = "https://inspiringnews.ai/medio-ambiente/suelto/"
    path = labels_file(tmp_path, {url: {"section": "Sociedad", "categories": ["Sociedad"], "tags": ["Solidaridad"],
                                        "topics_wordpress": ["community"], "closest_topic": "community",
                                        "topic_from": "WordPress"}})
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("suelto", topic=None))]), SOURCE, labels_path=path)

    article = index.articles()[0]

    assert article.group == GROUP_OF["community"]
    assert article.topics == (("community", 0.0),)
    assert article.approximate == "wordpress_topic"


def test_our_classifier_still_decides_when_it_gave_a_topic(tmp_path):

    url = "https://inspiringnews.ai/medio-ambiente/lobos/"
    path = labels_file(tmp_path, {url: {"closest_topic": "arts", "topics_wordpress": ["arts"]}})
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos", topic="nature"))]), SOURCE, labels_path=path)

    assert index.articles()[0].group == GROUP_OF["nature"]


def test_a_storys_links_carry_its_wordpress_labels(tmp_path):

    url = "https://inspiringnews.ai/medio-ambiente/lobos/"
    path = labels_file(tmp_path, {url: {"section": "Medio ambiente", "categories": ["Medio ambiente"],
                                        "tags": ["Animales", "Lo más leído"], "topics_wordpress": ["nature", "no-such-topic"],
                                        "closest_topic": "nature", "topic_from": "classifier"}})
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"))]), SOURCE, labels_path=path)

    links = index.links(reader_id(url))

    assert links["wordpress"] == {
        "section": "Medio ambiente",
        "categories": ["Medio ambiente"],
        "tags": ["Animales", "Lo más leído"],
        "topics": [{"key": "nature", "name": TOPICS["nature"].name}],
        "topicFrom": "classifier",
    }


def test_the_document_lists_every_wordpress_label_and_each_storys(tmp_path):
    """So the universe can show a category's or a tag's stories when one is clicked (2026-11-23)."""

    path = labels_file(tmp_path, {
        "https://inspiringnews.ai/medio-ambiente/lobos/": {"categories": ["Medio ambiente"], "tags": ["Animales"]},
        "https://inspiringnews.ai/medio-ambiente/tigres/": {"categories": ["Medio ambiente"], "tags": ["Animales", "Lo más leído", ""]},
    })
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"), row("tigres"), row("ballenas"))]), SOURCE,
                          labels_path=path)

    document = index.articles_document()

    labels = [(label["k"], label["n"]) for label in document["labels"]]
    assert sorted(labels) == [("category", "Medio ambiente"), ("tag", "Animales"), ("tag", "Lo más leído")]
    by_id = dict(zip(document["articles"]["id"], document["articles"]["wp"]))
    named = lambda refs: sorted(labels[r] for r in refs)
    assert named(by_id[reader_id("https://inspiringnews.ai/medio-ambiente/lobos/")]) == [("category", "Medio ambiente"), ("tag", "Animales")]
    assert len(by_id[reader_id("https://inspiringnews.ai/medio-ambiente/tigres/")]) == 3
    assert by_id[reader_id("https://inspiringnews.ai/medio-ambiente/ballenas/")] == []


def test_without_labels_the_document_is_the_lake_maps():

    document = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"))]), SOURCE).articles_document()

    assert "labels" not in document
    assert "wp" not in document["articles"]


def test_a_graph_storys_links_go_to_the_web_and_never_to_a_reader_page():
    """The import is never published: the newsroom's /reader/{id} would answer 404."""

    url = "https://inspiringnews.ai/medio-ambiente/lobos/"
    links = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"))]), SOURCE).links(reader_id(url))

    assert links["url"] == url
    assert links["readerPage"] is False


def test_a_missing_labels_file_is_no_labels_not_an_error(tmp_path):

    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("suelto", topic=None))]), SOURCE,
                          labels_path=str(tmp_path / "nowhere.json"))

    article = index.articles()[0]

    assert article.approximate == "no_topic"
    assert "wordpress" not in index.links(article.id)


# ---------------------------------------------------------------------------
# Photos (2026-11-20)
# ---------------------------------------------------------------------------

PHOTO = "https://inspiringnews.ai/wp-content/uploads/2026/10/Fotos-para-la-web-18.png"


def images_folder(tmp_path, posts: dict, files=("7345-medium_large.png", "7345-thumbnail.png", "5814-full.png")):
    """A folder as scripts/wordpress_images.py leaves it: the files and the manifest."""

    folder = tmp_path / "images"
    folder.mkdir()
    for name in files:
        (folder / name).write_bytes(b"\x89PNG" + name.encode())
    (folder / "secret.txt").write_text("not a photo", encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({"posts": posts}), encoding="utf-8")
    return str(folder)


def lobos_photos():
    return {"https://inspiringnews.ai/medio-ambiente/lobos/": {"images": [
        {"url": PHOTO, "featured": True, "alt": "Ocho cachorros", "caption": None,
         "files": {"medium_large": "7345-medium_large.png", "thumbnail": "7345-thumbnail.png", "full": "7345-full.png"}},
        {"url": "https://inspiringnews.ai/wp-content/uploads/2025/12/2-3.png", "featured": False, "alt": None,
         "caption": "Participantes del Spogomi 2025.", "files": {"full": "5814-full.png"}},
    ]}}


def test_a_story_shows_the_photo_the_graph_links_to_when_none_was_downloaded():

    article = article_from_graph(row("lobos", image_url=PHOTO, image_alt="Ocho cachorros"), {})

    assert (article.image, article.thumb, article.image_alt) == (PHOTO, None, "Ocho cachorros")


def test_a_photo_the_graph_names_by_another_scheme_is_no_photo():

    assert article_from_graph(row("lobos", image_url="javascript:alert(1)"), {}).image is None


def test_downloaded_photos_are_served_from_the_map_at_768_px_with_a_thumbnail(tmp_path):

    folder = images_folder(tmp_path, lobos_photos())
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos", image_url=PHOTO))]), SOURCE, images_dir=folder)

    document = index.articles_document()

    assert document["articles"]["img"] == ["/images/7345-medium_large.png"]
    assert document["articles"]["thumb"] == ["/images/7345-thumbnail.png"]

    links = index.links(document["articles"]["id"][0])
    assert links["photos"] == [
        # Its original was listed but not downloaded: the site's, to open it.
        {"src": "/images/7345-medium_large.png", "small": None, "thumb": "/images/7345-thumbnail.png", "full": PHOTO,
         "alt": "Ocho cachorros", "caption": None, "featured": True},
        {"src": "/images/5814-full.png", "small": None, "thumb": None, "full": "/images/5814-full.png",
         "alt": None, "caption": "Participantes del Spogomi 2025.", "featured": False},
    ]


def test_only_a_file_the_manifest_lists_and_the_folder_holds_is_served(tmp_path):

    folder = images_folder(tmp_path, lobos_photos())
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"))]), SOURCE, images_dir=folder)

    assert index.image_path("7345-thumbnail.png") == tmp_path / "images" / "7345-thumbnail.png"
    # Listed but not downloaded: not served, and not shown either.
    assert index.image_path("7345-full.png") is None
    for name in ("secret.txt", "manifest.json", "../images/7345-thumbnail.png", "..", ""):
        assert index.image_path(name) is None


def test_no_folder_is_the_graph_s_photos_and_nothing_served():

    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos", image_url=PHOTO))]), SOURCE)

    assert index.articles_document()["articles"]["img"] == [PHOTO]
    assert index.image_path("7345-thumbnail.png") is None


def test_a_broken_manifest_is_no_downloaded_photos_not_an_error(tmp_path):

    folder = tmp_path / "images"
    folder.mkdir()
    (folder / "manifest.json").write_text("{not json", encoding="utf-8")
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos", image_url=PHOTO))]), SOURCE, images_dir=str(folder))

    assert index.articles_document()["articles"]["img"] == [PHOTO]


def test_a_new_manifest_changes_the_etag(tmp_path):

    clock = Clock()
    folder = images_folder(tmp_path, {})
    graph = RecordingGraphClient(reads=[result(row("lobos")), result(row("lobos"))])
    index = GraphMapIndex(graph, SOURCE, clock=clock, images_dir=folder)

    before, _ = index.payload("articles", index.articles_document)

    (tmp_path / "images" / "manifest.json").write_text(json.dumps({"posts": lobos_photos()}), encoding="utf-8")
    import os
    os.utime(tmp_path / "images" / "manifest.json", ns=(10**18, 10**18))
    clock.now += graph_source.REFRESH_SECONDS + 1

    after, _ = index.payload("articles", index.articles_document)

    assert before != after


def test_the_route_serves_a_listed_photo_and_nothing_else(tmp_path, monkeypatch):

    folder = images_folder(tmp_path, lobos_photos())
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"))]), SOURCE, images_dir=folder)
    monkeypatch.setattr(map_routes, "get_map_index", lambda: index)
    client = TestClient(app)

    served = client.get("/map/images/7345-thumbnail.png")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert "immutable" in served.headers["cache-control"]
    assert served.content == b"\x89PNG7345-thumbnail.png"

    assert client.get("/map/images/secret.txt").status_code == 404
    assert client.get("/map/images/manifest.json").status_code == 404
    assert client.get("/map/images/..%2Fmanifest.json").status_code == 404


WEBP_FILES = ("7345-medium_large.png", "7345-thumbnail.png", "7345-full.png", "7345-thumbnail.webp",
              "7345-small.webp", "7345-medium_large.webp", "7345-full.webp")


def webp_photos():
    """The manifest after scripts/optimize_map_photos.py: the PNGs, and a WebP copy of each size."""

    return {"https://inspiringnews.ai/medio-ambiente/lobos/": {"images": [
        {"url": PHOTO, "featured": True, "alt": "Ocho cachorros", "caption": None, "files": {
            "medium_large": "7345-medium_large.png", "thumbnail": "7345-thumbnail.png", "full": "7345-full.png",
            "thumbnail_webp": "7345-thumbnail.webp", "small_webp": "7345-small.webp",
            "medium_large_webp": "7345-medium_large.webp", "full_webp": "7345-full.webp"}},
    ]}}


def test_the_webp_copies_are_shown_before_the_pngs_and_the_map_carries_the_480_px_one(tmp_path):
    """2026-11-23: 35 KB for the panel's photo instead of 212, 17 KB for the hover card's."""

    folder = images_folder(tmp_path, webp_photos(), files=WEBP_FILES)
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos", image_url=PHOTO))]), SOURCE, images_dir=folder)

    document = index.articles_document()

    assert document["articles"]["img"] == ["/images/7345-small.webp"]
    assert document["articles"]["thumb"] == ["/images/7345-thumbnail.webp"]

    photo = index.links(document["articles"]["id"][0])["photos"][0]
    assert (photo["src"], photo["small"], photo["thumb"], photo["full"]) == (
        "/images/7345-medium_large.webp", "/images/7345-small.webp", "/images/7345-thumbnail.webp", "/images/7345-full.webp")


def test_a_webp_photo_is_served_as_webp(tmp_path, monkeypatch):
    """The backend image's Python guessed no type for .webp, and FileResponse sent text/plain."""

    folder = images_folder(tmp_path, webp_photos(), files=WEBP_FILES)
    index = GraphMapIndex(RecordingGraphClient(reads=[result(row("lobos"))]), SOURCE, images_dir=folder)
    monkeypatch.setattr(map_routes, "get_map_index", lambda: index)

    served = TestClient(app).get("/map/images/7345-small.webp")

    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"


def test_a_photo_never_waits_for_the_graph_to_be_read_again(tmp_path):
    """Every photo asked for while a refresh read the graph used to wait for it."""

    clock = Clock()
    folder = images_folder(tmp_path, lobos_photos())
    graph = RecordingGraphClient(reads=[result(row("lobos")), result(row("lobos"))])
    index = GraphMapIndex(graph, SOURCE, clock=clock, images_dir=folder)

    assert index.image_path("7345-thumbnail.png") is not None
    clock.now += graph_source.REFRESH_SECONDS + 1

    assert index.image_path("7345-thumbnail.png") is not None
    assert len(graph.reads_made) == 1


def test_the_related_stories_carry_their_thumbnails(tmp_path):

    folder = images_folder(tmp_path, lobos_photos())
    rows = [row("lobos", entities=[("Karnataka", "city")]), row("tigres", entities=[("Karnataka", "city")], image_url=PHOTO)]
    index = GraphMapIndex(RecordingGraphClient(reads=[result(*rows)]), SOURCE, images_dir=folder)

    tigres = reader_id("https://inspiringnews.ai/medio-ambiente/tigres/")
    lobos = reader_id("https://inspiringnews.ai/medio-ambiente/lobos/")

    assert [(r["id"], r["thumb"]) for r in index.links(tigres)["related"]] == [(lobos, "/images/7345-thumbnail.png")]
    assert [(r["id"], r["thumb"]) for r in index.links(lobos)["related"]] == [(tigres, PHOTO)]

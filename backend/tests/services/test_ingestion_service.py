import requests

from src.models.storage.lineage import DataLayer
from src.services.ingestion_service import IngestionService
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService
from src.services.scraper.request_stats import RequestStats
from src.services.scraper.strategies.base import DiscoveryStrategy

from tests.builders.source_builder import build_source


class FakeLake:

    def __init__(self, stored_urls=()):
        self.records = [{"lineage": {"source_url": url}} for url in stored_urls]

    def list(self, layer, limit=None):
        return self.records if layer == DataLayer.RAW else []


class FakeDiscovery:
    """Canned discovery results per source id."""

    def __init__(self, urls_by_source):
        self.urls_by_source = urls_by_source
        self.topics_seen = []

    def run(self, source, topics=None):
        self.topics_seen.append(topics)
        found = self.urls_by_source.get(source.id)
        if isinstance(found, Exception):
            return DiscoveryResult(error=str(found))
        return DiscoveryResult(urls=list(found or []), method="RSSDiscoveryStrategy")


class Jobs:
    """Stands in for the route's _start_job."""

    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return f"job-{len(self.urls)}", False


def service(urls_by_source, stored=(), sources=None):

    return IngestionService(
        sources=sources or [
            build_source(id="bbc", name="BBC"),
            build_source(id="nasa", name="NASA"),
        ],
        lake=FakeLake(stored),
        discovery=FakeDiscovery(urls_by_source),
    )


# ----------------------------------------------------------------------
# IngestionService
# ----------------------------------------------------------------------


def test_new_articles_are_queued_as_analysis_jobs():

    jobs = Jobs()

    report = service({"bbc": ["https://bbc.com/a", "https://bbc.com/b"]}).run(jobs)

    assert jobs.urls == ["https://bbc.com/a", "https://bbc.com/b"]

    [bbc, nasa] = report["sources"]
    assert bbc["queued"] == [
        {"url": "https://bbc.com/a", "jobId": "job-1", "reused": False},
        {"url": "https://bbc.com/b", "jobId": "job-2", "reused": False},
    ]
    assert report["totals"]["queued"] == 2


def test_articles_already_in_the_lake_are_not_analysed_again():
    """Compared by host and path, so a tracking parameter is not a new article."""

    jobs = Jobs()

    report = service(
        {"bbc": ["https://www.bbc.com/a?at_medium=RSS", "https://bbc.com/b"]},
        stored=["https://bbc.com/a/"],
    ).run(jobs)

    assert jobs.urls == ["https://bbc.com/b"]
    assert report["sources"][0]["alreadyStored"] == 1


def test_at_most_per_source_articles_are_queued_and_the_rest_deferred():

    jobs = Jobs()

    report = service({"bbc": [f"https://bbc.com/{n}" for n in range(5)]}).run(jobs, per_source=2)

    assert len(jobs.urls) == 2
    assert report["sources"][0]["deferred"] == 3


def test_an_article_two_sources_syndicate_is_queued_once():

    jobs = Jobs()

    service({
        "bbc": ["https://wire.example.com/story"],
        "nasa": ["https://wire.example.com/story"],
    }).run(jobs)

    assert jobs.urls == ["https://wire.example.com/story"]


def test_only_the_requested_and_enabled_sources_are_read():

    discovery_sources = [
        build_source(id="bbc"),
        build_source(id="nasa"),
        build_source(id="off", enabled=False),
    ]

    ingestion = service({}, sources=discovery_sources)

    assert [source.id for source in ingestion.enabled_sources()] == ["bbc", "nasa"]

    report = ingestion.run(Jobs(), source_ids=["nasa"])

    assert [row["source"] for row in report["sources"]] == ["nasa"]


def test_a_source_whose_discovery_fails_is_reported_not_raised():

    report = service({"bbc": RuntimeError("feed is malformed")}).run(Jobs())

    [bbc, _] = report["sources"]
    assert bbc["discovered"] == 0
    assert "malformed" in bbc["error"]
    assert report["totals"]["failed"] == 1


def test_discovery_asks_for_every_configured_topic():

    from src.config.topics import TOPICS

    ingestion = service({"bbc": []})
    ingestion.run(Jobs())

    assert ingestion.discovery.topics_seen[0] == list(TOPICS)


def test_the_last_run_is_kept_for_the_page():

    ingestion = service({"bbc": ["https://bbc.com/a"]})

    report = ingestion.run(Jobs())

    assert ingestion.last_run is report


# ----------------------------------------------------------------------
# DiscoveryService: cheapest first, and counted
# ----------------------------------------------------------------------


class Canned(DiscoveryStrategy):

    def __init__(self, urls=None, error=None):
        self.urls = urls or []
        self.error = error
        self.calls = 0

    def discover(self, source, topics=None):
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.urls)


def test_the_fallback_is_only_tried_when_the_feed_finds_nothing():

    fallback = Canned(["https://bbc.com/b"])

    discovery = DiscoveryService([Canned(["https://bbc.com/a"]), fallback], stats=RequestStats())

    result = discovery.run(build_source())

    assert result.urls == ["https://bbc.com/a"]
    assert result.method == "Canned"
    assert fallback.calls == 0


def test_a_broken_feed_falls_back_and_both_attempts_are_counted():

    stats = RequestStats()

    error = requests.HTTPError("403", response=type("R", (), {"status_code": 403})())

    discovery = DiscoveryService(
        [Canned(error=error), Canned(["https://bbc.com/a"])],
        stats=stats,
    )

    result = discovery.run(build_source(rss_url="https://bbc.com/rss.xml"))

    assert result.urls == ["https://bbc.com/a"]

    [entry] = stats.snapshot()["domains"]
    assert entry["purposes"] == {"discovery": 2}
    assert entry["outcomes"] == {"http_error": 1, "ok": 1}


def test_topic_pages_are_the_last_discovery_step():
    """Only after both feed steps: they cost one request, it costs up to seven."""

    from src.services.scraper.strategies.rss import RSSDiscoveryStrategy
    from src.services.scraper.strategies.topic_pages import TopicPageDiscoveryStrategy
    from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

    assert [type(s) for s in DiscoveryService(stats=RequestStats()).strategies] == [
        RSSDiscoveryStrategy,
        TrafilaturaFeedDiscoveryStrategy,
        TopicPageDiscoveryStrategy,
    ]


def test_when_nothing_is_found_the_reason_is_kept():

    discovery = DiscoveryService([Canned([]), Canned([])], stats=RequestStats())

    result = discovery.run(build_source())

    assert result.urls == []
    assert "no matching article links" in result.error


# ----------------------------------------------------------------------
# TrafilaturaFeedDiscoveryStrategy: URL-only topic filter
# ----------------------------------------------------------------------


def test_trafilatura_discovery_filters_by_article_shape_and_topic(monkeypatch):

    from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.trafilatura.feeds.find_feed_urls",
        lambda url: [
            "https://example.com/science/nasa-launches-telescope",
            "https://example.com/about",
            "https://example.com/videos/science/nasa-clip",
            "https://example.com/sport/football-final",
        ],
    )
    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.check_url",
        lambda url: url,
    )

    urls = TrafilaturaFeedDiscoveryStrategy().discover(
        build_source(rss_url="https://example.com/rss.xml"),
        topics=["space"],
    )

    assert urls == ["https://example.com/science/nasa-launches-telescope"]


def test_trafilatura_discovery_tries_the_homepage_when_the_feed_is_gone(monkeypatch):
    """Four configured feed URLs had gone 404; the homepages still advertise feeds."""

    from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

    asked = []

    def find_feed_urls(url):
        asked.append(url)
        if url.endswith("rss.xml"):
            return []
        return ["https://example.com/2026/09/23/nasa-launches-telescope"]

    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.trafilatura.feeds.find_feed_urls",
        find_feed_urls,
    )
    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.check_url",
        lambda url: url,
    )

    urls = TrafilaturaFeedDiscoveryStrategy().discover(
        build_source(base_url="https://example.com", rss_url="https://example.com/rss.xml", language="es"),
        topics=["space"],
    )

    assert asked == ["https://example.com/rss.xml", "https://example.com/"]
    assert urls == ["https://example.com/2026/09/23/nasa-launches-telescope"]


# ----------------------------------------------------------------------
# Topic groups and candidate lists
# ----------------------------------------------------------------------


def grouped_sources():

    return [
        build_source(id="e360", name="Yale E360", groups=["environment"]),
        build_source(id="nasa", name="NASA", groups=["science"]),
        build_source(id="pais", name="El País", language="es", groups=["society", "science", "environment"]),
    ]


def test_groups_narrow_the_sources_read_and_the_topics_asked_for():

    from src.config.topics import TOPIC_GROUPS

    ingestion = service({"e360": [], "pais": []}, sources=grouped_sources())

    report = ingestion.run(Jobs(), groups=["environment"])

    assert [row["source"] for row in report["sources"]] == ["e360", "pais"]
    assert ingestion.discovery.topics_seen == [TOPIC_GROUPS["environment"]] * 2
    assert report["groups"] == ["environment"]


def test_groups_and_source_ids_together_read_only_what_both_allow():

    ingestion = service({}, sources=grouped_sources())

    assert [s.id for s in ingestion.sources_for(["science"], ["pais", "e360"])] == ["pais"]


class DetailedDiscovery(FakeDiscovery):
    """Discovery that also reports what the feed said about each link."""

    def run(self, source, topics=None):
        self.topics_seen.append(topics)
        urls = list(self.urls_by_source.get(source.id) or [])
        details = {url: {"title": f"Title of {url.rsplit('/', 1)[-1]}", "summary": "A summary."} for url in urls[:1]}
        return DiscoveryResult(urls=urls, method="RSSDiscoveryStrategy", details=details)


def test_candidates_are_listed_with_what_the_feed_says_and_nothing_is_queued():

    ingestion = IngestionService(
        sources=grouped_sources(),
        lake=FakeLake(stored_urls=["https://e360.yale.edu/old"]),
        discovery=DetailedDiscovery({
            "e360": ["https://e360.yale.edu/digest/a", "https://e360.yale.edu/old"],
            "pais": [
                "https://elpais.com/clima/2026-10-05/el-delta-del-ebro-recupera-aves.html",
                "https://elpais.com/clima/2026-10-05/b.html",
                "https://elpais.com/clima/2026-10-05/c.html",
            ],
        }),
    )

    round_ = ingestion.discover_candidates(["environment"], per_source=2)

    assert [c["url"] for c in round_["candidates"]] == [
        "https://e360.yale.edu/digest/a",
        "https://elpais.com/clima/2026-10-05/el-delta-del-ebro-recupera-aves.html",
        "https://elpais.com/clima/2026-10-05/b.html",
    ]

    [e360, pais, _] = round_["candidates"]
    assert (e360["title"], e360["titleFrom"], e360["summary"]) == ("Title of a", "feed", "A summary.")
    assert e360["groups"] == ["environment"] and pais["groups"] == ["environment"]
    assert pais["language"] == "es"

    [e360_row, pais_row] = round_["sources"]
    assert (e360_row["alreadyStored"], e360_row["candidates"]) == (1, 1)
    assert (pais_row["candidates"], pais_row["deferred"]) == (2, 1)
    assert round_["totals"]["candidates"] == 3


def test_a_link_with_no_feed_title_gets_one_from_its_slug():

    from src.services.ingestion_service import title_from_url

    assert title_from_url("https://www.lavanguardia.com/natural/20261005/11651300/rewilding-the-ebro-delta.html") == "Rewilding the ebro delta"
    assert title_from_url("https://e360.yale.edu/digest/x") is None


def test_a_slug_before_a_numeric_id_still_gives_a_title():
    """RTVE puts the id last; its links came back untitled, and so unscreened."""

    from src.services.ingestion_service import title_from_url

    assert title_from_url(
        "https://www.rtve.es/television/20260831/asi-se-hace-autentico-bacalao-valderas/17174859.shtml"
    ) == "Asi se hace autentico bacalao valderas"
    assert title_from_url("https://example.com/news/12345") is None


# ----------------------------------------------------------------------
# Only recent items (MAX_CANDIDATE_AGE)
# ----------------------------------------------------------------------


class Dated(DiscoveryStrategy):
    """A feed whose items carry their publication times."""

    def __init__(self, items):
        self.items = items

    def discover(self, source, topics=None):
        return [item.url for item in self.items]

    def discover_items(self, source, topics=None):
        return list(self.items)


def days_ago(days):

    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) - timedelta(days=days)


def test_items_older_than_the_limit_are_dropped_and_undated_ones_kept():

    from datetime import timedelta

    from src.services.scraper.strategies.rss import DiscoveredLink

    discovery = DiscoveryService(
        [Dated([
            DiscoveredLink(url="https://bbc.com/new", published=days_ago(2)),
            DiscoveredLink(url="https://bbc.com/old", published=days_ago(400)),
            DiscoveredLink(url="https://bbc.com/undated"),
        ])],
        stats=RequestStats(),
        max_age=timedelta(days=30),
    )

    result = discovery.run(build_source())

    assert result.urls == ["https://bbc.com/new", "https://bbc.com/undated"]
    assert result.stale == 1


def test_a_feed_with_only_old_items_counts_as_empty_and_the_next_step_is_tried():
    """RTVE's feed has carried only June 2022 items since then."""

    from datetime import timedelta

    from src.services.scraper.strategies.rss import DiscoveredLink

    stats = RequestStats()
    section_pages = Canned(["https://rtve.es/cultura/20261006/a-new-one/1.shtml"])

    discovery = DiscoveryService(
        [Dated([DiscoveredLink(url="https://rtve.es/television/20220609/old/2.shtml", published=days_ago(1580))]), section_pages],
        stats=stats,
        max_age=timedelta(days=30),
    )

    result = discovery.run(build_source(rss_url="https://rtve.es/rss.xml"))

    assert result.urls == ["https://rtve.es/cultura/20261006/a-new-one/1.shtml"]
    assert result.method == "Canned"
    assert section_pages.calls == 1

    [entry] = stats.snapshot()["domains"]
    assert entry["outcomes"] == {"no_content": 1, "ok": 1}


def test_when_every_item_is_old_the_reason_says_so():

    from datetime import timedelta

    from src.services.scraper.strategies.rss import DiscoveredLink

    discovery = DiscoveryService(
        [Dated([DiscoveredLink(url="https://bbc.com/old", published=days_ago(400))])],
        stats=RequestStats(),
        max_age=timedelta(days=30),
    )

    result = discovery.run(build_source())

    assert result.urls == []
    assert "only items older than 30 days" in result.error


def test_ingestion_discovers_only_recent_items_by_default():

    from src.services.ingestion_service import MAX_CANDIDATE_AGE

    ingestion = IngestionService(sources=[build_source()], lake=FakeLake())

    assert ingestion.discovery.max_age == MAX_CANDIDATE_AGE


# ----------------------------------------------------------------------
# The mission screen, before the per-source cap
# ----------------------------------------------------------------------


class FakeScreen:
    """
    Leaves out every candidate whose title contains one of `off`, unless
    exempt; reads each as `impact[title]` near positive impact (0.45, as
    near as to politics, by default). Records what it read and what it
    judged.
    """

    def __init__(self, off=(), error=None, impact=None, vectors=None):
        self.off = off
        self.error = error
        self.impact = impact or {}
        self.vectors = vectors or {}
        self.read = []
        self.judged = []

    def assess(self, candidates, exempt=None):

        from src.services.selection.mission_screen import Assessment, Reading, Verdict

        if self.error:
            raise self.error

        exempt = exempt or [False] * len(candidates)
        self.read.extend(candidates)
        self.judged.extend(candidate for candidate, spared in zip(candidates, exempt) if not spared)

        return [
            Assessment(
                verdict=Verdict(off_mission="politics", margin=0.09, nearest_topic="cities")
                if not spared and any(word in (candidate.title or "") for word in self.off) else None,
                reading=Reading(
                    nearest_topic="cities", topic=0.5, nearest_off="politics", off=0.45,
                    impact=self.impact.get(candidate.title, 0.45),
                    vector=self.vectors.get(candidate.title),
                ),
            )
            for candidate, spared in zip(candidates, exempt)
        ]


class TitledDiscovery(FakeDiscovery):
    """Every link titled by its last path segment."""

    def run(self, source, topics=None):
        urls = list(self.urls_by_source.get(source.id) or [])
        details = {url: {"title": url.rsplit("/", 1)[-1], "summary": None} for url in urls}
        return DiscoveryResult(urls=urls, method="RSSDiscoveryStrategy", details=details, stale=1)


def screened_service(urls_by_source, screen, sources=None):

    return IngestionService(
        sources=sources or [build_source(id="pais", name="El País", language="es", groups=["culture"])],
        lake=FakeLake(),
        discovery=TitledDiscovery(urls_by_source),
        screen=screen,
    )


def test_what_the_screen_leaves_out_does_not_take_a_sources_slots():
    """2026-10-06: election polls and a tanker crash in a Culture round."""

    ingestion = screened_service(
        {"pais": [
            "https://elpais.com/espana/elecciones-encuesta",
            "https://elpais.com/cultura/museo-abre",
            "https://elpais.com/espana/elecciones-sondeo",
            "https://elpais.com/cultura/festival-gratis",
            "https://elpais.com/cultura/biblioteca-nueva",
        ]},
        FakeScreen(off=("elecciones",)),
    )

    round_ = ingestion.discover_candidates(["culture"], per_source=2)

    assert [c["url"] for c in round_["candidates"]] == [
        "https://elpais.com/cultura/museo-abre",
        "https://elpais.com/cultura/festival-gratis",
    ]
    assert [s["url"] for s in round_["screened"]] == [
        "https://elpais.com/espana/elecciones-encuesta",
        "https://elpais.com/espana/elecciones-sondeo",
    ]
    assert round_["screened"][0] == {
        "url": "https://elpais.com/espana/elecciones-encuesta",
        "source": "pais",
        "sourceName": "El País",
        "title": "elecciones-encuesta",
        "offMission": "politics",
        "margin": 0.09,
        "nearestTopic": "cities",
    }
    assert round_["screen"]["status"] == "ok"

    [row] = round_["sources"]
    assert (row["candidates"], row["screened"], row["deferred"], row["stale"]) == (2, 2, 1, 1)
    assert (round_["totals"]["screened"], round_["totals"]["stale"]) == (2, 1)


def test_the_screen_reads_only_a_few_per_slot_not_the_whole_feed():

    from src.services.ingestion_service import SCREEN_DEPTH

    urls = [f"https://elpais.com/cultura/articulo-{i}" for i in range(40)]
    screen = FakeScreen()

    round_ = screened_service({"pais": urls}, screen).discover_candidates(["culture"], per_source=2)

    assert len(screen.read) == 2 * SCREEN_DEPTH
    assert len(round_["candidates"]) == 2
    assert round_["sources"][0]["deferred"] == 38


def test_a_positive_outlet_is_read_but_not_screened():
    """Good News Network's ex-prisoners-as-firefighters story read as "crime"."""

    gnn = build_source(id="gnn", name="Good News Network", groups=["culture"], positive_editorial=True)
    screen = FakeScreen(off=("prison",))

    round_ = screened_service(
        {"gnn": ["https://goodnewsnetwork.org/ex-prisoners-fight-wildfires"]}, screen, sources=[gnn],
    ).discover_candidates(["culture"], per_source=2)

    assert [c["url"] for c in round_["candidates"]] == ["https://goodnewsnetwork.org/ex-prisoners-fight-wildfires"]
    assert screen.judged == []
    # Read all the same, and only what it can offer: per_source, not SCREEN_DEPTH times that.
    assert [c.title for c in screen.read] == ["ex-prisoners-fight-wildfires"]
    assert round_["candidates"][0]["reading"]["impact"] == 0.45
    assert round_["sources"][0]["judged"] == 0


def test_when_the_screen_cannot_run_every_candidate_stays_and_the_round_says_so():

    from src.services.inference_client import InferenceUnavailable

    ingestion = screened_service(
        {"pais": ["https://elpais.com/espana/elecciones-encuesta", "https://elpais.com/cultura/museo-abre"]},
        FakeScreen(error=InferenceUnavailable("connection refused")),
    )

    round_ = ingestion.discover_candidates(["culture"], per_source=2)

    assert len(round_["candidates"]) == 2
    assert round_["screened"] == []
    assert round_["screen"]["status"] == "unavailable"
    assert "connection refused" in round_["screen"]["error"]
    # Ranked by the sources alone: nothing was read.
    assert all(c["rank"]["news"] is None and c["reading"] is None for c in round_["candidates"])


def test_without_a_screen_nothing_is_left_out_and_the_round_says_it_was_off():

    round_ = screened_service(
        {"pais": ["https://elpais.com/espana/elecciones-encuesta"]}, screen=None,
    ).discover_candidates(["culture"], per_source=2)

    assert len(round_["candidates"]) == 1
    assert round_["screen"]["status"] == "off"


def test_the_screen_is_told_each_candidates_language():
    """The death-report phrases are per language: "muere" is Spanish."""

    screen = FakeScreen()

    screened_service({"pais": ["https://elpais.com/cultura/muere-un-poeta"]}, screen).discover_candidates(["culture"])

    assert [(c.title, c.language) for c in screen.read] == [("muere-un-poeta", "es")]


def test_an_old_link_with_its_date_in_the_path_is_not_offered():
    """ABC's section pages listed a mortgage calculator stamped 2026-05-25 as news."""

    from datetime import timedelta

    from src.services.scraper.strategies.rss import DiscoveredLink

    discovery = DiscoveryService(
        [Dated([
            DiscoveredLink(url="https://www.abc.es/economia/cuentas-corrientes/calcula-hipoteca-20250525124640-nt.html"),
            DiscoveredLink(url="https://www.rtve.es/television/20240623/receta-de-macarrons-para-sant-joan/17128523.shtml"),
            DiscoveredLink(url="https://news.example/science/no-date-in-this-link-at-all"),
        ])],
        stats=RequestStats(),
        max_age=timedelta(days=30),
    )

    result = discovery.run(build_source())

    assert result.urls == ["https://news.example/science/no-date-in-this-link-at-all"]
    assert result.stale == 2
    assert result.published == {}


def test_post_ingest_screens_before_it_queues():

    jobs = Jobs()

    report = screened_service(
        {"pais": ["https://elpais.com/espana/elecciones-encuesta", "https://elpais.com/cultura/museo-abre"]},
        FakeScreen(off=("elecciones",)),
    ).run(jobs, per_source=1)

    assert jobs.urls == ["https://elpais.com/cultura/museo-abre"]
    assert report["totals"]["screened"] == 1
    assert report["sources"][0]["screened"] == 1


# ----------------------------------------------------------------------
# Best first (src/services/selection/ranking.py)
# ----------------------------------------------------------------------


def test_candidates_come_best_first_with_the_parts_of_their_score():

    from src.services.selection import ranking

    sources = [
        build_source(id="nasa", name="NASA", groups=["culture"], reliability_index=1.0),
        build_source(id="pais", name="El País", language="es", groups=["culture"], reliability_index=0.9),
    ]
    screen = FakeScreen(impact={"museo-abre": 0.48, "telescope-finds-water": 0.46})

    round_ = screened_service(
        {
            "nasa": ["https://nasa.gov/news/telescope-finds-water"],
            "pais": ["https://elpais.com/cultura/concierto-cancelado", "https://elpais.com/cultura/museo-abre"],
        },
        screen,
        sources=sources,
    ).discover_candidates(["culture"], per_source=2)

    listed = [c["url"].rsplit("/", 1)[-1] for c in round_["candidates"]]
    scores = [c["rank"]["score"] for c in round_["candidates"]]

    assert scores == sorted(scores, reverse=True)
    # Same source, same record and rating: the story itself decides.
    assert listed.index("museo-abre") < listed.index("concierto-cancelado")

    museum = next(c for c in round_["candidates"] if c["url"].endswith("museo-abre"))
    assert set(museum["rank"]) == {"score", "news", "record", "reliability"}
    assert museum["rank"]["reliability"] == 0.9
    assert museum["reading"]["impact"] == 0.48
    assert round_["ranking"]["weights"] == ranking.WEIGHTS


def test_a_source_whose_newest_items_are_mostly_off_mission_ranks_lower():
    """2026-10-06: eldiario and 20minutos kept about half of what the screen read; science outlets all of it."""

    sources = [
        build_source(id="abc", name="ABC", language="es", groups=["society"], reliability_index=0.9),
        build_source(id="sinc", name="SINC", language="es", groups=["society"], reliability_index=0.9),
    ]
    noisy = [f"https://abc.es/espana/elecciones-{i}" for i in range(4)] + ["https://abc.es/sociedad/un-huerto-escolar"]

    round_ = screened_service(
        {"abc": noisy, "sinc": ["https://agenciasinc.es/una-biblioteca-escolar"]},
        FakeScreen(off=("elecciones",)),
        sources=sources,
    ).discover_candidates(["society"], per_source=1)

    assert [c["source"] for c in round_["candidates"]] == ["sinc", "abc"]

    sinc, abc = (c["rank"] for c in round_["candidates"])
    assert sinc["news"] == abc["news"]
    assert abc["record"] < sinc["record"]
    assert [(row["judged"], row["screened"]) for row in round_["sources"]] == [(5, 4), (1, 0)]


def test_one_story_from_two_outlets_is_offered_once_before_any_story_twice():
    """2026-10-06: the physics Nobel, from nine outlets, took 8 of a round's first twenty places."""

    import numpy as np

    sources = [
        build_source(id="guardian", name="The Guardian", groups=["science"], reliability_index=0.9),
        build_source(id="sinc", name="SINC", language="es", groups=["science"], reliability_index=0.9),
    ]
    screen = FakeScreen(
        impact={"nobel-physics": 0.50, "nobel-fisica": 0.49, "telescope-finds-water": 0.46},
        vectors={
            "nobel-physics": np.array([1.0, 0.0]),
            "nobel-fisica": np.array([0.8, 0.6]),
            "telescope-finds-water": np.array([0.0, 1.0]),
        },
    )

    round_ = screened_service(
        {
            "guardian": ["https://theguardian.com/science/nobel-physics", "https://theguardian.com/science/telescope-finds-water"],
            "sinc": ["https://agenciasinc.es/nobel-fisica"],
        },
        screen,
        sources=sources,
    ).discover_candidates(["science"], per_source=2)

    assert [c["url"].rsplit("/", 1)[-1] for c in round_["candidates"]] == ["nobel-physics", "telescope-finds-water", "nobel-fisica"]
    assert round_["candidates"][-1]["sameStoryAs"] == "https://theguardian.com/science/nobel-physics"
    assert round_["totals"]["sameStory"] == 1
    # The vectors stay in memory: the round records the reading without them.
    assert "vector" not in round_["candidates"][0]["reading"]


def test_without_a_screen_the_sources_alone_decide_the_order():

    sources = [
        build_source(id="cnn", name="CNN", groups=["health"], reliability_index=0.72),
        build_source(id="who", name="WHO", groups=["health"], reliability_index=0.97),
    ]

    round_ = screened_service(
        {"cnn": ["https://cnn.com/health/a-new-vaccine"], "who": ["https://who.int/news/malaria-falls"]},
        screen=None,
        sources=sources,
    ).discover_candidates(["health"])

    assert [c["source"] for c in round_["candidates"]] == ["who", "cnn"]
    assert all(c["rank"]["news"] is None for c in round_["candidates"])

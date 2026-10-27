"""
A trending round (src/services/trends/trending.py, docs/decisions/trends.md
"The lens"), over the feeds saved on 2026-10-26.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.core.trend_signal import TrendSignal
from src.models.storage.lineage import DataLayer
from src.services.ingestion_service import IngestionService
from src.services.scraper.fetcher import FetchedPage
from src.services.scraper.request_stats import RequestStats
from src.services.scraper.sightings import Sightings
from src.services.selection import ranking
from src.services.selection.mission_screen import Assessment, Reading, Verdict
from src.services.trends.seeds import SeedError
from src.services.trends.trend_service import TrendService
from src.services.trends.trending import MAX_TREND_AGE, TrendingDiscovery, virality
from src.services.trends.trends import Trend

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "trends"

# The afternoon the feeds were saved: every Spanish trend started that
# morning, and its oldest article is three days old.
NOW = datetime(2026, 10, 26, 16, 0, tzinfo=timezone.utc)

SPAIN = TrendSignal(
    id="google_trends_es", name="Google Trends · Spain", kind="google_trends",
    url="https://trends.google.com/trending/rss?geo=ES", language="es", country="ES",
)

REDDIT = TrendSignal(
    id="uplifting_news", name="r/UpliftingNews", kind="ranked_feed",
    url="https://www.reddit.com/r/UpliftingNews/top/.rss?t=day", language="en", positive=True,
)

PAGES = {
    "https://trends.google.com/": (FIXTURES / "google_trends_es_2026-10-26.xml").read_text(encoding="utf-8"),
    "https://www.reddit.com/": (FIXTURES / "reddit_upliftingnews_2026-10-26.xml").read_text(encoding="utf-8"),
}


class FakeFetcher:

    def __init__(self, pages):
        self.pages = pages

    def get(self, url):
        for prefix, answer in self.pages.items():
            if url.startswith(prefix):
                if isinstance(answer, Exception):
                    raise answer
                return FetchedPage(url=url, status=200, html=answer)
        raise ConnectionError(url)


class FakeSearch:

    def __init__(self, results=None):
        self.results = results or []
        self.queries = []

    def search(self, query, max_results=None, language=None):
        self.queries.append((query, language))
        return self.results


class FakeLake:

    def __init__(self, stored=()):
        self.records = [{"lineage": {"source_url": url}} for url in stored]

    def list(self, layer, limit=None):
        return self.records if layer == DataLayer.RAW else []


class FakeScreen:
    """
    Leaves out a candidate whose title holds one of `off` (as a disaster);
    reads each as `impact` by the first word of `impact` its title holds
    (0.45 otherwise), as near to the topics in `topics` by the same rule.
    """

    def __init__(self, off=(), impact=None, topics=None, error=None):
        self.off = off
        self.impact = impact or {}
        self.topics = topics or {}
        self.error = error
        self.read = []
        self.exempt = []

    def _by(self, table, title, default):
        return next((value for word, value in table.items() if word.lower() in (title or "").lower()), default)

    def assess(self, candidates, exempt=None):

        if self.error:
            raise self.error

        self.read.extend(candidates)
        self.exempt.extend(exempt or [])

        return [
            Assessment(
                verdict=Verdict(off_mission="disaster", margin=0.05, nearest_topic="cities")
                if any(word.lower() in (candidate.title or "").lower() for word in self.off) else None,
                reading=Reading(
                    nearest_topic="cities", topic=0.5, nearest_off="disaster", off=0.45,
                    impact=self._by(self.impact, candidate.title, 0.45),
                    topics=self._by(self.topics, candidate.title, None),
                ),
            )
            for candidate in candidates
        ]


def trending(screen=None, stored=(), search=None, pages=None, signals=None):

    ingestion = IngestionService(
        sources=[], lake=FakeLake(stored), screen=screen, sightings=Sightings(),
    )
    service = TrendService(
        signals=signals or [SPAIN, REDDIT],
        fetcher=FakeFetcher(PAGES if pages is None else pages),
        search=search or FakeSearch(),
        stats=RequestStats(),
    )

    return TrendingDiscovery(ingestion, service)


def titles(round_: dict) -> list[str]:
    return [candidate["title"] for candidate in round_["candidates"]]


# ----------------------------------------------------------------------
# What a trend's articles must pass
# ----------------------------------------------------------------------


def test_spains_thirty_articles_through_the_link_filters():
    """Sport and crime sections and the two betting sites go; two articles a trend are offered."""

    round_ = trending().discover(signal_ids=["google_trends_es"], now=NOW)

    totals = round_["totals"]
    assert (totals["trends"], totals["discovered"], totals["notArticles"]) == (10, 30, 9)
    assert (totals["candidates"], totals["deferred"], totals["stale"]) == (15, 6, 0)

    urls = [candidate["url"] for candidate in round_["candidates"]]
    assert not any("fanduel" in url or "dimers.com" in url for url in urls)
    assert not any("/sucesos/" in url or "/baloncesto/" in url or "/tenis/" in url for url in urls)

    # Pierre Oriola's three were all sport: the trend offers nothing.
    oriola = next(trend for trend in round_["trends"] if trend["name"] == "pierre oriola")
    assert (oriola["articles"], oriola["candidates"]) == (3, 0)

    assert round_["lens"] == "trending"
    assert round_["screen"]["status"] == "off"


def test_each_candidate_carries_its_trend_card_and_its_outlet():

    round_ = trending().discover(signal_ids=["google_trends_es"], now=NOW)

    metro = next(c for c in round_["candidates"] if "linea-10" in c["url"])

    assert metro["trend"]["name"] == "línea 10"
    assert metro["trend"]["traffic"] == 200
    assert metro["trend"]["signal"] == "google_trends_es"
    assert metro["sourceName"] == "EL PAÍS"
    assert metro["source"] == "elpais.com"
    assert (metro["language"], metro["titleFrom"], metro["groups"]) == ("es", "signal", [])
    assert metro["method"] == "trend:google_trends"


def test_the_metro_reopening_ranks_above_the_lorry_crash():
    """The goal's case: the story's reading decides, the trends' searches being equal (200+ each)."""

    # "Metro de Madrid", not "Metro": the lorry's "kilómetros" holds it.
    screen = FakeScreen(impact={"Metro de Madrid": 0.6, "camión": 0.35})

    round_ = trending(screen=screen).discover(signal_ids=["google_trends_es"], now=NOW)

    order = [candidate["url"] for candidate in round_["candidates"]]
    metro = next(i for i, url in enumerate(order) if "linea-10-de-metro" in url)
    lorry = next(i for i, url in enumerate(order) if "camion-vuelca-ap-7" in url)

    assert metro < lorry
    assert round_["candidates"][metro]["rank"]["virality"] == round_["candidates"][lorry]["rank"]["virality"]


def test_the_screen_runs_on_every_article_and_exempts_none():
    """r/UpliftingNews is a positive signal, and still carried an election result on 26 Oct."""

    screen = FakeScreen(off=("Vucic",))

    round_ = trending(screen=screen).discover(signal_ids=["uplifting_news"], now=NOW)

    assert screen.exempt and not any(screen.exempt)
    assert [item["trend"] for item in round_["screened"]][0].startswith("Serbia's strongman")
    assert not any("pbs.org" in candidate["url"] for candidate in round_["candidates"])
    assert round_["sources"][0]["screened"] == 1


def test_a_trend_from_2016_is_stale():

    round_ = trending().discover(signal_ids=["uplifting_news"], now=NOW)

    dolly = next(trend for trend in round_["trends"] if trend["name"].startswith("Dolly Parton"))

    assert dolly["stale"] is True and dolly["candidates"] == 0
    assert round_["totals"]["stale"] >= 1


def test_an_article_older_than_a_week_is_stale_even_in_a_new_trend():

    # A week and a day after the feeds were saved, ABC's La Regenta piece
    # (dated 23 Oct in its path) is too old, and the trend itself too.
    later = datetime(2026, 10, 31, 13, 0, tzinfo=timezone.utc)

    round_ = trending().discover(signal_ids=["google_trends_es"], now=later)

    assert round_["candidates"] == []
    assert all(trend["stale"] for trend in round_["trends"])
    assert later - NOW > MAX_TREND_AGE


def test_an_article_already_analysed_is_not_offered_again():

    from src.services.trends.readers import read_google_trends

    trends = read_google_trends(PAGES["https://trends.google.com/"], SPAIN)
    metro = next(trend for trend in trends if trend.name == "línea 10").articles[0].url

    # Stored with a tracking parameter and without www: the same article.
    round_ = trending(stored=[metro + "?utm_source=rss"]).discover(signal_ids=["google_trends_es"], now=NOW)

    assert metro not in [c["url"] for c in round_["candidates"]]
    assert round_["totals"]["alreadyStored"] == 1


def test_an_article_two_trends_bring_is_offered_once_by_the_first():

    pages = {"https://trends.google.com/": """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>first</title><ht:approx_traffic>500+</ht:approx_traffic><pubDate>Mon, 26 Oct 2026 07:10:00 -0700</pubDate>
<ht:news_item><ht:news_item_title>Bosque recuperado</ht:news_item_title><ht:news_item_url>https://example.es/medio-ambiente/2026/10/26/bosque-recuperado-tras-el-incendio</ht:news_item_url><ht:news_item_source>Example</ht:news_item_source></ht:news_item>
</item>
<item><title>second</title><ht:approx_traffic>200+</ht:approx_traffic><pubDate>Mon, 26 Oct 2026 07:10:00 -0700</pubDate>
<ht:news_item><ht:news_item_title>Bosque recuperado</ht:news_item_title><ht:news_item_url>https://example.es/medio-ambiente/2026/10/26/bosque-recuperado-tras-el-incendio?utm=x</ht:news_item_url><ht:news_item_source>Example</ht:news_item_source></ht:news_item>
</item></channel></rss>"""}

    round_ = trending(pages=pages, signals=[SPAIN]).discover(now=NOW)

    [only] = round_["candidates"]
    assert only["trend"]["name"] == "first"
    assert round_["totals"]["alreadyStored"] == 1


# ----------------------------------------------------------------------
# A person's seed
# ----------------------------------------------------------------------


def test_a_seed_alone_is_searched_for_and_its_finds_offered():

    search = FakeSearch(results=[
        {"url": "https://www.20minutos.es/noticia/2026/10/25/farmear-aura-plazas-jovenes-reunen/", "title": "Farmear aura: los jóvenes vuelven a las plazas"},
    ])

    round_ = trending(search=search).discover(signal_ids=[], seed="#FarmearAura", now=NOW)

    assert search.queries == [("!news Farmear Aura", None)]
    [candidate] = round_["candidates"]
    assert candidate["trend"]["seed"] is True
    assert candidate["titleFrom"] == "search"
    assert candidate["rank"]["virality"] is None
    assert [row["source"] for row in round_["sources"]] == ["seed"]
    assert round_["seed"] == "#FarmearAura"


def test_a_seed_with_nothing_to_search_for_is_refused_before_any_feed_is_read():

    discovery = trending(pages={})

    with pytest.raises(SeedError):
        discovery.discover(seed="   #fyp ", now=NOW)


def test_signals_are_not_searched_unless_asked():

    search = FakeSearch()

    trending(search=search).discover(signal_ids=["google_trends_es"], now=NOW)
    assert search.queries == []

    trending(search=search).discover(signal_ids=["google_trends_es"], search=True, now=NOW)
    assert len(search.queries) == 10


# ----------------------------------------------------------------------
# The ranking
# ----------------------------------------------------------------------


def test_without_groups_the_order_is_positive_impact_and_says_so():

    round_ = trending(screen=FakeScreen()).discover(signal_ids=["google_trends_es"], now=NOW)

    assert round_["ranking"]["lens"] == "trending"
    assert round_["ranking"]["topicEmphasis"]["applied"] is None
    assert round_["ranking"]["weights"] == {"news": 0.6, "topic": 0.0, "record": 0.25, "virality": 0.15}
    assert all(candidate["rank"]["topic"] is None for candidate in round_["candidates"])


def test_with_groups_what_fits_them_comes_first():

    from src.config.topics import TOPICS

    near_culture = {topic: (0.6 if topic == "literature" else 0.3) for topic in TOPICS}
    near_cities = {topic: (0.6 if topic == "cities" else 0.3) for topic in TOPICS}

    screen = FakeScreen(topics={"Regenta": near_culture, "Metro": near_cities})

    round_ = trending(screen=screen).discover(groups=["culture"], signal_ids=["google_trends_es"], now=NOW)

    assert round_["ranking"]["topicEmphasis"]["applied"] == ranking.DEFAULT_TOPIC_EMPHASIS
    assert "Regenta" in round_["candidates"][0]["title"]
    metro = next(c for c in round_["candidates"] if "Metro" in (c["title"] or ""))
    assert metro["otherGroup"] == "society"


def test_a_signal_whose_items_the_screen_mostly_leaves_out_ranks_lower():
    """The record is the signal's in this round's screen, as the source's is in a topic round."""

    # Words of nearly every Spanish title and of no English one.
    screen = FakeScreen(off=(" de ", " la ", " el ", " en "))

    round_ = trending(screen=screen).discover(now=NOW)

    spain, reddit = round_["sources"]
    assert spain["screened"] > reddit["screened"]

    record = {c["trend"]["signal"]: c["rank"]["record"] for c in round_["candidates"]}
    assert record["uplifting_news"] > record["google_trends_es"]


def test_the_trend_weights_sum_to_one_at_every_emphasis():

    for step in range(21):
        assert sum(ranking.trend_weights(step / 20).values()) == pytest.approx(1.0)


def test_virality_is_a_trends_place_among_its_own_signals():

    def trend(name, signal="google_trends_es", traffic=None, position=1, seed=False):
        return Trend(id=name, name=name, signal=signal, signal_name=signal, language="es",
                     position=position, traffic=traffic, seed=seed)

    values = virality([
        trend("a", traffic=2000), trend("b", traffic=500), trend("c", traffic=500), trend("d", traffic=100),
        trend("x", signal="uplifting_news", position=1), trend("y", signal="uplifting_news", position=2),
        trend("only", signal="upworthy"),
        trend("typed", signal="seed", seed=True),
    ])

    assert values["a"] == 1.0 and values["d"] == 0.0
    # 500+ twice: both share places two and three.
    assert values["b"] == values["c"] == pytest.approx(0.5)
    assert (values["x"], values["y"]) == (1.0, 0.0)
    assert values["only"] == 1.0
    assert "typed" not in values


# ----------------------------------------------------------------------
# Failing soft
# ----------------------------------------------------------------------


def test_when_the_screen_cannot_run_nothing_is_left_out_and_the_round_says_so():

    round_ = trending(screen=FakeScreen(error=ConnectionError("inference down"))).discover(
        signal_ids=["google_trends_es"], now=NOW,
    )

    assert round_["screen"]["status"] == "unavailable"
    assert round_["totals"]["candidates"] == 15 and round_["screened"] == []


def test_a_signal_that_cannot_be_read_is_a_row_with_its_error():

    round_ = trending(pages={"https://trends.google.com/": PAGES["https://trends.google.com/"]}).discover(now=NOW)

    spain, reddit = round_["sources"]
    assert spain["error"] is None and reddit["error"]
    assert round_["totals"]["failed"] == 1
    assert round_["totals"]["candidates"] == 15


def test_an_emphasis_outside_zero_to_one_is_refused_before_any_feed_is_read():

    with pytest.raises(ValueError):
        trending(pages={}).discover(topic_emphasis=1.5, now=NOW)


def test_the_articles_offered_are_recorded_as_seen():

    discovery = trending()
    discovery.discover(signal_ids=["google_trends_es"], now=NOW)

    seen = discovery.ingestion.sightings.all()

    assert len(seen) == 21
    assert {entry["sourceId"] for entry in seen.values()} == {"google_trends_es"}


# ----------------------------------------------------------------------
# Against the real screen (inference/ running)
# ----------------------------------------------------------------------


def test_the_real_screen_puts_the_metro_trend_above_the_lorry_crash(require_inference):
    """
    The goal's case with bge-m3's own reading. Run first on 2026-10-26: the
    AP-7 crash was left out as a disaster (margin 0.10), and the Línea 10
    trend was offered third, by El Mundo's piece on the metro works. El
    País's reopening piece itself was left out as a service page (0.024,
    service's margin 0.02): the screen reads a transit announcement as a
    traffic update (docs/decisions/trends.md, "The lens, run").
    """

    from src.services.selection.mission_screen import MissionScreen

    round_ = trending(screen=MissionScreen()).discover(signal_ids=["google_trends_es"], now=NOW)

    places = [candidate["trend"]["name"] for candidate in round_["candidates"]]

    assert "línea 10" in places, "the metro trend must be offered"
    assert "ap-7" not in places or places.index("línea 10") < places.index("ap-7")
    assert any(item["trend"] == "ap-7" and item["offMission"] == "disaster" for item in round_["screened"])

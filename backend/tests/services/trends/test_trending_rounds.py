"""
A trending round through the selection step: made, read by the AI, sent
to analysis, and each article's trend remembered for the writing flow.
"""

import json

import pytest

from src.services.scraper.strategies.rss import betting_site, off_mission
from src.services.selection.ai_selector import TRENDING, AISelector, prompt
from src.services.selection.rounds import SelectionRounds
from src.services.selection.selection_service import InvalidSelection, SelectionService
from src.services.trends.ledger import TrendLedger

CARD = {"id": "abc123", "name": "línea 10", "signal": "google_trends_es", "traffic": 200, "seed": False}


def trend_round(urls=("https://elpais.com/madrid/2026-10-26/metro-reabre",)):

    return {
        "startedAt": "2026-10-26T16:00:00+00:00",
        "lens": "trending",
        "groups": [],
        "perSource": 2,
        "candidates": [
            {"url": url, "title": "Reabre la Línea 10", "language": "es", "sourceName": "EL PAÍS", "trend": CARD}
            for url in urls
        ],
        "totals": {"candidates": len(urls)},
    }


class FakeTrending:

    def __init__(self):
        self.calls = []

    def discover(self, **asked):
        self.calls.append(asked)
        return trend_round()


class FakeIngestion:

    def discover_candidates(self, *args, **kwargs):
        raise AssertionError("a trending round does not read the groups' sources")


class TellingSelector:
    """Records whether it was told the list is trending."""

    def __init__(self):
        self.told = []

    def select(self, candidates, groups, limit, min_score=6.0, trending=False):
        from src.services.selection.ai_selector import AISelection

        self.told.append(trending)
        return AISelection(picks=[], scored=[], model="fake", calls=1)


def service(tmp_path, ledger=None, selector=None):

    return SelectionService(
        ingestion=FakeIngestion(),
        selector=selector,
        rounds=SelectionRounds(tmp_path / "rounds"),
        trending=FakeTrending(),
        ledger=ledger,
    )


def test_a_trending_round_is_made_by_the_lens_with_what_was_asked(tmp_path):

    selection = service(tmp_path)

    round_ = selection.create_round(
        [], None, 2, trending=True, signal_ids=["google_trends_es"], seed="#FarmearAura", search=True,
    )

    assert round_["lens"] == "trending"
    assert selection.trending.calls == [{
        "groups": [], "signal_ids": ["google_trends_es"], "seed": "#FarmearAura",
        "per_trend": 2, "search": True, "topic_emphasis": None,
    }]
    assert selection.list()[0]["lens"] == "trending"


def test_without_a_lens_configured_a_trending_round_is_refused(tmp_path):

    selection = SelectionService(ingestion=FakeIngestion(), rounds=SelectionRounds(tmp_path))

    with pytest.raises(InvalidSelection):
        selection.create_round([], trending=True)


def test_queueing_a_trending_round_remembers_each_articles_trend(tmp_path):

    ledger = TrendLedger(tmp_path / "trends" / "articles.json")
    selection = service(tmp_path, ledger=ledger)

    round_ = selection.create_round([], trending=True)
    url = round_["candidates"][0]["url"]

    selection.queue(round_["id"], [url], start_job=lambda u: ("job-1", False))

    assert ledger.find(url)["name"] == "línea 10"
    # Found again by host and path, as the lake keys articles.
    assert ledger.find(url.replace("https://", "https://www.") + "?utm=x")["traffic"] == 200

    saved = json.loads((tmp_path / "trends" / "articles.json").read_text(encoding="utf-8"))
    [entry] = saved["articles"].values()
    assert (entry["url"], entry["roundId"]) == (url, round_["id"])


def test_an_article_that_could_not_be_queued_is_not_remembered(tmp_path):

    ledger = TrendLedger()
    selection = service(tmp_path, ledger=ledger)

    round_ = selection.create_round([], trending=True)
    url = round_["candidates"][0]["url"]

    def refuse(_):
        raise RuntimeError("queue full")

    selection.queue(round_["id"], [url], start_job=refuse)

    assert ledger.find(url) is None


def test_the_ledger_survives_a_restart(tmp_path):

    path = tmp_path / "articles.json"

    TrendLedger(path).remember("https://a.example/2026/10/26/story", CARD, round_id="0123456789abcdef")

    assert TrendLedger(path).find("https://a.example/2026/10/26/story")["id"] == "abc123"
    assert TrendLedger(path).find("https://a.example/other") is None
    assert TrendLedger(path).find(None) is None


def test_the_ai_is_told_only_when_a_round_is_trending(tmp_path):

    selector = TellingSelector()
    selection = service(tmp_path, selector=selector)

    round_ = selection.create_round([], trending=True)
    selection.run_ai_selection(round_["id"], 20, 6.0)

    assert selector.told == [True]


class RecordingLLM:

    model = "fake"

    def __init__(self):
        self.systems = []
        self.prompts = []

    def complete_json(self, system_prompt, user_prompt, max_retries=1):
        self.systems.append(system_prompt)
        self.prompts.append(user_prompt)
        return {"scores": []}


def test_a_trending_list_is_read_with_one_sentence_more_and_each_trend_named():

    llm = RecordingLLM()
    candidates = trend_round()["candidates"]

    AISelector(llm).select(candidates, [], limit=5, trending=True)
    AISelector(llm).select(candidates, [], limit=5)

    trending_system, plain_system = llm.systems
    assert TRENDING in trending_system and TRENDING not in plain_system
    assert "Score the story, not its popularity" in trending_system
    assert "   Trending: línea 10" in llm.prompts[0]
    assert prompt(candidates, []).startswith("Chosen topics: any.")


@pytest.mark.parametrize("url, betting", [
    ("https://sportsbook.fanduel.com/tennis/atp-vienna-2026/matteo-berrettini-v-tomas", True),
    ("https://www.dimers.com/tennis/news/matteo-berrettini-vs-tomas-etcheverry-prediction", True),
    ("https://www.bet365.es/noticias/2026/10/26/cuotas", True),
    ("https://www.tennisworlditalia.com/en/tennis/news/atp-vienna-berrettini-bounces-back", False),
    # "fanduel.com" inside another name is not FanDuel.
    ("https://notfanduel.com/story/2026/10/26/a-real-story", False),
])
def test_a_betting_sites_page_is_off_mission_whatever_its_path(url, betting):

    assert off_mission(url) is betting


def test_a_betting_host_is_matched_on_itself_and_its_parents():

    assert betting_site("sportsbook.fanduel.com") and betting_site("FanDuel.com.")
    assert not betting_site("fanduel.com.example.org")

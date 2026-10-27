"""
The trending lens's experiments (src/evaluation/trend_experiments.py), on
hand-built candidates and fake screens: nothing embedded.
"""

import json

import pytest

from src.config.topics import TOPICS
from src.evaluation import trend_experiments as te
from src.services.selection.mission_screen import Assessment, MissionScreen, Reading, Verdict


# ----------------------------------------------------------------------
# topics24 (T3)
# ----------------------------------------------------------------------


def test_the_two_topic_sets_differ_only_by_the_new_topic_and_entertainments_keywords():

    before, after = te.topics_before(), te.topics_after()

    assert len(before) == len(TOPICS) == 23 and len(after) == 24
    assert te.NEW_TOPIC not in before
    assert list(after)[list(after).index("inspiration") + 1] == te.NEW_TOPIC

    moved = {"viral trend", "internet culture", "social media trend"}
    assert moved <= set(before["entertainment"].keywords)
    assert not moved & set(after["entertainment"].keywords)
    assert moved <= set(after[te.NEW_TOPIC].keywords)
    assert {k: v for k, v in after.items() if k not in ("entertainment", te.NEW_TOPIC)} == {
        k: v for k, v in before.items() if k != "entertainment"
    }


def test_the_screen_compares_with_the_topics_it_is_given():

    class Recording:
        def __init__(self):
            self.texts = []

        def encode_many(self, texts):
            self.texts.extend(texts)
            return [[1.0, 0.0] for _ in texts]

    service = Recording()
    MissionScreen(service, topics=te.topics_after())._label_vectors()

    assert any("Internet Culture & Trends" in text for text in service.texts)


def test_labelled_candidates_are_read_once_each_with_their_exemption(tmp_path):

    ranking_file = tmp_path / "ranking.json"
    alignment_file = tmp_path / "alignment.json"
    reserve_file = tmp_path / "reserve.json"

    ranking_file.write_text(json.dumps({"candidates": [
        {"url": "https://a.example/2026/10/06/one", "title": "One", "hand": 2, "lang": "en", "positive_editorial": True},
        {"url": "https://a.example/untitled", "title": None, "hand": 0},
    ]}), encoding="utf-8")
    alignment_file.write_text(json.dumps({"candidates": [
        # The same article again, with a tracking parameter: read once.
        {"url": "https://www.a.example/2026/10/06/one?utm=x", "title": "One", "hand": 2},
        {"url": "https://b.example/two", "title": "Two", "summary": "s", "hand": 0, "source": "gnn", "belongsTo": ["society"]},
    ]}), encoding="utf-8")
    reserve_file.write_text(json.dumps({"candidates": [
        {"url": "https://c.example/three", "title": "Three", "hand": 1, "source": "bbc", "belongsTo": ["culture"]},
    ]}), encoding="utf-8")

    found = te.load_labelled(ranking_file, alignment_file, reserve_file, positive_sources={"gnn"})

    assert [c["title"] for c in found] == ["One", "Two", "Three"]
    assert [c["exempt"] for c in found] == [True, True, False]
    assert [c["set"] for c in found] == ["2026-10-06", "2026-10-09", "2026-10-13"]


class ScriptedScreen:
    """Answers each candidate by title from `plan`: (left out as, nearest topic, topics)."""

    def __init__(self, plan, topics):
        self.plan = plan
        self.topics = topics

    def assess(self, candidates, exempt=None):

        out = []

        for candidate in candidates:
            off, nearest, similarities = self.plan[candidate.title]
            reading = Reading(
                nearest_topic=nearest, topic=0.5, nearest_off="celebrity", off=0.45, impact=0.4,
                topics=similarities,
            )
            out.append(Assessment(Verdict(off_mission=off) if off else None, reading))

        return out


def sims(**near) -> dict:
    """Every 24 topics at 0.3, those named nearer."""

    return {topic: near.get(topic, 0.3) for topic in te.topics_after()}


def candidate(title, hand, belongs=None):
    return {"url": f"https://x.example/{title}", "title": title, "summary": None, "language": "en",
            "hand": hand, "belongsTo": belongs, "exempt": False, "set": "2026-10-09"}


def test_the_rule_counts_leaks_losses_and_pulls():

    candidates = [
        # Left out with 23, back in with 24, and not worth offering: a leak.
        candidate("influencer drama", 0, ["culture"]),
        # Kept with 23, left out with 24, worth offering: a loss.
        candidate("museum reopens", 2, ["culture"]),
        # A Society story that now fits Culture: a pull.
        candidate("school lunch", 2, ["society"]),
        candidate("a play", 1, ["culture"]),
    ]

    before = ScriptedScreen({
        "influencer drama": ("celebrity", "entertainment", sims(entertainment=0.5)),
        "museum reopens": (None, "arts", sims(arts=0.6)),
        "school lunch": (None, "education", sims(education=0.6)),
        "a play": (None, "arts", sims(arts=0.6)),
    }, te.topics_before())

    after = ScriptedScreen({
        "influencer drama": (None, te.NEW_TOPIC, sims(internet_culture=0.6)),
        "museum reopens": ("celebrity", "arts", sims(arts=0.6)),
        "school lunch": (None, te.NEW_TOPIC, sims(internet_culture=0.62, education=0.6)),
        "a play": (None, "arts", sims(arts=0.6)),
    }, te.topics_after())

    result = te.topics24_experiment(candidates, before, after)

    assert [item["title"] for item in result["leaked"]] == ["influencer drama"]
    assert [item["title"] for item in result["lost"]] == ["museum reopens"]
    assert [item["title"] for item in result["pulled"]] == ["school lunch"]
    assert {item["title"] for item in result["nearestIsNewTopic"]} == {"influencer drama", "school lunch"}
    assert result["checks"]["leak"]["holds"] and result["checks"]["loss"]["holds"]
    assert result["leftOut"] == {"before": 1, "after": 1}

    report = te.topics24_report(result)
    assert "| Leak: back in, not worth offering | 1 | <= 2 | True |" in report


def test_a_measured_fit_drop_past_the_bound_rejects_the_topic():

    result = {
        "rule": "rule.md", "candidates": 0, "bySet": {}, "labels": {"0": 0, "1": 0, "2": 0},
        "leftOut": {"before": 0, "after": 0}, "groupFitAuc": {"before": 0.9, "after": 0.877, "n": 0},
        "changedNearestTopic": 0, "leaked": [], "lost": [], "pulled": [], "nearestIsNewTopic": [],
        "checks": {
            "leak": {"value": 0, "bound": 2, "holds": True},
            "loss": {"value": 0, "bound": 2, "holds": True},
            "fit": {"value": 0.023, "bound": 0.02, "holds": False},
            "pull": {"value": 0, "bound": 3, "holds": True},
        },
        "adopt": False,
    }

    assert "**Not adopted**: fit failed." in te.topics24_report(result)


def test_the_configured_topics_are_still_twenty_three():
    """Not adopted on 2026-10-26: the topic lives only in the experiment."""

    assert te.NEW_TOPIC not in TOPICS
    assert len(TOPICS) == 23


# ----------------------------------------------------------------------
# trends (T6)
# ----------------------------------------------------------------------


def trend_candidate(n: int, signal: str = "Google Trends · Spain", trend_id: str = None) -> dict:
    return {
        "url": f"https://news.example/2026/10/26/story-{n}",
        "title": f"Story {n}",
        "summary": f"Summary {n}",
        "sourceName": "Example",
        "language": "es",
        "rank": {"score": 1 - n / 100, "news": 0.5, "record": 0.8, "virality": 0.5},
        "reading": {"impact": 0.4},
        "trend": {"id": trend_id or f"t{n}", "name": f"trend {n}", "signalName": signal},
    }


def test_the_first_twenty_are_labelled_without_their_scores_in_another_order():

    round_ = {"candidates": [trend_candidate(n) for n in range(1, 26)]}

    items = te.label_items(round_)

    assert len(items) == 20
    assert {item["url"] for item in items} == {c["url"] for c in round_["candidates"][:20]}
    assert [item["n"] for item in items] == list(range(1, 21))
    assert [item["url"] for item in items] != [c["url"] for c in round_["candidates"][:20]]
    for item in items:
        assert set(item) == {"url", "title", "summary", "outlet", "language", "trend", "signal", "n"}


class FakeSelection:

    def __init__(self):
        self.made = []

    def create_round(self, groups, source_ids=None, per_source=3, listed=20, trending=False, **_):
        self.made.append((tuple(groups), per_source, listed, trending))
        candidates = [trend_candidate(n) for n in range(1, 22)] if trending else [trend_candidate(100 + n) for n in range(5)]
        return {"id": f"{len(self.made):016x}", "candidates": candidates[:listed], "reserve": candidates[listed:]}


def test_a_day_makes_one_trending_round_and_the_five_groups_and_runs_once(tmp_path):

    selection = FakeSelection()

    folder = te.trends_day(selection, "2026-10-26", root=tmp_path)

    assert selection.made == [
        ((), 2, 20, True),
        (("society", "science", "environment"), 3, 20, False),
        (("culture", "health"), 3, 20, False),
    ]
    assert {path.name for path in folder.iterdir()} == {"rounds.json", "trending-round.json", "topic-rounds.json", "to-label.json"}
    assert len(json.loads((folder / "to-label.json").read_text(encoding="utf-8"))["items"]) == 20

    with pytest.raises(SystemExit, match="one round a day"):
        te.trends_day(selection, "2026-10-26", root=tmp_path)

    te.trends_day(selection, "2026-10-26", root=tmp_path, force=True)


def day(name: str, labels: dict | None, trending=None, topics=None) -> dict:
    trending = trending or {
        "id": "a" * 16,
        "candidates": [trend_candidate(n) for n in range(1, 21)],
        "trends": [{"id": f"t{n}"} for n in range(1, 21)],
        "totals": {"trends": 20, "discovered": 50, "notArticles": 10, "stale": 2, "alreadyStored": 3,
                   "screened": 15, "candidates": 20},
    }
    return {"day": name, "rounds": {}, "trending": trending, "topics": topics or [], "labels": labels}


def test_a_labelled_day_reports_precision_new_stories_and_the_funnel():

    labels = {"labelledBy": "Claude", "labels": {
        "https://news.example/2026/10/26/story-1": {"hand": 2, "angle": "story"},
        "https://news.example/2026/10/26/story-2": {"hand": 1, "angle": "possible", "private": True},
        "https://news.example/2026/10/26/story-3": {"hand": 0, "angle": "none"},
        "https://news.example/2026/10/26/story-4": {"hand": 1, "angle": "none"},
    }}

    # The topic rounds offered story 4 themselves, and a story titled like story 1.
    topics = [{"candidates": [{"url": "https://www.news.example/2026/10/26/story-4?utm=x", "title": "x"}],
               "reserve": [{"url": "https://other.example/a", "title": "Story 1, told elsewhere"}]}]

    def similar(title, titles):
        return 0.9 if title == "Story 1" else 0.1

    rounds_now = {"a" * 16: {"queued": {"urls": ["https://news.example/2026/10/26/story-1", "https://news.example/2026/10/26/story-2"]}}}
    admitted = {"news.example/2026/10/26/story-1": True, "news.example/2026/10/26/story-2": False}

    result = te.trends_experiment([day("2026-10-26", labels, topics=topics)], similar, rounds_now, admitted, {"t1"})

    [entry] = result["days"]
    assert (entry["labelled"], entry["worthOffering"], entry["clearlyPositive"]) == (4, 3, 1)
    assert entry["precision"] == 0.75 and entry["private"] == 1
    assert entry["angles"] == {"story": 1, "possible": 1, "none": 2}
    # Story 4 by its link, story 1 as the same story: only story 2 is new.
    assert [item["title"] for item in entry["newStories"]] == ["Story 2"]
    assert entry["funnel"] == {
        "trends": 20, "articles": 50, "passedLinkFilters": 35, "keptByScreen": 20, "offered": 20, "shown": 20,
        "chosen": 2, "admitted": 1, "published": 1,
    }
    assert (result["daysRemaining"], result["decisions"]) == (4, None)
    assert result["bySignal"]["Google Trends · Spain"] == {
        "labelled": 4, "notWorth": 1, "worth": 2, "clearlyPositive": 1, "notWorthShare": 0.25,
    }

    report = te.trends_report(result)
    assert "**4 to go**" in report
    assert "Nothing is decided before the five days" in report
    assert "Labelled by: Claude." in report


def test_without_inference_new_stories_are_told_by_link_and_the_report_says_so():

    labels = {"labels": {"https://news.example/2026/10/26/story-1": {"hand": 2}}}
    topics = [{"candidates": [{"url": "https://other.example/a", "title": "Story 1, told elsewhere"}]}]

    result = te.trends_experiment([day("2026-10-26", labels, topics=topics)])

    assert result["sameStoryBy"] == "link only"
    assert len(result["days"][0]["newStories"]) == 1


def test_an_unlabelled_day_counts_as_run_not_labelled():

    result = te.trends_experiment([day("2026-10-26", None)])

    assert (result["daysRun"], result["daysLabelled"], result["daysRemaining"]) == (1, 0, 5)
    assert result["precision"] is None
    assert "**5 to go**" in te.trends_report(result)


def test_after_five_days_the_rule_decides():

    def labelled(worth: int) -> dict:
        return {"labels": {
            f"https://news.example/2026/10/26/story-{n}": {"hand": 1 if n <= worth else 0}
            for n in range(1, 21)
        }}

    days = [day(f"2026-10-{26 + i}", labelled(worth)) for i, worth in enumerate((3, 2, 2, 2, 1))]

    result = te.trends_experiment(days)

    # 10 new stories worth offering (no topic round offered any): the lens stays.
    assert result["decisions"]["lensStays"] is True
    # 90 of 100 not worth offering from one signal: disabled by default.
    assert result["decisions"]["disableSignals"] == ["Google Trends · Spain"]
    assert result["decisions"]["refitWeights"] is True
    assert "Signals disabled by default: Google Trends · Spain." in te.trends_report(result)

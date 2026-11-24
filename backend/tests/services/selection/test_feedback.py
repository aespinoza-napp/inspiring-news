"""
What the person rejects teaches the ranking (src/services/selection/feedback.py):
the store, the lean, the ranking's story part, and what a new round leaves
out. Vectors are two- or three-dimensional and made by hand; nothing reaches
inference/.
"""

import json

import numpy as np
import pytest

from src.services.inference_client import InferenceUnavailable
from src.services.selection import feedback as feedback_module
from src.services.selection import ranking
from src.services.selection.feedback import Feedback, SelectionFeedback
from src.services.selection.mission_screen import Reading
from src.services.selection.rounds import SelectionRounds
from src.services.selection.selection_service import InvalidSelection, SelectionService

from tests.services.selection.test_selection_service import FakeSelector, Jobs

E1, E2, E3 = np.eye(3)


def unit(*values) -> np.ndarray:

    vector = np.asarray(values, dtype=float)

    return vector / np.linalg.norm(vector)


# ----------------------------------------------------------------------
# The lean, and what the ranking does with it
# ----------------------------------------------------------------------


def test_the_lean_is_how_much_nearer_the_rejected_average_than_the_chosen():

    taught = Feedback(rejected=E1, chosen=E2, rejected_count=3, chosen_count=3)

    assert taught.lean(E1) == pytest.approx(1.0)
    assert taught.lean(E2) == pytest.approx(-1.0)
    assert taught.lean(E3) == pytest.approx(0.0)
    # Not unit length on the way in: compared as a direction.
    assert taught.lean(E1 * 7) == pytest.approx(1.0)
    assert taught.lean(None) is None


def test_leaving_out_waits_for_enough_examples(monkeypatch):

    few = Feedback(rejected=E1, chosen=E2, rejected_count=10, chosen_count=5)
    many = Feedback(rejected=E1, chosen=E2, rejected_count=40, chosen_count=20)

    assert not few.leave_out(0.5)
    assert many.leave_out(0.09) and not many.leave_out(0.08) and not many.leave_out(None)


def reading(vector, impact=0.40, off=0.40) -> Reading:

    return Reading(nearest_topic="cities", topic=0.5, nearest_off="politics", off=off, impact=impact, vector=vector)


def test_a_story_like_the_rejected_ones_reads_less_positive_and_its_lean_is_recorded():

    taught = Feedback(rejected=E1, chosen=E2, rejected_count=3, chosen_count=3)
    standing = ranking.Standing(reliability=0.8, judged=5, kept=5)

    plain = ranking.rank(reading(E1), standing, fit=0.05)
    like_rejected = ranking.rank(reading(E1), standing, fit=0.05, feedback=taught)
    like_chosen = ranking.rank(reading(E2), standing, fit=0.05, feedback=taught)

    assert "lean" not in plain
    assert like_rejected["lean"] == pytest.approx(1.0) and like_chosen["lean"] == pytest.approx(-1.0)
    assert like_rejected["news"] < plain["news"] < like_chosen["news"]
    assert like_rejected["score"] < plain["score"] < like_chosen["score"]

    # The other parts, and so the weights, are untouched.
    assert (like_rejected["topic"], like_rejected["record"]) == (plain["topic"], plain["record"])


def test_a_trending_story_is_lowered_the_same_way():

    taught = Feedback(rejected=E1, chosen=E2, rejected_count=3, chosen_count=3)
    standing = ranking.Standing(reliability=0.0, judged=5, kept=5)

    plain = ranking.trend_rank(reading(E1), standing, virality=0.5)
    lowered = ranking.trend_rank(reading(E1), standing, virality=0.5, feedback=taught)

    assert lowered["lean"] == pytest.approx(1.0) and lowered["score"] < plain["score"]


def test_more_of_the_lean_comes_off_as_the_examples_grow():
    """A quarter from 3 + 3, half from 10 + 5: half cost the clearly positive a little with fewer."""

    few = Feedback(rejected=E1, chosen=E2, rejected_count=3, chosen_count=3)
    more = Feedback(rejected=E1, chosen=E2, rejected_count=10, chosen_count=5)
    rejected_many_chosen_few = Feedback(rejected=E1, chosen=E2, rejected_count=30, chosen_count=4)

    assert (few.weight, more.weight, rejected_many_chosen_few.weight) == (0.25, 0.5, 0.25)

    standing = ranking.Standing(reliability=0.8, judged=5, kept=5)
    tilted = unit(1, 0.0, 1)  # lean 0.7071
    as_is = reading(tilted, impact=0.45, off=0.40)

    for taught in (few, more):
        ranked = ranking.rank(as_is, standing, feedback=taught)
        expected = ranking.news_part(reading(None, impact=0.45 - taught.weight * taught.lean(tilted), off=0.40))
        assert ranked["news"] == round(expected, 3)


def test_the_lowered_share_comes_off_the_reading_before_it_is_scaled():

    assert ranking.news_part(reading(None, impact=0.45, off=0.40), lowered=0.02) == pytest.approx(
        ranking.news_part(reading(None, impact=0.43, off=0.40))
    )


# ----------------------------------------------------------------------
# The store
# ----------------------------------------------------------------------


def round_of(round_id="0123456789abcdef", edition="positive", n=4, host="news.example"):

    return {
        "id": round_id,
        "edition": edition,
        "startedAt": "2026-11-24T10:00:00+00:00",
        "candidates": [
            {"url": f"https://{host}/story-{i}?utm_source=rss", "title": f"Story {i}", "summary": f"About {i}", "sourceName": "Example"}
            for i in range(1, n + 1)
        ],
    }


def test_a_rejection_is_kept_by_host_and_path_per_edition_and_said_again_replaces(tmp_path):

    store = SelectionFeedback(lambda: tmp_path)
    round_ = round_of()
    first = round_["candidates"][0]

    store.reject(round_, first, ["politics"], None, False)
    store.reject(round_, first, ["no_impact", "politics"], "a campaign speech", True)

    assert store.rejected_keys("positive") == {"news.example/story-1"}
    assert store.rejected_keys("devastating") == set()
    assert store.blocked_hosts("positive") == {"news.example"}

    on_disk = json.loads((tmp_path / "feedback" / "examples.json").read_text(encoding="utf-8"))
    assert [row["reasons"] for row in on_disk["rejected"]] == [["no_impact", "politics"]]

    # A new process reads it back.
    again = SelectionFeedback(lambda: tmp_path)
    assert again.counts("positive") == (1, 0, 1)
    assert again.summary("positive")["rejected"][0]["note"] == "a campaign speech"


def test_forgetting_a_rejection_takes_its_blocked_site_with_it(tmp_path):

    store = SelectionFeedback(lambda: tmp_path)
    round_ = round_of()

    store.reject(round_, round_["candidates"][0], [], None, True)
    store.reject(round_, round_["candidates"][1], [], None, False)

    gone = store.forget("positive", url=round_["candidates"][0]["url"])

    assert len(gone) == 2
    assert store.counts("positive") == (1, 0, 0)
    assert store.forget("positive", url="https://elsewhere.example/x") == []


def test_what_was_chosen_counts_once_and_is_read_from_the_rounds_kept_on_first_use(tmp_path):

    rounds = SelectionRounds(tmp_path)
    old = round_of("aaaaaaaaaaaaaaaa")
    old["personSelection"] = {"urls": [old["candidates"][0]["url"]]}
    old["queued"] = {"urls": [old["candidates"][0]["url"], old["candidates"][1]["url"]]}
    rounds.save(old)

    store = SelectionFeedback(rounds.folder, rounds=rounds)

    assert store.counts("positive") == (0, 2, 0)

    store.choose(old, [old["candidates"][1]["url"], old["candidates"][2]["url"]], "sent")
    assert store.counts("positive") == (0, 3, 0)


def test_the_averages_need_three_of_each_and_each_text_is_embedded_once(tmp_path):

    asked = []

    def embed(texts):
        asked.append(list(texts))
        return np.array([E1 if "Bad" in text else E2 for text in texts])

    store = SelectionFeedback(lambda: tmp_path, embed=embed)
    round_ = round_of(n=6)
    bad = [{**c, "title": f"Bad {i}"} for i, c in enumerate(round_["candidates"][:3])]
    good = round_["candidates"][3:]

    for candidate in bad[:2]:
        store.reject(round_, candidate, [], None, False)
    store.choose({**round_, "candidates": good}, [c["url"] for c in good], "recorded")

    assert store.feedback("positive") is None and asked == []

    store.reject(round_, bad[2], [], None, False)
    taught = store.feedback("positive")

    assert taught.lean(E1) == pytest.approx(1.0) and (taught.rejected_count, taught.chosen_count) == (3, 3)
    assert len(asked) == 1 and len(asked[0]) == 6

    store.feedback("positive")
    assert len(asked) == 1


# ----------------------------------------------------------------------
# A new round
# ----------------------------------------------------------------------


class TaughtIngestion:
    """Discovery that records the feedback it was given and ranks by it as the real one would."""

    def __init__(self, candidates):
        self.candidates = candidates
        self.given = []

    def discover_candidates(self, groups, source_ids=None, per_source=3, topic_emphasis=None, **told):
        self.given.append(told.get("feedback"))
        taught = told.get("feedback")
        ranked = []
        for candidate in self.candidates:
            vector = candidate.get("_vector")
            rank = {"score": 0.5}
            if taught is not None and vector is not None:
                rank["lean"] = round(taught.lean(vector), 4)
            ranked.append({key: value for key, value in candidate.items() if key != "_vector"} | {"rank": rank})
        return {
            "startedAt": "2026-11-24T10:00:00+00:00", "groups": groups, "topics": [], "perSource": per_source,
            "sources": [], "candidates": ranked, "screened": [], "totals": {"candidates": len(ranked), "screened": 0},
        }


def taught_service(tmp_path, candidates, embed=None):

    rounds = SelectionRounds(tmp_path)
    feedback = SelectionFeedback(rounds.folder, embed=embed, rounds=rounds)

    return SelectionService(ingestion=TaughtIngestion(candidates), selector=FakeSelector(), rounds=rounds, feedback=feedback)


def story(slug, host="news.example", title=None, vector=None):

    return {"url": f"https://{host}/{slug}", "title": title or slug, "summary": None, "source": "x", "sourceName": host, "_vector": vector}


def test_a_rejected_article_never_comes_back_and_a_blocked_sites_are_left_out(tmp_path):

    service = taught_service(tmp_path, [
        story("horoscope-monday"), story("mortgage-calculator", host="calc.example"), story("solar-farm"), story("reef-recovers"),
    ])

    first = service.create_round(["science"], listed=2)
    assert [c["url"] for c in first["candidates"]] == ["https://news.example/horoscope-monday", "https://calc.example/mortgage-calculator"]

    service.reject(first["id"], "https://news.example/horoscope-monday", ["no_impact"])
    service.reject(first["id"], "https://calc.example/mortgage-calculator", ["service"], site=True)

    # The round itself keeps its list: the person and the AI choose from the same one.
    assert len(service.get(first["id"])["candidates"]) == 2

    # With a tracking parameter, the same article; and another page of the blocked site.
    service.ingestion.candidates[0]["url"] += "?utm_medium=rss"
    service.ingestion.candidates.insert(2, story("tax-calculator", host="calc.example"))
    second = service.create_round(["science"], listed=2)

    assert [c["url"] for c in second["candidates"]] == ["https://news.example/solar-farm", "https://news.example/reef-recovers"]
    assert [(row["url"].rsplit("/", 1)[1], row["offMission"]) for row in second["screened"]] == [
        ("horoscope-monday?utm_medium=rss", "rejected"),
        ("mortgage-calculator", "rejected"),
        ("tax-calculator", "blocked_site"),
    ]
    assert second["totals"]["learned"] == 3
    assert second["feedback"]["status"] == "ok" and second["feedback"]["lowered"] is False
    # Below three of each, nothing to lower by, and nothing asked of inference/.
    assert service.ingestion.given == [None, None]


def test_with_three_of_each_discovery_is_given_the_feedback_and_with_enough_it_leaves_out(tmp_path, monkeypatch):

    def embed(texts):
        return np.array([E1 if text.startswith("Bad") else E2 for text in texts])

    candidates = [story(f"bad-{i}", title=f"Bad {i}") for i in range(3)] + [story(f"good-{i}", title=f"Good {i}") for i in range(3)]
    service = taught_service(tmp_path, candidates, embed=embed)

    first = service.create_round(["science"])
    for i in range(3):
        service.reject(first["id"], f"https://news.example/bad-{i}")
    service.record_person_selection(first["id"], [f"https://news.example/good-{i}" for i in range(3)])

    service.ingestion.candidates = [
        story("like-the-bad", vector=unit(1, 0.1, 0)),
        story("like-the-good", vector=unit(0.1, 1, 0)),
        story("neither", vector=E3),
    ]

    lowered = service.create_round(["science"])
    leans = {c["url"].rsplit("/", 1)[1]: c["rank"]["lean"] for c in lowered["candidates"]}

    assert service.ingestion.given[-1] is not None
    assert leans["like-the-bad"] > 0.8 and leans["like-the-good"] < -0.8 and abs(leans["neither"]) < 1e-6
    assert lowered["feedback"]["lowered"] is True and lowered["feedback"]["leavesOut"] is False
    assert lowered["feedback"]["weight"] == 0.25
    assert len(lowered["candidates"]) == 3

    monkeypatch.setattr(feedback_module, "LEAVE_OUT_MINIMUM", (3, 3))
    left = service.create_round(["science"])

    assert [c["url"].rsplit("/", 1)[1] for c in left["candidates"]] == ["like-the-good", "neither"]
    [out] = [row for row in left["screened"] if row["offMission"] == "like_rejected"]
    assert out["url"].endswith("like-the-bad") and out["margin"] > feedback_module.LEAVE_OUT_LEAN


def test_without_inference_nothing_is_lowered_and_the_round_says_so_but_rejections_still_hold(tmp_path):

    def down(texts):
        raise InferenceUnavailable("refused")

    candidates = [story(f"bad-{i}") for i in range(3)] + [story(f"good-{i}") for i in range(3)]
    service = taught_service(tmp_path, candidates, embed=down)

    first = service.create_round(["science"])
    for i in range(3):
        service.reject(first["id"], f"https://news.example/bad-{i}")
    service.record_person_selection(first["id"], [f"https://news.example/good-{i}" for i in range(3)])

    second = service.create_round(["science"])

    assert second["feedback"]["status"] == "unavailable" and "refused" in second["feedback"]["error"]
    assert service.ingestion.given[-1] is None
    assert [c["url"].rsplit("/", 1)[1] for c in second["candidates"]] == ["good-0", "good-1", "good-2"]


def test_what_was_rejected_cannot_be_chosen_nor_what_was_chosen_rejected(tmp_path):

    service = taught_service(tmp_path, [story("a"), story("b"), story("c")])
    round_ = service.create_round(["science"])

    service.reject(round_["id"], "https://news.example/a", ["politics", "no_impact"], note="  campaign  ")
    assert service.get(round_["id"])["rejected"]["https://news.example/a"]["reasons"] == ["no_impact", "politics"]
    assert service.get(round_["id"])["rejected"]["https://news.example/a"]["note"] == "campaign"

    with pytest.raises(InvalidSelection, match="not for us"):
        service.record_person_selection(round_["id"], ["https://news.example/a"])

    with pytest.raises(InvalidSelection, match="not for us"):
        service.queue(round_["id"], ["https://news.example/a"], Jobs())

    with pytest.raises(InvalidSelection, match="Not a reason"):
        service.reject(round_["id"], "https://news.example/b", ["boring"])

    with pytest.raises(InvalidSelection, match="Not a candidate"):
        service.reject(round_["id"], "https://elsewhere.example/z")

    service.record_person_selection(round_["id"], ["https://news.example/b"])

    with pytest.raises(InvalidSelection, match="You chose this one"):
        service.reject(round_["id"], "https://news.example/b")

    service.reject(round_["id"], "https://news.example/a", undo=True)
    assert service.get(round_["id"])["rejected"] == {}
    assert service.feedback.counts("positive") == (0, 1, 0)


def test_forgetting_from_the_list_clears_the_rounds_mark_too(tmp_path):

    service = taught_service(tmp_path, [story("a"), story("b")])
    round_ = service.create_round(["science"])
    service.reject(round_["id"], "https://news.example/a", site=True)

    assert service.forget("positive", host="news.example")
    assert service.get(round_["id"])["rejected"]["https://news.example/a"]["site"] is False

    assert service.forget("positive", url="https://news.example/a")
    assert service.get(round_["id"])["rejected"] == {}
    assert not service.forget("positive", url="https://news.example/a")


def test_the_comparison_names_what_the_ai_chose_that_the_person_rejected(tmp_path):

    service = taught_service(tmp_path, [story("a"), story("b"), story("c")])
    service.selector = FakeSelector(picks=["https://news.example/a", "https://news.example/c"])
    round_ = service.create_round(["science"])

    service.reject(round_["id"], "https://news.example/a", ["no_impact"])
    service.record_person_selection(round_["id"], ["https://news.example/b"])
    service.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    comparison = service.get(round_["id"])["comparison"]

    assert comparison["rejected"] == ["https://news.example/a"]
    assert comparison["aiPickedRejected"] == ["https://news.example/a"]
    assert {summary["id"]: summary["rejected"] for summary in service.list()}[round_["id"]] == 1

import json

import pytest

from src.services.inference_client import InferenceUnavailable
from src.services.llms import LLMUnavailableError
from src.services.selection.ai_selector import AISelection, Scored
from src.services.selection.rounds import SelectionRounds
from src.services.selection.selection_service import (
    COMPARED,
    LISTED,
    MAX_LISTED,
    MAX_SELECTED,
    InvalidSelection,
    RoundNotFound,
    SelectionBusy,
    SelectionService,
    kappa,
)


def candidates(n: int) -> list[dict]:

    return [
        {"url": f"https://news.example/{i}", "title": f"Story {i}", "source": "example", "language": "en"}
        for i in range(1, n + 1)
    ]


class FakeIngestion:

    def __init__(self, found: int = 5):
        self.found = found
        self.calls = []
        self.emphases = []

    def discover_candidates(self, groups, source_ids=None, per_source=3, topic_emphasis=None):
        self.calls.append((groups, source_ids, per_source))
        self.emphases.append(topic_emphasis)
        return {
            "startedAt": "2026-10-05T10:00:00+00:00",
            "groups": groups,
            "topics": ["climate"],
            "perSource": per_source,
            "sources": [],
            "candidates": candidates(self.found),
            "ranking": {"topicEmphasis": {"asked": topic_emphasis, "applied": topic_emphasis if topic_emphasis is not None else 0.6, "default": 0.6}},
            "totals": {"candidates": self.found},
        }


class FakeSelector:

    def __init__(self, picks=(), error=None):
        self.picks = list(picks)
        self.error = error
        self.calls = []

    def select(self, candidates, groups, limit, min_score=6.0):
        self.calls.append((len(candidates), groups, limit, min_score))
        if self.error:
            raise self.error
        picks = [Scored(url, 8.0, "a solution") for url in self.picks][:limit]
        return AISelection(picks=picks, scored=picks, model="fake-model", calls=1)


class Jobs:

    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return f"job-{len(self.urls)}", False


def service(tmp_path, found=5, selector=None):

    return SelectionService(
        ingestion=FakeIngestion(found),
        selector=selector or FakeSelector(),
        rounds=SelectionRounds(tmp_path),
    )


def test_a_round_lists_the_candidates_and_is_written_to_disk(tmp_path):

    selection = service(tmp_path)

    round_ = selection.create_round(["environment", "science"], per_source=4)

    assert selection.ingestion.calls == [(["environment", "science"], None, 4)]
    assert len(round_["candidates"]) == 5
    assert round_["aiSelection"] is None and round_["queued"] is None

    on_disk = json.loads((tmp_path / f"{round_['id']}.json").read_text(encoding="utf-8"))
    assert on_disk["candidates"] == round_["candidates"]


def test_the_rounds_topic_emphasis_goes_to_discovery_per_call_and_is_listed(tmp_path):

    selection = service(tmp_path)

    asked = selection.create_round(["science"], topic_emphasis=0.2)
    default = selection.create_round(["science"])

    assert selection.ingestion.emphases == [0.2, None]
    assert asked["ranking"]["topicEmphasis"]["applied"] == 0.2

    listed = {summary["id"]: summary["topicEmphasis"] for summary in selection.list()}

    assert listed == {asked["id"]: 0.2, default["id"]: 0.6}


def test_a_person_queues_some_of_the_candidates(tmp_path):

    selection = service(tmp_path)
    round_ = selection.create_round(["health"])
    jobs = Jobs()

    queued = selection.queue(round_["id"], ["https://news.example/2", "https://news.example/4", "https://news.example/2"], jobs)

    assert jobs.urls == ["https://news.example/2", "https://news.example/4"]
    assert [job["jobId"] for job in queued["jobs"]] == ["job-1", "job-2"]
    assert queued["selectedBy"] == "user" and queued["aiProposed"] == 0


@pytest.mark.parametrize("urls, message", [
    ([], "at least one"),
    ([f"https://news.example/{i}" for i in range(1, MAX_SELECTED + 2)], f"At most {MAX_SELECTED}"),
    (["https://elsewhere.example/a"], "Not a candidate"),
])
def test_a_selection_that_breaks_a_rule_queues_nothing(tmp_path, urls, message):

    selection = service(tmp_path, found=MAX_SELECTED + 1)
    round_ = selection.create_round(["culture"])
    jobs = Jobs()

    with pytest.raises(InvalidSelection, match=message):
        selection.queue(round_["id"], urls, jobs)

    assert jobs.urls == []


def test_a_round_is_sent_to_analysis_once(tmp_path):

    selection = service(tmp_path)
    round_ = selection.create_round(["culture"])
    selection.queue(round_["id"], ["https://news.example/1"], Jobs())

    with pytest.raises(InvalidSelection, match="already sent"):
        selection.queue(round_["id"], ["https://news.example/2"], Jobs())


def test_the_ai_proposal_is_kept_and_the_agreement_measured(tmp_path):

    ai = FakeSelector(picks=["https://news.example/1", "https://news.example/3", "https://news.example/5"])
    selection = service(tmp_path, selector=ai)
    round_ = selection.create_round(["environment"])

    state = selection.run_ai_selection(round_["id"], limit=20, min_score=6.0)

    assert state["status"] == "done"
    assert [pick["url"] for pick in state["picks"]] == ai.picks
    assert ai.calls == [(5, ["environment"], 20, 6.0)]

    # The editor keeps two of the three and adds one of their own.
    queued = selection.queue(round_["id"], ["https://news.example/1", "https://news.example/3", "https://news.example/2"], Jobs())

    assert (queued["selectedBy"], queued["aiProposed"], queued["aiKept"], queued["aiDropped"], queued["userAdded"]) == ("ai+user", 3, 2, 1, 1)

    saved = SelectionRounds(tmp_path).get(round_["id"])
    assert saved["aiSelection"]["status"] == "done" and saved["queued"]["selectedBy"] == "ai+user"


def test_taking_the_ai_proposal_unchanged_is_recorded_as_the_ais(tmp_path):

    picks = ["https://news.example/2", "https://news.example/4"]
    selection = service(tmp_path, selector=FakeSelector(picks=picks))
    round_ = selection.create_round(["science"])
    selection.run_ai_selection(round_["id"], limit=20, min_score=6.0)

    assert selection.queue(round_["id"], picks, Jobs())["selectedBy"] == "ai"


def test_the_laya_scorer_is_used_only_when_asked_and_recorded(tmp_path):

    llm, laya = FakeSelector(picks=["https://news.example/1"]), FakeSelector(picks=["https://news.example/2"])
    selection = SelectionService(ingestion=FakeIngestion(), selector=llm, rounds=SelectionRounds(tmp_path), laya_selector=laya)
    round_ = selection.create_round(["science"])

    state = selection.run_ai_selection(round_["id"], limit=20, min_score=6.0, scorer="laya")

    assert [pick["url"] for pick in state["picks"]] == ["https://news.example/2"]
    assert state["scorer"] == "laya" and llm.calls == [] and len(laya.calls) == 1

    assert selection.run_ai_selection(round_["id"], limit=20, min_score=6.0)["scorer"] == "llm"


def test_an_unreachable_laya_is_a_failed_selection(tmp_path):

    laya = FakeSelector(error=InferenceUnavailable("connection refused"))
    selection = SelectionService(ingestion=FakeIngestion(), selector=FakeSelector(), rounds=SelectionRounds(tmp_path), laya_selector=laya)
    round_ = selection.create_round(["science"])

    state = selection.run_ai_selection(round_["id"], limit=20, min_score=6.0, scorer="laya")

    assert state["status"] == "failed" and "Laya could not be reached" in state["error"]


def test_an_unreachable_model_is_a_failed_selection_not_an_empty_one(tmp_path):

    selection = service(tmp_path, selector=FakeSelector(error=LLMUnavailableError("refused")))
    round_ = selection.create_round(["science"])

    state = selection.run_ai_selection(round_["id"], limit=20, min_score=6.0)

    assert state["status"] == "failed" and "could not be reached" in state["error"]


def test_only_one_ai_selection_runs_at_a_time(tmp_path, monkeypatch):

    selection = service(tmp_path)
    first = selection.create_round(["science"])
    second = selection.create_round(["health"])

    # Hold the first one "running": no thread is started.
    monkeypatch.setattr("threading.Thread.start", lambda self: None)

    selection.start_ai_selection(first["id"])

    with pytest.raises(SelectionBusy):
        selection.start_ai_selection(second["id"])


def test_a_round_with_no_candidates_has_nothing_for_the_ai(tmp_path):

    selection = service(tmp_path, found=0)
    round_ = selection.create_round(["science"])

    with pytest.raises(InvalidSelection, match="no candidates"):
        selection.start_ai_selection(round_["id"])


def test_an_unknown_round_is_not_found(tmp_path):

    with pytest.raises(RoundNotFound):
        service(tmp_path).get("0123456789abcdef")


def test_rounds_survive_a_restart_and_are_listed_newest_first(tmp_path):

    selection = service(tmp_path)
    round_ = selection.create_round(["society"])

    restarted = SelectionService(ingestion=FakeIngestion(), selector=FakeSelector(), rounds=SelectionRounds(tmp_path))

    assert restarted.get(round_["id"])["groups"] == ["society"]
    assert [summary["id"] for summary in restarted.list()] == [round_["id"]]


def test_an_id_that_is_not_hex_never_reaches_the_file_system(tmp_path):

    assert SelectionRounds(tmp_path).get("../../etc/passwd") is None


# ----------------------------------------------------------------------
# Twenty shown, best first; forty on request
# ----------------------------------------------------------------------


def urls(first: int, last: int) -> list[str]:

    return [f"https://news.example/{i}" for i in range(first, last + 1)]


def test_a_round_shows_the_best_twenty_and_keeps_the_rest(tmp_path):

    round_ = service(tmp_path, found=LISTED + 5).create_round(["society"])

    assert [c["url"] for c in round_["candidates"]] == urls(1, LISTED)
    assert [c["url"] for c in round_["reserve"]] == urls(LISTED + 1, LISTED + 5)
    assert round_["totals"]["candidates"] == LISTED + 5


def test_asking_for_more_shows_the_next_up_to_forty(tmp_path):

    selection = service(tmp_path, found=MAX_LISTED + 10)
    round_ = selection.create_round(["society"])

    shown = selection.show_more(round_["id"])

    assert [c["url"] for c in shown["candidates"]] == urls(1, MAX_LISTED)
    assert len(shown["reserve"]) == 10
    assert len(selection.show_more(round_["id"])["candidates"]) == MAX_LISTED
    assert len(SelectionRounds(tmp_path).get(round_["id"])["candidates"]) == MAX_LISTED


def test_forty_can_be_asked_for_at_once_and_never_more(tmp_path):

    selection = service(tmp_path, found=MAX_LISTED + 10)

    assert len(selection.create_round(["society"], listed=MAX_LISTED)["candidates"]) == MAX_LISTED
    assert len(selection.create_round(["society"], listed=500)["candidates"]) == MAX_LISTED


def test_only_what_is_shown_can_be_sent_or_read_by_the_ai(tmp_path):

    ai = FakeSelector()
    selection = service(tmp_path, found=LISTED + 7, selector=ai)
    round_ = selection.create_round(["society"])

    selection.run_ai_selection(round_["id"], limit=20, min_score=6.0)

    assert ai.calls[0][0] == LISTED

    with pytest.raises(InvalidSelection, match="Not a candidate"):
        selection.queue(round_["id"], urls(LISTED + 1, LISTED + 1), Jobs())


def test_more_is_refused_once_sent_and_while_the_ai_reads_the_list(tmp_path, monkeypatch):

    selection = service(tmp_path, found=LISTED + 5)

    sent = selection.create_round(["society"])
    selection.queue(sent["id"], urls(1, 1), Jobs())

    with pytest.raises(InvalidSelection, match="already sent"):
        selection.show_more(sent["id"])

    reading = selection.create_round(["society"])
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    selection.start_ai_selection(reading["id"])

    with pytest.raises(SelectionBusy):
        selection.show_more(reading["id"])



# ----------------------------------------------------------------------
# The person against the AI, five each (2026-11-24)
# ----------------------------------------------------------------------


def test_a_person_records_up_to_five_once_blind_and_nothing_is_sent(tmp_path):

    selection = service(tmp_path, found=8)
    round_ = selection.create_round(["health"])

    recorded = selection.record_person_selection(
        round_["id"],
        urls(2, 4) + ["https://news.example/2"],
        notes={"https://news.example/3": "  a cure that reaches people  ", "https://news.example/7": "not chosen"},
    )

    assert recorded["urls"] == urls(2, 4)
    assert recorded["blind"] is True and recorded["limit"] == COMPARED
    assert recorded["shown"] == urls(1, 8)
    assert recorded["notes"] == {"https://news.example/3": "a cure that reaches people"}

    on_disk = json.loads((tmp_path / f"{round_['id']}.json").read_text(encoding="utf-8"))
    assert on_disk["personSelection"]["urls"] == urls(2, 4)
    assert on_disk["queued"] is None and on_disk["comparison"] is None

    with pytest.raises(InvalidSelection, match="already recorded"):
        selection.record_person_selection(round_["id"], urls(5, 5))


@pytest.mark.parametrize("chosen, message", [
    ([], "at least one"),
    ([f"https://news.example/{i}" for i in range(1, COMPARED + 2)], f"At most {COMPARED}"),
    (["https://elsewhere.example/a"], "Not a candidate"),
])
def test_a_choice_that_breaks_a_rule_is_not_recorded(tmp_path, chosen, message):

    selection = service(tmp_path, found=8)
    round_ = selection.create_round(["health"])

    with pytest.raises(InvalidSelection, match=message):
        selection.record_person_selection(round_["id"], chosen)

    assert selection.get(round_["id"]).get("personSelection") is None


def test_a_choice_made_after_the_ais_proposal_is_not_blind(tmp_path):

    selection = service(tmp_path, selector=FakeSelector(picks=urls(1, 2)))
    round_ = selection.create_round(["health"])
    selection.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    assert selection.record_person_selection(round_["id"], urls(1, 1))["blind"] is False


def test_a_failed_ai_selection_showed_nothing_so_the_choice_is_still_blind(tmp_path):

    selection = service(tmp_path, selector=FakeSelector(error=LLMUnavailableError("down")))
    round_ = selection.create_round(["health"])
    selection.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    assert selection.record_person_selection(round_["id"], urls(1, 1))["blind"] is True


def test_nothing_is_recorded_or_sent_while_the_ai_reads_the_round(tmp_path, monkeypatch):
    """
    The 2026-11-24 bug: Analyse stayed enabled while the AI scored, and
    the AI's picks then landed on a round saved as selectedBy "user".
    """

    selection = service(tmp_path)
    round_ = selection.create_round(["health"])
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    selection.start_ai_selection(round_["id"])

    with pytest.raises(SelectionBusy):
        selection.queue(round_["id"], urls(1, 1), Jobs())

    with pytest.raises(SelectionBusy):
        selection.record_person_selection(round_["id"], urls(1, 1))

    after = selection.get(round_["id"])
    assert after["queued"] is None and after.get("personSelection") is None

    # Another round is not held up by this one's AI.
    other = selection.create_round(["health"])
    assert selection.queue(other["id"], urls(1, 1), Jobs())["selectedBy"] == "user"


def test_the_ai_is_not_started_on_a_round_being_sent(tmp_path, monkeypatch):

    selection = service(tmp_path)
    round_ = selection.create_round(["health"])
    refused = []

    def start_job(url):
        try:
            selection.start_ai_selection(round_["id"])
        except SelectionBusy:
            refused.append(url)
        return "job-1", False

    selection.queue(round_["id"], urls(1, 1), start_job)

    assert refused == urls(1, 1)
    assert selection.get(round_["id"])["aiSelection"] is None

    # Once sent, the AI can read it (the blind-ai protocol).
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    assert selection.start_ai_selection(round_["id"])["status"] == "running"


def test_against_a_recorded_choice_the_ai_is_asked_for_five_and_the_two_are_compared(tmp_path, monkeypatch):

    ai = FakeSelector(picks=urls(3, 9))
    selection = service(tmp_path, found=10, selector=ai)
    round_ = selection.create_round(["health"])

    selection.record_person_selection(round_["id"], urls(1, 4))

    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    started = selection.start_ai_selection(round_["id"], limit=20)
    assert started["limit"] == COMPARED

    selection.run_ai_selection(round_["id"], limit=started["limit"], min_score=6.0)
    assert ai.calls[0][2] == COMPARED

    comparison = selection.get(round_["id"])["comparison"]

    # The AI picked 3-7, the person 1-4: 3 and 4 in common.
    assert comparison["both"] == urls(3, 4)
    assert comparison["personOnly"] == urls(1, 2)
    assert comparison["aiOnly"] == urls(5, 7)
    assert (comparison["precision"], comparison["recall"]) == (0.4, 0.5)
    assert comparison["jaccard"] == round(2 / 7, 4)
    assert comparison["blind"] is True and comparison["over"] == 10
    assert comparison["aiScores"] == {url: (8.0 if url in urls(3, 4) else None) for url in urls(1, 4)}
    assert comparison["kappa"] == kappa(urls(1, 10), set(urls(1, 4)), set(urls(3, 7)))

    listed = {summary["id"]: summary for summary in selection.list()}[round_["id"]]
    assert (listed["personPicks"], listed["personBlind"], listed["bothPicked"]) == (4, True, 2)


def test_the_list_is_not_widened_once_a_choice_is_recorded(tmp_path):

    selection = service(tmp_path, found=LISTED + 5)
    round_ = selection.create_round(["society"])
    selection.record_person_selection(round_["id"], urls(1, 1))

    with pytest.raises(InvalidSelection, match="same one"):
        selection.show_more(round_["id"])


def test_kappa_is_cohens_for_two_raters_choosing_some_of_a_list():

    items = [str(i) for i in range(10)]

    assert kappa(items, {"0", "1"}, {"0", "1"}) == 1.0
    # Disjoint picks of 5 in 10: everything disagrees, below chance.
    assert kappa(items, set(items[:5]), set(items[5:])) == -1.0
    # Chance agreement is 1 when neither chose anything: undefined.
    assert kappa(items, set(), set()) is None
    assert kappa([], {"a"}, {"a"}) is None


class FakePhotos:

    def __init__(self):
        self.asked = []

    def keep(self, folder, candidates):
        self.asked.append([candidate["url"] for candidate in candidates])
        return {candidate["url"]: {"image": candidate["image"], "file": f"{i:016x}.jpg"} for i, candidate in enumerate(candidates)}


def test_the_photos_of_both_sides_picks_are_kept_once_each(tmp_path, monkeypatch):

    photos = FakePhotos()
    selection = SelectionService(
        ingestion=FakeIngestion(6),
        selector=FakeSelector(picks=urls(2, 3)),
        rounds=SelectionRounds(tmp_path),
        photos=photos,
    )

    round_ = selection.create_round(["health"])
    for candidate in round_["candidates"]:
        if candidate["url"] != "https://news.example/1":
            candidate["image"] = candidate["url"].replace("news.example", "cdn.example") + ".jpg"

    selection.record_person_selection(round_["id"], urls(1, 2))

    # The person's 1 has no picture, 2 has: only 2 is fetched.
    assert photos.asked == [urls(2, 2)]

    selection.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    # The AI's 2 and 3: 2 is already kept.
    assert photos.asked == [urls(2, 2), urls(3, 3)]

    on_disk = json.loads((tmp_path / f"{round_['id']}.json").read_text(encoding="utf-8"))
    assert sorted(on_disk["photos"]) == urls(2, 3)



# ----------------------------------------------------------------------
# Why each pick (2026-11-24, reasons.py)
# ----------------------------------------------------------------------


def test_each_picks_reasons_are_kept_in_the_offered_order_and_only_for_picks(tmp_path):

    selection = service(tmp_path, found=6)
    round_ = selection.create_round(["health"])

    recorded = selection.record_person_selection(
        round_["id"],
        urls(1, 2),
        reasons={
            "https://news.example/1": ["trending", "positive", "trending"],
            "https://news.example/2": [],
            "https://news.example/5": ["diversity"],
        },
    )

    assert recorded["reasons"] == {"https://news.example/1": ["positive", "trending"]}


def test_a_reason_nobody_defined_is_refused_and_nothing_is_recorded(tmp_path):

    selection = service(tmp_path)
    round_ = selection.create_round(["health"])

    with pytest.raises(InvalidSelection, match="Not a reason"):
        selection.record_person_selection(round_["id"], urls(1, 1), reasons={"https://news.example/1": ["vibes"]})

    assert selection.get(round_["id"]).get("personSelection") is None


def test_the_reasons_are_the_rounds_editions():

    from src.services.selection.reasons import UnknownReason, cleaned, reasons_for

    assert [reason.id for reason in reasons_for("devastating")][:2] == ["harm", "accountability"]
    assert cleaned({"u": ["harm", "trending"]}, ["u"], "devastating") == {"u": ["harm", "trending"]}

    with pytest.raises(UnknownReason):
        cleaned({"u": ["positive"]}, ["u"], "devastating")


def test_the_comparison_says_for_which_reasons_the_ai_chose_the_same(tmp_path):

    selection = service(tmp_path, found=6, selector=FakeSelector(picks=urls(1, 1)))
    round_ = selection.create_round(["health"])

    selection.record_person_selection(round_["id"], urls(1, 2), reasons={
        "https://news.example/1": ["positive", "trending"],
        "https://news.example/2": ["positive", "diversity"],
    })
    selection.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    assert selection.get(round_["id"])["comparison"]["reasons"] == {
        "positive": {"picks": 2, "aiAlso": 1},
        "trending": {"picks": 1, "aiAlso": 1},
        "diversity": {"picks": 1, "aiAlso": 0},
    }


def test_what_is_sent_keeps_why_too(tmp_path):

    selection = service(tmp_path)
    round_ = selection.create_round(["health"])

    queued = selection.queue(
        round_["id"], urls(1, 1), Jobs(),
        notes={"https://news.example/1": " first of its kind "},
        reasons={"https://news.example/1": ["original"]},
    )

    assert queued["notes"] == {"https://news.example/1": "first of its kind"}
    assert queued["reasons"] == {"https://news.example/1": ["original"]}

    other = selection.create_round(["health"])
    with pytest.raises(InvalidSelection, match="Not a reason"):
        selection.queue(other["id"], urls(1, 1), Jobs(), reasons={"https://news.example/1": ["nope"]})
    assert selection.get(other["id"])["queued"] is None

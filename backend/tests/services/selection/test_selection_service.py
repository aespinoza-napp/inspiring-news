import json

import pytest

from src.services.llms import LLMUnavailableError
from src.services.selection.ai_selector import AISelection, Scored
from src.services.selection.rounds import SelectionRounds
from src.services.selection.selection_service import (
    LISTED,
    MAX_LISTED,
    MAX_SELECTED,
    InvalidSelection,
    RoundNotFound,
    SelectionBusy,
    SelectionService,
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

    def discover_candidates(self, groups, source_ids=None, per_source=3):
        self.calls.append((groups, source_ids, per_source))
        return {
            "startedAt": "2026-10-05T10:00:00+00:00",
            "groups": groups,
            "topics": ["climate"],
            "perSource": per_source,
            "sources": [],
            "candidates": candidates(self.found),
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

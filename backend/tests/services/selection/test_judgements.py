"""
Every judgement made on /discover, kept in the lake as one dataset
(src/services/selection/judgements.py): the log as it is written, the
dataset built from it alone, the rounds from before it, and that a log
nobody attached writes nothing.
"""

import csv
import io
import json

from src.services.selection.judgements import (
    CSV_COLUMNS,
    DATASET,
    DATASET_CSV,
    EVENTS,
    SelectionJudgements,
    build_dataset,
    events_from_rounds,
)
from src.services.selection.rounds import SelectionRounds
from src.services.selection.selection_service import SelectionService

from tests.services.selection.test_selection_service import FakeIngestion, FakeSelector, Jobs


def service(tmp_path, found=5, selector=None):

    log = SelectionJudgements(tmp_path / "judgements")

    selection = SelectionService(
        ingestion=FakeIngestion(found),
        selector=selector or FakeSelector(),
        rounds=SelectionRounds(tmp_path / "rounds"),
        judgements=log,
    )

    return selection, log


def lines(tmp_path) -> list[dict]:

    text = (tmp_path / "judgements" / EVENTS).read_text(encoding="utf-8")

    return [json.loads(line) for line in text.splitlines()]


def labels(rows) -> dict[str, str]:

    return {row["url"]: row["label"] for row in rows}


URL = "https://news.example/{}".format


def test_each_judgement_is_a_line_after_the_list_it_was_made_from_and_the_dataset_follows(tmp_path):

    selection, log = service(tmp_path)
    round_ = selection.create_round(["health"])

    selection.reject(round_["id"], URL(1), reasons=["politics"], note="a campaign", site=True)
    selection.queue(round_["id"], [URL(2), URL(4)], Jobs(), notes={URL(2): "for the carousel"}, reasons={URL(2): ["positive", "audience"]})

    logged = lines(tmp_path)

    # The list once, before the first judgement: it did not grow after.
    assert [line["kind"] for line in logged] == ["shown", "not_for_us", "sent"]
    assert [row["position"] for row in logged[0]["candidates"]] == [1, 2, 3, 4, 5]
    assert all(line["round"]["id"] == round_["id"] and line["edition"] == "positive" for line in logged)
    assert logged[1]["reasons"] == ["politics"] and logged[1]["site"] is True and logged[1]["by"] == "person"
    assert logged[2]["picks"][0] == {"url": URL(2), "title": "Story 2", "reasons": ["positive", "audience"], "note": "for the carousel"}
    assert logged[2]["selectedBy"] == "user"

    rows = log.dataset()

    assert labels(rows) == {URL(1): "not_for_us", URL(2): "chosen", URL(3): "not_chosen", URL(4): "chosen", URL(5): "not_chosen"}

    chosen = next(row for row in rows if row["url"] == URL(2))
    assert chosen["chosenBy"] == ["sent"] and chosen["reasons"] == ["positive", "audience"] and chosen["note"] == "for the carousel"
    assert chosen["shown"] == 5 and chosen["position"] == 2 and chosen["groups"] == ["health"]

    rejected = next(row for row in rows if row["url"] == URL(1))
    assert rejected["reasons"] == ["politics"] and rejected["blockSite"] is True

    # Both files are rebuilt from the log after each judgement.
    folder = tmp_path / "judgements"
    assert [json.loads(line) for line in (folder / DATASET).read_text(encoding="utf-8").splitlines()] == rows

    table = list(csv.DictReader(io.StringIO((folder / DATASET_CSV).read_text(encoding="utf-8"))))
    assert list(table[0]) == list(CSV_COLUMNS) and len(table) == 5
    assert next(row for row in table if row["url"] == URL(2))["reasons"] == "positive|audience"


def test_taking_a_mark_back_is_a_line_of_its_own_and_the_log_is_never_rewritten(tmp_path):

    selection, log = service(tmp_path)
    round_ = selection.create_round(["health"])

    selection.reject(round_["id"], URL(1), reasons=["politics"])
    selection.reject(round_["id"], URL(2), reasons=["old"], site=True)
    before = (tmp_path / "judgements" / EVENTS).read_text(encoding="utf-8")

    selection.reject(round_["id"], URL(1), undo=True)
    assert selection.forget("positive", host="news.example")
    assert selection.forget("positive", url=URL(2))

    after = (tmp_path / "judgements" / EVENTS).read_text(encoding="utf-8")

    assert after.startswith(before)
    assert [line["kind"] for line in lines(tmp_path)] == ["shown", "not_for_us", "not_for_us", "undone", "unblocked", "forgotten"]

    # Nothing is marked any more, but the round was judged: its rows stay.
    assert set(labels(log.dataset()).values()) == {"not_chosen"}


def test_a_list_that_grew_is_logged_again_and_the_dataset_reads_the_longer_one(tmp_path):

    selection, log = service(tmp_path, found=25)
    round_ = selection.create_round(["health"])

    selection.reject(round_["id"], URL(1), reasons=["politics"])
    selection.show_more(round_["id"])
    selection.queue(round_["id"], [URL(22)], Jobs())

    logged = lines(tmp_path)

    assert [line["kind"] for line in logged] == ["shown", "not_for_us", "shown", "sent"]
    assert [len(line["candidates"]) for line in logged if line["kind"] == "shown"] == [20, 25]

    rows = log.dataset()
    assert len(rows) == 25 and labels(rows)[URL(22)] == "chosen" and labels(rows)[URL(1)] == "not_for_us"


def test_the_ais_scores_and_the_persons_recorded_five_land_on_the_same_rows(tmp_path):

    selection, log = service(tmp_path, selector=FakeSelector(picks=[URL(1), URL(3)]))
    round_ = selection.create_round(["health"])

    selection.record_person_selection(round_["id"], [URL(1), URL(2)], reasons={URL(2): ["trending"]})
    selection.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    logged = lines(tmp_path)
    assert [line["kind"] for line in logged] == ["shown", "recorded", "ai"]
    assert logged[1]["blind"] is True and logged[2]["by"] == "ai" and logged[2]["model"] == "fake-model"

    rows = {row["url"]: row for row in log.dataset()}

    assert rows[URL(1)]["label"] == "chosen" and rows[URL(1)]["chosenBy"] == ["recorded"]
    assert rows[URL(1)]["ai"] == {"score": 8.0, "reason": "a solution", "picked": True, "model": "fake-model"}
    assert rows[URL(2)]["ai"]["picked"] is False and rows[URL(2)]["reasons"] == ["trending"]
    assert rows[URL(3)]["label"] == "not_chosen" and rows[URL(3)]["ai"]["picked"] is True


def test_a_round_only_the_ai_read_is_logged_but_is_not_in_the_dataset(tmp_path):

    selection, log = service(tmp_path, selector=FakeSelector(picks=[URL(1)]))
    round_ = selection.create_round(["health"])

    selection.run_ai_selection(round_["id"], limit=5, min_score=6.0)

    assert [line["kind"] for line in lines(tmp_path)] == ["shown", "ai"]
    assert log.dataset() == []


def test_the_rounds_from_before_the_log_are_backfilled_once_with_their_own_times(tmp_path):

    # A round judged the old way: the log was not attached yet.
    selection, _ = service(tmp_path)
    selection.judgements = SelectionJudgements()
    round_ = selection.create_round(["health"])
    untouched = selection.create_round(["science"])
    selection.reject(round_["id"], URL(5), reasons=["old"])
    queued = selection.queue(round_["id"], [URL(2)], Jobs(), reasons={URL(2): ["solution"]})

    log = SelectionJudgements(tmp_path / "judgements")
    rounds = selection.rounds.list(limit=100)

    assert log.backfill(rounds) == 3
    assert log.backfill(rounds) == 0

    logged = lines(tmp_path)
    # The list first; the two judgements were made within one second here.
    assert logged[0]["kind"] == "shown" and sorted(line["kind"] for line in logged[1:]) == ["not_for_us", "sent"]
    assert all(line["backfilled"] and line["round"]["id"] == round_["id"] for line in logged)
    assert next(line for line in logged if line["kind"] == "sent")["at"] == queued["at"]
    assert untouched["id"] not in {line["round"]["id"] for line in logged}

    assert labels(log.dataset()) == {URL(1): "not_chosen", URL(2): "chosen", URL(3): "not_chosen", URL(4): "not_chosen", URL(5): "not_for_us"}

    # Judged from then on, the new lines follow the backfilled ones.
    selection.judgements = log
    selection.reject(round_["id"], URL(5), undo=True)
    assert [line["kind"] for line in lines(tmp_path)][-1] == "undone"
    assert labels(log.dataset())[URL(5)] == "not_chosen"


def test_the_dataset_is_the_same_from_the_log_and_from_the_rounds(tmp_path):

    selection, log = service(tmp_path)
    round_ = selection.create_round(["health"])
    selection.reject(round_["id"], URL(1), reasons=["politics"])
    selection.queue(round_["id"], [URL(3)], Jobs(), reasons={URL(3): ["evidence"]})

    replayed = build_dataset(events_from_rounds(selection.rounds.list(limit=100)))

    def comparable(rows):
        return [{k: v for k, v in row.items() if k != "judgedAt"} for row in rows]

    assert comparable(replayed) == comparable(log.dataset())


def test_a_log_nobody_attached_writes_nothing_and_a_broken_folder_breaks_no_click(tmp_path):

    selection, _ = service(tmp_path)
    selection.judgements = SelectionJudgements()
    round_ = selection.create_round(["health"])
    selection.queue(round_["id"], [URL(1)], Jobs())

    assert selection.judgements.events() == [] and not (tmp_path / "judgements").exists()

    # A file where the folder should be: the judgement is lost, the send is not.
    (tmp_path / "blocked").write_text("not a folder", encoding="utf-8")
    selection.judgements = SelectionJudgements(tmp_path / "blocked")
    second = selection.create_round(["health"])

    assert selection.queue(second["id"], [URL(2)], Jobs())["urls"] == [URL(2)]


def test_the_summary_counts_kinds_and_labels_and_lists_lines_without_their_lists(tmp_path):

    selection, log = service(tmp_path)
    round_ = selection.create_round(["health"])
    selection.reject(round_["id"], URL(1), reasons=["politics"])
    selection.queue(round_["id"], [URL(2)], Jobs())

    summary = log.summary("positive")

    assert summary["events"] == 3 and summary["rounds"] == 1 and summary["rows"] == 5
    assert summary["kinds"]["shown"] == 1 and summary["kinds"]["sent"] == 1 and summary["kinds"]["not_for_us"] == 1
    assert summary["labels"] == {"chosen": 1, "not_for_us": 1, "not_chosen": 3}
    assert [line["kind"] for line in summary["latest"]] == ["sent", "not_for_us", "shown"]
    assert summary["latest"][-1]["candidates"] == 5

    assert log.summary("devastating")["events"] == 0

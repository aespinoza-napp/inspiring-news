"""
The iteration loop (src/evaluation/iterate.py): a campaign's rule decides
each try, a try is pre-registered before it runs, and nothing but the
campaign's own train claims can be scored.

Runs are fixture directories written with support.make_record, as the
harness would leave them; git is stubbed so a test does not depend on the
state of the checkout it runs in.
"""

import json

import pytest

from src.evaluation import iterate
from src.evaluation.iterate import Pairing, decide

from tests.evaluation.support import custom_row, make_record, write_run

TARGET = {"medianSeconds": 20.0, "p90Seconds": 30.0}

ROWS = 10


@pytest.fixture(autouse=True)
def stub_git(monkeypatch):

    state = {"head": "c" * 40, "dirty": [], "changed": []}

    monkeypatch.setattr(iterate, "head_commit", lambda: state["head"])
    monkeypatch.setattr(iterate, "dirty_code", lambda: list(state["dirty"]))
    monkeypatch.setattr(iterate, "changed_paths", lambda since: list(state["changed"]))

    return state


# ----------------------------------------------------------------------
# Fixture runs
# ----------------------------------------------------------------------


def records(right: int, *, total: float = 10.0, retrieval: float = 0.0, model: str = "stub-model",
            rows: int = ROWS, wrong_verdict: str = "FALSE") -> list[dict]:
    """`rows` TRUE claims, the first `right` answered TRUE, the rest `wrong_verdict`."""

    made = []

    for index in range(rows):

        row = custom_row(f"fact{index:03d}", f"Claim number {index} about energy.", label="TRUE", split="train")

        record = make_record(row, "TRUE" if index < right else wrong_verdict, model=model, total=total)

        record["latency"] = {**(record.get("latency") or {}), "total": total, "retrieval": retrieval}

        made.append(record)

    return made


def run_dir(tmp_path, name: str, recs: list[dict], **manifest) -> str:

    directory = write_run(tmp_path / "runs" / name, recs, model=manifest.pop("model", "stub-model"),
                          key=manifest.pop("key", name[:12].ljust(12, "x")), stem="manual-train")

    path = directory / "run.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["dataset"]["rows"] = ROWS
    data.update(manifest)
    path.write_text(json.dumps(data), encoding="utf-8")

    return str(directory)


@pytest.fixture
def evidence_run(tmp_path):

    directory = run_dir(
        tmp_path, "evidence", records(5, total=30.0, retrieval=8.0), key="evidencekey1", mode="full",
        thresholds={"query_kinds": ["anchor", "proposition", "refutation"], "max_evidence_per_claim": 5,
                    "evidence_fetch_candidates": 8, "evidence_prerank": "embedding",
                    "fetch_evidence_pages": True, "claim_restatement": None,
                    "second_look_enabled": False, "claim_deadline_seconds": 0},
        sessions=[{"settings": {"LLM_MAX_CONCURRENCY": 1, "LLM_TIMEOUT": 180.0}}],
    )

    (tmp_path / "runs" / "evidence" / "evidence.jsonl").write_text("", encoding="utf-8")

    return directory


@pytest.fixture
def campaign(tmp_path, evidence_run):

    return iterate.init_campaign("c1", evidence_run, screen=4, tries=3, root=tmp_path / "campaigns")


def replay_of(campaign, entry, recs, tmp_path, name):

    return run_dir(
        tmp_path, name, recs, mode="replay", replayOf=f"some/where/{campaign.config['evidence']['key']}",
        label=entry["label"], thresholdsHash=entry["thresholdsHash"], model=entry["model"],
    )


def with_baseline(campaign, tmp_path):

    entry = iterate.propose(campaign, kind="baseline", hypothesis="the defaults", prediction="-")

    # The baseline replays at 5 s of its own; retrieval took 8 s in the evidence run.
    directory = replay_of(campaign, entry, records(5, total=5.0, retrieval=0.0), tmp_path, "baseline")

    return iterate.score(campaign, 0, directory, reports_root=tmp_path / "reports")


def thresholds_file(tmp_path, values: dict) -> str:

    path = tmp_path / f"t{abs(hash(json.dumps(values, sort_keys=True)))}.json"
    path.write_text(json.dumps(values), encoding="utf-8")

    return str(path)


# ----------------------------------------------------------------------
# The rule
# ----------------------------------------------------------------------


def pairing(net=0, low=-0.1, cw=(10, 10), set_apart=(0, 0), seconds=((40, 60), (40, 60)), paired=69):

    return Pairing(
        paired=paired, net=net,
        accuracy={"a": 0.5, "b": 0.5 + net / paired, "difference": net / paired, "low": low, "high": 0.2},
        confidently_wrong=cw, set_apart=set_apart,
        seconds=tuple({"median": m, "p90": p, "n": paired} for m, p in seconds),
    )


def test_an_interval_above_zero_with_no_more_confidently_wrong_is_kept():

    decision, _, quality, _ = decide([pairing(net=8, low=0.02, cw=(20, 18))], target=TARGET, screening=False)

    assert (decision, quality) == ("keep", "better")


def test_a_gain_that_is_confidently_wrong_more_often_is_not_better():

    decision, _, quality, _ = decide([pairing(net=8, low=0.02, cw=(20, 23))], target=TARGET, screening=False)

    assert (decision, quality) == ("reject", "worse")


def test_no_detectable_difference_and_no_faster_is_rejected():

    decision, _, quality, _ = decide([pairing(net=1)], target=TARGET, screening=False)

    assert (decision, quality) == ("reject", "same")


def test_the_same_quality_meeting_the_time_target_is_kept_for_speed():

    decision, reasons, quality, pace = decide(
        [pairing(net=-1, seconds=((48, 73), (16, 24)))], target=TARGET, screening=False,
    )

    assert (decision, quality, pace["meetsTarget"]) == ("keep", "same", True)
    assert "kept for speed" in reasons[-1]


def test_a_speed_gain_never_buys_two_lost_claims():

    decision, _, quality, _ = decide([pairing(net=-2, seconds=((48, 73), (14, 20)))], target=TARGET, screening=False)

    assert (decision, quality) == ("reject", "worse")


def test_giving_up_on_claims_is_invalid_whatever_the_accuracy():

    decision, reasons, _, _ = decide([pairing(net=10, low=0.05, set_apart=(1, 4))], target=TARGET, screening=False)

    assert decision == "invalid"
    assert "sets apart 4" in reasons[0]


def test_the_screen_stops_three_lost_claims_and_lets_the_rest_through():

    assert decide([pairing(net=-3, paired=20)], target=TARGET, screening=True)[0] == "screened-out"
    assert decide([pairing(net=-2, paired=20)], target=TARGET, screening=True)[0] == "continue"


def test_the_screen_stops_a_much_slower_try_that_gains_nothing():

    slow = pairing(net=0, paired=20, seconds=((40, 60), (70, 90)))

    assert decide([slow], target=TARGET, screening=True)[0] == "screened-out"


def test_a_searched_try_must_beat_the_gap_between_its_two_baselines():

    both = [pairing(net=4, low=0.01, cw=(20, 18)), pairing(net=5, low=0.01, cw=(20, 18))]

    assert decide(both, target=TARGET, screening=False, noise=6)[2] == "same"
    assert decide(both, target=TARGET, screening=False, noise=3)[2] == "better"


# ----------------------------------------------------------------------
# What a replay can measure
# ----------------------------------------------------------------------


EVIDENCE_THRESHOLDS = {
    "query_kinds": ["anchor", "proposition", "refutation"], "max_evidence_per_claim": 5,
    "claim_restatement": None, "second_look_enabled": False,
}


def test_a_search_side_threshold_cannot_be_replayed():

    changed = iterate.search_side_changes(EVIDENCE_THRESHOLDS, {**EVIDENCE_THRESHOLDS, "query_kinds": ["anchor"]})

    assert changed == ["query_kinds"]


def test_a_field_the_evidence_run_predates_is_read_as_its_old_behaviour():

    same = {**EVIDENCE_THRESHOLDS, "claim_restatement": "off"}
    restated = {**EVIDENCE_THRESHOLDS, "claim_restatement": "standalone"}

    assert iterate.search_side_changes(EVIDENCE_THRESHOLDS, same) == []
    assert iterate.search_side_changes(EVIDENCE_THRESHOLDS, restated) == ["claim_restatement"]


def test_fewer_sources_replay_and_more_than_were_fetched_do_not():

    assert iterate.search_side_changes(EVIDENCE_THRESHOLDS, {**EVIDENCE_THRESHOLDS, "max_evidence_per_claim": 3}) == []
    assert iterate.search_side_changes(EVIDENCE_THRESHOLDS, {**EVIDENCE_THRESHOLDS, "max_evidence_per_claim": 8})


def test_a_replays_seconds_add_back_what_retrieval_took_in_the_run_replayed():

    replayed = records(1, total=12.0, retrieval=0.5, rows=1)
    original = {r["id"]: r for r in records(1, total=40.0, retrieval=8.0, rows=1)}

    assert iterate.claim_seconds(replayed, original) == {"fact000": pytest.approx(19.5)}
    assert iterate.claim_seconds(replayed, None) == {"fact000": 12.0}


# ----------------------------------------------------------------------
# A campaign, end to end
# ----------------------------------------------------------------------


def test_a_campaign_refuses_anything_but_a_searched_train_run(tmp_path):

    test_half = run_dir(tmp_path, "testhalf", records(5), mode="full")
    data = json.loads((tmp_path / "runs" / "testhalf" / "run.json").read_text())
    data["dataset"]["stem"] = "manual-test"
    (tmp_path / "runs" / "testhalf" / "run.json").write_text(json.dumps(data))
    (tmp_path / "runs" / "testhalf" / "evidence.jsonl").write_text("")

    with pytest.raises(SystemExit, match="train half only"):
        iterate.init_campaign("c2", test_half, root=tmp_path / "campaigns")


def test_the_baseline_comes_first_and_is_registered(campaign, tmp_path):

    with pytest.raises(SystemExit, match="baseline first"):
        iterate.propose(campaign, kind="thresholds", hypothesis="h", prediction="p")

    decision = with_baseline(campaign, tmp_path)

    assert decision["decision"] == "registered"
    assert campaign.config["baseline"]["key"]
    # 5 s replayed plus the 8 s retrieval took in the evidence run.
    assert decision["seconds"]["median"] == 13.0


def test_a_try_is_screened_then_resumed_then_decided(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    entry = iterate.propose(
        campaign, kind="thresholds", hypothesis="the gate is too strict", prediction="more TRUE",
        thresholds_path=thresholds_file(tmp_path, {"evidence_min_pertinence": 0.2}),
    )

    assert entry["mode"] == "replay"
    assert entry["label"] == "iterate-c1-01"

    screen = replay_of(campaign, entry, records(4, rows=4), tmp_path, "try1")

    assert iterate.score(campaign, 1, screen, reports_root=tmp_path / "reports")["decision"] == "continue"

    # The same run, resumed over every claim.
    full = replay_of(campaign, entry, records(10, total=5.0), tmp_path, "try1")

    decision = iterate.score(campaign, 1, full, reports_root=tmp_path / "reports")

    assert decision["decision"] == "keep"
    assert decision["quality"] == "better"
    assert len(decision["changed"]["gained"]) == 5

    state = iterate.status(campaign, runs_root=tmp_path / "runs")

    assert state["best"] == 1
    assert [row["decision"] for row in state["rows"]] == ["registered", "keep"]


def test_a_run_that_is_not_the_proposed_try_is_refused(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    entry = iterate.propose(campaign, kind="model", hypothesis="a larger reader", prediction="fewer FALSE", model="granite3.3:8b")

    wrong_label = run_dir(tmp_path, "other", records(6), mode="replay", replayOf="evidencekey1",
                          label="something-else", model="granite3.3:8b", thresholdsHash=entry["thresholdsHash"])

    with pytest.raises(SystemExit, match="labelled"):
        iterate.score(campaign, 1, wrong_label, reports_root=tmp_path / "reports")

    wrong_model = replay_of(campaign, {**entry, "model": "llama3.2:3b"}, records(6), tmp_path, "othermodel")

    with pytest.raises(SystemExit, match="run with llama3.2:3b"):
        iterate.score(campaign, 1, wrong_model, reports_root=tmp_path / "reports")


def test_a_pending_try_blocks_the_next_and_a_repeat_is_refused(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    # The defaults again: try 0 measured them, and the model is deterministic on fixed evidence.
    with pytest.raises(SystemExit, match="try 0 already ran"):
        iterate.propose(campaign, kind="thresholds", hypothesis="h", prediction="p")

    path = thresholds_file(tmp_path, {"verifier_excerpt_chars": 1100})

    iterate.propose(campaign, kind="thresholds", hypothesis="h", prediction="p", thresholds_path=path)

    with pytest.raises(SystemExit, match="not decided"):
        iterate.propose(campaign, kind="thresholds", hypothesis="h2", prediction="p")

    # Abandoned, it measured nothing: it may be proposed again.
    iterate.abandon(campaign, 1, "inference went down")

    assert iterate.propose(campaign, kind="thresholds", hypothesis="h", prediction="p", thresholds_path=path)["try"] == 2


def test_editing_the_rule_ends_the_campaigns_decisions(campaign, tmp_path):

    (campaign.directory / iterate.RULE).write_text("a kinder rule", encoding="utf-8")

    with pytest.raises(SystemExit, match="changed after the campaign started"):
        iterate.propose(campaign, kind="baseline", hypothesis="h", prediction="p")


def test_a_code_try_needs_its_change_committed(campaign, tmp_path, stub_git):

    with_baseline(campaign, tmp_path)

    stub_git["dirty"] = ["backend/src/services/fact_checker/verification/per_source.py"]

    with pytest.raises(SystemExit, match="commit the change first"):
        iterate.propose(campaign, kind="prompt", hypothesis="h", prediction="p")


def test_search_side_code_or_thresholds_make_a_searched_try(campaign, tmp_path, stub_git):

    with_baseline(campaign, tmp_path)

    entry = iterate.propose(
        campaign, kind="thresholds", hypothesis="two queries are enough", prediction="faster",
        thresholds_path=thresholds_file(tmp_path, {"query_kinds": ["anchor", "proposition"]}),
    )

    assert entry["mode"] == "searched"
    assert "query_kinds" in entry["searchSide"]

    lines = iterate.commands(campaign, entry)

    assert "searched-baseline-a" in lines[0] and "searched-baseline-b" in lines[1]
    assert not any("--replay" in line for line in lines)

    searched = run_dir(tmp_path, "searched", records(6), mode="full", label=entry["label"],
                       thresholdsHash=entry["thresholdsHash"])

    with pytest.raises(SystemExit, match="both searched baselines"):
        iterate.score(campaign, 1, searched, reports_root=tmp_path / "reports")

    iterate.abandon(campaign, 1, "test")

    stub_git["changed"] = ["backend/src/services/fact_checker/retrieval/query_builder.py"]
    stub_git["head"] = "d" * 40

    entry = iterate.propose(campaign, kind="search", hypothesis="a better anchor", prediction="recall up")

    assert entry["mode"] == "searched"


def test_the_budget_is_spent_and_close_writes_the_summary(campaign, tmp_path, stub_git):

    with_baseline(campaign, tmp_path)

    for number in range(1, 4):
        stub_git["head"] = str(number) * 40
        iterate.propose(campaign, kind="code", hypothesis=f"h{number}", prediction="p")
        iterate.abandon(campaign, number, "test")

    with pytest.raises(SystemExit, match="spent"):
        iterate.propose(campaign, kind="code", hypothesis="one more", prediction="p")

    assert "tries are spent" in iterate.status(campaign, runs_root=tmp_path / "runs")["stop"]

    summary = iterate.close(campaign, "budget").read_text(encoding="utf-8")

    assert "Nothing: no try was kept." in summary
    assert iterate.load_campaign(campaign.directory).config["status"] == "closed"
    assert iterate.active_campaigns(tmp_path / "campaigns") == []


# ----------------------------------------------------------------------
# Self-hosted against hosted
# ----------------------------------------------------------------------


def test_a_hosted_try_points_its_verifier_at_the_provider_and_never_prints_the_key(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    entry = iterate.propose(campaign, kind="model", hypothesis="a larger reader, hosted", prediction="faster",
                            model="openai/gpt-oss-120b", provider="groq")

    command = iterate.commands(campaign, entry)[-1]

    assert "LLM_BASE_URL=https://api.groq.com/openai/v1" in command
    assert "LLM_API_KEY" not in command
    assert entry["provider"] == "groq"


def test_a_hosted_provider_is_only_a_model_try(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    with pytest.raises(SystemExit, match="--kind model"):
        iterate.propose(campaign, kind="thresholds", hypothesis="h", prediction="p", provider="groq",
                        thresholds_path=thresholds_file(tmp_path, {"verifier_excerpt_chars": 900}))


def test_a_hosted_try_whose_run_used_the_local_model_server_is_refused(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    entry = iterate.propose(campaign, kind="model", hypothesis="h", prediction="p",
                            model="openai/gpt-oss-120b", provider="groq")

    ran_locally = replay_of(campaign, entry, records(6), tmp_path, "groqtry")  # provider localhost:11434

    with pytest.raises(SystemExit, match="not api.groq.com"):
        iterate.score(campaign, 1, ran_locally, reports_root=tmp_path / "reports")


def test_the_benchmark_puts_every_measured_try_side_by_side(campaign, tmp_path):

    with_baseline(campaign, tmp_path)

    entry = iterate.propose(campaign, kind="model", hypothesis="hosted", prediction="p",
                            model="openai/gpt-oss-120b", provider="groq")

    directory = run_dir(
        tmp_path, "hosted", records(9, total=4.0), mode="replay", replayOf="x/evidencekey1",
        label=entry["label"], thresholdsHash=entry["thresholdsHash"], model=entry["model"],
    )
    run_json = tmp_path / "runs" / "hosted" / "run.json"
    data = json.loads(run_json.read_text())
    data["provider"] = "api.groq.com"
    run_json.write_text(json.dumps(data))

    iterate.score(campaign, 1, directory, reports_root=tmp_path / "reports")

    rows = iterate.benchmark(campaign)

    assert [(row["try"], row["provider"]) for row in rows] == [(0, "local"), (1, "groq")]
    assert rows[1]["accuracy"] == pytest.approx(0.9)

    text = iterate.render_benchmark(campaign, rows)

    assert "| 0 | self-hosted | stub-model |" in text
    assert "| 1 | groq | openai/gpt-oss-120b |" in text

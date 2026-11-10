"""
The troubleshooting script's deterministic half (src/evaluation/troubleshoot.py)
and the hook that keeps its agent blind (.claude/hooks/troubleshoot_blind.py).

What matters most is what the agent can and cannot see: the claims it is given
carry no label, and while it plans and searches it cannot open a run record, a
comparison or the label files. Then that the counts the experiment files rest on
are the same for every plan.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

from src.evaluation import troubleshoot as ts

REPO = Path(__file__).resolve().parents[3]


def record(claim_id: str, **extra) -> dict:

    return {
        "id": claim_id, "dataset": "custom", "language": "en", "claimDate": "2026-09-20",
        "articleUrl": f"https://www.example.org/{claim_id}", "claim": f"There were 212 travel-related cases ({claim_id}).",
        "label": "TRUE", "origin": "natural", "referenceEvidenceLinks": ["https://www.floridahealth.gov/report"],
        "queries": [{"text": "Florida", "kind": "anchor"}],
        "candidates": [
            {"url": "https://www.floridahealth.gov/report", "domain": "floridahealth.gov", "title": "Arbovirus", "stoppedAt": "evidence_retrieval", "reason": "cut by pre-rank funnel (rank 6 of 12)", "score": 0.3},
            {"url": "https://www.nytimes.com/cholera", "domain": "nytimes.com", "title": "Cholera", "stoppedAt": "ranked", "reason": None, "score": 0.5},
        ],
        "evidence": [{"url": "https://www.nytimes.com/cholera", "domain": "nytimes.com", "stance": "contradicts", "quote": "large numbers of whom travel"}],
        "verdict": "FALSE", "rawVerdict": "FALSE", "searchUnavailable": False,
        **extra,
    }


@pytest.fixture
def batch(tmp_path, monkeypatch):
    """A prepared batch over a two-claim fake run, everything under tmp_path."""

    run = tmp_path / "run"
    run.mkdir()
    (run / "results.jsonl").write_text("".join(json.dumps(record(i)) + "\n" for i in ("fact001", "fact002")), encoding="utf-8")

    monkeypatch.setattr(ts, "EXPERIMENTS", tmp_path / "experiments")
    monkeypatch.setattr(ts, "BACKEND", tmp_path)
    monkeypatch.setattr("src.evaluation.dataset.article_titles", lambda *a, **k: {})

    ts.cmd_prepare(argparse.Namespace(
        batch="b", force=False, evidence_run=str(run), replay_run=str(run), ids=None, offset=0, limit=20,
    ))

    return tmp_path / "experiments" / "b"


# ----------------------------------------------------------------------
# What the agent is given
# ----------------------------------------------------------------------

def test_the_claims_given_to_the_agent_carry_no_label_or_pipeline_record(batch):

    rows = [json.loads(line) for line in (batch / "claims.jsonl").read_text(encoding="utf-8").splitlines()]

    assert [row["id"] for row in rows] == ["fact001", "fact002"]

    for row in rows:
        assert set(row) == {"id", "language", "claimDate", "articleUrl", "excludeSite", "headline", "claim"}
        assert "TRUE" not in json.dumps(row)
        assert row["excludeSite"] == "example.org"


def test_a_prepared_batch_is_never_silently_replaced(batch, tmp_path):

    with pytest.raises(ts.TroubleshootError, match="fixed once prepared"):
        ts.cmd_prepare(argparse.Namespace(
            batch="b", force=False, evidence_run=str(tmp_path / "run"), replay_run=str(tmp_path / "run"), ids=None, offset=0, limit=20,
        ))


def test_an_incomplete_plan_is_refused_by_name(batch):

    (batch / "plan.jsonl").write_text(json.dumps({"id": "fact001", "lookingFor": "x", "decisive": "212"}) + "\n", encoding="utf-8")

    problems = ts.validate(batch, "plan")

    assert "fact002: no row in plan.jsonl" in problems
    assert any("fact001: no `queries`" in p for p in problems)
    assert any("`decisive` must be a list" in p for p in problems)


# ----------------------------------------------------------------------
# The counts
# ----------------------------------------------------------------------

@pytest.mark.parametrize("text, detail, expected", [
    ("Florida \"0.001 per cent\" neurons", "0.001%", True),
    ("Book Bunk 138000 books", "138,000", True),
    ("Florida been total known travel related cases", "212", False),
    ("Arctic Sea-ice minimum", "sea ice", True),
    ("Florida Dengue fever counties", "dengue", True),
    ("Florida tourism", "dengue", False),
    ("Venn \"11-set\" 2012", "11-set", True),
    ("Ronda Urbana Norte \"25 millones\"", "25 millones", True),
])
def test_a_detail_is_carried_by_its_figures_or_else_its_words(text, detail, expected):

    assert ts.carries(text, detail) is expected


def test_stage_05_flags_a_verdict_decided_by_a_stance_without_the_point():

    claims = [{"id": "fact037", "language": "en", "claim": "212 travel-related cases"}]
    plan = {"fact037": {"decisive": ["212", "dengue"]}}
    search = {"fact037": {"verdict": "TRUE"}}
    pipeline = {"fact037": {"evidenceNow": [{"domain": "nytimes.com", "stance": "contradicts", "quote": "large numbers of whom travel"}], "verdictNow": "FALSE"}}
    labels = {"fact037": {"label": "TRUE"}}

    rows = ts.compare("05", claims, plan, search, pipeline, labels)
    metrics = ts.summarise("05", rows)

    assert rows[0]["counted"]["decidedOffPoint"] is True
    assert metrics == {"claims": 1, "pipelineRight": 0, "claudeRight": 1, "pipelineWrong": 1, "wrongAndDecidedOffPoint": 1, "claudeAgreesWithGoldPipelineNot": 1}


def test_stage_04_follows_claudes_settling_source_through_the_cuts(batch):

    (batch / "plan.jsonl").write_text("".join(json.dumps({"id": i, "lookingFor": "x", "decisive": ["212"], "wouldSettleIt": "x", "sourceType": "report", "queries": ["q"]}) + "\n" for i in ("fact001", "fact002")), encoding="utf-8")
    (batch / "claude.jsonl").write_text("".join(json.dumps({"id": i, "searches": ["q"], "found": "x", "verdict": "TRUE", "sources": [], "settlingSource": "https://floridahealth.gov/report"}) + "\n" for i in ("fact001", "fact002")), encoding="utf-8")

    pipeline = {row["id"]: row for row in ts.recorded(ts.read_jsonl(batch / "claims.jsonl"), batch.parents[1] / "run", batch.parents[1] / "run")}
    rows = ts.compare("04", ts.read_jsonl(batch / "claims.jsonl"), {}, {r["id"]: r for r in ts.read_jsonl(batch / "claude.jsonl")}, pipeline, {})

    assert rows[0]["counted"]["settlingKept"] is False
    assert rows[0]["counted"]["settlingCut"] == ["cut by pre-rank funnel (rank 6 of 12)"]
    assert ts.summarise("04", rows)["settlingCut"] == 2


def test_the_measured_section_is_rewritten_and_the_agents_text_kept(batch, monkeypatch, tmp_path):

    monkeypatch.setattr(ts, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(ts, "REPO", tmp_path)

    out = ts.stage_dir(batch, "05")
    out.mkdir(parents=True)
    ts.write_json(out / "metrics-before.json", {"stage": "05", "label": "before", "at": "t", "pipelineRight": 3})

    path = ts.write_experiment("b", "05")
    path.write_text(path.read_text(encoding="utf-8").replace("## Findings\n", "## Findings\n\nThe agent's finding.\n").replace("| pipelineRight | 3 |", "| pipelineRight | 99 |"), encoding="utf-8")

    ts.write_json(out / "metrics-before.json", {"stage": "05", "label": "before", "at": "t", "pipelineRight": 4})
    text = ts.write_experiment("b", "05").read_text(encoding="utf-8")

    assert "| pipelineRight | 4 |" in text
    assert "99" not in text
    assert "The agent's finding." in text


# ----------------------------------------------------------------------
# The hook
# ----------------------------------------------------------------------

def hook():

    spec = importlib.util.spec_from_file_location("troubleshoot_blind", REPO / ".claude/hooks/troubleshoot_blind.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("phase, tool, tool_input, refused", [
    ("plan", "Read", {"file_path": "{batch}/claims.jsonl"}, False),
    ("plan", "Read", {"file_path": "backend/data/evaluation/runs/manual-train/x/results.jsonl"}, True),
    ("plan", "Read", {"file_path": "backend/data/evaluation/manual/fact001.json"}, True),
    ("plan", "Read", {"file_path": "{batch}/05-verification/comparison-before.json"}, True),
    ("plan", "Read", {"file_path": "docs/troubleshooting/fact-checking/02-queries.md"}, True),
    ("plan", "Grep", {"pattern": "fact001", "path": "."}, True),
    ("plan", "Bash", {"command": "cat anything"}, True),
    ("plan", "Write", {"file_path": "{batch}/plan.jsonl"}, False),
    ("plan", "Write", {"file_path": "{batch}/claude.jsonl"}, True),
    ("search", "Write", {"file_path": "{batch}/plan.jsonl"}, True),
    ("search", "WebFetch", {"url": "https://www.example.org/fact001"}, True),
    ("search", "WebFetch", {"url": "https://www.floridahealth.gov/report"}, False),
    ("analyse", "Edit", {"file_path": "{batch}/05-verification/metrics-before.json"}, True),
    ("analyse", "Write", {"file_path": "{batch}/05-verification/proposal.json"}, False),
    ("analyse", "Edit", {"file_path": "backend/src/services/x.py"}, True),
    ("implement", "Edit", {"file_path": "backend/src/services/x.py"}, False),
    ("analyse", "Read", {"file_path": "backend/data/evaluation/runs/manual-train/x/results.jsonl"}, False),
])
def test_the_hook_keeps_the_blind_steps_blind_and_the_numbers_the_scripts(batch, phase, tool, tool_input, refused):

    root = str(batch.parents[1])
    tool_input = {key: value.replace("{batch}", str(batch)) for key, value in tool_input.items()}

    reason = hook().refusal(phase, str(batch), root, tool, tool_input)

    assert (reason is not None) is refused, reason


# ----------------------------------------------------------------------
# The loop
# ----------------------------------------------------------------------

def rows01(shares: dict[str, float]) -> list[dict]:

    return [
        {"id": claim_id, "claude": {"decisive": ["x"], "sourceType": "s"},
         "counted": {"checkablePoint": {"share": share, "missing": [] if share == 1 else ["x"]}, "sentencePlan": {"share": 0}}}
        for claim_id, share in shares.items()
    ]


HOLD_SAME = ({"checkablePointCoverage": 0.5}, {"checkablePointCoverage": 0.5})


def test_a_round_is_kept_only_when_the_tune_batch_improves_and_nothing_falls():

    decision, _, changed = ts.decide("01", (rows01({"a": 0.5, "b": 0.5}), rows01({"a": 1.0, "b": 0.5})), HOLD_SAME)

    assert decision == "keep"
    assert changed["gained"] == ["a"] and changed["lost"] == []


def test_offline_stages_refuse_a_round_that_lowers_any_claim_even_when_the_total_rises():

    decision, reason, _ = ts.decide("01", (rows01({"a": 0.5, "b": 0.5}), rows01({"a": 1.0, "b": 0.25})), HOLD_SAME)

    assert decision == "reject" and "b" in reason


def test_the_held_out_batch_vetoes_a_round_the_tune_batch_liked():

    decision, reason, _ = ts.decide(
        "01", (rows01({"a": 0.5}), rows01({"a": 1.0})),
        ({"checkablePointCoverage": 0.6}, {"checkablePointCoverage": 0.5}),
    )

    assert decision == "reject" and "held-out" in reason


def test_a_searched_round_must_beat_the_search_noise():

    def rows03(found: dict[str, bool]) -> list[dict]:
        return [{"id": i, "counted": {"settlingInCandidates": ["d"] if hit else [], "referenceInCandidates": [], "searchUnavailable": False, "candidates": 10}} for i, hit in found.items()]

    hold = ({"settlingDomainInCandidates": 1}, {"settlingDomainInCandidates": 1})

    one, _, _ = ts.decide("03", (rows03({"a": False, "b": False}), rows03({"a": True, "b": False})), hold)
    two, _, _ = ts.decide("03", (rows03({"a": False, "b": False}), rows03({"a": True, "b": True})), hold)

    assert (one, two) == ("reject", "keep")


def test_a_rejected_round_is_put_back_byte_for_byte(tmp_path, monkeypatch):

    monkeypatch.setattr(ts, "REPO", tmp_path)
    (tmp_path / "backend/src").mkdir(parents=True)
    (tmp_path / "backend/tests").mkdir(parents=True)
    (tmp_path / "backend/src/a.py").write_text("before\n", encoding="utf-8")

    files = ts.snapshot()

    (tmp_path / "backend/src/a.py").write_text("after\n", encoding="utf-8")
    (tmp_path / "backend/tests/test_new.py").write_text("new\n", encoding="utf-8")

    assert ts.touched(files) == ["backend/src/a.py", "backend/tests/test_new.py"]
    assert ts.restore(files) == ["backend/src/a.py", "backend/tests/test_new.py"]
    assert (tmp_path / "backend/src/a.py").read_text(encoding="utf-8") == "before\n"
    assert not (tmp_path / "backend/tests/test_new.py").exists()


def test_a_run_over_a_batch_takes_only_its_ids_and_never_one_from_another_half():

    from types import SimpleNamespace

    from src.evaluation.dataset import Dataset, DatasetError, only_ids

    train = Dataset(path=Path("x"), stem="manual-train", sha256="s", rows=tuple(SimpleNamespace(id=i) for i in ("f1", "f2", "f3")))

    batch = only_ids(train, ["f3", "f1"])

    assert [row.id for row in batch.rows] == ["f1", "f3"]
    assert batch.stem.startswith("manual-train-ids") and batch.stem != train.stem

    with pytest.raises(DatasetError, match="f9"):
        only_ids(train, ["f1", "f9"])


@pytest.mark.parametrize("tool, tool_input, refused", [
    ("Read", {"file_path": "{hold}/01-what-to-look-for/round-01/comparison-before.json"}, True),
    ("Grep", {"pattern": "fact", "path": "{experiments}"}, True),
    ("Grep", {"pattern": "def checkable_point", "path": "backend/src"}, False),
    ("Read", {"file_path": "{batch}/01-what-to-look-for/round-01/comparison-before.json"}, False),
    ("Edit", {"file_path": "backend/src/evaluation/troubleshoot.py"}, True),
    ("Edit", {"file_path": "backend/tests/evaluation/test_troubleshoot.py"}, True),
    ("Edit", {"file_path": "backend/src/services/fact_checker/retrieval/checkable.py"}, False),
])
def test_in_a_loop_round_the_agent_cannot_see_the_held_out_batch_or_change_the_measure(batch, tmp_path, monkeypatch, tool, tool_input, refused):

    hold = batch.parent / "held"
    root = str(batch.parents[1])
    monkeypatch.setenv("TROUBLESHOOT_HOLDOUT", str(hold))

    tool_input = {key: value.replace("{hold}", str(hold)).replace("{batch}", str(batch)).replace("{experiments}", str(batch.parent)) for key, value in tool_input.items()}

    reason = hook().refusal("implement", str(batch), root, tool, tool_input)

    assert (reason is not None) is refused, reason


# ----------------------------------------------------------------------
# No cost beyond the subscription
# ----------------------------------------------------------------------

@pytest.fixture
def subscription(monkeypatch, tmp_path):
    """config.json as committed, and `claude auth status` answering as a claude.ai login."""

    config = tmp_path / "config.json"
    config.write_text(json.dumps({"billing": "subscription", "localOnly": True}), encoding="utf-8")
    monkeypatch.setattr(ts, "CONFIG", config)

    for name in ts.API_BILLING_ENV:
        monkeypatch.delenv(name, raising=False)

    # A local model, whatever backend/.env names: LLM_BASE_URL is
    # infrastructure, which pinned_settings leaves as configured, and a
    # machine pointed at Groq (2026-11-10) turned this test red.
    from src.config.settings import settings
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost:11434/v1")

    real_run = ts.subprocess.run

    def run(command, *args, **kwargs):
        if command[:3] == ["claude", "auth", "status"]:
            return SimpleNamespace(stdout=json.dumps({"loggedIn": True, "authMethod": "claude.ai"}), returncode=0)
        if command[:2] == ["claude", "-p"]:
            return SimpleNamespace(stdout=json.dumps({"type": "rate_limit_event", "rate_limit_info": {"overageStatus": "rejected"}}), returncode=0)
        return real_run(command, *args, **kwargs)

    from types import SimpleNamespace
    monkeypatch.setattr(ts.subprocess, "run", run)


def test_preflight_passes_a_subscription_login_with_a_local_model(subscription):

    assert ts.preflight(["01", "05"]) == []


def test_preflight_refuses_an_api_key_and_a_hosted_model(subscription, monkeypatch):

    from src.config.settings import settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")

    problems = ts.preflight(["05"])

    assert any("ANTHROPIC_API_KEY" in p for p in problems)
    assert any("hosted, paid provider" in p for p in problems)


def test_the_agent_never_receives_an_api_credential_under_a_subscription(subscription, monkeypatch, tmp_path):

    seen = {}

    class Process:
        def __init__(self, command, cwd=None, env=None, stdout=None, text=None):
            seen["env"] = env
            self.stdout = iter([json.dumps({"type": "system", "subtype": "init", "model": "m", "apiKeySource": "none"}) + "\n"])
        def wait(self):
            return 0

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(ts.shutil, "which", lambda name: "/bin/claude")
    monkeypatch.setattr(ts.subprocess, "Popen", Process)
    monkeypatch.setattr(ts, "REPO", tmp_path)
    monkeypatch.setattr(ts, "record_step", lambda *a, **k: None)

    status = ts._claude("p", "plan", tmp_path / "b", "plan", argparse.Namespace(model=None, max_budget_usd=None, dry_run=False))

    assert status == 0
    assert "ANTHROPIC_API_KEY" not in seen["env"]


def test_a_step_that_ran_on_an_api_key_stops_the_loop(subscription, monkeypatch, tmp_path):

    class Process:
        def __init__(self, *args, **kwargs):
            self.stdout = iter([json.dumps({"type": "system", "subtype": "init", "apiKeySource": "ANTHROPIC_API_KEY"}) + "\n"])
        def wait(self):
            return 0

    monkeypatch.setattr(ts.shutil, "which", lambda name: "/bin/claude")
    monkeypatch.setattr(ts.subprocess, "Popen", Process)
    monkeypatch.setattr(ts, "REPO", tmp_path)
    monkeypatch.setattr(ts, "record_step", lambda *a, **k: None)

    with pytest.raises(ts.TroubleshootError, match="API key"):
        ts._claude("p", "plan", tmp_path / "b", "plan", argparse.Namespace(model=None, max_budget_usd=None, dry_run=False))


# ----------------------------------------------------------------------
# Never extra credits
# ----------------------------------------------------------------------

@pytest.mark.parametrize("info, safe", [
    ({"status": "allowed", "overageStatus": "rejected", "overageDisabledReason": "org_level_disabled", "isUsingOverage": False}, True),
    ({"status": "allowed", "overageStatus": "allowed", "isUsingOverage": False}, False),
    ({"status": "allowed_warning", "overageStatus": "allowed", "isUsingOverage": False, "overageEnabled": True}, False),
    ({"status": "rejected", "overageStatus": "allowed", "isUsingOverage": True, "overageInUse": True}, False),
])
def test_only_an_account_with_extra_credits_off_counts_as_safe(info, safe):

    assert (ts.credit_risk(info) is None) is safe


def _probe_answers(monkeypatch, *lines):

    from types import SimpleNamespace

    def run(command, *args, **kwargs):
        if command[:3] == ["claude", "auth", "status"]:
            return SimpleNamespace(stdout=json.dumps({"loggedIn": True, "authMethod": "claude.ai"}), returncode=0)
        return SimpleNamespace(stdout="\n".join(lines), returncode=0)

    monkeypatch.setattr(ts.subprocess, "run", run)


def test_preflight_refuses_an_account_with_extra_credits_on_and_one_it_cannot_confirm(subscription, monkeypatch):

    report = {"type": "rate_limit_event", "rate_limit_info": {"overageStatus": "allowed", "isUsingOverage": False}}
    _probe_answers(monkeypatch, json.dumps(report))
    assert any("extra credits switched on" in p for p in ts.preflight(["01"]))

    _probe_answers(monkeypatch, json.dumps({"type": "system"}))
    assert any("could not confirm" in p for p in ts.preflight(["01"]))


def test_a_step_is_killed_at_the_first_report_of_extra_credits(subscription, monkeypatch, tmp_path):

    killed = []
    report = json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "isUsingOverage": True}}) + "\n"
    more = json.dumps({"type": "assistant", "message": {"content": []}}) + "\n"

    class Process:
        def __init__(self, *args, **kwargs):
            self.stdout = iter([report, more])
        def kill(self):
            killed.append(True)
        def wait(self):
            return -9

    steps = []
    monkeypatch.setattr(ts.shutil, "which", lambda name: "/bin/claude")
    monkeypatch.setattr(ts.subprocess, "Popen", Process)
    monkeypatch.setattr(ts, "REPO", tmp_path)
    monkeypatch.setattr(ts, "record_step", lambda batch, name, step: steps.append(step))

    with pytest.raises(ts.TroubleshootError, match="extra credits"):
        ts._claude("p", "plan", tmp_path / "b", "plan", argparse.Namespace(model=None, max_budget_usd=None, dry_run=False))

    assert killed == [True]
    assert "stopped" in steps[0]["outcome"]
    assert more not in (tmp_path / "b/logs/plan.jsonl").read_text(encoding="utf-8")

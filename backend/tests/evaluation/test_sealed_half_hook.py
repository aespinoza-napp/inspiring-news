"""
The hook that seals the custom set's test half during a campaign
(.claude/hooks/sealed_test_half.py): AVeriTeC runs pass since 2026-11-05, and
nothing that reaches the sealed half may pass with them.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "sealed_test_half.py"

RUN = "uv run python -m src.evaluation.cli run"


def _verdict(tmp_path: Path, command: str) -> int:

    campaign = tmp_path / "backend/data/evaluation/experiments/iterate/some-campaign"
    campaign.mkdir(parents=True, exist_ok=True)
    (campaign / "campaign.json").write_text(json.dumps({"status": "active"}))

    env = {key: value for key, value in os.environ.items() if key != "ITERATE_ALLOW_TEST_HALF"}
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)

    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        env=env,
    ).returncode


@pytest.mark.parametrize("command", [
    f"{RUN} --dataset data/evaluation/averitec/averitec_dev.jsonl --limit 100",
    f"{RUN} --dataset data/evaluation/averitec/averitec_train.jsonl --split train",
    f"{RUN} --dataset data/evaluation/manual --split train",
])
def test_these_pass_during_a_campaign(tmp_path, command):

    assert _verdict(tmp_path, command) == 0


@pytest.mark.parametrize("command", [
    f"{RUN} --dataset data/evaluation/manual",
    f"{RUN} --dataset data/evaluation/manual --split test",
    f"{RUN} --dataset data/evaluation/xfact_en_es.jsonl",
    # Another file with the name in it is not the benchmark.
    f"{RUN} --dataset data/evaluation/averitec/averitec_dev.jsonl.bak",
    f"{RUN} --dataset data/evaluation/not_averitec_dev.jsonl",
    # An AVeriTeC run does not excuse what else the command touches.
    f"{RUN} --dataset data/evaluation/averitec/averitec_dev.jsonl; cat data/evaluation/custom_en_es.jsonl",
    "cat data/evaluation/runs/manual-test/x/results.jsonl",
])
def test_these_stay_refused_during_a_campaign(tmp_path, command):

    assert _verdict(tmp_path, command) == 2

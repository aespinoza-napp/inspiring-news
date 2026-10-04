"""
The command line: arguments reach the runner, and threshold files
resolve the way a request's overrides do. The pipeline behind it is the
shared-fakes one; nothing here reaches a live service.
"""

import json

import pytest
from pydantic import ValidationError

from src.evaluation import cli
from src.evaluation.runner import HarnessRunner, latest_records

from tests.evaluation.support import claim_service, recording_checker, write_jsonl, xfact_row


@pytest.fixture
def fake_pipeline(monkeypatch, repository):
    """build_runner, over the recording checker instead of the real stack."""

    built = {}

    def build(config):
        checker, retriever = recording_checker(repository)
        runner = HarnessRunner(
            config,
            checker=checker,
            claims=claim_service(checker),
            provider="localhost:11434",
            commit="abc123",
            max_workers=1,
        )
        built.update(config=config, retriever=retriever, runner=runner)
        return runner, lambda: built.setdefault("closed", True)

    monkeypatch.setattr(cli, "build_runner", build)

    # The CLI installs a SIGINT handler; keep the test process's own.
    monkeypatch.setattr(cli, "_stop_on_first_interrupt", lambda stop: None)

    return built


def test_run_resolves_its_arguments_into_a_run(fake_pipeline, tmp_path, capsys):

    dataset = write_jsonl(tmp_path / "pilot.jsonl", [
        xfact_row("First claim."), xfact_row("Second claim.", language="es"),
    ])

    overrides = tmp_path / "thresholds.json"
    overrides.write_text(json.dumps({"evidence_min_pertinence": 0.4}), encoding="utf-8")

    status = cli.main([
        "run",
        "--dataset", str(dataset),
        "--model", "llama3.2:3b",
        "--limit", "1",
        "--thresholds", str(overrides),
        "--corpus", "none",
        "--root", str(tmp_path / "runs"),
    ])

    assert status == 0

    config = fake_pipeline["config"]

    assert config.model == "llama3.2:3b"
    assert config.corpus == "none"
    assert config.thresholds.evidence_min_pertinence == 0.4
    assert config.directory.parent == tmp_path / "runs" / "pilot" / "llama3.2-3b"

    assert fake_pipeline["closed"] is True

    printed = json.loads(capsys.readouterr().out)

    assert printed["ok"] == 1
    assert printed["run"] == str(config.directory)

    assert len(latest_records(config.directory)) == 1


def test_an_unknown_threshold_is_an_error_not_a_silent_typo(tmp_path):

    overrides = tmp_path / "thresholds.json"
    overrides.write_text(json.dumps({"evidence_min_pertinance": 0.4}), encoding="utf-8")

    with pytest.raises(ValidationError):
        cli.load_thresholds(str(overrides))


def test_no_threshold_file_means_the_defaults():

    assert cli.load_thresholds(None) == cli.PipelineThresholds()

"""
The CI workflow, held to scripts/check.sh.

The workflow is meant to call check.sh's targets and nothing else, so
that "green in CI" and "./scripts/check.sh passes" stay the same
statement. Two ways that silently stops being true, both caught here:

- a target is renamed or removed in check.sh, and the workflow goes on
  calling it. check.sh answers an unknown target with exit 2, which a
  reader of the CI log takes for a test failure - or, worse, someone
  "fixes" the job by inlining the command it used to run;
- the workflow starts composing its own pytest or tsc call, and drifts
  from what the script runs.

Read with PyYAML (already a backend dependency) rather than a regex, so
a comment that mentions a target does not count as calling it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"
CHECK_SH = ROOT / "scripts" / "check.sh"

CHECK_CALL = re.compile(r"(?:^|\s)(?:\./|bash\s+)?scripts/check\.sh\s+([A-Za-z0-9_-]+)")

CASE_BRANCH = re.compile(r"^\s*([A-Za-z0-9_-]+)\)")

# The targets kept out of CI on purpose, each for a reason written in the
# workflow's header: real models, the whole corpus, a running Neo4j,
# Docker. A job calling one of them would either fail on every run or
# take an hour - and a CI that is always red is a CI nobody reads.
LOCAL_ONLY = {"inference", "slow", "graph", "gcp"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def check_targets() -> set[str]:
    """The branches of check.sh's `case "$TARGET" in ... esac`."""

    lines = CHECK_SH.read_text(encoding="utf-8").splitlines()

    start = next(i for i, line in enumerate(lines) if line.strip().startswith('case "$TARGET" in'))
    end = next(i for i, line in enumerate(lines) if i > start and line.strip() == "esac")

    return {
        match.group(1)
        for line in lines[start + 1:end]
        if (match := CASE_BRANCH.match(line))
    }


def called_targets(workflow: dict) -> dict[str, list[str]]:
    """Per job, the check.sh targets its `run:` steps call."""

    return {
        name: [
            target
            for step in job.get("steps", [])
            for target in CHECK_CALL.findall(step.get("run") or "")
        ]
        for name, job in workflow["jobs"].items()
    }


def test_the_case_list_is_read_correctly():
    """Guards the parser above, so the next test cannot pass vacuously."""

    assert {"all", "fast", "backend", "frontend", "labeller", "inference"} <= check_targets()


def test_every_target_the_workflow_calls_exists_in_check_sh(workflow):

    targets = check_targets()

    called = called_targets(workflow)

    missing = sorted(
        f"{job}: {target}"
        for job, job_targets in called.items()
        for target in job_targets
        if target not in targets
    )

    assert missing == [], (
        "The workflow calls check.sh targets that no longer exist "
        f"(check.sh has {sorted(targets)}): {missing}"
    )


def test_every_job_runs_exactly_one_check_target(workflow):
    """
    One job, one target: what failed is then readable from the job name
    alone, and no job runs its own composition of the checks.
    """

    called = called_targets(workflow)

    assert {job: len(targets) for job, targets in called.items()} == {
        job: 1 for job in called
    }


def test_the_workflow_runs_the_three_ci_targets_and_none_of_the_local_ones(workflow):

    called = {target for targets in called_targets(workflow).values() for target in targets}

    assert called == {"backend", "frontend", "labeller"}
    assert called.isdisjoint(LOCAL_ONLY)


def test_it_runs_on_every_push_and_pull_request(workflow):

    # YAML 1.1 reads a bare `on` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))

    assert "push" in triggers
    assert "pull_request" in triggers


def test_the_backend_job_can_construct_settings_without_a_dot_env(workflow):
    """
    backend/.env is not in git, and Settings refuses to start without
    NEO4J_PASSWORD. Without it every backend test errors at import.
    """

    env = workflow["jobs"]["backend"].get("env", {})

    assert env.get("NEO4J_PASSWORD")


@pytest.mark.skipif(os.name == "nt", reason="Windows has no executable bit to check")
def test_check_sh_is_executable():
    """
    The workflow and the Makefile both call `./scripts/check.sh`, which
    a Linux runner refuses with "Permission denied" when git does not
    record the file as executable - it did not, until the workflow was
    added.
    """

    assert os.access(CHECK_SH, os.X_OK)

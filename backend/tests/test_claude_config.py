"""
The repo's Claude Code hooks and skills (.claude/). A hook that silently does
nothing looks exactly like one that works: the first post-edit hook read an
environment variable that was not set and never ran a check. So these run the
hooks on the input they really receive, in a throwaway git repository.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"
SKILLS = sorted((CLAUDE / "skills").glob("*/SKILL.md"))


def run_hook(name, payload, cwd):

    return subprocess.run(
        [sys.executable, str(CLAUDE / "hooks" / name)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(cwd)},
    )


@pytest.fixture
def repo(tmp_path):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "kept.txt").write_text("kept")
    git("add", "kept.txt")
    git("commit", "-m", "first")

    return tmp_path


# ----------------------------------------------------------------------
# The uncommitted-work hook
# ----------------------------------------------------------------------


def test_uncommitted_work_left_unsaid_sends_claude_back(repo):

    (repo / "kept.txt").write_text("changed")

    answer = json.loads(run_hook("uncommitted.py", {"last_assistant_message": "All done."}, repo).stdout)

    assert answer["decision"] == "block"
    assert "kept.txt" in answer["reason"]
    assert "Do not commit" in answer["reason"]


def test_a_new_file_counts(repo):

    (repo / "new.txt").write_text("new")

    assert "new.txt" in run_hook("uncommitted.py", {"last_assistant_message": "All done."}, repo).stdout


@pytest.mark.parametrize("message", ["Nothing is committed yet.", "Shall I commit this?", "Todavía sin commitear."])
def test_saying_it_is_enough(repo, message):

    (repo / "kept.txt").write_text("changed")

    assert run_hook("uncommitted.py", {"last_assistant_message": message}, repo).stdout == ""


def test_a_clean_tree_says_nothing(repo):

    assert run_hook("uncommitted.py", {"last_assistant_message": "All done."}, repo).stdout == ""


def test_it_never_loops(repo):

    (repo / "kept.txt").write_text("changed")

    assert run_hook("uncommitted.py", {"stop_hook_active": True, "last_assistant_message": "x"}, repo).stdout == ""


def test_it_reads_the_transcript_when_the_input_has_no_message(repo, tmp_path_factory):

    (repo / "kept.txt").write_text("changed")

    transcript = tmp_path_factory.mktemp("t") / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "user", "message": {"content": "commit?"}}) + "\n"
        + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Nothing committed."}]}}) + "\n"
    )

    assert run_hook("uncommitted.py", {"transcript_path": str(transcript)}, repo).stdout == ""


@pytest.mark.parametrize("payload", ["not json", {}])
def test_outside_a_repository_or_on_bad_input_it_stays_out_of_the_way(tmp_path, payload):

    result = run_hook("uncommitted.py", payload, tmp_path)

    assert result.returncode == 0 and result.stdout == ""


# ----------------------------------------------------------------------
# The post-edit hook
# ----------------------------------------------------------------------


def checks_project(tmp_path, exit_code):

    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check.sh").write_text(f"echo ran $1\nexit {exit_code}\n")

    return tmp_path


def test_an_edit_in_the_backend_runs_the_invariants_and_shows_a_failure(tmp_path):

    project = checks_project(tmp_path, 1)

    result = run_hook("fast_checks.py", {"tool_input": {"file_path": str(project / "backend/src/a.py")}}, project)

    assert result.returncode == 2
    assert "ran fast" in result.stderr


def test_a_passing_check_is_silent(tmp_path):

    project = checks_project(tmp_path, 0)

    result = run_hook("fast_checks.py", {"tool_input": {"file_path": str(project / "backend/tests/a.py")}}, project)

    assert result.returncode == 0 and result.stderr == ""


def test_an_edit_elsewhere_runs_nothing(tmp_path):

    project = checks_project(tmp_path, 1)

    assert run_hook("fast_checks.py", {"tool_input": {"file_path": str(project / "docs/a.md")}}, project).returncode == 0


# ----------------------------------------------------------------------
# What is declared
# ----------------------------------------------------------------------


def test_the_settings_name_hooks_that_exist():

    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))

    commands = [hook["command"] for groups in settings["hooks"].values() for group in groups for hook in group["hooks"]]

    assert len(commands) >= 2

    for command in commands:
        script = re.search(r"\.claude/hooks/([\w.]+)", command).group(1)
        assert (CLAUDE / "hooks" / script).exists(), command


def test_there_are_skills_to_check():

    assert SKILLS


@pytest.mark.parametrize("path", SKILLS, ids=lambda path: path.parent.name)
def test_a_skill_declares_its_name_and_when_to_use_it(path):

    head = path.read_text(encoding="utf-8").split("---")[1]

    assert re.search(rf"^name: {path.parent.name}$", head, re.MULTILINE)

    description = re.search(r"^description: (.+)$", head, re.MULTILINE).group(1)

    assert "Use " in description and len(description) <= 1024


@pytest.mark.parametrize("path", SKILLS, ids=lambda path: path.parent.name)
def test_a_skill_only_points_at_what_exists(path):
    """So a renamed script or target fails here, and not in the middle of an audit."""

    text = path.read_text(encoding="utf-8")

    # In backticks: a command, not a sentence that goes on after the name.
    for target in re.findall(r"`\./scripts/check\.sh (\w+)`", text):
        assert f"{target})" in (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8"), target

    for name in re.findall(r"`((?:scripts|docs|data/evaluation)/[\w./-]+\.\w+)`", text):
        assert (ROOT / name).exists() or (ROOT / "backend" / name).exists(), name

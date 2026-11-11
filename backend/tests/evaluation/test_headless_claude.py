"""
The headless-Claude contender's transport and its guard, against a fake
`claude` on PATH: the real CLI is never called from the suite.
"""

import json
import os
import stat

import pytest

from src.evaluation import headless_claude as hc
from src.services.llms import LLMClient


def _rate(five=0.10, week=0.20, **extra):

    info = {
        "status": "allowed",
        "overageStatus": "rejected",
        "isUsingOverage": False,
        "unifiedWindows": {"five_hour": {"utilization": five}, "seven_day": {"utilization": week}},
    }
    info.update(extra)
    return {"type": "rate_limit_event", "rate_limit_info": info}


def _fake_claude(tmp_path, monkeypatch, events, record_to=None):
    """A `claude` that prints `events` as stream-json and keeps its argv and stdin."""

    script = tmp_path / "bin" / "claude"
    script.parent.mkdir()
    lines = "\n".join(json.dumps(e) for e in events)
    record = record_to or tmp_path / "called.json"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"json.dump({{'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'env': sorted(os.environ)}}, open({str(record)!r}, 'w'))\n"
        f"print({lines!r})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{script.parent}{os.pathsep}{os.environ['PATH']}")
    return record


@pytest.fixture(autouse=True)
def _untripped(monkeypatch):

    monkeypatch.setattr(hc, "_TRIPPED", [])
    monkeypatch.delenv("HEADLESS_CLAUDE_CEILING", raising=False)


def _ok_events(text='{"verdict": "TRUE"}', **rate):

    return [
        {"type": "system", "subtype": "init", "apiKeySource": "none", "model": "claude-sonnet-5-5"},
        _rate(**rate),
        {"type": "result", "subtype": "success", "is_error": False, "result": text, "total_cost_usd": 0.01,
         "usage": {"input_tokens": 5, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0, "output_tokens": 9}},
    ]


def test_parse_model_reads_alias_and_effort():

    assert hc.parse_model("claude-headless:sonnet") == ("sonnet", None)
    assert hc.parse_model("claude-headless:haiku:low") == ("haiku", "low")

    with pytest.raises(ValueError):
        hc.parse_model("claude-headless:")


def test_any_other_model_is_the_plain_client():

    client = hc.llm_client("llama3.2:3b")

    assert isinstance(client, LLMClient)
    assert not isinstance(client._client, hc.HeadlessClaudeTransport)


@pytest.mark.parametrize("info, stops", [
    (_rate()["rate_limit_info"], False),
    (_rate(five=0.90)["rate_limit_info"], True),
    (_rate(week=0.95)["rate_limit_info"], True),
    (_rate(overageStatus="allowed")["rate_limit_info"], True),
    (_rate(isUsingOverage=True)["rate_limit_info"], True),
    (_rate(status="rejected")["rate_limit_info"], True),
])
def test_stop_reason(info, stops):

    assert (hc.stop_reason(info, 0.90) is not None) is stops


def test_a_call_answers_through_complete_json(tmp_path, monkeypatch):

    record = _fake_claude(tmp_path, monkeypatch, _ok_events())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-never-reach-the-child")

    client = hc.llm_client("claude-headless:sonnet:low")

    assert client.complete_json("the system", "the claim") == {"verdict": "TRUE"}

    called = json.loads(record.read_text())
    assert called["stdin"] == "the claim"
    assert called["argv"][called["argv"].index("--system-prompt") + 1] == "the system"
    assert called["argv"][called["argv"].index("--tools") + 1] == ""
    assert called["argv"][called["argv"].index("--effort") + 1] == "low"
    assert "ANTHROPIC_API_KEY" not in called["env"]
    assert LLMClient.last_call()["promptTokens"] == 605


def test_the_ceiling_stops_the_run_and_every_later_call(tmp_path, monkeypatch):

    record = _fake_claude(tmp_path, monkeypatch, _ok_events(five=0.91))
    client = hc.llm_client("claude-headless:sonnet")

    # A BaseException: an `except Exception` around one claim cannot swallow it.
    with pytest.raises(hc.UsageCeiling):
        client.complete_json("s", "u")

    record.unlink()

    with pytest.raises(hc.UsageCeiling):
        client.complete_json("s", "u")

    assert not record.exists(), "a tripped guard must not start claude again"


def test_an_api_key_source_stops(tmp_path, monkeypatch):

    events = _ok_events()
    events[0]["apiKeySource"] = "ANTHROPIC_API_KEY"
    _fake_claude(tmp_path, monkeypatch, events)

    with pytest.raises(hc.UsageCeiling):
        hc.llm_client("claude-headless:sonnet").complete_json("s", "u")


def test_the_ceiling_is_configurable(tmp_path, monkeypatch):

    _fake_claude(tmp_path, monkeypatch, _ok_events(five=0.85))
    monkeypatch.setenv("HEADLESS_CLAUDE_CEILING", "0.80")

    with pytest.raises(hc.UsageCeiling):
        hc.llm_client("claude-headless:sonnet").complete_json("s", "u")


def test_every_call_is_logged(tmp_path, monkeypatch):

    _fake_claude(tmp_path, monkeypatch, _ok_events())
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("HEADLESS_CLAUDE_LOG", str(log))

    hc.llm_client("claude-headless:sonnet").complete_json("s", "u")

    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["ok"] and entry["apiEquivalentUsd"] == 0.01
    assert entry["utilization"] == {"five_hour": 0.10, "seven_day": 0.20}


def test_a_retry_is_sent_as_one_turn():

    system, prompt = hc._flatten([
        {"role": "system", "content": "S"},
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "not json"},
        {"role": "user", "content": "JSON only"},
    ])

    assert system == "S"
    assert "not json" in prompt and prompt.endswith("JSON only")

"""
Claude as a contender in the evaluation harness, through the claude.ai
subscription's headless CLI (`claude -p`), never the API.

    --model claude-headless:sonnet        # any alias or full id `claude --model` takes
    --model claude-headless:haiku:low     # with an effort level

`llm_client(model)` is where the harness builds its model client. For any
other model it is `LLMClient(model=...)`, unchanged; for a
`claude-headless:` one it is the same `LLMClient` with its OpenAI transport
replaced by `HeadlessClaudeTransport`, so `complete_json`'s permit, retries,
JSON parsing and `last_call()` - and every prompt the pipeline sends - are
the ones every local model was measured with. The app never builds one:
nothing in `src/container.py` reads this module.

What is not the same as a local model, and is said in every report:

- **No temperature.** `claude -p` takes none, so two runs on the same
  evidence need not agree; the local models are asked at 0.
- **No token cap.** `max_tokens` is accepted and not enforced.
- **The cost is a share of a plan, not dollars.** `total_cost_usd` in the
  stream is what the same tokens would cost at list price on the API; it is
  logged as `apiEquivalentUsd`, never charged. The plan's own figure is the
  five-hour and seven-day `utilization` the stream reports on every call.

Why each flag (measured 2026-11-11, Claude Code 2.1.322):

- `--system-prompt` replaces Claude Code's own, and with `--tools ""`,
  `--strict-mcp-config`, `--disable-slash-commands`, `--setting-sources ""`
  and an empty working directory a one-line call carried ~630 tokens of
  context instead of ~19,000 (Claude Code's prompt, the project's CLAUDE.md,
  tools, connectors). It also means no tool: no web search, so on AVeriTeC
  nothing from after the claim's date can reach it through this path. What
  it remembers from training can - measure that with `--closed-book`.
- Not `--bare`: it authenticates only with ANTHROPIC_API_KEY, which is the API.
- Every API credential is removed from the child's environment, and a call
  whose `apiKeySource` is not "none" stops the run: with a key, the same
  command bills per token.

The guard (the user's rule, 2026-11-11: stop at 90% of the plan's usage;
and since 2026-11-05 never spend extra credits). Every call's stream
carries a `rate_limit_event`. The run stops - `UsageCeiling`, a
BaseException, so no `except Exception` in the pipeline turns it into one
claim's error and carries on - when:

- either window's `utilization` is at or past `HEADLESS_CLAUDE_CEILING`
  (0.90 by default);
- the account has extra credits on or is using them (`overageStatus` other
  than "rejected", `isUsingOverage`);
- the plan refused the call (`status` "rejected"), or the call ran on a key.

Once tripped, every later call in the process raises at once, without
starting `claude`. The utilization read is the one the call reports, so the
call that crosses the ceiling is the last one; at a few thousand tokens per
call that is well inside the remaining 10%. The interactive session that
started the run draws on the same windows and is not covered: watch it.

Every call is appended to `HEADLESS_CLAUDE_LOG` when set (JSONL: seconds,
tokens, apiEquivalentUsd, the utilization after it).

    uv run python -m src.evaluation.headless_claude status    # the plan's windows now, one short call
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
from openai import APIConnectionError, APITimeoutError

from src.services.llms import LLMClient

PREFIX = "claude-headless:"

DEFAULT_CEILING = 0.90

DEFAULT_TIMEOUT = 300.0

# The same list troubleshoot.py strips: any of these makes `claude -p` bill
# an API account, or a cloud provider, instead of the subscription.
API_BILLING_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "AWS_BEARER_TOKEN_BEDROCK",
)

_REQUEST = httpx.Request("POST", "claude-headless://claude-p")


class UsageCeiling(BaseException):
    """The plan's usage, or a credit risk, says stop: not one claim's failure."""


_TRIPPED: list[str] = []
_LOCK = threading.Lock()


def is_headless(model: str | None) -> bool:

    return bool(model) and model.startswith(PREFIX)


def parse_model(model: str) -> tuple[str, str | None]:
    """`claude-headless:sonnet:low` -> ("sonnet", "low")."""

    rest = model[len(PREFIX):]
    alias, _, effort = rest.partition(":")

    if not alias:
        raise ValueError(f"{model!r} names no Claude model: claude-headless:<alias>[:<effort>]")

    return alias, effort or None


def ceiling() -> float:

    return float(os.environ.get("HEADLESS_CLAUDE_CEILING", DEFAULT_CEILING))


def windows(info: dict) -> dict[str, float]:
    """{window: utilization 0-1} from one rate-limit report."""

    found = {
        name: float(window["utilization"])
        for name, window in (info.get("unifiedWindows") or {}).items()
        if isinstance(window, dict) and window.get("utilization") is not None
    }

    if not found and info.get("utilization") is not None:
        found[info.get("rateLimitType") or "window"] = float(info["utilization"])

    return found


def stop_reason(info: dict, limit: float) -> str | None:
    """Why this rate-limit report means the run must stop; None when it may go on."""

    if info.get("isUsingOverage") or info.get("overageInUse"):
        return "the account is spending extra credits"

    if info.get("overageEnabled") or info.get("overageStatus") not in (None, "rejected"):
        return f"the account has extra credits switched on (overageStatus {info.get('overageStatus')!r})"

    if info.get("status") == "rejected":
        return f"the plan refused the call ({info.get('rateLimitType')} limit reached)"

    over = {name: value for name, value in windows(info).items() if value >= limit}

    if over:
        shown = ", ".join(f"{name} {value:.0%}" for name, value in over.items())
        return f"usage at the ceiling ({shown} >= {limit:.0%})"

    return None


def trip(reason: str) -> None:

    with _LOCK:
        if not _TRIPPED:
            _TRIPPED.append(reason)
            print(f"\n[claude-headless] STOPPED: {reason}", file=sys.stderr, flush=True)


def _flatten(messages: list[dict]) -> tuple[str, str]:
    """The system prompt, and the rest as one turn: `claude -p` takes one."""

    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [m for m in messages if m["role"] != "system"]

    if len(turns) == 1:
        return system, turns[0]["content"]

    # complete_json's retry after a non-JSON answer: the answer, then the ask.
    parts = []
    for message in turns:
        label = "Your previous answer" if message["role"] == "assistant" else "Request"
        parts.append(f"## {label}\n\n{message['content']}")

    return system, "\n\n".join(parts)


def _log(record: dict) -> None:

    path = os.environ.get("HEADLESS_CLAUDE_LOG")

    if not path:
        return

    with _LOCK, open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class _Completions:

    def __init__(self, transport: "HeadlessClaudeTransport"):

        self._transport = transport

    def create(self, *, messages, model=None, timeout=None, **_ignored):

        return self._transport.complete(messages, timeout=timeout)


class HeadlessClaudeTransport:
    """
    Stands in for the OpenAI SDK client inside `LLMClient`: only
    `chat.completions.create` is used there, and it answers with the shape
    `complete_json` reads (choices[0].message.content, finish_reason, usage).
    """

    def __init__(self, alias: str, effort: str | None = None, timeout: float | None = None):

        self.alias = alias
        self.effort = effort
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.chat = SimpleNamespace(completions=_Completions(self))

        # No CLAUDE.md, settings or hooks to discover: an empty directory.
        self._cwd = tempfile.mkdtemp(prefix="claude-headless-")

    def command(self, system: str) -> list[str]:

        command = [
            "claude", "-p",
            "--model", self.alias,
            "--output-format", "stream-json", "--verbose",
            "--no-session-persistence",
            "--system-prompt", system or "Answer the request.",
            "--tools", "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--setting-sources", "",
        ]

        if self.effort:
            command += ["--effort", self.effort]

        return command

    def complete(self, messages: list[dict], timeout: float | None = None):

        if _TRIPPED:
            raise UsageCeiling(_TRIPPED[0])

        system, prompt = _flatten(messages)
        env = {key: value for key, value in os.environ.items() if key not in API_BILLING_ENV}
        limit = ceiling()
        deadline = timeout or self.timeout

        started = time.perf_counter()
        process = subprocess.Popen(
            self.command(system), cwd=self._cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        # The prompt on stdin, not argv: an article and its evidence are long.
        killer = threading.Timer(deadline, process.kill)
        killer.start()

        init: dict = {}
        result: dict = {}
        usage_after: dict = {}
        stopped = None

        try:
            process.stdin.write(prompt)
            process.stdin.close()

            for line in process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue

                kind = event.get("type")

                if kind == "system" and event.get("subtype") == "init":
                    init = event
                    if event.get("apiKeySource") not in (None, "none"):
                        stopped = f"the call ran on an API key ({event.get('apiKeySource')}), not the subscription"

                elif kind == "rate_limit_event":
                    info = event.get("rate_limit_info") or {}
                    usage_after = windows(info) or usage_after
                    stopped = stop_reason(info, limit)

                elif kind == "result":
                    result = event

                if stopped:
                    process.kill()
                    break

            process.wait()
            stderr = process.stderr.read()
        finally:
            killer.cancel()

        seconds = round(time.perf_counter() - started, 3)
        self.last_utilization = usage_after
        usage = result.get("usage") or {}
        prompt_tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) or None

        _log({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": init.get("model") or self.alias,
            "effort": self.effort,
            "seconds": seconds,
            "promptTokens": prompt_tokens,
            "completionTokens": usage.get("output_tokens"),
            "apiEquivalentUsd": result.get("total_cost_usd"),
            "utilization": usage_after,
            "ok": bool(result) and not result.get("is_error") and not stopped,
            "stopped": stopped,
        })

        if stopped:
            trip(stopped)
            raise UsageCeiling(stopped)

        if not result:
            if seconds >= deadline - 0.5:
                raise APITimeoutError(request=_REQUEST)
            raise APIConnectionError(message=f"claude -p ended without a result: {stderr.strip()[:300]}", request=_REQUEST)

        if result.get("is_error"):
            text = str(result.get("result") or result.get("subtype"))
            # A usage limit reached mid-run comes back as an error result.
            if "limit" in text.lower() and ("usage" in text.lower() or "reset" in text.lower()):
                trip(f"the plan refused the call: {text[:200]}")
                raise UsageCeiling(text)
            raise APIConnectionError(message=f"claude -p: {text[:300]}", request=_REQUEST)

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=result.get("result") or ""), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=usage.get("output_tokens")),
            model=init.get("model"),
        )


def llm_client(model: str | None = None, timeout: float | None = None) -> LLMClient:
    """The harness's model client: headless Claude for `claude-headless:`, else LLMClient as always."""

    if not is_headless(model):
        return LLMClient(model=model, timeout=timeout)

    alias, effort = parse_model(model)

    return LLMClient(model=model, timeout=timeout, client=HeadlessClaudeTransport(alias, effort, timeout))


def provider(model: str | None, base_url: str) -> str | None:
    """What a run records as who served the model."""

    from src.evaluation.runner import provider_of

    return "claude.ai subscription (claude -p)" if is_headless(model) else provider_of(base_url)


def status() -> dict:
    """The plan's windows now, from one very short call (it costs that call)."""

    transport = HeadlessClaudeTransport("haiku")
    reply = transport.complete([
        {"role": "system", "content": "Reply with OK."},
        {"role": "user", "content": "OK?"},
    ])

    return {"reply": reply.choices[0].message.content, "utilization": transport.last_utilization, "ceiling": ceiling()}


if __name__ == "__main__":

    if sys.argv[1:] != ["status"]:
        raise SystemExit("usage: python -m src.evaluation.headless_claude status")

    os.environ.setdefault("HEADLESS_CLAUDE_LOG", os.devnull)

    try:
        print(json.dumps(status()))
    except UsageCeiling as stop:
        raise SystemExit(f"stopped: {stop}")

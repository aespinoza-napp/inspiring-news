"""
Token and latency accounting for every LLM call a benchmark makes.

Why it hooks in *under* LLMClient rather than beside it
-------------------------------------------------------

`LLMClient.complete_json` returns the parsed JSON and nothing else: the
provider's `usage` block (prompt and completion tokens) is on the raw
response, which never leaves the method. Rather than fork the client or
change what it returns to every caller, the harness wraps the OpenAI SDK
object the client already holds, after the client has built it. That
keeps everything the client decides - `max_retries=0`, the timeout, the
LLM permit, the JSON retry - exactly as production has it: the benchmark
measures the client the pipeline uses, not a copy of it.

Why calls are attributed by thread
----------------------------------

Claims run concurrently (`bounded_map`), and a claim's one LLM call is
made on the thread that runs that claim: `FactChecker._check_claim`
calls the verifier directly. So each worker opens an `attribute()` block
around its claim and every call made on that thread lands in that
claim's list. A call made anywhere else - which would mean the pipeline
moved the LLM call onto another thread - is not lost: it is counted as
unattributed, and the run manifest says how many there were.

Latency here is the provider's own answer time, measured inside the LLM
permit. The record's `latency.llm` (from the `verifying_claim` →
`claim_checked` events) also includes waiting for that permit, which is
the difference between a slow model and a busy one.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from src.services.llms import LLMClient


@dataclass(frozen=True)
class LLMCall:

    # Seconds from sending the request to having the response (or the
    # error), inside the LLM permit.
    latency: float

    # False when the call raised: never reached the provider, timed out,
    # or the provider answered with an error status.
    ok: bool

    # From the response's `usage` block. None when the provider sent
    # none - Ollama's OpenAI-compatible endpoint does send it, but not
    # every server behind an OpenAI-shaped URL does, and a missing count
    # must not read as zero tokens.
    prompt_tokens: int | None = None

    completion_tokens: int | None = None

    error: str | None = None


class UsageMeter:
    """Collects the LLM calls made by each unit of work (a claim, a text)."""

    def __init__(self):

        self._local = threading.local()
        self._lock = threading.Lock()
        self.unattributed: list[LLMCall] = []

    @contextmanager
    def attribute(self) -> Iterator[list[LLMCall]]:
        """Every call made on this thread inside the block lands in the list."""

        calls: list[LLMCall] = []

        previous = getattr(self._local, "calls", None)

        self._local.calls = calls

        try:
            yield calls
        finally:
            self._local.calls = previous

    def record(self, call: LLMCall) -> None:

        calls = getattr(self._local, "calls", None)

        if calls is not None:
            calls.append(call)
            return

        with self._lock:
            self.unattributed.append(call)


class _MeteredCompletions:

    def __init__(self, inner, meter: UsageMeter):

        self._inner = inner
        self._meter = meter

    def create(self, **kwargs):

        started = time.perf_counter()

        try:
            response = self._inner.create(**kwargs)
        except Exception as exc:
            self._meter.record(LLMCall(
                latency=time.perf_counter() - started,
                ok=False,
                error=type(exc).__name__,
            ))
            raise

        latency = time.perf_counter() - started

        usage = getattr(response, "usage", None)

        self._meter.record(LLMCall(
            latency=latency,
            ok=True,
            prompt_tokens=_tokens(usage, "prompt_tokens"),
            completion_tokens=_tokens(usage, "completion_tokens"),
        ))

        return response


class _MeteredChat:

    def __init__(self, inner, meter: UsageMeter):

        self.completions = _MeteredCompletions(inner.completions, meter)


class MeteredOpenAI:
    """
    The SDK client with `chat.completions.create` timed and its `usage`
    read. Anything else is passed through untouched.
    """

    def __init__(self, inner, meter: UsageMeter):

        self._inner = inner
        self.chat = _MeteredChat(inner.chat, meter)

    def __getattr__(self, name):

        return getattr(self._inner, name)


def metered(llm: LLMClient, meter: UsageMeter) -> LLMClient:
    """
    `llm`, with every call it makes recorded in `meter`. Returns the same
    object: the client stays the one the pipeline would have built.
    """

    llm._client = MeteredOpenAI(llm._client, meter)

    return llm


def _tokens(usage, name: str) -> int | None:

    if usage is None:
        return None

    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)

    return int(value) if isinstance(value, (int, float)) else None


def summarise(calls: list[LLMCall]) -> dict:
    """
    One unit of work's calls, as the result record holds them.

    Token totals are the sum of what was reported; `usageMissing` counts
    the successful calls that reported nothing, so a total built from
    half the calls says so instead of passing for the whole.
    """

    answered = [call for call in calls if call.ok]

    missing = sum(
        1 for call in answered
        if call.prompt_tokens is None or call.completion_tokens is None
    )

    reported = [call for call in answered if call.prompt_tokens is not None]

    return {
        "calls": len(calls),
        "failedCalls": len(calls) - len(answered),
        "promptTokens": sum(call.prompt_tokens or 0 for call in reported) if reported else None,
        "completionTokens": (
            sum(call.completion_tokens or 0 for call in reported) if reported else None
        ),
        "usageMissing": missing,
        "latency": round(sum(call.latency for call in calls), 4),
        "perCall": [
            {
                "latency": round(call.latency, 4),
                "ok": call.ok,
                "promptTokens": call.prompt_tokens,
                "completionTokens": call.completion_tokens,
                "error": call.error,
            }
            for call in calls
        ],
    }

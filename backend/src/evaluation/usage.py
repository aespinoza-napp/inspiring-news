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

Per provider
------------

The provider is whatever LLM_BASE_URL points at; nothing here knows its
name. `totals` sums a run (calls, tokens, latency, throughput) and `cost`
prices it from a prices file the user fills in on the day of the run
(`data/evaluation/prices.json`), because per-token prices change and a
remembered one is not a price. Ollama is priced at 0 there, explicitly:
its cost is the wall time, reported beside it.

docs/decisions/evaluation.md §Cost, latency and tokens.
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from src.evaluation.stats import median, percentile, rounded
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


# ----------------------------------------------------------------------
# A run's totals, and what they cost
# ----------------------------------------------------------------------


def totals(records: list[dict]) -> dict:
    """
    A run's LLM usage and time, summed over its units of work: claim
    records from the harness, text records from the writing benchmark.
    Each has `usage` (summarise's shape) and `latency.total`.

    Token means are over the units that reported tokens, so a provider
    that sends no usage block yields None rather than a mean of zeros.
    """

    usages = [record.get("usage") or {} for record in records]

    calls = [call for usage in usages for call in usage.get("perCall") or []]

    answered = [call for call in calls if call.get("ok")]

    reported = [usage for usage in usages if usage.get("promptTokens") is not None]

    prompt = sum(usage["promptTokens"] for usage in reported) if reported else None
    completion = (
        sum(usage.get("completionTokens") or 0 for usage in reported) if reported else None
    )

    # Throughput over calls that answered and said how much they wrote:
    # the number that tells a fast provider from a slow one.
    timed = [
        call for call in answered
        if call.get("completionTokens") is not None and call.get("latency")
    ]

    unit_latency = [
        record["latency"]["total"]
        for record in records
        if (record.get("latency") or {}).get("total") is not None
    ]

    call_latency = [call["latency"] for call in answered]

    return {
        "units": len(records),
        "llmCalls": len(calls),
        "failedCalls": len(calls) - len(answered),
        "unitsWithoutCalls": sum(1 for usage in usages if not usage.get("calls")),
        "promptTokens": prompt,
        "completionTokens": completion,
        "usageMissing": sum(usage.get("usageMissing") or 0 for usage in usages),
        "promptTokensPerUnit": rounded(prompt / len(reported), 1) if reported else None,
        "completionTokensPerUnit": rounded(completion / len(reported), 1) if reported else None,
        "llmSeconds": rounded(sum(call.get("latency") or 0 for call in calls), 2),
        "callLatency": {
            "median": rounded(median(call_latency), 3),
            "p90": rounded(percentile(call_latency, 90), 3),
            "max": rounded(max(call_latency), 3) if call_latency else None,
        },
        "unitLatency": {
            "median": rounded(median(unit_latency), 3),
            "p90": rounded(percentile(unit_latency, 90), 3),
            "total": rounded(sum(unit_latency), 2),
        },
        "completionTokensPerSecond": (
            rounded(
                sum(call["completionTokens"] for call in timed)
                / sum(call["latency"] for call in timed),
                1,
            )
            if timed else None
        ),
    }


def load_prices(path) -> dict:
    """
    `{model or "provider/model": {inputPerMTok, outputPerMTok, currency,
    source, asOf}}`. Prices are the user's to state, per run date: they
    change, and a figure remembered from training data is not a price.
    Keys starting with `_` are comments.
    """

    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    return {key: value for key, value in raw.items() if not key.startswith("_")}


def price_for(prices: dict | None, model: str, provider: str | None = None) -> dict | None:
    """The provider-qualified entry first: one model name, two hosts, two prices."""

    if not prices:
        return None

    if provider and f"{provider}/{model}" in prices:
        return prices[f"{provider}/{model}"]

    return prices.get(model)


def cost(run_totals: dict, price: dict | None) -> dict | None:
    """
    What the run's tokens cost at `price`, or None when either the price
    or the token counts are unknown - never a zero standing in for "we
    don't know". A local model is priced at 0 explicitly in the prices
    file; its real cost is the wall time beside it.
    """

    if not price:
        return None

    per_input = price.get("inputPerMTok")
    per_output = price.get("outputPerMTok")

    prompt = run_totals.get("promptTokens")
    completion = run_totals.get("completionTokens")

    if None in (per_input, per_output, prompt, completion):
        return None

    total = prompt / 1_000_000 * per_input + completion / 1_000_000 * per_output

    units = run_totals.get("units") or 0

    return {
        "currency": price.get("currency", "USD"),
        "total": round(total, 6),
        "per100Units": round(total / units * 100, 6) if units else None,
        "source": price.get("source"),
        "asOf": price.get("asOf"),
    }

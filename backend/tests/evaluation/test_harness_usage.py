"""
Token and latency accounting, hooked in under LLMClient so the client the
benchmark measures is the one the pipeline uses.
"""

import threading

from openai import APIConnectionError

from src.evaluation.usage import LLMCall, UsageMeter, metered, summarise
from src.services.llms import LLMUnavailableError

from tests.evaluation.support import stub_llm


def test_a_call_is_recorded_with_its_tokens_on_the_thread_that_made_it():

    meter = UsageMeter()

    llm = metered(stub_llm({"verdict": "TRUE"}, usage=(500, 40)), meter)

    with meter.attribute() as calls:
        assert llm.complete_json("system", "user") == {"verdict": "TRUE"}

    assert len(calls) == 1
    assert (calls[0].prompt_tokens, calls[0].completion_tokens, calls[0].ok) == (500, 40, True)
    assert calls[0].latency >= 0
    assert meter.unattributed == []


def test_the_json_retry_is_two_calls_and_both_are_counted():
    """A model that fails the format costs twice; the bill should say so."""

    meter = UsageMeter()

    llm = metered(stub_llm("not json at all", usage=(300, 20)), meter)

    with meter.attribute() as calls:
        assert llm.complete_json("system", "user", max_retries=1) is None

    summary = summarise(calls)

    assert summary["calls"] == 2
    assert summary["promptTokens"] == 600
    assert summary["completionTokens"] == 40


def test_an_unreachable_provider_is_a_failed_call_with_no_tokens(monkeypatch):

    monkeypatch.setattr("src.services.llms.time.sleep", lambda seconds: None)

    meter = UsageMeter()

    llm = metered(stub_llm(APIConnectionError(request=None)), meter)

    with meter.attribute() as calls:
        try:
            llm.complete_json("system", "user", max_retries=1)
        except LLMUnavailableError:
            pass

    summary = summarise(calls)

    assert summary["calls"] == 2
    assert summary["failedCalls"] == 2
    assert summary["promptTokens"] is None
    assert [call["error"] for call in summary["perCall"]] == ["APIConnectionError"] * 2


def test_a_missing_usage_block_is_not_zero_tokens():

    meter = UsageMeter()

    llm = metered(stub_llm({"ok": True}, usage=None), meter)

    with meter.attribute() as calls:
        llm.complete_json("system", "user")

    summary = summarise(calls)

    assert summary["promptTokens"] is None
    assert summary["usageMissing"] == 1


def test_calls_on_concurrent_threads_land_on_their_own_unit():

    meter = UsageMeter()

    llm = metered(stub_llm({"ok": True}, usage=(10, 1)), meter)

    counts = {}

    def work(name, n):
        with meter.attribute() as calls:
            for _ in range(n):
                llm.complete_json("system", "user")
        counts[name] = len(calls)

    threads = [threading.Thread(target=work, args=(f"t{n}", n)) for n in (1, 2, 3)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert counts == {"t1": 1, "t2": 2, "t3": 3}


def test_a_call_outside_any_unit_is_kept_as_unattributed():

    meter = UsageMeter()

    llm = metered(stub_llm({"ok": True}), meter)

    llm.complete_json("system", "user")

    assert len(meter.unattributed) == 1


def test_summarise_with_no_calls():

    assert summarise([]) == {
        "calls": 0,
        "failedCalls": 0,
        "promptTokens": None,
        "completionTokens": None,
        "usageMissing": 0,
        "latency": 0,
        "perCall": [],
    }


def test_summarise_sums_only_reported_tokens():

    summary = summarise([
        LLMCall(latency=1.0, ok=True, prompt_tokens=100, completion_tokens=10),
        LLMCall(latency=2.0, ok=True),
        LLMCall(latency=0.5, ok=False, error="APITimeoutError"),
    ])

    assert summary["promptTokens"] == 100
    assert summary["completionTokens"] == 10
    assert summary["usageMissing"] == 1
    assert summary["failedCalls"] == 1
    assert summary["latency"] == 3.5

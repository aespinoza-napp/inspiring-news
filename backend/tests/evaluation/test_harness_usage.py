"""
Token and latency accounting, hooked in under LLMClient so the client the
benchmark measures is the one the pipeline uses.
"""

import threading

from openai import APIConnectionError

from src.evaluation.usage import (
    LLMCall,
    UsageMeter,
    cost,
    load_prices,
    metered,
    price_for,
    summarise,
    totals,
)
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


# ----------------------------------------------------------------------
# A run's totals and cost, per provider
# ----------------------------------------------------------------------


def unit(total, *calls):
    """A record as totals() reads it: usage (summarise's shape) and latency."""

    return {"usage": summarise(list(calls)), "latency": {"total": total}}


def test_totals_sum_a_run_by_hand():

    records = [
        unit(10.0, LLMCall(latency=4.0, ok=True, prompt_tokens=1000, completion_tokens=100)),
        unit(20.0,
             LLMCall(latency=1.0, ok=False, error="APITimeoutError"),
             LLMCall(latency=6.0, ok=True, prompt_tokens=2000, completion_tokens=200)),
        # Below the evidence floor: the model was never asked.
        unit(3.0),
    ]

    result = totals(records)

    assert result["units"] == 3
    assert result["llmCalls"] == 3
    assert result["failedCalls"] == 1
    assert result["unitsWithoutCalls"] == 1
    assert result["promptTokens"] == 3000
    assert result["completionTokens"] == 300
    # Means over the two units that reported tokens.
    assert result["promptTokensPerUnit"] == 1500
    assert result["completionTokensPerUnit"] == 150
    assert result["llmSeconds"] == 11.0
    # Answered calls only: 4.0 and 6.0.
    assert result["callLatency"] == {"median": 5.0, "p90": 5.8, "max": 6.0}
    # 3, 10, 20: median 10, p90 = 10 + 0.8 * 10.
    assert result["unitLatency"] == {"median": 10.0, "p90": 18.0, "total": 33.0}
    # 300 tokens over 10 seconds of answered calls.
    assert result["completionTokensPerSecond"] == 30.0


def test_totals_of_a_provider_that_sends_no_usage_are_unknown_not_zero():

    result = totals([unit(5.0, LLMCall(latency=2.0, ok=True))])

    assert result["promptTokens"] is None
    assert result["completionTokensPerSecond"] is None
    assert result["usageMissing"] == 1


def test_cost_prices_tokens_per_million():

    run = {"units": 4, "promptTokens": 2_000_000, "completionTokens": 500_000}

    priced = cost(run, {"inputPerMTok": 0.05, "outputPerMTok": 0.08, "asOf": "2026-11-10"})

    # 2 x 0.05 + 0.5 x 0.08
    assert priced["total"] == 0.14
    assert priced["per100Units"] == 3.5
    assert priced["currency"] == "USD"
    assert priced["asOf"] == "2026-11-10"


def test_an_unknown_price_or_unknown_tokens_is_no_cost_rather_than_zero():

    run = {"units": 1, "promptTokens": 10, "completionTokens": 1}

    assert cost(run, None) is None
    assert cost(run, {"inputPerMTok": None, "outputPerMTok": 0.08}) is None
    assert cost({"units": 1, "promptTokens": None, "completionTokens": None},
                {"inputPerMTok": 0, "outputPerMTok": 0}) is None

    # A local model, priced at zero on purpose, is a real zero.
    assert cost(run, {"inputPerMTok": 0, "outputPerMTok": 0})["total"] == 0


def test_a_provider_qualified_price_wins_over_the_bare_model_name():

    prices = {
        "llama-3.1-8b": {"inputPerMTok": 0},
        "api.groq.com/llama-3.1-8b": {"inputPerMTok": 0.05},
    }

    assert price_for(prices, "llama-3.1-8b", "api.groq.com")["inputPerMTok"] == 0.05
    assert price_for(prices, "llama-3.1-8b", "localhost:11434")["inputPerMTok"] == 0
    assert price_for(prices, "other", "api.groq.com") is None
    assert price_for(None, "llama-3.1-8b") is None


def test_the_committed_prices_file_loads_without_its_comment():

    from pathlib import Path

    prices = load_prices(Path(__file__).resolve().parents[2] / "data" / "evaluation" / "prices.json")

    assert "_comment" not in prices
    assert prices["llama3.2:3b"]["inputPerMTok"] == 0

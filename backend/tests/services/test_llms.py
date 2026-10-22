import pytest
from openai import APIConnectionError

from src.services.llms import LLMClient, LLMUnavailableError


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeCompletion:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [FakeChoice(content, finish_reason)]


class Cut(str):
    """An answer the server stopped at max_tokens."""


class FakeCompletions:

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeCompletion(item, "length" if isinstance(item, Cut) else "stop")


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeOpenAIClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


def make_client(responses):
    return LLMClient(client=FakeOpenAIClient(responses))


def test_complete_json_parses_valid_json():

    client = make_client(['{"verdict": "TRUE", "confidence": 0.9}'])

    result = client.complete_json("system", "user")

    assert result == {"verdict": "TRUE", "confidence": 0.9}


def test_complete_json_extracts_json_wrapped_in_prose():

    client = make_client(['Sure, here you go:\n{"verdict": "FALSE"}\nHope that helps.'])

    result = client.complete_json("system", "user")

    assert result == {"verdict": "FALSE"}


def test_complete_json_retries_then_succeeds():

    client = make_client([
        "not json at all",
        '{"verdict": "UNVERIFIED"}',
    ])

    result = client.complete_json("system", "user", max_retries=1)

    assert result == {"verdict": "UNVERIFIED"}
    assert client._client.chat.completions.calls.__len__() == 2


def test_complete_json_returns_none_after_exhausting_retries():

    client = make_client(["still not json", "nope"])

    result = client.complete_json("system", "user", max_retries=1)

    assert result is None


def test_an_answer_cut_at_the_cap_is_not_asked_for_again():
    """
    A model that looped to max_tokens once loops again at temperature 0:
    the retry would spend a second cap's worth of tokens on the same None.
    """

    client = make_client([Cut('{"verdict": "TRUE", "assessments": [{"index": 0, "quote": "again and again'), '{"verdict": "TRUE"}'])

    result = client.complete_json("system", "user", max_retries=1, max_tokens=1024)

    assert result is None
    assert len(client._client.chat.completions.calls) == 1


def test_complete_json_raises_llm_unavailable_on_connection_error(monkeypatch):
    """
    A dead socket is not a verdict. Raising here - rather than returning
    None like a malformed response would - is what lets callers tell "the
    LLM was unreachable" apart from a genuine UNVERIFIED.
    """

    monkeypatch.setattr("src.services.llms.time.sleep", lambda _: None)

    client = make_client([
        APIConnectionError(request=None),
        APIConnectionError(request=None),
    ])

    with pytest.raises(LLMUnavailableError):
        client.complete_json("system", "user", max_retries=1)


def test_complete_json_backs_off_between_retries(monkeypatch):

    sleeps = []
    monkeypatch.setattr("src.services.llms.time.sleep", sleeps.append)

    client = make_client([
        APIConnectionError(request=None),
        '{"verdict": "TRUE"}',
    ])

    result = client.complete_json("system", "user", max_retries=1)

    assert result == {"verdict": "TRUE"}
    assert sleeps == [pytest.approx(0.5)]


def test_the_sdk_is_not_allowed_to_retry_on_its_own():
    """
    The OpenAI SDK retries timeouts twice by default, on top of
    complete_json's own retry: one slow claim could hold a worker for
    6 x LLM_TIMEOUT.
    """

    assert LLMClient()._client.max_retries == 0


def test_an_answer_cap_is_sent_only_when_asked_for():
    """Every caller before the writer sent none; their requests stay as they were."""

    client = make_client(['{"a": 1}', '{"a": 2}'])

    client.complete_json("system", "user")
    client.complete_json("system", "user", max_tokens=4096)

    calls = client._client.chat.completions.calls

    assert "max_tokens" not in calls[0]
    assert calls[1]["max_tokens"] == 4096


class Usage:
    def __init__(self, prompt_tokens):
        self.prompt_tokens = prompt_tokens


def with_usage(prompt_tokens):
    """A client whose one answer reports how many prompt tokens were evaluated."""

    client = make_client(['{"ok": true}'])

    completions = client._client.chat.completions
    create = completions.create

    def create_with_usage(**kwargs):
        completion = create(**kwargs)
        completion.usage = Usage(prompt_tokens)
        return completion

    completions.create = create_with_usage

    return client


def test_a_prompt_the_server_cut_is_logged(caplog):
    """
    Measured on Ollama 0.40.4 with no context configured: 30,000
    characters were evaluated as 2,050 tokens, and the answer said
    nothing of it.
    """

    with caplog.at_level("WARNING", logger="src.services.llms"):
        assert with_usage(2050).complete_json("s", "x" * 30000) == {"ok": True}

    assert "probably cut" in caplog.text


@pytest.mark.parametrize("prompt_tokens, chars", [(7500, 30000), (300, 2000), (None, 30000)])
def test_a_prompt_evaluated_whole_or_too_short_to_judge_is_not(caplog, prompt_tokens, chars):

    with caplog.at_level("WARNING", logger="src.services.llms"):
        with_usage(prompt_tokens).complete_json("s", "x" * chars)

    assert "probably cut" not in caplog.text


def test_a_hybrid_reasoning_model_is_told_not_to_think(monkeypatch):
    """
    Qwen3.5 thinks before every answer unless the request says otherwise,
    and has no prompt switch for it. LLM_REASONING_EFFORT names the
    models that get one; every other model's request is unchanged.
    """

    from src.config.settings import settings

    monkeypatch.setattr(settings, "LLM_REASONING_EFFORT", {"qwen3.5:4b": "none"})

    writer = LLMClient(model="qwen3.5:4b", client=FakeOpenAIClient(['{"title": "T"}']))
    verifier = LLMClient(model="llama3.2:3b", client=FakeOpenAIClient(['{"verdict": "TRUE"}']))

    writer.complete_json("system", "user")
    verifier.complete_json("system", "user")

    assert writer._client.chat.completions.calls[0]["extra_body"] == {"reasoning_effort": "none"}
    assert "extra_body" not in verifier._client.chat.completions.calls[0]


# ----------------------------------------------------------------------
# A claim's deadline, and what a call cost (2026-10-22)
# ----------------------------------------------------------------------


def test_a_timeout_is_sent_with_the_request_only_when_given():
    """
    The claim's deadline reaches the request itself, so the server is
    left when time is up rather than after LLM_TIMEOUT.
    """

    client = make_client(['{"a": 1}', '{"b": 2}'])

    client.complete_json("s", "u")
    client.complete_json("s", "u", timeout=12.0)

    calls = client._client.chat.completions.calls

    assert "timeout" not in calls[0]
    assert 1.0 <= calls[1]["timeout"] <= 12.0


def test_a_model_busy_past_the_deadline_is_unavailable_not_a_verdict(monkeypatch):
    """
    Another claim's call holds the one permit for longer than this claim
    has left: the claim is "not checked" (LLMUnavailableError), and the
    model is never asked.
    """

    from src.services import llms
    from src.services.concurrency import BoundedResource

    resource = BoundedResource("llm", 1)
    monkeypatch.setattr(llms, "LLM", resource)

    client = make_client(['{"verdict": "TRUE"}'])

    with resource.permit():
        with pytest.raises(LLMUnavailableError, match="within"):
            client.complete_json("s", "u", timeout=1.2)

    assert client._client.chat.completions.calls == []
    assert LLMClient.last_call()["wait"] >= 1.0


def test_no_time_left_at_all_is_unavailable_without_asking():

    client = make_client(['{"verdict": "TRUE"}'])

    with pytest.raises(LLMUnavailableError):
        client.complete_json("s", "u", timeout=0.2)

    assert client._client.chat.completions.calls == []


class TokenUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


def test_the_last_call_says_what_it_cost():
    """
    What the live view shows for a claim's model call: the queue, the
    call's own seconds, and the tokens the server read and wrote.
    """

    client = make_client(['{"ok": true}'])

    completions = client._client.chat.completions
    create = completions.create

    def create_with_usage(**kwargs):
        completion = create(**kwargs)
        completion.usage = TokenUsage(512, 48)
        return completion

    completions.create = create_with_usage

    client.complete_json("s", "u")

    call = LLMClient.last_call()

    assert call["model"] == client.model
    assert call["promptTokens"] == 512
    assert call["completionTokens"] == 48
    assert call["seconds"] >= 0.0
    assert call["wait"] >= 0.0

from openai import APIConnectionError

from src.services.llms import LLMClient


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeCompletion(item)


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


def test_complete_json_returns_none_on_connection_error():

    client = make_client([
        APIConnectionError(request=None),
        APIConnectionError(request=None),
    ])

    result = client.complete_json("system", "user", max_retries=1)

    assert result is None

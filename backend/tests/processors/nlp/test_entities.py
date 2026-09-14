"""
EntityExtractor is now an Adapter over InferenceClient - GLiNER itself
moved to inference/tests/test_entities.py, which tests the real model.
This tests the adapter: it calls the client with the right arguments
and degrades to {} rather than raising when the client returns None.
"""

from src.processors.nlp.entities import EntityExtractor


class _StubClient:

    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def entities(self, text, threshold=None, labels=None):
        self.calls.append((text, threshold, labels))
        return self.result


def test_process_delegates_to_the_client_with_the_effective_threshold():

    client = _StubClient(result={"company": ["Apple"], "city": ["Barcelona"]})

    extractor = EntityExtractor(threshold=0.42, client=client)

    entities = extractor.process("Apple announced a product in Barcelona.")

    assert entities == {"company": ["Apple"], "city": ["Barcelona"]}

    [(text, threshold, labels)] = client.calls
    assert text == "Apple announced a product in Barcelona."
    assert threshold == 0.42
    assert labels == extractor.labels


def test_a_per_call_threshold_overrides_the_instance_default():

    client = _StubClient(result={})

    extractor = EntityExtractor(threshold=0.5, client=client)

    extractor.process("some text", threshold=0.9)

    [(_, threshold, _)] = client.calls
    assert threshold == 0.9


def test_degrades_to_empty_dict_when_the_client_returns_none():
    """
    Mirrors LLMClient's None-on-failure contract: ClaimExtractor's
    scoring already treats "no entities" as one weak signal among
    several, not a hard failure, so an inference outage should weaken a
    sentence's score rather than take down the whole enrichment pass.
    """

    extractor = EntityExtractor(client=_StubClient(result=None))

    assert extractor.process("some text") == {}


def test_empty_text_short_circuits_without_calling_the_client():

    client = _StubClient(result={"person": ["someone"]})

    extractor = EntityExtractor(client=client)

    assert extractor.process("") == {}
    assert client.calls == []

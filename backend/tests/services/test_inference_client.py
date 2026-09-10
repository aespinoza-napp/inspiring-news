"""
InferenceClient translates between backend's calls and the inference/
service's wire format, without needing that service running - httpx's
MockTransport intercepts the request and returns a canned response.
"""

import httpx
import pytest

from src.services.inference_client import InferenceClient, InferenceUnavailable


def _client(handler) -> InferenceClient:

    transport = httpx.MockTransport(handler)

    return InferenceClient(client=httpx.Client(transport=transport, base_url="http://inference"))


def test_entities_posts_the_expected_body_and_returns_the_dict():

    import json as jsonlib

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json={"entities": {"person": ["Ada"]}})

    result = _client(handler).entities("Ada Lovelace", threshold=0.6, labels=["person"])

    assert result == {"person": ["Ada"]}
    assert seen["path"] == "/entities"
    assert seen["body"] == {"text": "Ada Lovelace", "threshold": 0.6, "labels": ["person"]}


def test_entities_returns_none_on_a_server_error_rather_than_raising():

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    assert _client(handler).entities("text") is None


def test_entities_returns_none_when_the_service_is_unreachable():

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    assert _client(handler).entities("text") is None


def test_sentiment_returns_the_parsed_json():

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "label": "positive", "positive": 0.7, "neutral": 0.2, "negative": 0.1,
            "polarity": 0.6, "subjectivity": 0.3, "confidence": 0.7,
            "emotional_intensity": 0.6,
        })

    result = _client(handler).sentiment("great news")

    assert result["label"] == "positive"


def test_sentiment_raises_inference_unavailable_on_failure():

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(InferenceUnavailable):
        _client(handler).sentiment("text")


def test_encode_returns_vector_and_dimension_from_one_call():

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": [0.1, 0.2], "dimension": 2})

    vector, dimension = _client(handler).encode("text")

    assert vector == [0.1, 0.2]
    assert dimension == 2


def test_encode_many_returns_vectors_and_dimension():

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]], "dimension": 2})

    vectors, dimension = _client(handler).encode_many(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert dimension == 2


def test_encode_raises_inference_unavailable_on_a_timeout():

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    with pytest.raises(InferenceUnavailable):
        _client(handler).encode("text")

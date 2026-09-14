"""
Moved from backend/tests/processors/nlp/test_entities.py - this is
where the real GLiNER model lives now.
backend/tests/processors/nlp/test_entities.py tests the HTTP-adapter
behaviour instead (mocked transport), and relies on
tests/services/fact_checker/fakes.py's FakeEntityExtractor for
everything downstream.
"""

from src.entities import EntityModel


def test_entity_extraction():

    model = EntityModel()
    model.load()

    text = """
    Apple announced a new iPhone during an event in
    Barcelona. Tim Cook presented the device.
    """

    entities = model.extract(text)

    assert isinstance(entities, dict)

    total = sum(len(v) for v in entities.values())

    assert total > 0

    flattened = [entity for values in entities.values() for entity in values]

    assert "Apple" in flattened

    assert "Barcelona" in flattened


def test_entity_extraction_returns_empty_dict_for_empty_text():

    model = EntityModel()
    model.load()

    assert model.extract("") == {}

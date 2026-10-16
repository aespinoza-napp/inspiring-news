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


def test_a_long_text_is_cut_into_sentence_bounded_chunks():
    """No model needed: the rule that keeps every piece under GLiNER's limit."""

    from src.entities import CHUNK_WORDS, chunks

    short = "Apple opened a store in Barcelona."
    assert chunks(short) == [short]

    sentence = " ".join(["word"] * 40) + "."
    text = " ".join([sentence] * 20)            # 800 words, 20 sentences
    pieces = chunks(text)

    assert len(pieces) > 1
    assert all(len(piece.split()) <= CHUNK_WORDS for piece in pieces)
    assert all(piece.endswith(".") for piece in pieces)
    assert " ".join(pieces).split() == text.split()

    run_on = " ".join(["word"] * (CHUNK_WORDS * 2 + 10))
    assert [len(p.split()) for p in chunks(run_on)] == [CHUNK_WORDS, CHUNK_WORDS, 10]


def test_entities_past_the_models_input_limit_are_found():
    """
    GLiNER reads at most 384 tokens and truncated a whole article to its
    opening, with only a warning: a name in the last paragraph of a long
    article was never found.
    """

    model = EntityModel()
    model.load()

    filler = "The committee met again to review the annual figures in detail. " * 60
    text = "Apple announced a new phone. " + filler + "Tim Cook presented it in Barcelona."

    flattened = [e for values in model.extract(text).values() for e in values]

    assert "Apple" in flattened
    assert "Barcelona" in flattened


def test_several_texts_get_their_own_entities_in_one_call():

    model = EntityModel()
    model.load()

    texts = ["Apple opened a store in Barcelona.", "", "Tim Cook visited Madrid."]
    many = model.extract_many(texts)

    assert len(many) == 3
    assert many[1] == {}
    assert many[0] == model.extract(texts[0])
    assert many[2] == model.extract(texts[2])

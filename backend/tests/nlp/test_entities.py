from src.processors.nlp.entities import EntityExtractor


def test_entity_extraction():

    extractor = EntityExtractor()

    text = """
    Apple announced a new iPhone during an event in
    Barcelona. Tim Cook presented the device.
    """

    entities = extractor.process(text)
    print(f"Extracted entities: {entities}")
    print(f"Processor {extractor.name} extracted {len(entities)} entities")
    print(entities)

    assert isinstance(entities, dict)

    total = sum(
        len(v)
        for v in entities.values()
    )

    assert total > 0

    flattened = [
        entity
        for values in entities.values()
        for entity in values
    ]

    assert "Apple" in flattened

    assert "Barcelona" in flattened

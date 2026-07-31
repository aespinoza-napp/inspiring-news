
from src.processors.nlp.keywords import KeywordExtractor
from src.agents.fact_checker import FactChecker
from src.models.core.claim import Claim
import logging


def test_keyword_extractor():
    keyword_extractor = KeywordExtractor()
    text = "Apple announced a new iPhone during an event in Barcelona. Tim Cook presented the device."

    result = keyword_extractor.process(text)
    print(f"Extracted keywords: {result}")
    logger = logging.getLogger(__name__)
    logger.info(
        "Processor %s extracted %d keywords",
        keyword_extractor.name,
        len(result),
    )

    assert isinstance(result, list)
    assert len(result) > 0

test_keyword_extractor()
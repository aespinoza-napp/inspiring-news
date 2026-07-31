from unittest.mock import Mock

from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.extractor import ExtractorService

from tests.builders.source_builder import build_source


def make_extraction_result(**kwargs) -> ExtractionResult:

    defaults = dict(
        source_id="bbc",
        title="A title",
        body="x" * 600,
    )

    defaults.update(kwargs)

    return ExtractionResult(**defaults)


def test_first_strategy_success():

    service = ExtractorService()

    first = Mock()
    first.extract.return_value = make_extraction_result()

    second = Mock()

    service.strategies = [first, second]

    news = service.extract(build_source(), "https://bbc.com/a")

    assert news is not None
    assert news.title == "A title"

    second.extract.assert_not_called()


def test_fallback_strategy():

    service = ExtractorService()

    first = Mock()
    first.extract.return_value = None

    second = Mock()
    second.extract.return_value = make_extraction_result(title="Fallback title")

    service.strategies = [first, second]

    news = service.extract(build_source(), "https://bbc.com/a")

    assert news is not None
    assert news.title == "Fallback title"


def test_skips_strategy_result_that_fails_validation():

    service = ExtractorService()

    first = Mock()
    first.extract.return_value = make_extraction_result(body="too short")

    second = Mock()
    second.extract.return_value = make_extraction_result(title="Valid one")

    service.strategies = [first, second]

    news = service.extract(build_source(), "https://bbc.com/a")

    assert news is not None
    assert news.title == "Valid one"


def test_returns_none_when_no_strategy_succeeds():

    service = ExtractorService()

    strategy = Mock()
    strategy.extract.return_value = None

    service.strategies = [strategy]

    assert service.extract(build_source(), "https://bbc.com/a") is None

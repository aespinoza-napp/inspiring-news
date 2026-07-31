from src.agents.fact_checker import FactChecker
from src.models.core.claim import Claim


def test_fact_checker():
    checker = FactChecker()

    result = checker.verify(
        Claim(
            text="This fake article",
            entities=[],
            confidence=1.0,
        )
    )

    assert result.verdict == "FALSE"
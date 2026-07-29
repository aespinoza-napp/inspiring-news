from src.models.sentiment_result import SentimentResult
from src.processors.nlp.quality import ArticleQualityAnalyzer


def test_article_quality():

    analyzer = ArticleQualityAnalyzer()

    text = """
    Scientists from the World Health Organization developed a
    revolutionary vaccine that significantly improves the survival
    rate of children with a rare disease.

    The treatment has already benefited over 3.2 million of patients
    across Europe and researchers expect it to save many more lives
    in the coming years.
    """

    sentiment = SentimentResult(
        label="positive",
        positive=0.91,
        neutral=0.08,
        negative=0.01,
        polarity=0.90,
        subjectivity=0.45,
        confidence=0.91,
        emotional_intensity=0.90,
    )

    entities = [
        "World Health Organization",
        "Europe",
    ]

    quality = analyzer.process(
        text,
        sentiment=sentiment,
        entities=entities,
        novelty=0.82,
    )

    #print(quality)

    assert isinstance(quality, dict)

    expected_keys = {
        "readability",
        "objectivity",
        "constructiveness",
        "hopefulness",
        "societal_impact",
        "inspirational_score",
        "novelty",
    }

    assert expected_keys == set(quality.keys())

    for metric, value in quality.items():

        assert isinstance(value, float)

        assert 0.0 <= value <= 1.0
        print(f"{metric}: {value}")

    # Expected behavior for this article
    #assert quality["constructiveness"] > 0.5
    #assert quality["hopefulness"] > 0.5
    #assert quality["inspirational_score"] > 0.5
    #assert quality["societal_impact"] > 0.3
    #assert quality["novelty"] == 0.82

test_article_quality()
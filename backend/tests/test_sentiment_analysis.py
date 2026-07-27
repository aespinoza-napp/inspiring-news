from src.processors.nlp.sentiment import SentimentAnalyzer

def test_sentiment_analsyis():
    analyzer = SentimentAnalyzer()

    score = analyzer.process(
        "The company reported excellent results and investors were delighted."
    )

    assert score == 0.85
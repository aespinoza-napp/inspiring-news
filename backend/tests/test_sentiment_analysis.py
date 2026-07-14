from src.processors.sentiment_analysis import SentimentAnalyzer

def test_sentiment_analsyis():
    analyzer = SentimentAnalyzer()

    score = analyzer.analyze(
        "The company reported excellent results and investors were delighted."
    )

    assert score == 0.85
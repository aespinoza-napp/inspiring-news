from dataclasses import dataclass

@dataclass
class SentimentResult:

    label: str

    positive: float

    neutral: float

    negative: float

    polarity: float

    subjectivity: float

    confidence: float

    emotional_intensity: float
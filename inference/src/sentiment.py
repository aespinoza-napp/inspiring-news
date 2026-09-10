"""
Sentiment analysis - moved here unchanged from
backend/src/processors/nlp/sentiment.py's SentimentAnalyzer. Same
model, same normalization, same math; only the caller now reaches it
over HTTP instead of a direct Python call.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from scipy.special import softmax
from textblob import TextBlob
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .config import settings


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


class SentimentModel:

    def __init__(self):
        self._model = None
        self._tokenizer = None

    def load(self) -> None:

        if self._model is None:
            self._model = AutoModelForSequenceClassification.from_pretrained(
                settings.SENTIMENT_MODEL
            )
            self._tokenizer = AutoTokenizer.from_pretrained(
                settings.SENTIMENT_MODEL
            )

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def analyze(self, text: str) -> SentimentResult:

        text = self._normalize(text)

        encoded = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.no_grad():
            output = self._model(**encoded)

        scores = softmax(output.logits[0].numpy())

        negative, neutral, positive = map(float, scores)

        polarity = positive - negative

        blob = TextBlob(text)

        subjectivity = float(blob.sentiment.subjectivity)

        confidence = max(positive, neutral, negative)

        emotional_intensity = abs(polarity)

        label = max(
            [
                ("negative", negative),
                ("neutral", neutral),
                ("positive", positive),
            ],
            key=lambda x: x[1],
        )[0]

        return SentimentResult(
            label=label,
            positive=round(positive, 4),
            neutral=round(neutral, 4),
            negative=round(negative, 4),
            polarity=round(polarity, 4),
            subjectivity=round(subjectivity, 4),
            confidence=round(confidence, 4),
            emotional_intensity=round(emotional_intensity, 4),
        )

    @staticmethod
    def _normalize(text: str) -> str:

        words = []

        for word in text.split():

            if word.startswith("@"):
                words.append("@user")
            elif word.startswith("http"):
                words.append("http")
            else:
                words.append(word)

        return " ".join(words)


sentiment_model = SentimentModel()

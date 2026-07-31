"""
Sentiment analysis processor.

Outputs:
    - positive score
    - neutral score
    - negative score
    - polarity
    - subjectivity
    - confidence
    - emotional intensity
"""

from __future__ import annotations

from src.models.nlp.sentiment_result import SentimentResult

import torch
from scipy.special import softmax
from textblob import TextBlob
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

from .base import BaseProcessor

class SentimentAnalyzer(BaseProcessor):

    def __init__(self, cfg):

        self.model = AutoModelForSequenceClassification.from_pretrained(
            cfg.SENTIMENT_MODEL
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            cfg.SENTIMENT_MODEL
        )

    def process(
        self,
        text: str,
    ) -> SentimentResult:

        text = self._normalize(text)

        encoded = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.no_grad():

            output = self.model(**encoded)

        scores = softmax(
            output.logits[0].numpy()
        )

        negative, neutral, positive = map(float, scores)

        polarity = positive - negative

        blob = TextBlob(text)

        subjectivity = float(
            blob.sentiment.subjectivity
        )

        confidence = max(
            positive,
            neutral,
            negative,
        )

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

            emotional_intensity=round(
                emotional_intensity,
                4,
            ),
        )

    def _normalize(
        self,
        text: str,
    ) -> str:

        words = []

        for word in text.split():

            if word.startswith("@"):

                words.append("@user")

            elif word.startswith("http"):

                words.append("http")

            else:

                words.append(word)

        return " ".join(words)
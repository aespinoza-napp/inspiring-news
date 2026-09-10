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

The model itself moved to inference/src/sentiment.py, including the
@user/http normalization - that's the model's own preprocessing quirk
(the underlying twitter-trained classifier expects those tokens, not
raw handles/URLs), not orchestration logic, so it stays with the model
rather than being duplicated here. This class is now an Adapter over
InferenceClient; `cfg` is still accepted (unused) so every existing
`SentimentAnalyzer(cfg)` call site needed no change.
"""

from __future__ import annotations

from src.models.nlp.sentiment_result import SentimentResult
from src.services.inference_client import InferenceClient

from .base import BaseProcessor


class SentimentAnalyzer(BaseProcessor):

    def __init__(self, cfg=None, client: InferenceClient | None = None):

        self._client = client or InferenceClient()

    def process(
        self,
        text: str,
    ) -> SentimentResult:
        """
        Raises InferenceUnavailable (propagated from InferenceClient) on
        failure, rather than degrading - NewsEnrichmentPipeline.process
        feeds this straight into PositiveImpactValidator's admission
        gate, which reads sentiment.positive/negative as core scoring
        inputs. A silently neutral/zeroed SentimentResult here would
        corrupt that decision rather than just weaken one signal, so a
        visibly failed analysis (propagating up through
        AnalysisService's existing per-URL try/except) is the safer
        outcome. Contrast with EntityExtractor, which degrades to {}.
        """

        result = self._client.sentiment(text)

        return SentimentResult(**result)
"""
The article's IPTC Media Topic, from a classifier trained on MN-DS (2026-11-17).

MN-DS (Petukhova & Fachada, Data 2023, CC BY 4.0): 10,917 English news articles
hand-labelled with the 17 first-level IPTC Media Topics, the news industry's own
taxonomy; its Spanish half is the same articles machine-translated (OPUS-MT,
translate-train), since no human-labelled Spanish set covers the app's groups.
scripts/train_iptc_topics.py trains multinomial logistic regression on bge-m3
vectors of each article's title and first 80 words, and writes the weights
(17 x 1024, ~70 KB) to data/models/iptc_topics.npz. Scoring them is a dot
product: no model is loaded here (invariant 13); the vector comes from
inference/ like every other embedding.

`GROUP_OF_IPTC` is the table fixed before any result in
data/evaluation/experiments/topics_iptc/rule.md: the IPTC category an article is
about, read as one of the app's five groups, or none for what is off the mission.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL = Path(__file__).resolve().parents[3] / "data" / "models" / "iptc_topics.npz"

LEAD_WORDS = 80

GROUP_OF_IPTC = {
    "environment": "environment",
    "weather": "environment",
    "science and technology": "science",
    "health": "health",
    "arts, culture, entertainment and media": "culture",
    "human interest": "culture",
    "education": "society",
    "society": "society",
    "labour": "society",
}


@dataclass(frozen=True)
class IptcTopic:

    category: str

    probability: float

    # One of the app's five groups, or None: off the mission (politics,
    # crime, sport...) or no group (lifestyle and leisure).
    group: str | None

    def as_dict(self) -> dict:
        return {"category": self.category, "probability": round(self.probability, 4), "group": self.group}


def lead(title: str | None, body: str | None) -> str:
    """What the classifier was trained on: the title and the first 80 words."""

    words = (body or "").split()[:LEAD_WORDS]
    return f"{(title or '').strip()}. {' '.join(words)}".strip(" .")


class IptcTopicClassifier:

    def __init__(self, path: Path = MODEL):
        self.path = path
        self._weights = None

    @property
    def available(self) -> bool:
        return self.path.exists()

    def _load(self):
        if self._weights is None:
            bundle = np.load(self.path, allow_pickle=False)
            self._weights = (bundle["coef"], bundle["intercept"], [str(c) for c in bundle["classes"]])
        return self._weights

    def predict(self, vector) -> list[IptcTopic]:
        """Every category for the lead's vector, most probable first."""

        coef, intercept, classes = self._load()
        scores = coef @ np.asarray(vector, dtype=np.float32) + intercept
        scores = np.exp(scores - scores.max())
        probabilities = scores / scores.sum()

        return [
            IptcTopic(category=classes[i], probability=float(probabilities[i]), group=GROUP_OF_IPTC.get(classes[i]))
            for i in np.argsort(-probabilities)
        ]

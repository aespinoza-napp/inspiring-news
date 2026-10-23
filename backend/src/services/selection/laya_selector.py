"""
The AI selection without the LLM: the fine-tuned Laya decision
`worth_offering` (D1, docs/decisions/laya.md) scores every candidate from
its title and summary, in `inference/`, in one request.

An option, not the default. Measured 2026-10-23 on another day's 117
candidates (data/evaluation/experiments/laya/results.md): it ties the 3B
LLM on "clearly positive" (AUC 0.805 against 0.782, interval across
zero), so by the rule written before the run it is not adopted; it is
better on "worth offering at all" (+0.14, interval above zero) and takes
~0.2 s a candidate on a CPU where the LLM takes minutes a round.

Same answer as AISelector.select, so the selection service, the round
and the page need nothing new. Its score is Laya's expected level on the
labels' own scale (0 not worth offering, 1 worth offering, 2 clearly
positive) times five, so it sits on the LLM's 0-10 scale and the same
`min_score` applies: 6 is a level of 1.2, past "worth offering" towards
"clearly positive".

It does not read the round's topic groups: the labels it learnt from
judged positive impact alone, and the round's candidates were already
found for those groups.
"""

from __future__ import annotations

import time

from src.config.decisions import WORTH_OFFERING, candidate_state
from src.services.inference_client import InferenceClient
from src.services.selection.ai_selector import DEFAULT_MIN_SCORE, AISelection, Scored

# The fine-tuned checkpoint's folder name in inference/'s checkpoints
# (scripts/laya_train_all.sh writes it there).
CHECKPOINT = "worth_offering"

LEVEL_TO_SCORE = 5.0


class LayaSelector:

    def __init__(self, client: InferenceClient | None = None):

        # Built on first use, as AISelector's LLM is.
        self._client = client

    @property
    def client(self) -> InferenceClient:

        if self._client is None:
            self._client = InferenceClient()

        return self._client

    def select(
        self,
        candidates: list[dict],
        groups: list[str],
        limit: int,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> AISelection:
        """
        Raises InferenceUnavailable when inference/ or the checkpoint is
        missing: like the LLM's, a selection that silently scored nothing
        would look like a judgement.
        """

        started = time.perf_counter()

        answers = self.client.decide_many(
            CHECKPOINT,
            [candidate_state(c.get("title") or c.get("url"), c.get("summary")) for c in candidates],
            {"worth_offering": WORTH_OFFERING},
        )

        scored = []

        for candidate, answer in zip(candidates, answers):

            level = answer["worth_offering"]["score"]
            scored.append(Scored(candidate["url"], round(level * LEVEL_TO_SCORE, 2), f"Laya: level {level:.2f} of 2"))

        ranked = sorted((item for item in scored if item.score >= min_score), key=lambda item: item.score, reverse=True)

        return AISelection(
            picks=ranked[:limit],
            scored=scored,
            model=f"laya:{CHECKPOINT}",
            calls=1 if candidates else 0,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )

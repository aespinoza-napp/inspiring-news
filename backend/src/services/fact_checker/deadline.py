"""
One claim's clock: when its check started, and how long it has left.

A claim with `claim_deadline_seconds` must be answered within it, search
to verdict (docs/decisions/performance.md, "The 20-second fact-check").
The stages share the budget in order: retrieval may spend up to
RETRIEVAL_SHARE of it, waiting for pages included, and the model gets
whatever is left. A page still loading at retrieval's cut keeps its
search snippet; a model that has not answered at the end leaves the
claim not checked, as an unreachable one does - never a verdict made up
against the clock.

Without a deadline every method answers None ("no limit"), and every
stage behaves as it did before deadlines existed.
"""

from __future__ import annotations

import time

# Retrieval's share of a claim's budget, the rest the model's. Reasoned
# from the 2026-10-19 medians (retrieval 9 s, ranking 5 s, the model's
# answer 34 s, of a 73 s claim): with fewer pages and a shorter answer
# both shrink, and half is room for each; past it a slow page costs more
# than the snippet it would replace.
RETRIEVAL_SHARE = 0.5

# Below this, a stage is not started at all: a model call with two
# seconds left cannot read its prompt, and would only hold the permit.
MIN_STAGE_SECONDS = 2.0


class Deadline:

    def __init__(self, seconds: float | int | None):

        self.seconds = float(seconds) if seconds else None
        self.started = time.monotonic()

    @property
    def active(self) -> bool:

        return self.seconds is not None

    def elapsed(self) -> float:

        return time.monotonic() - self.started

    def remaining(self) -> float | None:
        """Seconds left, never below 0; None without a deadline."""

        if self.seconds is None:
            return None

        return max(0.0, self.seconds - self.elapsed())

    def retrieval_left(self) -> float | None:
        """Seconds left of retrieval's share; None without a deadline."""

        if self.seconds is None:
            return None

        return max(0.0, self.seconds * RETRIEVAL_SHARE - self.elapsed())

    def exceeded(self) -> bool:

        return self.seconds is not None and self.elapsed() >= self.seconds

"""
The few order statistics the reports need, in plain Python.

No numpy: the harness's arithmetic is small (hundreds of claims, ten
thousand resamples), the backend image does not carry it, and a test can
check every one of these against a value worked out by hand.
"""

from __future__ import annotations

import math
import random
from typing import Sequence


def percentile(values: Sequence[float], q: float) -> float | None:
    """
    The q-th percentile (0-100) with linear interpolation between the two
    nearest ranks - numpy's default ("linear"), so a reader re-computing
    it with numpy gets the same number. None for no values.
    """

    if not values:
        return None

    if not 0 <= q <= 100:
        raise ValueError(f"percentile must be within 0-100, not {q}")

    ordered = sorted(values)

    position = (len(ordered) - 1) * q / 100

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return float(ordered[lower])

    weight = position - lower

    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def median(values: Sequence[float]) -> float | None:

    return percentile(values, 50)


def mean(values: Sequence[float]) -> float | None:

    return sum(values) / len(values) if values else None


def rounded(value: float | None, digits: int = 4) -> float | None:

    return None if value is None else round(value, digits)


def bootstrap_mean(
    values: Sequence[float],
    *,
    seed: int,
    resamples: int,
    level: float = 0.95,
) -> dict:
    """Percentile interval of a mean, resampling the values themselves."""

    if not values:
        return {"low": None, "high": None}

    rng = random.Random(seed)

    n = len(values)

    means = [
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(resamples)
    ]

    tail = (1 - level) / 2 * 100

    return {"low": percentile(means, tail), "high": percentile(means, 100 - tail)}


def paired_bootstrap_mean(
    a: Sequence[float],
    b: Sequence[float],
    *,
    seed: int,
    resamples: int,
    level: float = 0.95,
) -> dict:
    """Interval of mean(b) - mean(a), resampling the pairs together."""

    if len(a) != len(b):
        raise ValueError("paired values must line up")

    if not a:
        return {"difference": None, "low": None, "high": None}

    rng = random.Random(seed)

    n = len(a)

    differences = []

    for _ in range(resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        differences.append(sum(b[i] - a[i] for i in indices) / n)

    tail = (1 - level) / 2 * 100

    return {
        "difference": sum(b) / n - sum(a) / n,
        "low": percentile(differences, tail),
        "high": percentile(differences, 100 - tail),
    }

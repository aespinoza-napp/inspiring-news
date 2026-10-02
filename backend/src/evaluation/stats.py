"""
The few order statistics the reports need, in plain Python.

No numpy: the harness's arithmetic is small (hundreds of claims, ten
thousand resamples), the backend image does not carry it, and a test can
check every one of these against a value worked out by hand.
"""

from __future__ import annotations

import math
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

"""
What a run measured: outcomes set apart, leak flags, classification
metrics with bootstrap intervals, and the paired comparison of two runs.

Pure Python and deliberately small. A wrong metric is a wrong paper, so
every function here is tested against values worked out by hand
(tests/evaluation/test_harness_metrics.py).

docs/decisions/evaluation.md §What is reported apart, §Metrics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable, Sequence

from src.evaluation.stats import percentile

# The five verdicts, in the order every table uses.
CLASSES = ("TRUE", "PARTIALLY_TRUE", "MISLEADING", "FALSE", "UNVERIFIED")

UNVERIFIED = "UNVERIFIED"

# Outcomes: each claim gets exactly one. Only `scored` claims enter the
# headline metrics; the rest would otherwise measure SearXNG's uptime or
# the LLM host's, not the pipeline.
ERROR = "error"
SEARCH_UNAVAILABLE = "searchUnavailable"
LLM_UNREACHABLE = "llmUnreachable"
SCORED = "scored"

OUTCOMES = (ERROR, SEARCH_UNAVAILABLE, LLM_UNREACHABLE, SCORED)

DEFAULT_SEED = 2026
DEFAULT_RESAMPLES = 10_000
LEVEL = 0.95

Pair = tuple[str, str]


# ----------------------------------------------------------------------
# Outcomes and flags
# ----------------------------------------------------------------------


def outcome(record: dict) -> str:
    """
    The first that applies: a crash, then search, then the LLM. A claim
    whose search failed is set apart even when the internal corpus gave
    it a verdict - the web, which the pipeline is about, was never asked.
    """

    if record.get("status") != "ok":
        return ERROR

    if record.get("searchUnavailable"):
        return SEARCH_UNAVAILABLE

    if record.get("llmUnreachable"):
        return LLM_UNREACHABLE

    return SCORED


def _day(value) -> date | None:

    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def temporal_leak(record: dict) -> bool | None:
    """
    The guide's Rule 3: a *cited* source published after the claim was
    made. Undetermined (None) when the claim has no date - every one of
    the 40 chequeado pilot rows - or when a cited source has none and no
    dated one is newer. Same-day is not after.
    """

    claimed = _day(record.get("claimDate"))

    if claimed is None:
        return None

    cited = [item for item in record.get("evidence") or [] if item.get("cited")]

    dates = [_day(item.get("publishedAt")) for item in cited]

    if any(day is not None and day > claimed for day in dates):
        return True

    if any(day is None for day in dates):
        return None

    return False


def newer_uncited(record: dict) -> int:
    """Ranked, newer than the claim, but not cited: counted, never flagged."""

    claimed = _day(record.get("claimDate"))

    if claimed is None:
        return 0

    return sum(
        1
        for item in record.get("evidence") or []
        if not item.get("cited")
        and (_day(item.get("publishedAt")) or date.min) > claimed
    )


def on_site(domain: str | None, site: str | None) -> bool:
    """`domain` is `site` or one of its subdomains."""

    if not domain or not site:
        return False

    domain = domain.lower().removeprefix("www.")
    site = site.lower().removeprefix("www.")

    return domain == site or domain.endswith("." + site)


def verdict_leak(record: dict) -> bool | None:
    """
    x-fact only: a ranked source is on the row's own site, the
    fact-checker that published the verdict. A verdict read off that page
    is the answer retrieved, not a claim verified. None for the custom
    set, whose `site` is the article's publisher, not a fact-checker.
    """

    if record.get("dataset") != "xfact":
        return None

    return any(
        on_site(item.get("domain"), record.get("site"))
        for item in record.get("evidence") or []
    )


def flagged(record: dict) -> bool:

    return temporal_leak(record) is True or verdict_leak(record) is True


# ----------------------------------------------------------------------
# Classification metrics
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Counts:
    """Everything every metric below is a function of."""

    n: int

    correct: int

    gold: dict[str, int]

    predicted: dict[str, int]

    true_positive: dict[str, int]


def counts(pairs: Iterable[Pair]) -> Counts:

    gold = dict.fromkeys(CLASSES, 0)
    predicted = dict.fromkeys(CLASSES, 0)
    true_positive = dict.fromkeys(CLASSES, 0)

    n = correct = 0

    for expected, got in pairs:

        n += 1

        gold[expected] = gold.get(expected, 0) + 1
        predicted[got] = predicted.get(got, 0) + 1

        if expected == got:
            correct += 1
            true_positive[got] = true_positive.get(got, 0) + 1

    return Counts(n, correct, gold, predicted, true_positive)


def accuracy(c: Counts) -> float | None:

    return c.correct / c.n if c.n else None


def class_scores(c: Counts, label: str) -> dict:
    """
    Precision is undefined (None) for a class never predicted; recall and
    F1 for a class with no gold support, which is shown with its
    predictions and left out of macro-F1. F1 is 0 for a class with
    support of which nothing was got right.
    """

    tp = c.true_positive.get(label, 0)
    support = c.gold.get(label, 0)
    predicted = c.predicted.get(label, 0)

    precision = tp / predicted if predicted else None
    recall = tp / support if support else None

    if not support:
        f1 = None
    elif tp == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
        "predicted": predicted,
    }


def macro_f1(c: Counts, classes: Sequence[str]) -> float | None:
    """
    F1 averaged over `classes` - the classes present in the gold labels.
    A class with no gold support is shown with its predictions but not
    averaged in: the custom set has no FALSE yet, and averaging in a zero
    for it would punish the model for the dataset.
    """

    if not classes:
        return None

    return sum(
        (2 * c.true_positive.get(label, 0))
        / (c.gold.get(label, 0) + c.predicted.get(label, 0))
        if c.true_positive.get(label, 0) else 0.0
        for label in classes
    ) / len(classes)


def coverage(c: Counts) -> float | None:
    """The share of definitive verdicts: anything but UNVERIFIED."""

    return (c.n - c.predicted.get(UNVERIFIED, 0)) / c.n if c.n else None


def selective_accuracy(c: Counts) -> float | None:
    """
    Accuracy among the definitive verdicts. UNVERIFIED is the commonest
    answer of a small local model, and plain accuracy hides what it gets
    right when it does commit.
    """

    definitive = c.n - c.predicted.get(UNVERIFIED, 0)

    if not definitive:
        return None

    return (c.correct - c.true_positive.get(UNVERIFIED, 0)) / definitive


def cohen_kappa(c: Counts) -> float | None:
    """
    Agreement with the gold labels beyond what the two label
    distributions would agree on by chance - the labeller's own
    self-agreement statistic, so the system and the annotator are
    compared on one scale. Undefined when chance agreement is total.
    """

    if not c.n:
        return None

    expected = sum(
        c.gold.get(label, 0) * c.predicted.get(label, 0)
        for label in set(c.gold) | set(c.predicted)
    ) / (c.n * c.n)

    if expected == 1:
        return None

    return (c.correct / c.n - expected) / (1 - expected)


def confusion(pairs: Iterable[Pair]) -> dict[str, dict[str, int]]:
    """Gold rows by predicted columns."""

    matrix = {gold: dict.fromkeys(CLASSES, 0) for gold in CLASSES}

    for gold, predicted in pairs:
        matrix.setdefault(gold, dict.fromkeys(CLASSES, 0))
        matrix[gold][predicted] = matrix[gold].get(predicted, 0) + 1

    return matrix


def gold_classes(pairs: Iterable[Pair]) -> list[str]:

    present = {gold for gold, _ in pairs}

    return [label for label in CLASSES if label in present]


def statistics(classes: Sequence[str]) -> dict[str, Callable[[Counts], float | None]]:
    """The headline statistics, each a function of the counts alone."""

    return {
        "accuracy": accuracy,
        "macroF1": lambda c: macro_f1(c, classes),
        "coverage": coverage,
        "selectiveAccuracy": selective_accuracy,
        "kappa": cohen_kappa,
    }


def classification(pairs: Sequence[Pair]) -> dict:

    c = counts(pairs)

    classes = gold_classes(pairs)

    result = {name: fn(c) for name, fn in statistics(classes).items()}

    result.update({
        "n": c.n,
        "goldClasses": classes,
        "perClass": {label: class_scores(c, label) for label in CLASSES},
        "confusion": confusion(pairs),
    })

    return result


# ----------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------


def bootstrap(
    pairs: Sequence[Pair],
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    level: float = LEVEL,
) -> dict[str, dict]:
    """
    Percentile intervals over claims for every headline statistic, from
    one set of resamples. Seeded, so the same run gives the same
    interval. The class set macro-F1 averages over is the full sample's,
    so the statistic means the same thing in every resample.

    A resample in which a statistic is undefined (no definitive verdict,
    for selective accuracy) is skipped for that statistic and counted.
    """

    if not pairs:
        return {}

    stats = statistics(gold_classes(pairs))

    draws: dict[str, list[float]] = {name: [] for name in stats}

    rng = random.Random(seed)

    n = len(pairs)

    for _ in range(resamples):

        c = counts(pairs[rng.randrange(n)] for _ in range(n))

        for name, fn in stats.items():
            value = fn(c)
            if value is not None:
                draws[name].append(value)

    return {name: _interval(values, resamples, level) for name, values in draws.items()}


def paired_bootstrap(
    pairs_a: Sequence[Pair],
    pairs_b: Sequence[Pair],
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    level: float = LEVEL,
) -> dict[str, dict]:
    """
    The interval of the *difference* B - A, over the same claims resampled
    together: model A against B, or before and after the search fix. Two
    intervals that happen to overlap say much less than this one.

    `pairs_a[i]` and `pairs_b[i]` must be the same claim (same gold).
    """

    if len(pairs_a) != len(pairs_b):
        raise ValueError("a paired comparison needs the same claims on both sides")

    if any(a[0] != b[0] for a, b in zip(pairs_a, pairs_b)):
        raise ValueError("paired claims disagree on the gold label: not the same claims")

    if not pairs_a:
        return {}

    classes = gold_classes(pairs_a)

    stats = statistics(classes)

    point_a, point_b = counts(pairs_a), counts(pairs_b)

    differences: dict[str, list[float]] = {name: [] for name in stats}

    rng = random.Random(seed)

    n = len(pairs_a)

    for _ in range(resamples):

        indices = [rng.randrange(n) for _ in range(n)]

        a = counts(pairs_a[i] for i in indices)
        b = counts(pairs_b[i] for i in indices)

        for name, fn in stats.items():
            value_a, value_b = fn(a), fn(b)
            if value_a is not None and value_b is not None:
                differences[name].append(value_b - value_a)

    result = {}

    for name, fn in stats.items():

        value_a, value_b = fn(point_a), fn(point_b)

        result[name] = {
            "a": value_a,
            "b": value_b,
            "difference": (
                value_b - value_a if value_a is not None and value_b is not None else None
            ),
            **_interval(differences[name], resamples, level),
        }

    return result


def _interval(values: list[float], resamples: int, level: float) -> dict:

    tail = (1 - level) / 2 * 100

    return {
        "low": percentile(values, tail),
        "high": percentile(values, 100 - tail),
        "undefinedResamples": resamples - len(values),
    }


def discordant(pairs_a: Sequence[Pair], pairs_b: Sequence[Pair]) -> dict:
    """How many claims only A got right, and how many only B did."""

    only_a = sum(1 for a, b in zip(pairs_a, pairs_b) if a[0] == a[1] and b[0] != b[1])
    only_b = sum(1 for a, b in zip(pairs_a, pairs_b) if a[0] != a[1] and b[0] == b[1])

    return {"onlyA": only_a, "onlyB": only_b}

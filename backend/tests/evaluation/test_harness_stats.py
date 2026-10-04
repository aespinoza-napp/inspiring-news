"""Order statistics, against values worked out by hand (and numpy's "linear")."""

import pytest

from src.evaluation.stats import mean, median, percentile


def test_percentile_interpolates_between_the_nearest_ranks():

    values = [3, 1, 4, 1, 5]  # sorted: 1 1 3 4 5

    assert percentile(values, 0) == 1
    assert percentile(values, 100) == 5
    assert percentile(values, 50) == 3
    # position 4 * 0.25 = 1.0 -> the second value
    assert percentile(values, 25) == 1
    # position 4 * 0.9 = 3.6 -> 4 + 0.6 * (5 - 4)
    assert percentile(values, 90) == pytest.approx(4.6)
    # position 4 * 0.025 = 0.1 -> 1 + 0.1 * 0
    assert percentile(values, 2.5) == 1


def test_median_of_an_even_count_is_the_midpoint():

    assert median([1, 2, 3, 4]) == 2.5


def test_empty_inputs_have_no_statistic():

    assert percentile([], 50) is None
    assert median([]) is None
    assert mean([]) is None


def test_a_percentile_outside_0_to_100_is_an_error():

    with pytest.raises(ValueError):
        percentile([1, 2], 101)

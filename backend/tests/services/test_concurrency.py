"""
The two properties the whole parallel pipeline rests on: results come
back in input order, and a resource's ceiling is never exceeded.

Both are the kind of thing that works in every manual test and fails
once under load, so they are pinned here rather than trusted.
"""

import threading
import time

import pytest

from src.services.concurrency import BoundedResource, bounded_map


def test_results_come_back_in_input_order_not_completion_order():
    """
    The evidence list's indices are what the LLM cites by number and
    what `cited_evidence_indices` refers to afterwards. Results in
    completion order would silently re-point every citation at a
    different source - a wrong answer, not a crash.
    """

    def slow_for_the_first(value: int) -> int:
        # The first item finishes last, so anything ordering by
        # completion returns it last too.
        time.sleep(0.05 if value == 0 else 0.0)
        return value

    assert bounded_map(slow_for_the_first, range(6), max_workers=6) == [
        0, 1, 2, 3, 4, 5
    ]


def test_a_single_item_does_not_spawn_a_pool():
    """
    Not an optimisation - it keeps the one-claim and one-source paths
    running as plain synchronous code, which is what most of the suite
    exercises.
    """

    threads = set()

    bounded_map(
        lambda value: threads.add(threading.current_thread().name),
        [1],
        max_workers=4,
    )

    assert threads == {threading.current_thread().name}


def test_an_exception_propagates_rather_than_being_swallowed():

    def fail_on_three(value: int) -> int:
        if value == 3:
            raise ValueError("boom")
        return value

    with pytest.raises(ValueError, match="boom"):
        bounded_map(fail_on_three, range(6), max_workers=4)


def test_a_bounded_resource_never_admits_more_than_its_limit():
    """
    The reason the fan-out numbers can be chosen for clarity: the real
    ceiling is here. ANALYSIS_MAX_CONCURRENCY articles x
    CLAIM_MAX_CONCURRENCY claims x SCRAPE_MAX_CONCURRENCY pages is what
    would otherwise arrive at someone else's web server at once.
    """

    resource = BoundedResource("test", limit=3)

    lock = threading.Lock()
    inside = 0
    high_water = 0

    def work(_):

        nonlocal inside, high_water

        with resource.permit():

            with lock:
                inside += 1
                high_water = max(high_water, inside)

            time.sleep(0.02)

            with lock:
                inside -= 1

    bounded_map(work, range(20), max_workers=20)

    assert high_water <= 3
    assert inside == 0


def test_a_limit_of_zero_means_unbounded():
    """
    What tests want: a fake collaborator has no capacity problem, and a
    semaphore around one is only a way for a test to hang.
    """

    resource = BoundedResource("test", limit=0)

    with resource.permit():
        with resource.permit():
            assert resource.limit == 0


def test_a_permit_is_released_when_the_work_raises():
    """
    A permit leaked on the error path is a deadlock that only appears
    after something else has already gone wrong.
    """

    resource = BoundedResource("test", limit=1)

    with pytest.raises(ValueError):
        with resource.permit():
            raise ValueError("boom")

    # Still acquirable: if the permit leaked, this blocks forever.
    with resource.permit():
        pass


# ----------------------------------------------------------------------
# A deadline (2026-10-22): stop waiting, keep the order
# ----------------------------------------------------------------------


def test_with_a_timeout_an_unfinished_item_is_replaced_in_its_own_place():
    """
    A claim with a deadline waits for its pages only so long. The page
    still loading is replaced where it stood - its index is still the
    number the model cites - and the others are not held up by it.
    """

    release = threading.Event()

    def slow_for_the_second(value: int) -> str:
        if value == 1:
            release.wait(5)
        return f"page {value}"

    started = time.monotonic()

    try:
        results = bounded_map(
            slow_for_the_second,
            [0, 1, 2],
            max_workers=3,
            timeout=0.2,
            late=lambda value: f"snippet {value}",
        )
    finally:
        release.set()

    assert results == ["page 0", "snippet 1", "page 2"]
    assert time.monotonic() - started < 2


def test_a_timeout_also_bounds_a_single_item():
    """
    The one-item shortcut runs the item in the caller's thread, which no
    timeout can cut - so with a timeout there is no shortcut.
    """

    release = threading.Event()

    try:
        results = bounded_map(
            lambda value: release.wait(5) or value,
            [7],
            max_workers=1,
            timeout=0.1,
            late=lambda value: None,
        )
    finally:
        release.set()

    assert results == [None]


def test_a_timeout_without_a_stand_in_is_refused():

    with pytest.raises(ValueError):
        bounded_map(lambda value: value, [1, 2], max_workers=2, timeout=1.0)


def test_a_permit_not_free_in_time_raises_rather_than_waiting():
    """
    A claim with seconds left would rather be "not checked" than queue
    for the model past its deadline.
    """

    from src.services.concurrency import PermitTimeout

    resource = BoundedResource("one", 1)

    with resource.permit():
        with pytest.raises(PermitTimeout):
            with resource.permit(timeout=0.05):
                pass

    # And it was not left taken by the failed attempt.
    with resource.permit(timeout=0.05):
        pass

"""
Per-key limits held in memory: how often one visitor may do something
costly on a public route. Used by the news map's search (an embedding in
inference/) and by reader accounts (a password hash: 64 MiB and three
passes of argon2id). In memory, per process: a restart forgets them,
which costs a visitor at most one more window.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from typing import Callable


class RateLimited(Exception):

    def __init__(self, retry_after: float):
        super().__init__(f"too many searches; retry in {retry_after:.0f} s")
        self.retry_after = retry_after


class RateLimiter:
    """At most `limit` calls per `window` seconds per key; memory bounded by `max_keys`."""

    def __init__(self, limit: int, window: float = 60.0, max_keys: int = 10_000, clock: Callable[[], float] = time.monotonic):

        self.limit = limit
        self.window = window
        self.max_keys = max_keys
        self.clock = clock
        self._calls: OrderedDict[str, deque] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Counts the call, or raises RateLimited with when to come back."""

        now = self.clock()

        with self._lock:

            calls = self._calls.pop(key, None) or deque()

            while calls and calls[0] <= now - self.window:
                calls.popleft()

            if len(calls) >= self.limit:
                self._calls[key] = calls
                raise RateLimited(max(1.0, calls[0] + self.window - now))

            calls.append(now)
            self._calls[key] = calls

            while len(self._calls) > self.max_keys:
                self._calls.popitem(last=False)

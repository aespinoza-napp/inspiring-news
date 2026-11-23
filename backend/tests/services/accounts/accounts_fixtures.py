"""A service over a throwaway database, with a hash cheap enough for a test suite."""

from __future__ import annotations

from argon2 import PasswordHasher

from src.services.accounts.service import AccountService
from src.services.accounts.store import AccountStore


class Clock:
    def __init__(self, now: float = 1_800_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class CountingHasher(PasswordHasher):
    """argon2id with the smallest cost, counting what it is asked."""

    def __init__(self):
        super().__init__(time_cost=1, memory_cost=8, parallelism=1)
        self.verified = 0

    def verify(self, hash, password):
        self.verified += 1
        return super().verify(hash, password)


def make_service(tmp_path, clock=None) -> AccountService:
    return AccountService(AccountStore(tmp_path / "users.db"), clock=clock or Clock(), hasher=CountingHasher())

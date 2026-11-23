"""
Reader accounts (docs/goals.md, N5; docs/decisions/news-map.md,
"Accounts", has the threat model).

- A password is hashed with argon2id (argon2-cffi's defaults: 64 MiB,
  three passes) and never stored, logged or returned. At most
  settings.ACCOUNT_HASH_CONCURRENCY hashes run at once.
- A session is a random 256-bit token in the cookie; the store keeps its
  sha256, so a copy of the database opens no session. It ends after
  SESSION_IDLE_DAYS without use, at logout, at a password change (every
  other session too) and at deletion.
- Every state-changing request of a signed-in reader carries the
  session's CSRF token in a header (src/api/account_routes.py).
- Signing in is limited per username and per client: LOGIN_FAILURES
  failures in LOGIN_WINDOW, then a wait. An unknown username costs the
  same hash as a known one, so the time of an answer says nothing about
  whether the name exists.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from src.config.settings import settings
from src.services.accounts.store import AccountStore
from src.services.rate_limit import RateLimited, RateLimiter

SESSION_IDLE_DAYS = 30

# A session's last use is written at most this often: not a write on
# every request.
TOUCH_SECONDS = 60

LOGIN_FAILURES = 5
LOGIN_WINDOW = 15 * 60

# Registrations per client per hour: each costs a hash, and an account
# is a row a stranger can make us keep.
REGISTRATIONS_PER_HOUR = 5

USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")
MIN_PASSWORD = 10
MAX_PASSWORD = 128

# Never a real password's hash: verified against when the username is
# unknown, so that answer takes as long as a wrong password.
_DUMMY_PASSWORD = "not-a-password-of-anyone"


class AccountError(Exception):
    """A request a reader can fix: the message is shown to them."""


class WrongCredentials(AccountError):

    def __init__(self):
        super().__init__("Wrong username or password.")


@dataclass(frozen=True)
class Session:
    user_id: int
    username: str
    email: str | None
    csrf: str
    created_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class FailureLimiter:
    """At most `limit` failures per `window` seconds per key; a success clears the key."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):

        self.limit = limit
        self.window = window
        self.clock = clock
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, *keys: str) -> None:

        now = self.clock()

        with self._lock:
            for key in keys:
                recent = [t for t in self._failures.get(key, []) if t > now - self.window]
                self._failures[key] = recent
                if len(recent) >= self.limit:
                    raise RateLimited(max(1.0, recent[0] + self.window - now))

    def failed(self, *keys: str) -> None:

        now = self.clock()

        with self._lock:
            for key in keys:
                self._failures.setdefault(key, []).append(now)

            # Bounded: keys with no recent failure are forgotten.
            if len(self._failures) > 10_000:
                for key in [k for k, v in self._failures.items() if not v or v[-1] <= now - self.window]:
                    del self._failures[key]

    def clear(self, key: str) -> None:

        with self._lock:
            self._failures.pop(key, None)


class AccountService:

    def __init__(self, store: AccountStore, clock: Callable[[], float] = time.time, hasher: PasswordHasher | None = None):

        self.store = store
        self.clock = clock
        self.hasher = hasher or PasswordHasher()
        self._hashing = threading.BoundedSemaphore(max(1, settings.ACCOUNT_HASH_CONCURRENCY))
        self._dummy = self.hasher.hash(_DUMMY_PASSWORD)
        self.logins = FailureLimiter(LOGIN_FAILURES, LOGIN_WINDOW, clock=time.monotonic)
        self.registrations = RateLimiter(REGISTRATIONS_PER_HOUR, window=3600)

    # ------------------------------------------------------------------
    # Passwords
    # ------------------------------------------------------------------

    def _hash(self, password: str) -> str:
        with self._hashing:
            return self.hasher.hash(password)

    def _verify(self, stored: str, password: str) -> bool:
        with self._hashing:
            try:
                return self.hasher.verify(stored, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

    @staticmethod
    def _check_password(password: str, username: str) -> None:

        if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise AccountError(f"A password is {MIN_PASSWORD} to {MAX_PASSWORD} characters.")

        if password.casefold() == username.casefold():
            raise AccountError("A password cannot be the username.")

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def register(self, username: str, password: str, email: str | None, client: str) -> tuple[str, Session]:
        """A new account and its first session: (cookie token, session)."""

        name = (username or "").strip().casefold()

        if not USERNAME.match(name):
            raise AccountError("A username is 3 to 32 letters, digits, dots, dashes or underscores, starting with a letter or digit.")

        self._check_password(password, name)

        email = (email or "").strip() or None
        if email is not None and (len(email) > 254 or not EMAIL.match(email)):
            raise AccountError("That email address does not look right. It is optional: leave it empty if you prefer.")

        self.registrations.check(client)

        hashed = self._hash(password)

        with self.store.connect() as db:

            if db.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone():
                raise AccountError("That username is taken.")

            cursor = db.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, hashed, _now_iso()),
            )
            user_id = int(cursor.lastrowid)

        return self._open_session(user_id)

    def login(self, username: str, password: str, client: str) -> tuple[str, Session]:

        name = (username or "").strip().casefold()
        keys = (f"user:{name}", f"client:{client}")

        self.logins.check(*keys)

        with self.store.connect() as db:
            row = db.execute("SELECT id, password_hash FROM users WHERE username = ?", (name,)).fetchone()

        # The same work whether or not the name exists.
        good = self._verify(row["password_hash"] if row else self._dummy, password or "")

        if not row or not good:
            self.logins.failed(*keys)
            raise WrongCredentials()

        self.logins.clear(keys[0])

        return self._open_session(int(row["id"]))

    def _open_session(self, user_id: int) -> tuple[str, Session]:

        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)

        with self.store.connect() as db:
            # Expired sessions go when anyone signs in, so the table does
            # not grow with sessions nobody will use again.
            db.execute("DELETE FROM sessions WHERE last_seen < ?", (self.clock() - SESSION_IDLE_DAYS * 86400,))
            db.execute(
                "INSERT INTO sessions (token_hash, user_id, csrf, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
                (_token_hash(token), user_id, csrf, _now_iso(), self.clock()),
            )

        session = self.session(token)
        assert session is not None
        return token, session

    def session(self, token: str | None) -> Session | None:
        """The live session for a cookie's token, or None; touches it at most once a minute."""

        if not token or len(token) > 100:
            return None

        now = self.clock()

        with self.store.connect() as db:

            row = db.execute(
                "SELECT s.token_hash, s.user_id, s.csrf, s.last_seen, u.username, u.email, u.created_at "
                "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
                (_token_hash(token),),
            ).fetchone()

            if row is None:
                return None

            if row["last_seen"] < now - SESSION_IDLE_DAYS * 86400:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
                return None

            if row["last_seen"] < now - TOUCH_SECONDS:
                db.execute("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (now, row["token_hash"]))

        return Session(
            user_id=int(row["user_id"]),
            username=row["username"],
            email=row["email"],
            csrf=row["csrf"],
            created_at=row["created_at"],
        )

    def logout(self, token: str) -> None:

        with self.store.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def change_password(self, session: Session, token: str, current: str, new: str) -> None:
        """Every other session ends: whoever had the old password is signed out."""

        with self.store.connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE id = ?", (session.user_id,)).fetchone()

        if row is None or not self._verify(row["password_hash"], current or ""):
            raise AccountError("The current password is not right.")

        self._check_password(new, session.username)
        hashed = self._hash(new)

        with self.store.connect() as db:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, session.user_id))
            db.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (session.user_id, _token_hash(token)))

    def export(self, session: Session) -> dict:
        """
        Everything held about the reader, by table: what a reader is owed
        on request. Secrets are left out (the password's hash, the
        sessions' token hashes and CSRF tokens); their existence is not.
        """

        hidden = {"password_hash", "token_hash", "csrf"}
        document: dict = {"exportedAt": _now_iso()}

        with self.store.connect() as db:
            for table, column in self.store.tables_of_a_user():
                rows = db.execute(f"SELECT * FROM {table} WHERE {column} = ?", (session.user_id,)).fetchall()
                document[table] = [{key: row[key] for key in row.keys() if key not in hidden} for row in rows]

        return document

    def delete(self, session: Session, password: str) -> None:
        """Every row about the reader, at once: the user's, and by cascade every table that names them."""

        with self.store.connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE id = ?", (session.user_id,)).fetchone()

        if row is None or not self._verify(row["password_hash"], password or ""):
            raise AccountError("The password is not right.")

        with self.store.connect() as db:
            for table, column in self.store.tables_of_a_user():
                if table != "users":
                    db.execute(f"DELETE FROM {table} WHERE {column} = ?", (session.user_id,))
            db.execute("DELETE FROM users WHERE id = ?", (session.user_id,))

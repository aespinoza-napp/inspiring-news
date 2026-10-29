"""
Where reader accounts are kept: one SQLite file (settings.USERS_DB_PATH),
standard library only, on the backend's data volume, so it is backed up
with it (deploy/gcp's snapshots).

Not the lake and not Neo4j. The lake is the record of what was analysed;
the graph is a view that `POST /graph/sync` rebuilds from it
(docs/decisions/graph.md). A reader's interests there would be wiped by
the next sync, or make sync something that must protect them. And a
reader's data must be removable at once and in full, which a file of its
own makes a DELETE with cascades.

Migrations are numbered and run in order on first use; each runs once.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

# Each entry: one migration, run once, in order. Never edit one that has
# shipped; add the next.
MIGRATIONS: list[str] = [
    # 1. Accounts and their sessions (N5).
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        -- Lower case: one account per name whatever its case.
        username TEXT NOT NULL UNIQUE,
        email TEXT,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE sessions (
        -- sha256 of the cookie's token: a copy of this file opens no session.
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        csrf TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_seen REAL NOT NULL
    );
    CREATE INDEX sessions_by_user ON sessions(user_id);
    """,
]


class AccountStore:

    def __init__(self, path: Path | str):

        self.path = Path(path)
        self._migrated = False
        self._lock = threading.Lock()

    @contextmanager
    def connect(self):
        """A connection with foreign keys on, committed on success, rolled back on error."""

        self._migrate()

        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self) -> None:

        if self._migrated:
            return

        with self._lock:

            if self._migrated:
                return

            self.path.parent.mkdir(parents=True, exist_ok=True)

            connection = sqlite3.connect(self.path, timeout=10)

            try:
                # WAL: a reader is never blocked by a writer, and a crash
                # mid-write leaves the last committed state.
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
                row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
                current = row[0] or 0

                for number, script in enumerate(MIGRATIONS, start=1):
                    if number > current:
                        connection.executescript(f"BEGIN; {script}; INSERT INTO schema_version VALUES ({number}); COMMIT;")

                connection.commit()
            finally:
                connection.close()

            self._migrated = True

    def tables_of_a_user(self) -> list[tuple[str, str]]:
        """
        (table, column naming the user) for every table that holds a
        reader's data: what export reads and what delete must empty. Read
        from the schema, so a table a later migration adds is covered
        without being listed anywhere.
        """

        with self.connect() as connection:

            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            found = []

            for table in tables:
                columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
                if table == "users":
                    found.append((table, "id"))
                elif "user_id" in columns:
                    found.append((table, "user_id"))

            return found

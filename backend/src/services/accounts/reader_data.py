"""
What a signed-in reader keeps (docs/goals.md, N6): the groups, topics
and names they follow, the stories they save, and the connections they
draw - one story to another, or a story to a name, with a note.

All of it in users.db (store.py, migration 2), and nowhere else. A
personal connection is drawn on that reader's map only: it never enters
the graph, the related-articles weights (news_map/index.py, links) or
another reader's view, and export and delete (service.py) cover these
tables because they read them from the schema.

What can be followed or saved is checked against what exists when it is
added: a group or topic from src/config/topics.py, a story or a name
from the published map. A story later withdrawn stays in the reader's
list - it is theirs - and the map simply has no point for it.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.config.topics import TOPIC_GROUP_NAMES, TOPIC_GROUPS, TOPICS
from src.services.accounts.service import AccountError, Session
from src.services.accounts.store import AccountStore
from src.services.news_map.for_you import PARTS, lowered

MAX_INTERESTS = 200
MAX_SAVED = 1000
MAX_CONNECTIONS = 500
MAX_NOTE = 280

ARTICLE_ID = re.compile(r"^[0-9a-f]{16}$")
KINDS = ("group", "topic", "entity")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ReaderData:

    def __init__(self, store: AccountStore, map_index):

        self.store = store
        self.map_index = map_index

    # ------------------------------------------------------------------
    # What exists
    # ------------------------------------------------------------------

    def _label(self, kind: str, key: str) -> str:
        """The name of something that can be followed, or AccountError if there is none."""

        if kind == "group" and key in TOPIC_GROUPS:
            return TOPIC_GROUP_NAMES.get(key, key)

        if kind == "topic" and key in TOPICS:
            return TOPICS[key].name

        if kind == "entity" and len(key) <= 200:
            entity = self.map_index.entity(key)
            if entity is not None:
                return entity.name

        raise AccountError(f"There is no {kind} {key!r} to follow.")

    def _article(self, article_id: str):

        article = self.map_index.get(article_id) if ARTICLE_ID.match(article_id or "") else None

        if article is None:
            raise AccountError("There is no published story with that id.")

        return article

    # ------------------------------------------------------------------
    # Interests
    # ------------------------------------------------------------------

    def interests(self, session: Session) -> list[dict]:

        with self.store.connect() as db:
            rows = db.execute(
                # rowid: the order they were chosen in; created_at has one-second steps.
                "SELECT kind, key, label, created_at FROM interests WHERE user_id = ? ORDER BY rowid",
                (session.user_id,),
            ).fetchall()

        return [{"kind": r["kind"], "key": r["key"], "label": r["label"], "createdAt": r["created_at"]} for r in rows]

    def follow(self, session: Session, kind: str, key: str) -> list[dict]:

        if kind not in KINDS:
            raise AccountError("One follows a group, a topic or a name.")

        label = self._label(kind, key)

        with self.store.connect() as db:

            count = db.execute("SELECT COUNT(*) FROM interests WHERE user_id = ?", (session.user_id,)).fetchone()[0]
            if count >= MAX_INTERESTS:
                raise AccountError(f"At most {MAX_INTERESTS} interests.")

            db.execute(
                "INSERT OR IGNORE INTO interests (user_id, kind, key, label, created_at) VALUES (?, ?, ?, ?, ?)",
                (session.user_id, kind, key, label, _now_iso()),
            )

        return self.interests(session)

    def unfollow(self, session: Session, kind: str, key: str) -> list[dict]:

        with self.store.connect() as db:
            db.execute("DELETE FROM interests WHERE user_id = ? AND kind = ? AND key = ?", (session.user_id, kind, key))

        return self.interests(session)

    def replace_interests(self, session: Session, items: list[dict]) -> list[dict]:
        """
        The whole set at once: the first-visit choice, or a signed-out
        reader's choices brought in at sign-up. Whatever no longer
        exists is skipped rather than refused, so a choice made last week
        still imports.
        """

        chosen = []

        for item in items[:MAX_INTERESTS]:
            kind, key = str(item.get("kind", "")), str(item.get("key", ""))
            if kind not in KINDS:
                continue
            try:
                chosen.append((kind, key, self._label(kind, key)))
            except AccountError:
                continue

        with self.store.connect() as db:
            db.execute("DELETE FROM interests WHERE user_id = ?", (session.user_id,))
            db.executemany(
                "INSERT OR IGNORE INTO interests (user_id, kind, key, label, created_at) VALUES (?, ?, ?, ?, ?)",
                [(session.user_id, kind, key, label, _now_iso()) for kind, key, label in chosen],
            )

        return self.interests(session)

    # ------------------------------------------------------------------
    # Saved stories
    # ------------------------------------------------------------------

    def saved(self, session: Session) -> list[dict]:

        with self.store.connect() as db:
            rows = db.execute(
                "SELECT article_id, title, created_at FROM saved WHERE user_id = ? ORDER BY rowid DESC",
                (session.user_id,),
            ).fetchall()

        return [{"id": r["article_id"], "title": r["title"], "createdAt": r["created_at"]} for r in rows]

    def save(self, session: Session, article_id: str) -> list[dict]:

        article = self._article(article_id)

        with self.store.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM saved WHERE user_id = ?", (session.user_id,)).fetchone()[0]
            if count >= MAX_SAVED:
                raise AccountError(f"At most {MAX_SAVED} saved stories.")
            db.execute(
                "INSERT OR IGNORE INTO saved (user_id, article_id, title, created_at) VALUES (?, ?, ?, ?)",
                (session.user_id, article.id, article.title, _now_iso()),
            )

        return self.saved(session)

    def unsave(self, session: Session, article_id: str) -> list[dict]:

        with self.store.connect() as db:
            db.execute("DELETE FROM saved WHERE user_id = ? AND article_id = ?", (session.user_id, article_id))

        return self.saved(session)

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def connections(self, session: Session) -> list[dict]:

        with self.store.connect() as db:
            rows = db.execute(
                "SELECT id, from_article, to_kind, to_key, note, created_at FROM connections WHERE user_id = ? ORDER BY id",
                (session.user_id,),
            ).fetchall()

        return [
            {"id": r["id"], "from": r["from_article"], "toKind": r["to_kind"], "to": r["to_key"], "note": r["note"], "createdAt": r["created_at"]}
            for r in rows
        ]

    def connect(self, session: Session, from_article: str, to_kind: str, to_key: str, note: str) -> list[dict]:

        self._article(from_article)

        if to_kind == "article":
            if to_key == from_article:
                raise AccountError("A story cannot be connected to itself.")
            self._article(to_key)
        elif to_kind == "entity":
            self._label("entity", to_key)
        else:
            raise AccountError("A story connects to another story or to a name.")

        note = (note or "").strip()
        if len(note) > MAX_NOTE:
            raise AccountError(f"A note is at most {MAX_NOTE} characters.")

        with self.store.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM connections WHERE user_id = ?", (session.user_id,)).fetchone()[0]
            if count >= MAX_CONNECTIONS:
                raise AccountError(f"At most {MAX_CONNECTIONS} connections.")
            db.execute(
                "INSERT INTO connections (user_id, from_article, to_kind, to_key, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session.user_id, from_article, to_kind, to_key, note, _now_iso()),
            )

        return self.connections(session)

    def disconnect(self, session: Session, connection_id: int) -> list[dict]:

        with self.store.connect() as db:
            db.execute("DELETE FROM connections WHERE user_id = ? AND id = ?", (session.user_id, connection_id))

        return self.connections(session)

    # ------------------------------------------------------------------
    # "Not interested" (N7)
    # ------------------------------------------------------------------

    def feed(self, session: Session) -> dict:
        """The stories hidden and the factors For you applies for this reader."""

        with self.store.connect() as db:
            hidden = [r["article_id"] for r in db.execute("SELECT article_id FROM hidden WHERE user_id = ? ORDER BY rowid", (session.user_id,))]
            factors = {r["part"]: r["factor"] for r in db.execute("SELECT part, factor FROM feed_factors WHERE user_id = ?", (session.user_id,))}

        return {"hidden": hidden, "factors": factors}

    def not_interested(self, session: Session, article_id: str, part: str) -> dict:
        """Hides the story and lowers, for this reader alone, the part that put it there."""

        if not ARTICLE_ID.match(article_id or ""):
            raise AccountError("There is no story with that id.")
        if part not in PARTS:
            raise AccountError(f"A reason is one of {', '.join(PARTS)}.")

        current = self.feed(session)

        with self.store.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM hidden WHERE user_id = ?", (session.user_id,)).fetchone()[0]
            if count >= MAX_SAVED:
                raise AccountError(f"At most {MAX_SAVED} hidden stories.")
            db.execute("INSERT OR IGNORE INTO hidden (user_id, article_id, created_at) VALUES (?, ?, ?)", (session.user_id, article_id, _now_iso()))
            factor = lowered(current["factors"], part)[part]
            db.execute(
                "INSERT INTO feed_factors (user_id, part, factor) VALUES (?, ?, ?) "
                "ON CONFLICT (user_id, part) DO UPDATE SET factor = excluded.factor",
                (session.user_id, part, factor),
            )

        return self.feed(session)

import logging
import sqlite3

import pytest

from src.services.accounts.service import SESSION_IDLE_DAYS, AccountError, WrongCredentials
from src.services.rate_limit import RateLimited

from tests.services.accounts.accounts_fixtures import Clock, make_service

PASSWORD = "correct horse battery"


def test_a_password_is_never_stored_or_logged_in_clear(tmp_path, caplog):

    service = make_service(tmp_path)

    with caplog.at_level(logging.DEBUG):
        service.register("ada", PASSWORD, "ada@example.org", "c1")
        service.login("ada", PASSWORD, "c1")
        with pytest.raises(WrongCredentials):
            service.login("ada", "wrong " + PASSWORD, "c1")

    raw = b"".join(path.read_bytes() for path in tmp_path.iterdir() if path.is_file())

    assert PASSWORD.encode() not in raw
    assert PASSWORD not in caplog.text

    with sqlite3.connect(tmp_path / "users.db") as db:
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("$argon2id$")


def test_a_cookie_token_is_stored_only_as_its_hash(tmp_path):

    service = make_service(tmp_path)
    token, _ = service.register("ada", PASSWORD, None, "c1")

    raw = b"".join(path.read_bytes() for path in tmp_path.iterdir() if path.is_file())

    assert token.encode() not in raw
    assert service.session(token).username == "ada"
    assert service.session(token + "x") is None


def test_usernames_are_one_per_name_whatever_the_case(tmp_path):

    service = make_service(tmp_path)
    service.register("Ada", PASSWORD, None, "c1")

    with pytest.raises(AccountError, match="taken"):
        service.register("ADA", PASSWORD, None, "c2")


@pytest.mark.parametrize("username, password, email, message", [
    ("a", PASSWORD, None, "username"),
    ("ada lovelace", PASSWORD, None, "username"),
    ("ada", "short", None, "password"),
    ("adalovelace", "AdaLovelace", None, "username"),
    ("ada", PASSWORD, "not an email", "email"),
])
def test_what_an_account_needs(tmp_path, username, password, email, message):

    with pytest.raises(AccountError, match=message):
        make_service(tmp_path).register(username, password, email, "c1")


def test_the_sixth_failed_login_is_limited_and_says_when(tmp_path):

    service = make_service(tmp_path)
    service.register("ada", PASSWORD, None, "c1")

    for _ in range(5):
        with pytest.raises(WrongCredentials):
            service.login("ada", "wrong password!", "c9")

    with pytest.raises(RateLimited) as limited:
        service.login("ada", PASSWORD, "c9")

    assert 1 <= limited.value.retry_after <= 15 * 60


def test_failures_from_many_names_on_one_client_are_limited_too(tmp_path):

    service = make_service(tmp_path)

    for n in range(5):
        with pytest.raises(WrongCredentials):
            service.login(f"nobody{n}", "wrong password!", "one-client")

    with pytest.raises(RateLimited):
        service.login("someone-else", "wrong password!", "one-client")


def test_an_unknown_name_costs_the_same_hash_as_a_wrong_password(tmp_path):

    service = make_service(tmp_path)
    service.register("ada", PASSWORD, None, "c1")
    before = service.hasher.verified

    with pytest.raises(WrongCredentials) as unknown:
        service.login("nobody", PASSWORD, "c2")
    with pytest.raises(WrongCredentials) as wrong:
        service.login("ada", "wrong password!", "c3")

    assert service.hasher.verified - before == 2
    assert str(unknown.value) == str(wrong.value)


def test_a_session_ends_after_thirty_idle_days(tmp_path):

    clock = Clock()
    service = make_service(tmp_path, clock)
    token, _ = service.register("ada", PASSWORD, None, "c1")

    clock.now += (SESSION_IDLE_DAYS - 1) * 86400
    assert service.session(token) is not None

    clock.now += (SESSION_IDLE_DAYS + 1) * 86400
    assert service.session(token) is None


def test_a_password_change_ends_every_other_session(tmp_path):

    service = make_service(tmp_path)
    here, session = service.register("ada", PASSWORD, None, "c1")
    elsewhere, _ = service.login("ada", PASSWORD, "c1")

    with pytest.raises(AccountError):
        service.change_password(session, here, "not the password", "a brand new password")

    service.change_password(session, here, PASSWORD, "a brand new password")

    assert service.session(here) is not None
    assert service.session(elsewhere) is None
    service.login("ada", "a brand new password", "c1")


def test_export_returns_everything_held_and_no_secret(tmp_path):

    service = make_service(tmp_path)
    token, session = service.register("ada", PASSWORD, "ada@example.org", "c1")
    service.login("ada", PASSWORD, "c1")

    document = service.export(session)

    assert document["users"][0]["username"] == "ada"
    assert document["users"][0]["email"] == "ada@example.org"
    assert len(document["sessions"]) == 2
    text = str(document)
    assert "password_hash" not in text and "$argon2" not in text
    assert session.csrf not in text and token not in text


def test_after_delete_every_row_about_the_reader_is_gone(tmp_path):

    service = make_service(tmp_path)
    token, session = service.register("ada", PASSWORD, None, "c1")
    service.login("ada", PASSWORD, "c1")
    other, _ = service.register("grace", PASSWORD, None, "c2")

    with pytest.raises(AccountError):
        service.delete(session, "not the password")

    service.delete(session, PASSWORD)

    assert service.session(token) is None
    with sqlite3.connect(tmp_path / "users.db") as db:
        for table, column in service.store.tables_of_a_user():
            assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (session.user_id,)).fetchone()[0] == 0
    assert service.session(other).username == "grace"


def test_accounts_import_nothing_that_writes_the_lake_the_graph_or_metrics():
    """A reader's data must reach none of them (docs/goals.md, the news-map rules)."""

    import ast
    from pathlib import Path

    sources = [*Path("src/services/accounts").glob("*.py"), Path("src/api/account_routes.py")]
    imported = set()

    for path in sources:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

    for module in imported:
        for forbidden in ("datalake", "lake_backend", "graph", "neo4j", "run_metrics", "journal"):
            assert forbidden not in module, module

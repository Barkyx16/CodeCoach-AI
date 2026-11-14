"""Row-level security (PostgreSQL): the database keeps each learner's rows to that learner, even
if an application query forgets its owner filter. Runs only on PostgreSQL with a role that is
subject to RLS (not a superuser or BYPASSRLS), which is how CI connects. Synthetic data only."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db import rls
from app.db.session import Base
from app.models import Note
from tests.conftest import TEST_DATABASE_URL, auth_headers, register

MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations/versions/20261106_248721f0fcb1_row_level_security.py"
)


def test_the_migration_and_the_app_protect_the_same_tables():
    spec = importlib.util.spec_from_file_location("rls_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TABLES == rls.BASE_TABLES
    assert module.POLICY == rls.POLICY
    for name in rls.PROTECTED_TABLES:  # each has the owner column the policy compares
        assert "user_id" in Base.metadata.tables[name].columns, name


SCOPES_MIGRATION = MIGRATION.parent / "20261108_7c1d2e3f4a5b_rls_scopes.py"


def test_the_scopes_migration_installs_exactly_what_the_app_does():
    spec = importlib.util.spec_from_file_location("rls_scopes_migration", SCOPES_MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TABLES == rls.BASE_TABLES
    assert (module.POLICY, module.MAINTENANCE_POLICY) == (rls.POLICY, rls.MAINTENANCE_POLICY)
    assert module.CONDITION == rls._CONDITION  # what a dev database gets from rls.apply()
    assert module.MAINTENANCE_CONDITION == rls._MAINTENANCE_CONDITION


def test_each_table_added_later_gets_the_same_policies_from_its_own_migration():
    """A table put under row-level security after 248721f0fcb1 is listed in rls.ADDED_TABLES under
    the migration that created it; that migration installs exactly the current policies on it."""
    assert set(rls.BASE_TABLES).isdisjoint(t for added in rls.ADDED_TABLES.values() for t in added)
    for revision, tables in rls.ADDED_TABLES.items():
        (path,) = MIGRATION.parent.glob(f"*_{revision}_*.py")
        spec = importlib.util.spec_from_file_location(f"rls_added_{revision}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert tables == module.TABLES, revision
        assert (module.POLICY, module.MAINTENANCE_POLICY) == (rls.POLICY, rls.MAINTENANCE_POLICY)
        assert module.CONDITION == rls._CONDITION
        assert module.MAINTENANCE_CONDITION == rls._MAINTENANCE_CONDITION


def _enforced(url: str) -> bool:
    engine = create_engine(url)
    with engine.connect() as conn:
        bypass = conn.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    engine.dispose()
    return not bypass


pytestmark_pg = pytest.mark.skipif(
    not TEST_DATABASE_URL or not _enforced(TEST_DATABASE_URL),
    reason="needs PostgreSQL and a role subject to row-level security",
)


def note(client, headers, title):
    r = client.post("/api/v1/me/notes", headers=headers, json={"title": title, "body": "synthetic"})
    assert r.status_code == 201, r.text
    return r.json()


@pytestmark_pg
def test_every_protected_table_has_the_policy_and_the_role_is_subject_to_it(client):
    status = rls.rls_status(client.app.state.engine)
    assert status["supported"] and not status["role_bypasses_rls"]
    assert status["missing"] == []
    present = set(inspect(client.app.state.engine).get_table_names())
    assert set(status["protected"]) == set(rls.PROTECTED_TABLES) & present


@pytestmark_pg
def test_the_database_shows_a_user_only_their_own_rows(client):
    a = register(client, email="ada@example.com")
    b = register(client, email="bea@example.com")
    mine = note(client, auth_headers(a), "Ada's note")
    note(client, auth_headers(b), "Bea's note")
    with Session(client.app.state.engine) as db:
        rls.bind_user(db, b["user"]["id"])
        # A query with no owner filter at all: the database applies one.
        titles = db.scalars(select(Note.title)).all()
        assert titles == ["Bea's note"]
        assert db.get(Note, mine["id"]) is None
        # Every new transaction in this session stays narrowed.
        db.commit()
        assert db.scalars(select(Note.title)).all() == ["Bea's note"]
    with Session(client.app.state.engine) as db:  # no user context (worker, CLI): everything
        assert len(db.scalars(select(Note.title)).all()) == 2


@pytestmark_pg
def test_a_user_can_not_write_a_row_under_someone_else(client):
    a = register(client, email="ada@example.com")
    b = register(client, email="bea@example.com")
    with Session(client.app.state.engine) as db:
        rls.bind_user(db, b["user"]["id"])
        db.add(Note(user_id=a["user"]["id"], title="planted", body=""))
        with pytest.raises(DBAPIError, match="row-level security"):
            db.flush()


@pytestmark_pg
def test_a_route_that_forgot_its_owner_check_still_leaks_nothing(client, monkeypatch):
    """Simulate the bug RLS exists for: the notes service loses its owner check."""
    from app.services import notes as notes_service

    a = register(client, email="ada@example.com")
    b = register(client, email="bea@example.com")
    secret = note(client, auth_headers(a), "Ada's private note")

    def careless_note(self, user, note_id):  # the real one also compares n.user_id to user.id
        n = self.db.get(Note, note_id)
        if n is None:
            from app.errors import NotFoundError

            raise NotFoundError("Note not found")
        return n

    monkeypatch.setattr(notes_service.Notebook, "_note", careless_note)
    r = client.get(f"/api/v1/me/notes/{secret['id']}", headers=auth_headers(b))
    assert r.status_code == 404
    assert "private" not in r.text
    # The owner still sees it through the same careless code.
    assert client.get(f"/api/v1/me/notes/{secret['id']}", headers=auth_headers(a)).status_code == 200


@pytestmark_pg
def test_context_never_leaks_to_the_next_request_on_a_pooled_connection(make_client):
    c = make_client()
    a = register(c, email="ada@example.com")
    note(c, auth_headers(a), "Ada's note")
    with c.app.state.session_factory() as db:
        rls.bind_user(db, a["user"]["id"])
        db.scalars(select(Note.id)).all()
        db.commit()
    # A fresh session on (very likely) the same pooled connection: no leftover narrowing.
    with c.app.state.session_factory() as db:
        assert (
            db.execute(text("SELECT coalesce(current_setting('codecoach.user_id', true), '')")).scalar() == ""
        )
        assert len(db.scalars(select(Note.id)).all()) == 1


def test_sqlite_runs_without_row_level_security(make_settings):
    if TEST_DATABASE_URL:
        pytest.skip("SQLite only")
    engine = create_engine(make_settings().database_url)
    assert rls.rls_status(engine) == {"supported": False}
    with engine.begin() as conn:
        rls.apply(conn)  # a no-op, not an error


@pytestmark_pg
def test_check_rls_reports_enforcement(client, monkeypatch, capsys):
    from app.cli import main

    monkeypatch.setenv("DATABASE_URL", client.app.state.settings.database_url)
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert main(["cli", "check-rls"]) == 0
    finally:
        get_settings.cache_clear()
    assert "Row-level security is enforced." in capsys.readouterr().out

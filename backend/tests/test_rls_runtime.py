"""Row-level security in the running application: one pooled connection serving request after
request (different users, signed out, after errors, timeouts and cancellations), concurrent
requests, the worker and maintenance scopes, and an administrator's boundary. Each test asks the
database itself what a request can see, through a probe route that applies no owner filter of its
own. Two tests break the protection on purpose to show the others would notice.

PostgreSQL only, as a role subject to row-level security (CI connects that way). On SQLite there is
no database-enforced isolation: the application's owner checks are the only protection there
(tests/test_route_access.py). Synthetic data only."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_user
from app.db import rls
from app.models import Note, User
from tests.conftest import TEST_DATABASE_URL, auth_headers, register
from tests.test_row_level_security import pytestmark_pg

pytestmark = pytestmark_pg


def install_probe(app) -> None:
    """GET /__probe: what this request's transaction may see of `notes`, with no owner filter."""

    def probe(
        fail: str | None = None,
        db: Session = Depends(get_db),
        user: User | None = Depends(get_optional_user),
    ) -> dict:
        row = db.execute(
            text(
                "SELECT (SELECT count(*) FROM notes), coalesce(current_setting('codecoach.user_id', true), ''),"
                " coalesce(current_setting('codecoach.scope', true), ''), pg_backend_pid()"
            )
        ).one()
        if fail == "error":
            raise RuntimeError("synthetic failure after the user was bound")
        if fail == "timeout":
            db.execute(text("SET LOCAL statement_timeout = '50ms'"))
            db.execute(text("SELECT pg_sleep(2)"))
        if fail == "sleep":
            db.execute(text("SELECT pg_sleep(30)"))  # cancelled from outside by the test
        return {"notes": row[0], "user": row[1], "scope": row[2], "pid": row[3]}

    app.add_api_route("/__probe", probe, methods=["GET"])


@pytest.fixture
def one_connection(make_client):
    """Every probe through the same single pooled connection. (Signing up needs a second
    connection for the rate limiter, so accounts are made through a normal client on the same
    database: `c.setup`.)"""
    c = make_client(db_pool_size=1, db_max_overflow=0)
    c.setup = make_client()
    install_probe(c.app)
    return c


def people(c):
    maker = getattr(c, "setup", c)
    a, b = register(maker, email="ada@example.com"), register(maker, email="bea@example.com")
    for title in ("Ada 1", "Ada 2"):
        assert maker.post("/api/v1/me/notes", headers=auth_headers(a), json={"title": title}).status_code == 201
    assert maker.post("/api/v1/me/notes", headers=auth_headers(b), json={"title": "Bea 1"}).status_code == 201
    return a, b


def probe(c, who=None, **params):
    return c.get("/__probe", headers=auth_headers(who) if who else {}, params=params)


def test_one_pooled_connection_serves_each_user_only_their_own_rows(one_connection):
    c = one_connection
    a, b = people(c)
    seen = [probe(c, a).json(), probe(c, b).json(), probe(c).json(), probe(c, a).json(), probe(c).json()]
    assert [s["notes"] for s in seen] == [2, 1, 0, 2, 0]  # signed out: nothing at all
    assert len({s["pid"] for s in seen}) == 1  # really the same connection every time
    assert seen[2] == {"notes": 0, "user": "", "scope": "request", "pid": seen[0]["pid"]}


def quiet(c) -> TestClient:
    """The same app, answering a failure with its 500 instead of raising it into the test."""
    return TestClient(c.app, raise_server_exceptions=False)


@pytest.mark.parametrize("failure", ["error", "timeout"])
def test_nothing_is_left_on_the_connection_after_an_error_or_a_timeout(one_connection, failure):
    c = one_connection
    a, _ = people(c)
    before = probe(c).json()["pid"]
    assert probe(quiet(c), a, fail=failure).status_code >= 500
    after = probe(c).json()
    assert after == {"notes": 0, "user": "", "scope": "request", "pid": before}  # same connection, clean


def test_a_query_cancelled_from_outside_leaves_nothing_behind(one_connection):
    c = one_connection
    a, _ = people(c)
    pid = probe(c).json()["pid"]
    result: dict = {}
    worker = threading.Thread(target=lambda: result.update(r=probe(quiet(c), a, fail="sleep")))
    worker.start()
    canceller = create_engine(TEST_DATABASE_URL)
    try:
        with canceller.connect() as conn:
            for _ in range(100):
                waiting = conn.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE pid = :p AND query LIKE '%pg_sleep(30)%'"
                    ),
                    {"p": pid},
                ).scalar()
                if waiting:
                    break
                threading.Event().wait(0.05)
            assert conn.execute(text("SELECT pg_cancel_backend(:p)"), {"p": pid}).scalar() is True
    finally:
        canceller.dispose()
    worker.join(10)
    assert result["r"].status_code >= 500
    after = probe(c).json()
    assert after == {"notes": 0, "user": "", "scope": "request", "pid": pid}


def test_concurrent_requests_never_see_each_others_rows(make_client):
    c = make_client(db_pool_size=2, db_max_overflow=0)
    install_probe(c.app)
    a, b = people(c)
    expected = {"a": 2, "b": 1, "anon": 0}
    who = {"a": a, "b": b, "anon": None}
    jobs = [k for k in ("a", "b", "anon") for _ in range(20)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(lambda k: (k, probe(c, who[k]).json()), jobs))
    assert all(r["notes"] == expected[k] for k, r in answers), [(k, r["notes"]) for k, r in answers]
    assert len({r["pid"] for _, r in answers}) <= 2  # 60 requests over two connections


def test_the_probe_would_catch_a_request_that_isnt_denied_by_default(one_connection, monkeypatch):
    """Sensitivity: without the request scope, a signed-out request sees every learner's rows."""
    c = one_connection
    people(c)
    real = rls.set_scope
    monkeypatch.setattr(rls, "set_scope", lambda s, scope: s if scope == rls.REQUEST else real(s, scope))
    assert probe(c).json()["notes"] == 3


def test_the_probe_would_catch_a_setting_that_outlives_its_transaction(one_connection, monkeypatch):
    """Sensitivity: a session-wide (not transaction-local) setting would follow the connection
    into the next use. With the real, transaction-local setting nothing follows."""
    c = one_connection
    a, _ = people(c)
    factory = c.app.state.session_factory

    def leftover() -> str:
        with factory() as db:
            return db.execute(
                text("SELECT coalesce(current_setting('codecoach.user_id', true), '')")
            ).scalar()

    assert c.post("/api/v1/me/notes", headers=auth_headers(a), json={"title": "Ada 3"}).status_code == 201
    assert leftover() == ""  # the real, transaction-local setting: nothing follows

    def session_wide(conn, info):
        conn.execute(
            text("SELECT set_config(:u, :v, false)"), {"u": rls.SETTING, "v": info.get("rls_user_id") or ""}
        )

    monkeypatch.setattr(rls, "_set", session_wide)
    # A request that commits (a rolled-back transaction undoes even a session-wide setting).
    assert c.post("/api/v1/me/notes", headers=auth_headers(a), json={"title": "Ada 3"}).status_code == 201
    assert leftover() == a["user"]["id"]  # leaked: this is what transaction-local prevents
    with factory() as db:  # put the connection back the way it was
        db.execute(text("RESET codecoach.user_id"))
        db.commit()


# --- the worker, maintenance, operators -----------------------------------------------------------


def count_notes(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Note))


def test_each_scope_sees_what_it_should(client):
    a, _ = people(client)
    factory = client.app.state.session_factory
    with rls.scoped(factory, rls.WORKER)() as db:
        assert count_notes(db) == 0  # the worker sees no learner's rows
        rls.bind_user(db, a["user"]["id"])
        assert count_notes(db) == 2  # ...until it works for one learner
    with factory() as db:
        assert count_notes(db) == 3  # operators and migrations: everything, as before
        rls.set_scope(db, rls.REQUEST)
        assert count_notes(db) == 0


def test_maintenance_reads_every_learner_and_can_change_nothing(client):
    people(client)
    with rls.scoped(client.app.state.session_factory, rls.WORKER)() as db:
        with rls.maintenance(db, "test: read every learner's notes"):
            assert count_notes(db) == 3
            changed = db.execute(
                update(Note).values(title="rewritten").execution_options(synchronize_session=False)
            )
            assert changed.rowcount == 0  # read-only: no row is visible to an update
            with pytest.raises(DBAPIError, match="row-level security"):
                db.add(Note(user_id=db.scalar(select(User.id).limit(1)), title="planted"))
                db.flush()
            db.rollback()
        assert count_notes(db) == 0  # back to the worker scope afterwards


def test_the_guest_clean_up_still_sees_recent_activity(client, monkeypatch):
    """The one maintenance read in use: a guest active only through progress events is kept.
    Without the maintenance read the worker scope would hide those events and delete both."""
    from contextlib import nullcontext

    from app.jobs import housekeeping
    from tests.test_retention import age, guest

    def two_old_guests() -> tuple[str, str]:
        ids = []
        for _ in range(2):
            g = guest(client)
            body = {"problem_slug": "two-sum", "level": 1, "source_code": ""}
            assert client.post("/api/v1/ai/hint", headers=auth_headers(g), json=body).status_code == 200
            ids.append(g["user"]["id"])
        age(client, ids[0], 90, events_days=1)  # created long ago, but used yesterday
        age(client, ids[1], 90)
        return ids[0], ids[1]

    def guests() -> set[str]:
        with client.app.state.session_factory() as db:
            return set(db.scalars(select(User.id).where(User.is_guest.is_(True))))

    worker = rls.scoped(client.app.state.session_factory, rls.WORKER)
    active, idle = two_old_guests()
    assert housekeeping(worker, client.app.state.settings)["guests_deleted"] == 1
    assert guests() == {active}

    monkeypatch.setattr(rls, "maintenance", lambda db, reason: nullcontext(db))  # sensitivity
    again, _ = two_old_guests()
    assert housekeeping(worker, client.app.state.settings)["guests_deleted"] == 3  # active ones too


def test_an_administrator_reads_no_learner_rows_either(client, monkeypatch):
    """Admin is for content triage. The admin's requests are bound to the admin's own id, so even a
    careless route shows them nothing of anyone else's."""
    from app.services import notes as notes_service

    a, _ = people(client)
    admin = register(client, email="admin@example.com")
    with client.app.state.session_factory() as db:
        db.execute(update(User).where(User.id == admin["user"]["id"]).values(is_admin=True))
        db.commit()
    secret = client.get("/api/v1/me/notes", headers=auth_headers(a)).json()["items"][0]["id"]

    def careless_note(self, user, note_id):
        n = self.db.get(Note, note_id)
        if n is None:
            from app.errors import NotFoundError

            raise NotFoundError("Note not found")
        return n

    monkeypatch.setattr(notes_service.Notebook, "_note", careless_note)
    r = client.get(f"/api/v1/me/notes/{secret}", headers=auth_headers(admin))
    assert r.status_code == 404 and "Ada" not in r.text

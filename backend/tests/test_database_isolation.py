"""Every test starts from the same clean, seeded database (Volume 15, prompt 1; docs/CI.md, "The
PostgreSQL suite's set-up"): the first test here writes to a seeded table (a problem's title and its
tests), adds an account and leaves a connection open; the second, which runs right after it, finds
the problem bank exactly as seeded, no account, and every table empty that the seed doesn't fill.
On SQLite each test has its own file; on PostgreSQL the test database is recreated from the
session's template, so a fixture that stopped restoring it is caught here. Synthetic data only."""

from __future__ import annotations

from sqlalchemy import func, inspect, select, text

from app.db.seed import DEBUGGING_DIR, load_seed_files
from app.db.session import Base
from app.models import Problem, TestCase, User
from tests.conftest import register

SLUG = "two-sum"
MARK = "Changed by the test before"
SEEDED = {"problems", "test_cases"}


def _seeded_title() -> str:
    return next(d["title"] for d in load_seed_files() if d["slug"] == SLUG)


def test_1_a_test_that_writes_to_seeded_and_owned_tables(client):
    register(client)
    with client.app.state.session_factory() as db:
        problem = db.scalar(select(Problem).where(Problem.slug == SLUG))
        problem.title = MARK
        problem.test_cases.clear()
        db.commit()
    # And a connection left open past the end of the test.
    client._left_open = client.app.state.engine.connect()  # type: ignore[attr-defined]
    client._left_open.execute(text("SELECT 1"))
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(Problem.title).where(Problem.slug == SLUG)) == MARK


def test_2_the_next_test_finds_the_database_as_seeded(client):
    with client.app.state.session_factory() as db:
        problem = db.scalar(select(Problem).where(Problem.slug == SLUG))
        assert problem.title == _seeded_title()
        assert len(problem.test_cases) > 0
        assert db.scalar(select(func.count()).select_from(Problem)) == len(load_seed_files()) + len(
            load_seed_files(DEBUGGING_DIR)
        )
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(TestCase)) > 0
        engine = client.app.state.engine
        names = set(inspect(engine).get_table_names())
        assert names >= {t.name for t in Base.metadata.sorted_tables}
        written = {
            t.name: db.scalar(select(func.count()).select_from(t))
            for t in Base.metadata.sorted_tables
            if t.name not in SEEDED
        }
        assert {k: v for k, v in written.items() if v} == {}

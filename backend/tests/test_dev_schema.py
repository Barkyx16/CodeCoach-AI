"""A database an older local run created (by create_all, not migrations) gets the columns added
since, when that's safe, so a `git pull` doesn't leave pages failing with "no such column"."""

from sqlalchemy import create_engine, inspect, text

from app.db.dev_schema import add_missing_columns
from app.db.session import Base


def test_missing_safe_columns_are_added_once_and_existing_rows_keep_their_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:  # as a database made before these columns existed
        c.exec_driver_sql(
            "INSERT INTO users (id, email, auth_provider_id, password_hash, display_name, is_guest, is_admin, "
            "token_version, created_at, career_track) VALUES ('u1', 'a@example.com', 'local:u1', 'x', 'A', 0, 0, 0, "
            "'2026-11-01 00:00:00', 'registered-nurse')"
        )
        c.exec_driver_sql(
            "INSERT INTO applications (id, user_id, employer, role_title, stage, archived, created_at, updated_at, "
            "story_ids, next_action, notes) VALUES ('a1', 'u1', 'E', 'R', 'saved', 0, '2026-11-01', '2026-11-01', '[]', '', '')"
        )
        c.exec_driver_sql(
            "INSERT INTO application_events (id, application_id, kind, title, notes, created_at) "
            "VALUES ('e1', 'a1', 'interview', 'Panel', '', '2026-11-01')"
        )
        c.exec_driver_sql(
            "INSERT INTO interview_kits (event_id, user_id, format, location, interviewers, notes, checklist, questions, "
            "story_ids, updated_at, revision) VALUES ('e1', 'u1', 'remote', '', '[]', 'kept', '[]', '[]', '[]', '2026-11-01', 0)"
        )
        for table, column in (
            ("schedule_entries", "anchor_at"),
            ("interview_kits", "event_when"),
            ("interview_kits", "story_revisions"),
            ("interview_kits", "revision"),
        ):
            c.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN {column}")

    added = add_missing_columns(engine, Base.metadata)
    assert sorted(added) == sorted(
        [
            "schedule_entries.anchor_at",
            "interview_kits.event_when",
            "interview_kits.story_revisions",
            "interview_kits.revision",
        ]
    )
    cols = {c["name"] for c in inspect(engine).get_columns("interview_kits")}
    assert {"revision", "event_when", "story_revisions"} <= cols
    with engine.connect() as c:  # the existing kit keeps its notes and gets the column's default
        assert c.execute(text("SELECT notes, revision, event_when FROM interview_kits")).one() == (
            "kept",
            0,
            None,
        )
    assert add_missing_columns(engine, Base.metadata) == []  # nothing more the second time


def test_a_column_that_cant_be_added_safely_is_left_for_migrations(tmp_path, caplog):
    from sqlalchemy import Column, Integer, MetaData, String, Table

    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}")
    old = MetaData()
    Table("things", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)
    new = MetaData()
    Table(
        "things",
        new,
        Column("id", Integer, primary_key=True),
        Column("required", String(10), nullable=False),  # no default: existing rows would break it
        Column("optional", String(10), nullable=True),
    )
    assert add_missing_columns(engine, new) == ["things.optional"]
    assert "things.required is missing and can't be added safely" in caplog.text

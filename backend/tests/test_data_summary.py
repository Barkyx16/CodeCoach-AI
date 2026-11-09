"""What's saved to an account, as counts (Volume 10, prompt 10; docs/YOUR_DATA.md): every table
holding a learner's rows is placed in one category; the counts are the caller's own, read with
COUNT queries only (no text, title or amount is selected); another account's rows aren't counted;
anonymous callers get nothing; export and deletion keep their own checks. Synthetic accounts only."""

from __future__ import annotations

from sqlalchemy import event

from app.db.session import Base
from app.services.data_summary import CATEGORIES, OWNER_COLUMN

from .conftest import auth_headers, register

URL = "/api/v1/me/data-summary"
SECRET = "PRIVATE-ZEBRA-7731"
OWNER_COLUMNS = {"user_id", "owner_id", "reporter_id", "reviewer_id"}


def owner_tables() -> set[str]:
    return {t.name for t in Base.metadata.tables.values() if OWNER_COLUMNS & {c.name for c in t.columns}}


def counts(client, h) -> dict[str, int]:
    r = client.get(URL, headers=h)
    assert r.status_code == 200, r.text
    return {c["key"]: c["count"] for c in r.json()["categories"]}


def test_every_table_with_a_learners_rows_is_in_exactly_one_category():
    placed = [t for c in CATEGORIES for t in (*c.tables, *c.includes)]
    assert len(placed) == len(set(placed)), "a table is in two categories"
    assert set(placed) == owner_tables(), (
        f"not placed: {sorted(owner_tables() - set(placed))}; not an owner table: {sorted(set(placed) - owner_tables())}"
    )
    for table, column in OWNER_COLUMN.items():
        assert column in Base.metadata.tables[table].c, (table, column)
    assert len({c.key for c in CATEGORIES}) == len(CATEGORIES)


def test_counts_are_yours_only_and_carry_no_content(client):
    ada = auth_headers(register(client, email="ada@example.com"))
    bea = auth_headers(register(client, email="bea@example.com"))
    before = counts(client, ada)
    assert before["account"] == 1 and before["notes"] == 0 and before["stories"] == 0
    for i in range(3):
        r = client.post("/api/v1/me/notes", headers=ada, json={"title": f"Note {i} {SECRET}", "body": SECRET})
        assert r.status_code == 201, r.text
    gone = client.get("/api/v1/me/notes", headers=ada).json()
    first = (gone["items"] if isinstance(gone, dict) else gone)[0]["id"]
    assert client.delete(f"/api/v1/me/notes/{first}", headers=ada).status_code in (200, 204)
    story = {"title": f"Story {SECRET}", "situation": SECRET, "task": "t", "action": "a", "result": "r"}
    assert client.post("/api/v1/me/stories", headers=ada, json=story).status_code == 201
    app = {"employer": f"Hospital {SECRET}", "role_title": "Nurse"}
    assert client.post("/api/v1/me/applications", headers=ada, json=app).status_code == 201
    assert (
        client.post("/api/v1/me/notes", headers=bea, json={"title": "Bea's", "body": "x"}).status_code == 201
    )

    r = client.get(URL, headers=ada)
    assert SECRET not in r.text and "Hospital" not in r.text
    now = counts(client, ada)
    assert now["notes"] == 2  # the deleted one is in its undo window, said in the note
    assert now["stories"] == 1 and now["applications"] == 1
    assert now["sign_in"] >= 1  # this session
    assert counts(client, bea)["notes"] == 1 and counts(client, bea)["stories"] == 0
    rows = r.json()["categories"]
    assert {row["group"] for row in rows} == {"work", "sharing", "account"}
    assert next(row for row in rows if row["key"] == "answers")["note"].endswith(
        "No audio reaches CodeCoach."
    )


def test_counting_reads_no_content_columns(client):
    """The summary never selects a learner's text: each statement about their tables is a COUNT."""
    h = auth_headers(register(client))
    client.post("/api/v1/me/notes", headers=h, json={"title": SECRET, "body": SECRET})
    statements: list[str] = []
    engine = client.app.state.session_factory.kw["bind"]

    def capture(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()).lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get(URL, headers=h).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    counted = [s for s in statements if any(f"from {t}" in s for t in owner_tables())]
    assert len(counted) >= sum(len(c.tables) for c in CATEGORIES)
    for s in counted:
        if s.startswith("select count(*)"):
            continue
        # Signing in reads the caller's own account row, not their work.
        assert s.startswith("select users.") or "from users" in s, s


def test_anonymous_callers_get_nothing_and_export_and_deletion_keep_their_checks(client):
    assert client.get(URL).status_code == 401
    assert client.get("/api/v1/me/export").status_code == 401
    h = auth_headers(register(client, email="del@example.com"))
    wrong = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "Nope12345A", "confirm": "DELETE"}
    )
    assert wrong.status_code == 401
    assert counts(client, h)["account"] == 1  # still there
    done = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert done.status_code in (200, 204), done.text
    assert client.get(URL, headers=h).status_code == 401

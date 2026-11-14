"""Recent work to continue (Volume 11, prompt 1; docs/CONTINUE.md): a running interview first, then
the caller's own records newest first with the times they really keep (saved, started, finished;
never "opened"); a finished interview is a result, not a session; titles and times only, no body,
story text, terms or transcript read; another account's records never listed; one kind that fails
is named and the rest still listed; anonymous callers get nothing. Synthetic accounts only."""

from __future__ import annotations

import time

from sqlalchemy import event

from app.services import recent_work as rw

from .conftest import auth_headers, register

URL = "/api/v1/me/recent-work"
APPS = "/api/v1/me/applications"
SECRET = "PRIVATE-OTTER-2208"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def seed(client, h):
    """One of each kind, a moment apart so the order is the order made."""
    made = {}
    r = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"})
    assert r.status_code == 201, r.text
    made["finished"] = r.json()["id"]
    assert client.post(f"/api/v1/interviews/{made['finished']}/abandon", headers=h).status_code == 200
    for kind, call in (
        (
            "note",
            lambda: client.post(
                "/api/v1/me/notes", headers=h, json={"title": "Sepsis signs", "body": SECRET}
            ),
        ),
        (
            "story",
            lambda: client.post(
                "/api/v1/me/stories",
                headers=h,
                json={"title": "Night shift", "situation": SECRET, "task": "t", "action": "a", "result": "r"},
            ),
        ),
        (
            "application",
            lambda: client.post(
                APPS, headers=h, json={"employer": "Northfield", "role_title": "Ward nurse", "notes": SECRET}
            ),
        ),
    ):
        time.sleep(0.01)
        r = call()
        assert r.status_code == 201, r.text
        made[kind] = r.json()["id"]
    time.sleep(0.01)
    ev = client.post(
        f"{APPS}/{made['application']}/events",
        headers=h,
        json={"title": "Panel interview", "on_date": "2026-12-15"},
    ).json()["events"][0]
    made["event"] = ev["id"]
    assert (
        client.put(
            f"{APPS}/{made['application']}/events/{ev['id']}/kit", headers=h, json={"notes": SECRET}
        ).status_code
        == 200
    )
    time.sleep(0.01)
    r = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"})
    made["live"] = r.json()["id"]
    return made


def test_a_running_interview_first_then_newest_saved_with_the_times_records_keep(client):
    h = nurse(client)
    made = seed(client, h)
    r = client.get(URL, headers=h, params={"limit": 12})
    assert r.status_code == 200, r.text
    assert SECRET not in r.text
    body = r.json()
    assert body["unavailable"] == []
    items = body["items"]
    assert (items[0]["type"], items[0]["id"], items[0]["state"], items[0]["at_meaning"]) == (
        "interview",
        made["live"],
        "in_progress",
        "started",
    )
    kinds = [i["type"] for i in items[1:]]
    assert kinds[:4] == ["kit", "application", "story", "note"]  # newest first
    kit = items[1]
    assert (kit["id"], kit["parent_id"]) == (made["event"], made["application"])
    assert (
        kit["title"] == "Interview-day kit: Panel interview (Northfield)" and kit["detail"] == "on 2026-12-15"
    )
    app = next(i for i in items if i["type"] == "application")
    assert (app["title"], app["detail"], app["at_meaning"]) == ("Ward nurse at Northfield", "Saved", "saved")
    done = next(i for i in items if i["id"] == made["finished"])
    assert (done["state"], done["at_meaning"]) == ("ended_early", "finished")  # a result, not a session
    assert all(i["at_meaning"] in ("saved", "started", "finished") for i in items)

    assert len(client.get(URL, headers=h, params={"limit": 3}).json()["items"]) == 3
    assert client.get(URL, headers=h, params={"limit": 13}).status_code == 422


def test_only_your_own_records_and_nothing_deleted(client):
    ada = nurse(client)
    bea = nurse(client, "bea@example.com")
    made = seed(client, ada)
    client.post("/api/v1/me/notes", headers=bea, json={"title": "Bea's own note", "body": "x"})
    theirs = client.get(URL, headers=bea).json()["items"]
    assert [i["title"] for i in theirs] == ["Bea's own note"]
    assert client.delete(f"/api/v1/me/notes/{made['note']}", headers=ada).status_code in (200, 204)
    assert client.delete(f"{APPS}/{made['application']}", headers=ada).status_code in (200, 204)
    left = {i["type"] for i in client.get(URL, headers=ada, params={"limit": 12}).json()["items"]}
    assert "note" not in left and "application" not in left and "kit" not in left  # the kit went with it
    assert client.get(URL).status_code == 401


def test_one_kind_failing_is_named_and_the_rest_are_still_listed(client, monkeypatch):
    h = nurse(client)
    seed(client, h)

    def broken(db, user, n):
        db.execute(
            rw.select(rw.func.count()).select_from(rw.Note).where(rw.Note.title == rw.func.no_such_function())
        )
        return []

    label, _ = rw.SOURCES["notes"]
    monkeypatch.setitem(rw.SOURCES, "notes", (label, broken))
    r = client.get(URL, headers=h, params={"limit": 12})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unavailable"] == ["notes"]
    kinds = {i["type"] for i in body["items"]}
    assert {
        "interview",
        "story",
        "kit",
        "application",
    } <= kinds  # read after the failure, in the same request
    assert "note" not in kinds


def test_only_titles_and_times_are_read(client):
    h = nurse(client)
    seed(client, h)
    statements: list[str] = []
    engine = client.app.state.session_factory.kw["bind"]

    def capture(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()).lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get(URL, headers=h).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    joined = "\n".join(statements)
    for content in (
        "notes.body",
        "experience_entries.situation",
        "applications.notes",
        "interview_kits.notes",
        "offer_comparisons.doc",
        "interview_turns",
    ):
        assert content not in joined, content

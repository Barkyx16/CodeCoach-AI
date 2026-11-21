"""Saving work under real conditions: the same create sent twice, two tabs saving at the same
moment, and an older tab editing a story through the role-target page. Each concurrency test has a
sensitivity twin that removes the row lock and shows the overwrite the lock prevents.
docs/PERSISTENCE.md has the feature-by-feature table. Synthetic accounts only."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.db import locking
from app.models import Note
from tests.conftest import TEST_DATABASE_URL, auth_headers, register

NOTES = "/api/v1/me/notes"
postgres_only = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="row locks are PostgreSQL's; SQLite allows one writer at a time"
)


def count_notes(client, user_id: str) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(Note).where(Note.user_id == user_id))


def test_a_create_sent_twice_makes_one_note(client):
    a = register(client, email="ada@example.com")
    b = register(client, email="bea@example.com")
    body = {"title": "Lost response", "client_request_id": "note-key-0001"}
    first = client.post(NOTES, headers=auth_headers(a), json=body)
    again = client.post(NOTES, headers=auth_headers(a), json={**body, "title": "the retry"})
    assert first.status_code == again.status_code == 201
    assert again.json()["id"] == first.json()["id"] and again.json()["title"] == "Lost response"
    assert count_notes(client, a["user"]["id"]) == 1
    # Keys are per account: someone else's identical key is a different note.
    other = client.post(NOTES, headers=auth_headers(b), json=body)
    assert other.status_code == 201 and other.json()["id"] != first.json()["id"]
    # Without a key, every create is new (older clients behave as before).
    client.post(NOTES, headers=auth_headers(a), json={"title": "no key"})
    assert count_notes(client, a["user"]["id"]) == 2


@postgres_only
def test_the_same_create_sent_twice_at_once_makes_one_note(client):
    a = register(client, email="ada@example.com")
    body = {"title": "Twice at once", "client_request_id": "note-key-0002"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies = list(pool.map(lambda _: client.post(NOTES, headers=auth_headers(a), json=body), range(4)))
    assert {r.status_code for r in replies} == {201}
    assert len({r.json()["id"] for r in replies}) == 1
    assert count_notes(client, a["user"]["id"]) == 1


def slow_lock(monkeypatch, module, *, lock: bool) -> None:
    """Hold each save open for a moment after its revision check, so two saves overlap."""
    real = locking.lock_for_update

    def slowed(db, row):
        out = real(db, row) if lock else row
        time.sleep(0.4)
        return out

    monkeypatch.setattr(module, "lock_for_update", slowed)


def two_at_once(fn):
    with ThreadPoolExecutor(max_workers=2) as pool:
        return sorted(r.status_code for r in pool.map(lambda i: fn(i), range(2)))


@postgres_only
@pytest.mark.parametrize("locked", [True, False], ids=["with the row lock", "sensitivity: without it"])
def test_two_tabs_saving_a_note_at_once(client, monkeypatch, locked):
    from app.services import notes as notes_service

    a = register(client, email="ada@example.com")
    h = auth_headers(a)
    note = client.post(NOTES, headers=h, json={"title": "v1"}).json()
    slow_lock(monkeypatch, notes_service, lock=locked)
    codes = two_at_once(
        lambda i: client.patch(
            f"{NOTES}/{note['id']}", headers=h, json={"base_revision": 1, "body": f"tab {i}"}
        )
    )
    final = client.get(f"{NOTES}/{note['id']}", headers=h).json()
    if locked:
        assert codes == [200, 409]  # the second tab is told, and keeps its text on screen
        assert final["revision"] == 2
    else:
        assert codes == [200, 200]  # both "saved": one silently replaced the other
        assert final["revision"] == 2  # two saves, one revision: the lost write


@postgres_only
@pytest.mark.parametrize("locked", [True, False], ids=["with the row lock", "sensitivity: without it"])
def test_two_tabs_saving_a_story_at_once(client, monkeypatch, locked):
    """Stories also have a unique (story, revision) row per save, so without the lock the race
    can't overwrite silently either: the second save fails with a server error. The lock turns
    that into the right answer, a 409 the editor explains."""
    from fastapi.testclient import TestClient

    from app.services import stories as stories_service

    quiet = TestClient(client.app, raise_server_exceptions=False)
    h = auth_headers(register(client, email="ada@example.com"))
    story = client.post("/api/v1/me/stories", headers=h, json={"title": "Launch"}).json()
    slow_lock(monkeypatch, stories_service, lock=locked)
    codes = two_at_once(
        lambda i: quiet.patch(
            f"/api/v1/me/stories/{story['id']}",
            headers=h,
            json={"expected_revision": 1, "title": f"Launch {i}"},
        )
    )
    assert codes == ([200, 409] if locked else [200, 500])


@postgres_only
def test_two_first_saves_of_a_whiteboard_draft_at_once(client, monkeypatch):
    from app.services import whiteboard as whiteboard_service
    from tests.test_whiteboard import DIAGRAM, P

    h = auth_headers(register(client, email="ada@example.com"))
    slow_lock(monkeypatch, whiteboard_service, lock=True)
    codes = two_at_once(
        lambda i: client.put(
            f"/api/v1/me/whiteboard/{P}/draft",
            headers=h,
            json={"diagram": DIAGRAM, "explanation": f"tab {i}", "expected_revision": 0},
        )
    )
    assert codes == [200, 409]  # not a 500 from the duplicate key
    assert client.get(f"/api/v1/me/whiteboard/{P}/draft", headers=h).json()["revision"] == 1


def test_an_older_tab_cannot_overwrite_a_story_through_the_target_page(client):
    h = auth_headers(register(client, email="ada@example.com"))
    t = client.post(
        "/api/v1/targets",
        headers=h,
        json={
            "title": "Backend engineer",
            "description": "Build APIs. Own migrations. Write tests.",
            "track": "software-engineer",
        },
    )
    assert t.status_code in (200, 201), t.text
    target = t.json()
    target = client.post(
        f"/api/v1/targets/{target['id']}/experience",
        headers=h,
        json={"title": "Migration", "requirement_ids": []},
    ).json()
    entry = target["experience"][0]
    assert entry["revision"] == 1
    # Edited in the story bank (another tab): revision 2.
    assert (
        client.patch(
            f"/api/v1/me/stories/{entry['id']}", headers=h, json={"expected_revision": 1, "title": "Newer"}
        ).status_code
        == 200
    )
    stale = client.put(
        f"/api/v1/targets/{target['id']}/experience/{entry['id']}",
        headers=h,
        json={"title": "Older tab", "requirement_ids": [], "expected_revision": 1},
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    story = client.get(f"/api/v1/me/stories/{entry['id']}", headers=h).json()
    assert story["title"] == "Newer"
    fresh = client.put(
        f"/api/v1/targets/{target['id']}/experience/{entry['id']}",
        headers=h,
        json={"title": "Up to date", "requirement_ids": [], "expected_revision": story["revision"]},
    )
    assert fresh.status_code == 200 and fresh.json()["experience"][0]["revision"] == story["revision"] + 1

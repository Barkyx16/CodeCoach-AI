"""Restoring from a backup, with synthetic data only: a real export round-trips into a fresh
account; older/malformed/oversized/unknown files are handled; duplicates and re-imports add
nothing; missing content is never remapped; ids, roles, results and shares in a file are never
trusted; a failure part-way changes nothing; removing a batch keeps later edits; private."""

import json

from sqlalchemy import select

from app.models import (
    Application,
    Bookmark,
    ExperienceEntry,
    ImportBatch,
    Note,
    PracticeAnswer,
    Submission,
    User,
)
from app.services import restore as restore_module
from tests.conftest import auth_headers, register

P = "/api/v1/me/restore"
ALL = ["notes", "stories", "bookmarks", "applications"]


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def seed(client, h):
    """A little of everything, through the real API."""
    client.post(
        "/api/v1/me/notes",
        headers=h,
        json={"title": "Handover tips", "body": "SBAR, then questions.", "tags": ["handover"]},
    )
    client.post(
        "/api/v1/me/notes",
        headers=h,
        json={
            "title": "About a question",
            "body": "Remember the result.",
            "source": {"type": "question", "id": "e-time-0", "track": "registered-nurse"},
        },
    )
    client.post(
        "/api/v1/me/stories",
        headers=h,
        json={
            "title": "Two call lights",
            "situation": "Two patients rang at once.",
            "action": "I triaged by risk.",
            "result": "Both were seen within minutes.",
        },
    )
    client.put(
        "/api/v1/me/bookmarks",
        headers=h,
        json={"item_type": "question", "track": "registered-nurse", "ref_id": "e-time-0"},
    )
    a = client.post(
        "/api/v1/me/applications",
        headers=h,
        json={"employer": "Mercy General", "role_title": "Ward nurse", "stage": "applied"},
    ).json()
    client.post(
        f"/api/v1/me/applications/{a['id']}/events",
        headers=h,
        json={
            "title": "Panel interview",
            "on_date": "2026-11-12",
            "local_time": "10:00",
            "timezone": "Europe/London",
        },
    )


def backup(client, h) -> bytes:
    return json.dumps(client.get("/api/v1/me/export", headers=h).json()).encode()


def preview(client, h, raw: bytes):
    return client.post(f"{P}/preview", headers={**h, "Content-Type": "application/json"}, content=raw)


def apply(client, h, raw: bytes, cats=ALL):
    return client.post(
        P, headers={**h, "Content-Type": "application/json"}, params={"categories": cats}, content=raw
    )


def test_a_real_export_restores_into_a_fresh_account_and_exports_again(client):
    a = nurse(client)
    seed(client, a)
    raw = backup(client, a)
    b = nurse(client, email="bea@example.com")
    pv = preview(client, b, raw)
    assert pv.status_code == 200 and pv.headers["cache-control"] == "no-store"
    body = pv.json()
    cats = {c["key"]: c for c in body["categories"]}
    assert (
        cats["notes"]["new"],
        cats["stories"]["new"],
        cats["bookmarks"]["new"],
        cats["applications"]["new"],
    ) == (2, 1, 1, 1)
    assert body["from_other_account"] is True
    reasons = {u["key"]: u["reason"] for u in body["not_restored"]}
    assert "never restored" in reasons["profile"] and "can't prove" in reasons["submissions"]
    with client.app.state.session_factory() as db:
        assert (
            db.scalars(select(Note).join(User).where(User.email == "bea@example.com")).all() == []
        )  # preview changes nothing
    r = apply(client, b, raw)
    assert r.status_code == 201 and r.json()["counts"]["notes"]["added"] == 2
    again = client.get("/api/v1/me/export", headers=b).json()
    assert {n["title"] for n in again["notes"]} == {"Handover tips", "About a question"}
    assert (
        again["applications"][0]["events"][0]["time"] == "10:00"
        and again["applications"][0]["stage"] == "applied"
    )
    assert again["bookmarks"][0]["item"] == "e-time-0" and again["stories"][0]["title"] == "Two call lights"
    assert again["restores"][0]["status"] == "applied"


def test_the_same_file_twice_adds_nothing_and_duplicates_are_skipped(client):
    h = nurse(client)
    seed(client, h)
    raw = backup(client, h)
    cats = {c["key"]: c for c in preview(client, h, raw).json()["categories"]}
    assert all(
        c["new"] == 0 and c["duplicates"] == c["found"] for c in cats.values()
    )  # all already in this account
    other = nurse(client, email="bea@example.com")
    first = apply(client, other, raw)
    second = apply(client, other, raw)
    assert (
        first.status_code == 201 and second.status_code == 200 and first.json()["id"] == second.json()["id"]
    )
    edited = raw.replace(
        b"SBAR, then questions.", b"SBAR, then questions!"
    )  # a different file, mostly the same content
    third = apply(client, other, edited).json()
    assert third["counts"]["notes"] == {"added": 1, "duplicates": 1, "skipped": 0}
    with client.app.state.session_factory() as db:
        bea = db.scalar(select(User).where(User.email == "bea@example.com"))
        assert len(db.scalars(select(Note).where(Note.user_id == bea.id)).all()) == 3
        assert len(db.scalars(select(Bookmark).where(Bookmark.user_id == bea.id)).all()) == 1


def test_files_that_are_not_backups_are_refused_with_reasons(client):
    h = nurse(client)
    assert preview(client, h, b"{not json").json()["error"]["code"] == "invalid_json"
    assert preview(client, h, b"[1, 2]").json()["error"]["code"] == "not_a_backup"
    old = preview(client, h, json.dumps({"export_version": 0, "notes": []}).encode())
    assert (
        old.status_code == 400
        and old.json()["error"]["code"] == "unsupported_version"
        and old.json()["error"]["details"] == {"supported": [1]}
    )
    big = preview(
        client, h, b'{"export_version": 1, "notes": "' + b"x" * (restore_module.MAX_BYTES + 10) + b'"}'
    )
    assert big.json()["error"]["code"] == "file_too_large"
    # A version-1 file from before stories existed, with unknown fields: read what's there.
    early = {
        "export_version": 1,
        "notes": [{"title": "Old", "body": "b", "colour": "blue"}],
        "mystery": [1, 2],
    }
    body = preview(client, h, json.dumps(early).encode()).json()
    assert {c["key"]: c["new"] for c in body["categories"]} == {
        "notes": 1,
        "stories": 0,
        "bookmarks": 0,
        "applications": 0,
    }
    assert (
        body["ignored_fields"] == 1
        and {"key": "mystery", "count": 2, "reason": "Not recognised, so it's ignored."}
        in body["not_restored"]
    )
    assert client.post(f"{P}/preview", content=b"{}").status_code == 401


def test_missing_content_is_never_remapped_and_tampering_is_ignored(client):
    h = nurse(client)
    victim = nurse(client, email="vic@example.com")
    story = client.post("/api/v1/me/stories", headers=victim, json={"title": "Victim's story"}).json()
    data = {
        "export_version": 1,
        "profile": {"id": "someone-else", "email": "admin@example.com", "is_admin": True},
        "submissions": [{"problem": "two-sum", "status": "accepted", "passed": 99}],
        "answers": [{"question": "e-time-0", "score": 100}],
        "shares": [{"token": "abc"}],
        "bookmarks": [
            {
                "type": "question",
                "career": "registered-nurse",
                "item": "e-time-999",
            },  # gone: not mapped to a similar one
            {"type": "problem", "item": "not-a-problem"},
        ],
        "notes": [
            {
                "title": "Points at nothing",
                "body": "keep me",
                "source": {"type": "question", "id": "zzz", "career": "registered-nurse"},
            }
        ],
        "stories": [{"id": story["id"], "title": "Mine now?", "situation": "x"}],
    }
    raw = json.dumps(data).encode()
    cats = {c["key"]: c for c in preview(client, h, raw).json()["categories"]}
    assert cats["bookmarks"]["new"] == 0 and sum(s["count"] for s in cats["bookmarks"]["skipped"]) == 2
    assert any("link is left out" in s["reason"] for s in cats["notes"]["skipped"])
    apply(client, h, raw)
    with client.app.state.session_factory() as db:
        me = db.scalar(select(User).where(User.email == "ada@example.com"))
        assert me.is_admin is False and me.email == "ada@example.com"
        assert db.scalars(select(Submission)).all() == [] and db.scalars(select(PracticeAnswer)).all() == []
        note = db.scalar(select(Note).where(Note.user_id == me.id))
        assert note.body == "keep me" and note.source_id is None
        theirs = db.get(ExperienceEntry, story["id"])
        assert (
            theirs.title == "Victim's story" and theirs.user_id != me.id
        )  # an id in a file never reaches another account
        mine = db.scalar(select(ExperienceEntry).where(ExperienceEntry.user_id == me.id))
        assert mine.id != story["id"]


def test_a_failure_part_way_changes_nothing(client, monkeypatch):
    h = nurse(client)
    seed(client, h)
    raw = backup(client, h)
    other = nurse(client, email="bea@example.com")

    def boom(self, item):
        raise RuntimeError("disk full")

    monkeypatch.setattr(restore_module.Restore, "_add_stories", boom)  # the last kind written
    r = apply(client, other, raw)
    assert r.status_code == 400 and r.json()["error"]["code"] == "restore_failed"
    with client.app.state.session_factory() as db:
        bea = db.scalar(select(User).where(User.email == "bea@example.com"))
        assert (
            db.scalars(select(Note).where(Note.user_id == bea.id)).all() == []
        )  # written before the failure, rolled back
        assert [b.status for b in db.scalars(select(ImportBatch).where(ImportBatch.user_id == bea.id))] == [
            "failed"
        ]
    monkeypatch.undo()
    assert apply(client, other, raw).status_code == 201  # and it can simply be tried again


def test_removing_a_batch_keeps_later_edits_and_is_owner_only(client):
    h = nurse(client)
    seed(client, h)
    raw = backup(client, h)
    b = nurse(client, email="bea@example.com")
    batch = apply(client, b, raw).json()
    notes = client.get("/api/v1/me/notes", headers=b).json()["items"]
    edited = next(n for n in notes if n["title"] == "Handover tips")
    client.patch(
        f"/api/v1/me/notes/{edited['id']}",
        headers=b,
        json={"body": "SBAR, then questions. Edited later.", "base_revision": edited["revision"]},
    )
    assert client.post(f"{P}/batches/{batch['id']}/remove", headers=h).status_code == 404  # not theirs
    out = client.post(f"{P}/batches/{batch['id']}/remove", headers=b).json()
    assert out["status"] == "removed" and out["removal"] == {
        "removed": 4,
        "kept_edited": 1,
        "already_gone": 0,
    }
    left = client.get("/api/v1/me/notes", headers=b).json()["items"]
    assert [n["title"] for n in left] == ["Handover tips"]
    assert "Edited later" in client.get(f"/api/v1/me/notes/{edited['id']}", headers=b).json()["body"]
    with client.app.state.session_factory() as db:
        bea = db.scalar(select(User).where(User.email == "bea@example.com"))
        assert db.scalars(select(Application).where(Application.user_id == bea.id)).all() == []
    assert (
        client.post(f"{P}/batches/{batch['id']}/remove", headers=b).json()["removal"]["removed"] == 4
    )  # idempotent


def test_restores_are_exported_and_deleted_with_the_account(client):
    h = nurse(client)
    seed(client, h)
    raw = backup(client, h)
    b = nurse(client, email="bea@example.com")
    apply(client, b, raw, ["notes"])
    assert [x["categories"] for x in client.get(f"{P}/batches", headers=b).json()] == [["notes"]]
    assert client.get(f"{P}/batches", headers=h).json() == []
    client.request(
        "DELETE", "/api/v1/auth/me", headers=b, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert db.scalars(select(ImportBatch)).all() == []


def test_a_backup_never_carries_credentials(client):
    h = nurse(client)
    seed(client, h)
    text = backup(client, h).decode()
    with client.app.state.session_factory() as db:
        me = db.scalar(select(User).where(User.email == "ada@example.com"))
        assert me.password_hash not in text
    assert (
        "password" not in text and "token_version" not in text and h["Authorization"].split()[1] not in text
    )

"""An application's private notes are revision-checked (Volume 8, prompt 5; docs/PERSISTENCE.md).

They were last-write-wins: two devices editing them from the same start silently kept only the
later save. Now a notes change names the revision it started from; a stale one is refused with
the saved notes to compare; other fields never need it and never conflict with the notes; and a
keyed save whose reply was lost is recognised as having gone through."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from tests.conftest import auth_headers, register
from tests.test_storage import needs_admin, rehearsal, run  # noqa: F401  (rehearsal: a fixture)

URL = "/api/v1/me/applications"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def app_with_notes(client, h, notes="Recruiter: Sam") -> dict:
    r = client.post(
        URL, headers=h, json={"employer": "Mercy General", "role_title": "Ward nurse", "notes": notes}
    )
    assert r.status_code == 201, r.text
    return r.json()


def patch(client, h, app_id, **body):
    return client.patch(f"{URL}/{app_id}", headers=h, json=body)


def test_two_devices_from_the_same_base_one_saves_the_other_compares(client):
    h = nurse(client)
    a = app_with_notes(client, h)
    assert a["notes_revision"] == 1
    phone = patch(client, h, a["id"], notes="Recruiter: Sam. Panel on Tuesday.", notes_expected_revision=1)
    assert phone.status_code == 200 and phone.json()["notes_revision"] == 2
    laptop = patch(client, h, a["id"], notes="Recruiter: Sam. Bring references.", notes_expected_revision=1)
    assert laptop.status_code == 409 and laptop.json()["error"]["code"] == "notes_conflict"
    details = laptop.json()["error"]["details"]
    assert details == {"current_revision": 2, "current": "Recruiter: Sam. Panel on Tuesday."}
    assert client.get(f"{URL}/{a['id']}", headers=h).json()["notes"] == "Recruiter: Sam. Panel on Tuesday."
    # The laptop chooses, having seen both: saving over revision 2 is deliberate.
    kept = patch(
        client, h, a["id"], notes="Both: Panel on Tuesday; bring references.", notes_expected_revision=2
    )
    assert kept.status_code == 200 and kept.json()["notes_revision"] == 3


def test_other_fields_never_need_the_revision_and_never_conflict_with_the_notes(client):
    h = nurse(client)
    a = app_with_notes(client, h)
    patch(client, h, a["id"], notes="Changed on the phone", notes_expected_revision=1)
    # A stale page edits the next action and sends its unchanged-on-that-page notes along? No:
    # it sends only what it changed. The next action saves, the notes and their revision stay.
    r = patch(client, h, a["id"], next_action="Send thank-you email", next_action_due="2026-11-20")
    assert r.status_code == 200 and r.json()["next_action"] == "Send thank-you email"
    assert (r.json()["notes"], r.json()["notes_revision"]) == ("Changed on the phone", 2)
    client.post(f"{URL}/{a['id']}/stage", headers=h, json={"stage": "applied"})
    assert client.get(f"{URL}/{a['id']}", headers=h).json()["notes_revision"] == 2
    # The same notes text again, with or without a revision, changes nothing.
    same = patch(client, h, a["id"], notes="Changed on the phone")
    assert same.status_code == 200 and same.json()["notes_revision"] == 2


def test_a_notes_change_without_its_revision_is_refused_not_guessed(client):
    h = nurse(client)
    a = app_with_notes(client, h)
    r = patch(client, h, a["id"], notes="An older page's notes")
    assert r.status_code == 428 and r.json()["error"]["code"] == "notes_revision_required"
    assert client.get(f"{URL}/{a['id']}", headers=h).json()["notes"] == "Recruiter: Sam"


def test_a_lost_reply_is_recognised_not_reported_as_a_conflict(client):
    h = nurse(client)
    a = app_with_notes(client, h)
    body = {"notes": "Panel on Tuesday", "notes_expected_revision": 1, "client_request_id": "notes-save-01"}
    first = patch(client, h, a["id"], **body)
    again = patch(client, h, a["id"], **body)  # its reply was lost
    assert first.json()["notes_revision"] == 2
    assert again.status_code == 200 and again.json()["save_replay"] == {
        "accepted_revision": 2,
        "current_revision": 2,
    }
    assert again.json()["notes_revision"] == 2
    # The same key with other notes isn't a retry.
    other = patch(client, h, a["id"], **{**body, "notes": "Something else"})
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_key_reused"


def test_another_account_finds_nothing_and_the_list_never_carries_notes(client):
    h = nurse(client)
    a = app_with_notes(client, h, notes="PRIVATE-NOTES-MARKER")
    client.cookies.clear()
    bea = nurse(client, email="bea@example.com")
    r = patch(client, bea, a["id"], notes="Bea's", notes_expected_revision=1)
    assert r.status_code == 404 and "PRIVATE" not in r.text
    r = patch(client, bea, a["id"], notes="Bea's", notes_expected_revision=99)
    assert r.status_code == 404 and "PRIVATE" not in r.text  # a revision is never access
    assert "PRIVATE" not in client.get(URL, headers=h).text  # the board's list
    assert client.get(f"{URL}/{a['id']}", headers=h).json()["notes"] == "PRIVATE-NOTES-MARKER"


def test_export_and_deletion_still_carry_and_remove_the_notes(client):
    h = nurse(client)
    a = app_with_notes(client, h, notes="Kept for export")
    exported = client.get("/api/v1/me/export", headers=h).json()["applications"]
    assert [x["notes"] for x in exported] == ["Kept for export"]
    assert client.delete(f"{URL}/{a['id']}", headers=h).status_code in (200, 204)
    assert client.get(f"{URL}/{a['id']}", headers=h).status_code == 404


@needs_admin
def test_the_migration_keeps_every_note_and_starts_them_at_revision_1(rehearsal):  # noqa: F811
    url = rehearsal.admin
    run(["alembic", "upgrade", "7045bdb6a532"], url)
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id, email, auth_provider_id, is_guest, is_admin, token_version, created_at,"
                " career_track) VALUES ('u1', 'notes@example.com', 'password:u1', false, false, 0,"
                " '2026-11-01 10:00:00+00', 'registered-nurse')"
            )
        )
        db.execute(
            text(
                "INSERT INTO applications (id, user_id, employer, role_title, stage, archived, created_at,"
                " updated_at, story_ids, next_action, notes) VALUES ('a1', 'u1', 'Mercy', 'RN', 'saved', false,"
                " '2026-11-01 10:00:00+00', '2026-11-01 10:00:00+00', '[]', '', 'Written before the revision')"
            )
        )
    run(["alembic", "upgrade", "head"], url)
    with engine.connect() as db:
        row = db.execute(text("SELECT notes, notes_revision FROM applications WHERE id = 'a1'")).one()
        assert tuple(row) == ("Written before the revision", 1)
    engine.dispose()
    run(["alembic", "downgrade", "7045bdb6a532"], url)  # and back: the column goes, the notes stay
    engine = create_engine(url)
    with engine.connect() as db:
        assert (
            db.scalar(text("SELECT notes FROM applications WHERE id = 'a1'")) == "Written before the revision"
        )
    engine.dispose()

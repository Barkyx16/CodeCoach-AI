"""A save whose reply was lost is recovered as the learner's own success (Volume 8, prompt 3).

Stories, notes, kits, whiteboard drafts and reflections are saved against a base revision. A save
that went through but whose reply never arrived, sent again, used to meet its own new revision and
read as "changed elsewhere". With a key, the server keeps a receipt of the accepted save (in the
same transaction), and the retry is answered "went through as revision N", with the entity as it
is now. What stays protected:
- another device's later save is never overwritten, and is reported separately (current_revision);
- a real two-device conflict still shows both versions;
- the same key with changed content is refused, not replayed past the revision check;
- a deleted entity isn't recreated; another account finds nothing;
- without a receipt (no key, or it expired) a stale save is a conflict, as before.
Synthetic accounts; SQLite and PostgreSQL."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.models import StoryRevision, UpdateReceipt
from app.services import update_receipts
from tests.conftest import TEST_DATABASE_URL, auth_headers, register
from tests.test_kits import event as kit_event
from tests.test_reflections import event as reflection_event
from tests.test_stories import STORY, URL, nurse
from tests.test_whiteboard import DIAGRAM, P
from tests.test_whiteboard import URL as WB


def story(client, h) -> dict:
    r = client.post(URL, headers=h, json=STORY)
    assert r.status_code == 201, r.text
    return r.json()


def save(client, h, sid, key, base, **fields):
    body = {"expected_revision": base, **fields}
    if key:
        body["client_request_id"] = key
    return client.patch(f"{URL}/{sid}", headers=h, json=body)


def revisions(client, sid) -> int:
    with client.app.state.session_factory() as db:
        return (
            db.scalar(select(func.count()).select_from(StoryRevision).where(StoryRevision.story_id == sid))
            or 0
        )


def code(r) -> str | None:
    return r.json().get("error", {}).get("code") if r.status_code >= 400 else None


# --- the story editor: every case ----------------------------------------------------------------


def test_a_lost_save_retried_is_the_same_accepted_revision_not_a_conflict(client):
    h = nurse(client)
    s = story(client, h)
    first = save(client, h, s["id"], "save-key-0001", 1, situation="A busier night.")
    assert first.status_code == 200 and first.json()["revision"] == 2 and first.json()["save_replay"] is None
    # The reply was lost; the page sends the same save again (twice, even).
    for _ in range(2):
        again = save(client, h, s["id"], "save-key-0001", 1, situation="A busier night.")
        assert again.status_code == 200, again.text
        assert again.json()["save_replay"] == {"accepted_revision": 2, "current_revision": 2}
        assert again.json()["revision"] == 2 and again.json()["situation"] == "A busier night."
    assert revisions(client, s["id"]) == 2  # created + one edit: nothing saved twice
    # Without the key, the same retry is what it always was: a conflict with its own save.
    assert code(save(client, h, s["id"], None, 1, situation="A busier night.")) == "stale_revision"


def test_a_later_save_from_another_device_is_kept_and_reported_separately(client):
    h = nurse(client)
    s = story(client, h)
    assert save(client, h, s["id"], "phone-save-01", 1, situation="From the phone.").json()["revision"] == 2
    # The laptop saw revision 2 and saved over it (its own key).
    laptop = save(client, h, s["id"], "laptop-save-1", 2, situation="From the laptop.")
    assert laptop.json()["revision"] == 3
    # The phone's lost reply is retried: its save went through (2); the story is now 3, the laptop's.
    retry = save(client, h, s["id"], "phone-save-01", 1, situation="From the phone.")
    assert retry.status_code == 200
    assert retry.json()["save_replay"] == {"accepted_revision": 2, "current_revision": 3}
    assert retry.json()["situation"] == "From the laptop."  # the newer one, never the old snapshot
    assert client.get(f"{URL}/{s['id']}", headers=h).json()["situation"] == "From the laptop."
    assert revisions(client, s["id"]) == 3


def test_real_conflicts_stay_conflicts_and_a_reused_key_cannot_skip_the_check(client):
    h = nurse(client)
    s = story(client, h)
    save(client, h, s["id"], "tab-a-save-01", 1, situation="Tab A.")
    # Tab B never saved: its stale save is a real conflict, with both versions.
    tab_b = save(client, h, s["id"], "tab-b-save-01", 1, situation="Tab B.")
    assert code(tab_b) == "stale_revision"
    assert tab_b.json()["error"]["details"]["current"]["situation"] == "Tab A."
    # Tab A's key with other words (or another base) isn't a retry: refused, nothing written.
    for r in (
        save(client, h, s["id"], "tab-a-save-01", 1, situation="Something else."),
        save(client, h, s["id"], "tab-a-save-01", 2, situation="Tab A."),
    ):
        assert code(r) == "idempotency_key_reused", r.text
    assert client.get(f"{URL}/{s['id']}", headers=h).json()["situation"] == "Tab A."
    # Typing continued after the save: that's a new save with a new key, against revision 2.
    more = save(client, h, s["id"], "tab-a-save-02", 2, situation="Tab A, and more.")
    assert more.json()["revision"] == 3 and more.json()["save_replay"] is None


def test_a_deleted_story_isnt_recreated_and_another_account_finds_nothing(client):
    h = nurse(client)
    s = story(client, h)
    save(client, h, s["id"], "gone-save-001", 1, situation="Saved, then deleted.")
    client.cookies.clear()
    bea = nurse(client, email="bea@example.com")
    # Bea, with Ada's story id and key: not found, and nothing about it.
    r = save(client, bea, s["id"], "gone-save-001", 1, situation="Saved, then deleted.")
    assert r.status_code == 404 and "deleted" not in r.text
    assert client.delete(f"{URL}/{s['id']}", headers=h).status_code in (200, 204)
    r = save(client, h, s["id"], "gone-save-001", 1, situation="Saved, then deleted.")
    assert r.status_code == 404
    assert client.get(f"{URL}/{s['id']}", headers=h).status_code == 404


def test_expired_evidence_is_a_conflict_again_and_housekeeping_removes_it(client):
    h = nurse(client)
    s = story(client, h)
    save(client, h, s["id"], "old-save-0001", 1, situation="Last week.")
    old = datetime.now(UTC) - timedelta(days=update_receipts.UPDATE_RECEIPT_DAYS, minutes=1)
    with client.app.state.session_factory() as db:
        db.execute(update(UpdateReceipt).values(created_at=old))
        db.commit()
    # No proof any more that this request made revision 2: the safe answer is the conflict.
    assert code(save(client, h, s["id"], "old-save-0001", 1, situation="Last week.")) == "stale_revision"
    with client.app.state.session_factory() as db:
        assert update_receipts.purge(db) == 1
        db.commit()
        assert db.scalar(select(func.count()).select_from(UpdateReceipt)) == 0


def test_a_receipt_holds_no_content(client):
    h = nurse(client)
    s = story(client, h)
    save(client, h, s["id"], "plain-save-01", 1, situation="PRIVATE-MARKER words.")
    with client.app.state.session_factory() as db:
        r = db.scalars(select(UpdateReceipt)).one()
    stored = " ".join(str(getattr(r, c.key)) for c in UpdateReceipt.__table__.columns)
    assert "PRIVATE" not in stored and r.request_fingerprint.startswith("v1:")
    assert (r.entity, r.base_revision, r.accepted_revision) == ("story", 1, 2)


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="row locks: PostgreSQL")
def test_two_copies_of_one_save_at_once_make_one_revision(client):
    h = nurse(client)
    s = story(client, h)
    start = threading.Barrier(2)
    out: list = []

    def send():
        start.wait(5)
        out.append(save(client, h, s["id"], "twin-save-001", 1, situation="Sent twice at once."))

    threads = [threading.Thread(target=send, daemon=True) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert [r.status_code for r in out] == [200, 200], [r.text for r in out]
    assert sorted(bool(r.json()["save_replay"]) for r in out) == [False, True]
    assert revisions(client, s["id"]) == 2


# --- the other editors: the same contract --------------------------------------------------------


def test_note_kit_whiteboard_and_reflection_saves_recover_the_same_way(client):
    h = nurse(client)
    # Note
    n = client.post("/api/v1/me/notes", headers=h, json={"title": "Handover", "body": "first"}).json()
    body = {"base_revision": n["revision"], "body": "second", "client_request_id": "note-save-001"}
    first = client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json=body).json()
    again = client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json=body)
    assert again.status_code == 200 and again.json()["save_replay"]["accepted_revision"] == first["revision"]
    assert code(client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json={**body, "body": "third"})) == (
        "idempotency_key_reused"
    )
    assert code(
        client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json={**body, "client_request_id": None})
    ) == ("note_conflict")

    # Kit
    _, _, kit_url = kit_event(client, h)
    body = {"notes": "Bring the badge", "expected_revision": 0, "client_request_id": "kit-save-0001"}
    assert client.put(kit_url, headers=h, json=body).json()["revision"] == 1
    again = client.put(kit_url, headers=h, json=body)
    assert again.status_code == 200 and again.json()["save_replay"] == {
        "accepted_revision": 1,
        "current_revision": 1,
    }
    assert (
        code(client.put(kit_url, headers=h, json={**body, "client_request_id": "kit-save-0002"}))
        == "stale_revision"
    )

    # Reflection
    _, _, refl_url = reflection_event(client, h)
    body = {"clear": "My opening", "expected_revision": 0, "client_request_id": "refl-save-001"}
    assert client.put(refl_url, headers=h, json=body).json()["revision"] == 1
    client.put(
        refl_url,
        headers=h,
        json={"clear": "Elsewhere", "expected_revision": 1, "client_request_id": "refl-save-002"},
    )
    again = client.put(refl_url, headers=h, json=body)
    assert again.json()["save_replay"] == {"accepted_revision": 1, "current_revision": 2}
    assert again.json()["clear"] == "Elsewhere"

    # Whiteboard draft (another account, a coding career)
    client.cookies.clear()
    lin = auth_headers(register(client, email="lin@example.com", display_name="Lin"))
    body = {
        "diagram": DIAGRAM,
        "explanation": "draft",
        "expected_revision": 0,
        "client_request_id": "wb-save-0001",
    }
    assert client.put(f"{WB}/{P}/draft", headers=lin, json=body).json()["revision"] == 1
    again = client.put(f"{WB}/{P}/draft", headers=lin, json=body)
    assert again.status_code == 200 and again.json()["save_replay"]["accepted_revision"] == 1
    # Another account with Lin's key: its own draft, saved normally; nothing of Lin's.
    client.cookies.clear()
    kim = auth_headers(register(client, email="kim@example.com", display_name="Kim"))
    theirs = client.put(f"{WB}/{P}/draft", headers=kim, json={**body, "explanation": "Kim's"})
    assert theirs.status_code == 200 and theirs.json()["save_replay"] is None
    assert theirs.json()["revision"] == 1 and theirs.json()["explanation"] == "Kim's"


def test_every_receipt_entity_name_fits_its_column():
    """PostgreSQL enforces the column's length and SQLite doesn't: an entity name that's too long
    only failed on PostgreSQL (found while adding `app_notes`)."""
    from typing import get_args

    width = UpdateReceipt.__table__.c.entity.type.length
    assert all(len(name) <= width for name in get_args(update_receipts.Entity)), get_args(
        update_receipts.Entity
    )

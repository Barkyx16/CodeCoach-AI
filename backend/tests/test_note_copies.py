"""Keep both after a note conflict makes one copy, whatever happens to the reply (Volume 8, prompt 4).

The copy is a keyed note create with `copy_of`: one key per decision (the exact text chosen). A
double click, two copies at once, or a retry after a lost reply returns the copy already made.
Changed text or a deliberate second copy is a new key, so a new note. A copy that was made and then
deleted isn't silently made again: 410 `copy_deleted`. The source note is never changed; its
learner-visible link (the question or problem it's about) comes along only if the source is the
caller's own. Another account's note id is treated exactly like a missing one."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.models import Note, UpdateReceipt
from app.services import update_receipts
from tests.conftest import TEST_DATABASE_URL, auth_headers, register

URL = "/api/v1/me/notes"


def source_note(client, h, **over) -> dict:
    body = {
        "title": "Handover",
        "body": "Saved elsewhere",
        "source": {"type": "problem", "id": "two-sum"},
        **over,
    }
    r = client.post(URL, headers=h, json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def copy(client, h, of, key, body="Mine: the version on this page", title="Handover (my version)"):
    return client.post(
        URL, headers=h, json={"title": title, "body": body, "copy_of": of, "client_request_id": key}
    )


def notes(client) -> list[Note]:
    with client.app.state.session_factory() as db:
        return list(db.scalars(select(Note).order_by(Note.created_at)))


def test_a_repeated_or_retried_copy_makes_one_note_and_never_touches_the_source(client, user_headers):
    h = user_headers
    src = source_note(client, h)
    first = copy(client, h, src["id"], "copy-key-0001")
    assert first.status_code in (200, 201), first.text
    for _ in range(2):  # a double click, then a retry after a lost reply
        again = copy(client, h, src["id"], "copy-key-0001")
        assert again.status_code in (200, 201) and again.json()["id"] == first.json()["id"]
    rows = notes(client)
    assert len(rows) == 2
    original = next(n for n in rows if n.id == src["id"])
    assert (original.body, original.revision) == ("Saved elsewhere", src["revision"])  # untouched
    made = first.json()
    assert made["title"] == "Handover (my version)" and made["body"] == "Mine: the version on this page"
    # The learner-visible link of their own source comes along; nothing else does.
    assert made["source"]["id"] == "two-sum" and made["revision"] == 1 and made["pinned"] is False


def test_changed_text_or_a_deliberate_second_copy_is_a_new_note_and_a_reused_key_is_refused(
    client, user_headers
):
    h = user_headers
    src = source_note(client, h)
    copy(client, h, src["id"], "copy-key-0001")
    # The same key with other text isn't a retry of that copy: refused, nothing made.
    r = copy(client, h, src["id"], "copy-key-0001", body="Something else")
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"
    # A new decision (new key): a second copy, even of the same text.
    second = copy(client, h, src["id"], "copy-key-0002")
    assert second.status_code in (200, 201)
    assert len(notes(client)) == 3


def test_a_copy_made_then_deleted_is_not_made_again(client, user_headers):
    h = user_headers
    src = source_note(client, h)
    made = copy(client, h, src["id"], "copy-key-gone").json()
    assert client.delete(f"{URL}/{made['id']}", headers=h).status_code in (200, 204)
    r = copy(client, h, src["id"], "copy-key-gone")
    assert r.status_code == 410 and r.json()["error"]["code"] == "copy_deleted"
    # Purged after the undo window: still not made again while the receipt lasts.
    with client.app.state.session_factory() as db:
        db.execute(
            update(Note)
            .where(Note.id == made["id"])
            .values(deleted_at=datetime.now(UTC) - timedelta(days=60))
        )
        db.commit()
    client.get(URL, headers=h)  # listing purges old deleted notes
    r = copy(client, h, src["id"], "copy-key-gone")
    assert r.status_code == 410
    # A deliberate new copy is a new key: made.
    assert copy(client, h, src["id"], "copy-key-new1").status_code in (200, 201)


def test_a_missing_or_someone_elses_source_gives_a_plain_copy_and_reveals_nothing(client):
    ada = auth_headers(register(client, email="ada@example.com"))
    theirs = source_note(client, ada, title="Ada's", body="Ada's private words")
    client.cookies.clear()
    bea = auth_headers(register(client, email="bea@example.com"))
    with_their_id = copy(client, bea, theirs["id"], "bea-copy-0001", body="Bea's words")
    missing = copy(client, bea, "00000000-0000-0000-0000-000000000000", "bea-copy-0002", body="Bea's words")
    for r in (with_their_id, missing):
        assert r.status_code in (200, 201), r.text
        assert r.json()["source"] is None and "Ada" not in r.text
    by_id = {n.id: n for n in notes(client)}
    assert by_id[theirs["id"]].body == "Ada's private words"  # never touched
    # Bea's copy with Ada's id and Bea's copy with a missing id look exactly alike.
    a, b = with_their_id.json(), missing.json()
    assert {k: v for k, v in a.items() if k not in ("id", "created_at", "updated_at", "title")} == {
        k: v for k, v in b.items() if k not in ("id", "created_at", "updated_at", "title")
    }


def test_a_copy_needs_a_key(client, user_headers):
    src = source_note(client, user_headers)
    r = client.post(URL, headers=user_headers, json={"title": "x", "body": "y", "copy_of": src["id"]})
    assert r.status_code in (400, 422) and "client_request_id" in r.text


def test_the_receipt_holds_no_content_and_expires(client, user_headers):
    h = user_headers
    src = source_note(client, h)
    made = copy(client, h, src["id"], "copy-key-0001", body="PRIVATE-MARKER")
    with client.app.state.session_factory() as db:
        r = db.scalars(select(UpdateReceipt)).one()
        assert (r.entity, r.entity_id) == ("note_copy", made.json()["id"])
        assert "PRIVATE" not in " ".join(str(getattr(r, c.key)) for c in UpdateReceipt.__table__.columns)
        db.execute(update(UpdateReceipt).values(created_at=datetime.now(UTC) - timedelta(days=8)))
        db.commit()
        assert update_receipts.purge(db) == 1
        db.commit()
    # Without the receipt, the note's own key still finds the copy.
    assert (
        copy(client, h, src["id"], "copy-key-0001", body="PRIVATE-MARKER").json()["id"] == made.json()["id"]
    )


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="concurrent writers: PostgreSQL")
def test_two_identical_copies_at_once_make_one_note(client, user_headers):
    h = user_headers
    src = source_note(client, h)
    start = threading.Barrier(2)
    out: list = []

    def send():
        start.wait(5)
        out.append(copy(client, h, src["id"], "twin-copy-001"))

    threads = [threading.Thread(target=send, daemon=True) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert [r.status_code in (200, 201) for r in out] == [True, True], [r.text for r in out]
    assert out[0].json()["id"] == out[1].json()["id"]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Note)) == 2

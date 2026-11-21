"""Duplicate a collection (Volume 16, prompt 8; docs/BULK_ACTIONS.md, docs/STORY_FRESHNESS.md): a new
collection ("… (copy)", renamed freely, never a name already here in any letter case) with the same
items in the same order, each at the version it was added at and with its "Mark reviewed" copied as
the copy's own record; the copy's queue starts fresh and the original is unchanged; the collection
limit applies, said before it's reached; a retried request makes one copy; an item whose content left
the library is carried as unavailable, never swapped or dropped; removing or reviewing in one never
touches the other or the saved list. Within one account only. Synthetic data only."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import PracticeCollection, SourceReview
from app.services import explore
from tests.test_collection_restore import DRILL, OTHER_Q, prepared, view
from tests.test_content_quality import admin, nurse
from tests.test_note_freshness import NURSE, QID
from tests.test_row_level_security import pytestmark_pg
from tests.test_saved_freshness import (
    COLLECTIONS,
    PROBLEM,
    QUESTION,
    SAVED,
    collection,
    item_of,
    review_item,
    save,
)

KEY = "copy-request-0001"


def duplicate(client, h, cid, **body):
    return client.post(f"{COLLECTIONS}/{cid}/duplicate", headers=h, json=body)


def copied(client, h, cid, **body):
    r = duplicate(client, h, cid, **body)
    assert r.status_code == 201, r.text
    return r.json()


def reviews_of(client, holder_id):
    with client.app.state.session_factory() as db:
        return [
            (r.to_revision, r.decision)
            for r in db.scalars(select(SourceReview).where(SourceReview.holder_id == holder_id))
        ]


def test_the_copy_keeps_the_items_order_versions_and_reviews_and_starts_a_fresh_queue(client):
    h = nurse(client)
    cid = prepared(client, h)  # reordered, one done, one reviewed at version 2, queue at item 3
    before = view(client, h, cid)
    out = copied(client, h, cid)
    assert out["name"] == "Night shift prep (copy)" and out["copied_from_id"] == cid
    assert out["id"] != cid and out["queue_position"] == 0 and out["queue_started"] is False
    assert out["queue_done"] == 0 and not any(i["queue_done"] for i in out["item_list"])
    same = ("item_type", "track", "ref_id", "position", "content_version")
    assert [{k: i[k] for k in same} for i in out["item_list"]] == [
        {k: i[k] for k in same} for i in before["items"]
    ]
    # The reviewed item shows reviewed in the copy, at the same version, as the copy's own record.
    orig = item_of(client, h, cid)
    mine = next(i for i in out["item_list"] if i["ref_id"] == QID)
    assert mine["freshness"] == orig["freshness"] and orig["freshness"]["reviewed_version"] == 2
    assert mine["freshness"]["text"].startswith("You marked it reviewed at version 2")
    assert reviews_of(client, mine["id"]) == reviews_of(client, orig["id"]) == [(2, "reviewed")]
    assert view(client, h, cid) == before  # the original is unchanged


def test_marking_done_and_moving_the_copys_queue_leaves_the_originals_as_it_was(client):
    h = nurse(client)
    cid = prepared(client, h)
    before = view(client, h, cid)
    out = copied(client, h, cid)
    first = out["item_list"][0]["id"]
    assert (
        client.put(
            f"{COLLECTIONS}/{out['id']}/items/{first}/done", headers=h, json={"done": True}
        ).status_code
        == 200
    )
    assert client.put(f"{COLLECTIONS}/{out['id']}/queue", headers=h, json={"position": 3}).status_code == 200
    assert view(client, h, cid) == before
    original = client.get(f"{COLLECTIONS}/{cid}", headers=h).json()
    assert original["queue_done"] == 1 and original["queue_position"] == 2


def test_reviewing_or_removing_in_one_never_changes_the_other_or_the_saved_list(client):
    h = nurse(client)
    save(client, h, QUESTION)

    def saved():
        return [
            (b["id"], b["ref_id"], b["content_version"], b["freshness"]["reviewed_version"])
            for b in client.get(SAVED, headers=h).json()
        ]

    saved_before = saved()
    c = collection(client, h, "Ward round", (QUESTION, PROBLEM))
    out = copied(client, h, c["id"])
    from tests.test_note_freshness import correct

    correct(client, admin(client))  # version 2: both ask for a review
    copy_item = item_of(client, h, out["id"])
    assert review_item(client, h, out["id"], copy_item["id"], 2).status_code == 200
    assert item_of(client, h, c["id"])["freshness"]["state"] == "needs_review"  # the original still asks
    # Removing it from the original leaves the copy's item, and its review, where they are.
    orig_item = item_of(client, h, c["id"])
    assert client.delete(f"{COLLECTIONS}/{c['id']}/items/{orig_item['id']}", headers=h).status_code == 200
    assert item_of(client, h, out["id"])["freshness"]["reviewed_version"] == 2
    assert reviews_of(client, copy_item["id"]) == [(2, "reviewed")]
    assert saved() == saved_before  # bookmarks untouched: none added, none reviewed


def test_a_retried_request_makes_one_copy(client):
    h = nurse(client)
    c = collection(client, h, "Ward round", (QUESTION, PROBLEM))
    first = copied(client, h, c["id"], client_request_id=KEY)
    again = duplicate(client, h, c["id"], client_request_id=KEY)
    assert again.status_code == 200 and again.json()["id"] == first["id"]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PracticeCollection)) == 2
    # The same key for another collection's copy is refused, and makes nothing.
    other = collection(client, h, "Other", (PROBLEM,))
    r = duplicate(client, h, other["id"], client_request_id=KEY)
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"
    # Without a key, a second copy is a second copy, numbered.
    assert copied(client, h, c["id"])["name"] == "Ward round (copy 2)"


def test_the_name_is_checked_in_any_letter_case_and_can_be_chosen(client):
    h = nurse(client)
    c = collection(client, h, "Ward round", (QUESTION,))
    collection(client, h, "WARD ROUND (copy)", ())
    assert copied(client, h, c["id"])["name"] == "Ward round (copy 2)"  # the default skips a taken name
    r = duplicate(client, h, c["id"], name="ward  round")
    assert r.status_code == 409 and r.json()["error"]["code"] == "name_taken"
    assert "already have a collection called “ward round”" in r.json()["error"]["message"]
    assert copied(client, h, c["id"], name="  Night  list ")["name"] == "Night list"
    long = collection(client, h, "x" * 80, ())
    assert copied(client, h, long["id"])["name"] == "x" * 73 + " (copy)"  # within the 80-character limit


def test_the_limit_applies_and_is_said(client, monkeypatch):
    monkeypatch.setattr(explore, "MAX_COLLECTIONS", 2)
    h = nurse(client)
    c = collection(client, h, "Ward round", (QUESTION,))
    copied(client, h, c["id"])
    r = duplicate(client, h, c["id"])
    assert r.status_code == 400 and r.json()["error"]["code"] == "too_many_collections"
    assert r.json()["error"]["details"] == {"limit": 2, "count": 2}
    assert "delete one to make room for a copy" in r.json()["error"]["message"]


def test_a_retired_or_removed_item_is_carried_as_unavailable_never_dropped(client):
    h = nurse(client)
    c = collection(client, h, "Mixed", (QUESTION, OTHER_Q, DRILL))
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{QID}/retire",
        headers=admin(client),
        json={"reason": "Too vague."},
    )
    assert r.status_code == 200, r.text
    with client.app.state.session_factory() as db:  # a drill that's no longer offered
        from app.models import CollectionItem

        db.query(CollectionItem).filter(CollectionItem.ref_id == "example").update({"ref_id": "gone-drill"})
        db.commit()
    original = client.get(f"{COLLECTIONS}/{c['id']}", headers=h).json()["item_list"]
    out = copied(client, h, c["id"])["item_list"]
    shown = ("ref_id", "title", "available", "unavailable_reason", "position")
    assert [{k: i[k] for k in shown} for i in out] == [{k: i[k] for k in shown} for i in original]
    assert [i["available"] for i in out] == [False, True, False]
    assert out[0]["unavailable_reason"] == "Retired: Too vague."


def test_the_order_holds_after_a_reload_and_on_another_device(client):
    h = nurse(client)
    cid = prepared(client, h)
    out = copied(client, h, cid)
    order = [i["ref_id"] for i in out["item_list"]]
    other_device = client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "CorrectHorse42"}
    ).json()
    from tests.conftest import auth_headers

    there = auth_headers(other_device)
    assert [
        i["ref_id"] for i in client.get(f"{COLLECTIONS}/{out['id']}", headers=there).json()["item_list"]
    ] == order
    assert [i["ref_id"] for i in view(client, h, cid)["items"]] == order  # the original's, too


def test_another_accounts_collection_cant_be_duplicated_and_nothing_is_said(client):
    a = nurse(client)
    c = collection(client, a, "Ward round", (QUESTION,))
    b = nurse(client, email="bea@example.com")
    r = duplicate(client, b, c["id"])
    assert r.status_code == 404 and r.json()["error"]["message"] == "Collection not found"
    gone = duplicate(client, b, "no-such-collection").json()["error"]
    assert (gone["code"], gone["message"]) == (r.json()["error"]["code"], r.json()["error"]["message"])
    assert client.get(COLLECTIONS, headers=b).json() == []
    # Bea's key never finds Ada's copy either.
    copied(client, a, c["id"], client_request_id=KEY)
    mine = collection(client, b, "Mine", (PROBLEM,))
    assert copied(client, b, mine["id"], client_request_id=KEY)["name"] == "Mine (copy)"


@pytestmark_pg
def test_on_postgresql_a_copy_reads_and_writes_only_this_accounts_rows(client):
    """Row-level security: a request scoped to one account can't read another's collections or the
    reviews its items hold, so nothing of them can be copied even if a query forgot its owner."""
    from sqlalchemy.orm import Session

    from app.db import rls
    from app.models import User

    a = nurse(client)
    cid = prepared(client, a)  # with a review on one item
    b = nurse(client, email="bea@example.com")
    with Session(client.app.state.engine) as db:
        rls.bind_user(db, db.scalar(select(User.id).where(User.email == "bea@example.com")))
        assert db.scalars(select(PracticeCollection.id)).all() == []
        assert db.scalars(select(SourceReview.id)).all() == []
    assert duplicate(client, b, cid).status_code == 404
    assert copied(client, a, cid)["item_list"]  # Ada's own copy works

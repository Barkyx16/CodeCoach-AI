"""Mark several saved items reviewed at once (Volume 15, prompt 6; docs/BULK_ACTIONS.md): on the
saved list and in a collection, each item gets its own outcome by the same rule as one at a time:
recorded once for the version shown, a newer version since still asks, a drill has no versions, an
item gone from the library has nothing to review, and an item that isn't yours is "not there".
Sending the same batch again records nothing twice. Nothing about the items themselves changes.
Synthetic data only."""

from __future__ import annotations

from sqlalchemy import select, update

from app.models import Bookmark, SourceReview
from tests.test_content_quality import admin, nurse
from tests.test_note_freshness import NURSE, QID, correct
from tests.test_saved_freshness import COLLECTIONS, PROBLEM, QUESTION, SAVED, collection, save, saved

DRILL = {"item_type": "drill", "track": "", "ref_id": "example"}
OTHER_Q = {"item_type": "question", "track": NURSE, "ref_id": "m-pressure-1"}


def key(item):
    return f"{item['item_type']}:{item['track'] if item['item_type'] == 'question' else ''}:{item['ref_id']}"


def review_saved(client, h, entries):
    r = client.post(f"{SAVED}/review/batch", headers=h, json={"items": entries})
    assert r.status_code == 200, r.text
    return r.json()


def review_in(client, h, cid, entries):
    return client.post(f"{COLLECTIONS}/{cid}/items/review/batch", headers=h, json={"items": entries})


def outcomes(body):
    return [(r["key"], r["outcome"]) for r in body["results"]]


def review_rows(client):
    with client.app.state.session_factory() as db:
        return db.scalars(select(SourceReview)).all()


def test_several_saved_items_are_marked_reviewed_each_with_its_own_outcome(client):
    h = nurse(client)
    for item in (QUESTION, PROBLEM, DRILL, OTHER_Q):
        save(client, h, item)
    before = {b["id"]: (b["created_at"], b["content_version"]) for b in client.get(SAVED, headers=h).json()}
    correct(client, admin(client))  # QID: version 2
    assert saved(client, h)["freshness"]["state"] == "needs_review"
    body = review_saved(
        client,
        h,
        [
            {**QUESTION, "reviewed_version": 2},
            {**QUESTION, "reviewed_version": 2},
            {**DRILL, "reviewed_version": 1},
            {**OTHER_Q, "reviewed_version": 1},
            {"item_type": "question", "track": NURSE, "ref_id": "e-time-0", "reviewed_version": 1},
        ],
    )
    assert outcomes(body) == [
        (key(QUESTION), "reviewed"),
        (key(QUESTION), "repeated"),
        (key(DRILL), "not_versioned"),
        (key(OTHER_Q), "already_reviewed"),
        (f"question:{NURSE}:e-time-0", "not_there"),
    ]
    assert body["results"][0]["message"] == "Marked reviewed at version 2."
    q = next(b for b in body["bookmarks"] if b["ref_id"] == QID)
    assert q["freshness"]["state"] == "current" and q["freshness"]["reviewed_version"] == 2
    # Nothing about the saved items changed.
    after = {b["id"]: (b["created_at"], b["content_version"]) for b in client.get(SAVED, headers=h).json()}
    assert after == before
    # The same batch again records nothing twice.
    again = review_saved(client, h, [{**QUESTION, "reviewed_version": 2}])
    assert outcomes(again) == [(key(QUESTION), "already_reviewed")]
    assert [r.to_revision for r in review_rows(client)] == [2]


def test_a_newer_version_since_still_asks_and_a_version_that_doesnt_exist_is_refused(client):
    h = nurse(client)
    save(client, h)
    root = admin(client)
    correct(client, root)
    correct(client, root, prompt="Describe a hard shift and how you kept every patient safe.")  # version 3
    body = review_saved(client, h, [{**QUESTION, "reviewed_version": 2}])
    [r] = body["results"]
    assert r["outcome"] == "newer_since"
    assert r["message"] == "Marked reviewed at version 2; it's version 3 now, so it still asks."
    bad = review_saved(client, h, [{**QUESTION, "reviewed_version": 9}])
    assert outcomes(bad) == [(key(QUESTION), "invalid_version")]
    assert bad["results"][0]["message"] == "Version 9 doesn't exist yet (it's version 3 now)."


def test_an_item_gone_from_the_library_has_nothing_to_review(client):
    h = nurse(client)
    b = save(client, h)
    with client.app.state.session_factory() as db:
        db.execute(update(Bookmark).where(Bookmark.id == b["id"]).values(ref_id="gone-0"))
        db.commit()
    gone = {**QUESTION, "ref_id": "gone-0"}
    body = review_saved(client, h, [{**gone, "reviewed_version": 1}])
    assert outcomes(body) == [(key(gone), "unavailable")]


def test_several_items_of_a_collection_are_marked_reviewed_each_with_its_own_outcome(client):
    h = nurse(client)
    c = collection(client, h, "Night shift prep", (QUESTION, DRILL, OTHER_Q))
    ids = {i["ref_id"]: i["id"] for i in c["item_list"]}
    correct(client, admin(client))
    r = review_in(
        client,
        h,
        c["id"],
        [
            {"item_id": ids[QID], "reviewed_version": 2},
            {"item_id": ids["example"], "reviewed_version": 1},
            {"item_id": ids["m-pressure-1"], "reviewed_version": 1},
            {"item_id": "not-an-item", "reviewed_version": 1},
            {"item_id": ids[QID], "reviewed_version": 2},
        ],
    )
    assert r.status_code == 200, r.text
    assert outcomes(r.json()) == [
        (ids[QID], "reviewed"),
        (ids["example"], "not_versioned"),
        (ids["m-pressure-1"], "already_reviewed"),
        ("not-an-item", "not_there"),
        (ids[QID], "repeated"),
    ]
    items = {i["ref_id"]: i for i in r.json()["collection"]["item_list"]}
    assert items[QID]["freshness"]["state"] == "current"
    assert [i["position"] for i in r.json()["collection"]["item_list"]] == [0, 1, 2]
    # The saved list's own review isn't touched: each holder keeps its own.
    assert all(row.holder_kind == "collection_item" for row in review_rows(client))


def test_another_accounts_collection_is_not_found_and_its_items_are_not_there(client):
    a = nurse(client)
    theirs = collection(client, a, "Theirs", (QUESTION,))
    their_item = theirs["item_list"][0]["id"]
    b = nurse(client, "bea@example.com")
    mine = collection(client, b, "Mine", (OTHER_Q,))
    assert (
        review_in(client, b, theirs["id"], [{"item_id": their_item, "reviewed_version": 1}]).status_code
        == 404
    )
    r = review_in(client, b, mine["id"], [{"item_id": their_item, "reviewed_version": 1}])
    assert outcomes(r.json()) == [(their_item, "not_there")]
    assert review_rows(client) == []
    # Another account's saved item, by its key, is simply not saved here.
    save(client, a)
    body = review_saved(client, b, [{**QUESTION, "reviewed_version": 1}])
    assert outcomes(body) == [(key(QUESTION), "not_there")]


def test_a_batch_holds_at_most_fifty(client):
    h = nurse(client)
    r = client.post(
        f"{SAVED}/review/batch", headers=h, json={"items": [{**QUESTION, "reviewed_version": 1}] * 51}
    )
    assert r.status_code == 422

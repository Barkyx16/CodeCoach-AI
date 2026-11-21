"""Collections come back from a backup file (Volume 15, prompt 6; docs/BACKUP_FORMAT.md): from a
version 2 export, each collection is restored under its own id with its items in order, each
item's id, the version it was added at, its mark of done and what was reviewed, and the practice
queue where it was. A collection already here is never overwritten (the same id: already here; the
same name: skipped and said); an item whose content left the library is left out with the reason,
a retired one is kept and shown unavailable. A file from another account brings its content in
under new ids and never touches the other account. Removing the restore takes back only the
collections still as restored, and names the ones changed since. Synthetic data only."""

from __future__ import annotations

import json

from tests.test_content_quality import admin, nurse
from tests.test_note_freshness import NURSE, QID, correct
from tests.test_restore import apply, preview
from tests.test_saved_freshness import COLLECTIONS, PROBLEM, QUESTION, collection, item_of, review_item

DRILL = {"item_type": "drill", "track": "", "ref_id": "example"}
OTHER_Q = {"item_type": "question", "track": NURSE, "ref_id": "m-pressure-1"}
STABLE = ("id", "item_type", "track", "ref_id", "position", "content_version", "queue_done", "freshness")


def v2(client, h) -> bytes:
    r = client.get("/api/v1/me/export", headers=h, params={"version": 2})
    assert r.status_code == 200, r.text
    return r.content


def view(client, h, cid):
    r = client.get(f"{COLLECTIONS}/{cid}", headers=h)
    assert r.status_code == 200, r.text
    c = r.json()
    return {
        "id": c["id"],
        "name": c["name"],
        "queue_position": c["queue_position"],
        "items": [{k: i[k] for k in STABLE} for i in c["item_list"]],
    }


def prepared(client, h, name="Night shift prep"):
    """A collection of four items, reordered, one marked done, one reviewed after a change, the queue
    moved on."""
    c = collection(client, h, name, (QUESTION, PROBLEM, DRILL, OTHER_Q))
    ids = [i["id"] for i in c["item_list"]]
    order = [ids[3], ids[0], ids[2], ids[1]]
    assert (
        client.put(f"{COLLECTIONS}/{c['id']}/order", headers=h, json={"item_ids": order}).status_code == 200
    )
    assert client.put(f"{COLLECTIONS}/{c['id']}/queue", headers=h, json={"position": 2}).status_code == 200
    done = client.put(f"{COLLECTIONS}/{c['id']}/items/{ids[2]}/done", headers=h, json={"done": True})
    assert done.status_code == 200, done.text
    correct(client, admin(client))  # the question changes: version 2
    assert review_item(client, h, c["id"], ids[0], 2).status_code == 200
    return c["id"]


def delete(client, h, cid):
    assert client.delete(f"{COLLECTIONS}/{cid}", headers=h).status_code in (200, 204)


def category(p, key="collections"):
    return next(c for c in p.json()["categories"] if c["key"] == key)


def test_export_delete_restore_brings_each_collection_back_as_it_was(client):
    h = nurse(client)
    cid = prepared(client, h)
    before = view(client, h, cid)
    assert [i["ref_id"] for i in before["items"]] == ["m-pressure-1", QID, "example", "two-sum"]
    raw = v2(client, h)
    delete(client, h, cid)

    p = preview(client, h, raw)
    assert p.status_code == 200, p.text
    cat = category(p)
    assert (cat["found"], cat["new"], cat["duplicates"], cat["samples"]) == (1, 1, 0, ["Night shift prep"])
    r = apply(client, h, raw, ["collections"])
    assert r.status_code in (200, 201), r.text
    assert r.json()["counts"]["collections"] == {"added": 1, "duplicates": 0, "skipped": 0}

    after = view(client, h, cid)
    assert after == before  # the same id, order, item ids, versions, done marks, reviews and queue
    reviewed = item_of(client, h, cid)["freshness"]
    assert reviewed["state"] == "current" and reviewed["reviewed_version"] == 2

    # The same file again adds nothing; a new export finds the same collection again.
    again = apply(client, h, raw, ["collections"])
    assert again.status_code == 200 and again.json()["id"] == r.json()["id"]
    assert category(preview(client, h, raw))["duplicates"] == 1


def test_the_order_comes_from_each_items_position_not_where_it_sits_in_the_file(client):
    h = nurse(client)
    cid = prepared(client, h)
    before = view(client, h, cid)
    doc = json.loads(v2(client, h))
    items = doc["collections"][0]["items"]
    doc["collections"][0]["items"] = [items[2], items[0], items[3], items[1]]  # shuffled; positions kept
    delete(client, h, cid)
    apply(client, h, json.dumps(doc).encode(), ["collections"])
    assert [i["ref_id"] for i in view(client, h, cid)["items"]] == [i["ref_id"] for i in before["items"]]


def test_a_collection_already_here_is_never_overwritten_and_a_name_clash_is_skipped_and_said(client):
    h = nurse(client)
    c = collection(client, h, "Week one", (QUESTION,))
    raw = v2(client, h)
    # Already here, by id: counted as already there; nothing about it changes.
    client.post(f"{COLLECTIONS}/{c['id']}/items", headers=h, json=PROBLEM)
    kept = view(client, h, c["id"])
    p = category(preview(client, h, raw))
    assert (p["new"], p["duplicates"]) == (0, 1)
    apply(client, h, raw, ["collections"])
    assert view(client, h, c["id"]) == kept
    # Another collection with the same name (and a different id): skipped with its reason.
    delete(client, h, c["id"])
    other = collection(client, h, "week  ONE", (DRILL,))
    p = category(preview(client, h, raw))
    assert p["new"] == 0 and p["skipped"] == [
        {
            "reason": "A collection with this name is already here (it's never overwritten or merged)",
            "count": 1,
        }
    ]
    apply(client, h, raw, ["collections"])
    assert [i["ref_id"] for i in view(client, h, other["id"])["items"]] == ["example"]
    names = [x["name"] for x in client.get(COLLECTIONS, headers=h).json()]
    assert names == ["week  ONE"] or names == ["week ONE"]


def test_items_whose_content_left_the_library_are_left_out_and_retired_ones_kept_unavailable(client):
    h = nurse(client)
    c = collection(client, h, "Mixed", (QUESTION, OTHER_Q, PROBLEM))
    doc = json.loads(v2(client, h))
    items = doc["collections"][0]["items"]
    items[1]["item"] = "gone-0"  # left the library
    items.append({**items[0], "id": None})  # the same item twice
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{QID}/retire",
        headers=admin(client),
        json={"reason": "Too vague."},
    )
    assert r.status_code == 200, r.text
    delete(client, h, c["id"])
    raw = json.dumps(doc).encode()
    skipped = {s["reason"]: s["count"] for s in category(preview(client, h, raw))["skipped"]}
    assert skipped == {
        "Items left out: the question isn't in the library (it's never swapped for a similar one)": 1,
        "Items left out: the same item twice in one collection": 1,
        "Items kept but shown as unavailable: retired from the library": 1,
    }
    apply(client, h, raw, ["collections"])
    got = client.get(f"{COLLECTIONS}/{c['id']}", headers=h).json()["item_list"]
    assert [(i["ref_id"], i["available"]) for i in got] == [(QID, False), ("two-sum", True)]
    assert got[0]["unavailable_reason"] == "Retired: Too vague."
    assert [i["position"] for i in got] == [0, 1]


def test_a_version_1_file_doesnt_restore_collections(client):
    h = nurse(client)
    c = collection(client, h, "Old file")
    raw = client.get("/api/v1/me/export", headers=h).content
    delete(client, h, c["id"])
    cat = category(preview(client, h, raw))
    assert cat["new"] == 0 and cat["skipped"] == [
        {"reason": "Restored from a version 2 export only (it keeps the ids and the order)", "count": 1}
    ]


def test_removing_the_restore_takes_back_only_unchanged_collections_and_names_the_others(client):
    h = nurse(client)
    a = collection(client, h, "Untouched", (QUESTION,))
    b = collection(client, h, "Changed since", (QUESTION, PROBLEM))
    raw = v2(client, h)
    delete(client, h, a["id"])
    delete(client, h, b["id"])
    batch = apply(client, h, raw, ["collections"]).json()
    ids = [i["id"] for i in view(client, h, b["id"])["items"]]
    client.put(f"{COLLECTIONS}/{b['id']}/order", headers=h, json={"item_ids": list(reversed(ids))})
    r = client.post(f"/api/v1/me/restore/batches/{batch['id']}/remove", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["removal"] == {
        "removed": 1,
        "kept_edited": 1,
        "already_gone": 0,
        "kept_collections": ["Changed since"],
    }
    assert client.get(f"{COLLECTIONS}/{a['id']}", headers=h).status_code == 404
    assert [i["ref_id"] for i in view(client, h, b["id"])["items"]] == ["two-sum", QID]


def test_a_file_from_another_account_brings_content_in_under_new_ids_and_never_touches_it(client):
    a = nurse(client)
    cid = prepared(client, a)
    theirs = view(client, a, cid)
    raw = v2(client, a)
    b = nurse(client, "bea@example.com")
    r = apply(client, b, raw, ["collections"])
    assert r.status_code in (200, 201), r.text
    [mine] = client.get(COLLECTIONS, headers=b).json()
    got = view(client, b, mine["id"])
    assert got["id"] != cid and {i["id"] for i in got["items"]}.isdisjoint({i["id"] for i in theirs["items"]})
    assert [i["ref_id"] for i in got["items"]] == [i["ref_id"] for i in theirs["items"]]
    assert [i["content_version"] for i in got["items"]] == [i["content_version"] for i in theirs["items"]]
    assert view(client, a, cid) == theirs  # the other account's collection is exactly as it was
    assert client.get(f"{COLLECTIONS}/{cid}", headers=b).status_code == 404
    # Removing it in this account leaves the other's alone.
    client.post(f"/api/v1/me/restore/batches/{r.json()['id']}/remove", headers=b)
    assert view(client, a, cid) == theirs
    # Even once the other account has deleted it, its ids are never taken into this one.
    delete(client, a, cid)
    c = nurse(client, "cy@example.com")
    assert apply(client, c, raw, ["collections"]).status_code in (200, 201)
    [restored] = client.get(COLLECTIONS, headers=c).json()
    assert restored["id"] != cid
    got = view(client, c, restored["id"])
    assert {i["id"] for i in got["items"]}.isdisjoint({i["id"] for i in theirs["items"]})


def test_a_file_naming_this_account_but_another_accounts_collection_id_gets_a_new_id(client):
    a = nurse(client)
    theirs = collection(client, a, "Theirs", (QUESTION,))
    b = nurse(client, "bea@example.com")
    mine = collection(client, b, "Mine", (PROBLEM,))
    doc = json.loads(v2(client, b))
    doc["collections"][0]["id"] = theirs["id"]
    doc["collections"][0]["name"] = "Renamed"
    r = apply(client, b, json.dumps(doc).encode(), ["collections"])
    assert r.status_code in (200, 201), r.text
    restored = next(c for c in client.get(COLLECTIONS, headers=b).json() if c["name"] == "Renamed")
    assert restored["id"] not in (theirs["id"], mine["id"])
    assert [i["ref_id"] for i in view(client, a, theirs["id"])["items"]] == [QID]

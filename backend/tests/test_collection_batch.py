"""Bulk collection membership (Volume 11, prompt 5; docs/BULK_ACTIONS.md): several adds or removals in
one request, each with its own outcome; already there, not in the library, full, not in this
collection and listed twice all said per item; another account's collection is not found and its
items are "not there"; sending the same batch again changes nothing twice; removing leaves the
question, bookmarks and answers alone; the request is bounded. Synthetic accounts only."""

from __future__ import annotations

from app.careers.questions import questions_for
from app.services import explore as ex

from .test_explore import ANSWER, NURSE, make, nurse, q

BATCH = "/api/v1/me/collections/{}/items/batch"


def batch(client, h, cid, **body):
    return client.post(BATCH.format(cid), headers=h, json=body)


def outcomes(r):
    assert r.status_code == 200, r.text
    return [(x["key"], x["outcome"]) for x in r.json()["results"]]


def key(item):
    return f"{item['item_type']}:{item.get('track', '')}:{item['ref_id']}"


def test_adds_several_with_an_honest_outcome_for_each(client):
    h = nurse(client)
    qs = questions_for(NURSE)
    c = make(client, h)
    client.post(f"/api/v1/me/collections/{c['id']}/items", headers=h, json=q(qs[0].id))  # already there
    items = [
        q(qs[0].id),
        q(qs[1].id),
        q("no-such-question"),
        q(qs[1].id),
        {"item_type": "problem", "ref_id": "two-sum"},
    ]
    r = batch(client, h, c["id"], add=items)
    assert outcomes(r) == [
        (key(items[0]), "already_there"),
        (key(items[1]), "added"),
        (key(items[2]), "unavailable"),
        (key(items[3]), "repeated"),
        ("problem::two-sum", "added"),
    ]
    body = r.json()
    assert [i["ref_id"] for i in body["collection"]["item_list"]] == [qs[0].id, qs[1].id, "two-sum"]
    assert [i["position"] for i in body["collection"]["item_list"]] == [0, 1, 2]
    # The same batch again (a lost reply, sent again): nothing changes twice.
    again = outcomes(batch(client, h, c["id"], add=items))
    assert [o for _, o in again] == [
        "already_there",
        "already_there",
        "unavailable",
        "repeated",
        "already_there",
    ]
    assert len(client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()["item_list"]) == 3


def test_a_full_collection_says_which_items_didnt_fit(client, monkeypatch):
    h = nurse(client)
    qs = questions_for(NURSE)
    c = make(client, h)
    monkeypatch.setattr(ex, "MAX_ITEMS", 2)
    r = batch(client, h, c["id"], add=[q(x.id) for x in qs[:4]])
    assert [o for _, o in outcomes(r)] == ["added", "added", "full", "full"]
    assert "holds up to 2 items" in r.json()["results"][2]["message"]


def test_removes_several_and_leaves_the_questions_bookmarks_and_answers_alone(client):
    h = nurse(client)
    qs = questions_for(NURSE)
    c = make(client, h)
    batch(client, h, c["id"], add=[q(x.id) for x in qs[:4]])
    client.put("/api/v1/me/bookmarks", headers=h, json=q(qs[1].id))
    answered = client.post(
        f"/api/v1/careers/{NURSE}/questions/{qs[1].id}/answers", headers=h, json={"answer": ANSWER}
    )
    assert answered.status_code == 201, answered.text
    items = client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()["item_list"]
    ids = [i["id"] for i in items]
    r = batch(client, h, c["id"], remove=[ids[1], ids[2], "no-such-item", ids[1]])
    assert outcomes(r) == [
        (ids[1], "removed"),
        (ids[2], "removed"),
        ("no-such-item", "not_there"),
        (ids[1], "repeated"),
    ]
    left = r.json()["collection"]["item_list"]
    assert [i["id"] for i in left] == [ids[0], ids[3]] and [i["position"] for i in left] == [0, 1]
    # Only the collection changed: the bookmark and the answer are still there.
    marks = client.get("/api/v1/me/bookmarks", headers=h).json()
    assert any(m["ref_id"] == qs[1].id for m in marks)
    history = client.get(f"/api/v1/careers/{NURSE}/questions/{qs[1].id}/answers", headers=h).json()
    assert len(history) == 1
    # Removing again after a lost reply: not there, nothing else touched.
    assert [o for _, o in outcomes(batch(client, h, c["id"], remove=[ids[1], ids[2]]))] == [
        "not_there",
        "not_there",
    ]


def test_another_accounts_collection_and_items_are_out_of_reach(client):
    ada = nurse(client)
    bea = nurse(client, "bea@example.com")
    qs = questions_for(NURSE)
    adas = make(client, ada, "Ada's")
    beas = make(client, bea, "Bea's")
    batch(client, ada, adas["id"], add=[q(qs[0].id)])
    ada_item = client.get(f"/api/v1/me/collections/{adas['id']}", headers=ada).json()["item_list"][0]["id"]
    # Bea can't touch Ada's collection at all...
    assert batch(client, bea, adas["id"], add=[q(qs[1].id)]).status_code == 404
    assert batch(client, bea, adas["id"], remove=[ada_item]).status_code == 404
    # ...and Ada's item id in Bea's own collection is just "not there", saying nothing about Ada's.
    r = batch(client, bea, beas["id"], remove=[ada_item])
    assert outcomes(r) == [(ada_item, "not_there")] and "Ada" not in r.text
    assert len(client.get(f"/api/v1/me/collections/{adas['id']}", headers=ada).json()["item_list"]) == 1
    assert client.post(BATCH.format(adas["id"]), json={"remove": [ada_item]}).status_code == 401


def test_the_request_is_bounded_and_does_one_thing(client):
    h = nurse(client)
    c = make(client, h)
    qs = questions_for(NURSE)
    assert batch(client, h, c["id"], add=[q(x.id) for x in qs[:51]]).status_code == 422  # at most 50
    assert batch(client, h, c["id"], remove=[str(i) for i in range(51)]).status_code == 422
    assert batch(client, h, c["id"]).status_code == 422  # neither
    assert batch(client, h, c["id"], add=[q(qs[0].id)], remove=["x"]).status_code == 422  # not both
    assert batch(client, h, c["id"], add=[q(x.id) for x in qs[:50]]).status_code == 200


def test_two_batches_adding_the_same_items_at_once_keep_one_copy_each(client):
    from concurrent.futures import ThreadPoolExecutor

    h = nurse(client)
    qs = questions_for(NURSE)
    c = make(client, h)
    items = [q(x.id) for x in qs[:3]]
    with ThreadPoolExecutor(4) as pool:
        replies = list(pool.map(lambda _: batch(client, h, c["id"], add=items), range(4)))
    assert all(r.status_code == 200 for r in replies), [r.text for r in replies]
    for i in range(3):  # each item added by exactly one request; the others say it was already there
        said = [r.json()["results"][i]["outcome"] for r in replies]
        assert said.count("added") == 1 and set(said) <= {"added", "already_there"}, said
    assert len(client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()["item_list"]) == 3

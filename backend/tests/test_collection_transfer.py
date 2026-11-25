"""Copy or move chosen items between collections (Volume 17, prompt 6; docs/BULK_ACTIONS.md, "Copy or
move items"): each item arrives at the version it was added at and with its "Mark reviewed" (moved
with it, or copied as the new item's own record), at the end of the other collection in this one's
order; its queue mark stays behind; a move takes an item out only once it's in the other collection;
an item already there is never doubled; the same request sent again changes nothing twice; the limit
is said per item; both collections must be yours; one transaction. Synthetic data only."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import CollectionItem
from app.services import explore
from tests.test_collection_copies import reviews_of
from tests.test_collection_restore import DRILL, OTHER_Q, prepared, view
from tests.test_content_quality import nurse
from tests.test_note_freshness import QID
from tests.test_saved_freshness import COLLECTIONS, PROBLEM, QUESTION, collection


def key(item: dict) -> str:
    track = item.get("track") or "" if item["item_type"] == "question" else ""
    return f"{item['item_type']}:{track}:{item['ref_id']}"


def transfer(client, h, cid, to, items, move=False):
    return client.post(
        f"{COLLECTIONS}/{cid}/items/transfer", headers=h, json={"to": to, "items": items, "move": move}
    )


def ref(i: dict) -> dict:
    return {"item_type": i["item_type"], "track": i["track"], "ref_id": i["ref_id"]}


def test_a_copy_keeps_each_items_version_and_review_and_leaves_the_source_as_it_was(client):
    h = nurse(client)
    cid = prepared(client, h)  # reordered; one marked done; the question reviewed at version 2
    before = view(client, h, cid)
    src = client.get(f"{COLLECTIONS}/{cid}", headers=h).json()
    dst = collection(client, h, "Week 2", ())
    chosen = [i for i in src["item_list"] if i["ref_id"] in (QID, DRILL["ref_id"])]
    r = transfer(client, h, cid, dst["id"], [ref(i) for i in reversed(chosen)])  # sent in the other order
    assert r.status_code == 200, r.text
    out = r.json()
    assert [x["outcome"] for x in out["results"]] == ["copied", "copied"]
    got = out["destination"]["item_list"]
    assert [i["ref_id"] for i in got] == [i["ref_id"] for i in chosen]  # the source's order
    for new, old in zip(got, chosen, strict=True):
        assert new["content_version"] == old["content_version"] and new["queue_done"] is False
    q_new = next(i for i in got if i["ref_id"] == QID)
    q_old = next(i for i in chosen if i["ref_id"] == QID)
    assert reviews_of(client, q_new["id"]) == reviews_of(client, q_old["id"]) == [(2, "reviewed")]
    assert view(client, h, cid) == before  # a copy changes nothing here


def test_a_move_takes_the_items_out_with_their_reviews_and_leaves_their_queue_marks_behind(client):
    h = nurse(client)
    cid = prepared(client, h)
    src = client.get(f"{COLLECTIONS}/{cid}", headers=h).json()
    done = next(i for i in src["item_list"] if i["queue_done"])
    q_old = next(i for i in src["item_list"] if i["ref_id"] == QID)
    dst = collection(client, h, "Week 2", (PROBLEM,))
    out = transfer(client, h, cid, dst["id"], [ref(q_old), ref(done)], move=True).json()
    assert [x["outcome"] for x in out["results"]] == ["moved", "moved"]
    left = [i["ref_id"] for i in out["source"]["item_list"]]
    assert QID not in left and done["ref_id"] not in left and len(left) == 2
    arrived = {i["ref_id"]: i for i in out["destination"]["item_list"]}
    assert (
        arrived[done["ref_id"]]["queue_done"] is False
    )  # the mark stayed with the collection it was made in
    assert reviews_of(client, arrived[QID]["id"]) == [(2, "reviewed")]
    assert reviews_of(client, q_old["id"]) == []  # moved with it, not left behind
    assert [i["position"] for i in out["source"]["item_list"]] == [0, 1]


def test_sent_again_after_a_lost_reply_nothing_changes_twice(client):
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", ())
    items = [ref(i) for i in c["item_list"]]
    first = transfer(client, h, c["id"], dst["id"], items, move=True).json()
    assert [x["outcome"] for x in first["results"]] == ["moved", "moved"]
    again = transfer(client, h, c["id"], dst["id"], items, move=True).json()
    assert [x["outcome"] for x in again["results"]] == ["already_there", "already_there"]
    assert len(again["destination"]["item_list"]) == 2 and again["source"]["item_list"] == []
    copy_again = transfer(client, h, dst["id"], c["id"], items).json()
    assert [x["outcome"] for x in copy_again["results"]] == ["copied", "copied"]
    twice = transfer(client, h, dst["id"], c["id"], items).json()
    assert [x["outcome"] for x in twice["results"]] == ["already_there", "already_there"]
    assert len(twice["destination"]["item_list"]) == 2  # never doubled


def test_an_item_already_there_isnt_doubled_and_a_move_just_takes_it_out_of_here(client):
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", (QUESTION,))
    out = transfer(client, h, c["id"], dst["id"], [ref(c["item_list"][0])], move=True).json()
    [res] = out["results"]
    assert res["outcome"] == "moved" and res["message"] == "Already in “Week 2”; taken out of “Week 1”."
    assert len(out["destination"]["item_list"]) == 1 and len(out["source"]["item_list"]) == 1


def test_repeated_items_missing_items_and_the_limit_each_have_their_own_outcome(client, monkeypatch):
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM, OTHER_Q))
    dst = collection(client, h, "Week 2", (DRILL,))
    monkeypatch.setattr(explore, "MAX_ITEMS", 2)
    a, b, d = (ref(i) for i in c["item_list"])
    missing = {"item_type": "question", "track": a["track"], "ref_id": "no-such-question"}
    out = transfer(client, h, c["id"], dst["id"], [a, a, missing, b, d]).json()
    by = [(x["key"], x["outcome"]) for x in out["results"]]
    assert by == [
        (key(a), "copied"),
        (key(a), "repeated"),
        (key(missing), "not_there"),
        (key(b), "full"),
        (key(d), "full"),
    ]
    assert (
        next(x for x in out["results"] if x["outcome"] == "full")["message"]
        == "“Week 2” holds up to 2 items."
    )


def test_both_collections_must_be_yours_and_different(client):
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION,))
    other = nurse(client, email="other@example.com")
    theirs = collection(client, other, "Theirs", ())
    item = [ref(c["item_list"][0])]
    assert transfer(client, h, c["id"], theirs["id"], item).status_code == 404
    assert transfer(client, other, c["id"], theirs["id"], item).status_code == 404
    same = transfer(client, h, c["id"], c["id"], item)
    assert same.status_code == 409 and same.json()["error"]["code"] == "same_collection"
    assert view(client, h, c["id"])["items"][0]["ref_id"] == item[0]["ref_id"]


def test_a_failure_part_way_changes_nothing(client, monkeypatch):
    """The question is already in the other collection, so the move takes it out of here (the step that
    fails, after the problem was already added there): neither collection changes."""
    import pytest

    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", (QUESTION,))
    before = (view(client, h, c["id"]), view(client, h, dst["id"]))

    def boom(*a, **k):
        raise RuntimeError("synthetic failure after an item was added there")

    monkeypatch.setattr(explore, "forget", boom)
    with pytest.raises(RuntimeError):
        transfer(client, h, c["id"], dst["id"], [ref(i) for i in c["item_list"]], move=True)
    assert (view(client, h, c["id"]), view(client, h, dst["id"])) == before
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CollectionItem)) == 3


def test_another_tab_sending_the_same_move_at_once_changes_nothing_twice(client, monkeypatch):
    """Another tab's identical move commits first, while this one is under way: this pass meets the
    unique item constraint (simulated: it's raised where the clash would be), changes nothing, and is
    worked out once more against what's now there."""
    from sqlalchemy.exc import IntegrityError

    from app.db import rls
    from app.models import User

    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", ())
    items = [ref(i) for i in c["item_list"]]
    real = explore.Explorer._transfer_once
    calls = []

    def racing(self, user, cid, body):
        calls.append(cid)
        if len(calls) == 1:
            with client.app.state.session_factory() as other:
                rls.bind_user(other, user.id)
                them = other.get(User, user.id)
                real(explore.Explorer(other), them, cid, body)  # the other tab's request, committed
            raise IntegrityError("INSERT", {}, Exception("uq_collection_item"))
        return real(self, user, cid, body)

    monkeypatch.setattr(explore.Explorer, "_transfer_once", racing)
    out = transfer(client, h, c["id"], dst["id"], items, move=True)
    assert out.status_code == 200, out.text
    assert len(calls) == 2
    assert [x["outcome"] for x in out.json()["results"]] == ["already_there", "already_there"]
    assert len(view(client, h, dst["id"])["items"]) == 2 and view(client, h, c["id"])["items"] == []


def test_a_move_takes_out_only_what_arrived(client, monkeypatch):
    """Past the other collection's limit an item stays here, with its review and its place."""
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM, OTHER_Q))
    dst = collection(client, h, "Week 2", (DRILL,))
    monkeypatch.setattr(explore, "MAX_ITEMS", 2)
    out = transfer(client, h, c["id"], dst["id"], [ref(i) for i in c["item_list"]], move=True).json()
    assert [x["outcome"] for x in out["results"]] == ["moved", "full", "full"]
    left = [i["ref_id"] for i in out["source"]["item_list"]]
    assert left == [i["ref_id"] for i in c["item_list"][1:]]  # the two that didn't fit, in their order
    assert [i["ref_id"] for i in out["destination"]["item_list"]] == [DRILL["ref_id"], QID]

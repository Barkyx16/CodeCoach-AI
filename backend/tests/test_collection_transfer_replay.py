"""A keyed copy or move sent again repeats its first reply (Volume 18, prompt 5; docs/BULK_ACTIONS.md,
"Copy or move items"). With a request key, the first reply's outcomes are kept with what it did, in the
same transaction; the same request sent again after a lost reply gets them back exactly ("Moved", not
"Already there"), marked as a replay, with both collections as they are now, and nothing is done twice.
Without a key it reads as before. The same key for another request is refused; another account's key
is its own. Two copies of one keyed request at once: the second gets the first's reply. Synthetic data
only."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import CollectionItem, LifecycleReceipt
from app.services import explore
from tests.test_collection_transfer import ref
from tests.test_content_quality import nurse
from tests.test_saved_freshness import COLLECTIONS, PROBLEM, QUESTION, collection

KEY = "transfer-key-0001"


def transfer(client, h, cid, to, items, move=False, key=KEY):
    body = {"to": to, "items": items, "move": move}
    if key:
        body["client_request_id"] = key
    return client.post(f"{COLLECTIONS}/{cid}/items/transfer", headers=h, json=body)


def items_in(client, cid) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(CollectionItem).where(CollectionItem.collection_id == cid)
        )


def two(client, h):
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", ())
    return c, dst, [ref(i) for i in c["item_list"]]


def test_a_keyed_move_sent_again_repeats_its_first_reply(client):
    h = nurse(client)
    c, dst, items = two(client, h)
    first = transfer(client, h, c["id"], dst["id"], items, move=True)
    assert first.status_code == 200, first.text
    assert [x["outcome"] for x in first.json()["results"]] == ["moved", "moved"]
    assert first.json()["replayed"] is False
    again = transfer(client, h, c["id"], dst["id"], items, move=True)
    assert again.status_code == 200, again.text
    out = again.json()
    assert out["replayed"] is True
    assert out["results"] == first.json()["results"]  # word for word: "Moved", not "Already there"
    assert out["source"]["item_list"] == [] and len(out["destination"]["item_list"]) == 2
    assert items_in(client, dst["id"]) == 2 and items_in(client, c["id"]) == 0


def test_without_a_key_a_resend_reads_as_before(client):
    h = nurse(client)
    c, dst, items = two(client, h)
    transfer(client, h, c["id"], dst["id"], items, move=True, key=None)
    again = transfer(client, h, c["id"], dst["id"], items, move=True, key=None).json()
    assert [x["outcome"] for x in again["results"]] == ["already_there", "already_there"]
    assert again["replayed"] is False


def test_the_same_key_for_another_request_is_refused_and_does_nothing(client):
    h = nurse(client)
    c, dst, items = two(client, h)
    transfer(client, h, c["id"], dst["id"], items[:1])
    other = transfer(client, h, c["id"], dst["id"], items)  # other items, the same key
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_key_reused"
    assert items_in(client, dst["id"]) == 1
    copy_not_move = transfer(client, h, c["id"], dst["id"], items[:1], move=True)
    assert copy_not_move.status_code == 409


def test_another_accounts_key_is_its_own(client):
    theirs = nurse(client, "bea@example.com")
    tc, tdst, titems = two(client, theirs)
    transfer(client, theirs, tc["id"], tdst["id"], titems)
    h = nurse(client)
    c, dst, items = two(client, h)
    out = transfer(client, h, c["id"], dst["id"], items).json()
    assert out["replayed"] is False and [x["outcome"] for x in out["results"]] == ["copied", "copied"]
    # And a collection that isn't yours is not found, whatever the key.
    assert transfer(client, h, tc["id"], dst["id"], items).status_code == 404


def test_two_copies_at_once_the_second_gets_the_first_reply(client, monkeypatch):
    """The second copy looked for the key before the first had committed (found nothing), then met
    the first's receipt on commit: it's given the first's reply, and nothing is done twice."""
    h = nurse(client)
    c, dst, items = two(client, h)
    first = transfer(client, h, c["id"], dst["id"], items, move=True).json()
    real = explore.Explorer._transfer_replay
    looked = {"n": 0}

    def not_yet(self, user, cid, body):
        looked["n"] += 1
        return None if looked["n"] == 1 else real(self, user, cid, body)

    monkeypatch.setattr(explore.Explorer, "_transfer_replay", not_yet)
    again = transfer(client, h, c["id"], dst["id"], items, move=True)
    assert again.status_code == 200, again.text
    assert again.json()["replayed"] is True and again.json()["results"] == first["results"]
    assert looked["n"] == 2
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(LifecycleReceipt)) == 1

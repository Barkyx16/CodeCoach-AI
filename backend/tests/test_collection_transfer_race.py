"""Two tabs copying or moving the same items at once, in two real PostgreSQL transactions (Volume 18,
prompt 6; docs/BULK_ACTIONS.md, "Copy or move items"). Each request has read the other collection
and found the items missing before either inserts them (a flush hook holds both until then); then
both insert, the second waits on the unique (collection, item) until the first commits, and its
insert is refused. That request is worked out once more against what's now there: nothing is
doubled, nothing is lost, and both get a reply, one with "Copied" or "Moved" and one with "Already
there". Before Volume 18 this was checked by raising the constraint where it would be. PostgreSQL
only: SQLite serialises writers, so there is no race to show. Synthetic data only."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import CollectionItem
from app.services import explore
from tests.test_collection_transfer import ref
from tests.test_content_quality import nurse
from tests.test_saved_freshness import COLLECTIONS, PROBLEM, QUESTION, collection


@pytest.fixture
def passes(monkeypatch):
    """How many times a transfer is worked out: three when the two really overlap (the one that met
    the other's insert is worked out once more), two when one simply ran after the other."""
    count = {"n": 0}
    real = explore.Explorer._transfer_once

    def counted(self, *args, **kwargs):
        with threading.Lock():
            count["n"] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(explore.Explorer, "_transfer_once", counted)
    return count


@pytest.fixture
def held_inserts(client):
    """Hold the first two flushes that add collection items until both have arrived: both requests
    have then read the other collection, and neither has inserted yet."""
    with client.app.state.session_factory() as probe:
        if probe.get_bind().dialect.name != "postgresql":
            pytest.skip("needs PostgreSQL: SQLite serialises writers, so the two can't race")
    both = threading.Barrier(2, timeout=20)
    held = {"n": 0, "armed": False}  # armed only for the two racing requests, not the set-up
    lock = threading.Lock()

    def hold(session, _ctx, _instances):
        if not held["armed"] or session.info.get("held"):
            return
        if not any(isinstance(o, CollectionItem) for o in session.new):
            return
        with lock:
            if held["n"] >= 2:
                return
            held["n"] += 1
        session.info["held"] = True
        both.wait()

    event.listen(Session, "before_flush", hold)
    yield held
    event.remove(Session, "before_flush", hold)


def items_in(client, cid) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(CollectionItem).where(CollectionItem.collection_id == cid)
        )


def at_once(client, h, cid, to, items, move):
    out: list = []

    def send(key):
        body = {"to": to, "items": items, "move": move, "client_request_id": key}
        out.append(client.post(f"{COLLECTIONS}/{cid}/items/transfer", headers=h, json=body))

    threads = [threading.Thread(target=send, args=(f"tab-{n}-race-key",)) for n in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return out


def test_two_tabs_copying_the_same_items_at_once_copy_them_once(client, held_inserts, passes):
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", ())
    items = [ref(i) for i in c["item_list"]]
    held_inserts["armed"] = True
    replies = at_once(client, h, c["id"], dst["id"], items, move=False)
    assert held_inserts["n"] == 2 and passes["n"] == 3  # they overlapped: one met the other's insert
    assert [r.status_code for r in replies] == [200, 200], [r.text for r in replies]
    outcomes = sorted(tuple(x["outcome"] for x in r.json()["results"]) for r in replies)
    assert outcomes == [("already_there", "already_there"), ("copied", "copied")]
    assert items_in(client, dst["id"]) == 2 and items_in(client, c["id"]) == 2


def test_two_tabs_moving_the_same_items_at_once_move_them_once(client, held_inserts, passes):
    h = nurse(client)
    c = collection(client, h, "Week 1", (QUESTION, PROBLEM))
    dst = collection(client, h, "Week 2", ())
    items = [ref(i) for i in c["item_list"]]
    held_inserts["armed"] = True
    replies = at_once(client, h, c["id"], dst["id"], items, move=True)
    assert held_inserts["n"] == 2 and passes["n"] == 3
    assert [r.status_code for r in replies] == [200, 200], [r.text for r in replies]
    outcomes = sorted(tuple(x["outcome"] for x in r.json()["results"]) for r in replies)
    # One of them moved them; the other found them there (or gone from here), and took nothing twice.
    assert outcomes[1] == ("moved", "moved"), outcomes
    assert set(outcomes[0]) <= {"already_there", "not_there"}, outcomes
    assert items_in(client, dst["id"]) == 2 and items_in(client, c["id"]) == 0

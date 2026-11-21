"""A copy or move's key, asked about after a reload (Volume 19, prompt 1; docs/BULK_ACTIONS.md, "Copy
or move items"). The page keeps the key on the device before sending; after a reload it asks
GET /me/requests/{key} what that key made, a read that never sends anything again. A keyed transfer
answers with what its first reply said each item did, and where they went. Another account's key, or
a key nothing was made with, is 404. A receipt from before the destination was kept still answers,
without it. Synthetic data only."""

from __future__ import annotations

from sqlalchemy import update

from app.models import LifecycleReceipt
from tests.test_collection_transfer_replay import KEY, transfer, two
from tests.test_content_quality import nurse

OUTCOME = "/api/v1/me/requests"


def test_a_keyed_move_answers_with_its_first_reply_and_where_it_went(client):
    h = nurse(client)
    c, dst, items = two(client, h)
    first = transfer(client, h, c["id"], dst["id"], items, move=True).json()
    r = client.get(f"{OUTCOME}/{KEY}", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["kind"], out["state"], out["id"]) == ("transfer", "done", c["id"])
    made = out["transfer"]
    assert (made["source_id"], made["destination_id"], made["move"]) == (c["id"], dst["id"], True)
    assert made["results"] == first["results"]  # word for word: "Moved"
    # Asking changes nothing: still moved once.
    assert client.get(f"{OUTCOME}/{KEY}", headers=h).json() == out


def test_a_copy_says_it_was_a_copy(client):
    h = nurse(client)
    c, dst, items = two(client, h)
    transfer(client, h, c["id"], dst["id"], items, move=False)
    made = client.get(f"{OUTCOME}/{KEY}", headers=h).json()["transfer"]
    assert made["move"] is False and [x["outcome"] for x in made["results"]] == ["copied", "copied"]


def test_another_accounts_key_or_an_unused_one_is_not_found(client):
    theirs = nurse(client, "bea@example.com")
    tc, tdst, titems = two(client, theirs)
    transfer(client, theirs, tc["id"], tdst["id"], titems)
    h = nurse(client)
    r = client.get(f"{OUTCOME}/{KEY}", headers=h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "request_not_found"
    assert client.get(f"{OUTCOME}/never-used-key-01", headers=h).status_code == 404


def test_a_receipt_from_before_still_answers_without_where_it_went(client):
    h = nurse(client)
    c, dst, items = two(client, h)
    first = transfer(client, h, c["id"], dst["id"], items, move=True).json()
    with client.app.state.session_factory() as db:  # as kept before Volume 19
        row = db.query(LifecycleReceipt).one()
        db.execute(
            update(LifecycleReceipt)
            .where(LifecycleReceipt.id == row.id)
            .values(impact={"fingerprint": row.impact["fingerprint"], "results": row.impact["results"]})
        )
        db.commit()
    made = client.get(f"{OUTCOME}/{KEY}", headers=h).json()["transfer"]
    assert (made["destination_id"], made["move"]) == (None, None)
    assert made["results"] == first["results"]

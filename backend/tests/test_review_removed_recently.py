"""Questions removed from the review queue, listed to put back after a reload (Volume 19, prompt 2;
docs/DISPUTES.md, "Removed recently"). A removal now records when; GET /me/reviews/removed lists the
last 30 days', newest first, then removals from before their time was kept, at most 20; one saved
again since isn't listed; putting one back is the existing restore, as it was; another account's are
never listed; the export carries the time; the list is one statement however many there are.
Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.models import ReviewItem
from tests.test_disputes_everywhere import QUEUE, nurse
from tests.test_review_point_removal import restore
from tests.test_review_points import save_raw
from tests.test_review_recount import exported

REMOVED = f"{QUEUE}/removed"
QUESTIONS = ["e-good-0", "e-steps-0", "e-time-0", "e-good-7", "e-steps-7", "m-walk-0"]


def save(client, h, qid):
    out = save_raw(client, h, qid)
    return next(i for i in out["due"] + out["upcoming"] if i["question_id"] == qid)


def removed(client, h):
    r = client.get(REMOVED, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def stamp(client, item_id, at):
    with client.app.state.session_factory() as db:
        db.execute(update(ReviewItem).where(ReviewItem.id == item_id).values(removed_at=at))
        db.commit()


def test_a_removal_is_listed_with_when_and_put_back_as_it_was(client):
    h = nurse(client)
    item = save(client, h, QUESTIONS[0])
    assert client.delete(f"{QUEUE}/{item['id']}", headers=h).status_code == 200
    [row] = removed(client, h)
    assert (row["id"], row["question_id"], row["track"]) == (item["id"], QUESTIONS[0], "registered-nurse")
    assert row["removed_at"] and row["title"] == item["title"] and row["points"] == item["points"]
    assert row["href"] == f"/careers/registered-nurse/questions/{QUESTIONS[0]}"
    back = restore(client, h, item["id"])
    assert back.status_code == 200, back.text
    [again] = [i for i in back.json()["due"] + back.json()["upcoming"] if i["id"] == item["id"]]
    assert again == item  # as it was
    assert removed(client, h) == []  # back in the queue: no longer listed


def test_newest_first_then_undated_and_old_ones_left_out(client):
    h = nurse(client)
    items = [save(client, h, q) for q in QUESTIONS[:4]]
    for i in items:
        client.delete(f"{QUEUE}/{i['id']}", headers=h)
    now = datetime.now(UTC)
    stamp(client, items[0]["id"], now - timedelta(days=2))
    stamp(client, items[1]["id"], now - timedelta(hours=1))
    stamp(client, items[2]["id"], None)  # removed before the time was kept
    stamp(client, items[3]["id"], now - timedelta(days=31))  # too long ago
    rows = removed(client, h)
    assert [r["id"] for r in rows] == [items[1]["id"], items[0]["id"], items[2]["id"]]
    assert rows[2]["removed_at"] is None


def test_one_saved_again_is_not_listed(client):
    h = nurse(client)
    item = save(client, h, QUESTIONS[0])
    client.delete(f"{QUEUE}/{item['id']}", headers=h)
    save_raw(client, h, QUESTIONS[0])  # saved again: a new item in the queue
    assert removed(client, h) == []


def test_at_most_twenty(client, monkeypatch):
    from app.services import review_queue

    monkeypatch.setattr(review_queue, "REMOVED_LIMIT", 3)
    h = nurse(client)
    for q in QUESTIONS[:5]:
        client.delete(f"{QUEUE}/{save(client, h, q)['id']}", headers=h)
    assert len(removed(client, h)) == 3
    assert review_queue.REMOVED_DAYS == 30


def test_another_accounts_removals_are_never_listed(client):
    theirs = nurse(client, "bea@example.com")
    item = save(client, theirs, QUESTIONS[0])
    client.delete(f"{QUEUE}/{item['id']}", headers=theirs)
    h = nurse(client)
    assert removed(client, h) == []
    assert restore(client, h, item["id"]).status_code == 404
    assert client.get(REMOVED).status_code == 401


def test_the_export_carries_when_it_was_removed(client):
    h = nurse(client)
    item = save(client, h, QUESTIONS[0])
    assert exported(client, h)["removed_at"] is None
    client.delete(f"{QUEUE}/{item['id']}", headers=h)
    row = exported(client, h)
    assert row["removed"] is True and row["removed_at"]
    restore(client, h, item["id"])
    assert exported(client, h)["removed_at"] is None


def test_the_list_is_one_statement_however_many_there_are(client):
    from tests.test_query_budgets import statements

    h = nurse(client)
    client.delete(f"{QUEUE}/{save(client, h, QUESTIONS[0])['id']}", headers=h)
    with statements(client) as seen:
        removed(client, h)
    few = len(seen)
    for q in QUESTIONS[1:5]:
        client.delete(f"{QUEUE}/{save(client, h, q)['id']}", headers=h)
    with statements(client) as seen:
        assert len(removed(client, h)) == 5
    assert len(seen) == few, (few, len(seen))

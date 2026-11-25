"""Which point, by name (Volume 17, prompt 8; docs/DISPUTES.md, "Saved for several points"): with
several points saved and one disputed, the recount names the disputed point and the ones the item
stays for; with one point it reads as before, word for word; points disputed in turn are named in the
order they were disputed. One point can be removed, keeping the item, its ladder and its other points;
the last one can't be (removing it is removing the question, and that can be undone, ladder and all).
A removed point is kept in the item's history with its date, no longer holds a date back, and the
queue says why its disputed score counts again. The export carries both. Removing a point never
touches an answer, a score or a dispute. Synthetic data only."""

from __future__ import annotations

from app.models import AnswerFlag
from tests.test_disputes import flag
from tests.test_disputes_everywhere import QUEUE, nurse, review
from tests.test_review_points import remove_point, save_raw, two_points
from tests.test_review_recount import exported, only, queue, stored_answers


def restore(client, h, item_id):
    return client.post(f"{QUEUE}/{item_id}/restore", headers=h)


def test_two_points_one_disputed_names_it_and_the_point_it_stays_for(client):
    h = nurse(client)
    _item, _qid, label, second, _a1, a2, _ = two_points(client, h)
    flag(client, h, a2["id"], second)
    shown = only(queue(client, h))
    assert shown["recounted"] == (
        f"Recounted: one earlier score was disputed (on “{second}”, one of the points it's saved for; it "
        f"stays for “{label}”), so it's due in 3 days, not 7."
    )


def test_with_one_point_the_sentence_is_unchanged_word_for_word(client):
    h = nurse(client)
    _item, _qid, label, second, _a1, a2, _ = two_points(client, h)
    flag(client, h, a2["id"], second)
    item = only(queue(client, h))
    assert (
        remove_point(client, h, item["id"], label).status_code == 200
    )  # now saved for the disputed point only
    assert only(queue(client, h))["recounted"] == (
        f"Recounted: one earlier score was disputed (on “{second}”, the point it was saved for), so it's due "
        "in 3 days, not 7."
    )


def test_two_points_disputed_in_turn_are_each_named_in_order(client):
    h = nurse(client)
    _item, _qid, label, second, a1, a2, _ = two_points(client, h)
    flag(client, h, a2["id"], second)  # disputed first
    flag(client, h, a1["id"], label)  # then this one
    shown = only(queue(client, h))
    assert shown["recounted"].startswith(
        f"Recounted: two earlier scores were disputed (on “{second}” and “{label}”, every point it's saved for)"
    )


def test_removing_one_point_keeps_the_ladder_and_the_other_points(client):
    h = nurse(client)
    item, _qid, label, second, *_ = two_points(client, h)
    before = only(queue(client, h))
    r = remove_point(client, h, item["id"], second)
    assert r.status_code == 200, r.text
    after = only(r.json())
    for key in ("id", "due_at", "interval_days", "reviews", "last_score", "snoozed"):
        assert after[key] == before[key], key
    assert after["points"] == [label]
    [gone] = after["removed_points"]
    assert gone["point"] == second and gone["removed_at"]


def test_the_last_point_is_the_question_and_undo_puts_it_back_as_it_was(client):
    h = nurse(client)
    item, _qid, label, second, *_ = two_points(client, h)
    remove_point(client, h, item["id"], second)
    before = only(queue(client, h))
    last = remove_point(client, h, item["id"], label)
    assert last.status_code == 409 and last.json()["error"]["code"] == "last_point"
    assert client.delete(f"{QUEUE}/{item['id']}", headers=h).status_code == 200
    q = queue(client, h)
    assert q["due"] == [] and q["upcoming"] == []
    back = restore(client, h, item["id"])
    assert back.status_code == 200, back.text
    assert only(back.json()) == before  # its ladder, its point and its history, as they were


def test_a_removed_point_no_longer_holds_a_date_and_the_queue_says_why(client):
    h = nurse(client)
    item, _qid, label, second, _a1, a2, _ = two_points(client, h)
    before = stored_answers(client)
    f = flag(client, h, a2["id"], second)
    assert only(queue(client, h))["interval_days"] == 3
    shown = only(remove_point(client, h, item["id"], second).json())
    assert shown["interval_days"] == 7 and shown["recounted"] is None
    assert shown["released"].startswith(f"“{second}” was taken off on ")
    assert shown["released"].endswith(", so one disputed score on it counts again.")
    # The answer, its score and its dispute are as they were.
    assert stored_answers(client) == before
    with client.app.state.session_factory() as db:
        assert db.get(AnswerFlag, f["id"]).reinstated_at is None


def test_saved_again_the_point_holds_again_and_its_history_stays(client):
    h = nurse(client)
    item, qid, label, second, _a1, a2, _ = two_points(client, h)
    flag(client, h, a2["id"], second)
    remove_point(client, h, item["id"], second)
    again = only(save_raw(client, h, qid, criterion=second))
    assert again["points"] == [label, second] and again["interval_days"] == 3
    assert again["released"] is None and [p["point"] for p in again["removed_points"]] == [second]


def test_undo_is_refused_when_the_question_is_back_and_for_another_account(client):
    h = nurse(client)
    item, qid, label, second, *_ = two_points(client, h)
    client.delete(f"{QUEUE}/{item['id']}", headers=h)
    save_raw(client, h, qid, criterion=label)  # saved again: a new item
    r = restore(client, h, item["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_in_queue"
    other = nurse(client, "bea@example.com")
    assert restore(client, other, item["id"]).status_code == 404
    assert remove_point(client, other, only(queue(client, h))["id"], label).status_code == 404


def test_the_export_carries_the_points_now_and_the_ones_removed(client):
    h = nurse(client)
    item, _qid, label, second, *_ = two_points(client, h)
    remove_point(client, h, item["id"], second)
    row = exported(client, h)
    assert row["saved_for_points"] == [label]
    [gone] = row["points_removed"]
    assert gone["point"] == second and gone["removed_at"]


def test_the_interview_summary_names_the_item_and_its_points(client):
    h = nurse(client)
    item, qid, label, second, *_ = two_points(client, h)
    r = review(client, h, iv_session(client, item["id"]))
    entry = next(i for i in r["items"] if i.get("question_id") == qid)
    assert entry["in_review_queue"] is True
    assert entry["review_item_id"] == item["id"] and entry["review_points"] == [label, second]


def iv_session(client, item_id):
    from app.models import ReviewItem

    with client.app.state.session_factory() as db:
        return db.get(ReviewItem, item_id).session_id

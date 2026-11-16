"""One question saved for review for more than one point (Volume 16, prompt 5; docs/DISPUTES.md, "The
review queue"): saving it again for another point adds that point and says so, saving it for the whole
answer makes it a whole-answer item; a dispute on any of its points leaves that answer's score out of
the recount, and the sentence names each disputed point; one point can be removed, bringing its
scores back in, without removing the item; an item from before this reads as it did; the export lists
every point. Answers, scores and feedback never change. Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import AnswerFlag, ReviewItem
from tests.test_disputes import flag
from tests.test_disputes_everywhere import QUEUE, TRACK, a_round, nurse, reinstate
from tests.test_review import STRONG
from tests.test_review_recount import (
    QID,
    backdate,
    exported,
    many_answers,
    old_way,
    only,
    queue,
    save,
    scored,
    statements,
    stored_answers,
    user_id,
)
from tests.test_roadmap import answer
from tests.test_row_level_security import pytestmark_pg


def save_raw(client, h, qid, **body):
    r = client.post(QUEUE, headers=h, json={"track": TRACK, "question_id": qid, **body})
    assert r.status_code in (200, 201), r.text
    return r.json()


def remove_point(client, h, item_id, point):
    return client.delete(f"{QUEUE}/{item_id}/points", headers=h, params={"point": point})


def two_points(client, h):
    """A question with two strong answers after it was saved, saved for two of the answer's points."""
    iv, r, label, missing = a_round(client, h)
    qid = missing[0]["question_id"]
    item = save(client, h, qid, session_id=iv, criterion=label)
    a1, a2 = answer(client, h, TRACK, qid, STRONG), answer(client, h, TRACK, qid, STRONG)
    a1, a2 = scored(client, a1, 90), scored(client, a2, 90)
    old_way(client, item["id"], [a1, a2])
    second = next(p["label"] for p in a2["points"] if p["label"] not in (label, "Overall"))
    out = save_raw(client, h, qid, session_id=iv, criterion=second)
    return item, qid, label, second, a1, a2, out


def test_saving_again_for_another_point_adds_it_and_says_so(client):
    h = nurse(client)
    item, qid, label, second, _a1, _a2, out = two_points(client, h)
    assert out["saved"] == f"Added “{second}” to the points it's saved for."
    shown = only(out)
    assert shown["id"] == item["id"] and shown["points"] == [label, second] and shown["criterion"] == label
    # The same point again changes nothing and says nothing.
    again = save_raw(client, h, qid, criterion=second)
    assert again["saved"] is None and only(again)["points"] == [label, second]


def test_a_dispute_on_the_second_point_leaves_that_score_out_and_names_it(client):
    h = nurse(client)
    item, _qid, label, second, a1, a2, _ = two_points(client, h)
    before = stored_answers(client)
    assert only(queue(client, h))["interval_days"] == 7
    f = flag(client, h, a2["id"], second)
    shown = only(queue(client, h))
    assert shown["interval_days"] == 3 and shown["reviews"] == 1
    assert shown["recounted"] == (
        f"Recounted: one earlier score was disputed (on “{second}”, the point it was saved for), so it's due in "
        "3 days, not 7."
    )
    # Both points disputed, on two answers: each is named.
    flag(client, h, a1["id"], label)
    both = only(queue(client, h))
    assert both["recounted"].startswith(
        f"Recounted: two earlier scores were disputed, on {' and '.join(f'“{p}”' for p in sorted([label, second]))}"
    )
    assert stored_answers(client) == before  # no answer, score or feedback changed
    reinstate(client, h, a2["id"], f["id"])


def test_removing_a_point_brings_its_score_back_in_and_keeps_the_item(client):
    h = nurse(client)
    item, _qid, label, second, _a1, a2, _ = two_points(client, h)
    flag(client, h, a2["id"], second)
    assert only(queue(client, h))["interval_days"] == 3
    r = remove_point(client, h, item["id"], second)
    assert r.status_code == 200, r.text
    shown = only(r.json())
    assert shown["id"] == item["id"] and shown["points"] == [label]
    assert shown["interval_days"] == 7 and shown["recounted"] is None
    # The last point can't be taken off: the item would change meaning; remove the question instead.
    last = remove_point(client, h, item["id"], label)
    assert last.status_code == 409 and last.json()["error"]["code"] == "last_point"
    assert remove_point(client, h, item["id"], "Not a point it has").status_code == 404


def test_saving_for_the_whole_answer_makes_it_a_whole_answer_item(client):
    h = nurse(client)
    item, qid, label, second, _a1, a2, _ = two_points(client, h)
    out = save_raw(client, h, qid)
    assert out["saved"] == f"It's now saved for the whole answer, not only for “{label}” and “{second}”."
    shown = only(out)
    assert shown["points"] == [] and shown["criterion"] is None
    flag(client, h, a2["id"], second)  # a dispute of one point doesn't hold a whole-answer item
    assert only(queue(client, h))["interval_days"] == 7
    # A whole-answer item saved for a point stays whole, and says so.
    again = save_raw(client, h, qid, criterion=label)
    assert again["saved"] == "It's already saved for the whole answer, which covers every point."
    assert only(again)["points"] == []


def test_an_item_from_before_reads_the_same(client):
    h = nurse(client)
    iv, _r, label, missing = a_round(client, h)
    qid = missing[0]["question_id"]
    item = save(client, h, qid, session_id=iv, criterion=label)
    with client.app.state.session_factory() as db:  # as stored before: one point, no list
        row = db.get(ReviewItem, item["id"])
        row.points = None
        db.commit()
    shown = only(queue(client, h))
    assert shown["criterion"] == label and shown["points"] == [label]
    assert exported(client, h)["saved_for_point"] == label
    assert exported(client, h)["saved_for_points"] == [label]


def test_the_export_lists_every_point(client):
    h = nurse(client)
    _item, _qid, label, second, *_ = two_points(client, h)
    row = exported(client, h)
    assert row["saved_for_point"] == label and row["saved_for_points"] == [label, second]


def test_a_hundred_answers_with_points_disputed_on_half_read_in_the_same_statements_as_one(client):
    h = nurse(client)
    item = save(client, h, criterion="Backs it up with a concrete example")
    save(client, h, criterion="Lays out clear steps or habits")
    backdate(client, item["id"], days=3)
    start = datetime.now(UTC) - timedelta(days=2)
    uid = user_id(client)
    ids = many_answers(client, uid, 1, start)
    queue(client, h)
    seen, stop = statements(client)
    queue(client, h)
    one = len(seen)
    stop()
    ids += many_answers(client, uid, 99, start + timedelta(minutes=5))
    with client.app.state.session_factory() as db:
        now = datetime.now(UTC)
        for n, aid in enumerate(ids[::2]):  # half disputed, on one point or the other
            point = "Backs it up with a concrete example" if n % 2 else "Lays out clear steps or habits"
            db.add(AnswerFlag(answer_id=aid, user_id=uid, criterion=point, kind="disagree", disputed_at=now))
        db.commit()
    queue(client, h)
    seen, stop = statements(client)
    shown = only(queue(client, h))
    stop()
    assert shown["reviews"] == 50 and shown["points"] == [
        "Backs it up with a concrete example",
        "Lays out clear steps or habits",
    ]
    assert len(seen) == one, (one, len(seen))


def test_another_accounts_items_and_disputes_never_apply(client):
    a = nurse(client)
    item = save(client, a, criterion="Backs it up with a concrete example")
    b = nurse(client, "bea@example.com")
    assert remove_point(client, b, item["id"], "Backs it up with a concrete example").status_code == 404
    r = save_raw(client, b, QID, criterion="Lays out clear steps or habits")
    assert only(r)["points"] == ["Lays out clear steps or habits"]  # Bea's own item
    assert only(queue(client, a))["points"] == ["Backs it up with a concrete example"]


@pytestmark_pg
def test_on_postgresql_the_points_read_only_this_accounts_rows(client):
    """Row-level security: a request scoped to one account can't read another's item or its points."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db import rls

    a = nurse(client)
    save(client, a, criterion="Backs it up with a concrete example")
    b = nurse(client, "bea@example.com")
    with Session(client.app.state.engine) as db:
        rls.bind_user(db, user_id(client, "bea@example.com"))
        assert db.scalars(select(ReviewItem.points)).all() == []
    assert queue(client, b)["due"] == [] and queue(client, b)["upcoming"] == []

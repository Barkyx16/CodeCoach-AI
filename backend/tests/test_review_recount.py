"""Review ladders recounted from history so a dispute applies to every answer (Volume 15, prompt 9;
docs/DISPUTES.md, "The review queue"): an item counted before the rule (built here the old way, its
stored step already moved by an answer now disputed) recounts without that score and says what
changed; the queue, the schedule (and Today, which reads the queue) and the export show the same
ladder; a snooze still holds; an item saved for one point is held by a dispute on that point and an
item saved for another isn't; withdrawing restores both; a long history reads in the same number of
statements; answers, scores and feedback never change; another account's rows never count, and on
PostgreSQL row-level security keeps them out even if the query forgot its owner filter. Synthetic
data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import event, select

from app.models import AnswerFlag, PracticeAnswer, ReviewItem, User
from app.services import review_queue
from tests.test_disputes import flag
from tests.test_disputes_everywhere import QUEUE, TRACK, a_round, all_items, nurse, reinstate
from tests.test_review import STRONG, WEAK
from tests.test_roadmap import answer
from tests.test_row_level_security import pytestmark_pg

QID = "e-time-0"


def queue(client, h):
    r = client.get(QUEUE, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def only(q):
    [item] = all_items(q)
    return item


def save(client, h, qid=QID, **body):
    r = client.post(QUEUE, headers=h, json={"track": TRACK, "question_id": qid, **body})
    assert r.status_code in (200, 201), r.text
    return next(i for i in all_items(r.json()) if i["question_id"] == qid)


def backdate(client, item_id, days=1):
    """Saved a day ago, so every answer here comes after it."""
    with client.app.state.session_factory() as db:
        row = db.get(ReviewItem, item_id)
        then = datetime.now(UTC) - timedelta(days=days)
        row.created_at = row.scheduled_at = then
        row.due_at = then + timedelta(days=1)
        db.commit()


def old_way(client, item_id, answers):
    """The stored ladder as the code before Volume 14, prompt 9 left it: every answer counted, in order,
    whatever was disputed later."""
    step = 0
    with client.app.state.session_factory() as db:
        row = db.get(ReviewItem, item_id)
        for a in answers:
            step = min(step + 1, 4) if a["score"] >= 85 else (0 if a["score"] < 70 else step)
        last = db.get(PracticeAnswer, answers[-1]["id"])
        at = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=UTC)
        row.step, row.reviews, row.last_score = step, len(answers), answers[-1]["score"]
        row.scheduled_at, row.due_at = at, at + timedelta(days=(1, 3, 7, 14, 30)[step])
        db.commit()


def scored(client, a, score):
    """Synthetic set-up only: this answer's score as stored (the app never changes one)."""
    with client.app.state.session_factory() as db:
        db.get(PracticeAnswer, a["id"]).score = score
        db.commit()
    return {**a, "score": score}


def parse(text):
    at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def schedulable(client, h):
    r = client.get("/api/v1/me/schedule/schedulable", headers=h)
    assert r.status_code == 200, r.text
    return [o["ref"] for o in r.json() if o["kind"] == "review_item"]


def exported(client, h):
    [row] = client.get("/api/v1/me/export", headers=h).json()["review_queue"]
    return row


def stored_answers(client):
    with client.app.state.session_factory() as db:
        return sorted((a.id, a.score, a.feedback) for a in db.scalars(select(PracticeAnswer)))


def test_an_item_counted_the_old_way_recounts_without_the_disputed_score_and_says_what_changed(client):
    h = nurse(client)
    item = save(client, h)
    backdate(client, item["id"])
    a1, a2 = answer(client, h, TRACK, QID, STRONG), answer(client, h, TRACK, QID, STRONG)
    assert a1["score"] >= 85 and a2["score"] >= 85
    old_way(client, item["id"], [a1, a2])
    before = only(queue(client, h))
    assert (before["interval_days"], before["reviews"], before["recounted"]) == (7, 2, None)
    answers_before = stored_answers(client)

    f = flag(client, h, a1["id"], "Overall")
    after = only(queue(client, h))
    assert (after["interval_days"], after["reviews"], after["last_score"]) == (3, 1, a2["score"])
    assert after["recounted"] == "Recounted: one earlier score was disputed, so it's due in 3 days, not 7."
    assert after["why"].endswith(after["recounted"])
    # Never an answer, a score or the feedback: only what the queue shows.
    assert stored_answers(client) == answers_before
    with client.app.state.session_factory() as db:
        assert db.get(ReviewItem, item["id"]).step == 2  # the stored count isn't rewritten

    # Withdrawing the dispute restores the count.
    reinstate(client, h, a1["id"], f["id"])
    back = only(queue(client, h))
    assert (back["interval_days"], back["reviews"], back["recounted"]) == (7, 2, None)


def test_the_queue_the_schedule_and_the_export_show_the_same_recounted_ladder(client):
    h = nurse(client)
    item = save(client, h)
    backdate(client, item["id"])
    answers = [answer(client, h, TRACK, QID, STRONG) for _ in range(4)]
    old_way(client, item["id"], answers)  # four strong answers: the 30-day step
    assert item["id"] not in schedulable(client, h)  # not due within the schedule's 14 days
    assert exported(client, h)["step"] == 4 and exported(client, h)["recounted"] is False

    for a in answers[1:]:
        flag(client, h, a["id"], "Overall")
    shown = only(queue(client, h))
    assert shown["interval_days"] == 3 and shown["reviews"] == 1
    assert (
        shown["recounted"] == "Recounted: three earlier scores were disputed, so it's due in 3 days, not 30."
    )
    assert item["id"] in schedulable(client, h)  # the schedule follows the recount
    row = exported(client, h)
    assert (row["step"], row["reviews"], row["last_score"], row["recounted"]) == (
        1,
        1,
        answers[0]["score"],
        True,
    )
    assert parse(row["due_at"]) == parse(shown["due_at"])


def test_a_recount_never_brings_a_snoozed_item_back_before_its_snooze(client):
    h = nurse(client)
    item = save(client, h)
    backdate(client, item["id"])
    a1, a2 = answer(client, h, TRACK, QID, WEAK), answer(client, h, TRACK, QID, STRONG)
    old_way(client, item["id"], [a1, a2])
    snoozed = client.post(f"{QUEUE}/{item['id']}/snooze", headers=h, json={"days": 7}).json()
    until = only(snoozed)["due_at"]
    flag(client, h, a2["id"], "Overall")  # the recount alone would make it due sooner
    after = only(queue(client, h))
    assert after["due_at"] == until and after["snoozed"] and after["recounted"] is None
    assert after["reviews"] == 1 and after["last_score"] == a1["score"]


def other_point(r, item, label):
    return next(p["label"] for p in item["feedback"]["points"] if p["label"] not in (label, "Overall"))


def test_a_point_dispute_holds_an_item_saved_for_that_point_and_not_one_saved_for_another(client):
    h = nurse(client)
    iv, r, label, missing = a_round(client, h)
    first, second = missing[0], missing[1]
    held = save(client, h, first["question_id"], session_id=iv, criterion=label)
    other = save(client, h, second["question_id"], session_id=iv, criterion=other_point(r, second, label))
    assert held["criterion"] == label and other["criterion"] != label
    f1 = flag(client, h, first["feedback"]["id"], label)
    f2 = flag(client, h, second["feedback"]["id"], label)
    q = queue(client, h)
    assert [i["id"] for i in q["disputed"]] == [held["id"]]
    [shown] = q["disputed"]
    assert shown["why"].startswith(
        f"Not scheduled: you saved it from an interview answer, for “{label}”, and you disputed that point"
    )
    assert other["id"] in [i["id"] for i in q["due"] + q["upcoming"]]
    assert held["id"] not in schedulable(client, h) and other["id"] in schedulable(client, h)
    # An item saved for the whole answer isn't held by a dispute of one point (Volume 14's rule).
    # Withdrawing restores it.
    reinstate(client, h, first["feedback"]["id"], f1["id"])
    reinstate(client, h, second["feedback"]["id"], f2["id"])
    q = queue(client, h)
    assert q["disputed"] == [] and {held["id"], other["id"]} <= {i["id"] for i in q["due"] + q["upcoming"]}


def test_a_point_dispute_on_a_later_answer_is_left_out_of_the_recount_and_said(client):
    h = nurse(client)
    iv, r, label, missing = a_round(client, h)
    qid = missing[0]["question_id"]
    item = save(client, h, qid, session_id=iv, criterion=label)  # saved after the round's answers
    a1, a2 = answer(client, h, TRACK, qid, STRONG), answer(client, h, TRACK, qid, STRONG)
    a1, a2 = scored(client, a1, 90), scored(client, a2, 90)  # synthetic: two strong answers
    old_way(client, item["id"], [a1, a2])
    labels = [p["label"] for p in a2["points"]]
    assert label in labels
    # A dispute of another point of that answer leaves the score in: the item wasn't saved for it.
    other = next(x for x in labels if x not in (label, "Overall"))
    flag(client, h, a2["id"], other)
    assert only(queue(client, h))["interval_days"] == 7
    f = flag(client, h, a2["id"], label)
    shown = only(queue(client, h))
    assert shown["interval_days"] == 3 and shown["reviews"] == 1
    assert shown["recounted"] == (
        f"Recounted: one earlier score was disputed (on “{label}”, the point it was saved for), so it's due in "
        "3 days, not 7."
    )
    reinstate(client, h, a2["id"], f["id"])
    assert only(queue(client, h))["interval_days"] == 7


def test_saving_for_the_whole_feedback_is_no_one_point(client):
    h = nurse(client)
    assert save(client, h, criterion="Overall")["criterion"] is None
    assert save(client, h, "e-good-0", criterion="  ")["criterion"] is None


def statements(client):
    seen: list[str] = []
    engine = client.app.state.engine

    def record(_conn, _cursor, statement, *_args):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    return seen, lambda: event.remove(engine, "before_cursor_execute", record)


def many_answers(client, user_id, n, start):
    with client.app.state.session_factory() as db:
        ids = []
        for i in range(n):
            a = PracticeAnswer(
                user_id=user_id,
                track=TRACK,
                question_id=QID,
                difficulty="easy",
                answer=f"Synthetic answer {i}",
                score=90 if i % 3 else 60,
                feedback={"points": []},
                provider="rules",
                created_at=start + timedelta(minutes=i),
            )
            db.add(a)
            db.flush()
            ids.append(a.id)
        db.commit()
        return ids


def user_id(client, email="ada@example.com"):
    with client.app.state.session_factory() as db:
        return db.scalar(select(User.id).where(User.email == email))


def test_a_hundred_answers_read_in_the_same_statements_as_one(client):
    h = nurse(client)
    item = save(client, h)
    backdate(client, item["id"], days=3)
    start = datetime.now(UTC) - timedelta(days=2)
    uid = user_id(client)
    ids = many_answers(client, uid, 1, start)
    queue(client, h)  # counted once into the stored ladder
    seen, stop = statements(client)
    queue(client, h)
    one = len(seen)
    stop()

    ids += many_answers(client, uid, 99, start + timedelta(minutes=5))
    with client.app.state.session_factory() as db:
        now = datetime.now(UTC)
        for aid in ids[::2]:  # half of them disputed: the recount runs over the whole history
            db.add(
                AnswerFlag(answer_id=aid, user_id=uid, criterion="Overall", kind="disagree", disputed_at=now)
            )
        db.commit()
    queue(client, h)
    seen, stop = statements(client)
    t0 = datetime.now(UTC)
    shown = only(queue(client, h))
    elapsed = (datetime.now(UTC) - t0).total_seconds()
    stop()
    assert shown["reviews"] == 50  # half disputed: those scores left out of the recount
    assert len(seen) == one, (one, len(seen))  # the same statements: never one per answer
    assert elapsed < 2.0, elapsed


def test_another_accounts_answers_and_disputes_never_count(client):
    a = nurse(client)
    item = save(client, a)
    backdate(client, item["id"])
    b = nurse(client, "bea@example.com")
    theirs = answer(client, b, TRACK, QID, STRONG)
    flag(client, b, theirs["id"], "Overall")
    shown = only(queue(client, a))
    assert (shown["reviews"], shown["recounted"]) == (0, None)


@pytestmark_pg
def test_on_postgresql_the_recount_reads_only_this_accounts_rows_even_without_its_owner_filter(
    client, monkeypatch
):
    """Row-level security keeps the recount to this account's rows, even if the history query lost
    its owner filter (the bug it exists for)."""
    a = nurse(client)
    item = save(client, a)
    backdate(client, item["id"])
    b = nurse(client, "bea@example.com")
    for _ in range(3):
        flag(client, b, answer(client, b, TRACK, QID, STRONG)["id"], "Overall")

    def careless(_user_id, question_ids):  # the real one also names the account
        return (
            select(
                PracticeAnswer.id,
                PracticeAnswer.track,
                PracticeAnswer.question_id,
                PracticeAnswer.score,
                PracticeAnswer.created_at,
            )
            .where(PracticeAnswer.question_id.in_(sorted(question_ids)))
            .order_by(PracticeAnswer.created_at, PracticeAnswer.id)
        )

    monkeypatch.setattr(review_queue, "_answers_to", careless)
    shown = only(queue(client, a))
    assert (shown["reviews"], shown["recounted"]) == (0, None)


def test_nothing_is_scheduled_that_wasnt_saved(client):
    h = nurse(client)
    answer(client, h, TRACK, QID, STRONG)
    assert all_items(queue(client, h)) == [] and schedulable(client, h) == []

"""Which questions were saved for review comes back from a backup file, and nothing it can't prove
(Volume 20, prompt 1; docs/BACKUP_FORMAT.md). Each is a new item starting afresh: the ladder's first
rung, due as a newly saved question is, no score, no reviews and no points from the file, however
the file was edited. A question already in the queue is left as it is; one removed in the file, or
removed here, stays removed. The queue's limit holds. Removing the restore takes away only what it
added and is still as added: anything practised, snoozed, given a point, scheduled or removed since
is kept or already gone. Version 1 and version 2 files are both read. Synthetic data only."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import ReviewItem, User
from app.services.restore import NOTES
from app.services.review_queue import LADDER, MAX_ACTIVE
from tests.test_restore import P, apply, backup, nurse, preview

TRACK = "registered-nurse"
QUESTIONS = ["e-time-0", "e-time-1", "e-inform-0"]
REVIEWS = "/api/v1/me/reviews"


def save(client, h, question, criterion=None):
    r = client.post(
        REVIEWS, headers=h, json={"track": TRACK, "question_id": question, "criterion": criterion}
    )
    assert r.status_code in (200, 201), r.text
    return next(i for i in listed(r.json()) if i["question_id"] == question)


def listed(queue: dict) -> list[dict]:
    return queue["due"] + queue["upcoming"] + queue["disputed"]


def rows(client, email) -> dict[str, ReviewItem]:
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        return {r.question_id: r for r in db.scalars(select(ReviewItem).where(ReviewItem.user_id == uid))}


def progressed(client, email):
    """A ladder well along, as practice would leave it: the file then carries all of it."""
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        db.execute(
            update(ReviewItem)
            .where(ReviewItem.user_id == uid)
            .values(step=3, reviews=4, last_score=91, due_at=datetime.now(UTC) + timedelta(days=13))
        )
        db.commit()


def category(body, key="review_queue"):
    return next(c for c in body["categories"] if c["key"] == key)


def a_file(client, version=1):
    """Account A saves three questions (one for a point), practises them along, removes the third."""
    a = nurse(client)
    first = save(client, a, QUESTIONS[0], criterion="Name the trade-off")
    save(client, a, QUESTIONS[1])
    third = save(client, a, QUESTIONS[2])
    progressed(client, "ada@example.com")
    assert client.delete(f"{REVIEWS}/{third['id']}", headers=a).status_code == 200
    if version == 1:
        raw = backup(client, a)
    else:
        raw = json.dumps(client.get("/api/v1/me/export", params={"version": 2}, headers=a).json()).encode()
    return a, first, raw


def test_the_preview_offers_the_saved_questions_and_says_what_isnt_restored(client):
    _, _, raw = a_file(client)
    b = nurse(client, "bea@example.com")
    body = preview(client, b, raw).json()
    cat = category(body)
    assert (cat["found"], cat["new"], cat["duplicates"]) == (3, 2, 0)
    assert cat["skipped"] == [
        {"reason": "Removed from the queue when the file was made: left out", "count": 1}
    ]
    assert cat["note"] == NOTES["review_queue"] and "aren't restored" in cat["note"]
    assert "A time patient assessment mattered" in cat["samples"]
    # It's offered, so it's no longer among what isn't restored; other categories carry no note.
    assert "review_queue" not in {u["key"] for u in body["not_restored"]}
    assert all(c["note"] is None for c in body["categories"] if c["key"] != "review_queue")
    assert rows(client, "bea@example.com") == {}  # the preview changes nothing


def test_applying_starts_every_ladder_afresh_with_nothing_from_the_file(client):
    _, _, raw = a_file(client)
    b = nurse(client, "bea@example.com")
    before = datetime.now(UTC)
    r = apply(client, b, raw, ["review_queue"])
    assert r.status_code == 201, r.text
    assert r.json()["counts"]["review_queue"] == {"added": 2, "duplicates": 0, "skipped": 1}
    got = rows(client, "bea@example.com")
    assert set(got) == set(QUESTIONS[:2])
    for row in got.values():
        assert (row.step, row.reviews, row.last_score, row.criterion, row.points, row.removed_points) == (
            0,
            0,
            None,
            None,
            None,
            None,
        )
        due = row.due_at if row.due_at.tzinfo else row.due_at.replace(tzinfo=UTC)
        assert before + timedelta(days=LADDER[0]) - timedelta(seconds=5) <= due
        assert due <= datetime.now(UTC) + timedelta(days=LADDER[0])
        assert not row.removed and not row.snoozed
    queue = listed(client.get(REVIEWS, headers=b).json())
    assert {i["question_id"] for i in queue} == set(QUESTIONS[:2])
    assert all(not i["due"] for i in queue)  # due a day from now, as a newly saved question


def test_an_edited_file_can_only_name_questions(client):
    b = nurse(client, "bea@example.com")
    far = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    raw = json.dumps(
        {
            "export_version": 1,
            "review_queue": [
                {
                    "career": TRACK,
                    "question": QUESTIONS[0],
                    "step": 4,
                    "reviews": 99,
                    "last_score": 100,
                    "due_at": far,
                    "saved_for_point": "Made up",
                    "saved_for_points": ["Made up", "Also made up"],
                    "removed": False,
                    "user_id": "someone-else",
                },
                {"career": TRACK, "question": "not-a-question"},
                {"career": "astronaut", "question": QUESTIONS[1]},
                {"career": TRACK},
                {"career": TRACK, "question": QUESTIONS[0]},  # twice in one file
            ],
        }
    ).encode()
    cat = category(preview(client, b, raw).json())
    assert (cat["new"], cat["duplicates"]) == (1, 1)
    assert {s["reason"]: s["count"] for s in cat["skipped"]} == {
        "The question isn't in the library (it's never swapped for a similar one)": 2,
        "Malformed": 1,
    }
    assert apply(client, b, raw, ["review_queue"]).status_code == 201
    row = rows(client, "bea@example.com")[QUESTIONS[0]]
    assert (row.step, row.reviews, row.last_score, row.criterion, row.points) == (0, 0, None, None, None)


def test_a_question_already_saved_is_left_as_it_is_and_a_removed_one_stays_removed(client):
    _, _, raw = a_file(client)
    b = nurse(client, "bea@example.com")
    save(client, b, QUESTIONS[0], criterion="Bea's own point")
    progressed(client, "bea@example.com")
    gone = save(client, b, QUESTIONS[1])
    assert client.delete(f"{REVIEWS}/{gone['id']}", headers=b).status_code == 200
    cat = category(preview(client, b, raw).json())
    assert (cat["new"], cat["duplicates"]) == (0, 1)
    assert {s["reason"]: s["count"] for s in cat["skipped"]} == {
        "Removed from the queue when the file was made: left out": 1,
        "Removed from your queue here: left as it is (put it back from Removed recently)": 1,
    }
    before = {
        q: (r.step, r.reviews, r.last_score, r.criterion, r.removed)
        for q, r in rows(client, "bea@example.com").items()
    }
    r = apply(client, b, raw, ["review_queue", "notes"])
    assert r.status_code == 201 and r.json()["counts"]["review_queue"]["added"] == 0
    after = {
        q: (r.step, r.reviews, r.last_score, r.criterion, r.removed)
        for q, r in rows(client, "bea@example.com").items()
    }
    assert after == before


def test_the_queue_limit_holds_and_nothing_changes(client):
    _, _, raw = a_file(client)
    b = nurse(client, "bea@example.com")
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == "bea@example.com"))
        now = datetime.now(UTC)
        for i in range(MAX_ACTIVE - 1):
            db.add(
                ReviewItem(user_id=uid, track=TRACK, question_id=f"filler-{i}", due_at=now, scheduled_at=now)
            )
        db.commit()
    r = apply(client, b, raw, ["review_queue"])
    assert r.status_code == 400 and r.json()["error"]["code"] == "over_limit", r.text
    assert "limit of 100" in r.json()["error"]["message"]
    assert not {QUESTIONS[0], QUESTIONS[1]} & set(rows(client, "bea@example.com"))


def test_a_restore_goes_only_into_the_signed_in_account(client):
    a, _, raw = a_file(client)
    before = {q: (r.step, r.removed) for q, r in rows(client, "ada@example.com").items()}
    b = nurse(client, "bea@example.com")
    assert apply(client, b, raw, ["review_queue"]).status_code == 201
    assert {q: (r.step, r.removed) for q, r in rows(client, "ada@example.com").items()} == before
    assert client.get(f"{P}/batches", headers=a).json() == []


def test_removing_the_restore_takes_only_what_it_added_and_is_unchanged(client):
    a = nurse(client)
    for q in ["e-time-0", "e-time-1", "e-inform-0", "e-inform-2"]:
        save(client, a, q)
    raw = backup(client, a)
    b = nurse(client, "bea@example.com")
    own = save(client, b, "e-inform-3")  # Bea's own, never the restore's
    batch = apply(client, b, raw, ["review_queue"]).json()
    items = {i["question_id"]: i for i in listed(client.get(REVIEWS, headers=b).json())}
    # Changed since: snoozed, scheduled, removed; one left as restored.
    assert (
        client.post(f"{REVIEWS}/{items['e-time-1']['id']}/snooze", headers=b, json={"days": 3}).status_code
        == 200
    )
    entry = {
        "kind": "review_item",
        "ref": items["e-inform-0"]["id"],
        "on_date": (datetime.now(UTC) + timedelta(days=2)).date().isoformat(),
        "all_day": True,
    }
    assert client.post("/api/v1/me/schedule", headers=b, json=entry).status_code == 201
    assert client.delete(f"{REVIEWS}/{items['e-inform-2']['id']}", headers=b).status_code == 200
    out = client.post(f"{P}/batches/{batch['id']}/remove", headers=b).json()
    assert out["removal"] == {"removed": 1, "kept_edited": 2, "already_gone": 1}
    left = rows(client, "bea@example.com")
    assert "e-time-0" not in left  # unchanged since: taken away
    assert {"e-time-1", "e-inform-0", "e-inform-3"} <= set(left)  # changed since, and Bea's own
    assert left["e-inform-3"].id == own["id"] and not left["e-inform-3"].removed


def test_a_version_2_file_restores_the_same_way_and_twice_adds_nothing(client):
    _, _, raw = a_file(client, version=2)
    b = nurse(client, "bea@example.com")
    cat = category(preview(client, b, raw).json())
    assert (cat["found"], cat["new"]) == (3, 2)
    first = apply(client, b, raw, ["review_queue"])
    assert first.status_code == 201
    again = apply(client, b, raw, ["review_queue"])
    assert again.json()["id"] == first.json()["id"]  # the same file and choice: the first batch
    assert len(rows(client, "bea@example.com")) == 2

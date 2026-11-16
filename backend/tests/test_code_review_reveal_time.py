"""A code review's "Solution revealed" carries when the authored review was first shown (Volume 18,
prompt 9; docs/ATTEMPT_CONDITIONS.md). Before, the time beside it was the review's own: the reveal's
time wasn't kept. Now the first showing at an exercise version is kept with the draft
(`code_review_drafts.revealed_at`), whether asked for or shown by sending a review, and copied onto
each review written after it (`code_review_attempts.revealed_at`); showing it again doesn't move it;
a new version of the exercise is a new first showing. A review from before, with only the flag,
says the time wasn't recorded and that the time beside it is the review's. The export carries both.
Another account's reveal is never this account's. Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import CodeReviewAttempt, CodeReviewDraft
from app.services.conditions import REVEAL_TIMES_FROM
from tests.test_code_reviews import MINE
from tests.test_practice_conditions import labels, nurse
from tests.test_review_formats_conditions import EXERCISE, a_review


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def draft(client, h) -> CodeReviewDraft:
    me = client.get("/api/v1/auth/me", headers=h).json()["id"]
    with client.app.state.session_factory() as db:
        return db.scalar(
            select(CodeReviewDraft).where(
                CodeReviewDraft.user_id == me, CodeReviewDraft.exercise_slug == EXERCISE
            )
        )


def reveal(client, h):
    assert client.post(f"{MINE}/{EXERCISE}/reveal", headers=h).status_code == 200


def at(attempt) -> datetime:
    [shown] = [x for x in attempt["conditions"]["help"] if x["label"] == "Solution revealed"]
    return datetime.fromisoformat(shown["at"].replace("Z", "+00:00"))


def test_a_review_after_asking_for_the_authored_one_says_when_it_was_shown(client):
    h = nurse(client)
    reveal(client, h)
    shown = _aware(draft(client, h).revealed_at)
    with client.app.state.session_factory() as db:  # as if shown an hour before the review
        db.execute(update(CodeReviewDraft).values(revealed_at=shown - timedelta(hours=1)))
        db.commit()
    review = a_review(client, h)
    assert review["after_reveal"] is True and labels(review["conditions"]) == ["Solution revealed"]
    assert (
        review["conditions"]["help"][0]["detail"] == "The authored review was shown before this was written"
    )
    assert at(review) == shown - timedelta(hours=1)  # the reveal's time, not the review's
    assert at(review) < datetime.fromisoformat(review["created_at"].replace("Z", "+00:00"))


def test_sending_a_review_is_the_first_showing_for_the_next_one(client):
    h = nurse(client)
    first = a_review(client, h)
    assert first["after_reveal"] is False
    sent_at = _aware(draft(client, h).revealed_at)
    second = a_review(client, h)
    assert at(second) == sent_at
    third = a_review(client, h)
    assert at(third) == sent_at  # still the first showing
    reveal(client, h)  # shown again: the time doesn't move
    assert _aware(draft(client, h).revealed_at) == sent_at


def test_a_new_version_of_the_exercise_is_a_new_first_showing(client):
    h = nurse(client)
    reveal(client, h)
    old = _aware(draft(client, h).revealed_at)
    with client.app.state.session_factory() as db:  # as if the earlier showing was at version 0
        db.execute(update(CodeReviewDraft).values(revealed_version=0, revealed_at=old - timedelta(days=2)))
        db.commit()
    review = a_review(client, h)
    assert review["after_reveal"] is False  # not seen at this version
    assert _aware(draft(client, h).revealed_at) > old - timedelta(days=2)


def test_a_review_from_before_says_the_time_wasnt_recorded(client):
    h = nurse(client)
    a_review(client, h)
    second = a_review(client, h)
    with client.app.state.session_factory() as db:  # as stored before the time was kept
        db.execute(
            update(CodeReviewAttempt).where(CodeReviewAttempt.id == second["id"]).values(revealed_at=None)
        )
        db.commit()
    listed = {a["id"]: a for a in client.get(f"{MINE}/{EXERCISE}/attempts", headers=h).json()}
    [shown] = listed[second["id"]]["conditions"]["help"]
    assert shown["label"] == "Solution revealed"
    assert shown["detail"] == (
        "The authored review was shown before this was written (when wasn't recorded before "
        f"{REVEAL_TIMES_FROM}; the time here is this review's)"
    )
    assert datetime.fromisoformat(shown["at"].replace("Z", "+00:00")) == datetime.fromisoformat(
        listed[second["id"]]["created_at"].replace("Z", "+00:00")
    )


def test_the_export_carries_both_times(client):
    h = nurse(client)
    a_review(client, h)
    second = a_review(client, h)
    out = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()["code_reviews"]
    [d] = out["drafts"]
    assert d["revealed_at"] is not None
    row = next(a for a in out["attempts"] if a["id"] == second["id"])
    assert row["revealed_at"] == d["revealed_at"]
    first = next(a for a in out["attempts"] if a["id"] != second["id"])
    assert first["revealed_at"] is None and first["after_reveal"] is False


def test_another_accounts_reveal_is_never_this_accounts(client):
    theirs = nurse(client, "bea@example.com")
    reveal(client, theirs)
    h = nurse(client)
    review = a_review(client, h)
    assert review["after_reveal"] is False and labels(review["conditions"]) == ["No in-app help recorded"]

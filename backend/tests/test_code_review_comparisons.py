"""Code reviews compared by the one contract (Volume 18, prompt 4; docs/COMPARING_ATTEMPTS.md, "Code
reviews"): each review of an exercise is set beside the previous review of the same exercise. The
result is how many of the exercise's authored defects it raised, as its fixed rules matched them; both
results are shown as given, never "improved". The same help (none) at the same version is
comparable; one written after reading the authored review is partly comparable and says why; another
exercise or version isn't comparable with it. Its list, its own page and History say the same. Another
account's review is never the one before. Synthetic data only."""

from __future__ import annotations

from sqlalchemy import update

from app.models import CodeReviewAttempt
from tests.test_code_reviews import MINE, finding
from tests.test_code_reviews import send as review
from tests.test_history_practice import feed
from tests.test_practice_conditions import nurse
from tests.test_review_formats_conditions import EXERCISE

OTHER = "review-largest-number"


def a_review(client, h, slug=EXERCISE, problem="duplicates of the max slip in"):
    r = review(client, h, slug, [finding("d", 9, 10, problem)])
    assert r.status_code in (200, 201), r.text
    return r.json()


def listed(client, h, slug=EXERCISE):
    r = client.get(f"{MINE}/{slug}/attempts", headers=h)
    assert r.status_code == 200, r.text
    return {x["id"]: x for x in r.json()}


def page(client, h, attempt_id):
    r = client.get(f"{MINE}/attempts/{attempt_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def history_row(client, h, attempt_id):
    rows = feed(client, h, type="code_review_attempt")["items"]
    return next(r for r in rows if r["target"]["attempt_id"] == attempt_id)


def test_the_second_review_is_partly_comparable_since_the_first_showed_the_authored_review(client):
    """Sending a review shows the authored one with its feedback, so the next is written after reading
    it: the help differed, and the comparison says so; both results are shown as given."""
    h = nurse(client)
    first = a_review(client, h)
    second = a_review(client, h, problem="when the largest value repeats, the second largest is wrong")
    rows = listed(client, h)
    assert rows[first["id"]]["compared"] is None
    assert rows[first["id"]]["not_compared"] == "Not compared: the first checked attempt at this exercise"
    c = rows[second["id"]]["compared"]
    assert c["previous"]["id"] == first["id"]
    assert c["comparison"]["outcome"] == "partially_comparable"
    assert (
        "before the earlier one, none recorded; before the later one, solution revealed"
        in (c["comparison"]["explanation"])
    )
    fb = second["feedback"]
    assert c["result"] == f"{fb['defects_raised']} of {fb['defects_total']} authored defects raised"
    for claim in ("improved", "better", "worse"):
        assert claim not in str(c).lower()
    # Its own page and History say the same.
    assert page(client, h, second["id"])["compared"] == c
    assert history_row(client, h, second["id"])["detail"].endswith(" · Partly comparable with the one before")
    assert history_row(client, h, first["id"])["detail"].endswith(
        " · Not compared: the first checked attempt at this exercise"
    )


def test_two_reviews_both_after_reading_the_authored_review_are_comparable(client):
    h = nurse(client)
    a_review(client, h)
    second = a_review(client, h, problem="when the largest value repeats, the second largest is wrong")
    third = a_review(client, h, problem="a repeated maximum is taken as the second largest")
    c = listed(client, h)[third["id"]]["compared"]
    assert c["previous"]["id"] == second["id"]
    assert c["comparison"]["outcome"] == "comparable"
    assert c["comparison"]["explanation"].startswith(
        "Comparable: the same exercise and version, checked by the same fixed rules, with the same in-app help"
    )
    assert history_row(client, h, third["id"])["detail"].endswith(" · Comparable with the one before")


def test_reading_the_authored_review_before_the_first_review_is_said_too(client):
    h = nurse(client)
    assert client.post(f"{MINE}/{EXERCISE}/reveal", headers=h).status_code == 200
    first = a_review(client, h)
    second = a_review(client, h, problem="the second largest misses a repeated maximum")
    c = listed(client, h)[second["id"]]["compared"]
    assert first["after_reveal"] is True
    assert c["comparison"]["outcome"] == "comparable"  # both after reading it


def test_reviews_of_different_exercises_are_each_the_first(client):
    h = nurse(client)
    one = a_review(client, h)
    two = a_review(client, h, slug=OTHER, problem="the loop never looks at the last element")
    assert listed(client, h)[one["id"]]["compared"] is None
    assert listed(client, h, OTHER)[two["id"]]["compared"] is None


def test_another_version_of_the_exercise_isnt_comparable(client):
    """Both written after reading the authored review (the same help), but at different versions of
    the exercise: its authored defects may differ, so they're not comparable."""
    h = nurse(client)
    a_review(client, h)
    second = a_review(client, h, problem="when the largest value repeats, the second largest is wrong")
    with client.app.state.session_factory() as db:  # as if reviewed at the exercise's earlier version
        db.execute(
            update(CodeReviewAttempt).where(CodeReviewAttempt.id == second["id"]).values(exercise_version=0)
        )
        db.commit()
    third = a_review(client, h, problem="a repeated maximum is taken as the second largest")
    c = listed(client, h)[third["id"]]["compared"]
    assert c["previous"]["id"] == second["id"]
    assert c["comparison"]["outcome"] in ("incompatible", "partially_comparable")
    assert "version" in c["comparison"]["explanation"]


def test_another_accounts_review_is_never_the_one_before(client):
    theirs = nurse(client, "bea@example.com")
    a_review(client, theirs)
    h = nurse(client)
    mine = a_review(client, h)
    assert listed(client, h)[mine["id"]]["compared"] is None

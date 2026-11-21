"""The help before a code-review exercise, a sample-answer comparison and a work sample (Volume 15,
prompt 3; docs/ATTEMPT_CONDITIONS.md): each format's own answer shown first is "Solution revealed"
(the authored review, the comparison's explanation), a Learn lesson that prepares it is "Hint
shown" for the first attempt after the read only, a work sample's section hints are not help, older
attempts are "Not recorded", another account's reads never count, and the bulk route and the export
carry them by id. Nothing about the feedback changes. Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update

from app.learn import UNIT_INDEX
from app.models import CodeReviewAttempt, ComparisonAttempt, WorkSampleAttempt
from app.services.conditions import practice_version
from tests.test_code_reviews import finding
from tests.test_code_reviews import send as review
from tests.test_comparisons import pick
from tests.test_comparisons import send as compare
from tests.test_practice_conditions import labels, nurse, read
from tests.test_work_samples import GOOD_INCIDENT, INCIDENT
from tests.test_work_samples import send as work_sample

SPECIFIC = "cmp-specific-evidence"
OTHER_LESSON = "cmp-relevance"
STAR = "rn-star-answers"
EXERCISE = "review-second-largest"
CONDITIONS = "/api/v1/me/attempt-conditions"


def a_comparison(client, h, lesson=SPECIFIC, early=False):
    body = client.get(f"/api/v1/comparisons/{lesson}").json()
    sample = body["samples"][0]
    sel = [pick(sample["id"], sample["sentences"][0]["id"], "strength", "It names a real action taken.")]
    r = compare(client, h, lesson, sel, choice=sample["id"] if body["kind"] == "clear" else None, early=early)
    assert r.status_code in (200, 201), r.text
    return r.json()


def a_review(client, h):
    r = review(client, h, EXERCISE, [finding("d", 9, 10, "duplicates of the max slip in")])
    assert r.status_code in (200, 201), r.text
    return r.json()


def a_work_sample(client, h):
    r = work_sample(client, h, INCIDENT, GOOD_INCIDENT)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_the_star_lesson_prepares_the_specific_evidence_comparison_and_the_link_is_real():
    assert f"comparison:{SPECIFIC}" in UNIT_INDEX[STAR].prepares
    assert practice_version(f"comparison:{SPECIFIC}") == 1
    assert practice_version("code_review:review-binary-search") == 1
    assert practice_version(f"work_sample:{INCIDENT}") == 1
    assert practice_version("comparison:cmp-nope") is None


def test_a_code_review_written_after_the_authored_review_was_shown_says_so(client):
    h = nurse(client)
    first = a_review(client, h)
    assert labels(first["conditions"]) == ["No in-app help recorded"]
    again = a_review(client, h)  # the first attempt showed the authored review
    assert again["after_reveal"] is True
    assert labels(again["conditions"]) == ["Solution revealed"]
    assert again["conditions"]["help"][0]["detail"] == "The authored review was shown before this was written"
    listed = {
        a["id"]: a for a in client.get(f"/api/v1/me/code-reviews/{EXERCISE}/attempts", headers=h).json()
    }
    assert labels(listed[again["id"]]["conditions"]) == ["Solution revealed"]
    assert labels(listed[first["id"]]["conditions"]) == ["No in-app help recorded"]


def test_a_comparison_sent_after_its_explanation_was_opened_says_so(client):
    h = nurse(client)
    early = a_comparison(client, h, OTHER_LESSON, early=True)
    assert labels(early["conditions"]) == ["Solution revealed"]
    # Sent as opened with no opening recorded on the account (Volume 19, prompt 5): it says so, and
    # that the time beside it is the reading's own.
    assert early["conditions"]["help"][0]["detail"] == (
        "The explanation was opened before this was sent (opening it wasn't recorded on your account, so "
        "the time here is this reading's)"
    )
    # Its result showed the explanation (Volume 20, prompt 3): the next reading says so, with that time.
    plain = a_comparison(client, h, OTHER_LESSON)
    [seen] = plain["conditions"]["help"]
    assert seen["detail"] == "The explanation was shown with an earlier reading's result before this was sent"
    assert seen["at"] == early["created_at"]
    # Opened through the page's recording route first: the plain words, with the opening's time.
    opened = client.post(f"/api/v1/me/comparisons/{SPECIFIC}/explanation", json={}, headers=h).json()
    recorded = a_comparison(client, h, SPECIFIC, early=True)
    [help_] = recorded["conditions"]["help"]
    assert help_["detail"] == "The explanation was opened before this was sent"
    assert datetime.fromisoformat(help_["at"].replace("Z", "+00:00")) == datetime.fromisoformat(
        opened["opened_at"].replace("Z", "+00:00")
    )


def test_a_lesson_that_prepares_a_comparison_is_help_for_the_first_attempt_after_it_only(client):
    h = nurse(client)
    read(client, h, STAR)
    first = a_comparison(client, h)
    assert labels(first["conditions"]) == ["Hint shown"]
    assert first["conditions"]["help"][0]["detail"].startswith("Lesson “Structuring a behavioral answer")
    second = a_comparison(client, h)
    # The lesson isn't help for it; the first reading's result, which showed the explanation, is
    # (Volume 20, prompt 3).
    assert labels(second["conditions"]) == ["Solution revealed"]
    assert "shown with an earlier reading's result" in second["conditions"]["help"][0]["detail"]
    # A lesson that prepares a different comparison isn't help for this one.
    assert labels(a_comparison(client, h, OTHER_LESSON)["conditions"]) == ["No in-app help recorded"]


def test_a_work_samples_hints_arent_help_and_no_lesson_prepares_a_brief(client):
    h = nurse(client)
    for unit in UNIT_INDEX:
        read(client, h, unit)
    made = a_work_sample(client, h)
    assert labels(made["conditions"]) == ["No in-app help recorded"]


def test_attempts_from_before_recording_began_are_not_recorded_unless_their_own_flag_says_more(client):
    h = nurse(client)
    rev = a_review(client, h)
    revealed = a_review(client, h)
    cmp_ = a_comparison(client, h, OTHER_LESSON)
    ws = a_work_sample(client, h)
    then = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
    with client.app.state.session_factory() as db:
        for model, ids in (
            (CodeReviewAttempt, [rev["id"], revealed["id"]]),
            (ComparisonAttempt, [cmp_["id"]]),
            (WorkSampleAttempt, [ws["id"]]),
        ):
            db.execute(update(model).where(model.id.in_(ids)).values(created_at=then))
        db.commit()
    got = client.post(
        CONDITIONS,
        headers=h,
        json={
            "code_review_attempt_ids": [rev["id"], revealed["id"]],
            "comparison_attempt_ids": [cmp_["id"]],
            "work_sample_attempt_ids": [ws["id"]],
        },
    ).json()
    assert labels(got["code_review_attempts"][rev["id"]]) == ["Not recorded"]
    assert got["code_review_attempts"][rev["id"]]["recorded_from"] == "2026-11-15"
    assert labels(got["code_review_attempts"][revealed["id"]]) == ["Solution revealed"]  # always stored
    assert labels(got["comparison_attempts"][cmp_["id"]]) == ["Not recorded"]
    assert labels(got["work_sample_attempts"][ws["id"]]) == ["Not recorded"]


def test_another_accounts_reads_never_count_and_its_attempts_are_left_out(client):
    a = nurse(client)
    b = nurse(client, email="bea@example.com")
    read(client, b, STAR)
    mine = a_comparison(client, a)
    assert labels(mine["conditions"]) == ["No in-app help recorded"]
    theirs = a_comparison(client, b)
    got = client.post(
        CONDITIONS, headers=a, json={"comparison_attempt_ids": [mine["id"], theirs["id"]]}
    ).json()
    assert set(got["comparison_attempts"]) == {mine["id"]}


def test_the_export_carries_each_attempts_conditions_by_id(client):
    h = nurse(client)
    a_review(client, h)
    revealed = a_review(client, h)
    early = a_comparison(client, h, early=True)
    ws = a_work_sample(client, h)
    doc = client.get("/api/v1/me/export", headers=h).json()
    reviews = {r["id"]: r for r in doc["code_reviews"]["attempts"]}
    comparisons = {r["id"]: r for r in doc["comparisons"]}
    samples = {r["id"]: r for r in doc["work_samples"]["attempts"]}
    assert labels(reviews[revealed["id"]]["conditions"]) == ["Solution revealed"]
    assert labels(comparisons[early["id"]]["conditions"]) == ["Solution revealed"]
    assert labels(samples[ws["id"]]["conditions"]) == ["No in-app help recorded"]

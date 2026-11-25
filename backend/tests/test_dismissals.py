"""Suggestions dismissed with "Not now", kept with the account (Volume 15, prompt 2;
docs/FOLLOW_UPS.md, "Not now"): a dismissed follow-up isn't offered on any device, the question's
other follow-ups still are, Settings lists what was dismissed in plain words and can offer it again
(it then follows its own rules), the same dismissal twice is one record, another account's are never
read or changed, the export carries them and deleting the account removes them. A follow-up
problem's dismissal kept in the onboarding row before moves here with the migration. Synthetic data
only."""

from __future__ import annotations

import json

from sqlalchemy import create_engine, select, text

from app.careers.followups import RELATIONSHIPS, FollowUp
from app.models import DismissedSuggestion, SubmissionStatus
from tests.conftest import auth_headers
from tests.test_follow_ups import NURSE, A, B, answer, nurse, offer
from tests.test_problem_followups import FU, SORTED, passed_two_sum, submit
from tests.test_storage import needs_admin, rehearsal, run  # noqa: F401  (rehearsal: a fixture)
from tests.test_submission_comparisons import coder, judge

URL = "/api/v1/me/dismissals"
KEY = f"question-follow-up:{NURSE}/{A}>{B}"


def offered_follow_up(client, h):
    for _ in range(2):
        assert answer(client, h, A).status_code == 201
    got = offer(client, h)
    assert [o["question_id"] for o in got["offers"]] == [B]
    return got


def dismiss(client, h, key, offered_on=None):
    r = client.post(URL, headers=h, json={"items": [{"key": key, "offered_on": offered_on}]})
    return r


def listed(client, h):
    r = client.get(URL, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def second_device(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "CorrectHorse42"})
    assert r.status_code == 200, r.text
    return auth_headers(r.json())


def test_a_dismissed_follow_up_question_isnt_offered_on_any_device_and_can_be_offered_again(client):
    h = nurse(client)
    offered_follow_up(client, h)
    r = dismiss(client, h, KEY, offered_on=f"/careers/{NURSE}/questions/{A}")
    assert r.status_code == 200, r.text
    [item] = r.json()["items"]
    assert item["kind"] == "question_follow_up" and item["offered_on"] == f"/careers/{NURSE}/questions/{A}"
    assert item["label"].startswith("A related question: ") and "(after “" in item["label"]
    assert item["note"] is None
    other = second_device(client, "nia@example.com")
    got = offer(client, other)
    assert got["offers"] == [] and got["dismissed"] == 1 and got["status"] == "offered"
    # Practising the question again doesn't bring it back: the dismissal names the follow-up.
    assert answer(client, other, A).status_code == 201
    assert offer(client, h)["offers"] == []
    # Offered again from Settings, on either device: back on both.
    assert client.delete(URL, headers=other, params={"key": KEY}).status_code == 204
    assert [o["question_id"] for o in offer(client, h)["offers"]] == [B]
    assert offer(client, other)["dismissed"] == 0
    assert client.delete(URL, headers=h, params={"key": KEY}).status_code == 404  # nothing to undo now


def test_dismissing_one_follow_up_leaves_the_questions_others_offered(client, monkeypatch):
    extra = FollowUp(
        track=NURSE, from_id=A, to_id="e-inform-1", objective="Keeping people informed", difference="Another",
        review_status="Reviewed for this test",
    )  # fmt: skip
    rels = (*RELATIONSHIPS, extra)
    from app.careers import followups as content

    monkeypatch.setattr(
        "app.services.followups.follow_ups_from", lambda t, q: content.follow_ups_from(t, q, rels)
    )
    monkeypatch.setattr(
        "app.services.dismissals.follow_ups_from", lambda t, q: content.follow_ups_from(t, q, rels)
    )
    h = nurse(client)
    for _ in range(2):
        answer(client, h, A)
    assert sorted(o["question_id"] for o in offer(client, h)["offers"]) == sorted([B, "e-inform-1"])
    assert dismiss(client, h, KEY).status_code == 200
    got = offer(client, h)
    assert [o["question_id"] for o in got["offers"]] == ["e-inform-1"] and got["dismissed"] == 1


def test_the_list_says_what_each_is_and_what_offering_it_again_will_do(client):
    h = coder(client)
    passed_two_sum(client, h)
    assert client.post(f"{FU}/two-sum-sorted/dismiss", headers=h).json()["status"] == "done"
    assert dismiss(client, h, "plan-change:software-engineer@3").status_code == 200
    items = {i["kind"]: i for i in listed(client, h)}
    assert (
        items["problem_follow_up"]["label"] == "A related problem: Two Sum in a Sorted Array (after Two Sum)"
    )
    assert (
        items["problem_follow_up"]["note"] is None
        and items["problem_follow_up"]["offered_on"] == "/problems/two-sum"
    )
    assert (
        items["plan_change"]["label"].startswith("“Your plan changed” for ")
        and "(plan version 3)" in items["plan_change"]["label"]
    )
    # Tried since: offering it again won't bring it back, and the list says why.
    sub = submit(client, h, slug="two-sum-sorted", code=SORTED).json()["id"]
    judge(client, sub, SubmissionStatus.FAILED, 1, 6)
    [problem] = [i for i in listed(client, h) if i["kind"] == "problem_follow_up"]
    assert problem["note"] == "You've tried this problem since, so it won't be offered again."
    assert client.delete(URL, headers=h, params={"key": problem["key"]}).status_code == 204
    assert client.get(FU, headers=h).json()["status"] == "done"  # its own rule still holds


def test_a_problem_follow_up_offered_again_comes_back_when_untried(client):
    h = coder(client)
    passed_two_sum(client, h)
    client.post(f"{FU}/two-sum-sorted/dismiss", headers=h)
    assert client.get(FU, headers=h).json()["status"] == "done"
    assert (
        client.delete(URL, headers=h, params={"key": "problem-follow-up:two-sum>two-sum-sorted"}).status_code
        == 204
    )
    assert client.get(FU, headers=h).json()["status"] == "offered"


def test_keys_that_name_no_suggestion_are_refused(client):
    h = nurse(client)
    for key in (
        "welcome",
        f"question-follow-up:{NURSE}/{A}>e-nothing-9",  # not a reviewed relationship
        "problem-follow-up:two-sum>valid-anagram",  # not a reviewed pair
        "plan-change:no-such-career@2",
        "plan-change:registered-nurse@0",
    ):
        r = dismiss(client, h, key)
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_dismissal", key
    assert listed(client, h) == []


def test_the_same_dismissal_twice_is_one_record_and_keeps_its_first_time(client):
    h = nurse(client)
    first = dismiss(client, h, KEY).json()["items"][0]["dismissed_at"]
    r = client.post(URL, headers=h, json={"items": [{"key": KEY}, {"key": KEY}]})
    assert r.status_code == 200 and [i["dismissed_at"] for i in r.json()["items"]] == [first]


def test_another_accounts_dismissals_are_never_read_or_changed(client):
    a = nurse(client)
    b = nurse(client, email="bea@example.com")
    dismiss(client, a, KEY)
    assert listed(client, b) == []
    assert client.delete(URL, headers=b, params={"key": KEY}).status_code == 404
    assert [i["key"] for i in listed(client, a)] == [KEY]
    assert offer(client, b)["dismissed"] == 0


def test_the_export_carries_them_and_deleting_the_account_removes_them(client):
    h = nurse(client)
    dismiss(client, h, KEY, offered_on="/careers/x")
    doc = client.get("/api/v1/me/export", headers=h).json()
    [row] = doc["dismissed_suggestions"]
    assert (row["key"], row["kind"], row["offered_on"]) == (KEY, "question_follow_up", "/careers/x")
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code in (200, 202, 204), r.text
    with client.app.state.session_factory() as db:
        assert db.scalars(select(DismissedSuggestion)).all() == []


@needs_admin
def test_the_migration_moves_problem_follow_up_dismissals_out_of_the_onboarding_row(rehearsal):  # noqa: F811
    url = rehearsal.admin
    run(["alembic", "upgrade", "b7e1f3a5c924"], url)
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id, email, auth_provider_id, is_guest, is_admin, token_version, created_at,"
                " career_track) VALUES ('u1', 'moved@example.com', 'password:u1', false, false, 0,"
                " '2026-11-01 10:00:00+00', 'software-engineer')"
            )
        )
        db.execute(
            text(
                "INSERT INTO user_onboarding (user_id, tour_status, tour_step, tour_version, career_intros_seen,"
                " dismissed, updated_at) VALUES ('u1', 'skipped', 0, 1, '[]', :d, '2026-11-14 09:00:00+00')"
            ),
            {"d": json.dumps(["welcome", "problem-follow-up:two-sum>two-sum-sorted"])},
        )
    run(["alembic", "upgrade", "c9a4e2f6d871"], url)
    with engine.connect() as db:
        row = db.execute(text("SELECT key, kind, offered_on, dismissed_at FROM dismissed_suggestions")).one()
        assert row[:3] == (
            "problem-follow-up:two-sum>two-sum-sorted",
            "problem_follow_up",
            "/problems/two-sum",
        )
        assert row[3].isoformat().startswith("2026-11-14T09:00:00")
        kept = db.scalar(text("SELECT dismissed FROM user_onboarding WHERE user_id = 'u1'"))
        assert (json.loads(kept) if isinstance(kept, str) else kept) == ["welcome"]  # the banner stays
    engine.dispose()
    run(["alembic", "downgrade", "b7e1f3a5c924"], url)  # and back: the dismissal returns to the row
    engine = create_engine(url)
    with engine.connect() as db:
        kept = db.scalar(text("SELECT dismissed FROM user_onboarding WHERE user_id = 'u1'"))
        assert (json.loads(kept) if isinstance(kept, str) else kept) == [
            "welcome",
            "problem-follow-up:two-sum>two-sum-sorted",
        ]
    engine.dispose()

"""Passed lesson checks count as new evidence for the plan (Volume 17, prompt 3; docs/PLAN_UPDATES.md,
"What counts as new"). A Learn lesson's check passed since the plan, on the lesson's current version,
is named with its skill in the update's preview, counted in the line ("1 lesson check passed"), and
the next version made from it records it by unit and version; the export carries that record.
Reading a lesson, starting it or a failed check attempt never counts; a pass on a version the lesson
has since replaced is said and not counted; a check that completed one of the plan's own activities
isn't counted twice; another account's checks are never read. Accepted improvements stay beside the
plan (docs/ACCEPTED_ACTIONS.md) and the plan says so. Synthetic data only."""

from __future__ import annotations

import dataclasses

from app.learn import units_for
from app.services import roadmap
from tests.test_disputes import WEAK
from tests.test_learn import right_answers
from tests.test_plan_updates import TRACK, nurse, update
from tests.test_roadmap import answer, plan

SBAR = "rn-sbar-handoff"
HANDOFF_QUESTIONS = ["e-good-7", "e-steps-7"]  # questions on "shift handoffs", the lesson's skill


def weak_handoffs(client, h):
    for qid in HANDOFF_QUESTIONS:
        assert answer(client, h, TRACK, qid, WEAK)["score"] < 70


def check(client, h, unit=SBAR, right=True, version=1):
    answers = right_answers(unit) if right else {}
    r = client.post(
        f"/api/v1/me/learn/units/{unit}/check", headers=h, json={"version": version, "answers": answers}
    )
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is right
    return r.json()


def lesson_suggested(p) -> bool:
    return any(i["kind"] == "learn" and SBAR in (i["href"] or "") for i in p["items"])


def test_a_passed_check_is_named_with_its_skill_and_the_next_version_records_it(client):
    h = nurse(client)
    v1 = plan(client, h)
    assert not lesson_suggested(v1)
    weak_handoffs(client, h)
    check(client, h)
    news = plan(client, h)["news"]
    assert news["lessons"] == 1
    assert "1 lesson check passed" in news["text"]
    [lesson] = [e for e in news["entries"] if e["kind"] == "lesson"]
    unit = next(u for u in units_for(TRACK) if u.id == SBAR)
    assert (lesson["title"], lesson["skill"], lesson["href"]) == (
        unit.title,
        "shift handoffs",
        f"/learn/{SBAR}",
    )
    sentence = next(s["text"] for s in news["by_skill"] if s["skill"] == "shift handoffs")
    assert f"the check passed on the lesson “{unit.title}”" in sentence
    for claim in ("mastered", "improved", "learned"):
        assert claim not in sentence.lower()
    v2 = update(client, h, 1).json()
    assert not lesson_suggested(v2)  # passed: the next version doesn't suggest it
    assert v2["read_lessons"] == [
        {"unit_id": SBAR, "version": 1, "title": unit.title, "href": f"/learn/{SBAR}"}
    ]
    assert (
        v2["changes"][0].startswith("Updated when you asked: ")
        and "1 lesson check passed" in v2["changes"][0]
    )
    exported = client.get("/api/v1/me/export", headers=h).json()
    [row] = [p for p in exported["practice_plans"] if p["version"] == 2]
    assert row["read_lessons"] == [{"unit_id": SBAR, "version": 1}]
    assert v1["read_lessons"] is None  # a version not made by an update reads as before


def test_without_the_check_the_same_answers_bring_the_lesson(client):
    """The control for the test above: the lesson is what the check moved."""
    h = nurse(client)
    plan(client, h)
    weak_handoffs(client, h)
    news = plan(client, h)["news"]
    assert news["lessons"] == 0 and all(e["kind"] != "lesson" for e in news["entries"])
    assert lesson_suggested(update(client, h, 1).json())


def test_reading_starting_or_failing_the_check_is_never_evidence(client):
    h = nurse(client)
    plan(client, h)
    weak_handoffs(client, h)
    for kind in ("started", "read"):
        r = client.post(f"/api/v1/me/learn/units/{SBAR}/events", headers=h, json={"kind": kind, "version": 1})
        assert r.status_code == 200, r.text
    check(client, h, right=False)
    news = plan(client, h)["news"]
    assert news["lessons"] == 0 and "lesson" not in news["text"]
    v2 = update(client, h, 1).json()
    assert lesson_suggested(v2) and v2["read_lessons"] == []


def test_a_pass_on_a_version_the_lesson_has_since_replaced_is_said_not_counted(client, monkeypatch):
    h = nurse(client)
    plan(client, h)
    weak_handoffs(client, h)
    check(client, h)
    revised = [dataclasses.replace(u, version=2) if u.id == SBAR else u for u in units_for(TRACK)]
    monkeypatch.setattr(roadmap, "units_for", lambda track: revised if track == TRACK else units_for(track))
    news = plan(client, h)["news"]
    assert news["lessons"] == 0
    assert news["not_counted"] == [
        "1 lesson check passed on a version the lesson has since replaced isn’t counted: pass its current version."
    ]


def test_a_check_that_completed_one_of_the_plans_activities_isnt_counted_again(client):
    h = nurse(client)
    plan(client, h)
    weak_handoffs(client, h)
    v2 = update(client, h, 1).json()
    assert lesson_suggested(v2)
    check(client, h)  # does the plan's own lesson activity
    seen = plan(client, h)
    # The activity it completed moved the plan on by itself (the plan's own rule for a done activity),
    # so the check isn't new evidence on top of that.
    assert seen["version"] == 3 and not lesson_suggested(seen)
    assert seen["news"] is None or seen["news"]["lessons"] == 0


def test_another_accounts_checks_are_never_read(client):
    h = nurse(client)
    plan(client, h)
    theirs = nurse(client, email="other@example.com")
    check(client, theirs)  # after this account's plan was made
    weak_handoffs(client, h)
    news = plan(client, h)["news"]
    assert news["lessons"] == 0
    assert lesson_suggested(update(client, h, 1).json())


def test_a_new_check_is_left_out_of_the_plan_made_without_the_new_evidence(client):
    """What the planner is given when it plans without what's new: the lesson passed since the plan
    isn't passed there (the planner's one-lesson rule rarely lets that alone change a plan, so this is
    checked where the planner reads it)."""
    from sqlalchemy import select

    from app.models import User
    from app.services.disputes import Disputes
    from app.services.roadmap import Roadmap, _Used

    h = nurse(client)
    plan(client, h)
    check(client, h)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        r = Roadmap(db, judge_enabled=False)
        disputes = Disputes(db, user.id).active(TRACK)
        assert SBAR in r._evidence(user, TRACK, disputes).learn_passed
        out = _Used(set(), set(), set(), {SBAR})
        assert SBAR not in r._evidence(user, TRACK, disputes, out).learn_passed


def test_the_plan_says_what_lessons_and_accepted_improvements_count_for(client):
    h = nurse(client)
    said = plan(client, h)["evidence_read"]
    assert "A lesson only read, or a check not passed, isn't evidence." in said
    assert "Improvements you accept are kept beside the plan and don't change what it suggests" in said

"""A debugging exercise tried and not fixed brings the lesson that prepares it (Volume 18, prompt 7;
docs/PLAN_UPDATES.md, "What the plan suggests"; docs/ATTEMPT_CONDITIONS.md). The lesson "Fixing code
from a failing test" prepares the debugging exercises; when a submission to one of them was judged and
didn't pass, and none since did, the plan suggests the lesson, naming the exercise, unless its check is
passed or another lesson is already suggested (one lesson at a time, as before). A submission the
judge failed to run, or a run (public tests only), isn't an attempt. A fixed exercise doesn't bring it;
another account's never does. The plan reads the code once for this and its coding suggestions.
Verdicts are written as the worker writes them (the judge isn't run here). Synthetic data only."""

from __future__ import annotations

from app.learn import UNIT_INDEX
from app.models import SubmissionStatus
from tests.test_learn import right_answers
from tests.test_plan_code_evidence import LAB, LAB_TITLE, coder, judged, plan

UNIT = "se-failing-test"
TITLE = f"Learn: {UNIT_INDEX[UNIT].title}"


def lesson(p):
    return next((i for i in p["items"] if i["title"] == TITLE), None)


def pass_check(client, h, unit=UNIT):
    r = client.post(
        f"/api/v1/me/learn/units/{unit}/check",
        headers=h,
        json={"version": UNIT_INDEX[unit].version, "answers": right_answers(unit)},
    )
    assert r.status_code == 200 and r.json()["passed"] is True, r.text


def test_an_exercise_tried_and_not_fixed_brings_the_lesson_naming_it(client):
    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    item = lesson(plan(client, h))
    assert item is not None
    assert item["kind"] == "learn" and item["href"] == f"/learn/{UNIT}"
    assert item["reason"] == (
        f"A {UNIT_INDEX[UNIT].minutes}-minute lesson that prepares the debugging exercises, because "
        f"“{LAB_TITLE}” isn't fixed yet. It's a generated draft, not reviewed yet."
    )  # a draft says so (Volume 18, prompt 8)
    assert item["completion"] == "Pass the lesson's comprehension check. Reading it alone doesn't count."
    assert item["skill"] == "debugging exercises"  # not the written-answer skill "debugging"
    # The exercise itself is never suggested: it's evidence, not an activity.
    assert LAB not in str([i["href"] for i in plan(client, h)["items"]])


def test_a_compile_error_is_tried_too(client):
    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.COMPILE_ERROR)
    assert lesson(plan(client, h)) is not None


def test_a_fixed_exercise_doesnt_bring_it(client):
    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    judged(client, h, LAB, SubmissionStatus.PASSED)
    assert lesson(plan(client, h)) is None


def test_a_passed_check_stops_it(client):
    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    pass_check(client, h)
    assert lesson(plan(client, h)) is None


def test_a_judge_failure_or_a_run_isnt_an_attempt(client):
    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.INTERNAL_ERROR)  # the judge's problem, not the code
    judged(client, h, LAB, SubmissionStatus.FAILED, mode="run")  # public tests only
    assert lesson(plan(client, h)) is None


def test_with_no_debugging_attempt_there_is_none(client):
    h = coder(client)
    judged(client, h, "two-sum", SubmissionStatus.FAILED)  # a problem, not a debugging exercise
    assert lesson(plan(client, h)) is None


def test_another_accounts_exercise_never_counts(client):
    theirs = coder(client, "bea@example.com")
    judged(client, theirs, LAB, SubmissionStatus.FAILED)
    assert lesson(plan(client, theirs)) is not None
    h = coder(client)
    assert lesson(plan(client, h)) is None


def test_the_most_recent_exercise_not_fixed_is_named(client):
    h = coder(client)
    judged(client, h, "debug-count-at-most", SubmissionStatus.FAILED, earlier=True)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    assert f"“{LAB_TITLE}” isn't fixed yet" in lesson(plan(client, h))["reason"]


def test_one_lesson_at_a_time(client):
    """A focus skill's lesson comes first; the debugging lesson waits: one lesson at a time."""
    h = coder(client)
    r = client.put("/api/v1/me/goals", headers=h, json={"focus_areas": ["debugging"]})
    assert r.status_code == 200, r.text
    judged(client, h, LAB, SubmissionStatus.FAILED)
    titles = [i["title"] for i in plan(client, h)["items"] if i["kind"] == "learn"]
    assert titles == [f"Learn: {UNIT_INDEX['se-debugging-answers'].title}"]
    pass_check(client, h, "se-debugging-answers")  # that one done: now the debugging lesson
    client.put("/api/v1/me/goals", headers=h, json={"focus_areas": ["debugging"], "weekly_minutes": 90})
    titles = [i["title"] for i in plan(client, h)["items"] if i["kind"] == "learn"]
    assert titles == [TITLE], titles


def test_the_code_is_read_once_for_the_lesson_and_the_coding_suggestions(client, monkeypatch):
    from app.services import progress

    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    real = progress.ProgressService.fact_rows
    reads = {"n": 0}

    def counted(self, *args, **kwargs):
        reads["n"] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(progress.ProgressService, "fact_rows", counted)
    assert lesson(plan(client, h)) is not None  # the first version, made here
    assert reads["n"] == 1, reads  # the lesson and the coding suggestions read the same facts


def skip_all(client, h, p):
    for i in p["items"]:
        if i["status"] == "pending":
            r = client.post(f"/api/v1/me/plan/items/{i['id']}/skip", headers=h)
            assert r.status_code == 200, r.text
    return plan(client, h)


def test_a_skipped_lesson_isnt_suggested_again_for_a_week(client):
    """As a skipped question or problem isn't (Volume 18, prompt 7): before, the next version brought
    it straight back."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.models import PlanItem

    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    v1 = plan(client, h)
    assert lesson(v1) is not None
    v2 = skip_all(client, h, v1)
    assert v2["version"] == 2 and lesson(v2) is None
    with client.app.state.session_factory() as db:  # as if skipped eight days ago
        db.execute(
            update(PlanItem)
            .where(PlanItem.status == "skipped")
            .values(resolved_at=datetime.now(UTC) - timedelta(days=8))
        )
        db.commit()
    v3 = skip_all(client, h, v2)
    assert v3["version"] == 3 and lesson(v3) is not None


def test_a_skipped_focus_lesson_makes_way_for_the_debugging_lesson(client):
    h = coder(client)
    assert client.put("/api/v1/me/goals", headers=h, json={"focus_areas": ["debugging"]}).status_code == 200
    judged(client, h, LAB, SubmissionStatus.FAILED)
    v1 = plan(client, h)
    assert [i["title"] for i in v1["items"] if i["kind"] == "learn"] == [
        f"Learn: {UNIT_INDEX['se-debugging-answers'].title}"
    ]
    v2 = skip_all(client, h, v1)
    assert [i["title"] for i in v2["items"] if i["kind"] == "learn"] == [TITLE]

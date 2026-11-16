"""Judged code as new evidence for the plan (Volume 16, prompt 7; docs/PLAN_UPDATES.md): submissions
(submit, not run) to problems and debugging exercises since the plan's version count for the skills
they practise, and the preview names them, grouped by skill, one sentence each saying what the next
version would suggest or stop suggesting and why; a verdict is said as a verdict, never a score, with
the rule said; a submission the judge failed to run isn't counted, and is said; accepting makes the
next version as before and records the submissions it read, by id, which the export lists; not
accepting changes nothing; versions from before read exactly as they did. One career's evidence
never counts toward another's; another account's never counts. Verdicts are written as the worker
writes them (the judge isn't run here). Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import PracticePlan, Problem, Submission, SubmissionMode, SubmissionStatus
from app.services import roadmap
from tests.conftest import auth_headers, register
from tests.test_disputes import WEAK
from tests.test_plan_updates import outside
from tests.test_roadmap import answer
from tests.test_submission_comparisons import judge

TRACK = "software-engineer"
CODE = "class Solution {}"
LAB = "debug-coldest-day"
LAB_TITLE = "Fix: Coldest Reading"


def coder(client, email="ada@example.com", track=TRACK):
    return auth_headers(register(client, email=email, career_track=track))


def submit(client, h, slug, mode="submit"):
    if mode == "run":  # runs need the judge here; stored as the route stores one
        with client.app.state.session_factory() as db:
            me = client.get("/api/v1/auth/me", headers=h).json()["id"]
            pid = db.scalar(select(Problem.id).where(Problem.slug == slug))
            run = Submission(
                user_id=me, problem_id=pid, source_code=CODE, mode=SubmissionMode.RUN, content_version=1
            )
            db.add(run)
            db.commit()
            return run.id
    r = client.post(
        "/api/v1/submissions",
        headers=h,
        json={"problem_slug": slug, "language": "java", "source_code": CODE, "mode": mode},
    )
    assert r.status_code == 202, r.text
    return r.json()["id"]


def judged(client, h, slug, status, mode="submit", earlier=False):
    sid = submit(client, h, slug, mode)
    judge(client, sid, status, 7 if status == SubmissionStatus.PASSED else 1)
    if earlier:  # made well before the plan's version
        with client.app.state.session_factory() as db:
            db.execute(
                update(Submission)
                .where(Submission.id == sid)
                .values(created_at=datetime.now(UTC) - timedelta(hours=1))
            )
            db.commit()
    return sid


def plan(client, h, track=None):
    r = client.get("/api/v1/me/plan", headers=h, params={"track": track} if track else {})
    assert r.status_code == 200, r.text
    return r.json()


def accept(client, h, version, track=None):
    r = client.post("/api/v1/me/plan/update", headers=h, json={"version": version, "track": track})
    assert r.status_code == 200, r.text
    return r.json()


def exported(client, h):
    r = client.get("/api/v1/me/export", headers=h, params={"version": 2})
    assert r.status_code == 200, r.text
    return r.json()["practice_plans"]


def two_sum_unfinished(client, h):
    """Two Sum failed before the plan: version 1 suggests finishing it, and Find Largest Number."""
    judged(client, h, "two-sum", SubmissionStatus.FAILED, earlier=True)
    v1 = plan(client, h)
    coding = [i["title"] for i in v1["items"] if i["kind"] == "coding"]
    assert coding == ["Solve: Two Sum", "Solve: Find Largest Number"], coding
    return v1


def test_a_passed_submission_after_the_version_is_named_and_moves_its_skill(client):
    h = coder(client)
    two_sum_unfinished(client, h)
    sid = judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    news = plan(client, h)["news"]
    assert news is not None and news["text"] == "1 submission (passed) since this plan."
    [entry] = news["entries"]
    assert entry == {
        "kind": "submission",
        "title": "Contains Duplicate",
        "score": None,  # a verdict is never re-read as a score
        "verdict": "passed",
        "verdict_detail": "passed",
        "exercise": False,
        "skill": "arrays",
        "href": f"/history/submissions/{sid}",
    }
    assert news["by_skill"] == [
        {
            "skill": "arrays",
            "count": 1,
            "text": "Arrays: “Contains Duplicate” passed, which counts as solved, so the next version would "
            "suggest “Solve: First Unique Character” and not “Solve: Find Largest Number”.",
        }
    ]
    assert news["rule"] == roadmap.CODE_RULE
    assert "/100" not in str(news["by_skill"]) and "score" not in news["rule"].replace("a score", "")


def test_each_skill_gets_one_sentence_and_a_failed_verdict_is_said_in_the_judges_terms(client):
    h = coder(client)
    two_sum_unfinished(client, h)
    judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    judged(client, h, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)
    news = plan(client, h)["news"]
    assert news["text"] == "2 submissions (1 not passed) since this plan."
    assert [e["verdict_detail"] for e in news["entries"]] == ["passed", "compile error"]
    assert [(g["skill"], g["text"]) for g in news["by_skill"]] == [
        (
            "arrays",
            "Arrays: “Contains Duplicate” passed, which counts as solved, so the next version wouldn't "
            "suggest “Solve: Find Largest Number”.",
        ),
        (
            "strings",
            "Strings: “Valid Parentheses” didn't pass (compile error), which counts as tried, not solved, "
            "so the next version would suggest “Solve: Valid Parentheses”.",
        ),
    ]
    assert all(g["text"].count(".") == 1 for g in news["by_skill"])  # one sentence each


def test_a_run_doesnt_count(client):
    h = coder(client)
    two_sum_unfinished(client, h)
    run = judged(client, h, "contains-duplicate", SubmissionStatus.PASSED, mode="run")
    assert plan(client, h)["news"] is None  # public tests only: not evidence
    sid = judged(client, h, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)
    news = plan(client, h)["news"]
    assert [e["href"] for e in news["entries"]] == [f"/history/submissions/{sid}"]
    assert run not in str(news)


def test_a_debugging_exercise_counts_for_the_skills_it_names(client):
    h = coder(client)
    # Two easy arrays problems solved before the plan: arrays isn't weak, so the plan climbs the ladder.
    judged(client, h, "find-largest-number", SubmissionStatus.PASSED, earlier=True)
    judged(client, h, "two-sum", SubmissionStatus.PASSED, earlier=True)
    v1 = plan(client, h)
    assert [i["title"] for i in v1["items"] if i["kind"] == "coding"] == [
        "Solve: Reverse a String",
        "Solve: Valid Palindrome",
    ]
    sid = judged(client, h, LAB, SubmissionStatus.FAILED)
    news = plan(client, h)["news"]
    assert news["text"] == "1 submission (not passed) since this plan."
    [entry] = news["entries"]
    assert (entry["exercise"], entry["skill"], entry["verdict_detail"]) == (True, "arrays", "tests failed")
    assert entry["href"] == f"/history/submissions/{sid}"
    assert news["by_skill"][0]["text"] == (
        f"Arrays: the debugging exercise “{LAB_TITLE}” didn't pass (tests failed), which counts as tried, "
        "not solved, so the next version would suggest “Solve: Contains Duplicate” and not "
        "“Solve: Valid Palindrome”."
    )
    # The exercise itself is never suggested: it's evidence for its skills, not an activity.
    v2 = accept(client, h, 1)
    assert LAB not in str([i["href"] for i in v2["items"]])
    assert "Solve: Contains Duplicate" in [i["title"] for i in v2["items"]]


def test_an_exercise_passed_after_the_version_counts_as_solved(client):
    h = coder(client)
    judged(client, h, "find-largest-number", SubmissionStatus.PASSED, earlier=True)
    judged(client, h, "two-sum", SubmissionStatus.PASSED, earlier=True)
    judged(client, h, LAB, SubmissionStatus.FAILED, earlier=True)
    v1 = plan(client, h)
    # Arrays is weak: the exercise failed.
    assert "Solve: Contains Duplicate" in [i["title"] for i in v1["items"]]
    judged(client, h, LAB, SubmissionStatus.PASSED)
    [group] = plan(client, h)["news"]["by_skill"]
    assert group["text"] == (
        f"Arrays: the debugging exercise “{LAB_TITLE}” passed, which counts as solved, so the next version "
        "would suggest “Solve: Valid Palindrome” and not “Solve: Contains Duplicate”."
    )


def test_a_submission_the_judge_couldnt_run_isnt_counted_and_is_said(client):
    h = coder(client)
    # Before the plan, too: not read as an attempt (version 1 doesn't ask to finish it).
    judged(client, h, "contains-duplicate", SubmissionStatus.INTERNAL_ERROR, earlier=True)
    v1 = two_sum_unfinished(client, h)
    broken = judged(client, h, "contains-duplicate", SubmissionStatus.INTERNAL_ERROR)
    assert plan(client, h)["news"] is None  # on its own: nothing to offer
    # Nor does it complete the activity it was for: the judge's failure isn't an attempt judged.
    judged(client, h, "find-largest-number", SubmissionStatus.INTERNAL_ERROR)
    seen = plan(client, h)
    assert seen["version"] == 1
    assert next(i for i in seen["items"] if i["title"] == "Solve: Find Largest Number")["status"] == "pending"
    sid = judged(client, h, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)
    news = plan(client, h)["news"]
    assert news["submissions"] == 1 and [e["href"] for e in news["entries"]] == [
        f"/history/submissions/{sid}"
    ]
    assert news["not_counted"] == [
        "2 submissions the judge couldn't run aren’t counted: that was a problem on the judge's side, not your code."
    ]
    assert broken not in str(news) and v1["version"] == 1
    v2 = accept(client, h, 1)
    assert [r["id"] for r in v2["read_submissions"]] == [sid]


def test_accepting_records_what_it_read_by_id_and_the_export_lists_it(client):
    h = coder(client)
    two_sum_unfinished(client, h)
    passed = judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    failed = judged(client, h, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)
    v2 = accept(client, h, 1)
    assert v2["version"] == 2 and v2["news"] is None
    assert v2["changes"][0] == "Updated when you asked: 2 submissions (1 not passed) since version 1."
    assert v2["read_submissions"] == [
        {
            "id": passed,
            "title": "Contains Duplicate",
            "verdict": "passed",
            "exercise": False,
            "href": f"/history/submissions/{passed}",
        },
        {
            "id": failed,
            "title": "Valid Parentheses",
            "verdict": "not passed",
            "exercise": False,
            "href": f"/history/submissions/{failed}",
        },
    ]
    assert plan(client, h)["read_submissions"] == v2["read_submissions"]  # kept with the version
    rows = {p["version"]: p for p in exported(client, h)}
    assert rows[1]["read_submissions"] is None and rows[2]["read_submissions"] == [passed, failed]
    # A version made otherwise (an activity done, read on the next view) cites nothing.
    judged(client, h, "valid-parentheses", SubmissionStatus.PASSED)
    v3 = plan(client, h)
    assert v3["version"] == 3 and v3["read_submissions"] is None


def test_not_accepting_changes_nothing_and_nothing_is_applied_later(client):
    h = coder(client)
    v1 = two_sum_unfinished(client, h)
    judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    for _ in range(3):  # reloads, and the next visit
        seen = plan(client, h)
        assert seen["version"] == 1 and seen["items"] == v1["items"] and seen["news"] is not None
    with client.app.state.session_factory() as db:
        assert db.scalars(select(PracticePlan.version)).all() == [1]


def test_a_version_from_before_reads_exactly_as_it_did(client):
    h = coder(client)
    two_sum_unfinished(client, h)
    judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    v2 = accept(client, h, 1)
    with client.app.state.session_factory() as db:  # as an update stored it before this release
        db.execute(update(PracticePlan).where(PracticePlan.version == 2).values(read_submissions=None))
        db.commit()
    before = plan(client, h)
    assert before["read_submissions"] is None
    assert {k: v for k, v in before.items() if k != "read_submissions"} == {
        k: v for k, v in v2.items() if k != "read_submissions"
    }
    assert exported(client, h)[1]["read_submissions"] is None


def test_another_careers_plan_never_reads_code(client):
    h = coder(client, track="registered-nurse")
    v1 = plan(client, h)
    assert "judge" not in v1["evidence_read"] and "code" not in v1["evidence_read"]
    [qid] = outside(v1)
    answer(client, h, "registered-nurse", qid, WEAK)
    judged(client, h, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)
    news = plan(client, h)["news"]
    assert news["text"] == "1 answer since this plan, below 70."
    assert news["submissions"] == 0 and [e["kind"] for e in news["entries"]] == ["answer"]
    assert news["rule"] is None and all(g["skill"] != "strings" for g in news["by_skill"])
    assert accept(client, h, 1)["read_submissions"] == []  # an update that read no code


def test_another_accounts_submissions_never_count(client):
    theirs = coder(client, email="bea@example.com")
    h = coder(client)
    two_sum_unfinished(client, h)
    judged(client, theirs, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)
    assert plan(client, h)["news"] is None
    mine = judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    news = plan(client, h)["news"]
    assert news["text"] == "1 submission (passed) since this plan."
    assert [e["href"] for e in news["entries"]] == [f"/history/submissions/{mine}"]
    assert [r["id"] for r in accept(client, h, 1)["read_submissions"]] == [mine]


def test_the_plan_says_which_evidence_it_reads(client):
    h = coder(client)
    said = plan(client, h)["evidence_read"]
    assert said == (
        "This plan reads your scored answers to Software Engineer questions, your finished question rounds "
        "and the lesson checks you've passed, and the judge's verdicts on code you submit: to problems, and "
        "to debugging exercises for the skills they name (not runs, which check the public tests only). "
        # Since Volume 17, prompt 3: what a lesson and an accepted improvement count for.
        "A lesson only read, or a check not passed, isn't evidence. Improvements you accept are kept beside "
        "the plan and don't change what it suggests; the practice they lead to does."
    )


def test_a_problem_tried_twice_is_named_once_with_its_attempts_in_order():
    p = roadmap._Piece
    tries = [
        p("submission", "Two Sum", passed=False, verdict="tests failed"),
        p("submission", "Two Sum", passed=True),
    ]
    assert roadmap._skill_sentence("arrays", tries, [], []) == (
        "Arrays: “Two Sum” didn't pass (tests failed), then passed: a pass counts as solved, the rest as tried; "
        "on its own that changes nothing the plan chooses."
    )


def test_the_skill_sentence_counts_many_and_names_few():
    p = roadmap._Piece
    spec = roadmap.Spec("coding", "arrays", "Solve: Two Sum", "", "", 15, {"problem_slug": "two-sum"})
    many = [
        p("submission", f"P{i}", passed=i == 0, verdict="passed" if i == 0 else "tests failed")
        for i in range(4)
    ]
    assert roadmap._skill_sentence("arrays", many, [spec], []) == (
        "Arrays: 4 submissions, 1 of them passed: a pass counts as solved, the rest as tried, so the next "
        "version would suggest “Solve: Two Sum”."
    )
    assert roadmap._skill_sentence("Triage", [p("answer", "Q", score=55)], [], []) == (
        "Triage: “Q” scored 55/100; on its own that changes nothing the plan chooses."
    )

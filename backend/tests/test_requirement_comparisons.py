"""A requirement's code, compared (Volume 16, prompt 9; docs/COMPARING_ATTEMPTS.md): each submission a
target's requirement lists shows its verdict, its result and the contract's one-line outcome against
the one before it, the same comparison its own page shows; the first says it's the first; one the
contract couldn't set beside the one before says so in the contract's words; the requirement says
how many were compared and how many weren't, and why; the coverage line counts as before; reading
the target doesn't grow with the number of submissions, and a problem two requirements share is
compared once; the export carries each listed submission's outcome by id. Runs and another account's
submissions never appear. Verdicts are written as the worker writes them. Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import Problem, Submission, SubmissionMode, SubmissionStatus, TestCase, User
from tests.test_coding_practice_links import JD, coder, submit
from tests.test_submission_comparisons import BETTER, CODE, judge

REQ = "Strong knowledge of data structures and algorithms"
TWO = """Software Engineer
Requirements:
- Strong knowledge of data structures and algorithms
- Strong problem-solving skills
"""


def target(client, h, description=JD):
    r = client.post(
        "/api/v1/targets", headers=h, json={"title": "Backend engineer", "description": description}
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def requirement(client, h, tid, text=REQ):
    t = client.get(f"/api/v1/targets/{tid}", headers=h).json()
    return next(r for r in t["requirement_list"] if r["text"] == text)


def page(client, h, sid):
    r = client.get(f"/api/v1/submissions/{sid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def failed_then_passed(client, h):
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    return first, second


def test_a_failed_then_passed_submission_is_compared_with_the_rule_and_the_first_says_its_first(client):
    h = coder(client)
    tid = target(client, h)
    first, second = failed_then_passed(client, h)
    req = requirement(client, h, tid)
    newer, older = req["submissions"]
    assert (newer["submission_id"], older["submission_id"]) == (second, first)
    assert (newer["status"], newer["passed_count"], newer["total_count"]) == ("PASSED", 7, 7)
    assert newer["outcome_text"] == "Comparable with the one before"
    c = newer["compared"]
    assert c["previous"]["id"] == first and c["previous"]["status"] == "FAILED"
    assert (c["previous"]["passed_count"], c["previous"]["total_count"]) == (2, 7)
    assert c["comparison"]["outcome"] == "comparable" and c["comparison"]["scores_comparable"] is True
    assert c["comparison"]["explanation"]  # the rule, as the contract says it
    # The same comparison its own page shows, word for word.
    assert c == page(client, h, second)["compared"]
    assert older["compared"] is None
    assert older["outcome_text"] == "Not compared: the first judged submission of this problem"
    assert req["comparisons"] == (
        "1 compared with the one before; 1 not compared: the first judged submission of its problem."
    )
    for claim in ("improved", "better", "mastered", "worse"):
        assert claim not in str(req).lower()


def test_each_listed_submission_says_its_hidden_tests_as_its_own_page_does(client):
    """Volume 17, prompt 10: beside the total, the hidden tests, by the rule its own page reads them with."""
    h = coder(client)
    tid = target(client, h)
    failed_then_passed(client, h)
    listed = requirement(client, h, tid)["submissions"]
    assert len(listed) == 2
    for item in listed:
        result = page(client, h, item["submission_id"])["result"]
        assert (item["passed_count"], item["total_count"]) == (result["passed_count"], result["total_count"])
        assert (item["hidden_passed"], item["hidden_total"]) == (
            result["hidden_passed"],
            result["hidden_total"],
        )
        assert item["hidden_total"] > 0


def test_the_coverage_line_counts_as_before(client):
    """Comparisons add a line beside the coverage; the coverage itself counts practice as it did (the
    same level, label and counts as a target page read before comparisons were added)."""
    h = coder(client)
    tid = target(client, h)
    failed_then_passed(client, h)
    req = requirement(client, h, tid)
    assert req["coverage"] == {
        "level": "some",
        "label": "Some practice",
        "answers": 0,
        "questions_answered": 0,
        "average_best_score": None,
        "judged_attempts": 2,
        "passed": 1,
    }
    assert "compared" not in req["coverage"]["label"] and req["comparisons"].startswith("1 compared")


def test_a_run_never_appears(client):
    h = coder(client)
    tid = target(client, h)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        run = Submission(
            user_id=user.id, problem_id=pid, source_code=CODE, mode=SubmissionMode.RUN, content_version=1
        )
        db.add(run)
        db.commit()
        run_id = run.id
    judge(client, run_id, SubmissionStatus.PASSED, 3, 3)
    req = requirement(client, h, tid)
    assert req["submissions"] == [] and req["comparisons"] is None
    sid = submit(client, h)
    judge(client, sid, SubmissionStatus.FAILED, 2)
    req = requirement(client, h, tid)
    assert [s["submission_id"] for s in req["submissions"]] == [sid]
    assert req["submissions"][0]["compared"] is None  # never compared with the run


def test_one_the_contract_cant_set_beside_the_one_before_says_so_in_its_words(client):
    h = coder(client)
    tid = target(client, h)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    with client.app.state.session_factory() as db:  # its tests' version wasn't recorded; the tests changed
        db.execute(update(Submission).where(Submission.id == first).values(content_version=None))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    req = requirement(client, h, tid)
    newer = req["submissions"][0]
    assert newer["outcome_text"] == "Can't tell whether it compares with the one before"
    reason = next(r["text"] for r in newer["compared"]["comparison"]["reasons"] if r["kind"] == "unknown")
    assert req["comparisons"] == (
        f"2 not compared: {reason.rstrip('.')}; the first judged submission of its problem."
    )
    assert newer["compared"] == page(client, h, second)["compared"]


def test_two_requirements_sharing_a_problem_show_the_same_comparison_read_once(client):
    from tests.test_query_budgets import statements

    h = coder(client)
    one, two = target(client, h), target(client, h, TWO)
    first, second = failed_then_passed(client, h)
    a = requirement(client, h, two)
    b = requirement(client, h, two, "Strong problem-solving skills")
    assert [s["submission_id"] for s in b["submissions"]] == [second, first]
    assert a["submissions"] == b["submissions"] == requirement(client, h, one)["submissions"]

    def reads(tid):
        with statements(client) as seen:
            client.get(f"/api/v1/targets/{tid}", headers=h)
        return [s for s in seen if "FROM submissions" in s and "submissions.problem_id IN" in s]

    assert len(reads(two)) == len(reads(one))  # two requirements, the same reads as one


def test_reading_the_target_doesnt_grow_with_the_number_of_submissions(client):
    from tests.test_query_budgets import statements

    h = coder(client)
    tid = target(client, h, TWO)
    failed_then_passed(client, h)
    failed_then_passed(client, h)  # four: one earlier than the three listed
    with statements(client) as seen:
        client.get(f"/api/v1/targets/{tid}", headers=h)
    few = len(seen)
    with client.app.state.session_factory() as db:  # forty more, written as the API writes them
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        start = datetime.now(UTC)
        for n, slug in enumerate(
            ["two-sum", "contains-duplicate", "valid-parentheses", "reverse-string"] * 10
        ):
            pid = db.scalar(select(Problem.id).where(Problem.slug == slug))
            db.add(
                Submission(
                    user_id=user.id,
                    problem_id=pid,
                    source_code=CODE,
                    content_version=1,
                    created_at=start + timedelta(seconds=n),
                )
            )
        db.commit()
        ids = db.scalars(select(Submission.id).where(Submission.status == SubmissionStatus.QUEUED)).all()
    for n, sid in enumerate(ids):
        judge(client, sid, SubmissionStatus.FAILED if n % 3 else SubmissionStatus.PASSED, 3)
    with statements(client) as seen:
        r = client.get(f"/api/v1/targets/{tid}", headers=h)
    assert r.status_code == 200
    assert len(seen) == few, (few, len(seen))
    assert all(len(x["submissions"]) <= 3 for x in r.json()["requirement_list"])


def test_another_accounts_submissions_never_appear(client):
    theirs = coder(client, email="other@example.com")
    t = submit(client, theirs)
    judge(client, t, SubmissionStatus.PASSED, 7)
    h = coder(client)
    tid = target(client, h)
    assert requirement(client, h, tid)["submissions"] == []
    mine = submit(client, h)
    judge(client, mine, SubmissionStatus.FAILED, 2)
    [only] = requirement(client, h, tid)["submissions"]
    assert only["submission_id"] == mine and only["compared"] is None  # never compared with theirs


def test_the_export_carries_each_listed_submissions_outcome_by_id(client):
    h = coder(client)
    tid = target(client, h)
    first, second = failed_then_passed(client, h)
    doc = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    [t] = [x for x in doc["target_roles"] if x["id"] == tid]
    req = next(r for r in t["requirements"] if r["text"] == REQ)
    assert req["submissions"] == [
        {
            "id": second,
            "status": "PASSED",
            "comparison": "comparable",
            "compared_with": first,
            "outcome": "Comparable with the one before",
        },
        {
            "id": first,
            "status": "FAILED",
            "comparison": None,
            "compared_with": None,
            "outcome": "Not compared: the first judged submission of this problem",
        },
    ]

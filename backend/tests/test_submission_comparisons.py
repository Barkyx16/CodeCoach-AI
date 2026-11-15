"""A coding submission beside the previous judged one of the same problem and mode (Volume 14, prompt
1; docs/COMPARING_ATTEMPTS.md, "Coding submissions"): the one comparison contract, with code's facts.
Both verdicts are kept as judged; nothing says one improved on the other. The judge isn't run here:
verdicts are written as the worker writes them. Synthetic data only."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.careers.comparability import AttemptFacts, classify
from app.models import ExecutionResult, Problem, Submission, SubmissionMode, SubmissionStatus, TestCase, User
from tests.conftest import auth_headers, register

CODE = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[0]; } }"
BETTER = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[] {0, 1}; } }"


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def hint(client, h, level=1):
    r = client.post(
        "/api/v1/ai/hint", headers=h, json={"problem_slug": "two-sum", "level": level, "source_code": CODE}
    )
    assert r.status_code == 200, r.text


def submit(client, h, code=CODE):
    r = client.post("/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": code})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def judge(client, sub_id, status, passed=0, total=7):
    """As the worker records a verdict: the status, and the result for a verdict on the code."""
    with client.app.state.session_factory() as db:
        sub = db.get(Submission, sub_id)
        sub.status = status
        sub.judged_at = datetime.now(UTC)
        if status != SubmissionStatus.INTERNAL_ERROR:
            db.add(
                ExecutionResult(
                    submission_id=sub_id, passed_count=passed, total_count=total, public_results=[]
                )
            )
        db.commit()


def detail(client, h, sub_id):
    r = client.get(f"/api/v1/submissions/{sub_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_same_tests_and_help_compare_and_both_verdicts_are_kept(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)

    got = detail(client, h, second)["compared"]
    assert got["previous"] == {
        **got["previous"],
        "id": first,
        "status": "FAILED",
        "passed_count": 2,
        "total_count": 7,
    }
    c = got["comparison"]
    assert c["against"] == first and c["outcome"] == "comparable" and c["scores_comparable"]
    assert c["explanation"].startswith(
        "Comparable: the same problem and tests, judged the same way, with the same in-app help"
    )
    assert c["contract_version"] == 1
    for word in ("improv", "better", "average"):
        assert word not in c["explanation"].lower()
    # The earlier one has nothing before it, and its own verdict is untouched.
    first_detail = detail(client, h, first)
    assert first_detail["compared"] is None and first_detail["status"] == "FAILED"


def test_a_hint_before_one_of_them_makes_them_partly_comparable_with_both_counts_shown(client):
    h = coder(client)
    hint(client, h)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    c = detail(client, h, second)["compared"]["comparison"]
    assert c["outcome"] == "partially_comparable" and c["scores_comparable"] and c["points_comparable"]
    assert [r["rule"] for r in c["reasons"]] == ["help"]
    assert (
        "before the earlier one, hint shown; before the later one, none recorded" in c["reasons"][0]["text"]
    )
    assert "The counts are from the same tests, so both are shown" in c["explanation"]


def test_new_tests_in_between_compare_the_code_not_the_counts(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    with client.app.state.session_factory() as db:
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    c = detail(client, h, second)["compared"]["comparison"]
    assert c["outcome"] == "partially_comparable" and not c["scores_comparable"]
    assert c["reasons"][0]["text"] == (
        "the problem's tests changed in between (version 1, now 2): compare the code, not the counts"
    )


def test_a_test_version_that_wasnt_recorded_says_so_on_a_revised_problem(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    with client.app.state.session_factory() as db:
        db.execute(update(Submission).where(Submission.id == first).values(content_version=None))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    c = detail(client, h, second)["compared"]["comparison"]
    assert c["outcome"] == "unknown"
    assert "which version of the problem's tests judged one of them wasn't recorded" in c["explanation"]


def test_the_judges_own_failure_isnt_a_verdict_and_is_never_the_previous_one(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    broken = submit(client, h, BETTER)
    judge(client, broken, SubmissionStatus.INTERNAL_ERROR)
    c = detail(client, h, broken)["compared"]["comparison"]
    assert c["outcome"] == "incompatible" and not c["scores_comparable"]
    assert "this one wasn't judged, so there's no verdict to set beside the other" in c["explanation"]
    third = submit(client, h, BETTER + " ")
    judge(client, third, SubmissionStatus.PASSED, 7)
    assert detail(client, h, third)["compared"]["previous"]["id"] == first  # not the one the judge failed


def test_one_still_being_judged_isnt_compared_yet(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    waiting = submit(client, h, BETTER)
    assert detail(client, h, waiting)["compared"] is None


def test_a_run_is_compared_only_with_runs(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        now = datetime.now(UTC)
        runs = [
            Submission(
                user_id=user.id,
                problem_id=pid,
                source_code=CODE,
                mode=SubmissionMode.RUN,
                content_version=1,
                created_at=now + timedelta(seconds=i + 1),
            )
            for i in range(2)
        ]
        db.add_all(runs)
        db.commit()
        run_ids = [r.id for r in runs]
    for rid in run_ids:
        judge(client, rid, SubmissionStatus.PASSED, 3, 3)
    assert detail(client, h, run_ids[0])["compared"] is None  # the submission before it isn't a run
    assert detail(client, h, run_ids[1])["compared"]["previous"]["id"] == run_ids[0]


def test_a_run_and_a_submission_never_compare_by_the_contract():
    def facts(i, fmt):
        return AttemptFacts(
            id=i,
            track="code",
            question_id="1",
            question_version=1,
            scale="tests passed",
            rubric="the problem's tests",
            source="judge",
            scoring="scored",
            format=fmt,
            help=("No in-app help recorded",),
            kind="code",
        )

    c = classify(facts("a", "run"), facts("b", "submit"))
    assert c.outcome == "incompatible"
    assert c.reasons[0].text == "a run checks the public tests only and a submission checks every test"


def test_another_accounts_submissions_are_never_the_previous_one(client):
    theirs = coder(client, email="other@example.com")
    t = submit(client, theirs)
    judge(client, t, SubmissionStatus.FAILED, 2)
    mine = coder(client)
    m = submit(client, mine)
    judge(client, m, SubmissionStatus.PASSED, 7)
    assert detail(client, mine, m)["compared"] is None
    assert client.get(f"/api/v1/submissions/{t}", headers=mine).status_code == 404


def test_history_rows_and_the_export_carry_the_same_comparison(client):
    h = coder(client)
    hint(client, h)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    items = client.get("/api/v1/me/activity", headers=h, params={"type": "code_submission"}).json()["items"]
    detail_of = {i["target"]["submission_id"]: i["detail"] for i in items}
    assert detail_of == {second: "Partly comparable with the one before", first: None}
    doc = client.get("/api/v1/me/export", headers=h).json()
    exported = {s["id"]: s["comparison"] for s in doc["submissions"]}
    assert exported[first] is None
    assert exported[second]["against"] == first and exported[second]["outcome"] == "partially_comparable"
    assert (
        exported[second]["explanation"] == detail(client, h, second)["compared"]["comparison"]["explanation"]
    )


def test_history_compares_a_page_of_submissions_in_a_fixed_number_of_statements(client):
    """No N+1: the comparisons for a page of rows are worked out together."""
    from tests.test_query_budgets import statements

    def page_statements(h, n):
        # Written as the API writes them (the submit endpoint allows six a minute).
        with client.app.state.session_factory() as db:
            user = db.scalar(select(User).order_by(User.created_at.desc()))
            pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
            start = datetime.now(UTC)
            rows = [Submission(user_id=user.id, problem_id=pid, source_code=CODE, content_version=1,
                               created_at=start + timedelta(seconds=i)) for i in range(n)]
            db.add_all(rows)
            db.commit()
            ids = [r.id for r in rows]
        for i, sid in enumerate(ids):
            judge(client, sid, SubmissionStatus.FAILED if i % 2 else SubmissionStatus.PASSED, 3)
        with statements(client) as seen:
            r = client.get("/api/v1/me/activity", headers=h, params={"type": "code_submission", "page_size": 20})
        assert r.status_code == 200 and len(r.json()["items"]) == n
        return len(seen)

    few = page_statements(coder(client, email="few@example.com"), 3)
    many = page_statements(coder(client, email="many@example.com"), 12)
    assert many == few

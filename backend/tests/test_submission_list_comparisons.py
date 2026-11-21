"""Your submissions list says how each compares with the one before (Volume 16, after prompt 9;
docs/COMPARING_ATTEMPTS.md): the contract's outcome in History's words, the first judged one says it's
the first, one still being judged or that the judge couldn't run says nothing; the page's rows are
compared together, so its statements don't grow with the number of submissions. The dashboard's
"Recent attempts" reads this list. Verdicts are written as the worker writes them. Synthetic data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Problem, Submission, SubmissionMode, SubmissionStatus, User
from tests.test_coding_practice_links import coder, submit
from tests.test_submission_comparisons import BETTER, CODE, judge

MINE = "/api/v1/me/submissions"


def listed(client, h, **params):
    r = client.get(MINE, headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_each_row_says_how_it_compares_in_historys_words(client):
    h = coder(client)
    first = submit(client, h)
    judge(client, first, SubmissionStatus.FAILED, 2)
    second = submit(client, h, BETTER)
    judge(client, second, SubmissionStatus.PASSED, 7)
    waiting = submit(client, h, BETTER + " ")
    rows = {r["id"]: r["outcome_text"] for r in listed(client, h)}
    assert rows == {
        waiting: None,  # still being judged: nothing to compare yet
        second: "Comparable with the one before",
        first: "Not compared: the first judged submission of this problem",
    }
    history = client.get("/api/v1/me/activity", headers=h, params={"type": "code_submission"}).json()["items"]
    row = next(i for i in history if i["target"]["submission_id"] == second)
    assert row["detail"] == rows[second]  # the same words as History


def test_the_judges_own_failure_says_nothing_and_a_first_run_says_its_first(client):
    h = coder(client)
    broken = submit(client, h)
    judge(client, broken, SubmissionStatus.INTERNAL_ERROR)
    assert listed(client, h)[0]["outcome_text"] is None
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
    [only] = listed(client, h, mode="run")
    assert only["outcome_text"] == "Not compared: the first judged run of this problem"


def test_a_page_of_rows_is_compared_in_a_fixed_number_of_statements(client):
    from tests.test_query_budgets import statements

    h = coder(client)

    def add(n):
        with client.app.state.session_factory() as db:
            user = db.scalar(select(User).where(User.email == "ada@example.com"))
            pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
            start = datetime.now(UTC) + timedelta(minutes=len(db.scalars(select(Submission.id)).all()))
            rows = [
                Submission(
                    user_id=user.id,
                    problem_id=pid,
                    source_code=CODE,
                    content_version=1,
                    created_at=start + timedelta(seconds=i),
                )
                for i in range(n)
            ]
            db.add_all(rows)
            db.commit()
            ids = [r.id for r in rows]
        for i, sid in enumerate(ids):
            judge(client, sid, SubmissionStatus.FAILED if i % 2 else SubmissionStatus.PASSED, 3)

    add(2)
    with statements(client) as seen:
        listed(client, h, page_size=20)
    few = len(seen)
    add(18)
    with statements(client) as seen:
        rows = listed(client, h, page_size=20)
    assert len(rows) == 20 and all(r["outcome_text"] for r in rows)
    assert len(seen) == few, (few, len(seen))

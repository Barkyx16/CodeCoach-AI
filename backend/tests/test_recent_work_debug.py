"""Debugging exercises tried and not fixed, and a scenario run's last step, in Continue your work
(Volume 20, prompt 6; docs/CONTINUE.md). An exercise none of whose submitted attempts passed (the
plan's rule for "not fixed"), with its newest attempt in the last week, is listed as "tried" at that
attempt's time, its verdict in the exercise page's words; Resume opens the exercise. One fixed, or
whose newest attempt is more than a week old, drops out. A scenario run in progress is listed at its
last step's time (its start when it has none) and says which. Both only for a page that says it can
show them: one that doesn't gets what it did. Only titles, verdicts and times are read, never code.
Verdicts are written as the worker writes them (the judge isn't run here). Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import event, update

from app.models import ScenarioAttempt, Submission, SubmissionStatus
from app.scenarios import SCENARIO_INDEX
from app.services import recent_work as rw
from tests.conftest import auth_headers, register
from tests.judge_fakes import TOKEN
from tests.test_plan_code_evidence import LAB, LAB_TITLE, plan, submit
from tests.test_plan_debug_lesson import lesson
from tests.test_scenarios import RN, start, step
from tests.test_submission_comparisons import judge

URL = "/api/v1/me/recent-work"
SHOWS = "debug_exercise,last_step"
OTHER_LAB = "debug-count-at-most"


def judging(make_client):
    """A server whose judge is on (no worker runs: verdicts are written as the worker writes them)."""
    return make_client(execution_enabled=True, runner_token=TOKEN)


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def rows(client, h, shows=SHOWS) -> list[dict]:
    r = client.get(URL, headers=h, params={"limit": 12, **({"shows": shows} if shows else {})})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def debug_rows(client, h, shows=SHOWS) -> dict[str, dict]:
    return {i["id"]: i for i in rows(client, h, shows) if i["type"] == "debug_exercise"}


def when(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def created(client, sid: str) -> datetime:
    with client.app.state.session_factory() as db:
        at = db.get(Submission, sid).created_at
        return at if at.tzinfo else at.replace(tzinfo=UTC)


def age(client, sid: str, days: float) -> None:
    with client.app.state.session_factory() as db:
        db.execute(
            update(Submission)
            .where(Submission.id == sid)
            .values(created_at=datetime.now(UTC) - timedelta(days=days))
        )
        db.commit()


def test_an_exercise_tried_and_not_fixed_is_listed_with_its_verdict_and_time(make_client):
    client = judging(make_client)
    h = coder(client)
    first = submit(client, h, LAB)
    judge(client, first, SubmissionStatus.FAILED, passed=3, total=7)
    age(client, first, 1)
    row = debug_rows(client, h)[LAB]
    assert (row["title"], row["detail"], row["at_meaning"]) == (
        LAB_TITLE,
        "Not fixed yet: 3 of 7 tests pass",
        "tried",
    )
    assert when(row["at"]) == created(client, first)
    assert row["state"] is None and row["parent_id"] is None
    # The newest attempt speaks for it: one still waiting for the judge, then one the judge failed on.
    newer = submit(client, h, LAB)
    row = debug_rows(client, h)[LAB]
    assert row["detail"] == "Queued" and when(row["at"]) == created(client, newer)
    judge(client, newer, SubmissionStatus.INTERNAL_ERROR)
    assert debug_rows(client, h)[LAB]["detail"] == "Not fixed yet"  # the page's heading, with no counts


def test_without_the_judge_an_attempt_is_saved_not_checked_as_the_page_says(client):
    h = coder(client)
    submit(client, h, LAB)
    assert debug_rows(client, h)[LAB]["detail"] == "Saved, not checked"


def test_a_fixed_exercise_drops_out_even_if_a_later_attempt_fails(make_client):
    client = judging(make_client)
    h = coder(client)
    judge(client, submit(client, h, LAB), SubmissionStatus.FAILED, passed=1)
    judge(client, submit(client, h, OTHER_LAB), SubmissionStatus.FAILED, passed=2)
    assert set(debug_rows(client, h)) == {LAB, OTHER_LAB}
    judge(client, submit(client, h, LAB), SubmissionStatus.PASSED, passed=7)
    assert set(debug_rows(client, h)) == {OTHER_LAB}
    # Fixed is fixed: a failing attempt after the pass doesn't bring it back (the plan's rule).
    judge(client, submit(client, h, LAB), SubmissionStatus.FAILED, passed=0)
    assert set(debug_rows(client, h)) == {OTHER_LAB}


def test_one_whose_newest_attempt_is_more_than_a_week_old_drops_out(make_client):
    client = judging(make_client)
    h = coder(client)
    old = submit(client, h, LAB)
    judge(client, old, SubmissionStatus.FAILED, passed=1)
    age(client, old, 6.9)
    assert LAB in debug_rows(client, h)
    age(client, old, 7.1)
    assert LAB not in debug_rows(client, h)
    # A new attempt brings it back, at the new attempt's time.
    new = submit(client, h, LAB)
    assert when(debug_rows(client, h)[LAB]["at"]) == created(client, new)


def test_a_scenario_run_is_listed_at_its_last_steps_time_and_says_so(client):
    h = coder(client)
    stepped = start(client, h)
    after = step(client, h, stepped)
    fresh = start(client, h, scenario="se-incident-checkout")
    with client.app.state.session_factory() as db:  # started well before its step
        db.execute(
            update(ScenarioAttempt)
            .where(ScenarioAttempt.id == stepped["id"])
            .values(created_at=datetime.now(UTC) - timedelta(hours=3))
        )
        db.commit()
    items = {i["id"]: i for i in rows(client, h)}
    row = items[stepped["id"]]
    assert (row["title"], row["at_meaning"]) == (SCENARIO_INDEX[RN].title, "last_step")
    assert when(row["at"]) == when(after["steps"][-1]["at"])
    untouched = items[fresh["id"]]
    assert untouched["at_meaning"] == "started" and when(untouched["at"]) == when(fresh["created_at"])


def test_a_page_that_doesnt_say_what_it_can_show_gets_what_it_did(make_client):
    client = judging(make_client)
    h = coder(client)
    judge(client, submit(client, h, LAB), SubmissionStatus.FAILED, passed=1)
    run = start(client, h)
    step(client, h, run)
    old = rows(client, h, shows=None)
    assert not [i for i in old if i["type"] == "debug_exercise"]
    [scenario] = [i for i in old if i["type"] == "scenario_run"]
    assert scenario["at_meaning"] == "started" and when(scenario["at"]) == when(run["created_at"])
    # Unknown values are ignored, so a newer page asking for more still gets an answer.
    assert LAB in debug_rows(client, h, shows="debug_exercise,something_later")


def test_another_accounts_exercises_are_never_listed(make_client):
    client = judging(make_client)
    bea = coder(client, email="bea@example.com")
    judge(client, submit(client, bea, LAB), SubmissionStatus.FAILED, passed=1)
    h = coder(client)
    assert debug_rows(client, h) == {}
    judge(client, submit(client, h, OTHER_LAB), SubmissionStatus.PASSED, passed=7)
    assert set(debug_rows(client, bea)) == {LAB}  # Ada's pass of another exercise is hers alone


def test_the_read_failing_is_named_and_the_rest_still_load(client, monkeypatch):
    h = coder(client)
    submit(client, h, LAB)
    start(client, h)

    def broken(db, user, n, _opts):
        db.execute(
            rw.select(rw.func.count()).select_from(rw.Submission).where(rw.Submission.id == rw.func.no_such())
        )
        return []

    label, _ = rw.SOURCES["debug_exercises"]
    monkeypatch.setitem(rw.SOURCES, "debug_exercises", (label, broken))
    r = client.get(URL, headers=h, params={"limit": 12, "shows": SHOWS}).json()
    assert r["unavailable"] == ["debugging exercises"]
    assert {i["type"] for i in r["items"]} == {"scenario_run"}


def test_only_titles_verdicts_and_times_are_read_never_code(client):
    h = coder(client)
    submit(client, h, LAB)
    run = start(client, h)
    step(client, h, run)
    statements: list[str] = []
    engine = client.app.state.session_factory.kw["bind"]

    def capture(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()).lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert debug_rows(client, h)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    code = "\n".join(s for s in statements if "submissions" in s)
    assert "submissions.source_code" not in code and "submissions.starting_code" not in code, code
    assert "execution_results.public_results" not in code and "execution_results.stderr_excerpt" not in code
    # A scenario run's steps only as its last step's time, taken in the query.
    steps = "\n".join(s for s in statements if "scenario_attempts" in s)
    bare = steps.replace("json_extract(scenario_attempts.steps, '$[#-1].at')", "").replace(
        "scenario_attempts.steps -> -1) ->> 'at'", ""
    )
    assert "scenario_attempts.steps" not in bare, steps
    assert "scenario_attempts.current_node" not in steps


def test_listed_once_here_and_the_plans_words_are_unchanged(make_client):
    client = judging(make_client)
    h = coder(client)
    judge(client, submit(client, h, LAB), SubmissionStatus.FAILED, passed=1)
    judge(client, submit(client, h, LAB), SubmissionStatus.FAILED, passed=2)
    assert [i["id"] for i in rows(client, h) if i["type"] == "debug_exercise"] == [LAB]
    item = lesson(plan(client, h))
    assert item is not None and f"“{LAB_TITLE}” isn't fixed yet" in item["reason"]

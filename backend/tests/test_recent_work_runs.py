"""Scenario runs and test-design runs in Continue your work (Volume 19, prompt 6; docs/CONTINUE.md): a
scenario run left in progress is listed as started, with its scenario's title; a finished one isn't
(there's nothing to continue). A test-design run waiting for the judge is listed as saved, "Waiting for
the judge"; one that finished, failed or wasn't run says so in its run list's words, and drops out after
a week. Neither's steps, cases nor report are read; another account's runs are never listed; each kind
is read in its own savepoint, so one failing is named and the rest still show. Synthetic data only; the
judge isn't run here (statuses are written as the worker writes them)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import event, update

from app.models import ScenarioAttempt, TestDesignRun
from app.scenarios import SCENARIO_INDEX
from app.services import recent_work as rw
from app.testdesign import BY_SLUG
from tests.conftest import auth_headers, register
from tests.test_scenarios import RN, start
from tests.test_test_design import COUNT, MINE, NORMAL, case

URL = "/api/v1/me/recent-work"


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def a_run(client, h) -> dict:
    r = client.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0])]}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()


def write(client, model, row_id, **values):
    with client.app.state.session_factory() as db:
        db.execute(update(model).where(model.id == row_id).values(**values))
        db.commit()


def listed(client, h) -> dict:
    r = client.get(URL, headers=h, params={"limit": 12})
    assert r.status_code == 200, r.text
    return {i["id"]: i for i in r.json()["items"]}


def test_a_scenario_run_in_progress_is_listed_as_started_and_a_finished_one_isnt(client):
    h = coder(client)
    going = start(client, h)
    done = start(client, h, scenario="se-incident-checkout")
    write(client, ScenarioAttempt, done["id"], status="completed", completed_at=datetime.now(UTC))
    items = listed(client, h)
    row = items[going["id"]]
    assert (row["type"], row["title"], row["at_meaning"]) == (
        "scenario_run",
        SCENARIO_INDEX[RN].title,
        "started",
    )
    assert row["detail"] is None and row["state"] is None
    assert done["id"] not in items


def test_a_test_design_run_waiting_is_saved_and_finished_ones_say_so_in_the_run_lists_words(client):
    h = coder(client)
    waiting, done, failed, saved = (a_run(client, h) for _ in range(4))
    write(client, TestDesignRun, waiting["id"], status="queued")
    judged = datetime.now(UTC)
    write(
        client,
        TestDesignRun,
        done["id"],
        status="done",
        report={"caught": 2, "total": 4, "cases": [], "variants": []},
        judged_at=judged,
    )
    write(client, TestDesignRun, failed["id"], status="failed", judged_at=judged)
    items = listed(client, h)
    title = BY_SLUG[COUNT].title
    got = {
        k: (items[k]["detail"], items[k]["at_meaning"])
        for k in (waiting["id"], done["id"], failed["id"], saved["id"])
    }
    assert got == {
        waiting["id"]: ("Waiting for the judge · version 1", "saved"),
        done["id"]: ("Told apart 2 of 4 faulty versions · version 1", "finished"),
        failed["id"]: ("The judge couldn't run it · version 1", "finished"),
        saved["id"]: ("Not run: this server can't run code · version 1", "saved"),
    }
    assert {items[k]["title"] for k in got} == {title}
    assert {items[k]["parent_id"] for k in got} == {COUNT}  # its link: /test-design/<slug>?attempt=<id>
    assert datetime.fromisoformat(items[done["id"]]["at"].replace("Z", "+00:00")) == judged
    # The words are the run list's.
    words = {r["id"]: r["outcome_text"] for r in client.get(f"{MINE}/{COUNT}/runs", headers=h).json()}
    assert words[done["id"]].endswith("told apart 2 of 4 faulty versions · version 1")


def test_a_finished_run_drops_out_after_a_week_and_a_waiting_one_stays(client):
    h = coder(client)
    old_done, old_waiting = a_run(client, h), a_run(client, h)
    long_ago = datetime.now(UTC) - timedelta(days=rw.FINISHED_RUN_DAYS, minutes=1)
    write(
        client,
        TestDesignRun,
        old_done["id"],
        status="done",
        report={"caught": 1, "total": 4},
        judged_at=long_ago,
    )
    write(client, TestDesignRun, old_waiting["id"], status="running", created_at=long_ago)
    items = listed(client, h)
    assert old_done["id"] not in items
    assert items[old_waiting["id"]]["detail"] == "Waiting for the judge · version 1"


def test_another_accounts_runs_are_never_listed(client):
    bea = coder(client, "bea@example.com")
    start(client, bea)
    a_run(client, bea)
    h = coder(client)
    assert not [i for i in listed(client, h).values() if i["type"] in ("scenario_run", "test_design_run")]


def test_each_new_kind_failing_is_named_and_the_rest_still_show(client, monkeypatch):
    h = coder(client)
    start(client, h)
    a_run(client, h)

    def broken(db, user, n):
        db.execute(
            rw.select(rw.func.count())
            .select_from(rw.ScenarioAttempt)
            .where(rw.ScenarioAttempt.id == rw.func.no_such())
        )
        return []

    for name in ("scenario_runs", "test_design_runs"):
        label, read = rw.SOURCES[name]
        monkeypatch.setitem(rw.SOURCES, name, (label, broken))
        r = client.get(URL, headers=h, params={"limit": 12}).json()
        assert r["unavailable"] == [label]
        kinds = {i["type"] for i in r["items"]}
        other = "test_design_run" if name == "scenario_runs" else "scenario_run"
        assert (
            other in kinds and ("scenario_run" if name == "scenario_runs" else "test_design_run") not in kinds
        )
        monkeypatch.setitem(rw.SOURCES, name, (label, read))


def test_no_runs_steps_cases_or_report_are_read(client):
    h = coder(client)
    attempt = start(client, h)
    run = a_run(client, h)
    write(
        client,
        TestDesignRun,
        run["id"],
        status="done",
        report={"caught": 1, "total": 4, "cases": [{"secret": 1}]},
        judged_at=datetime.now(UTC),
    )
    statements: list[str] = []
    engine = client.app.state.session_factory.kw["bind"]

    def capture(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()).lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get(URL, headers=h).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    joined = "\n".join(s for s in statements if "scenario_attempts" in s or "test_design_runs" in s)
    assert "scenario_attempts.steps" not in joined and "scenario_attempts.current_node" not in joined
    assert "test_design_runs.cases" not in joined
    # The report only as the two numbers taken from it, never the column itself.
    bare = joined.replace("test_design_runs.report ->>", "").replace(
        "json_extract(test_design_runs.report,", ""
    )
    assert "test_design_runs.report" not in bare, joined
    assert attempt["id"]

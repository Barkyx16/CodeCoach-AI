"""Each judged test-design run beside the previous judged run of the same exercise, by the one
comparison contract (Volume 19, prompt 4; docs/COMPARING_ATTEMPTS.md, "Test-design runs"). Its result
is how many of the exercise's authored faulty versions the cases told apart, both shown as given; the
same version with the same help is comparable, a run after the faulty versions were shown beside one
before is partly comparable and says why, another version isn't comparable. A run that wasn't run,
is waiting or failed isn't compared, says why, and is never the one before. Every explanation repeats
the report's caveat (authored versions only); none says "improved". The run's report, its list and
History say the same. Another account's runs never count. Synthetic data only; the judge isn't run
here (results are written as the worker writes them)."""

from __future__ import annotations

from sqlalchemy import update

from app.models import TestDesignRun
from app.testdesign.report import REPORT_VERSION
from tests.conftest import auth_headers, register
from tests.test_history_practice import feed
from tests.test_test_design import COUNT, MINE, NORMAL, case

FIRST = "Not compared: the first judged run of this exercise"
CAVEAT = (
    "Both counts are of the faulty versions written for this exercise only, not of every possible defect."
)


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def a_run(client, h, n=1) -> dict:
    r = client.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*c) for c in NORMAL[:n]]}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()  # no judge here: saved, not run


def judged(client, run_id, caught, total=4, **values):
    """As the worker writes a finished run (the report's own fields the contract reads)."""
    report = {"report_version": REPORT_VERSION, "caught": caught, "total": total, "cases": [], "variants": []}
    with client.app.state.session_factory() as db:
        db.execute(
            update(TestDesignRun)
            .where(TestDesignRun.id == run_id)
            .values(status="done", report=report, **values)
        )
        db.commit()


def as_worker(client, run_id, **values):
    with client.app.state.session_factory() as db:
        db.execute(update(TestDesignRun).where(TestDesignRun.id == run_id).values(**values))
        db.commit()


def listed(client, h) -> dict:
    return {r["id"]: r for r in client.get(f"{MINE}/{COUNT}/runs", headers=h).json()}


def report(client, h, run_id) -> dict:
    return client.get(f"{MINE}/runs/{run_id}", headers=h).json()


def history(client, h) -> dict:
    items = feed(client, h, type="test_design_run")["items"]
    return {i["target"]["attempt_id"]: i["detail"] for i in items}


def no_trend(c: dict) -> None:
    text = c["comparison"]["explanation"].lower()
    assert CAVEAT in c["comparison"]["explanation"]
    for word in ("improv", "better", "worse", "trend"):
        assert word not in text, text


def test_the_first_judged_run_says_so_and_has_nothing_beside_it(client):
    h = coder(client)
    run = a_run(client, h)
    judged(client, run["id"], 2)
    page = report(client, h, run["id"])
    assert page["compared"] is None and page["not_compared"] == FIRST
    assert listed(client, h)[run["id"]]["not_compared"] == FIRST
    assert history(client, h)[run["id"]].endswith(f" · {FIRST}")


def test_two_judged_runs_at_one_version_with_the_same_help_are_comparable(client):
    h = coder(client)
    first, second = a_run(client, h), a_run(client, h, 2)
    judged(client, first["id"], 1)
    judged(client, second["id"], 3)
    page = report(client, h, second["id"])
    c = page["compared"]
    assert c["previous"]["id"] == first["id"]
    assert c["previous"]["created_at"] == first["created_at"]
    assert c["previous"]["result"] == "told apart 1 of 4 faulty versions"
    assert c["result"] == "told apart 3 of 4 faulty versions"
    assert c["comparison"]["outcome"] == "comparable" and c["comparison"]["reasons"] == []
    assert c["comparison"]["explanation"].startswith(
        "Comparable: the same exercise and version, run against the same authored faulty versions"
    )
    no_trend(c)
    assert page["not_compared"] is None
    # The report itself and its counts are as the worker wrote them.
    assert (page["report"]["caught"], page["report"]["total"]) == (3, 4)
    # The list and History say the same, History in the contract's short words.
    row = listed(client, h)[second["id"]]
    assert row["compared"] == c and row["not_compared"] is None
    assert history(client, h)[second["id"]] == f"{row['outcome_text']} · Comparable with the one before"


def test_a_run_after_the_faulty_versions_were_shown_is_partly_comparable_with_one_before(client):
    h = coder(client)
    before = a_run(client, h)
    judged(client, before["id"], 1)
    assert client.post(f"{MINE}/{COUNT}/variants", headers=h).status_code == 200
    after, later = a_run(client, h), a_run(client, h)
    judged(client, after["id"], 4)
    judged(client, later["id"], 4)
    c = report(client, h, after["id"])["compared"]
    assert c["previous"]["id"] == before["id"]
    assert c["comparison"]["outcome"] == "partially_comparable"
    assert c["comparison"]["scores_comparable"] is True
    [reason] = c["comparison"]["reasons"]
    assert (reason["rule"], reason["kind"]) == ("help", "partial_conditions")
    assert reason["text"] == (
        "the in-app help differed: before the earlier one, none recorded; before the later one, solution revealed"
    )
    no_trend(c)
    # Both after the showing: the same help, so comparable.
    assert report(client, h, later["id"])["compared"]["comparison"]["outcome"] == "comparable"
    assert history(client, h)[after["id"]].endswith(" · Partly comparable with the one before")


def test_a_run_at_another_version_of_the_exercise_isnt_comparable(client):
    h = coder(client)
    old, new = a_run(client, h), a_run(client, h)
    judged(client, old["id"], 2)
    judged(client, new["id"], 2, exercise_version=2)  # the same help (none): only the version differs
    c = report(client, h, new["id"])["compared"]
    assert c["previous"]["id"] == old["id"]
    assert c["comparison"]["outcome"] == "incompatible"
    [reason] = c["comparison"]["reasons"]
    assert reason["rule"] == "question_version"
    assert reason["text"] == (
        "the exercise's faulty versions changed in between (version 1, now 2); each keeps its own result"
    )
    no_trend(c)
    assert history(client, h)[new["id"]].endswith(" · Not comparable with the one before")


def test_a_run_not_run_waiting_or_failed_isnt_compared_and_is_never_the_one_before(client):
    h = coder(client)
    first, saved, failed, waiting, last = (a_run(client, h) for _ in range(5))
    judged(client, first["id"], 1)
    as_worker(client, failed["id"], status="failed")
    as_worker(client, waiting["id"], status="queued")
    judged(client, last["id"], 2)
    rows = listed(client, h)
    assert rows[last["id"]]["compared"]["previous"]["id"] == first["id"]
    said = {
        saved["id"]: "Not compared: it wasn't run (this server can't run code), so there's no result",
        failed["id"]: "Not compared: the judge couldn't run it, so there's no result",
        waiting["id"]: "Not compared: it's waiting for the judge, so there's no result yet",
    }
    lines = history(client, h)
    for run_id, words in said.items():
        assert rows[run_id]["compared"] is None and rows[run_id]["not_compared"] == words
        assert report(client, h, run_id)["not_compared"] == words
        assert lines[run_id] == f"{rows[run_id]['outcome_text']} · {words}"


def test_another_accounts_runs_are_never_the_one_before(client):
    bea = coder(client, "bea@example.com")
    theirs = a_run(client, bea)
    judged(client, theirs["id"], 4)
    h = coder(client)
    mine = a_run(client, h)
    judged(client, mine["id"], 1)
    assert report(client, h, mine["id"])["not_compared"] == FIRST
    assert listed(client, h)[mine["id"]]["compared"] is None
    # And theirs is still their first.
    assert report(client, bea, theirs["id"])["not_compared"] == FIRST


def test_reading_history_stays_bounded_with_judged_runs(client):
    from tests.test_query_budgets import statements

    h = coder(client)
    judged(client, a_run(client, h)["id"], 1)
    with statements(client) as seen:
        feed(client, h)
    few = len(seen)
    for n in range(4):  # five in all: the per-minute limit for runs is six
        judged(client, a_run(client, h)["id"], n)
    with statements(client) as seen:
        feed(client, h)
    assert len(seen) == few, (few, len(seen))

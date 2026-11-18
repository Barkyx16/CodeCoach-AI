"""Test-design runs in History (Volume 18, prompt 10; docs/COMPARING_ATTEMPTS.md, History): the one
practice format History left out. Each run is a row with its date, the exercise, and its result in
the words its own page's list uses (one rule, `run_words`, serves both), then how it compares with
the run before or why it isn't compared (Volume 19, prompt 4: tests/test_test_design_comparisons.py
covers the pairs); it links to that run on the exercise's page. Its status is History's: waiting
for the judge, completed, saved but not run (no judge here), or the judge couldn't run it. The type,
status, career ("Coding problems") and search filters, the counts and the facets include it; reading
History stays bounded; another account's runs never appear. Synthetic data only; the judge isn't
run here (statuses are written as the worker writes them)."""

from __future__ import annotations

from sqlalchemy import update

from app.models import TestDesignRun
from app.testdesign import BY_SLUG
from tests.conftest import auth_headers, register
from tests.test_history_practice import feed
from tests.test_test_design import COUNT, MINE, NORMAL, case

ACTIVITY = "/api/v1/me/activity"
NOT_RUN = "Not compared: it wasn't run (this server can't run code), so there's no result"
FIRST = "Not compared: the first judged run of this exercise"
WAITING = "Not compared: it's waiting for the judge, so there's no result yet"
FAILED = "Not compared: the judge couldn't run it, so there's no result"


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def a_run(client, h, n=1) -> dict:
    r = client.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*c) for c in NORMAL[:n]]}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()  # no judge here: saved, not run


def as_worker(client, run_id, **values):
    with client.app.state.session_factory() as db:
        db.execute(update(TestDesignRun).where(TestDesignRun.id == run_id).values(**values))
        db.commit()


def rows(client, h, **params):
    return [i for i in feed(client, h, **params)["items"] if i["type"] == "test_design_run"]


def listed(client, h) -> dict:
    return {r["id"]: r for r in client.get(f"{MINE}/{COUNT}/runs", headers=h).json()}


def test_a_run_is_a_row_in_its_pages_words_linking_to_that_run(client):
    h = coder(client)
    run = a_run(client, h)
    [row] = rows(client, h)
    words = listed(client, h)[run["id"]]["outcome_text"]
    assert words == "1 case · not run: this server can't run code · version 1"
    assert row["detail"] == f"{words} · {NOT_RUN}"
    assert row["title"] == BY_SLUG[COUNT].title and row["career"] == "coding"
    assert row["career_title"] == "Coding problems"
    assert (row["status"], row["status_label"]) == ("saved_not_judged", "Saved, not judged")
    assert row["target"]["href"] == f"/test-design/{COUNT}?attempt={run['id']}"
    assert row["target"]["attempt_id"] == run["id"]


def test_each_status_reads_as_historys_in_the_same_words_as_its_list(client):
    h = coder(client)
    done, waiting, failed = a_run(client, h, 2), a_run(client, h), a_run(client, h, 3)
    as_worker(client, done["id"], status="done", report={"report_version": 1, "caught": 2, "total": 3})
    as_worker(client, waiting["id"], status="queued")
    as_worker(client, failed["id"], status="failed")
    by_id = {r["target"]["attempt_id"]: r for r in rows(client, h)}
    words = {k: v["outcome_text"] for k, v in listed(client, h).items()}
    assert words[done["id"]] == "2 cases · told apart 2 of 3 faulty versions · version 1"
    assert words[waiting["id"]] == "1 case · waiting for the judge · version 1"
    assert words[failed["id"]] == "3 cases · the judge couldn't run it · version 1"
    assert {k: (r["status"], r["detail"]) for k, r in by_id.items()} == {
        done["id"]: ("completed", f"{words[done['id']]} · {FIRST}"),
        waiting["id"]: ("awaiting_judge", f"{words[waiting['id']]} · {WAITING}"),
        failed["id"]: ("evaluation_unavailable", f"{words[failed['id']]} · {FAILED}"),
    }


def test_filters_counts_and_facets_include_them(client):
    h = coder(client)
    done = a_run(client, h)
    a_run(client, h)
    as_worker(client, done["id"], status="done", report={"caught": 1, "total": 3})
    assert feed(client, h, type="test_design_run")["total"] == 2
    assert feed(client, h, type="test_design_run", status="completed")["total"] == 1
    assert feed(client, h, type="test_design_run", status="saved_not_judged")["total"] == 1
    assert feed(client, h, type="test_design_run", status="in_progress")["total"] == 0
    assert len(rows(client, h, career="coding")) == 2
    assert rows(client, h, career="registered-nurse") == []
    title = BY_SLUG[COUNT].title
    assert len(rows(client, h, q=title.split()[0].lower())) == 2
    assert rows(client, h, q="no such exercise") == []
    facets = client.get(f"{ACTIVITY}/facets", headers=h).json()
    counts = {t["value"]: t["count"] for t in facets["types"]}
    assert counts["test_design_run"] == 2
    statuses = {s["value"]: s["count"] for s in facets["statuses"]}
    assert statuses["completed"] >= 1 and statuses["saved_not_judged"] >= 1
    assert sum(counts.values()) == feed(client, h)["total"]


def test_another_accounts_runs_never_appear(client):
    a_run(client, coder(client, "bea@example.com"))
    h = coder(client)
    assert rows(client, h) == [] and feed(client, h)["total"] == 0
    facets = client.get(f"{ACTIVITY}/facets", headers=h).json()
    assert {t["value"]: t["count"] for t in facets["types"]}["test_design_run"] == 0


def test_reading_history_stays_bounded_with_runs(client):
    from tests.test_query_budgets import statements

    h = coder(client)
    a_run(client, h)
    with statements(client) as seen:
        feed(client, h)
    few = len(seen)
    for _ in range(4):  # five in all: the per-minute limit for runs is six
        a_run(client, h)
    with statements(client) as seen:
        feed(client, h)
    assert len(seen) == few, (few, len(seen))

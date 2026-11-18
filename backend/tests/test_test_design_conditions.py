"""The help before a test-design run (Volume 19, prompt 3; docs/ATTEMPT_CONDITIONS.md): having the
faulty versions shown, while signed in, is recorded once per exercise version, with when; every run
after it at that version says "Solution revealed" with that time (they can't be unseen); one before
it, or after a showing at another version, doesn't. Runs from before recording began say "Not
recorded" and why. Another account's showing never counts. The run's page, its list, the bulk
route History uses and the export say the same. Showing them signed out records nothing. Synthetic
data only; no judge here (runs are saved as not run)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update

from app.models import TestDesignReveal, TestDesignRun
from tests.conftest import auth_headers, register
from tests.test_test_design import COUNT, MINE, NORMAL, case

CONDITIONS = "/api/v1/me/attempt-conditions"
DETAIL = "The faulty versions were shown before these cases were written"


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def show(client, h):
    r = client.post(f"{MINE}/{COUNT}/variants", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def a_run(client, h):
    r = client.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0])]}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()


def labels(c):
    return c["labels"]


def reveals(client) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(TestDesignReveal))


def test_showing_them_is_recorded_once_per_version_and_signed_out_not_at_all(client):
    assert client.get(f"/api/v1/test-design/{COUNT}/variants").status_code == 200
    assert reveals(client) == 0
    h = coder(client)
    first = show(client, h)
    assert first["variants"] and first["recorded_at"]
    again = show(client, h)
    assert again["recorded_at"] == first["recorded_at"] and reveals(client) == 1
    assert client.post(f"{MINE}/{COUNT}/variants").status_code == 401


def test_runs_after_say_solution_revealed_with_its_time_and_one_before_doesnt(client):
    h = coder(client)
    before = a_run(client, h)
    shown = show(client, h)
    after = a_run(client, h)
    later = a_run(client, h)
    assert labels(before["conditions"]) == ["No in-app help recorded"]
    for run in (after, later):  # every run after it: they can't be unseen
        [help_] = run["conditions"]["help"]
        assert (help_["label"], help_["detail"]) == ("Solution revealed", DETAIL)
        assert datetime.fromisoformat(help_["at"].replace("Z", "+00:00")) == datetime.fromisoformat(
            shown["recorded_at"].replace("Z", "+00:00")
        )
    # The run's page, its list and the bulk route History uses say the same.
    page = client.get(f"{MINE}/runs/{after['id']}", headers=h).json()
    listed = {r["id"]: r for r in client.get(f"{MINE}/{COUNT}/runs", headers=h).json()}
    bulk = client.post(
        CONDITIONS, headers=h, json={"test_design_run_ids": [before["id"], after["id"]]}
    ).json()
    assert page["conditions"] == listed[after["id"]]["conditions"] == bulk["test_design_runs"][after["id"]]
    assert bulk["test_design_runs"][before["id"]] == listed[before["id"]]["conditions"]
    # Read again after the showing, the run made before it still had none.
    assert labels(listed[before["id"]]["conditions"]) == ["No in-app help recorded"]


def test_a_showing_at_another_version_doesnt_count(client):
    h = coder(client)
    show(client, h)
    with client.app.state.session_factory() as db:  # as if shown at the exercise's earlier version
        db.execute(update(TestDesignReveal).values(exercise_version=0))
        db.commit()
    assert labels(a_run(client, h)["conditions"]) == ["No in-app help recorded"]


def test_a_run_from_before_recording_began_is_not_recorded_and_says_why(client):
    h = coder(client)
    run = a_run(client, h)
    with client.app.state.session_factory() as db:
        db.execute(
            update(TestDesignRun)
            .where(TestDesignRun.id == run["id"])
            .values(created_at=datetime(2026, 11, 17, 12, tzinfo=UTC))
        )
        db.commit()
    c = client.get(f"{MINE}/runs/{run['id']}", headers=h).json()["conditions"]
    assert labels(c) == ["Not recorded"]
    assert c["unrecorded"].startswith("Showing the faulty versions wasn't recorded before 18 Nov 2026")


def test_another_accounts_showing_never_counts_and_their_runs_are_left_out(client):
    theirs = coder(client, "bea@example.com")
    show(client, theirs)
    their_run = a_run(client, theirs)
    h = coder(client)
    assert labels(a_run(client, h)["conditions"]) == ["No in-app help recorded"]
    bulk = client.post(CONDITIONS, headers=h, json={"test_design_run_ids": [their_run["id"]]}).json()
    assert bulk["test_design_runs"] == {}


def test_the_export_carries_the_runs_conditions_and_the_showings(client):
    h = coder(client)
    shown = show(client, h)
    run = a_run(client, h)
    doc = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    [exported] = doc["test_design_runs"]
    assert exported["conditions"] == client.get(f"{MINE}/runs/{run['id']}", headers=h).json()["conditions"]
    [r] = doc["test_design_reveals"]
    assert (r["exercise"], r["exercise_version"]) == (COUNT, 1)
    assert r["at"].replace("+00:00", "Z")[:19] == shown["recorded_at"].replace("+00:00", "Z")[:19]

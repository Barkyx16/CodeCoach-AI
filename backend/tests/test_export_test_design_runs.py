"""Test-design runs exported as every other attempt is (Volume 19, prompt 9; docs/YOUR_DATA.md): each
with its id (the one History and its page name it by), status and detail, cases, report, created and
judged times, its list's words, its conditions (the bulk route's own function) and its comparison
with the run before in the contract's words. The export stays version 2 and its validation passes
with runs in every status. A walk over every section fails on any attempt without its id, so a
format added later can't be left out. Another account's runs are never exported; a backup file still
doesn't restore them. Synthetic data only; the judge isn't run here (statuses are written as the
worker writes them)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update

from app.models import TestDesignRun
from app.services import export_walk
from app.services.export_v2 import validate_export
from app.testdesign.report import REPORT_VERSION
from tests.conftest import auth_headers, register
from tests.test_comparisons import SPECIFIC, pick, send
from tests.test_history_practice import feed
from tests.test_offer_rehearsals import start as start_rehearsal
from tests.test_restore import apply, backup, preview
from tests.test_scenarios import start as start_scenario
from tests.test_test_design import COUNT, MINE, NORMAL, case

CONDITIONS = "/api/v1/me/attempt-conditions"


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def a_run(client, h) -> dict:
    r = client.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0])]}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()


def as_worker(client, run_id, **values):
    with client.app.state.session_factory() as db:
        db.execute(update(TestDesignRun).where(TestDesignRun.id == run_id).values(**values))
        db.commit()


def every_status(client, h) -> dict[str, dict]:
    """One run in each status: judged twice (so the second is compared), waiting, not run, failed."""
    runs = {k: a_run(client, h) for k in ("judged", "judged_again", "waiting", "not_run", "failed")}
    now = datetime.now(UTC)
    report = {"report_version": REPORT_VERSION, "caught": 1, "total": 4, "cases": [], "variants": []}
    as_worker(client, runs["judged"]["id"], status="done", report=report, judged_at=now, status_detail="Ran.")
    as_worker(
        client, runs["judged_again"]["id"], status="done", report={**report, "caught": 2}, judged_at=now
    )
    as_worker(client, runs["waiting"]["id"], status="queued", status_detail="Waiting for the judge…")
    as_worker(
        client, runs["failed"]["id"], status="failed", judged_at=now, status_detail="The judge kept failing."
    )
    return runs


def export(client, h, version=2) -> dict:
    r = client.get("/api/v1/me/export", params={"version": version}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_each_run_is_exported_with_its_id_and_matches_its_page_history_and_the_bulk_route(client):
    h = coder(client)
    runs = every_status(client, h)
    doc = export(client, h)
    exported = {r["id"]: r for r in doc["test_design_runs"]}
    assert set(exported) == {r["id"] for r in runs.values()}
    listed = {r["id"]: r for r in client.get(f"{MINE}/{COUNT}/runs", headers=h).json()}
    history = {i["target"]["attempt_id"] for i in feed(client, h, type="test_design_run")["items"]}
    bulk = client.post(CONDITIONS, headers=h, json={"test_design_run_ids": list(exported)}).json()
    for run_id, row in exported.items():
        page = client.get(f"{MINE}/runs/{run_id}", headers=h).json()
        assert run_id in history
        assert (row["status"], row["status_detail"], row["cases"], row["report"]) == (
            page["status"],
            page["status_detail"],
            page["cases"],
            page["report"],
        )
        assert row["outcome_text"] == listed[run_id]["outcome_text"]
        assert row["conditions"] == bulk["test_design_runs"][run_id] == page["conditions"]
        assert (row["judged_at"] is None) == (page["judged_at"] is None)
        assert row["created_at"] and row["exercise"] == COUNT and row["exercise_version"] == 1
    # The comparison with the run before, in the contract's words.
    again = exported[runs["judged_again"]["id"]]
    assert again["compared"]["against"] == runs["judged"]["id"]
    assert again["compared"]["text"] == "Comparable with the one before"
    assert (
        again["compared"]["explanation"]
        == listed[runs["judged_again"]["id"]]["compared"]["comparison"]["explanation"]
    )
    assert again["not_compared"] is None
    assert (
        exported[runs["judged"]["id"]]["not_compared"]
        == "Not compared: the first judged run of this exercise"
    )
    assert exported[runs["failed"]["id"]]["compared"] is None


def test_the_exports_own_validation_passes_with_runs_in_every_status(client):
    h = coder(client)
    every_status(client, h)
    doc = export(client, h)
    assert doc["export_version"] == 2
    assert validate_export(doc) == []
    assert {r["status"] for r in doc["test_design_runs"]} == {"done", "queued", "not_run", "failed"}
    # It knows the runs' ids: one twice, or one without, is found.
    twice = {**doc, "test_design_runs": doc["test_design_runs"] + doc["test_design_runs"][:1]}
    assert [i["rule"] for i in validate_export(twice)] == ["duplicate_id"]
    without = {
        **doc,
        "test_design_runs": [{k: v for k, v in doc["test_design_runs"][0].items() if k != "id"}],
    }
    assert [(i["path"], i["rule"]) for i in validate_export(without)] == [
        ("test_design_runs[0]", "missing_id")
    ]


def test_exporting_changes_no_run(client):
    h = coder(client)
    every_status(client, h)

    def snapshot():
        with client.app.state.session_factory() as db:
            return sorted(
                (r.id, r.status, r.status_detail, str(r.report), str(r.judged_at))
                for r in db.scalars(select(TestDesignRun))
            )

    before = snapshot()
    export(client, h)
    export(client, h, version=1)
    assert snapshot() == before


def test_another_accounts_runs_are_never_exported(client):
    bea = coder(client, "bea@example.com")
    theirs = a_run(client, bea)
    h = coder(client)
    mine = a_run(client, h)
    assert [r["id"] for r in export(client, h)["test_design_runs"]] == [mine["id"]]
    assert theirs["id"] not in repr(export(client, h))


def test_the_walk_finds_every_attempt_with_its_id_across_every_section(client):
    h = coder(client)
    every_status(client, h)
    start_scenario(client, h)
    assert (
        send(client, h, SPECIFIC, [pick("B", "b4", "strength", "A result that can be checked.")]).status_code
        == 201
    )
    start_rehearsal(client, h)
    doc = export(client, h)
    assert export_walk.walk(doc) == []
    for path, (field, _) in export_walk.ATTEMPTS.items():
        assert field == "id", path  # the rule each section is held to, named
    # Every section is classified, and each attempt section here has its records.
    assert all(s in export_walk.OTHER or s in {p.split(".")[0] for p in export_walk.ATTEMPTS} for s in doc)
    assert (
        doc["offer_rehearsals"][0]["id"] and doc["scenario_attempts"][0]["id"] and doc["comparisons"][0]["id"]
    )
    # Version 1 too.
    assert export_walk.walk(export(client, h, version=1)) == []


def test_the_walk_fails_on_an_attempt_without_its_id_or_conditions_and_on_a_new_section(client):
    h = coder(client)
    a_run(client, h)
    doc = export(client, h)
    no_id = {
        **doc,
        "test_design_runs": [{k: v for k, v in r.items() if k != "id"} for r in doc["test_design_runs"]],
    }
    assert {i["rule"] for i in export_walk.walk(no_id)} == {"attempt_without_id"}
    no_conditions = {
        **doc,
        "test_design_runs": [
            {k: v for k, v in r.items() if k != "conditions"} for r in doc["test_design_runs"]
        ],
    }
    assert [i["rule"] for i in export_walk.walk(no_conditions)] == ["attempt_without_conditions"]
    # A format added later, its attempts without ids: named as unclassified, and its records caught.
    added = {**doc, "new_format_attempts": [{"conditions": {"labels": []}, "created_at": "2026-11-18"}]}
    rules = {i["rule"] for i in export_walk.walk(added)}
    assert rules == {"unclassified_section", "attempt_without_id"}


def test_a_backup_still_doesnt_restore_runs_and_says_so(client):
    h = coder(client)
    a_run(client, h)
    raw = backup(client, h)
    other = coder(client, "bea@example.com")
    body = preview(client, other, raw).json()
    reasons = {u["key"]: u["reason"] for u in body["not_restored"]}
    assert "test_design_runs" in reasons and reasons["test_design_runs"]
    assert apply(client, other, raw).status_code == 201
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TestDesignRun)) == 1  # only the original

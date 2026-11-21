"""Drills, whiteboard designs and work samples compared by the one contract (Volume 15, prompt 4;
docs/COMPARING_ATTEMPTS.md, "Drills, whiteboards and work samples"): each assessed attempt is set
beside the previous assessed attempt at the same item (a work sample's revision beside the one it
revises), with both results as given and the contract's own explanation. Each outcome is produced for
each format: the same item, version, rules and help compare; different help is partly comparable; a
changed checklist or set of rules isn't comparable; help from before recording began is unknown. The
first attempt compares with nothing, another account's attempts are never compared, and the export
carries each comparison by id. Synthetic data only."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from sqlalchemy import update

from app import whiteboard as wb
from app import worksamples as ws
from app.careers.comparability import CONTRACT_VERSION
from app.learn import UNIT_INDEX
from app.models import DrillAttempt, WhiteboardAttempt, WorkSampleAttempt
from app.services.conditions import FORMATS_RECORDED_FROM
from tests.test_practice_conditions import ANSWER, STAR, nurse, read
from tests.test_whiteboard import DIAGRAM, EXPLAIN
from tests.test_work_samples import GOOD_INCIDENT, INCIDENT
from tests.test_work_samples import send as send_work_sample

PROMPT = "sd-url-shortener"
FORMATS = ("drill", "whiteboard", "work_sample")
MODEL = {"drill": DrillAttempt, "whiteboard": WhiteboardAttempt, "work_sample": WorkSampleAttempt}
LIST = {
    "drill": "/api/v1/me/drills/example/attempts",
    "whiteboard": f"/api/v1/me/whiteboard/{PROMPT}/attempts",
    "work_sample": f"/api/v1/me/work-samples/{INCIDENT}/attempts",
}
ITEM = {"drill": "drill", "whiteboard": "prompt", "work_sample": "brief"}


def attempt(client, h, kind, revision_of=None, n=0):
    if kind == "drill":
        r = client.post(
            LIST["drill"], headers=h, json={"text": ANSWER + " It worked." * n, "source": "typed"}
        )
    elif kind == "whiteboard":
        r = client.post(LIST["whiteboard"], headers=h, json={"diagram": DIAGRAM, "explanation": EXPLAIN})
    else:
        r = send_work_sample(client, h, INCIDENT, GOOD_INCIDENT, revision_of=revision_of)
    assert r.status_code == 201, r.text
    return r.json()


def own_result(kind, a):
    """The attempt's own result, counted from its own feedback."""
    fb = a["feedback"]
    if kind == "drill":
        found, of, word = sum(o["present"] for o in fb["observations"]), len(fb["observations"]), "there"
    elif kind == "whiteboard":
        found, of, word = sum(r["addressed"] for r in fb["rubric"]), len(fb["rubric"]), "addressed"
    else:
        found, of, word = fb["covered"], fb["total"], "covered"
    return f"{found} of {of} points {word}"


def listed(client, h, kind):
    r = client.get(LIST[kind], headers=h)
    assert r.status_code == 200, r.text
    return {a["id"]: a for a in r.json()}


def prepare(monkeypatch, kind):
    """Lets the STAR lesson prepare this format's item too (only the drill has a real lesson link)."""
    ref = {"whiteboard": f"whiteboard:{PROMPT}", "work_sample": f"work_sample:{INCIDENT}"}.get(kind)
    if ref:
        unit = UNIT_INDEX[STAR]
        monkeypatch.setitem(UNIT_INDEX, STAR, dataclasses.replace(unit, prepares=(*unit.prepares, ref)))


def change_checklist(monkeypatch, kind):
    """The item's points change: a new rubric for the drill, a new prompt or brief version."""
    if kind == "drill":
        monkeypatch.setattr("app.services.drills.RUBRIC_VERSION", 2)
    elif kind == "whiteboard":
        monkeypatch.setitem(wb.BY_ID, PROMPT, dataclasses.replace(wb.BY_ID[PROMPT], version=2))
    else:
        monkeypatch.setitem(ws.BY_ID, INCIDENT, dataclasses.replace(ws.BY_ID[INCIDENT], version=2))


@pytest.mark.parametrize("kind", FORMATS)
def test_the_same_item_rules_and_help_compare_and_both_results_are_shown(client, kind):
    h = nurse(client)
    first = attempt(client, h, kind)
    assert first["compared"] is None  # nothing earlier to compare with
    second = attempt(client, h, kind, n=1)
    got = second["compared"]
    assert got["previous"]["id"] == first["id"] and got["comparison"]["against"] == first["id"]
    c = got["comparison"]
    assert (
        c["outcome"] == "comparable" and c["scores_comparable"] and c["contract_version"] == CONTRACT_VERSION
    )
    assert c["explanation"] == (
        f"Comparable: the same {ITEM[kind]} and version, checked by the same fixed rules, with the same "
        f"in-app help. (Comparison rules v{CONTRACT_VERSION})"
    )
    assert got["previous"]["result"] == own_result(kind, first) and got["result"] == own_result(kind, second)
    # The list carries the same comparison; its first attempt has none.
    rows = listed(client, h, kind)
    assert rows[second["id"]]["compared"] == got and rows[first["id"]]["compared"] is None


@pytest.mark.parametrize("kind", FORMATS)
def test_different_help_is_partly_comparable_and_the_results_still_stand_side_by_side(
    client, monkeypatch, kind
):
    prepare(monkeypatch, kind)
    h = nurse(client)
    read(client, h, STAR)
    first = attempt(client, h, kind)
    assert first["conditions"]["labels"] == ["Hint shown"]
    second = attempt(client, h, kind, n=1)
    c = second["compared"]["comparison"]
    assert c["outcome"] == "partially_comparable" and c["scores_comparable"] and c["points_comparable"]
    assert [r["rule"] for r in c["reasons"]] == ["help"]
    assert "before the earlier one, hint shown; before the later one, none recorded" in c["explanation"]
    assert "same checks by the same fixed rules, so both are shown" in c["explanation"]


@pytest.mark.parametrize("kind", FORMATS)
def test_a_changed_checklist_isnt_comparable_and_each_keeps_its_own_result(client, monkeypatch, kind):
    h = nurse(client)
    first = attempt(client, h, kind)
    change_checklist(monkeypatch, kind)
    second = attempt(client, h, kind, n=1)
    got = second["compared"]
    c = got["comparison"]
    assert c["outcome"] == "incompatible" and not c["scores_comparable"] and not c["points_comparable"]
    assert [r["rule"] for r in c["reasons"]] == ["question_version"]
    assert (
        f"the {ITEM[kind]}'s points changed in between (version 1, now 2); each keeps its own result"
        in c["explanation"]
    )
    # Both results are still shown as they were given.
    assert got["previous"]["id"] == first["id"] and got["previous"]["result"] and got["result"]


@pytest.mark.parametrize("kind", ("whiteboard", "work_sample"))
def test_a_changed_set_of_rules_isnt_comparable(client, monkeypatch, kind):
    h = nurse(client)
    attempt(client, h, kind)
    if kind == "whiteboard":
        monkeypatch.setattr("app.services.whiteboard.RUBRIC_VERSION", 2)
    else:
        monkeypatch.setattr("app.worksamples.feedback.RULES_VERSION", 2)
    c = attempt(client, h, kind, n=1)["compared"]["comparison"]
    assert c["outcome"] == "incompatible" and [r["rule"] for r in c["reasons"]] == ["rubric"]
    assert (
        "checked by different versions of the rules (v1 and v2); each keeps its own result"
        in c["explanation"]
    )


def test_a_drill_asked_for_another_career_isnt_comparable(client):
    h = nurse(client)
    first = attempt(client, h, "drill")
    with client.app.state.session_factory() as db:
        db.execute(
            update(DrillAttempt).where(DrillAttempt.id == first["id"]).values(track="software-engineer")
        )
        db.commit()
    c = attempt(client, h, "drill", n=1)["compared"]["comparison"]
    assert c["outcome"] == "incompatible"
    assert "the drill's prompt was worded for a different career each time" in c["explanation"]


@pytest.mark.parametrize("kind", FORMATS)
def test_help_from_before_recording_began_is_unknown_not_assumed_the_same(client, kind):
    h = nurse(client)
    first = attempt(client, h, kind)
    with client.app.state.session_factory() as db:
        model = MODEL[kind]
        db.execute(
            update(model)
            .where(model.id == first["id"])
            .values(created_at=FORMATS_RECORDED_FROM - timedelta(days=1))
        )
        db.commit()
    c = attempt(client, h, kind, n=1)["compared"]["comparison"]
    assert c["outcome"] == "unknown" and [r["rule"] for r in c["reasons"]] == ["help"]
    assert (
        "in-app help before one of them wasn't recorded (it's recorded from 15 Nov 2026)" in c["explanation"]
    )


def test_a_work_sample_without_its_rules_version_is_unknown(client):
    h = nurse(client)
    first = attempt(client, h, "work_sample")
    with client.app.state.session_factory() as db:
        row = db.get(WorkSampleAttempt, first["id"])
        row.feedback = {k: v for k, v in row.feedback.items() if k != "rules_version"}
        db.commit()
    c = attempt(client, h, "work_sample")["compared"]["comparison"]
    assert c["outcome"] == "unknown" and [r["rule"] for r in c["reasons"]] == ["rubric"]


def test_a_revision_is_compared_with_the_attempt_it_revises(client):
    h = nurse(client)
    original = attempt(client, h, "work_sample")
    attempt(client, h, "work_sample")
    revised = attempt(client, h, "work_sample", revision_of=original["id"])
    assert revised["compared"]["previous"]["id"] == original["id"]


def test_an_attempt_with_no_stored_result_is_never_compared(client):
    h = nurse(client)
    first = attempt(client, h, "drill")
    broken = attempt(client, h, "drill", n=1)
    with client.app.state.session_factory() as db:
        db.execute(update(DrillAttempt).where(DrillAttempt.id == broken["id"]).values(feedback={}))
        db.commit()
    third = attempt(client, h, "drill", n=2)
    rows = listed(client, h, "drill")
    assert rows[broken["id"]]["compared"] is None
    assert third["compared"]["previous"]["id"] == first["id"]  # beside the last assessed one


@pytest.mark.parametrize("kind", FORMATS)
def test_another_accounts_attempts_are_never_compared(client, kind):
    a = nurse(client)
    b = nurse(client, email="bea@example.com")
    attempt(client, a, kind)
    theirs = attempt(client, b, kind)
    assert theirs["compared"] is None
    assert all(r["compared"] is None for r in listed(client, b, kind).values())


def test_the_export_carries_each_comparison_by_id(client):
    h = nurse(client)
    made = {k: [attempt(client, h, k), attempt(client, h, k, n=1)] for k in FORMATS}
    doc = client.get("/api/v1/me/export", headers=h).json()
    rows = {
        "drill": {r["id"]: r for r in doc["drill_attempts"]},
        "whiteboard": {r["id"]: r for r in doc["whiteboard"]["attempts"]},
        "work_sample": {r["id"]: r for r in doc["work_samples"]["attempts"]},
    }
    for kind, (first, second) in made.items():
        assert rows[kind][first["id"]]["comparison"] is None, kind
        c = rows[kind][second["id"]]["comparison"]
        assert (c["against"], c["outcome"]) == (first["id"], "comparable"), kind
        assert c == second["compared"]["comparison"], kind


def test_no_comparison_says_one_attempt_improved_on_the_other(client, monkeypatch):
    h = nurse(client)
    texts = []
    for kind in FORMATS:
        attempt(client, h, kind)
        texts.append(attempt(client, h, kind, n=1)["compared"]["comparison"]["explanation"])
    change_checklist(monkeypatch, "drill")
    texts.append(attempt(client, h, "drill", n=2)["compared"]["comparison"]["explanation"])
    for t in texts:
        low = t.lower()
        assert not any(w in low for w in ("improv", "better", "worse", "progress")), t

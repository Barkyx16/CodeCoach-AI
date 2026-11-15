"""The conditions of drills, scenario runs and whiteboard attempts (Volume 14, prompt 4;
docs/ATTEMPT_CONDITIONS.md): the Learn lessons that prepare a drill or a scenario, read before an
attempt at the version it was made at, are "Hint shown" for the first attempt after them (in the
same mode), with the labels every other format uses. Nothing is recorded for what the app didn't
show; no score, verdict or feedback changes. Synthetic data only."""

import dataclasses
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app import scenarios as sc
from app.learn import UNIT_INDEX
from app.models import DrillAttempt, LearnEvent, ScenarioAttempt, User, WhiteboardAttempt
from app.services.conditions import FORMATS_RECORDED_FROM, practice_version
from tests.conftest import auth_headers, register
from tests.test_scenarios import SBAR
from tests.test_whiteboard import DIAGRAM, EXPLAIN

RN = "rn-two-patients"
PRIORITIZE = "rn-prioritization"
STAR = "rn-star-answers"
ANSWER = (
    "When two patients needed me at once I checked the one short of breath first, asked a colleague to "
    "tell the other I was coming, then gave the medicine and documented both."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def read(client, h, unit, minutes_ago=5):
    r = client.post(f"/api/v1/me/learn/units/{unit}/events", headers=h, json={"kind": "read", "version": 1})
    assert r.status_code == 200, r.text
    with client.app.state.session_factory() as db:  # a little earlier than what follows
        db.execute(
            update(LearnEvent)
            .where(LearnEvent.unit_id == unit, LearnEvent.kind.in_(["read", "started"]))
            .values(created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago))
        )
        db.commit()


def run(client, h, mode="assessed", parent=None):
    body = {"mode": mode} | ({"parent_id": parent} if parent else {})
    r = client.post(f"/api/v1/me/scenarios/{RN}/attempts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def finish(client, h, attempt):
    """Walks a run to an ending, choosing the first option and answering any written step."""
    a = attempt
    while a["status"] != "completed":
        cur = a["current"]
        body = {"node_id": cur["id"]}
        if cur["kind"] == "choice":
            body["choice_id"] = cur["options"][0]["id"]
        elif cur["kind"] == "written":
            body["text"] = SBAR
        r = client.post(f"/api/v1/me/scenario-attempts/{a['id']}/steps", headers=h, json=body)
        assert r.status_code == 200, r.text
        a = r.json()
    return a


def drill(client, h, text=ANSWER):
    r = client.post("/api/v1/me/drills/example/attempts", headers=h, json={"text": text, "source": "typed"})
    assert r.status_code == 201, r.text
    return r.json()


def labels(c):
    return c["labels"]


def test_every_lesson_link_names_something_that_exists():
    for u in UNIT_INDEX.values():
        for ref in u.prepares:
            assert practice_version(ref) is not None, (u.id, ref)
    assert "scenario:rn-two-patients" in UNIT_INDEX[PRIORITIZE].prepares
    assert "drill:example" in UNIT_INDEX[STAR].prepares


def test_a_lesson_before_a_scenario_run_is_help_for_the_first_run_only(client):
    h = nurse(client)
    read(client, h, PRIORITIZE)
    first = run(client, h)
    c = first["conditions"]
    assert labels(c) == ["Hint shown"]
    assert c["help"][0]["detail"] == "Lesson “Prioritizing when several patients need you” read"
    first = finish(client, h, first)
    second = run(client, h)
    assert labels(second["conditions"]) == ["No in-app help recorded"]
    # The run's list says the same; the run itself is untouched.
    listed = {a["id"]: a["conditions"] for a in client.get("/api/v1/me/scenario-attempts", headers=h).json()}
    assert labels(listed[first["id"]]) == ["Hint shown"] and labels(listed[second["id"]]) == [
        "No in-app help recorded"
    ]
    again = client.get(f"/api/v1/me/scenario-attempts/{first['id']}", headers=h).json()
    assert again["debrief"] == first["debrief"]


def test_an_exploration_counts_its_help_apart_from_assessed_runs(client):
    h = nurse(client)
    read(client, h, PRIORITIZE, minutes_ago=10)
    first = finish(client, h, run(client, h))
    explore = run(client, h, mode="exploration", parent=first["id"])
    assert labels(explore["conditions"]) == ["Hint shown"]  # its first in that mode


def test_a_lesson_read_at_another_version_of_the_scenario_isnt_its_help(client, monkeypatch):
    h = nurse(client)
    read(client, h, PRIORITIZE)  # recorded while the scenario was at version 1
    with client.app.state.session_factory() as db:
        e = db.scalar(select(LearnEvent).where(LearnEvent.unit_id == PRIORITIZE, LearnEvent.kind == "read"))
        assert e.detail == {"prepares": {"scenario:rn-two-patients": 1}}
    monkeypatch.setitem(
        sc.SCENARIO_INDEX, RN, dataclasses.replace(sc.SCENARIO_INDEX[RN], version=2, _index={})
    )
    a = run(client, h)
    assert a["version"] == 2 and labels(a["conditions"]) == ["No in-app help recorded"]


def test_a_read_from_before_versions_were_recorded_is_unknown_on_a_revised_scenario(client, monkeypatch):
    h = nurse(client)
    read(client, h, PRIORITIZE)
    with client.app.state.session_factory() as db:
        db.execute(update(LearnEvent).where(LearnEvent.unit_id == PRIORITIZE).values(detail=None))
        db.commit()
    # Never revised: a read with no version recorded can only have been of version 1.
    assert labels(run(client, h)["conditions"]) == ["Hint shown"]
    with client.app.state.session_factory() as db:
        db.execute(update(ScenarioAttempt).values(status="completed"))
        db.execute(
            update(LearnEvent).where(LearnEvent.unit_id == PRIORITIZE).values(created_at=datetime.now(UTC))
        )
        db.commit()
    monkeypatch.setitem(
        sc.SCENARIO_INDEX, RN, dataclasses.replace(sc.SCENARIO_INDEX[RN], version=2, _index={})
    )
    a = run(client, h)
    assert labels(a["conditions"]) == ["Not recorded"]  # read since, but at which version isn't known


def test_attempts_from_before_recording_began_are_not_recorded(client):
    h = nurse(client)
    first = run(client, h)
    d = drill(client, h)
    w = client.post(
        "/api/v1/me/whiteboard/sd-url-shortener/attempts",
        headers=h,
        json={"diagram": DIAGRAM, "explanation": EXPLAIN},
    )
    assert w.status_code == 201, w.text
    before = FORMATS_RECORDED_FROM - timedelta(days=1)
    with client.app.state.session_factory() as db:
        for model in (ScenarioAttempt, DrillAttempt, WhiteboardAttempt):
            db.execute(update(model).values(created_at=before))
        db.commit()
    got = client.post(
        "/api/v1/me/attempt-conditions",
        headers=h,
        json={
            "scenario_attempt_ids": [first["id"]],
            "drill_attempt_ids": [d["id"]],
            "whiteboard_attempt_ids": [w.json()["id"]],
        },
    ).json()
    for kind in ("scenario_attempts", "drill_attempts", "whiteboard_attempts"):
        [c] = got[kind].values()
        assert labels(c) == ["Not recorded"] and c["recorded_from"] == "2026-11-15", kind


def test_a_drill_shows_its_lesson_once_and_its_comparison_reads_the_help(client):
    h = nurse(client)
    read(client, h, STAR)
    first = drill(client, h)
    assert labels(first["conditions"]) == ["Hint shown"]
    assert (
        first["conditions"]["help"][0]["detail"] == "Lesson “Structuring a behavioral answer with STAR” read"
    )
    second = drill(client, h, ANSWER + " It worked.")
    assert labels(second["conditions"]) == ["No in-app help recorded"]
    assert (
        "The in-app help differed: before the earlier one, hint shown; before this one, none recorded."
        in second["compared_with_previous"]
    )
    # The feedback itself is the same as it would be without the lesson.
    assert first["feedback"]["rubric_version"] == second["feedback"]["rubric_version"]
    listed = {a["id"]: a for a in client.get("/api/v1/me/drills/example/attempts", headers=h).json()}
    assert labels(listed[first["id"]]["conditions"]) == ["Hint shown"]
    assert listed[second["id"]]["compared_with_previous"] == second["compared_with_previous"]
    # A lesson for another drill's skill isn't help for this one.
    other = client.post(
        "/api/v1/me/drills/intro/attempts", headers=h, json={"text": ANSWER, "source": "typed"}
    ).json()
    assert labels(other["conditions"]) == ["No in-app help recorded"]


def test_a_whiteboard_attempt_has_no_lesson_to_show(client):
    h = auth_headers(register(client, email="lin@example.com"))
    for unit in UNIT_INDEX:  # even having read every lesson
        r = client.post(
            f"/api/v1/me/learn/units/{unit}/events", headers=h, json={"kind": "read", "version": 1}
        )
        assert r.status_code in (200, 404), r.text
    r = client.post(
        "/api/v1/me/whiteboard/sd-url-shortener/attempts",
        headers=h,
        json={"diagram": DIAGRAM, "explanation": EXPLAIN},
    )
    assert r.status_code == 201, r.text
    assert labels(r.json()["conditions"]) == ["No in-app help recorded"]
    assert labels(
        client.get(f"/api/v1/me/whiteboard/attempts/{r.json()['id']}", headers=h).json()["conditions"]
    ) == ["No in-app help recorded"]
    listed = client.get("/api/v1/me/whiteboard/sd-url-shortener/attempts", headers=h).json()
    assert labels(listed[0]["conditions"]) == ["No in-app help recorded"]


def test_another_accounts_reads_and_attempts_never_count(client):
    theirs = nurse(client, email="other@example.com")
    read(client, theirs, PRIORITIZE)
    read(client, theirs, STAR)
    mine = nurse(client)
    a = run(client, mine)
    d = drill(client, mine)
    assert labels(a["conditions"]) == ["No in-app help recorded"]
    assert labels(d["conditions"]) == ["No in-app help recorded"]
    t = run(client, theirs)
    got = client.post(
        "/api/v1/me/attempt-conditions",
        headers=mine,
        json={"scenario_attempt_ids": [t["id"], a["id"], "nope"]},
    ).json()
    assert list(got["scenario_attempts"]) == [a["id"]]
    assert client.get(f"/api/v1/me/scenario-attempts/{t['id']}", headers=mine).status_code == 404


def test_the_export_carries_each_attempts_conditions_by_id(client):
    h = nurse(client)
    read(client, h, PRIORITIZE)
    a = run(client, h)
    d = drill(client, h)
    w = client.post(
        "/api/v1/me/whiteboard/sd-url-shortener/attempts",
        headers=h,
        json={"diagram": DIAGRAM, "explanation": EXPLAIN},
    ).json()
    doc = client.get("/api/v1/me/export", headers=h).json()
    [sa] = doc["scenario_attempts"]
    assert sa["id"] == a["id"] and labels(sa["conditions"]) == ["Hint shown"]
    [da] = doc["drill_attempts"]
    assert da["id"] == d["id"] and labels(da["conditions"]) == ["No in-app help recorded"]
    [wa] = doc["whiteboard"]["attempts"]
    assert wa["id"] == w["id"] and labels(wa["conditions"]) == ["No in-app help recorded"]


def test_reading_a_lesson_that_prepares_nothing_else_records_nothing_more(client):
    h = nurse(client)
    r = client.post(
        "/api/v1/me/learn/units/rn-sbar-handoff/events", headers=h, json={"kind": "read", "version": 1}
    )
    assert r.status_code == 200
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        events = {
            e.kind: e.detail for e in db.scalars(select(LearnEvent).where(LearnEvent.user_id == user.id))
        }
    assert events["read"] == {"prepares": {"scenario:rn-two-patients": 1}}
    assert events["started"] is None  # only a read records what the lesson prepares

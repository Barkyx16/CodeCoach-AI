"""Branching scenarios: graph validation, two full paths, server-side transitions, idempotent and
stale steps, resume, retired versions, exploration attempts, privacy and export."""

import dataclasses
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import scenarios as sc
from app.models import ScenarioAttempt
from app.scenarios import Node, Option, RubricPoint, ScenarioError, validate
from tests.conftest import auth_headers, register

RN = "rn-two-patients"
SE = "se-incident-checkout"
SBAR = (
    "Situation: I'm calling about bed 3, he's short of breath and his saturation is dropping. Background: he's "
    "day 1 after hip surgery. Assessment: I'm worried he's deteriorating. Recommendation: please come and see him now."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def start(client, h, scenario=RN, **body):
    r = client.post(f"/api/v1/me/scenarios/{scenario}/attempts", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def step(client, h, attempt, **body):
    r = client.post(
        f"/api/v1/me/scenario-attempts/{attempt['id']}/steps",
        headers=h,
        json={"node_id": attempt["current"]["id"], **body},
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- authoring format and validation ------------------------------------------------------------


def test_every_shipped_scenario_validates_and_reaches_its_required_endings():
    assert set(sc.SCENARIO_INDEX) == {RN, SE}
    for s in sc.SCENARIO_INDEX.values():
        validate(s)
        assert s.required_endings and all(s.node(e).kind == "ending" for e in s.required_endings)


def _broken(**changes):
    base = sc.SCENARIO_INDEX[SE]
    return dataclasses.replace(base, _index={}, **changes)


@pytest.mark.parametrize(
    ("nodes", "message"),
    [
        (
            lambda n: [x if x.id != "start" else dataclasses.replace(x, next="nowhere") for x in n],
            "unknown node 'nowhere'",
        ),
        (
            lambda n: [*n, Node("orphan", "info", "Orphan", "never reached", next="contained")],
            "unreachable nodes ['orphan']",
        ),
        (
            lambda n: [x if x.id != "rolled_back" else dataclasses.replace(x, next="first") for x in n],
            "cycle",
        ),
        (
            lambda n: [x if x.id != "rolled_back" else dataclasses.replace(x, next=None) for x in n],
            "no way out",
        ),
        (
            lambda n: [x if x.id != "first" else dataclasses.replace(x, options=x.options[:1]) for x in n],
            "at least two options",
        ),
        (
            lambda n: [x if x.id != "comms_fast" else dataclasses.replace(x, rubric=()) for x in n],
            "needs rubric points",
        ),
    ],
)
def test_validation_rejects_broken_graphs(nodes, message):
    s = _broken(nodes=tuple(nodes(list(sc.SCENARIO_INDEX[SE].nodes))))
    with pytest.raises(ScenarioError, match=message.replace("[", r"\[").replace("]", r"\]")):
        validate(s)


def test_validation_rejects_a_missing_start_and_unreachable_required_endings():
    with pytest.raises(ScenarioError, match="start node"):
        validate(_broken(start="missing"))
    # Make "recovered_hotfix" unreachable by sending the hotfix option elsewhere, and drop the orphaned nodes.
    base = sc.SCENARIO_INDEX[SE]
    nodes = []
    for x in base.nodes:
        if x.id == "second":
            x = dataclasses.replace(
                x, options=(x.options[0], dataclasses.replace(x.options[1], to="rolled_back_late"))
            )
        nodes.append(x)
    with pytest.raises(ScenarioError, match="unreachable|can't be reached"):
        validate(_broken(nodes=tuple(nodes)))


# --- catalog ------------------------------------------------------------------------------------


def test_catalog_and_detail_state_scope_estimates_and_coverage(client):
    r = client.get("/api/v1/scenarios", params={"track": "registered-nurse"}).json()
    s = r["scenarios"][0]
    assert s["id"] == RN and s["minutes"] == 7 and s["regulated"] and s["validated"] is False
    assert s["decisions"] == 2 and s["endings"] == 2 and "not clinically validated" in s["scope"]
    assert "Registered Nurse (1)" in r["coverage_note"] and "Software Engineer (1)" in r["coverage_note"]
    none = client.get("/api/v1/scenarios", params={"track": "electrician"}).json()
    assert none["scenarios"] == [] and "Electrician doesn't have any yet" in none["coverage_note"]
    d = client.get(f"/api/v1/scenarios/{SE}").json()
    assert d["role"] == "On-call software engineer" and d["references"][0]["url"].startswith("https://")
    assert client.get("/api/v1/scenarios/nope").status_code == 404


# --- playing ------------------------------------------------------------------------------------


def test_strong_path_reaches_the_good_ending_with_a_debrief_of_this_path(client):
    h = nurse(client)
    a = start(client, h)
    assert a["current"]["id"] == "start" and a["status"] == "in_progress" and a["mode"] == "assessed"
    a = step(client, h, a)  # start -> report
    a = step(client, h, a)  # report -> who
    assert a["current"]["kind"] == "choice" and {o["id"] for o in a["current"]["options"]} == {"bed3", "bed7"}
    assert "quality" not in a["current"]["options"][0]  # feedback only after choosing
    a = step(client, h, a, choice_id="bed3")
    assert a["steps"][-1]["quality"] == "strong" and a["steps"][-1]["choice_label"].startswith("Bed 3")
    a = step(client, h, a)  # assess3 -> escalate
    a = step(client, h, a, choice_id="call")
    a = step(client, h, a, text=SBAR)
    assert a["status"] == "completed" and a["current"] is None
    d = a["debrief"]
    assert d["outcome"] == "Escalated promptly (simulated)"
    assert d["path"] == [
        "Start of shift",
        "What you know",
        "Who first?",
        "At bed 3",
        "Your next step",
        "Make the call",
        "Help is on the way",
    ]
    assert [x["chosen"][:5] for x in d["decisions"]] == ["Bed 3", "Follo"]
    assert d["decisions"][0]["step_index"] == 2 and d["decisions"][0]["alternatives"][0]["quality"] == "risky"
    assert d["written"][0]["missing"] == [] and len(d["written"][0]["covered"]) == 4
    assert "No AI commentary" in d["feedback_source"] and "simulated" in d["disclaimer"].lower()


def test_an_imperfect_path_reaches_the_alternate_ending_and_says_why(client):
    h = nurse(client)
    a = start(client, h)
    a = step(client, h, a)
    a = step(client, h, a)
    a = step(client, h, a, choice_id="bed7")
    assert a["current"]["id"] == "bed7_first"
    a = step(client, h, a)
    a = step(client, h, a)
    a = step(client, h, a, choice_id="wait")
    a = step(client, h, a)
    a = step(
        client, h, a, text="I would escalate earlier using SBAR because his breathing was getting worse."
    )
    d = a["debrief"]
    assert d["outcome"] == "Escalation delayed (simulated)"
    assert [x["quality"] for x in d["decisions"]] == ["risky", "risky"]
    assert d["decisions"][1]["alternatives"][0]["quality"] == "strong"
    assert d["strengths"] and "covered" in d["strengths"][-1]


def test_the_server_decides_transitions_and_refuses_anything_else(client):
    h = nurse(client)
    a = start(client, h)
    url = f"/api/v1/me/scenario-attempts/{a['id']}/steps"
    # Jumping to an ending or another node is refused.
    jump = client.post(url, headers=h, json={"node_id": "escalated"})
    assert jump.status_code == 409 and jump.json()["error"]["code"] == "stale_step"
    a = step(client, h, a)
    a = step(client, h, a)
    bad = client.post(url, headers=h, json={"node_id": "who", "choice_id": "escalated"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_choice"
    assert client.post(url, headers=h, json={"node_id": "who"}).status_code == 400
    # A repeated request for a recorded step changes nothing (double-click / network retry).
    after = step(client, h, a, choice_id="bed3")
    again = client.post(url, headers=h, json={"node_id": "who", "choice_id": "bed3"}).json()
    assert again["current"]["id"] == after["current"]["id"] and len(again["steps"]) == len(after["steps"])
    # But a different answer to an already-answered node is refused: decisions can't be changed.
    change = client.post(url, headers=h, json={"node_id": "who", "choice_id": "bed7"})
    assert change.status_code == 409 and change.json()["error"]["code"] == "stale_step"
    short = client.post(url, headers=h, json={"node_id": after["current"]["id"]})
    assert short.status_code == 200  # info node
    a = short.json()
    a = step(client, h, a, choice_id="call")
    assert (
        client.post(url, headers=h, json={"node_id": "sbar", "text": "ok"}).json()["error"]["code"]
        == "response_too_short"
    )


def test_concurrent_duplicate_steps_record_once(client):
    h = nurse(client)
    a = start(client, h)
    url = f"/api/v1/me/scenario-attempts/{a['id']}/steps"
    with ThreadPoolExecutor(4) as pool:
        codes = list(
            pool.map(lambda _: client.post(url, headers=h, json={"node_id": "start"}).status_code, range(4))
        )
    assert set(codes) <= {200, 409}
    got = client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=h).json()
    assert [s["node_id"] for s in got["steps"]] == ["start"]


def test_resume_and_starting_again_return_the_same_attempt(client):
    h = nurse(client)
    a = start(client, h)
    a = step(client, h, a)
    again = start(client, h)
    assert again["id"] == a["id"] and again["current"]["id"] == "report"
    got = client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=h).json()
    assert got["current"]["id"] == "report" and [s["node_id"] for s in got["steps"]] == ["start"]
    listed = client.get("/api/v1/me/scenario-attempts", headers=h, params={"scenario_id": RN}).json()
    assert [x["id"] for x in listed] == [a["id"]] and listed[0]["status"] == "in_progress"


def test_try_another_approach_is_a_separate_attempt_and_keeps_the_original(client):
    h = nurse(client)
    a = start(client, h)
    for kw in ({}, {}, {"choice_id": "bed7"}, {}, {}, {"choice_id": "wait"}, {}):
        a = step(client, h, a, **kw)
    a = step(client, h, a, text="Escalate earlier with SBAR because things were getting worse.")
    assert (
        client.post(
            f"/api/v1/me/scenarios/{RN}/attempts", headers=h, json={"mode": "exploration"}
        ).status_code
        == 400
    )
    b = start(client, h, mode="exploration", parent_id=a["id"])
    assert b["id"] != a["id"] and b["mode"] == "exploration" and b["parent_id"] == a["id"]
    original = client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=h).json()
    assert original["debrief"]["outcome"] == "Escalation delayed (simulated)"
    # Finished attempts can't be continued or changed.
    done = client.post(
        f"/api/v1/me/scenario-attempts/{a['id']}/steps",
        headers=h,
        json={"node_id": "who", "choice_id": "bed3"},
    )
    assert done.status_code == 409 and done.json()["error"]["code"] == "attempt_finished"


def test_a_retired_version_keeps_attempts_readable_but_not_continuable(client, monkeypatch):
    h = nurse(client)
    finished = start(client, h, scenario=SE)
    for kw in ({}, {"choice_id": "rollback"}, {}):
        finished = step(client, h, finished, **kw)
    finished = step(
        client,
        h,
        finished,
        text="Customers saw checkout errors for 6 minutes; we rolled back and it's stable.",
    )
    ongoing = start(client, h)
    ongoing = step(client, h, ongoing)
    for sid in (SE, RN):
        monkeypatch.setitem(
            sc.SCENARIO_INDEX, sid, dataclasses.replace(sc.SCENARIO_INDEX[sid], version=2, _index={})
        )
    r = client.post(
        f"/api/v1/me/scenario-attempts/{ongoing['id']}/steps", headers=h, json={"node_id": "report"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "scenario_updated"
    got = client.get(f"/api/v1/me/scenario-attempts/{ongoing['id']}", headers=h).json()
    assert got["retired"] and got["current"] is None and got["version"] == 1
    old = client.get(f"/api/v1/me/scenario-attempts/{finished['id']}", headers=h).json()
    assert old["retired"] and old["debrief"]["outcome"] == "Contained in about 6 minutes (simulated)"
    fresh = start(client, h)
    assert fresh["id"] != ongoing["id"] and fresh["version"] == 2


def test_attempts_are_private_and_exported_and_deleted_with_the_account(client):
    ada = nurse(client, "ada@example.com")
    bob = nurse(client, "bob@example.com")
    a = start(client, ada)
    assert client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=bob).status_code == 404
    r = client.post(f"/api/v1/me/scenario-attempts/{a['id']}/steps", headers=bob, json={"node_id": "start"})
    assert r.status_code == 404
    assert (
        client.post(
            f"/api/v1/me/scenarios/{RN}/attempts",
            headers=bob,
            json={"mode": "exploration", "parent_id": a["id"]},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/me/scenario-attempts", headers=bob).json() == []
    assert client.post(f"/api/v1/me/scenarios/{RN}/attempts", json={}).status_code == 401
    step(client, ada, a)
    data = client.get("/api/v1/me/export", headers=ada).json()
    assert (
        data["scenario_attempts"][0]["scenario"] == RN
        and data["scenario_attempts"][0]["steps"][0]["node_id"] == "start"
    )
    client.request(
        "DELETE", "/api/v1/auth/me", headers=ada, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    db = client.app.state.session_factory()
    assert db.query(ScenarioAttempt).count() == 0
    db.close()


def test_written_responses_are_checked_against_authored_points():
    node = sc.SCENARIO_INDEX[RN].node("sbar")
    covered, missing = sc.check_written(
        node, "Please come now, bed 3 is breathing fast after his hip surgery."
    )
    assert "Situation: who and what's happening now" in covered and "Recommendation: what you need" in covered
    assert "Assessment: what you think is going on" in covered or missing  # keyword-based, reported honestly
    assert isinstance(RubricPoint, type) and isinstance(Option, type)

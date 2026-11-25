"""Work-queue scenarios (Volume 10, prompt 7; docs/SCENARIOS.md, "Work queues"): several valid
orders, a broken dependency and a missed hard deadline routed by the graph, reasoning required,
orders the server refuses, altered client steps, plans judged on what was known at the time,
recorded versions, no AI, ownership, export, and the authoring checks. Synthetic accounts."""

from __future__ import annotations

import dataclasses

import pytest

from app import scenarios as sc
from app.scenarios import Dependency, ScenarioError, Strategy, Task, validate
from tests.conftest import auth_headers, register

IT = "it-morning-queue"
LOG = "logistics-dispatch-queue"
WHY = "I'd start here because three people can't work, then tell Priya's manager about 09:30."


def person(client, email="ada@example.com", track="it-support-specialist"):
    return auth_headers(register(client, email=email, career_track=track))


def start(client, h, scenario):
    r = client.post(f"/api/v1/me/scenarios/{scenario}/attempts", headers=h, json={})
    assert r.status_code == 200, r.text
    return r.json()


def send(client, h, attempt, **body):
    return client.post(
        f"/api/v1/me/scenario-attempts/{attempt['id']}/steps",
        headers=h,
        json={"node_id": attempt["current"]["id"], **body},
    )


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def test_the_catalog_marks_queues_and_the_page_gets_every_fact(client):
    h = person(client)
    listed = client.get("/api/v1/scenarios", params={"track": "it-support-specialist"}).json()["scenarios"]
    assert [(s["id"], s["queue"], s["decisions"]) for s in listed] == [(IT, True, 1)]
    a = start(client, h, IT)
    cur = a["current"]
    assert cur["kind"] == "prioritize" and cur["clock"] == "08:45"
    assert [t["id"] for t in cur["tasks"]] == ["vpn", "newhire", "board", "locked", "printer"]
    assert cur["tasks"][1]["due"] == "09:30" and "Priya starts at 09:30" in cur["tasks"][1]["facts"][0]
    assert "strateg" not in str(cur).lower()  # the strategies are for the debrief, not hints


def test_two_different_orders_are_both_valid_and_neither_is_the_right_one(client):
    debriefs = []
    for email, order in (
        ("ada@example.com", ["vpn", "newhire", "board", "locked", "printer"]),
        ("bea@example.com", ["newhire", "board", "vpn", "locked", "printer"]),
    ):
        h = person(client, email)
        done = ok(send(client, h, start(client, h, IT), order=order, text=WHY))
        assert (
            done["status"] == "completed"
            and done["debrief"]["outcome"] == "Queue cleared by 09:50 (simulated)"
        )
        debriefs.append(done["debrief"])
    first, second = (d["plans"][0] for d in debriefs)
    assert first["violations"] == [] and second["violations"] == []
    assert [s["label"] for s in first["follows"]] == ["Most people blocked first"]
    assert [s["label"] for s in second["follows"]] == ["Fixed times first"]
    assert {s["label"] for s in first["others"]} == {"Fixed times first", "A five-minute unblock first"}
    assert all("gives up" in s["explanation"] for s in first["follows"] + first["others"])
    # The case's own times, computed on the server: Priya's account is ready at 09:20 or 09:00.
    assert [(p["id"], p["finish"]) for p in first["plan"]][:2] == [("vpn", "09:05"), ("newhire", "09:20")]
    assert second["plan"][0] == {
        "id": "newhire",
        "title": "New starter's account",
        "start": "08:45",
        "finish": "09:00",
        "due": "09:30",
        "late": False,
    }
    assert "no single right order" in debriefs[0]["summary"]


def test_a_soft_deadline_missed_is_shown_but_not_called_impossible(client):
    h = person(client)
    done = ok(
        send(
            client, h, start(client, h, IT), order=["vpn", "printer", "newhire", "board", "locked"], text=WHY
        )
    )
    on_time = next(p for p in done["debrief"]["plans"][0]["plan"] if p["id"] == "newhire")
    assert (on_time["finish"], on_time["late"]) == ("09:30", False)  # exactly on time isn't late
    h2 = person(client, "bea@example.com")
    done = ok(
        send(
            client,
            h2,
            start(client, h2, IT),
            order=["vpn", "board", "printer", "locked", "newhire"],
            text=WHY,
        )
    )
    plan = done["debrief"]["plans"][0]
    assert next(p for p in plan["plan"] if p["id"] == "newhire") == {
        "id": "newhire",
        "title": "New starter's account",
        "start": "09:35",
        "finish": "09:50",
        "due": "09:30",
        "late": True,
    }
    assert plan["violations"] == []  # a soft deadline is a tradeoff, not a broken constraint


def test_a_broken_dependency_is_named_and_the_graph_decides_what_happens(client):
    h = person(client, track="logistics-coordinator")
    a = start(client, h, LOG)
    a = ok(
        send(
            client,
            h,
            a,
            order=["labels", "pick", "truck", "returns", "supplier"],
            text="Labels first, then the list, then I call the carrier.",
        )
    )
    step = a["steps"][-1]
    assert step["kind"] == "prioritize" and [v["kind"] for v in step["violations"]] == ["dependency"]
    assert "the label system reads the box count from the pick list" in step["violations"][0]["text"]
    assert a["current"]["id"] == "stalled_plan"  # the authored consequence, not the client's choice
    a = ok(send(client, h, a))
    assert a["current"]["id"] == "call"
    a = ok(send(client, h, a))
    assert a["current"]["id"] == "replan" and "courier" in [t["id"] for t in a["current"]["tasks"]]
    good = ["pick", "labels", "courier", "truck", "returns", "supplier"]
    a = ok(
        send(
            client,
            h,
            a,
            order=good,
            text="Urgent chain first for the 10:00 sports day, then I call the carrier before 09:00.",
        )
    )
    assert a["status"] == "completed" and a["debrief"]["outcome"] == "Everything ships (simulated)"
    plans = a["debrief"]["plans"]
    assert [p["title"] for p in plans] == ["08:00: plan the morning", "08:10: re-plan with what you know now"]
    # Each plan is judged on what had been said by then: the first knew nothing of the courier.
    assert (
        "courier" not in [t["id"] for t in plans[0]["known"]]
        and "08:10: new information" not in plans[0]["learned_before"]
    )
    assert "08:10: new information" in plans[1]["learned_before"] and plans[1]["violations"] == []
    assert [s["label"] for s in plans[1]["follows"]] == ["The urgent chain first"]
    assert next(p for p in plans[1]["plan"] if p["id"] == "truck")["finish"] == "08:45"


def test_a_missed_hard_deadline_is_a_broken_constraint(client):
    h = person(client, track="logistics-coordinator")
    a = start(client, h, LOG)
    a = ok(
        send(
            client,
            h,
            a,
            order=["pick", "labels", "returns", "supplier", "truck"],
            text="Pickers first, then labels, the dock, the supplier and the truck.",
        )
    )
    v = a["steps"][-1]["violations"]
    assert v == [
        {
            "kind": "deadline",
            "text": "Confirm the 11:00 truck has to be finished by 09:00; in this order it finishes at 09:05.",
        }
    ]
    a = ok(send(client, h, ok(send(client, h, a))))
    bad = ["pick", "courier", "labels", "truck", "returns", "supplier"]  # the courier needs the labels
    a = ok(send(client, h, a, order=bad, text="Pick list, courier, labels, then the truck before 09:00."))
    assert (
        a["status"] == "completed" and a["debrief"]["outcome"] == "A hard constraint was broken (simulated)"
    )
    assert not any("meets every hard constraint" in s for s in a["debrief"]["strengths"])


def test_reasoning_is_required_and_kept_as_plain_text(client):
    h = person(client)
    a = start(client, h, IT)
    order = ["vpn", "newhire", "board", "locked", "printer"]
    r = send(client, h, a, order=order, text="vpn first")
    assert r.status_code == 400 and r.json()["error"]["code"] == "reasoning_required"
    assert send(client, h, a, order=order).json()["error"]["code"] == "reasoning_required"
    hostile = '<img src=x onerror="alert(1)"> three people can\'t work, so VPN first'
    done = ok(send(client, h, a, order=order, text=hostile + "\x00\x07"))
    assert done["debrief"]["plans"][0]["response"] == hostile
    assert done["debrief"]["plans"][0]["covered"] == ["Impact: who is blocked, and how many"]


@pytest.mark.parametrize(
    "order",
    [
        ["vpn", "newhire", "board", "locked"],  # one left out
        ["vpn", "vpn", "newhire", "board", "locked"],  # twice
        ["vpn", "newhire", "board", "locked", "coffee"],  # not in the case
        [],
        None,
    ],
)
def test_an_order_must_hold_every_task_once(client, order):
    h = person(client)
    a = start(client, h, IT)
    r = send(client, h, a, order=order, text=WHY)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_order"
    again = client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=h).json()
    assert again["steps"] == [] and again["current"]["id"] == "queue"


def test_a_client_cant_skip_ahead_or_bring_its_own_facts(client):
    h = person(client, track="logistics-coordinator")
    a = start(client, h, LOG)
    url = f"/api/v1/me/scenario-attempts/{a['id']}/steps"
    good = {
        "order": ["truck", "pick", "labels", "returns", "supplier"],
        "text": "I call the carrier first, then the pickers.",
    }
    for node in ("replan", "shipped", "call"):  # later nodes, an ending
        r = client.post(url, headers=h, json={"node_id": node, **good})
        assert r.status_code == 409 and r.json()["error"]["code"] == "stale_step"
    r = client.post(url, headers=h, json={"node_id": "plan", "choice_id": "shipped"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_order"
    # Extra fields (its own deadlines, minutes or a verdict) are ignored: the case's facts decide.
    r = ok(
        client.post(
            url,
            headers=h,
            json={
                "node_id": "plan",
                **good,
                "tasks": [{"id": "truck", "due": "23:59", "minutes": 0}],
                "violations": [],
            },
        )
    )
    truck = next(p for p in r["steps"][-1]["plan"] if p["id"] == "truck")
    assert (truck["due"], truck["finish"]) == ("09:00", "08:05")
    again = client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=h).json()
    same = ok(client.post(url, headers=h, json={"node_id": "plan", **good}))  # a repeat: unchanged
    assert len(same["steps"]) == len(again["steps"]) == 1
    # The same node with another order isn't a repeat: that step is over.
    other = {**good, "order": ["pick", "truck", "labels", "returns", "supplier"]}
    r = client.post(url, headers=h, json={"node_id": "plan", **other})
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_step"


def test_the_debrief_reads_the_version_recorded_at_the_time(client, monkeypatch):
    h = person(client)
    done = ok(
        send(
            client, h, start(client, h, IT), order=["vpn", "newhire", "board", "locked", "printer"], text=WHY
        )
    )
    old = sc.SCENARIO_INDEX[IT]
    queue = old.node("queue")
    edited = dataclasses.replace(
        queue,
        tasks=(dataclasses.replace(queue.tasks[0], minutes=45, facts=("Rewritten.",)), *queue.tasks[1:]),
    )
    monkeypatch.setitem(
        sc.SCENARIO_INDEX, IT, dataclasses.replace(old, version=2, nodes=(edited, *old.nodes[1:]), _index={})
    )
    again = client.get(f"/api/v1/me/scenario-attempts/{done['id']}", headers=h).json()
    assert again["retired"] and again["version"] == 1
    plan = again["debrief"]["plans"][0]
    assert (
        plan["known"][0]["facts"][0].startswith("Since 08:30, three people")
        and plan["known"][0]["minutes"] == 20
    )
    assert plan["plan"][0]["finish"] == "09:05"


def test_queues_work_the_same_when_the_ai_coach_is_unavailable(client):
    class Down:
        name, model = "anthropic", "m"

        def __getattr__(self, _):
            raise AssertionError("queues don't call the AI coach")

    client.app.state.ai_provider = Down()
    h = person(client)
    done = ok(
        send(
            client, h, start(client, h, IT), order=["locked", "vpn", "newhire", "board", "printer"], text=WHY
        )
    )
    assert "No AI commentary" in done["debrief"]["feedback_source"]
    assert {s["label"] for s in done["debrief"]["plans"][0]["follows"]} == {
        "Most people blocked first",
        "A five-minute unblock first",
    }


def test_another_account_cant_read_or_step_and_export_keeps_the_order(client):
    ada = person(client)
    bea = person(client, "bea@example.com")
    secret = "ADA-QUEUE-7781"
    a = start(client, ada, IT)
    assert client.get(f"/api/v1/me/scenario-attempts/{a['id']}", headers=bea).status_code == 404
    order = ["vpn", "newhire", "board", "locked", "printer"]
    assert send(client, bea, a, order=order, text=WHY).status_code == 404
    ok(send(client, ada, a, order=order, text=f"{WHY} {secret}"))
    exported = client.get("/api/v1/me/export", headers=ada).json()
    rows = [x for x in exported["scenario_attempts"] if x["scenario"] == IT]
    queue = next(s for s in rows[0]["steps"] if s["kind"] == "prioritize")
    assert queue["order"] == order and queue["response"].endswith(secret)
    assert secret not in client.get("/api/v1/me/export", headers=bea).text


def _queue(**changes):
    base = sc.SCENARIO_INDEX[LOG]
    plan = dataclasses.replace(base.node("plan"), **changes)
    return dataclasses.replace(base, nodes=(plan, *base.nodes[1:]), _index={})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"dependencies": (Dependency("pick", "labels", "x"), Dependency("labels", "pick", "y"))}, "circle"),
        ({"dependencies": (Dependency("pick", "nope", "x"),)}, "needs two of its tasks"),
        ({"strategies": sc.SCENARIO_INDEX[LOG].node("plan").strategies[:1]}, "at least two strategies"),
        ({"rubric": ()}, "rubric points"),
        (
            {
                "strategies": (
                    Strategy(
                        "late",
                        "Truck last",
                        (("supplier", "truck"), ("returns", "truck"), ("labels", "truck")),
                        "x",
                    ),
                    Strategy("ok", "Fine", (("pick", "labels"),), "y"),
                )
            },
            "can't be followed",
        ),
        (
            {
                "tasks": tuple(
                    dataclasses.replace(t, due="08:05", due_is_hard=True)
                    if t.id in ("truck", "returns")
                    else t
                    for t in sc.SCENARIO_INDEX[LOG].node("plan").tasks
                )
            },
            "no order meets every hard constraint",
        ),
        ({"tasks": (Task("a", "A", ("x",), 5), Task("b", "B", ("y",), 5))}, "3 to 8 tasks"),
    ],
)
def test_the_validator_refuses_queues_the_case_cant_support(changes, message):
    with pytest.raises(ScenarioError, match=message):
        validate(_queue(**changes))


def test_only_a_queue_has_tasks():
    base = sc.SCENARIO_INDEX[LOG]
    call = dataclasses.replace(base.node("call"), tasks=base.node("plan").tasks)
    bad = dataclasses.replace(base, nodes=tuple(call if n.id == "call" else n for n in base.nodes), _index={})
    with pytest.raises(ScenarioError, match="only a prioritize node has tasks"):
        validate(bad)

"""Scenario runs compared with the run before by the one contract (Volume 20, prompt 2;
docs/COMPARING_ATTEMPTS.md, "Scenario runs"). Only finished, assessed runs of the same scenario are
compared: an exploration or a run in progress says why it isn't. What's set side by side is each
run's choices' authored qualities, any order that broke a hard constraint, and the ending; the
decisions a run faced are its path. The same decisions, version and help: comparable. A different
path: partly comparable, the decisions side by side and not the counts. A different version: not
comparable. The run's page, History and the export say the same. Synthetic accounts only."""

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.careers.comparability import AttemptFacts, classify
from app.models import ScenarioAttempt
from app.services.attempt_comparisons import (
    EXPLORATION_RUN,
    FIRST_SCENARIO_RUN,
    SCENARIO_RULES,
    UNFINISHED_RUN,
)
from tests.test_history_practice import feed
from tests.test_scenarios import RN, SBAR, nurse, start, step

ATTEMPT = "/api/v1/me/scenario-attempts"


def strong(client, h):
    """Bed 3 first, then the call, then SBAR: the scenario's strong path."""
    a = start(client, h)
    for kw in ({}, {}, {"choice_id": "bed3"}, {}, {"choice_id": "call"}, {"text": SBAR}):
        a = step(client, h, a, **kw)
    assert a["status"] == "completed"
    return a


def imperfect(client, h):
    """Bed 7 first, then waiting: another path through the same scenario."""
    a = start(client, h)
    for kw in ({}, {}, {"choice_id": "bed7"}, {}, {}, {"choice_id": "wait"}, {}):
        a = step(client, h, a, **kw)
    a = step(
        client, h, a, text="I would escalate earlier using SBAR because his breathing was getting worse."
    )
    assert a["status"] == "completed"
    return a


def finish(client, h, a):
    """Whatever path it's on: the first option at each choice, SBAR when asked to write."""
    while a["status"] == "in_progress":
        node = a["current"]
        if node["kind"] == "choice":
            a = step(client, h, a, choice_id=node["options"][0]["id"])
        elif node["kind"] == "written":
            a = step(client, h, a, text=SBAR)
        else:
            a = step(client, h, a)
    return a


def read(client, h, attempt):
    r = client.get(f"{ATTEMPT}/{attempt['id']}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def facts(**changes) -> AttemptFacts:
    base = dict(
        id="a",
        track="scenario",
        question_id=RN,
        question_version=1,
        scale=SCENARIO_RULES,
        rubric=SCENARIO_RULES,
        source="rules",
        scoring="scored",
        format="single",
        help=("No in-app help recorded",),
        kind="scenario",
        path=("who", "escalate", "call_text"),
    )
    return AttemptFacts(**{**base, **changes})


PAIRS = [
    # (what differs in the later run, outcome, scores comparable, a phrase the explanation says)
    ({}, "comparable", True, "Comparable: the same scenario and version, the same decisions faced"),
    (
        {"path": ("who", "bed7_choice", "call_text")},
        "partially_comparable",
        False,
        "the runs took different paths: 2 of the decisions were the same, of 3 in the earlier run and 3 in this one",
    ),
    (
        {"question_version": 2, "path": ("who", "x")},
        "incompatible",
        False,
        "the scenario's decisions changed in between (version 1, now 2)",
    ),
    (
        {"help": ("Lesson read",)},
        "partially_comparable",
        True,
        "The choices were the same decisions with the same authored qualities, so both are shown",
    ),
    ({"scoring": "not_judged"}, "incompatible", False, "this one wasn't assessed"),
]


@pytest.mark.parametrize(("change", "outcome", "scores", "says"), PAIRS)
def test_the_contract_rule_for_scenarios(change, outcome, scores, says):
    c = classify(facts(), facts(id="b", **change))
    assert (c.outcome, c.scores_comparable) == (outcome, scores)
    assert says in c.explanation, c.explanation
    assert c.explanation.endswith("(Comparison rules v1)")


def test_the_same_decisions_twice_are_comparable_with_both_results_as_given(client):
    h = nurse(client)
    first = strong(client, h)
    second = strong(client, h)
    page = read(client, h, second)
    assert page["not_compared"] is None
    c = page["compared"]
    assert c["previous"]["id"] == first["id"]
    assert c["comparison"]["against"] == first["id"]
    # Each run's own result, as its steps recorded it.
    assert (
        c["result"]
        == c["previous"]["result"]
        == ("2 strong, 0 acceptable, 0 risky · ended: Escalated promptly (simulated)")
    )
    assert (c["comparison"]["outcome"], c["comparison"]["reasons"]) == ("comparable", [])
    assert c["comparison"]["explanation"] == (
        "Comparable: the same scenario and version, the same decisions faced, with the same in-app help. "
        "(Comparison rules v1)"
    )
    assert read(client, h, first)["not_compared"] == FIRST_SCENARIO_RUN


def test_a_different_path_is_partly_comparable_and_says_which_decisions_differed(client):
    h = nurse(client)
    first = strong(client, h)
    second = imperfect(client, h)
    c = read(client, h, second)["compared"]["comparison"]
    assert c["outcome"] == "partially_comparable" and c["scores_comparable"] is False
    path = next(r for r in c["reasons"] if r["rule"] == "path")
    assert path["kind"] == "partial_text" and "the runs took different paths" in path["text"]
    assert "set the decisions side by side, not the counts" in c["explanation"]
    assert read(client, h, second)["compared"]["result"] == (
        "0 strong, 0 acceptable, 2 risky · ended: Escalation delayed (simulated)"
    )
    assert read(client, h, second)["compared"]["previous"]["id"] == first["id"]


def test_an_exploration_or_a_run_in_progress_says_why_it_isnt_compared(client):
    h = nurse(client)
    first = imperfect(client, h)
    explore = finish(client, h, start(client, h, mode="exploration", parent_id=first["id"]))
    assert read(client, h, explore)["not_compared"] == EXPLORATION_RUN
    going = step(client, h, start(client, h))
    assert going["status"] == "in_progress"
    assert read(client, h, going)["not_compared"] == UNFINISHED_RUN
    # An exploration is never the run a later one is compared with: the latest finished, assessed one is.
    going = finish(client, h, going)
    later = strong(client, h)
    assert read(client, h, later)["compared"]["previous"]["id"] == going["id"] != explore["id"]


def test_a_different_version_is_not_comparable(client):
    h = nurse(client)
    first = strong(client, h)
    with client.app.state.session_factory() as db:
        db.execute(update(ScenarioAttempt).where(ScenarioAttempt.id == first["id"]).values(version=0))
        db.commit()
    second = strong(client, h)
    c = read(client, h, second)["compared"]["comparison"]
    assert c["outcome"] == "incompatible"
    assert "the scenario's decisions changed in between (version 0, now 1)" in c["explanation"]


def test_history_and_the_export_say_what_the_page_says(client):
    h = nurse(client)
    first = strong(client, h)
    second = imperfect(client, h)
    rows = {i["target"]["attempt_id"]: i for i in feed(client, h, type="scenario_attempt")["items"]}
    assert rows[second["id"]]["detail"].endswith("· Partly comparable with the one before")
    assert rows[first["id"]]["detail"].endswith(f"· {FIRST_SCENARIO_RUN}")
    exported = {r["id"]: r for r in client.get("/api/v1/me/export", headers=h).json()["scenario_attempts"]}
    page = read(client, h, second)["compared"]["comparison"]
    assert exported[second["id"]]["compared"] == {
        "against": first["id"],
        "outcome": "partially_comparable",
        "text": "Partly comparable with the one before",
        "explanation": page["explanation"],
        "contract_version": 1,
    }
    assert exported[second["id"]]["not_compared"] is None
    assert exported[first["id"]]["compared"] is None
    assert exported[first["id"]]["not_compared"] == FIRST_SCENARIO_RUN


def test_another_accounts_run_is_never_the_one_before(client):
    bea = nurse(client, "bea@example.com")
    strong(client, bea)
    h = nurse(client)
    mine = strong(client, h)
    assert read(client, h, mine)["not_compared"] == FIRST_SCENARIO_RUN

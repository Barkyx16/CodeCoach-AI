"""Learn mode: content integrity, progress events, the comprehension check, versions, practice
evidence, the practice-plan contract, and that reading never counts as mastery."""

import dataclasses

import pytest

from app import learn as learn_pkg
from app.careers import CATALOG
from app.careers.questions import get_question
from app.careers.skills import career_skills
from app.learn import UNIT_INDEX, units_for
from app.models import LearnEvent
from tests.conftest import auth_headers, register

SE_UNIT = "se-hash-map-lookup"
RN_UNIT = "rn-sbar-handoff"
GOOD = (
    "Situation: the patient in bed 4 has new chest pain. Background: two days after surgery. Assessment: "
    "I'm worried about his heart, so I checked his vital signs and ran an ECG per protocol. Recommendation: "
    "please see him now. I read back the orders, documented the call and handed off to the next nurse."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def right_answers(unit_id):
    return {c.id: c.answer for c in UNIT_INDEX[unit_id].check}


# --- content integrity -------------------------------------------------------------------------


def test_every_unit_is_complete_and_points_at_real_practice(client):
    assert {u.track for u in UNIT_INDEX.values()} == {"software-engineer", "registered-nurse"}
    db = client.app.state.session_factory()
    from app.models import Problem

    slugs = {s for (s,) in db.query(Problem.slug).all()}
    db.close()
    for u in UNIT_INDEX.values():
        assert u.track in CATALOG and u.version >= 1 and len(u.changes) >= 1
        assert u.objective and u.explanation and u.example.walkthrough and u.mistakes
        assert len(u.check) >= 3 and all(0 <= c.answer < len(c.options) for c in u.check)
        assert len({c.id for c in u.check}) == len(u.check)
        e = u.exercise
        assert all((e.think, e.concept, e.example, e.explanation, e.solution))
        for p in u.prerequisites:
            assert p in UNIT_INDEX and UNIT_INDEX[p].track == u.track and p != u.id
        if u.skill is not None:
            assert u.skill in career_skills(u.track), u.id
        if u.practice.kind == "question":
            assert get_question(u.track, u.practice.ref_id) is not None
        else:
            assert u.practice.ref_id in slugs
        for qid in u.question_ids:
            assert get_question(u.track, qid) is not None
        assert u.review.status in ("author_reviewed", "generated_draft")
        for r in u.references:
            # A link is either absent or a real https URL; never a placeholder.
            assert r.url is None or r.url.startswith("https://")
            assert r.kind in ("external", "repository")
    # Regulated careers carry a visible scope note.
    assert all(
        u.scope_note and "not clinical guidance" in u.scope_note for u in units_for("registered-nurse")
    )


def test_catalog_states_coverage_honestly(client):
    r = client.get("/api/v1/learn", params={"track": "registered-nurse"}).json()
    assert [u["id"] for u in r["units"]] == ["rn-star-answers", "rn-sbar-handoff", "rn-prioritization"]
    assert {c["track"]: c["units"] for c in r["careers_with_units"]} == {
        "registered-nurse": 3,
        "software-engineer": 3,
    }
    prio = r["units"][2]
    assert prio["prerequisites"] == [{"id": "rn-sbar-handoff", "title": "SBAR for handoffs and escalation"}]
    assert prio["regulated"] and prio["review_status"] == "author_reviewed"
    none = client.get("/api/v1/learn", params={"track": "electrician"}).json()
    assert none["units"] == [] and "Electrician doesn't have any yet" in none["coverage_note"]
    assert client.get("/api/v1/learn", params={"track": "astronaut"}).status_code == 404


def test_a_unit_never_reveals_check_answers(client):
    u = client.get(f"/api/v1/learn/units/{SE_UNIT}").json()
    assert u["career_title"] == "Software Engineer" and u["version"] == 1
    assert [c.keys() for c in u["check"]] and all(set(c) == {"id", "prompt", "options"} for c in u["check"])
    assert len(u["exercise"]["guided_steps"]) == 4 and u["exercise"]["solution"]
    assert u["practice"] == {
        "kind": "problem",
        "ref_id": "two-sum",
        "label": "Solve Two Sum",
        "href": "/problems/two-sum",
    }
    refs = {r["title"]: r for r in u["references"]}
    assert refs["Class HashMap<K,V> (java.util)"]["url"].startswith("https://docs.oracle.com/")
    rn = client.get(f"/api/v1/learn/units/{RN_UNIT}").json()
    ihi = next(r for r in rn["references"] if "SBAR" in r["title"])
    assert ihi["url"] is None and "No link recorded" in ihi["note"]  # never a guessed link
    assert "jurisdiction" in rn["scope_note"]
    assert client.get("/api/v1/learn/units/nope").status_code == 404


def test_related_units_for_questions_and_problems(client):
    r = client.get(
        "/api/v1/learn/related", params={"track": "registered-nurse", "question_id": "e-steps-7"}
    ).json()
    assert [u["id"] for u in r] == [RN_UNIT]
    p = client.get("/api/v1/learn/related", params={"problem_slug": "longest-unique-substring"}).json()
    assert {u["id"] for u in p} == {
        "se-sliding-window",
        SE_UNIT,
    }  # its practice action, and the hash-maps topic
    assert (
        client.get("/api/v1/learn/related", params={"track": "registered-nurse", "question_id": "zzz"}).json()
        == []
    )


# --- progress events ---------------------------------------------------------------------------


def test_events_are_distinct_and_reading_is_not_mastery(client):
    h = nurse(client)
    p = client.get(f"/api/v1/me/learn/units/{RN_UNIT}", headers=h).json()
    assert not p["started"] and p["next_action"]["kind"] == "read"
    for _ in range(2):  # repeated requests don't duplicate once-per-version events
        client.post(
            f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "started", "version": 1}
        )
    p = client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "read", "version": 1}
    ).json()
    assert p["started"] and p["read"] and not p["check_passed"] and not p["practiced"]
    assert [e["kind"] for e in p["events"]] == ["started", "read"]
    assert p["next_action"]["kind"] == "check"
    # Reading doesn't touch answers, progress or the coding dashboard.
    assert client.get("/api/v1/careers/registered-nurse/progress", headers=h).json()["answered"] == 0
    assert client.get("/api/v1/me/progress", headers=h).json()["solved"] == 0
    # Only started/read can be posted; the rest come from the check and from practice.
    bad = client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "check_passed", "version": 1}
    )
    assert bad.status_code == 422


def test_the_check_is_graded_on_the_server_and_every_attempt_is_kept(client):
    h = nurse(client)
    wrong = {**right_answers(RN_UNIT), "q1": 0}
    r = client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/check", headers=h, json={"version": 1, "answers": wrong}
    ).json()
    assert not r["passed"] and r["correct"] == 2 and r["total"] == 3
    q1 = next(x for x in r["results"] if x["id"] == "q1")
    assert not q1["correct"] and q1["chosen"] == 0 and q1["answer"] == 1 and q1["explanation"]
    assert r["pass_rule"] == "Every answer in the check is right."
    assert r["progress"]["check_attempts"] == 1 and not r["progress"]["check_passed"]
    missing = client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/check", headers=h, json={"version": 1, "answers": {}}
    ).json()
    assert missing["correct"] == 0 and all(x["chosen"] is None for x in missing["results"])
    ok = client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/check",
        headers=h,
        json={"version": 1, "answers": right_answers(RN_UNIT)},
    ).json()
    assert ok["passed"] and ok["progress"]["check_passed"] and ok["progress"]["check_attempts"] == 3
    assert ok["progress"]["passed_versions"] == [1]
    # Passing the check is not practice and not a scored answer.
    assert not ok["progress"]["practiced"] and ok["progress"]["next_action"]["kind"] in ("practice", "read")
    assert client.get("/api/v1/careers/registered-nurse/progress", headers=h).json()["answered"] == 0


def test_practice_is_recorded_from_a_real_answer_after_starting(client):
    h = nurse(client)
    # An answer given before the unit was started doesn't count as practising it.
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-steps-7/answers", headers=h, json={"answer": GOOD}
    )
    client.post(f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "started", "version": 1})
    assert not client.get(f"/api/v1/me/learn/units/{RN_UNIT}", headers=h).json()["practiced"]
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-steps-7/answers", headers=h, json={"answer": GOOD}
    )
    p = client.get(f"/api/v1/me/learn/units/{RN_UNIT}", headers=h).json()
    assert p["practiced"] and p["practiced_evidence"].startswith("answered, scored ")
    assert [e["kind"] for e in p["events"]].count("practiced") == 1


def test_a_revised_unit_keeps_history_and_shows_the_version_used(client, monkeypatch):
    h = nurse(client)
    client.post(f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "read", "version": 1})
    client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/check",
        headers=h,
        json={"version": 1, "answers": right_answers(RN_UNIT)},
    )
    v2 = dataclasses.replace(
        UNIT_INDEX[RN_UNIT], version=2, changes=(*UNIT_INDEX[RN_UNIT].changes, "Added closing the loop.")
    )
    monkeypatch.setitem(learn_pkg.UNIT_INDEX, RN_UNIT, v2)
    p = client.get(f"/api/v1/me/learn/units/{RN_UNIT}", headers=h).json()
    assert p["current_version"] == 2 and p["versions_used"] == [1]
    assert (
        p["passed_versions"] == [1] and not p["check_passed"] and not p["read"]
    )  # the new version is unread
    assert all(e["version"] == 1 for e in p["events"])
    # A page still showing version 1 is told the unit changed instead of recording against the wrong version.
    stale = client.post(
        f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "read", "version": 1}
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "unit_changed"
    assert stale.json()["error"]["details"] == {"current_version": 2}
    unit = client.get(f"/api/v1/learn/units/{RN_UNIT}").json()
    assert unit["version"] == 2 and unit["changes"][-1] == "Added closing the loop."


def test_learn_works_when_no_ai_provider_is_available(client, monkeypatch):
    """Content is authored, so nothing here needs (or calls) a model, even when one is down."""
    from app.services.ai import anthropic_provider, offline, service

    def boom(*_a, **_k):
        raise AssertionError("Learn mode must not call a model")

    monkeypatch.setattr(service.CoachService, "__init__", boom)
    for cls in (offline.OfflineCoach, anthropic_provider.AnthropicCoach):
        for name in ("hint", "review", "explain_failure"):
            if hasattr(cls, name):
                monkeypatch.setattr(cls, name, boom)
    h = nurse(client)
    assert client.get("/api/v1/learn", params={"track": "registered-nurse"}).status_code == 200
    assert client.get(f"/api/v1/learn/units/{RN_UNIT}").status_code == 200
    assert (
        client.post(
            f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=h, json={"kind": "read", "version": 1}
        ).status_code
        == 200
    )
    r = client.post(f"/api/v1/me/learn/units/{RN_UNIT}/check", headers=h, json={"version": 1, "answers": {}})
    assert r.status_code == 200


def test_progress_is_private_and_exported_and_deleted_with_the_account(client):
    ada = nurse(client, "ada@example.com")
    bob = nurse(client, "bob@example.com")
    client.post(f"/api/v1/me/learn/units/{RN_UNIT}/events", headers=ada, json={"kind": "read", "version": 1})
    assert not client.get(f"/api/v1/me/learn/units/{RN_UNIT}", headers=bob).json()["started"]
    statuses = client.get("/api/v1/me/learn", headers=ada, params={"track": "registered-nurse"}).json()
    assert statuses[RN_UNIT]["read"] and not statuses["rn-star-answers"]["started"]
    assert client.get(f"/api/v1/me/learn/units/{RN_UNIT}").status_code == 401
    data = client.get("/api/v1/me/export", headers=ada).json()
    assert [e["kind"] for e in data["learn_events"]] == ["started", "read"]
    client.request(
        "DELETE", "/api/v1/auth/me", headers=ada, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    db = client.app.state.session_factory()
    assert db.query(LearnEvent).count() == 0
    db.close()


# --- the practice plan contract ----------------------------------------------------------------

WEAK = "I would tell the next nurse about the patient."


def test_the_plan_adds_a_lesson_before_a_retry_and_completes_it_only_on_a_passed_check(client):
    h = nurse(client)
    for qid in ("e-steps-7", "e-good-0", "e-time-0"):
        client.post(
            f"/api/v1/careers/registered-nurse/questions/{qid}/answers", headers=h, json={"answer": WEAK}
        )
    plan = client.get("/api/v1/me/plan", headers=h, params={"track": "registered-nurse"}).json()
    learn = [i for i in plan["items"] if i["kind"] == "learn"]
    assert len(learn) == 1
    item = learn[0]
    assert item["href"].startswith("/learn/") and "Reading it alone doesn't count" in item["completion"]
    kinds = [i["kind"] for i in plan["items"]]
    unit_id = item["href"].removeprefix("/learn/")
    client.post(f"/api/v1/me/learn/units/{unit_id}/events", headers=h, json={"kind": "read", "version": 1})
    after_read = client.get("/api/v1/me/plan", headers=h, params={"track": "registered-nurse"}).json()
    assert next(i for i in after_read["items"] if i["id"] == item["id"])["status"] == "pending"
    client.post(
        f"/api/v1/me/learn/units/{unit_id}/check",
        headers=h,
        json={"version": 1, "answers": right_answers(unit_id)},
    )
    done = client.get("/api/v1/me/plan", headers=h, params={"track": "registered-nurse"}).json()
    # Completing it makes a new plan version that says why, citing the passed check.
    assert done["version"] == after_read["version"] + 1
    assert f"Done: “{item['title']}” (passed the check on version 1)." in done["changes"]
    assert all(i["kind"] != "learn" for i in done["items"])  # passed units aren't planned again
    retry = next(i for i in plan["items"] if i["kind"] == "retry" and i["skill"] == item["skill"])
    assert kinds.index("learn") == [i["id"] for i in plan["items"]].index(retry["id"]) - 1


@pytest.mark.parametrize("track", ["electrician"])
def test_careers_without_units_get_no_lesson_items(client, track):
    h = auth_headers(register(client, career_track=track))
    for qid in ("e-good-0", "e-steps-0", "e-time-0"):
        client.post(f"/api/v1/careers/{track}/questions/{qid}/answers", headers=h, json={"answer": "short"})
    plan = client.get("/api/v1/me/plan", headers=h, params={"track": track}).json()
    assert all(i["kind"] != "learn" for i in plan["items"])

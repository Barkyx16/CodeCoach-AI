"""The adaptive practice plan: goals, baseline, evidence-based completion, adaptation, control."""

from tests.conftest import auth_headers, register

STRONG = (
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. "
    "I was responsible for five patients, so I had to move fast. I checked his vital signs again and started "
    "oxygen per protocol. I called the rapid response team and asked the charge nurse to cover my other "
    "patients. I updated the doctor and documented everything. As a result, he was stable within 30 minutes, "
    "and I learned to escalate early instead of waiting to be sure."
)


def user(client, track="registered-nurse", email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=track))


def plan(client, h, **params):
    r = client.get("/api/v1/me/plan", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def answer(client, h, track, qid, text=STRONG):
    r = client.post(f"/api/v1/careers/{track}/questions/{qid}/answers", headers=h, json={"answer": text})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_new_user_can_skip_setup_and_start_a_relevant_activity(client):
    h = user(client)
    goals = client.get("/api/v1/me/goals", headers=h).json()
    assert goals["saved"] is False and goals["track"] == "registered-nurse" and "triage" in goals["skills"]
    assert client.put("/api/v1/me/goals", headers=h, json={"setup_skipped": True}).json()["saved"] is True
    p = plan(client, h)
    assert p["version"] == 1 and p["career_title"] == "Registered Nurse"
    first = p["items"][0]
    assert first["kind"] == "assessment" and first["round"]["purpose"] == "baseline"
    assert "isn't enough evidence" in first["reason"] and first["minutes"] > 0 and first["completion"]
    assert p["today"]["primary"]["id"] == first["id"]
    assert p["assessment"]["state"] == "building_baseline"
    assert "Building your baseline" in p["assessment"]["note"]
    assert all("java" not in i["title"].lower() and i["kind"] != "coding" for i in p["items"])


def test_two_careers_get_different_plans(client):
    nurse = plan(client, user(client))
    engineer = plan(client, user(client, "software-engineer", "sam@example.com"))

    def specific(p):
        return {i["title"] for i in p["items"] if i["kind"] != "assessment"}  # the baseline step is shared

    assert specific(nurse) and specific(nurse).isdisjoint(specific(engineer))
    assert any("patient assessment" in t for t in specific(nurse))
    assert any(i["kind"] == "coding" for i in engineer["items"])
    assert not any(i["kind"] == "coding" for i in nurse["items"])
    coding = next(i for i in engineer["items"] if i["kind"] == "coding")
    assert coding["href"].startswith("/problems/") and "saved without a verdict" in coding["completion"]
    assert engineer["assessment"]["coding"] == {
        "judge_available": False,
        "judged_attempts": 0,
        "passed": 0,
        "saved_not_judged": 0,
    }
    assert nurse["assessment"]["coding"] is None


def test_the_baseline_changes_the_plan_for_stated_reasons(client):
    h = user(client)
    v1 = plan(client, h)
    iv = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "questions", "purpose": "baseline", "duration_minutes": 15},
    ).json()
    assert [q["kind"] for q in iv["questions"]] == ["knowledge", "behavioral", "situational"]
    for i, text in enumerate([STRONG, "I would ask someone for help I think.", STRONG]):
        client.post(
            f"/api/v1/interviews/{iv['id']}/answers", headers=h, json={"question_index": i, "answer": text}
        )
    v2 = plan(client, h)
    assert v2["version"] == 2
    assert any(c.startswith("Done: “Baseline check") for c in v2["changes"])
    weak = next(
        q
        for q in client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["questions"]
        if q["index"] == 1
    )
    retry = next(i for i in v2["items"] if i["kind"] == "retry")
    assert retry["title"] == f"Retry: {weak['title']}"
    assert f"{weak['answer']['score']}/100" in retry["reason"]
    assert any(c.startswith("Added “Retry:") for c in v2["changes"])
    review = next(i for i in v2["items"] if i["kind"] == "review")
    assert review["can_mark_reviewed"] and "self-reported" in review["completion"]
    assert v2["assessment"]["state"] == "baseline_ready" and v2["assessment"]["evaluated"]
    assert v1["items"][0]["kind"] == "assessment" and v2["items"][0]["kind"] != "assessment"


def test_completion_comes_from_evidence_and_refresh_keeps_progress(client):
    h = user(client)
    for qid in ("e-good-0", "e-good-1", "e-good-2"):
        answer(client, h, "registered-nurse", qid)
    p = plan(client, h)
    q = next(i for i in p["items"] if i["kind"] == "question")
    qid = q["href"].rsplit("/", 1)[1]
    assert plan(client, h)["version"] == p["version"]  # a refresh changes nothing
    answer(client, h, "registered-nurse", qid)
    after = plan(client, h)
    assert after["version"] == p["version"] + 1
    assert f"Done: “{q['title']}” (answered, scored" in after["changes"][0]
    assert after["progress"]["done_this_week"] == 1 and after["progress"]["minutes_this_week"] == q["minutes"]
    assert plan(client, h)["version"] == after["version"]


def test_a_skipped_activity_is_never_shown_as_completed(client):
    h = user(client)
    for qid in ("e-good-0", "e-good-1", "e-good-2"):
        answer(client, h, "registered-nurse", qid)
    p = plan(client, h)
    q = next(i for i in p["items"] if i["kind"] == "question")
    skipped = client.post(f"/api/v1/me/plan/items/{q['id']}/skip", headers=h).json()
    assert skipped["status"] == "skipped" and skipped["evidence"] is None
    answer(
        client, h, "registered-nurse", q["href"].rsplit("/", 1)[1]
    )  # doing it later doesn't rewrite the skip
    items = plan(client, h)["items"]
    same = [i for i in items if i["id"] == q["id"]]
    assert same == [] or same[0]["status"] == "skipped"
    assert client.post(f"/api/v1/me/plan/items/{q['id']}/skip", headers=h).status_code == 409


def test_replace_swaps_in_the_same_skill_and_review_is_the_only_self_report(client):
    h = user(client)
    for qid in ("e-good-0", "e-good-1", "e-good-2"):
        answer(client, h, "registered-nurse", qid)
    p = plan(client, h)
    q = next(i for i in p["items"] if i["kind"] == "question")
    new = client.post(f"/api/v1/me/plan/items/{q['id']}/replace", headers=h).json()
    assert new["skill"] == q["skill"] and new["title"] != q["title"] and new["status"] == "pending"
    items = {i["id"]: i for i in plan(client, h)["items"]}
    assert items[q["id"]]["status"] == "replaced" and items[new["id"]]["status"] == "pending"
    r = client.post(f"/api/v1/me/plan/items/{new['id']}/reviewed", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_self_reportable"


def test_today_fits_the_time_you_have(client):
    h = user(client, "software-engineer")
    client.put("/api/v1/me/goals", headers=h, json={"formats": ["written", "coding"]})
    short = plan(client, h, minutes=5)["today"]
    medium = plan(client, h, minutes=15)["today"]
    long = plan(client, h, minutes=30)["today"]
    assert short["minutes_available"] == 5 and short["primary"] is not None
    assert short["note"] and "shortest" in short["note"]  # the 12-minute baseline is the shortest thing
    assert medium["primary"]["minutes"] <= 15 and medium["session_minutes"] <= 15
    assert long["session_minutes"] <= 30
    assert long["follow_up"] is not None or long["session_minutes"] == long["primary"]["minutes"]


def test_goals_are_validated_editable_and_trigger_an_explained_update(client):
    h = user(client)
    v1 = plan(client, h)
    bad = client.put("/api/v1/me/goals", headers=h, json={"focus_areas": ["espresso preparation"]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unknown_skill"
    assert (
        client.put("/api/v1/me/goals", headers=h, json={"formats": ["coding"]}).json()["error"]["code"]
        == "no_coding"
    )
    assert client.put("/api/v1/me/goals", headers=h, json={"confidence": {"triage": 9}}).status_code == 400
    saved = client.put(
        "/api/v1/me/goals",
        headers=h,
        json={
            "experience": "mid",
            "focus_areas": ["triage"],
            "formats": ["written", "voice"],
            "weekly_minutes": 90,
            "confidence": {"triage": 4},
            "target_date": "2030-01-15",
            "specialty": "Emergency",
        },
    ).json()
    assert saved["focus_areas"] == ["triage"] and saved["specialty"] == "Emergency"
    v2 = plan(client, h)
    assert v2["version"] == v1["version"] + 1
    assert "Your goals changed, so priorities were recalculated." in v2["changes"]
    focus = next(i for i in v2["items"] if i["kind"] == "question")
    assert focus["skill"] == "triage" and focus["reason"] == "You asked for help with triage."
    assert any(i["kind"] == "voice" and i["round"]["question_ids"] for i in v2["items"])
    assert v2["assessment"]["self_reported"] == [{"skill": "triage", "rating": 4}]
    assert v2["progress"]["weekly_minutes"] == 90 and v2["days_to_interview"] > 0


def test_changing_careers_keeps_the_old_plan_and_history(client):
    h = user(client)
    answer(client, h, "registered-nurse", "e-good-0")
    nurse = plan(client, h)
    client.patch("/api/v1/auth/me", headers=h, json={"career_track": "barista"})
    barista = plan(client, h)
    assert barista["track"] == "barista" and barista["version"] == 1
    assert barista["assessment"]["evaluated"] == []  # nursing scores never count toward barista skills
    again = plan(client, h, track="registered-nurse")
    assert again["version"] == nurse["version"] and again["assessment"]["evaluated"]


def test_coding_activity_completes_from_a_submission_without_claiming_a_verdict(client):
    h = user(client, "software-engineer")
    p = plan(client, h)
    coding = next(i for i in p["items"] if i["kind"] == "coding")
    slug = coding["href"].rsplit("/", 1)[1]
    client.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": slug, "source_code": "class Solution {}"}
    )
    after = plan(client, h)
    assert any("submitted; saved, not judged here" in c for c in after["changes"])
    assert (
        after["assessment"]["coding"]["saved_not_judged"] == 1
        and after["assessment"]["coding"]["passed"] == 0
    )


def test_targeted_rounds_ask_exactly_the_chosen_questions(client):
    h = user(client)
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "question_ids": ["e-good-3", "e-good-1"]}
    ).json()
    assert [q["id"] for q in iv["questions"]] == ["e-good-3", "e-good-1"]
    client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h)
    bad = client.post("/api/v1/interviews", headers=h, json={"kind": "questions", "question_ids": ["nope"]})
    assert bad.status_code == 404


def test_another_user_cannot_touch_your_plan_and_export_includes_it(client):
    h = user(client)
    client.put("/api/v1/me/goals", headers=h, json={"focus_areas": ["triage"]})
    item = plan(client, h)["items"][0]
    other = user(client, email="other@example.com")
    for action in ("skip", "replace", "reviewed"):
        assert client.post(f"/api/v1/me/plan/items/{item['id']}/{action}", headers=other).status_code == 404
    export = client.get("/api/v1/me/export", headers=h).json()
    assert export["practice_goals"][0]["focus_areas"] == ["triage"]
    assert export["practice_plans"][0]["activities"][0]["title"] == item["title"]
    assert client.get("/api/v1/me/plan").status_code == 401

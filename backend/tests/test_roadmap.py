"""The adaptive practice plan: goals, baseline, evidence-based completion, adaptation, control."""

from app.careers.grading import grade
from app.services import question_rounds
from app.services.roadmap import WEAK
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


def strong_scores(monkeypatch, *, low: bool) -> None:
    """Pins what the baseline tests depend on: whether STRONG scores below the plan's weak line on
    the round's knowledge and situational questions. The round picks them at random, and STRONG is
    low on about a fifth of the pairs (the plan then retries those two first), so without this the
    test failed about one run in five. The real picker still runs, on a pool filtered to one case."""
    real = question_rounds.pick_baseline

    def pick(pool, answered, rng):
        keep = [
            q
            for q in pool
            if q.kind not in ("knowledge", "situational") or (grade(q, STRONG).score < WEAK) == low
        ]
        return real(keep, answered, rng)

    monkeypatch.setattr(question_rounds, "pick_baseline", pick)


def baseline_with_a_short_answer(client, h):
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
    return iv


def test_the_baseline_changes_the_plan_for_stated_reasons(client, monkeypatch):
    strong_scores(monkeypatch, low=False)
    h = user(client)
    v1 = plan(client, h)
    iv = baseline_with_a_short_answer(client, h)
    v2 = plan(client, h)
    assert v2["version"] == 2
    assert any(c.startswith("Done: “Baseline check") for c in v2["changes"])
    weak = next(
        q
        for q in client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["questions"]
        if q["index"] == 1
    )
    # The weak baseline answer was too short to score: it's retried, but its capped stored score
    # isn't quoted as a result (app/careers/eligibility.py).
    retry = next(i for i in v2["items"] if i["kind"] == "retry" and i["title"] == f"Retry: {weak['title']}")
    assert "too short to score" in retry["reason"]
    assert f"{weak['answer']['score']}/100" not in retry["reason"]
    assert any(c.startswith("Added “Retry:") for c in v2["changes"])
    review = next(i for i in v2["items"] if i["kind"] == "review")
    assert review["can_mark_reviewed"] and "self-reported" in review["completion"]
    assert v2["assessment"]["state"] == "baseline_ready" and v2["assessment"]["evaluated"]
    assert v1["items"][0]["kind"] == "assessment" and v2["items"][0]["kind"] != "assessment"


def test_two_low_scores_are_retried_before_an_answer_too_short_to_score(client, monkeypatch):
    """The other case: STRONG scored low on both. The plan retries at most two questions, lowest
    score first, so the one answered too briefly to score waits (app/services/roadmap.py)."""
    strong_scores(monkeypatch, low=True)
    h = user(client)
    plan(client, h)
    iv = baseline_with_a_short_answer(client, h)
    v2 = plan(client, h)
    qs = {q["index"]: q for q in client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["questions"]}
    retries = [i for i in v2["items"] if i["kind"] == "retry"]
    assert {i["title"] for i in retries} == {f"Retry: {qs[0]['title']}", f"Retry: {qs[2]['title']}"}
    assert all(i["reason"].startswith("Your best score is ") for i in retries)
    scores = [int(i["reason"].removeprefix("Your best score is ").split("/")[0]) for i in retries]
    assert scores == sorted(scores) and all(s < WEAK for s in scores)


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


def test_two_tabs_opening_a_new_plan_at_once_both_get_the_same_plan(client, monkeypatch):
    """Found under load (docs/PERFORMANCE.md): both first views built version 1, and the second
    one's insert hit the unique (user, track, version) constraint and answered 500."""
    from sqlalchemy import func, select

    from app.models import PracticePlan
    from app.services.roadmap import Roadmap

    h = user(client)
    real = Roadmap._new_version
    other_tab: dict = {}

    def the_other_tab_saves_first(self, *args, **kwargs):
        monkeypatch.setattr(Roadmap, "_new_version", real)
        other_tab["plan"] = plan(client, h)  # the other tab's request finishes first
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Roadmap, "_new_version", the_other_tab_saves_first)
    mine = plan(client, h)
    assert other_tab["plan"]["version"] == mine["version"] == 1
    assert [i["title"] for i in mine["items"]] == [i["title"] for i in other_tab["plan"]["items"]]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PracticePlan)) == 1


def test_one_spoken_answer_completes_one_activity_not_two(client):
    """The voice activity asks out loud for the first focus question, so one spoken answer used to
    finish both it and that question's own activity, and its minutes counted twice. Evidence is
    now used once: the round claims its answer first; the written activity waits for another."""
    h = user(client)
    client.put(
        "/api/v1/me/goals", headers=h, json={"focus_areas": ["triage"], "formats": ["written", "voice"]}
    )
    before = plan(client, h)
    voice = next(i for i in before["items"] if i["kind"] == "voice")
    [qid] = voice["round"]["question_ids"]
    written = next(i for i in before["items"] if i["kind"] == "question" and i["href"].endswith(f"/{qid}"))
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "question_ids": [qid]}
    ).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers=h,
        json={"question_index": 0, "answer": STRONG, "source": "voice"},
    )
    assert r.status_code == 200, r.text

    after = plan(client, h)
    assert f"Done: “{voice['title']}” (answered out loud)." in after["changes"]
    assert not any(c.startswith(f"Done: “{written['title']}”") for c in after["changes"])  # not twice
    assert after["progress"]["done_this_week"] == 1
    assert after["progress"]["minutes_this_week"] == voice["minutes"]


def test_a_too_short_answer_finishes_the_activity_without_quoting_a_score(client):
    h = user(client)
    q = next(i for i in plan(client, h)["items"] if i["kind"] == "question")
    qid = q["href"].rsplit("/", 1)[1]
    answer(client, h, "registered-nurse", qid, text="I would check on the patient.")
    changes = plan(client, h)["changes"]
    assert f"Done: “{q['title']}” (answered (too short to score))." in changes  # attempted, not scored
    assert not any("scored" in c and q["title"] in c and "too short" not in c for c in changes)


def test_swapping_never_repeats_a_target_and_keeps_the_original_when_nothing_is_left(client):
    """Each swap brings in a question with the same skill that this plan hasn't had (the replaced
    ones are avoided). When the pool runs out, the request says so and the activity stays."""
    h = user(client)
    item = next(i for i in plan(client, h)["items"] if i["kind"] == "question")
    seen = {item["href"].rsplit("/", 1)[1]}
    current = item
    for _ in range(200):
        r = client.post(f"/api/v1/me/plan/items/{current['id']}/replace", headers=h)
        if r.status_code == 409:
            break
        assert r.status_code == 200, r.text
        new = r.json()
        qid = new["href"].rsplit("/", 1)[1]
        assert qid not in seen and new["skill"] == item["skill"] and new["minutes"] == item["minutes"]
        seen.add(qid)
        current = new
    else:
        raise AssertionError("the pool never ran out")
    assert r.json()["error"]["code"] == "no_alternative"
    assert "stays in your plan" in r.json()["error"]["message"]
    still = {i["id"]: i for i in plan(client, h)["items"]}
    assert still[current["id"]]["status"] == "pending"  # not dropped, not marked done


def test_a_coding_swap_is_never_longer_than_what_it_replaces(client):
    h = user(client, track="software-engineer", email="sam@example.com")
    client.put("/api/v1/me/goals", headers=h, json={"formats": ["written", "coding"]})
    coding = next(i for i in plan(client, h)["items"] if i["kind"] == "coding")
    r = client.post(f"/api/v1/me/plan/items/{coding['id']}/replace", headers=h)
    if r.status_code == 200:
        assert r.json()["minutes"] <= coding["minutes"]
    else:
        assert r.status_code == 409 and r.json()["error"]["code"] == "no_alternative"


def test_weekly_minutes_are_a_rolling_7_days_of_estimates_each_counted_once(client, monkeypatch):
    """What the dashboard calls "Last 7 days": estimated minutes of activities finished in the
    previous 7 days (not timed practice), each activity once however often the plan is read."""
    from datetime import timedelta

    from app.services import roadmap

    h = user(client)
    q = next(i for i in plan(client, h)["items"] if i["kind"] == "question")
    answer(client, h, "registered-nurse", q["href"].rsplit("/", 1)[1])
    for _ in range(3):  # reading the plan again doesn't count the same activity again
        progress = plan(client, h)["progress"]
        assert progress["done_this_week"] == 1 and progress["minutes_this_week"] == q["minutes"]

    real_now = roadmap._now
    monkeypatch.setattr(roadmap, "_now", lambda: real_now() + timedelta(days=8))
    later = plan(client, h)["progress"]
    assert later["done_this_week"] == 0 and later["minutes_this_week"] == 0  # out of the 7 days

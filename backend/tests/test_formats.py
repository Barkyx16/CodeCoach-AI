"""Interview formats: availability, panel turn order and roles, follow-ups chosen from the answer,
bounded and never repeated, server-side turn validation, timeouts, review and privacy."""

from datetime import UTC, datetime, timedelta

from app.careers.formats import MAX_FOLLOWUPS, choose_probe, details_in
from app.models import InterviewTurn, PracticeSession, TurnRole
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
VAGUE = "We handled it together as a team and everything was fine in the end."
OWNED_NO_RESULT = "I checked his vital signs and I called the doctor straight away while the team helped."
FULL = (
    "Last winter I was the night nurse for five patients. I checked his vital signs, I called the rapid response "
    "team and as a result he was stable within 30 minutes. I learned to escalate earlier."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def start(client, h, fmt, difficulty="medium"):
    return client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "format": fmt, "difficulty": difficulty}
    )


def answer(client, h, iv, index, text):
    return client.post(
        f"/api/v1/interviews/{iv}/answers",
        headers=h,
        json={"question_index": index, "answer": text, "source": "typed"},
    )


def followup(client, h, iv, text):
    return client.post(
        f"/api/v1/interviews/{iv}/followup", headers=h, json={"answer": text, "source": "typed"}
    )


def test_formats_are_offered_only_where_the_bank_can_fill_them(client):
    easy = {
        f["id"]: f
        for f in client.get(
            "/api/v1/interviews/formats", params={"track": NURSE, "difficulty": "easy"}
        ).json()
    }
    assert easy["mixed"]["available"] and easy["mixed"]["follow_ups"] == 0
    assert not easy["situational"]["available"]
    assert "Try Medium or Hard" in easy["situational"]["unavailable_reason"]
    assert easy["technical"]["available"] and easy["behavioral"]["available"]
    panel = easy["panel"]
    assert panel["available"] and [r["title"] for r in panel["roles"]] == [
        "Nurse manager",
        "Charge nurse (peer)",
        "Physician colleague (interdisciplinary partner)",
    ]
    assert [s["speaker"]["id"] for s in panel["structure"]] == [
        "hiring_manager",
        "peer",
        "partner",
        "peer",
        "hiring_manager",
    ]
    assert all("prompt" not in s for s in panel["structure"])  # structure only, no questions
    # A career without a reviewed panel says so instead of falling back to generic questions.
    el = {
        f["id"]: f for f in client.get("/api/v1/interviews/formats", params={"track": "electrician"}).json()
    }
    assert (
        not el["panel"]["available"]
        and "no reviewed panel for Electrician" in el["panel"]["unavailable_reason"]
    )
    assert el["panel"]["roles"] == [] and el["behavioral"]["available"]
    assert client.get("/api/v1/interviews/formats", params={"track": "astronaut"}).status_code == 404


def test_unavailable_or_misused_formats_are_refused(client):
    h = nurse(client)
    r = start(client, h, "situational", "easy")
    assert r.status_code == 409 and r.json()["error"]["code"] == "format_unavailable"
    r = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "format": "panel", "purpose": "baseline"}
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "format_not_allowed"
    el = auth_headers(register(client, email="el@example.com", career_track="electrician"))
    r = start(client, el, "panel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "format_unavailable"


def test_a_situational_round_uses_only_scenarios_and_records_its_format(client):
    h = nurse(client)
    iv = start(client, h, "situational").json()
    assert {q["kind"] for q in iv["questions"]} == {"situational"} and len(iv["questions"]) == 5
    f = iv["round_format"]
    assert f["id"] == "situational" and f["version"] == "formats v1" and f["rubric_version"] == "rubric v1"
    assert f["followups_max"] == MAX_FOLLOWUPS and f["roles"] == [] and f["pending_followup"] is None


def test_a_panel_takes_turns_one_speaker_at_a_time(client):
    h = nurse(client)
    iv = start(client, h, "panel").json()
    speakers = [q["speaker"]["id"] for q in iv["questions"]]
    assert speakers == ["hiring_manager", "peer", "partner", "peer", "hiring_manager"]
    assert iv["questions"][0]["speaker"]["title"] == "Nurse manager"
    with client.app.state.session_factory() as db:
        turns = db.query(InterviewTurn).filter_by(session_id=iv["id"], role=TurnRole.INTERVIEWER).all()
        assert [t.meta["speaker"] for t in turns] == ["hiring_manager"]  # only the active speaker has asked
    # Five turns in order; any follow-up comes from the role that asked, and the next role waits.
    r = iv
    asked_by = []
    for i in range(5):
        r = answer(client, h, iv["id"], i, FULL).json()
        pending = r["round_format"]["pending_followup"]
        if pending:
            assert pending["speaker"]["id"] == speakers[i] and pending["question_index"] == i
            asked_by.append(pending["speaker"]["id"])
            r = followup(
                client, h, iv["id"], "I would assess breathing first because it is the most urgent."
            ).json()
    assert len(asked_by) <= MAX_FOLLOWUPS
    assert r["status"] == "completed"
    review = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()
    assert [i["speaker"]["id"] for i in review["items"]] == speakers
    persp = {p["role"]["id"]: p for p in review["perspectives"]}
    assert (
        persp["peer"]["asked"] == 2
        and persp["peer"]["answered"] == 2
        and persp["peer"]["average_score"] is not None
    )
    assert (
        "aren't separate human judgments" in review["disclaimer"]
        and "hiring decision" in review["disclaimer"]
    )
    assert review["round_format"]["id"] == "panel"


def test_follow_ups_come_from_the_answer_and_block_the_next_question_until_handled(client):
    h = nurse(client)
    iv = start(client, h, "behavioral").json()
    r = answer(client, h, iv["id"], 0, VAGUE).json()
    pending = r["round_format"]["pending_followup"]
    assert pending["detail"] == "ownership" and pending["question"].startswith("What did you personally do")
    assert r["questions"][0]["followup"]["status"] == "pending"
    assert all(q["status"] != "current" for q in r["questions"])  # the follow-up is the active turn
    blocked = answer(client, h, iv["id"], 1, FULL)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "followup_pending"
    r = followup(client, h, iv["id"], OWNED_NO_RESULT).json()
    assert r["questions"][0]["followup"] == {
        **r["questions"][0]["followup"],
        "status": "answered",
        "covered": True,
        "answer": OWNED_NO_RESULT,
    }
    assert r["questions"][1]["status"] == "current" and r["round_format"]["followups_used"] == 1
    # The same reply again changes nothing; a reply with nothing pending is refused.
    assert followup(client, h, iv["id"], OWNED_NO_RESULT).status_code == 200
    assert followup(client, h, iv["id"], "something else").json()["error"]["code"] == "no_followup"


def test_a_supplied_detail_is_never_asked_for_again_and_follow_ups_are_bounded(client):
    h = nurse(client)
    iv = start(client, h, "behavioral").json()
    # The first answer already gives ownership; so the first follow-up asks for the result.
    r = answer(client, h, iv["id"], 0, OWNED_NO_RESULT).json()
    assert r["round_format"]["pending_followup"]["detail"] == "result"
    r = followup(client, h, iv["id"], "As a result he was stable within 30 minutes.").json()
    # ownership, result and numbers are now known for this session; next probe can only be "learning".
    r = answer(client, h, iv["id"], 1, VAGUE).json()
    assert r["round_format"]["pending_followup"]["detail"] == "learning"
    r = client.post(f"/api/v1/interviews/{iv['id']}/followup/skip", headers=h).json()
    assert r["questions"][1]["followup"]["status"] == "skipped" and r["round_format"]["followups_used"] == 2
    for i in range(2, 5):  # the session's follow-up budget is spent
        r = answer(client, h, iv["id"], i, VAGUE).json()
        assert r["round_format"]["pending_followup"] is None
    assert r["status"] == "completed"
    review = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()
    dim = next(d for d in review["overall"] if d["name"] == "Follow-up questions")
    assert dim["status"] == "evaluated" and "1 of 2 follow-up replies supplied the detail" in dim["summary"]
    assert review["items"][0]["followup"]["detail"] == "result"


def test_the_mixed_format_keeps_its_original_behavior(client):
    h = nurse(client)
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    assert iv["round_format"]["id"] == "mixed" and iv["round_format"]["followups_max"] == 0
    r = answer(client, h, iv["id"], 0, VAGUE).json()
    assert r["round_format"]["pending_followup"] is None and r["questions"][1]["status"] == "current"


def test_time_running_out_during_a_follow_up_ends_the_round(client):
    h = nurse(client)
    iv = start(client, h, "behavioral").json()
    answer(client, h, iv["id"], 0, VAGUE)
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv["id"])
        s.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    r = followup(client, h, iv["id"], OWNED_NO_RESULT)
    assert r.status_code == 409
    got = client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()
    assert got["status"] == "expired" and got["seconds_remaining"] == 0


def test_follow_ups_are_private_to_the_owner(client):
    ada = nurse(client, "ada@example.com")
    bob = nurse(client, "bob@example.com")
    iv = start(client, ada, "behavioral").json()
    answer(client, ada, iv["id"], 0, VAGUE)
    assert followup(client, bob, iv["id"], OWNED_NO_RESULT).status_code == 404
    assert client.post(f"/api/v1/interviews/{iv['id']}/followup/skip", headers=bob).status_code == 404


def test_detail_detection_and_probe_choice():
    assert {"ownership", "result", "numbers", "learning"} <= details_in(FULL)
    assert details_in(VAGUE) == set()
    probes = ("ownership", "result", "numbers")
    assert choose_probe(VAGUE, probes, set(), set()) == "ownership"
    assert choose_probe(VAGUE, probes, {"ownership"}, set()) == "result"
    assert choose_probe(VAGUE, probes, {"ownership"}, {"result"}) == "numbers"
    assert choose_probe(FULL, probes, set(), set()) is None

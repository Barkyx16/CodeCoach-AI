"""The conditions of a practice attempt (Volume 12, prompt 3; docs/ATTEMPT_CONDITIONS.md): the
in-app help shown for the same question and version since the previous attempt, worked out when
read from the coach's saved hints and Learn's lesson reads. Synthetic data only."""

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.learn import get_unit
from app.models import AIInteraction, Problem, Submission, TestCase, User
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
UNIT = "rn-sbar-handoff"  # prepares for e-steps-7, e-good-7 and e-time-7
CODE = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[0]; } }"
ANSWER = (
    "At a 7 p.m. handoff I used SBAR: I gave the situation, the background, my assessment and a clear "
    "recommendation, and asked the oncoming nurse to repeat back the plan, so nothing was missed."
)


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def nurse(client, email="nia@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def hint(client, h, level, slug="two-sum", key=None):
    body = {"problem_slug": slug, "level": level, "source_code": CODE}
    if key:
        body["client_request_id"] = key
    return client.post("/api/v1/ai/hint", headers=h, json=body)


def submit(client, h, slug="two-sum"):
    r = client.post("/api/v1/submissions", headers=h, json={"problem_slug": slug, "source_code": CODE})
    assert r.status_code in (200, 201, 202), r.text
    return r.json()["id"]


def conditions(client, h, sub_id):
    r = client.get(f"/api/v1/submissions/{sub_id}", headers=h)
    assert r.status_code == 200
    return r.json()["conditions"]


def answer(client, h, qid="e-steps-7"):
    r = client.post(f"/api/v1/careers/{NURSE}/questions/{qid}/answers", headers=h, json={"answer": ANSWER})
    assert r.status_code in (200, 201), r.text
    return r.json()


def read_lesson(client, h):
    version = get_unit(UNIT).version
    r = client.post(
        f"/api/v1/me/learn/units/{UNIT}/events", headers=h, json={"kind": "read", "version": version}
    )
    assert r.status_code == 200, r.text


def test_a_hint_marks_the_next_attempt_only(client):
    h = coder(client)
    assert hint(client, h, 1).status_code == 200
    first = submit(client, h)
    second = submit(client, h)
    c1 = conditions(client, h, first)
    assert c1["labels"] == ["Hint shown"]
    assert [x["detail"] for x in c1["help"]] == ["Level 1 hint (nudge)"]
    assert conditions(client, h, second)["labels"] == ["No in-app help recorded"]
    # The history says the same.
    listed = {
        i["id"]: i["conditions"]["labels"]
        for i in client.get("/api/v1/me/submissions", headers=h).json()["items"]
    }
    assert listed == {first: ["Hint shown"], second: ["No in-app help recorded"]}


def test_a_failed_hint_request_leaves_no_label(client):
    h = coder(client)
    assert hint(client, h, 3).status_code == 409  # locked: nothing was shown
    sub = submit(client, h)
    assert conditions(client, h, sub)["labels"] == ["No in-app help recorded"]


def test_help_after_an_attempt_belongs_to_the_next_and_never_changes_the_earlier(client):
    h = coder(client)
    first = submit(client, h)
    before = conditions(client, h, first)
    for level in (1, 2, 3, 4):
        assert hint(client, h, level).status_code == 200
    assert conditions(client, h, first) == before == conditions(client, h, first)
    assert before["labels"] == ["No in-app help recorded"]
    nxt = conditions(client, h, submit(client, h))
    assert nxt["labels"] == ["Hint shown", "Solution revealed"]
    assert nxt["help"][-1]["detail"] == "Level 4 hint (full explanation): the full explanation"


def test_help_on_one_problem_or_an_old_version_doesnt_mark_another(client):
    h = coder(client)
    assert hint(client, h, 1).status_code == 200
    other = submit(client, h, slug="find-largest-number")
    assert conditions(client, h, other)["labels"] == ["No in-app help recorded"]
    # Two Sum gets a new version of its tests: the hint was for the old one.
    with client.app.state.session_factory() as db:
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    assert conditions(client, h, submit(client, h))["labels"] == ["No in-app help recorded"]


def test_a_replayed_hint_is_one_help_event(client):
    h = coder(client)
    a = hint(client, h, 1, key="hint-key-replayed-1")
    b = hint(client, h, 1, key="hint-key-replayed-1")  # the reply was lost: sent again
    assert a.status_code == b.status_code == 200
    with client.app.state.session_factory() as db:
        assert len(db.scalars(select(AIInteraction)).all()) == 1
    assert len(conditions(client, h, submit(client, h))["help"]) == 1


def test_an_attempt_from_before_recording_says_not_recorded(client):
    h = coder(client)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        old = Submission(
            user_id=user.id, problem_id=pid, source_code=CODE, created_at=datetime(2026, 3, 1, tzinfo=UTC)
        )
        db.add(old)
        db.commit()
        old_id = old.id
    c = conditions(client, h, old_id)
    assert c["labels"] == ["Not recorded"] and c["recorded_from"] == "2026-11-14"
    assert "none" not in str(c["labels"]).lower()


def test_a_hint_of_unknown_version_on_a_revised_problem_is_not_recorded(client):
    h = coder(client)
    assert hint(client, h, 1).status_code == 200
    with client.app.state.session_factory() as db:
        db.execute(update(AIInteraction).values(content_version=None))  # saved before versions were kept
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    assert conditions(client, h, submit(client, h))["labels"] == ["Not recorded"]


def test_another_accounts_attempts_and_help_are_refused(client):
    mine = coder(client)
    theirs = coder(client, email="grace@example.com")
    assert hint(client, theirs, 1).status_code == 200
    their_sub = submit(client, theirs)
    assert client.get(f"/api/v1/submissions/{their_sub}", headers=mine).status_code == 404
    # Their hint doesn't appear on my attempt.
    assert conditions(client, mine, submit(client, mine))["labels"] == ["No in-app help recorded"]


def test_a_lesson_read_before_an_answer_marks_that_answer_only(client):
    h = nurse(client)
    read_lesson(client, h)
    first = answer(client, h)
    assert first["conditions"]["labels"] == ["Hint shown"]
    assert first["conditions"]["help"][0]["detail"] == "Lesson “SBAR for handoffs and escalation” read"
    second = answer(client, h)
    assert second["conditions"]["labels"] == ["No in-app help recorded"]
    # A question the lesson doesn't prepare for isn't marked.
    unrelated = answer(client, h, qid="m-pressure-0")
    assert unrelated["conditions"]["labels"] == ["No in-app help recorded"]
    listed = client.get(f"/api/v1/careers/{NURSE}/questions/e-steps-7/answers", headers=h).json()
    assert [a["conditions"]["labels"] for a in listed] == [["No in-app help recorded"], ["Hint shown"]]


def test_a_lesson_read_for_an_old_version_doesnt_mark_a_revised_question(client):
    h = nurse(client)
    read_lesson(client, h)
    admin = nurse(client, email="root@example.com")
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.email == "root@example.com")).is_admin = True
        db.commit()
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/e-steps-7/corrections",
        headers=admin,
        json={
            "prompt": "Walk me through how you hand off a patient at the end of a shift.",
            "change_note": "Clearer.",
        },
    )
    assert r.status_code in (200, 201), r.text
    a = answer(client, h)
    assert a["content_version"] == 2
    assert a["conditions"]["labels"] == ["No in-app help recorded"]


def test_help_changes_no_score_and_is_exported(client):
    helped = nurse(client)
    plain = nurse(client, email="ola@example.com")
    read_lesson(client, helped)
    a, b = answer(client, helped), answer(client, plain)
    assert a["conditions"]["labels"] == ["Hint shown"] and b["conditions"]["labels"] == [
        "No in-app help recorded"
    ]
    assert a["score"] == b["score"] and a["rating"] == b["rating"]
    doc = client.get("/api/v1/me/export", headers=helped).json()
    assert doc["interview_answers"][0]["conditions"]["labels"] == ["Hint shown"]
    assert doc["interview_answers"][0]["conditions"]["help"][0]["detail"].startswith("Lesson")


def test_coding_conditions_are_exported(client):
    h = coder(client)
    assert hint(client, h, 1).status_code == 200
    submit(client, h)
    doc = client.get("/api/v1/me/export", headers=h).json()
    assert doc["submissions"][0]["conditions"]["labels"] == ["Hint shown"]
    assert doc["ai_feedback"][0]["problem_version"] == 1


def test_a_list_asks_for_its_rows_conditions_in_one_bounded_request(client):
    from tests.test_query_budgets import fresh_content, statements

    h = nurse(client)
    read_lesson(client, h)
    ids = [answer(client, h)["id"] for _ in range(3)]
    other = nurse(client, email="ola@example.com")
    theirs = answer(client, other)["id"]
    body = {"answer_ids": [*ids, theirs, "no-such-id"], "submission_ids": ["no-such-id"]}
    fresh_content(client)  # the corrections snapshot reloads every 5 s: not inside a measurement
    with statements(client) as few:
        r = client.post("/api/v1/me/attempt-conditions", headers=h, json=body)
    assert r.status_code == 200
    got = r.json()
    assert set(got["answers"]) == set(ids)  # theirs and unknown ids are simply absent
    assert [got["answers"][i]["labels"] for i in ids] == [
        ["Hint shown"],
        ["No in-app help recorded"],
        ["No in-app help recorded"],
    ]
    assert got["submissions"] == {}
    for _ in range(20):
        answer(client, h)
    fresh_content(client)
    with statements(client) as many:
        client.post("/api/v1/me/attempt-conditions", headers=h, json=body)
    assert len(many) == len(few) and len(few) <= 9, (len(few), len(many))
    assert client.post("/api/v1/me/attempt-conditions", json=body).status_code == 401


def test_a_lesson_read_after_an_answer_belongs_to_the_next_answer(client):
    h = nurse(client)
    first = answer(client, h)
    assert first["conditions"]["labels"] == ["No in-app help recorded"]
    read_lesson(client, h)
    listed = client.get(f"/api/v1/careers/{NURSE}/questions/e-steps-7/answers", headers=h).json()
    assert [a["conditions"]["labels"] for a in listed] == [["No in-app help recorded"]]  # unchanged
    assert answer(client, h)["conditions"]["labels"] == ["Hint shown"]

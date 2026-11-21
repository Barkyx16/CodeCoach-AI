"""The unified activity feed, career analytics and resume: derived from recorded rows only."""

from datetime import UTC, datetime, timedelta

from app.careers.grading import RUBRIC_VERSION
from tests.conftest import auth_headers, register
from tests.judge_fakes import EXPECTED, expected_outputs, lines, submit

ANSWER = (
    "Last winter I noticed a patient's oxygen dropping during my 2 a.m. patient assessment. I checked his "
    "vital signs, started oxygen per protocol and called the rapid response team. I updated the doctor and "
    "documented everything. He was stable within 30 minutes and I learned to escalate early."
)


def feed(client, headers, **params):
    r = client.get("/api/v1/me/activity", headers=headers, params={"page_size": 50, **params})
    assert r.status_code == 200, r.text
    return r.json()


def coding_activity(client, h):
    client.get("/api/v1/problems/two-sum", headers=h)  # opened
    client.get("/api/v1/problems/two-sum", headers=h)  # same day: not counted twice
    client.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": "class Solution {}"}
    )
    client.post("/api/v1/ai/hint", headers=h, json={"problem_slug": "two-sum", "level": 1})
    client.post("/api/v1/interviews", headers=h, json={"problem_slug": "valid-parentheses"})


def test_coding_activity_with_honest_statuses(client):
    h = auth_headers(register(client))
    coding_activity(client, h)
    items = feed(client, h)["items"]
    by_type = {i["type"]: i for i in items}
    assert set(by_type) == {"problem_opened", "code_submission", "coaching", "interview"}
    assert sum(i["type"] == "problem_opened" for i in items) == 1
    assert by_type["problem_opened"]["status"] == "opened"
    # The judge isn't available in this test app: saved, never shown as graded.
    sub = by_type["code_submission"]
    assert sub["status"] == "saved_not_judged" and "not judged" in sub["status_label"]
    assert sub["target"]["href"].startswith("/history/submissions/")
    assert by_type["coaching"]["detail"] == "Hint, level 1"
    assert (
        by_type["coaching"]["target"]["href"]
        == f"/history/coaching/{by_type['coaching']['target']['ai_interaction_id']}"
    )
    assert by_type["interview"]["status"] == "in_progress" and by_type["interview"]["career"] == "coding"
    assert all(i["career"] == "coding" and i["career_title"] == "Coding problems" for i in items)
    assert "hash-maps" in sub["skills"]


def test_judged_submissions_show_their_verdict(judged):
    c, _, worker, h = judged(lambda files, nonce: ("ok", lines(nonce, EXPECTED[0]), {}))
    EXPECTED[:] = [expected_outputs(c, "two-sum")[0]]
    submit(c, h)
    queued = feed(c, h, type="code_submission")["items"][0]
    assert queued["status"] == "awaiting_judge"
    worker.process_one()
    done = feed(c, h, type="code_submission")["items"][0]
    assert done["status"] == "passed"


def test_written_answers_and_rounds_belong_to_their_career(client):
    h = auth_headers(register(client, career_track="registered-nurse"))
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-good-0/answers", headers=h, json={"answer": ANSWER}
    )
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    client.post(
        f"/api/v1/interviews/{iv['id']}/answers", headers=h, json={"question_index": 0, "answer": ANSWER}
    )
    items = feed(client, h)["items"]
    answers = [i for i in items if i["type"] == "written_answer"]
    assert len(answers) == 2  # each answer exactly once, in or out of an interview
    single = next(a for a in answers if a["session_id"] is None)
    assert single["career"] == "registered-nurse" and single["score"] is not None
    assert single["status"] == "scored" and single["status_label"].startswith("Scored")
    assert (
        single["target"]["href"]
        == f"/careers/registered-nurse/questions/e-good-0?answer={single['target']['answer_id']}"
    )
    assert "patient assessment" in single["skills"]
    in_round = next(a for a in answers if a["session_id"])
    assert in_round["session_id"] == iv["id"] and in_round["detail"] == "Part of a mock interview"
    round_item = next(i for i in items if i["type"] == "interview")
    assert round_item["title"] == "Registered Nurse question round"
    assert (
        round_item["detail"] == "1 of 5 answered"
        and round_item["target"]["href"] == f"/interviews/{iv['id']}"
    )
    # Nursing activity never shows coding statuses.
    assert not {i["status"] for i in items} & {"passed", "failed", "saved_not_judged"}


def test_filters_pagination_and_search(client):
    h = auth_headers(register(client, career_track="registered-nurse"))
    coding_activity(client, h)
    for qid in ("e-good-0", "e-good-1", "e-good-2"):
        client.post(
            f"/api/v1/careers/registered-nurse/questions/{qid}/answers", headers=h, json={"answer": ANSWER}
        )
    everything = feed(client, h)
    assert everything["total"] == 7
    assert feed(client, h, career="coding")["total"] == 4
    assert feed(client, h, career="registered-nurse")["total"] == 3
    assert feed(client, h, type="written_answer", status="scored")["total"] == 3
    assert feed(client, h, status="opened")["total"] == 1
    assert {i["type"] for i in feed(client, h, skill="hash-maps", career="coding")["items"]} <= {
        "problem_opened",
        "code_submission",
        "coaching",
    }
    assert (
        feed(client, h, q="two sum")["total"] == 3
    )  # opened, submitted, hint (the interview is another problem)
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    assert feed(client, h, since=tomorrow)["total"] == 0
    assert feed(client, h, until=tomorrow)["total"] == 7
    p1 = client.get("/api/v1/me/activity", headers=h, params={"page": 1, "page_size": 3}).json()
    p2 = client.get("/api/v1/me/activity", headers=h, params={"page": 2, "page_size": 3}).json()
    p3 = client.get("/api/v1/me/activity", headers=h, params={"page": 3, "page_size": 3}).json()
    ids = [i["id"] for p in (p1, p2, p3) for i in p["items"]]
    assert len(ids) == len(set(ids)) == 7 and p1["total"] == 7
    assert ids == [i["id"] for i in everything["items"]]  # same order as one big page
    assert client.get("/api/v1/me/activity", headers=h, params={"type": "nonsense"}).status_code == 422


def test_facets_and_career_switch_keep_history(client):
    h = auth_headers(register(client, career_track="registered-nurse"))
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-good-0/answers", headers=h, json={"answer": ANSWER}
    )
    coding_activity(client, h)
    assert client.patch("/api/v1/auth/me", headers=h, json={"career_track": "barista"}).status_code == 200
    facets = client.get("/api/v1/me/activity/facets", headers=h).json()
    careers = {c["value"]: c["count"] for c in facets["careers"]}
    assert careers == {"coding": 4, "registered-nurse": 1}
    assert feed(client, h, career="registered-nurse")["total"] == 1  # history survives the switch
    nurse = client.get("/api/v1/me/activity/facets", headers=h, params={"career": "registered-nurse"}).json()
    skills = {s["value"]: s["count"] for s in nurse["skills"]}
    assert skills["patient assessment"] == 1 and skills["triage"] == 0
    coding = client.get("/api/v1/me/activity/facets", headers=h, params={"career": "coding"}).json()
    assert "hash-maps" in {s["value"] for s in coding["skills"]}


def test_career_analytics_for_any_career_with_definitions(client):
    h = auth_headers(register(client, career_track="barista"))
    for _ in range(2):
        client.post(
            "/api/v1/careers/registered-nurse/questions/e-good-0/answers", headers=h, json={"answer": ANSWER}
        )
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-good-1/answers",
        headers=h,
        json={"answer": "Too short."},
    )
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "track": "registered-nurse"}
    ).json()
    client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h)
    a = client.get("/api/v1/me/careers/registered-nurse/analytics", headers=h).json()
    assert a["career_title"] == "Registered Nurse" and a["since"] is None
    assert a["questions_practiced"] == 2 and a["answers"] == 3 and a["total_questions"] == 300
    skill = next(s for s in a["skills"] if s["skill"] == "patient assessment")
    assert skill["questions_answered"] == 1 and skill["answers"] == 2
    untouched = next(s for s in a["skills"] if s["skill"] == "triage")
    assert untouched["questions_answered"] == 0 and untouched["average_best_score"] is None  # not zero
    assert a["interviews"]["abandoned"] == 1 and a["interviews"]["completed"] == 0
    assert len(a["trends"]) == 1 and f"rubric {RUBRIC_VERSION}," in a["trends"][0]["evaluator"]
    # The trend counts its cohort (docs/COMPARING_ATTEMPTS.md); the rest are counted by reason.
    in_trend = sum(p["answers"] for p in a["trends"][0]["points"])
    assert in_trend == a["trends"][0]["attempts"]
    assert in_trend + sum(n["count"] for n in a["not_in_trend"]) == 3
    assert sum(d["answers"] for d in a["by_day"]) == 3
    assert {"trend", "average_best_score", "skills"} <= set(a["definitions"])
    future = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    empty = client.get(
        "/api/v1/me/careers/registered-nurse/analytics", headers=h, params={"since": future}
    ).json()
    assert empty["answers"] == 0 and empty["trends"] == []
    assert client.get("/api/v1/me/careers/astronaut/analytics", headers=h).status_code == 404


def test_resume_reports_real_saved_work(client):
    h = auth_headers(register(client, career_track="registered-nurse"))
    assert client.get("/api/v1/me/resume", headers=h).json() == {
        "interview": None,
        "unfinished_problem": None,
        "last_question": None,
    }
    client.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": "class Solution {}"}
    )
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-good-0/answers", headers=h, json={"answer": ANSWER}
    )
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "duration_minutes": 10}
    ).json()
    r = client.get("/api/v1/me/resume", headers=h).json()
    assert r["interview"]["id"] == iv["id"] and 0 < r["interview"]["seconds_remaining"] <= 600
    assert r["interview"]["title"] == "Registered Nurse question round"
    assert (
        r["unfinished_problem"]["slug"] == "two-sum"
        and r["unfinished_problem"]["last_status"] == "saved_not_judged"
    )
    assert r["last_question"]["question_id"] == "e-good-0"


def test_one_account_cannot_read_anothers_activity(client):
    owner = auth_headers(register(client, career_track="registered-nurse"))
    coding_activity(client, owner)
    client.post(
        "/api/v1/careers/registered-nurse/questions/e-good-0/answers", headers=owner, json={"answer": ANSWER}
    )
    coaching_id = next(i for i in feed(client, owner)["items"] if i["type"] == "coaching")["target"][
        "ai_interaction_id"
    ]
    other = auth_headers(register(client, email="other@example.com"))
    assert feed(client, other)["total"] == 0
    assert client.get("/api/v1/me/activity/facets", headers=other).json()["careers"] == []
    assert client.get("/api/v1/me/careers/registered-nurse/analytics", headers=other).json()["answers"] == 0
    assert client.get("/api/v1/me/resume", headers=other).json()["unfinished_problem"] is None
    assert client.get(f"/api/v1/me/ai-history/{coaching_id}", headers=other).status_code == 404
    mine = client.get(f"/api/v1/me/ai-history/{coaching_id}", headers=owner).json()
    assert mine["action"] == "hint" and mine["problem_slug"] == "two-sum"
    assert client.get("/api/v1/me/activity").status_code == 401


def test_a_problem_open_is_counted_once_even_when_requests_race(client):
    from sqlalchemy import func, select

    from app.models import Problem, ProgressEvent, ProgressEventType, User

    h = auth_headers(register(client))
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        problem = db.scalar(select(Problem).where(Problem.slug == "two-sum"))
        today = datetime.now(UTC).date().isoformat()
        # A concurrent request already recorded today's open, stamped just before midnight, so the
        # cheap "seen today?" check misses it and the insert path (and its unique key) is exercised.
        db.add(
            ProgressEvent(
                user_id=user.id,
                problem_id=problem.id,
                event_type=ProgressEventType.OPENED,
                dedupe_key=f"opened:{problem.id}:{today}",
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db.commit()
    assert client.get("/api/v1/problems/two-sum", headers=h).status_code == 200
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProgressEvent)) == 1

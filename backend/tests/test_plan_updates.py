"""New evidence updates the plan when the learner asks (Volume 13, prompt 1; docs/PLAN_UPDATES.md).

Practice the current version doesn't use is counted and named in one line, and the plan stays as it
is until the learner presses "Update my plan": the update is the normal next version with its notes,
bound to the version the learner saw. Evidence the planner doesn't use (too short to score,
disputed) offers nothing. Synthetic data only."""

from sqlalchemy import func, select

from app.careers.grading import grade
from app.careers.questions import questions_for
from app.models import PracticePlan
from app.services.roadmap import Roadmap, news_text
from tests.conftest import auth_headers, register
from tests.test_disputes import WEAK, flag
from tests.test_roadmap import STRONG, answer, plan

TRACK = "registered-nurse"
SHORT = "I would check it again."


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def outside(p, n=1):
    """Questions none of this version's activities is about."""
    planned = {
        i["href"].split("/questions/")[1].split("?")[0]
        for i in p["items"]
        if i["href"] and "/questions/" in i["href"]
    }
    planned |= {q for i in p["items"] if i["round"] for q in i["round"]["question_ids"] or []}
    return [q.id for q in questions_for(TRACK) if q.id not in planned][:n]


def update(client, h, version):
    return client.post("/api/v1/me/plan/update", headers=h, json={"version": version})


def versions(client):
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(PracticePlan))


def test_new_practice_is_named_and_the_plan_waits_until_asked(client):
    h = nurse(client)
    v1 = plan(client, h)
    assert v1["version"] == 1 and v1["news"] is None
    [qid] = outside(v1)
    weak = answer(client, h, TRACK, qid, WEAK)
    assert weak["score"] < 70 and weak["evidence_level"] == "sufficient"

    seen = plan(client, h)
    assert seen["version"] == 1  # reading never makes a version
    news = seen["news"]
    assert news["text"] == "1 answer since this plan, below 70."
    assert (news["answers"], news["retries"], news["below"], news["rounds"]) == (1, 0, 1, 0)
    [entry] = news["entries"]
    assert entry["kind"] == "answer" and entry["score"] == weak["score"]
    assert entry["href"] == f"/careers/{TRACK}/questions/{qid}?answer={weak['id']}"
    assert "improv" not in news["text"].lower()

    # Not updating: a reload, another tab and a fresh sign-in all show the same version.
    assert plan(client, h)["version"] == 1
    again = auth_headers(
        client.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": "CorrectHorse42"}
        ).json()
    )
    assert plan(client, again)["version"] == 1 and plan(client, again)["news"] == news
    assert versions(client) == 1

    r = update(client, h, 1)
    assert r.status_code == 200, r.text
    v2 = r.json()
    title = next(q.title for q in questions_for(TRACK) if q.id == qid)
    assert v2["version"] == 2 and v2["news"] is None
    assert any(i["kind"] == "retry" and i["title"] == f"Retry: {title}" for i in v2["items"])
    assert v2["changes"][0] == "Updated when you asked: 1 answer since version 1, below 70."
    assert any(c.startswith(f"Added “Retry: {title}”") for c in v2["changes"])
    assert plan(client, h)["version"] == 2


def test_two_tabs_updating_make_one_version_and_the_second_is_told(client):
    h = nurse(client)
    v1 = plan(client, h)
    answer(client, h, TRACK, outside(v1)[0], WEAK)
    first = update(client, h, 1)
    assert first.status_code == 200 and first.json()["version"] == 2
    second = update(client, h, 1)  # the other tab still shows version 1
    assert second.status_code == 409
    body = second.json()["error"]
    assert body["code"] == "plan_changed" and body["details"] == {"version": 2}
    assert "already updated" in body["message"] and "version 2" in body["message"]
    assert versions(client) == 2
    assert plan(client, h)["version"] == 2


def test_two_tabs_pressing_at_the_same_moment_make_one_version(client, monkeypatch):
    """Both pass the version check; the second insert meets the unique version and is told."""
    h = nurse(client)
    v1 = plan(client, h)
    answer(client, h, TRACK, outside(v1)[0], WEAK)
    real = Roadmap._new_version
    other_tab: dict = {}

    def the_other_tab_saves_first(self, *args, **kwargs):
        monkeypatch.setattr(Roadmap, "_new_version", real)
        other_tab["r"] = update(client, h, 1)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Roadmap, "_new_version", the_other_tab_saves_first)
    mine = update(client, h, 1)
    assert other_tab["r"].status_code == 200 and other_tab["r"].json()["version"] == 2
    assert mine.status_code == 409 and mine.json()["error"]["details"] == {"version": 2}
    assert versions(client) == 2


def test_evidence_the_planner_does_not_use_offers_no_update(client):
    h = nurse(client)
    v1 = plan(client, h)
    short_q, disputed_q, weak_q = outside(v1, 3)
    short = answer(client, h, TRACK, short_q, SHORT)
    assert short["evidence_level"] == "insufficient"
    assert plan(client, h)["news"] is None
    disputed = answer(client, h, TRACK, disputed_q, WEAK)
    flag(client, h, disputed["id"], "Overall")
    p = plan(client, h)
    assert p["version"] == 1 and p["news"] is None
    # Pressing anyway (a stale page): the same version, nothing made.
    same = update(client, h, 1)
    assert same.status_code == 200 and same.json()["version"] == 1 and versions(client) == 1

    # Next to evidence that counts, they're named as not counted.
    answer(client, h, TRACK, weak_q, WEAK)
    news = plan(client, h)["news"]
    assert news["answers"] == 1
    assert news["not_counted"] == [
        "1 answer too short to score isn’t counted.",
        "1 answer whose feedback you disputed isn’t counted.",
    ]


def test_practice_that_changes_nothing_the_planner_chooses_offers_nothing(client):
    """An answer to a question the plan already has as done evidence, or a strong one that moves no
    choice, keeps the version as it is and offers no update."""
    h = nurse(client)
    v1 = plan(client, h)
    question = next(i for i in v1["items"] if i["kind"] == "question")
    qid = question["href"].rsplit("/", 1)[1]
    answer(client, h, TRACK, qid, STRONG)  # completes it: the plan moves on as before, by itself
    v2 = plan(client, h)
    assert v2["version"] == 2 and v2["news"] is None
    answer(client, h, TRACK, qid, STRONG)  # the same question again: nothing it chooses changes
    p = plan(client, h)
    assert p["version"] == 2 and p["news"] is None


def test_a_finished_round_and_its_answers_are_counted(client):
    h = nurse(client)
    v1 = plan(client, h)
    assert v1["items"][0]["kind"] == "assessment"
    qs = outside(v1, 3)
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions", "question_ids": qs}).json()
    for i in range(3):
        r = client.post(
            f"/api/v1/interviews/{iv['id']}/answers", headers=h, json={"question_index": i, "answer": WEAK}
        )
        assert r.status_code == 200, r.text
    p = plan(client, h)
    assert p["version"] == 1
    news = p["news"]
    assert (news["answers"], news["rounds"]) == (3, 1)
    assert news["text"].startswith("3 answers and 1 finished round since this plan")
    assert {
        "kind": "round",
        "title": "Practice round (3 questions)",
        "score": None,
        "href": f"/interviews/{iv['id']}",
    } in news["entries"]
    v2 = update(client, h, 1).json()
    assert "Dropped the baseline check: there's now enough evidence to plan from." in v2["changes"]


def test_dropping_an_activity_the_learner_started_says_so(client):
    h = nurse(client)
    v1 = plan(client, h)
    assert v1["items"][0]["kind"] == "assessment"
    started = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "questions", "purpose": "baseline", "duration_minutes": 15},
    )
    assert started.status_code in (200, 201), started.text
    for qid in outside(v1, 3):
        answer(client, h, TRACK, qid, WEAK)
    v2 = update(client, h, 1).json()
    assert (
        "Dropped the baseline check: there's now enough evidence to plan from. You'd started it: that round "
        "stays open, and what you answer in it is saved."
    ) in v2["changes"]


def test_a_revision_is_counted_as_a_retry(client):
    h = nurse(client)
    # A strong answer before the plan exists: it isn't retried, so its question isn't in the plan.
    other_q = next(q.id for q in questions_for(TRACK) if grade(q, STRONG).score >= 70)
    strong = answer(client, h, TRACK, other_q, STRONG)
    v1 = plan(client, h)
    weak_q = next(q for q in outside(v1, 20) if q != other_q)
    answer(client, h, TRACK, weak_q, WEAK)
    r = client.post(
        f"/api/v1/careers/{TRACK}/questions/{other_q}/answers",
        headers=h,
        json={"answer": WEAK, "revises_answer_id": strong["id"]},
    )
    assert r.status_code == 201, r.text
    news = plan(client, h)["news"]
    assert (news["answers"], news["retries"], news["below"]) == (2, 1, 2)
    assert news["text"] == "2 answers (1 of them a retry) since this plan, both below 70."
    assert [e["kind"] for e in news["entries"]] == ["answer", "retry"]


def test_another_accounts_practice_never_counts_or_shows(client):
    a = nurse(client)
    v1 = plan(client, a)
    b = nurse(client, email="bea@example.com")
    plan(client, b)
    mine, theirs = outside(v1, 2)
    answer(client, b, TRACK, theirs, WEAK)
    assert plan(client, a)["news"] is None
    assert update(client, a, 1).json()["version"] == 1
    assert plan(client, b)["news"]["answers"] == 1
    # Beside the learner's own new practice, theirs still isn't counted or named.
    answer(client, a, TRACK, mine, WEAK)
    news = plan(client, a)["news"]
    assert news["answers"] == 1 and [e["href"].split("/")[4].split("?")[0] for e in news["entries"]] == [mine]


def test_an_update_before_any_plan_is_refused(client):
    h = nurse(client)
    r = update(client, h, 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "plan_changed"
    assert r.json()["error"]["details"] == {"version": None}
    assert versions(client) == 0


def test_the_one_line():
    assert news_text(1, 0, 1, 0, "this plan") == "1 answer since this plan, below 70."
    assert news_text(2, 0, 1, 0, "this plan") == "2 answers since this plan, one below 70."
    assert news_text(2, 0, 2, 0, "this plan") == "2 answers since this plan, both below 70."
    assert (
        news_text(3, 1, 0, 1, "version 4")
        == "3 answers (1 of them a retry) and 1 finished round since version 4."
    )
    assert news_text(1, 1, 0, 0, "this plan") == "1 retry since this plan."
    assert news_text(0, 0, 0, 2, "this plan") == "2 finished rounds since this plan."

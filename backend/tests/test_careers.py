"""Career tracks: the catalog, generated questions, answering with feedback, and the user's track."""

import collections

import pytest

from app.careers import CATALOG, DEFAULT_TRACK
from app.careers.grading import grade
from app.careers.profiles import MIN_METRICS, MIN_PEOPLE, MIN_SITUATIONS, MIN_SKILLS, MIN_TOOLS
from app.careers.questions import PER_LEVEL, get_question, questions_for
from tests.conftest import auth_headers, register

STRONG = (
    "Last winter, while I was working nights on a busy medical unit, one of my patients became confused and his "
    "oxygen levels started dropping during my 2 a.m. assessment. I was responsible for five patients that night, so "
    "I had to move fast. I checked his vital signs again, raised the head of the bed and started oxygen per "
    "protocol. I called the rapid response team and asked the charge nurse to cover my other call lights. I gave "
    "the doctor a clear update and documented everything in the electronic health record. As a result, he was "
    "moved to step-down care within 30 minutes and recovered fully. I learned to trust my assessment early and "
    "escalate quickly rather than wait to be sure."
)


def test_the_catalog_covers_over_a_hundred_jobs_with_complete_profiles():
    assert len(CATALOG) >= 100
    assert DEFAULT_TRACK in CATALOG and CATALOG[DEFAULT_TRACK].has_coding
    for slug, p in CATALOG.items():
        assert len(p.skills) >= MIN_SKILLS and len(p.tools) >= MIN_TOOLS, slug
        assert len(p.situations) >= MIN_SITUATIONS and len(p.people) >= MIN_PEOPLE, slug
        assert len(p.metrics) >= MIN_METRICS, slug
        assert all(s[0].islower() or s[0] == "I" or s.split()[0][:1].isupper() for s in p.situations), slug


@pytest.mark.parametrize("slug", sorted(CATALOG))
def test_every_job_gets_three_hundred_distinct_questions(slug):
    qs = questions_for(slug)
    assert collections.Counter(q.difficulty for q in qs) == {
        "easy": PER_LEVEL,
        "medium": PER_LEVEL,
        "hard": PER_LEVEL,
    }
    assert len({q.id for q in qs}) == len(qs)
    assert len({q.prompt for q in qs}) == len(qs)
    assert len({q.title for q in qs}) == len(qs)
    for q in qs:
        assert q.rubric and q.outline and q.tips, q.id
        assert "{" not in q.prompt and "{" not in q.title and not any("{" in line for line in q.outline), q.id


def test_question_ids_are_stable_and_first_page_is_varied():
    first = [q.id for q in questions_for("registered-nurse")[:5]]
    assert first == ["e-good-0", "e-steps-0", "e-time-0", "e-mistake-0", "e-explain-0"]
    assert get_question("registered-nurse", "m-walk-0").prompt.startswith(
        "A patient's vital signs drop suddenly"
    )


def test_the_grader_rewards_a_complete_star_answer_and_explains_gaps():
    q = get_question("registered-nurse", "m-pressure-0")
    strong, weak = grade(q, STRONG), grade(q, "I am good at patient assessment and work well under pressure.")
    assert strong.score >= 85 and strong.rating == "Strong" and all(p.covered for p in strong.points)
    assert weak.score <= 35 and weak.rating == "Needs work"
    assert any("words" in n for n in weak.notes)
    assert [p.covered for p in weak.points].count(False) >= 4


def test_careers_endpoint_lists_jobs_grouped_by_category(client):
    careers = client.get("/api/v1/careers").json()
    assert len(careers) == len(CATALOG)
    nurse = next(c for c in careers if c["slug"] == "registered-nurse")
    assert nurse == {
        "slug": "registered-nurse",
        "title": "Registered Nurse",
        "category": "Healthcare",
        "summary": CATALOG["registered-nurse"].summary,
        "has_coding": False,
        "question_count": 300,
    }
    categories = [c["category"] for c in careers]
    assert categories == sorted(categories, key=categories.index)  # grouped, not interleaved


def test_questions_are_paged_filtered_searched_and_counted(client):
    base = "/api/v1/careers/registered-nurse/questions"
    first = client.get(base, params={"difficulty": "easy", "page_size": 5}).json()
    assert first["total"] == 100 and len(first["items"]) == 5
    assert {i["difficulty"] for i in first["items"]} == {"easy"}
    found = client.get(base, params={"q": "medication error"}).json()
    assert found["total"] > 0 and any("medication" in i["prompt"].lower() for i in found["items"][:3])
    counts = client.get(f"{base}/counts", params={"q": "medication error"}).json()
    assert sum(counts.values()) == found["total"]
    assert client.get("/api/v1/careers/astronaut/questions").status_code == 404
    assert client.get(f"{base}/nope-1").status_code == 404
    detail = client.get(f"{base}/m-walk-0").json()
    assert detail["career_title"] == "Registered Nurse" and detail["tips"] and detail["rubric_labels"]


def test_answering_needs_an_account_and_stores_feedback(client, user_headers):
    url = "/api/v1/careers/registered-nurse/questions/m-pressure-0/answers"
    assert client.post(url, json={"answer": STRONG}).status_code == 401
    r = client.post(url, headers=user_headers, json={"answer": STRONG})
    assert r.status_code == 201
    body = r.json()
    assert body["score"] >= 85 and body["coach"] == "built-in (offline)" and body["outline"]
    assert all(p["covered"] for p in body["points"])
    client.post(url, headers=user_headers, json={"answer": "Too short."})
    mine = client.get(url, headers=user_headers).json()
    assert [a["answer"] for a in mine] == ["Too short.", STRONG]  # newest first
    listed = client.get(
        "/api/v1/careers/registered-nurse/questions",
        headers=user_headers,
        params={"difficulty": "medium", "q": "pressure"},
    ).json()
    assert next(i for i in listed["items"] if i["id"] == "m-pressure-0")["best_score"] == body["score"]
    progress = client.get("/api/v1/careers/registered-nurse/progress", headers=user_headers).json()
    assert progress == {
        "track": "registered-nurse",
        "answered": 1,
        "strong": 1,
        "by_difficulty": {"easy": 0, "medium": 1, "hard": 0},
        "total_questions": 300,
    }
    other = auth_headers(register(client, email="eve@example.com"))
    assert client.get(url, headers=other).json() == []  # answers are private
    export = client.get("/api/v1/me/export", headers=user_headers).json()
    assert len(export["interview_answers"]) == 2


def test_answers_are_rate_limited(make_client):
    c = make_client(practice_answers_per_hour=2)
    h = auth_headers(register(c))
    url = "/api/v1/careers/accountant/questions/e-good-0/answers"
    assert [c.post(url, headers=h, json={"answer": "x"}).status_code for _ in range(3)] == [201, 201, 429]


def test_people_choose_a_career_at_signup_and_can_change_it(client):
    tokens = register(client, career_track="registered-nurse")
    assert tokens["user"]["career_track"] == "registered-nurse"
    h = auth_headers(tokens)
    me = client.patch("/api/v1/auth/me", headers=h, json={"career_track": "teaching-assistant"}).json()
    assert me["career_track"] == "teaching-assistant"
    renamed = client.patch("/api/v1/auth/me", headers=h, json={"display_name": "Ada"}).json()
    assert renamed["career_track"] == "teaching-assistant"  # partial update keeps the track
    assert client.patch("/api/v1/auth/me", headers=h, json={"career_track": "wizard"}).status_code == 422
    assert (
        client.patch("/api/v1/auth/me", headers=h, json={"career_track": "accountant"}).json()["display_name"]
        == "Ada"
    )
    guest = client.post("/api/v1/auth/guest", json={"career_track": "barista"}).json()
    assert guest["user"]["career_track"] == "barista"
    assert client.post("/api/v1/auth/guest").json()["user"]["career_track"] == DEFAULT_TRACK


def test_unknown_career_is_rejected_at_signup(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "CorrectHorse42", "career_track": "astronaut"},
    )
    assert r.status_code == 422


def test_a_too_short_answer_is_never_summarised_as_solid():
    q = get_question("registered-nurse", "m-walk-0")
    assert q is not None
    fb = grade(q, "I checked the airway, prioritized, called the team and followed up.")
    assert fb.score <= 35 and fb.rating == "Needs work"
    assert fb.summary.startswith("Too short to be convincing yet") and "Solid" not in fb.summary

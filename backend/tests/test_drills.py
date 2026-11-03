"""Communication drills: career-aware prompts, attempts that only count when there's something to
review, measurements that are only what was measured, feedback that never penalises fillers or
typing, comparisons under the same rubric, and privacy."""

from sqlalchemy import select

from app.drills import BY_ID
from app.drills.feedback import clean_transcript, compare, evaluate
from app.models import DrillAttempt
from tests.conftest import auth_headers, register

URL = "/api/v1/me/drills"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def test_five_drills_with_prompts_from_your_own_career(client):
    h = nurse(client)
    drills = client.get(URL, headers=h).json()
    assert [d["id"] for d in drills] == ["intro", "example", "explain", "clarify", "followup"]
    intro = drills[0]
    assert intro["target_seconds"] == 60 and "registered nurse" in intro["prompt"].lower()
    assert all(d["target_seconds"] is None for d in drills[1:])  # speed isn't the point elsewhere
    assert all(len(d["looks_for"]) == 3 for d in drills)
    coder = auth_headers(register(client, email="lin@example.com"))
    assert "software engineer" in client.get(f"{URL}/intro", headers=coder).json()["prompt"].lower()


def test_nothing_to_review_is_not_an_attempt(client):
    h = nurse(client)
    for text in ("   ", "um uh", "Hi."):
        r = client.post(
            f"{URL}/intro/attempts", headers=h, json={"text": text, "source": "voice", "spoken_seconds": 4}
        )
        assert r.status_code in (400, 422), text
    assert client.get(f"{URL}/intro/attempts", headers=h).json() == []
    assert (
        client.post(
            f"{URL}/intro/attempts",
            headers=h,
            json={"text": "I am a nurse on a ward.", "source": "typed", "spoken_seconds": 30},
        ).status_code
        == 400
    )


def test_measurements_are_only_what_was_measured_and_fillers_are_never_penalised(client):
    h = nurse(client)
    spoken = "Um, I'm a registered nurse with three years on a medical ward. Uh, I've led handovers and trained new staff, which is why I want this role."
    v = client.post(
        f"{URL}/intro/attempts", headers=h, json={"text": spoken, "source": "voice", "spoken_seconds": 41}
    ).json()
    m = v["feedback"]["measured"]
    assert m["spoken_seconds"] == 41 and m["words"] == 25 and "reading_estimate_seconds" in m
    assert any("filler sound" in n and "aren't marked down" in n for n in v["feedback"]["notes"])
    assert all(o["present"] for o in v["feedback"]["observations"])
    typed = client.post(
        f"{URL}/intro/attempts",
        headers=h,
        json={"text": spoken.replace("Um, ", "").replace("Uh, ", ""), "source": "typed"},
    ).json()
    assert "spoken_seconds" not in typed["feedback"]["measured"]  # never invented for typed answers
    assert [o["present"] for o in typed["feedback"]["observations"]] == [
        o["present"] for o in v["feedback"]["observations"]
    ]  # typing isn't penalised


def test_feedback_describes_the_words_and_points_out_generalities():
    drill = BY_ID["example"]
    vague = evaluate(
        drill,
        "Tell me about a time patient assessment mattered.",
        "I'm a hard worker and a team player and I always do my best.",
        "typed",
        None,
    )
    assert vague["generalities"] == ["hard worker", "team player", "always"]
    assert vague["observations"][1]["present"] is False  # no specific situation
    specific = evaluate(
        drill,
        "Tell me about a time patient assessment mattered.",
        "Last month when I was on nights, a patient's assessment showed falling blood pressure. I called the doctor, so we started fluids and he recovered.",
        "typed",
        None,
    )
    assert specific["generalities"] == [] and all(o["present"] for o in specific["observations"])
    assert clean_transcript("um so uh I did it")[1] == 2


def test_repeats_are_compared_under_the_same_rubric_and_originals_kept(client):
    h = nurse(client)
    first = client.post(
        f"{URL}/example/attempts",
        headers=h,
        json={"text": "Patient assessment matters because patients change quickly.", "source": "typed"},
    ).json()
    assert first["compared_with_previous"] is None
    second = client.post(
        f"{URL}/example/attempts",
        headers=h,
        json={
            "text": "Last week when I was on nights I checked a patient whose breathing changed. I called the team, so he was seen within minutes.",
            "source": "typed",
        },
    ).json()
    assert any(
        c.startswith("Now there: gives one specific situation") for c in second["compared_with_previous"]
    )
    history = client.get(f"{URL}/example/attempts", headers=h).json()
    assert [a["id"] for a in history] == [second["id"], first["id"]] and history[1]["text"] == first["text"]
    assert compare({"rubric_version": 0, "observations": []}, second["feedback"])[0].startswith(
        "These attempts were checked with different rubric versions"
    )


def test_retries_save_once_and_drills_are_private(client):
    h = nurse(client)
    body = {
        "text": "I'm a nurse and I want this role because I like acute care.",
        "source": "typed",
        "client_request_id": "d1",
    }
    a = client.post(f"{URL}/intro/attempts", headers=h, json=body)
    b = client.post(f"{URL}/intro/attempts", headers=h, json=body)
    assert a.status_code == 201 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    other = nurse(client, email="bea@example.com")
    assert client.get(f"{URL}/intro/attempts", headers=other).json() == []
    assert client.get(f"{URL}/nope", headers=h).status_code == 404
    exported = client.get("/api/v1/me/export", headers=h).json()["drill_attempts"]
    assert len(exported) == 1 and exported[0]["drill"] == "intro"
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert db.scalars(select(DrillAttempt)).all() == []


def test_a_drill_can_be_bookmarked_collected_and_scheduled(client):
    h = nurse(client)
    ref = {"item_type": "drill", "track": "", "ref_id": "clarify"}
    marks = client.put("/api/v1/me/bookmarks", headers=h, json=ref)
    assert marks.status_code == 200, marks.text
    mark = next(m for m in marks.json() if m["item_type"] == "drill")
    assert (
        mark["title"] == "Drill: Ask a clarifying question"
        and mark["href"] == "/drills/clarify"
        and mark["available"]
    )
    assert client.put("/api/v1/me/bookmarks", headers=h, json={**ref, "ref_id": "nope"}).status_code == 404
    c = client.post("/api/v1/me/collections", headers=h, json={"name": "Between interviews"}).json()
    added = client.post(f"/api/v1/me/collections/{c['id']}/items", headers=h, json=ref)
    assert added.status_code in (200, 201), added.text
    item = added.json()["item_list"][0]
    assert item["practiced_since_added"] is False
    client.post(
        f"{URL}/clarify/attempts",
        headers=h,
        json={
            "text": "Which part of the ward would this be on, and how many patients would I have?",
            "source": "typed",
        },
    )
    item = client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()["item_list"][0]
    assert item["practiced_since_added"] is True
    entry = client.post(
        "/api/v1/me/schedule",
        headers=h,
        json={"kind": "drill", "ref": "intro", "on_date": "2030-01-07", "all_day": True},
    )
    assert entry.status_code == 201, entry.text
    assert entry.json()["title"] == "Drill: Introduce yourself briefly" and entry.json()["done_at"] is None
    assert (
        client.post(
            "/api/v1/me/schedule",
            headers=h,
            json={"kind": "drill", "ref": "nope", "on_date": "2030-01-07", "all_day": True},
        ).status_code
        == 404
    )

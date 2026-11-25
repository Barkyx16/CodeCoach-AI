"""The optional first-session introduction: a career-appropriate real starter, a tour whose state
is the learner's own and never counts as practice, resume/skip/replay, and a format introduction
after a career change."""

from sqlalchemy import select

from app.models import OnboardingState, User
from tests.conftest import auth_headers, register

URL = "/api/v1/me/onboarding"
NURSE = "registered-nurse"
ANSWER = "I check airway, breathing and circulation first, then vital signs, then I ask the patient how they feel and compare with the last set of observations."


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def coder(client, email="lin@example.com"):
    return auth_headers(register(client, email=email, display_name="Lin"))


def patch(client, h, **body):
    r = client.patch(URL, headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_new_learner_is_welcomed_with_a_real_activity_from_their_own_career(client):
    n = client.get(URL, headers=nurse(client)).json()
    assert n["tour_status"] == "not_started" and n["welcome_due"] is True and n["first_activity_at"] is None
    assert n["format"] == "written" and n["tour_steps"] == 5
    s = n["starter"]
    # A nurse starts with an easy nursing question from the real bank, never Java.
    assert s["kind"] == "question" and s["track"] == NURSE and s["difficulty"] == "easy"
    assert s["href"] == f"/careers/{NURSE}/questions/{s['ref']}"
    q = client.get(f"/api/v1/careers/{NURSE}/questions/{s['ref']}").json()
    assert q["title"] == s["title"]

    c = client.get(URL, headers=coder(client)).json()
    assert c["format"] == "coding"
    assert c["starter"] == {
        "kind": "problem",
        "track": "software-engineer",
        "ref": "two-sum",
        "title": client.get("/api/v1/problems/two-sum").json()["title"],
        "difficulty": "easy",
        "href": "/problems/two-sum",
        "minutes": 15,
    }
    # Reading the state never creates a row.
    with client.app.state.session_factory() as db:
        assert db.scalars(select(OnboardingState)).all() == []


def test_guests_get_the_same_introduction_for_the_career_they_chose(client):
    g = client.post("/api/v1/auth/guest", json={"career_track": "accountant"}).json()
    h = auth_headers(g)
    state = client.get(URL, headers=h).json()
    assert state["welcome_due"] and state["starter"]["track"] == "accountant" and state["format"] == "written"
    assert patch(client, h, start_choice="intro", tour="start")["tour_status"] == "in_progress"
    assert client.get(URL).status_code == 401


def test_the_tour_can_be_stepped_paused_resumed_finished_and_replayed(client):
    h = nurse(client)
    s = patch(client, h, start_choice="intro", tour="start")
    assert (s["tour_status"], s["tour_kind"], s["tour_step"], s["welcome_due"]) == (
        "in_progress",
        "written",
        0,
        False,
    )
    assert patch(client, h, tour="step", tour_step=2)["tour_step"] == 2
    # A refresh reads the same place back.
    assert client.get(URL, headers=h).json()["tour_step"] == 2
    paused = patch(client, h, tour="pause")
    assert paused["tour_status"] == "paused" and paused["resume_due"] is True and paused["tour_step"] == 2
    assert patch(client, h, dismiss="resume_tour")["resume_due"] is False
    # Resuming moves it on and clears nothing else.
    resumed = patch(client, h, tour="step", tour_step=3)
    assert resumed["tour_status"] == "in_progress" and resumed["tour_step"] == 3
    # Steps past the end are clamped, not stored.
    assert patch(client, h, tour="step", tour_step=20)["tour_step"] == 4
    done = patch(client, h, tour="complete")
    assert done["tour_status"] == "completed" and done["resume_due"] is False
    # A late step from another tab doesn't reopen a finished tour; skipping doesn't undo it.
    assert patch(client, h, tour="step", tour_step=1)["tour_status"] == "completed"
    assert patch(client, h, tour="skip")["tour_status"] == "completed"
    # Replay from Help starts over, and brings back the resume reminder if it's left again.
    replay = patch(client, h, tour="start")
    assert replay["tour_status"] == "in_progress" and replay["tour_step"] == 0
    assert patch(client, h, tour="pause")["resume_due"] is True


def test_skipping_and_choosing_the_library_are_respected(client):
    h = nurse(client)
    later = patch(client, h, start_choice="later")
    assert later["tour_status"] == "skipped" and later["welcome_due"] is False
    h2 = nurse(client, email="bea@example.com")
    lib = patch(client, h2, start_choice="library")
    assert (
        lib["tour_status"] == "not_started"
        and lib["welcome_due"] is False
        and lib["start_choice"] == "library"
    )
    # Repeating a choice is harmless.
    assert patch(client, h2, start_choice="library") == lib


def test_invalid_updates_are_refused(client):
    h = nurse(client)
    for body in (
        {"tour": "dance"},
        {"tour_step": -1},
        {"tour_step": 99},
        {"dismiss": "everything"},
        {"start_choice": "x"},
    ):
        r = client.patch(URL, headers=h, json=body)
        assert r.status_code == 422, body


def test_the_introduction_never_counts_as_practice_and_real_activity_is_recognised(client):
    h = nurse(client)
    before = (
        client.get("/api/v1/me/progress", headers=h).json(),
        client.get("/api/v1/me/activity", headers=h).json(),
    )
    patch(client, h, start_choice="intro", tour="start")
    for step in range(5):
        patch(client, h, tour="step", tour_step=step)
    patch(client, h, tour="complete")
    after = (
        client.get("/api/v1/me/progress", headers=h).json(),
        client.get("/api/v1/me/activity", headers=h).json(),
    )
    assert after == before
    assert client.get(URL, headers=h).json()["first_activity_at"] is None

    starter = client.get(URL, headers=h).json()["starter"]
    r = client.post(
        f"/api/v1/careers/{NURSE}/questions/{starter['ref']}/answers", headers=h, json={"answer": ANSWER}
    )
    assert r.status_code == 201, r.text
    state = client.get(URL, headers=h).json()
    assert state["first_activity_at"] is not None and state["tour_status"] == "completed"


def test_an_existing_learner_who_has_practised_is_not_welcomed_again(client):
    h = nurse(client)
    starter = client.get(URL, headers=h).json()["starter"]
    client.post(
        f"/api/v1/careers/{NURSE}/questions/{starter['ref']}/answers", headers=h, json={"answer": ANSWER}
    )
    assert client.get(URL, headers=h).json()["welcome_due"] is False


def test_a_career_change_offers_that_formats_introduction_once_without_resetting_anything(client):
    h = coder(client)
    patch(client, h, start_choice="practice")
    assert client.get(URL, headers=h).json()["career_intro"] is None
    client.patch("/api/v1/auth/me", headers=h, json={"career_track": NURSE})
    state = client.get(URL, headers=h).json()
    assert state["career_intro"] == {"track": NURSE, "title": "Registered Nurse", "kind": "written"}
    assert state["starter"]["track"] == NURSE and state["start_choice"] == "practice"
    # Taking it starts the written tour; either way the offer isn't repeated.
    taken = patch(client, h, career_intro_seen=True, tour="start", tour_kind="written")
    assert (
        taken["career_intro"] is None
        and taken["tour_kind"] == "written"
        and taken["tour_status"] == "in_progress"
    )
    client.patch("/api/v1/auth/me", headers=h, json={"career_track": "software-engineer"})
    assert client.get(URL, headers=h).json()["career_intro"] is None  # seen when they started


def test_a_retired_starter_is_never_offered(client):
    h = coder(client)
    root = auth_headers(register(client, email="root@example.com"))
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.email == "root@example.com")).is_admin = True
        db.commit()
    client.post(
        "/api/v1/admin/content/problem/two-sum/retire", headers=root, json={"reason": "A test was wrong."}
    )
    starter = client.get(URL, headers=h).json()["starter"]
    assert starter["kind"] == "problem" and starter["ref"] != "two-sum" and starter["difficulty"] == "easy"


def test_state_is_private_exported_and_deleted_with_the_account(client):
    a = nurse(client)
    b = coder(client)
    patch(client, a, start_choice="intro", tour="start")
    assert client.get(URL, headers=b).json()["tour_status"] == "not_started"  # only ever your own
    exported = client.get("/api/v1/me/export", headers=a).json()
    assert exported["onboarding"]["tour_status"] == "in_progress"
    assert exported["onboarding"]["start_choice"] == "intro"
    assert client.get("/api/v1/me/export", headers=b).json()["onboarding"] is None
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=a, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code == 204, r.text
    with client.app.state.session_factory() as db:
        assert len(db.scalars(select(OnboardingState)).all()) == 0

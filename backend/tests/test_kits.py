"""Interview-day kits: useful with only a role and a time, suggestions labelled and grounded in
the learner's own job target, nothing verified on their behalf, private links, owner-only."""

from sqlalchemy import select

from app.models import InterviewKit
from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"
JD = "Registered Nurse, Medical Ward. Responsibilities: assess and prioritise patient care. We offer a structured induction and preceptorship. 12-hour shifts."


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def event(client, h, **over):
    a = client.post(
        APPS, headers=h, json={"employer": "Mercy General", "role_title": "Ward nurse", **over}
    ).json()
    ev = client.post(
        f"{APPS}/{a['id']}/events",
        headers=h,
        json={
            "title": "Panel interview",
            "on_date": "2026-11-12",
            "local_time": "10:00",
            "timezone": "Europe/London",
        },
    ).json()["events"][0]
    return a, ev, f"{APPS}/{a['id']}/events/{ev['id']}/kit"


def test_a_kit_is_useful_with_only_a_role_and_a_time_and_stores_nothing_until_changed(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    r = client.get(url, headers=h)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    kit = r.json()
    assert kit["saved"] is False and kit["format"] == "unknown" and kit["role_title"] == "Ward nurse"
    assert kit["starts_at"].startswith("2026-11-12T10:00:00")
    assert all(c["origin"] == "suggested" and not c["done"] for c in kit["checklist"])
    assert "Find out whether it's remote, by phone or in person" in [c["text"] for c in kit["checklist"]]
    assert {q["group"] for q in kit["questions"]} >= {"role", "team", "training", "workflow", "next_steps"}
    with client.app.state.session_factory() as db:
        assert db.scalars(select(InterviewKit)).all() == []


def test_questions_come_from_your_own_target_and_never_claim_employer_facts(client):
    h = nurse(client)
    t = client.post("/api/v1/targets", headers=h, json={"title": "Ward nurse", "description": JD}).json()
    a, ev, url = event(client, h, target_id=t["id"])
    kit = client.get(url, headers=h).json()
    from_target = [q for q in kit["questions"] if q["id"].startswith("s-req-")]
    assert from_target and all(
        q["note"].startswith("Based on a requirement from your job target") for q in from_target
    )
    training = next(q for q in kit["questions"] if q["group"] == "training")
    assert (
        "mentions “induction”" in training["note"] and training["excluded"] is False
    )  # pointed out, not hidden
    workflow = next(q for q in kit["questions"] if q["group"] == "workflow")
    assert "shifts" in workflow["note"]


def test_switching_format_swaps_untouched_suggestions_and_keeps_yours(client):
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    checklist = kit["checklist"]
    checklist[0]["done"] = True  # the learner ticked "Confirm the date…"
    checklist.append({"id": "u-1", "text": "Print my registration card", "origin": "yours"})
    saved = client.put(url, headers=h, json={"checklist": checklist}).json()
    assert saved["saved"] is True
    remote = client.put(url, headers=h, json={"format": "remote"}).json()
    texts = [c["text"] for c in remote["checklist"]]
    assert "Print my registration card" in texts and "Check your microphone and camera" in texts
    assert "Find out whether it's remote, by phone or in person" not in texts
    assert (
        next(c for c in remote["checklist"] if c["text"] == "Confirm the date, time and time zone")["done"]
        is True
    )


def test_editing_hiding_reordering_and_excluding_are_kept(client):
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    qs = kit["questions"]
    qs.reverse()  # priority is the order you save
    qs[0]["excluded"] = True
    qs.append(
        {"id": "u-q", "text": "How is feedback given to new nurses?", "group": "training", "origin": "yours"}
    )
    cl = kit["checklist"]
    cl[1]["hidden"] = True
    out = client.put(
        url,
        headers=h,
        json={"questions": qs, "checklist": cl, "interviewers": [{"name": "", "role": "Ward manager"}]},
    ).json()
    assert [q["id"] for q in out["questions"]] == [q["id"] for q in qs]
    assert out["questions"][0]["excluded"] and out["questions"][-1]["origin"] == "yours"
    assert out["checklist"][1]["hidden"] and out["interviewers"] == [{"name": "", "role": "Ward manager"}]


def test_links_are_checked_and_stories_must_be_yours(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    _, _, url = event(client, h)
    for bad in ("javascript:alert(1)", "zoommtg://x", "https://exa mple.com"):
        assert client.put(url, headers=h, json={"meeting_link": bad}).status_code == 422, bad
    assert (
        client.put(url, headers=h, json={"meeting_link": "https://meet.example.com/abc?pwd=1"}).json()[
            "meeting_link"
        ]
        == "https://meet.example.com/abc?pwd=1"
    )
    assert client.put(url, headers=h, json={"clear_meeting_link": True}).json()["meeting_link"] is None
    mine = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": "Two call lights", "short_version": "I triaged by risk."},
    ).json()
    theirs = client.post("/api/v1/me/stories", headers=other, json={"title": "Not yours"}).json()
    assert client.put(url, headers=h, json={"story_ids": [theirs["id"]]}).status_code == 404
    out = client.put(url, headers=h, json={"story_ids": [mine["id"]]}).json()
    assert out["stories"] == [
        {"id": mine["id"], "title": "Two call lights", "short_version": "I triaged by risk."}
    ]


def test_kits_are_private_exported_and_deleted(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    a, ev, url = event(client, h)
    client.put(
        url, headers=h, json={"notes": "Ask about parking.", "meeting_link": "https://meet.example.com/x"}
    )
    assert client.get(url, headers=other).status_code == 404
    assert client.put(url, headers=other, json={"notes": "x"}).status_code == 404
    exported = client.get("/api/v1/me/export", headers=h).json()["interview_kits"]
    assert exported[0]["notes"] == "Ask about parking."
    # Deleting the event deletes its kit.
    client.delete(f"{APPS}/{a['id']}/events/{ev['id']}", headers=h)
    with client.app.state.session_factory() as db:
        assert db.scalars(select(InterviewKit)).all() == []


def test_a_format_change_saved_with_the_whole_kit_still_gets_that_formats_suggestions(client):
    # The page saves everything at once: the new format together with the checklist it showed.
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    out = client.put(
        url,
        headers=h,
        json={"format": "in_person", "checklist": kit["checklist"], "questions": kit["questions"]},
    ).json()
    texts = [c["text"] for c in out["checklist"]]
    assert "Check the address and how long it takes to get there" in texts
    assert "Find out whether it's remote, by phone or in person" not in texts

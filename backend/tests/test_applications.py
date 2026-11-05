"""Private application tracker: recorded facts only, safe retries, history that's never rewritten,
interview events with exact times (and honest refusals around daylight saving), private links."""

from sqlalchemy import select

from app.models import Application, ApplicationEvent, ApplicationStageChange
from tests.conftest import auth_headers, register

URL = "/api/v1/me/applications"
NURSE = "registered-nurse"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def create(client, h, **over):
    body = {"employer": "Mercy General", "role_title": "Ward nurse", **over}
    r = client.post(URL, headers=h, json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_recording_an_application_and_retrying_safely(client):
    h = nurse(client)
    first = client.post(
        URL, headers=h, json={"employer": "Mercy", "role_title": "RN", "client_request_id": "req-1"}
    )
    again = client.post(
        URL, headers=h, json={"employer": "Mercy", "role_title": "RN", "client_request_id": "req-1"}
    )
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert len(client.get(URL, headers=h).json()) == 1
    a = first.json()
    assert a["stage"] == "saved" and a["applied_on"] is None
    assert [(x["from_stage"], x["to_stage"]) for x in a["history"]] == [(None, "saved")]


def test_stage_changes_are_history_and_never_rewritten(client):
    h = nurse(client)
    a = create(client, h)
    client.post(f"{URL}/{a['id']}/stage", headers=h, json={"stage": "applied", "note": "Sent the form."})
    # A repeated click (or a second tab) changes nothing.
    same = client.post(f"{URL}/{a['id']}/stage", headers=h, json={"stage": "applied"}).json()
    assert len(same["history"]) == 2
    # A mistake is corrected as its own entry.
    client.post(f"{URL}/{a['id']}/stage", headers=h, json={"stage": "offer"})
    fixed = client.post(
        f"{URL}/{a['id']}/stage", headers=h, json={"stage": "interviewing", "correction": True}
    ).json()
    assert fixed["stage"] == "interviewing"
    assert [(x["from_stage"], x["to_stage"], x["correction"]) for x in fixed["history"]] == [
        ("offer", "interviewing", True),
        ("applied", "offer", False),
        ("saved", "applied", False),
        (None, "saved", False),
    ]
    # Renaming the role later doesn't rewrite what the history says.
    renamed = client.patch(
        f"{URL}/{a['id']}", headers=h, json={"role_title": "Senior ward nurse", "employer": "Mercy Health"}
    ).json()
    assert renamed["role_title"] == "Senior ward nurse"
    assert {(x["role_title"], x["employer"]) for x in renamed["history"]} == {("Ward nurse", "Mercy General")}
    assert client.post(f"{URL}/{a['id']}/stage", headers=h, json={"stage": "hired"}).status_code == 422


def test_dates_are_the_learners_and_unknown_is_fine(client):
    h = nurse(client)
    a = create(
        client, h, applied_on="2026-10-30", next_action="Call the recruiter", next_action_due="2026-11-05"
    )
    assert a["applied_on"] == "2026-10-30" and a["next_action_due"] == "2026-11-05"
    cleared = client.patch(
        f"{URL}/{a['id']}", headers=h, json={"clear": ["applied_on", "next_action_due"]}
    ).json()
    assert (
        cleared["applied_on"] is None
        and cleared["next_action_due"] is None
        and cleared["next_action"] == "Call the recruiter"
    )


def test_interview_events_keep_exact_times_and_refuse_impossible_ones(client):
    h = nurse(client)
    a = create(client, h)
    url = f"{URL}/{a['id']}/events"
    one = client.post(
        url,
        headers=h,
        json={
            "title": "Phone screen",
            "kind": "phone_screen",
            "on_date": "2026-07-01",
            "local_time": "09:30",
            "timezone": "Europe/London",
        },
    )
    assert one.status_code == 200, one.text
    (e,) = one.json()["events"]
    assert e["starts_at"].startswith("2026-07-01T08:30:00")  # 09:30 BST is 08:30 UTC
    # Unknown date and time are fine: no instant is invented.
    two = client.post(url, headers=h, json={"title": "Panel interview"}).json()
    assert [x["starts_at"] for x in two["events"] if x["title"] == "Panel interview"] == [None]
    # The hour that doesn't exist when clocks go forward is refused, not shifted.
    gap = client.post(
        url,
        headers=h,
        json={"title": "X", "on_date": "2026-03-08", "local_time": "02:30", "timezone": "America/Chicago"},
    )
    assert gap.status_code == 400 and gap.json()["error"]["code"] == "nonexistent_time"
    # The hour that happens twice needs a choice; with one, the right instant is kept.
    amb = client.post(
        url,
        headers=h,
        json={"title": "X", "on_date": "2026-11-01", "local_time": "01:30", "timezone": "America/Chicago"},
    )
    assert amb.status_code == 400 and amb.json()["error"]["code"] == "ambiguous_time"
    assert amb.json()["error"]["details"]["first_offset"] == "-0500"
    chosen = client.post(
        url,
        headers=h,
        json={
            "title": "Night interview",
            "on_date": "2026-11-01",
            "local_time": "01:30",
            "timezone": "America/Chicago",
            "fold": 1,
        },
    ).json()
    assert [x["starts_at"][:19] for x in chosen["events"] if x["title"] == "Night interview"] == [
        "2026-11-01T07:30:00"
    ]
    for bad in (
        {"title": "X", "timezone": "EST", "on_date": "2026-01-01", "local_time": "09:00"},
        {"title": "X", "local_time": "25:00", "on_date": "2026-01-01", "timezone": "UTC"},
        {"title": "X", "local_time": "09:00", "timezone": "UTC"},
    ):
        assert client.post(url, headers=h, json=bad).status_code == 400, bad


def test_repeated_interviews_stay_separate_and_retries_dont_duplicate(client):
    h = nurse(client)
    a = create(client, h)
    url = f"{URL}/{a['id']}/events"
    client.post(
        url, headers=h, json={"title": "First interview", "on_date": "2026-11-10", "client_request_id": "e1"}
    )
    client.post(
        url, headers=h, json={"title": "First interview", "on_date": "2026-11-10", "client_request_id": "e1"}
    )
    out = client.post(
        url, headers=h, json={"title": "Second interview", "on_date": "2026-11-20", "client_request_id": "e2"}
    ).json()
    assert [e["title"] for e in out["events"]] == ["First interview", "Second interview"]
    event_id = out["events"][0]["id"]
    edited = client.put(
        f"{url}/{event_id}", headers=h, json={"title": "First interview (moved)", "on_date": "2026-11-11"}
    ).json()
    assert edited["events"][0]["title"] == "First interview (moved)"
    assert len(client.delete(f"{url}/{event_id}", headers=h).json()["events"]) == 1


def test_links_are_your_own_and_never_copies(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    t = client.post(
        "/api/v1/targets", headers=h, json={"title": "Ward nurse", "description": "Assess patients."}
    ).json()
    s = client.post("/api/v1/me/stories", headers=h, json={"title": "Two call lights"}).json()
    theirs = client.post("/api/v1/me/stories", headers=other, json={"title": "Not yours"}).json()
    a = create(client, h)
    linked = client.patch(
        f"{URL}/{a['id']}", headers=h, json={"target_id": t["id"], "story_ids": [s["id"]]}
    ).json()
    assert linked["target"] == {"id": t["id"], "title": "Ward nurse"} and linked["stories"] == [
        {"id": s["id"], "title": "Two call lights"}
    ]
    assert client.patch(f"{URL}/{a['id']}", headers=h, json={"story_ids": [theirs["id"]]}).status_code == 404
    # Renaming the story shows the new title: it's a link, not a copy.
    client.patch(
        f"/api/v1/me/stories/{s['id']}",
        headers=h,
        json={"title": "Two call lights at once", "expected_revision": 1},
    )
    assert (
        client.get(f"{URL}/{a['id']}", headers=h).json()["stories"][0]["title"] == "Two call lights at once"
    )
    # Deleting the target unlinks it.
    client.delete(f"/api/v1/targets/{t['id']}", headers=h)
    assert client.get(f"{URL}/{a['id']}", headers=h).json()["target"] is None


def test_untrusted_input_is_checked(client):
    h = nurse(client)
    for link in ("javascript:alert(1)", "ftp://x.example", "https://exa mple.com"):
        r = client.post(URL, headers=h, json={"employer": "X", "role_title": "Y", "link": link})
        assert r.status_code == 422, link
    a = create(client, h, employer="<b>Mercy</b>\x00", link="https://jobs.example.com/rn?id=1")
    assert a["employer"] == "<b>Mercy</b>" and a["link"] == "https://jobs.example.com/rn?id=1"


def test_archive_privacy_export_and_deletion(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    a = create(client, h)
    client.post(f"{URL}/{a['id']}/events", headers=h, json={"title": "Interview", "on_date": "2026-11-10"})
    client.post(f"{URL}/{a['id']}/archive", headers=h)
    assert client.get(URL, headers=h).json() == []
    assert [x["id"] for x in client.get(f"{URL}?archived=true", headers=h).json()] == [a["id"]]
    for method, path, body in [
        ("GET", f"{URL}/{a['id']}", None),
        ("PATCH", f"{URL}/{a['id']}", {"notes": "mine"}),
        ("POST", f"{URL}/{a['id']}/stage", {"stage": "applied"}),
        ("POST", f"{URL}/{a['id']}/events", {"title": "x"}),
        ("POST", f"{URL}/{a['id']}/unarchive", None),
        ("DELETE", f"{URL}/{a['id']}", None),
    ]:
        assert client.request(method, path, headers=other, json=body).status_code == 404, path
    exported = client.get("/api/v1/me/export", headers=h).json()["applications"]
    assert (
        exported[0]["events"][0]["title"] == "Interview" and exported[0]["stage_history"][0]["to"] == "saved"
    )
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        for model in (Application, ApplicationEvent, ApplicationStageChange):
            assert db.scalars(select(model)).all() == []


# --- Interview Workflow pack: which interview is "next" -------------------------------------------


def test_the_next_interview_is_ordered_by_time_then_date_only_then_recorded_order(client):
    from datetime import UTC, date, datetime, timedelta

    h = auth_headers(register(client, email="ord@example.com"))
    a = client.post(URL, headers=h, json={"employer": "Mercy", "role_title": "Nurse"}).json()
    day = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
    ev = lambda body: client.post(f"{URL}/{a['id']}/events", headers=h, json=body)  # noqa: E731
    ev({"title": "Date only", "on_date": day})
    ev({"title": "Afternoon", "on_date": day, "local_time": "15:00", "timezone": "Europe/London"})
    ev({"title": "Morning", "on_date": day, "local_time": "09:00", "timezone": "Europe/London"})
    ev({"title": "No date yet"})
    nxt = client.get(f"{URL}/{a['id']}", headers=h).json()["next_event"]
    # Before: same-day events were ordered by random id, so any of the three could come first.
    assert nxt["title"] == "Morning"
    # A date-only event today still counts for someone west of UTC: it's dropped only once that
    # date is over everywhere, never on the server's own date.
    b = client.post(URL, headers=h, json={"employer": "St Anne's", "role_title": "Nurse"}).json()
    yesterday_utc = (datetime.now(UTC) - timedelta(hours=30)).date()
    client.post(
        f"{URL}/{b['id']}/events",
        headers=h,
        json={"title": "Long over", "on_date": (yesterday_utc - timedelta(days=1)).isoformat()},
    )
    client.post(
        f"{URL}/{b['id']}/events", headers=h, json={"title": "Today", "on_date": date.today().isoformat()}
    )
    assert client.get(f"{URL}/{b['id']}", headers=h).json()["next_event"]["title"] == "Today"

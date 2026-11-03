"""Scheduling: real activities on dates and times the learner chooses, exact around daylight
saving, never mistaken for completed work, and exported as standards-compliant calendar files."""

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import ScheduleEntry, ScheduleSettings
from app.services.ics import IcsEvent, calendar, escape, fold
from tests.conftest import auth_headers, register

URL = "/api/v1/me/schedule"
NURSE = "registered-nurse"
Q = f"{NURSE}/m-pressure-0"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def schedule(client, h, **over):
    body = {
        "kind": "question",
        "ref": Q,
        "on_date": "2026-11-10",
        "local_time": "18:30",
        "timezone": "America/Chicago",
        "duration_min": 30,
        **over,
    }
    return client.post(URL, headers=h, json=body)


def unfold(ics: str) -> list[str]:
    assert "\n" not in ics.replace("\r\n", ""), "lines end with CRLF"
    return ics.replace("\r\n ", "").split("\r\n")


def test_settings_start_empty_and_reminders_are_opt_in(client):
    h = nurse(client)
    s = client.get(f"{URL}/settings", headers=h).json()
    assert s == {
        "timezone": None,
        "reminders": False,
        "reminder_minutes": 10,
        "quiet_start": None,
        "quiet_end": None,
    }
    assert (
        client.put(f"{URL}/settings", headers=h, json={"reminders": True}).status_code == 400
    )  # a zone first
    assert client.put(f"{URL}/settings", headers=h, json={"timezone": "EST"}).status_code == 400
    saved = client.put(
        f"{URL}/settings",
        headers=h,
        json={"timezone": "America/Chicago", "reminders": True, "quiet_start": "22:00", "quiet_end": "07:00"},
    ).json()
    assert (
        saved["timezone"] == "America/Chicago"
        and saved["reminders"] is True
        and saved["quiet_start"] == "22:00"
    )
    assert client.put(f"{URL}/settings", headers=h, json={"quiet_start": "late"}).status_code == 400
    assert client.put(f"{URL}/settings", headers=h, json={"reminders": False}).json()["reminders"] is False


def test_a_scheduled_question_is_not_done_until_it_is_answered(client):
    h = nurse(client)
    r = schedule(client, h)
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["title"] == client.get(f"/api/v1/careers/{NURSE}/questions/m-pressure-0").json()["title"]
    assert e["starts_at"].startswith("2026-11-11T00:30:00")  # 18:30 CST is 00:30 UTC the next day
    assert (
        e["on_date"] == "2026-11-10"
        and e["done_at"] is None
        and e["href"] == f"/careers/{Q.replace('/', '/questions/')}"
    )
    listed = client.get(f"{URL}?from=2026-11-09&to=2026-11-15", headers=h).json()
    assert [x["id"] for x in listed] == [e["id"]]
    client.post(
        f"/api/v1/careers/{NURSE}/questions/m-pressure-0/answers",
        headers=h,
        json={"answer": "I assessed, escalated and documented."},
    )
    assert client.get(f"{URL}/{e['id']}", headers=h).json()["done_at"] is not None


def test_all_day_entries_are_dates_and_timed_ones_need_a_time(client):
    h = nurse(client)
    day = schedule(client, h, all_day=True, local_time=None, timezone=None).json()
    assert day["all_day"] and day["starts_at"] is None and day["local_time"] is None
    r = schedule(client, h, local_time=None)
    assert r.status_code == 400 and r.json()["error"]["code"] == "time_required"


def test_daylight_saving_never_shifts_an_entry_silently(client):
    h = nurse(client)
    gap = schedule(client, h, on_date="2026-03-08", local_time="02:30")
    assert gap.status_code == 400 and gap.json()["error"]["code"] == "nonexistent_time"
    twice = schedule(client, h, on_date="2026-11-01", local_time="01:30")
    assert twice.status_code == 400 and twice.json()["error"]["code"] == "ambiguous_time"
    first = schedule(client, h, on_date="2026-11-01", local_time="01:30", fold=0).json()
    assert first["starts_at"].startswith("2026-11-01T06:30:00")
    # The day after the change: same wall-clock time, a different UTC offset, the same date.
    after = schedule(client, h, on_date="2026-11-02", local_time="09:00").json()
    assert after["starts_at"].startswith("2026-11-02T15:00:00") and after["on_date"] == "2026-11-02"


def test_moving_and_cancelling_update_the_calendar_identity(client):
    h = nurse(client)
    e = schedule(client, h).json()
    moved = client.patch(
        f"{URL}/{e['id']}",
        headers=h,
        json={"on_date": "2026-11-12", "local_time": "08:00", "timezone": "Europe/London"},
    ).json()
    assert (
        moved["uid"] == e["uid"]
        and moved["sequence"] == 1
        and moved["starts_at"].startswith("2026-11-12T08:00:00")
    )
    cancelled = client.post(f"{URL}/{e['id']}/cancel", headers=h).json()
    assert cancelled["status"] == "cancelled" and cancelled["sequence"] == 2
    assert client.post(f"{URL}/{e['id']}/cancel", headers=h).json()["sequence"] == 2  # repeated: no change
    again = client.patch(f"{URL}/{e['id']}", headers=h, json={"on_date": "2026-11-13", "all_day": True})
    assert again.status_code == 409
    assert client.get(f"{URL}?from=2026-11-01&to=2026-11-30", headers=h).json() == []
    assert (
        len(client.get(f"{URL}?from=2026-11-01&to=2026-11-30&include_cancelled=true", headers=h).json()) == 1
    )


def test_repeated_clicks_schedule_once_and_overlaps_are_explained_not_moved(client):
    h = nurse(client)
    a = schedule(client, h, client_request_id="r1")
    b = schedule(client, h, client_request_id="r1")
    assert a.status_code == 201 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    c = schedule(client, h, kind="problem", ref="two-sum", local_time="18:45", duration_min=30).json()
    d = schedule(client, h, kind="problem", ref="two-sum", local_time="20:00").json()
    listed = {x["id"]: x for x in client.get(f"{URL}?from=2026-11-10&to=2026-11-10", headers=h).json()}
    assert listed[a.json()["id"]]["conflicts"] == [c["id"]] and listed[c["id"]]["conflicts"] == [
        a.json()["id"]
    ]
    assert listed[d["id"]]["conflicts"] == []
    assert listed[c["id"]]["starts_at"] == c["starts_at"]  # nothing was moved


def test_only_your_own_activities_can_be_scheduled(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    app = client.post(
        "/api/v1/me/applications", headers=other, json={"employer": "X", "role_title": "Y"}
    ).json()
    ev = client.post(
        f"/api/v1/me/applications/{app['id']}/events", headers=other, json={"title": "Interview"}
    ).json()["events"][0]
    assert schedule(client, h, kind="application_event", ref=ev["id"]).status_code == 404
    assert (
        schedule(client, other, kind="application_event", ref=ev["id"]).json()["title"]
        == "Prepare: Interview (X)"
    )
    assert schedule(client, h, kind="plan_item", ref="nope").status_code == 404
    assert schedule(client, h, kind="question", ref=f"{NURSE}/nope").status_code == 404
    mine = schedule(client, h).json()
    for method, path, body in [
        ("GET", f"{URL}/{mine['id']}", None),
        ("PATCH", f"{URL}/{mine['id']}", {"on_date": "2026-11-11", "all_day": True}),
        ("POST", f"{URL}/{mine['id']}/cancel", None),
        ("GET", f"{URL}/export.ics?ids={mine['id']}", None),
    ]:
        assert client.request(method, path, headers=other, json=body).status_code == 404, path


def test_changing_the_schedule_time_zone_keeps_every_entry_where_it_was(client):
    h = nurse(client)
    client.put(f"{URL}/settings", headers=h, json={"timezone": "America/Chicago"})
    timed = schedule(client, h).json()
    day = schedule(client, h, all_day=True, local_time=None, timezone=None).json()
    client.put(f"{URL}/settings", headers=h, json={"timezone": "Asia/Tokyo"})  # travelling
    assert client.get(f"{URL}/{timed['id']}", headers=h).json()["starts_at"] == timed["starts_at"]
    assert client.get(f"{URL}/{day['id']}", headers=h).json()["on_date"] == "2026-11-10"


def test_the_calendar_file_is_valid_and_holds_only_what_was_chosen(client):
    h = nurse(client)
    e = schedule(client, h, notes="PRIVATE NOTE").json()
    day = schedule(
        client, h, all_day=True, local_time=None, timezone=None, kind="problem", ref="two-sum"
    ).json()
    client.patch(
        f"{URL}/{e['id']}",
        headers=h,
        json={"on_date": "2026-11-10", "local_time": "19:00", "timezone": "America/Chicago"},
    )
    r = client.get(f"{URL}/export.ics?ids={e['id']}", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    lines = unfold(r.text)
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-2] == "END:VCALENDAR" and lines[-1] == ""
    assert f"UID:{e['uid']}" in lines and "SEQUENCE:1" in lines and "STATUS:CONFIRMED" in lines
    assert "DTSTART:20261111T010000Z" in lines and "DTEND:20261111T013000Z" in lines
    assert lines.count("BEGIN:VEVENT") == 1  # only the selected entry
    assert "PRIVATE NOTE" not in r.text and "ada@example.com" not in r.text and "Bearer" not in r.text
    assert all(len(line.encode()) <= 75 for line in r.text.split("\r\n"))
    # A range includes cancellations, so a calendar that re-imports can remove them.
    client.post(f"{URL}/{day['id']}/cancel", headers=h)
    week = unfold(client.get(f"{URL}/export.ics?from=2026-11-09&to=2026-11-15", headers=h).text)
    assert (
        "DTSTART;VALUE=DATE:20261110" in week
        and "DTEND;VALUE=DATE:20261111" in week
        and "STATUS:CANCELLED" in week
    )
    assert client.get(f"{URL}/export.ics", headers=h).status_code == 400


def test_ics_escaping_and_folding():
    assert escape("a, b; c\\d\nnext") == "a\\, b\\; c\\\\d\\nnext"
    long = "SUMMARY:" + "é" * 60  # two bytes each: must fold without splitting a character
    folded = fold(long)
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == long
    text = calendar(
        [
            IcsEvent(
                uid="u@x",
                sequence=0,
                summary='Ward round, nights; "A"',
                status="CONFIRMED",
                all_day=False,
                on_date=date(2026, 1, 1),
                starts_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
                minutes=45,
            )
        ],
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert 'SUMMARY:Ward round\\, nights\\; "A"' in unfold(text) and "DTEND:20260101T094500Z" in unfold(text)


def test_export_and_deletion(client):
    h = nurse(client)
    client.put(f"{URL}/settings", headers=h, json={"timezone": "Europe/London"})
    schedule(client, h)
    exported = client.get("/api/v1/me/export", headers=h).json()["schedule"]
    assert exported["settings"]["timezone"] == "Europe/London" and len(exported["entries"]) == 1
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert (
            db.scalars(select(ScheduleEntry)).all() == [] and db.scalars(select(ScheduleSettings)).all() == []
        )

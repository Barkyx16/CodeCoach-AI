"""Interview preparation: fixed by default; kept relative to its interview only when the learner
chooses, and even then moved only after a preview and an explicit, all-or-none confirmation.
Synthetic accounts and dates only."""

from datetime import UTC, datetime

from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"
SCHED = "/api/v1/me/schedule"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def interview(client, h, on="2026-12-15", at="10:00", tz="Europe/London"):
    a = client.post(
        APPS, headers=h, json={"employer": "Synthetic Hospital", "role_title": "Ward nurse"}
    ).json()
    body = {"title": "Panel interview", "on_date": on}
    if at:
        body |= {"local_time": at, "timezone": tz}
    ev = client.post(f"{APPS}/{a['id']}/events", headers=h, json=body).json()["events"][0]
    return a, ev


def prep(client, h, ev, on="2026-12-13", at="18:00", tz="Europe/London"):
    body = {"kind": "application_event", "ref": ev["id"], "on_date": on}
    body |= {"local_time": at, "timezone": tz} if at else {"all_day": True}
    r = client.post(SCHED, headers=h, json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def move_event(client, h, a, ev, **fields):
    body = {"title": ev["title"], **fields}
    r = client.put(f"{APPS}/{a['id']}/events/{ev['id']}", headers=h, json=body)
    assert r.status_code == 200, r.text
    return next(e for e in r.json()["events"] if e["id"] == ev["id"])


def follow(client, h, entry, follows=True):
    return client.put(
        f"{SCHED}/{entry['id']}/follows-interview",
        headers=h,
        json={"follows": follows, "expected_sequence": entry["sequence"]},
    )


def preview(client, h, a, ev):
    r = client.get(f"{APPS}/{a['id']}/events/{ev['id']}/prep", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def shift(client, h, a, ev, p, ids):
    entries = [{"id": e["id"], "sequence": e["sequence"]} for e in p["entries"] if e["id"] in ids]
    return client.post(
        f"{APPS}/{a['id']}/events/{ev['id']}/prep/shift",
        headers=h,
        json={"event_starts_at": p["event_starts_at"], "entries": entries},
    )


def test_preparation_is_fixed_by_default_and_a_reschedule_moves_nothing(client):
    h = nurse(client)
    a, ev = interview(client, h)
    e = prep(client, h, ev)
    assert e["follows_interview"] is False
    move_event(client, h, a, ev, on_date="2026-12-16", local_time="14:00", timezone="Europe/London")
    p = preview(client, h, a, ev)
    assert [(x["status"], x["proposal"]) for x in p["entries"]] == [("fixed", None)]
    assert client.get(f"{SCHED}/{e['id']}", headers=h).json()["local_time"] == "18:00"  # untouched


def test_a_followed_entry_moves_only_when_chosen_keeping_the_same_time_before(client):
    h = nurse(client)
    a, ev = interview(client, h)
    bound = prep(client, h, ev)
    fixed = prep(client, h, ev, on="2026-12-14", at="09:00")
    r = follow(client, h, bound)
    assert r.status_code == 200 and r.json()["follows_interview"] is True
    bound = r.json()
    move_event(client, h, a, ev, on_date="2026-12-16", local_time="14:00", timezone="Europe/London")
    p = preview(client, h, a, ev)
    by_id = {x["id"]: x for x in p["entries"]}
    assert by_id[fixed["id"]]["status"] == "fixed"
    can = by_id[bound["id"]]
    assert can["status"] == "can_move" and "40 hours before the interview" in can["note"]
    assert (can["proposal"]["on_date"], can["proposal"]["local_time"]) == ("2026-12-14", "22:00")
    # Nothing has moved yet: a preview changes nothing.
    assert client.get(f"{SCHED}/{bound['id']}", headers=h).json()["local_time"] == "18:00"
    # Choosing nothing isn't a request.
    assert shift(client, h, a, ev, p, set()).status_code == 422

    done = shift(client, h, a, ev, p, {bound["id"]})
    assert done.status_code == 200 and done.json()["moved"] == [bound["id"]]
    moved = client.get(f"{SCHED}/{bound['id']}", headers=h).json()
    assert (moved["on_date"], moved["local_time"], moved["sequence"]) == (
        "2026-12-14",
        "22:00",
        bound["sequence"] + 1,
    )
    assert (
        client.get(f"{SCHED}/{fixed['id']}", headers=h).json()["local_time"] == "09:00"
    )  # not chosen, not moved
    assert {x["id"]: x["status"] for x in done.json()["preview"]["entries"]}[bound["id"]] == "aligned"

    # The same request again (say the first response was lost) moves nothing twice.
    again = shift(client, h, a, ev, p, {bound["id"]})
    assert (
        again.status_code == 200
        and again.json()["moved"] == []
        and again.json()["already_aligned"] == [bound["id"]]
    )
    assert client.get(f"{SCHED}/{bound['id']}", headers=h).json()["local_time"] == "22:00"


def test_a_stale_preview_moves_nothing(client):
    h = nurse(client)
    a, ev = interview(client, h)
    one = follow(client, h, prep(client, h, ev)).json()
    two = follow(client, h, prep(client, h, ev, on="2026-12-14", at="08:00")).json()
    move_event(client, h, a, ev, on_date="2026-12-16", local_time="14:00", timezone="Europe/London")
    p = preview(client, h, a, ev)
    # Another tab makes one of them fixed in the meantime: all or none, so neither moves.
    follow(client, h, client.get(f"{SCHED}/{two['id']}", headers=h).json(), follows=False)
    r = shift(client, h, a, ev, p, {one["id"], two["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "prep_not_movable"
    assert {x["id"] for x in r.json()["error"]["details"]["entries"]} == {two["id"]}
    assert client.get(f"{SCHED}/{one['id']}", headers=h).json()["local_time"] == "18:00"
    # The interview moving again after the preview: nothing moves either.
    move_event(client, h, a, ev, on_date="2026-12-17", local_time="14:00", timezone="Europe/London")
    r = shift(client, h, a, ev, p, {one["id"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "interview_changed"
    assert client.get(f"{SCHED}/{one['id']}", headers=h).json()["local_time"] == "18:00"


def test_without_exact_times_nothing_is_guessed(client):
    h = nurse(client)
    a, ev = interview(client, h)
    bound = follow(client, h, prep(client, h, ev)).json()
    # The interview's time is removed (date only): no proposal, no midnight invented.
    move_event(client, h, a, ev, on_date="2026-12-16")
    p = preview(client, h, a, ev)
    assert p["event_starts_at"] is None
    assert [(x["status"], x["proposal"]) for x in p["entries"]] == [("interview_time_unknown", None)]
    # Following can't start without exact times on both sides.
    _, dated = interview(client, h, at=None)
    e = prep(client, h, dated)
    assert follow(client, h, e).json()["error"]["code"] == "interview_time_unknown"
    _, timed = interview(client, h)
    all_day = prep(client, h, timed, at=None)
    assert follow(client, h, all_day).json()["error"]["code"] == "untimed_entry"
    other = client.post(
        SCHED,
        headers=h,
        json={
            "kind": "question",
            "ref": "registered-nurse/m-pressure-0",
            "on_date": "2026-12-01",
            "local_time": "09:00",
            "timezone": "Europe/London",
        },
    ).json()
    assert follow(client, h, other).json()["error"]["code"] == "not_interview_prep"
    assert client.get(f"{SCHED}/{bound['id']}", headers=h).json()["local_time"] == "18:00"


def test_a_time_zone_change_is_a_move_and_the_new_time_is_shown_in_the_entrys_own_zone(client):
    h = nurse(client)
    a, ev = interview(client, h)  # 10:00 London
    follow(client, h, prep(client, h, ev))  # 18:00 London, two days before
    move_event(client, h, a, ev, on_date="2026-12-15", local_time="10:00", timezone="America/New_York")  # +5h
    can = preview(client, h, a, ev)["entries"][0]
    assert can["status"] == "can_move"
    assert (can["proposal"]["local_time"], can["proposal"]["timezone"]) == ("23:00", "Europe/London")


def test_across_a_daylight_saving_change_the_elapsed_time_is_kept_and_the_clock_time_is_said(client):
    h = nurse(client)
    # London moves to summer time on 2027-03-28.
    a, ev = interview(client, h, on="2027-03-29", at="10:00")
    bound = follow(client, h, prep(client, h, ev, on="2027-03-27", at="18:00")).json()
    move_event(client, h, a, ev, on_date="2027-03-30", local_time="10:00", timezone="Europe/London")
    can = preview(client, h, a, ev)["entries"][0]
    assert can["status"] == "can_move"
    assert (can["proposal"]["on_date"], can["proposal"]["local_time"]) == ("2027-03-28", "19:00")
    assert "daylight-saving" in can["note"]
    assert shift(client, h, a, ev, preview(client, h, a, ev), {bound["id"]}).status_code == 200


def test_past_and_removed_preparation_never_moves(client):
    h = nurse(client)
    a, ev = interview(client, h)
    past = follow(client, h, prep(client, h, ev, on="2026-01-10")).json()
    assert past["follows_interview"] is True
    move_event(client, h, a, ev, on_date="2026-12-16", local_time="14:00", timezone="Europe/London")
    assert preview(client, h, a, ev)["entries"][0]["status"] == "past"
    # Removing the interview leaves its preparation entry as it was (shown as unavailable).
    client.delete(f"{APPS}/{a['id']}/events/{ev['id']}", headers=h)
    assert client.get(f"{APPS}/{a['id']}/events/{ev['id']}/prep", headers=h).status_code == 404
    kept = client.get(f"{SCHED}/{past['id']}", headers=h).json()
    assert kept["available"] is False and kept["local_time"] == "18:00" and kept["status"] == "scheduled"


def test_moving_a_followed_entry_by_hand_keeps_it_relative_to_the_current_interview(client):
    h = nurse(client)
    a, ev = interview(client, h)
    bound = follow(client, h, prep(client, h, ev)).json()
    move_event(client, h, a, ev, on_date="2026-12-16", local_time="14:00", timezone="Europe/London")
    r = client.patch(
        f"{SCHED}/{bound['id']}",
        headers=h,
        json={"on_date": "2026-12-15", "local_time": "09:00", "timezone": "Europe/London"},
    )
    assert r.json()["follows_interview"] is True
    assert preview(client, h, a, ev)["entries"][0]["status"] == "aligned"  # the time set by hand stands
    # Made all-day by hand: there's nothing to keep relative, so it becomes fixed.
    r = client.patch(f"{SCHED}/{bound['id']}", headers=h, json={"on_date": "2026-12-15", "all_day": True})
    assert r.json()["follows_interview"] is False


def test_only_the_owner_can_preview_follow_or_move(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    a, ev = interview(client, h)
    e = follow(client, h, prep(client, h, ev)).json()
    assert client.get(f"{APPS}/{a['id']}/events/{ev['id']}/prep", headers=other).status_code == 404
    assert follow(client, other, e, follows=False).status_code == 404
    p = preview(client, h, a, ev)
    r = client.post(
        f"{APPS}/{a['id']}/events/{ev['id']}/prep/shift",
        headers=other,
        json={
            "event_starts_at": p["event_starts_at"],
            "entries": [{"id": e["id"], "sequence": e["sequence"]}],
        },
    )
    assert r.status_code == 404
    assert datetime.now(UTC).year >= 2026  # the fixtures' future dates assume today is before them

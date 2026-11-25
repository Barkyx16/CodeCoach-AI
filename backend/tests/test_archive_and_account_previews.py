"""Archiving a story or an application, and deleting the account, shown first (Volume 14, prompt 6;
docs/LIFECYCLE.md): each is planned by the same code that carries it out, bound to the preview the
learner read, refused with the new plan when the scope changed, and retried safely. The account's
counts are the privacy page's own, and equal what is then removed. Synthetic data only; no email is
sent."""

from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.models import EmailJob, ExperienceEntry, Note, RefreshToken, ScheduleEntry, User
from app.services.data_summary import CATEGORIES
from app.services.lifecycle import backups_age_out_by
from tests.test_lifecycle import add_event, application, nurse
from tests.test_lifecycle_more import APPS, STORIES, carry_out, get_preview, story_in_use

SCHEDULE = "/api/v1/me/schedule"
DELETE_ME = "/api/v1/auth/me"
PASSWORD = "CorrectHorse42"


def kinds(impact):
    return [(e["effect"], e["kind"]) for e in impact["effects"]]


def test_archiving_a_story_lists_what_keeps_it_and_unarchive_brings_it_back(client):
    h = nurse(client)
    s = story_in_use(client, h)
    p = get_preview(client, h, f"{STORIES}/{s['story']}/archive-preview")
    assert kinds(p)[0] == ("archived", "story")
    assert {k for _, k in kinds(p)[1:]} == {
        "requirement link",
        "interview-day kit",
        "application",
        "reflection",
        "practice answer",
    }
    assert all(e["effect"] == "kept" for e in p["effects"][1:])
    r = carry_out(client, h, f"{STORIES}/{s['story']}/archive-as-previewed", p["fingerprint"])
    assert r.status_code == 200, r.text
    assert client.get(f"{STORIES}/{s['story']}", headers=h).json()["archived"] is True
    kit = client.get(f"{APPS}/{s['app']['id']}/events/{s['event']['id']}/kit", headers=h).json()
    assert [st["archived"] for st in kit["stories"]] == [True]  # the kit keeps what it prepared
    # The requirement link stays, and the target labels the story archived.
    t = client.get(f"/api/v1/targets/{s['target']['id']}", headers=h).json()
    [ex] = [e for e in t["experience"] if e["id"] == s["story"]]
    assert ex["archived"] is True and ex["requirement_ids"] == [s["rid"]]
    assert client.post(f"{STORIES}/{s['story']}/unarchive", headers=h).json()["archived"] is False
    t = client.get(f"/api/v1/targets/{s['target']['id']}", headers=h).json()
    assert next(e for e in t["experience"] if e["id"] == s["story"])["archived"] is False
    # Nothing was unlinked: the same list, the story active again.
    again = get_preview(client, h, f"{STORIES}/{s['story']}/archive-preview")
    assert kinds(again) == kinds(p)


def test_a_story_scope_changed_after_the_preview_is_refused(client):
    h = nurse(client)
    s = story_in_use(client, h)
    p = get_preview(client, h, f"{STORIES}/{s['story']}/archive-preview")
    other = application(client, h, employer="St Elsewhere")
    assert client.put(f"{APPS}/{other['id']}/stories/{s['story']}", headers=h).status_code == 200
    r = carry_out(client, h, f"{STORIES}/{s['story']}/archive-as-previewed", p["fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    assert client.get(f"{STORIES}/{s['story']}", headers=h).json()["archived"] is False


def test_a_retried_story_archive_answers_with_what_was_done(client):
    h = nurse(client)
    s = story_in_use(client, h)
    p = get_preview(client, h, f"{STORIES}/{s['story']}/archive-preview")
    url = f"{STORIES}/{s['story']}/archive-as-previewed"
    first = carry_out(client, h, url, p["fingerprint"], key="archive-story-0001")
    again = carry_out(client, h, url, p["fingerprint"], key="archive-story-0001")
    assert first.status_code == again.status_code == 200 and again.json()["replayed"] is True


def test_archiving_an_application_takes_its_interviews_off_the_schedule_until_unarchived(client):
    h = nurse(client)
    a = application(client, h)
    ev = add_event(client, h, a["id"], "Panel interview", on_date="2026-11-20")
    entry = client.post(
        SCHEDULE,
        headers=h,
        json={"kind": "application_event", "ref": ev["id"], "on_date": "2026-11-19", "all_day": True},
    )
    assert entry.status_code == 201, entry.text
    window = {"from": "2026-11-15", "to": "2026-11-30"}
    assert len(client.get(SCHEDULE, headers=h, params=window).json()) == 1
    p = get_preview(client, h, f"{APPS}/{a['id']}/archive-preview")
    assert kinds(p) == [("archived", "application"), ("kept", "interview event"), ("kept", "schedule entry")]
    assert "Off your schedule and Today while it's archived" in p["effects"][-1]["note"]
    assert carry_out(client, h, f"{APPS}/{a['id']}/archive-as-previewed", p["fingerprint"]).status_code == 200
    assert client.get(SCHEDULE, headers=h, params=window).json() == []
    assert client.get(f"{APPS}/{a['id']}", headers=h).json()["archived"] is True
    client.post(f"{APPS}/{a['id']}/unarchive", headers=h)
    assert len(client.get(SCHEDULE, headers=h, params=window).json()) == 1


def test_an_application_scope_changed_after_the_preview_is_refused_with_the_new_one(client):
    h = nurse(client)
    a = application(client, h)
    p = get_preview(client, h, f"{APPS}/{a['id']}/archive-preview")
    add_event(client, h, a["id"], "Phone screen", on_date="2026-11-25")
    r = carry_out(client, h, f"{APPS}/{a['id']}/archive-as-previewed", p["fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    current = r.json()["error"]["details"]["current"]
    assert ("kept", "interview event") in kinds(current)
    assert client.get(f"{APPS}/{a['id']}", headers=h).json()["archived"] is False
    # A retry of the new plan, twice with one key: done once, then answered with what was done.
    first = carry_out(
        client, h, f"{APPS}/{a['id']}/archive-as-previewed", current["fingerprint"], key="archive-app-0001"
    )
    again = carry_out(
        client, h, f"{APPS}/{a['id']}/archive-as-previewed", current["fingerprint"], key="archive-app-0001"
    )
    assert first.status_code == again.status_code == 200 and again.json()["replayed"] is True


def test_the_older_archive_routes_carry_out_the_same_plan(client):
    h = nurse(client)
    s = story_in_use(client, h)
    assert client.post(f"{STORIES}/{s['story']}/archive", headers=h).json()["archived"] is True
    assert client.post(f"{APPS}/{s['app']['id']}/archive", headers=h).json()["archived"] is True


def test_another_accounts_story_and_application_are_not_found(client):
    owner = nurse(client, "owner@example.com")
    s = story_in_use(client, owner)
    other = nurse(client, "other@example.com")
    for url in (f"{STORIES}/{s['story']}/archive-preview", f"{APPS}/{s['app']['id']}/archive-preview"):
        assert client.get(url, headers=other).status_code == 404
    for url in (
        f"{STORIES}/{s['story']}/archive-as-previewed",
        f"{APPS}/{s['app']['id']}/archive-as-previewed",
    ):
        assert carry_out(client, other, url, "0" * 32).status_code == 404


def _counts(client, email):
    """The rows of each privacy-page category this account has now, read directly."""
    from app.services.data_summary import _count

    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            return None
        return {c.key: sum(_count(db, user.id, t) for t in c.tables) for c in CATEGORIES}


def test_the_account_preview_counts_equal_what_goes_and_a_change_since_is_refused(client):
    h = nurse(client)
    s = story_in_use(client, h)
    client.post("/api/v1/me/notes", headers=h, json={"title": "Shift notes", "body": "SBAR first."})
    p = get_preview(client, h, f"{DELETE_ME}/delete-preview")
    listed = {e["id"]: e["title"] for e in p["effects"] if e["kind"] == "records"}
    actual = _counts(client, "ada@example.com")
    assert {k: v for k, v in actual.items() if v} == {
        k: int(t.rsplit(": ", 1)[1]) for k, t in listed.items()
    }  # every category with something in it, with its count
    assert any(e["kind"] == "signed-in device" for e in p["effects"])
    assert any("age out" in n for n in p["notes"])
    # Something added since: refused with the new list, nothing deleted.
    client.post("/api/v1/me/notes", headers=h, json={"title": "Another", "body": "One more."})
    stale = client.request(
        "DELETE",
        DELETE_ME,
        headers=h,
        json={"password": PASSWORD, "confirm": "DELETE", "expected_fingerprint": p["fingerprint"]},
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "impact_changed"
    assert _counts(client, "ada@example.com") is not None
    # The typed confirmation stays.
    fresh = get_preview(client, h, f"{DELETE_ME}/delete-preview")
    no_word = client.request(
        "DELETE",
        DELETE_ME,
        headers=h,
        json={"password": PASSWORD, "confirm": "yes", "expected_fingerprint": fresh["fingerprint"]},
    )
    assert no_word.status_code == 400
    done = client.request(
        "DELETE",
        DELETE_ME,
        headers=h,
        json={"password": PASSWORD, "confirm": "DELETE", "expected_fingerprint": fresh["fingerprint"]},
    )
    assert done.status_code == 204, done.text
    assert _counts(client, "ada@example.com") is None
    with client.app.state.session_factory() as db:
        for model in (Note, ExperienceEntry, ScheduleEntry, RefreshToken, EmailJob):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__
    assert s  # the story, its kit and links went with it


def test_pending_emails_are_listed_as_cancelled(client):
    h = nurse(client)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        db.add(EmailJob(kind="verify_email", user_id=user.id, status="pending", payload={}))
        db.commit()
    p = get_preview(client, h, f"{DELETE_ME}/delete-preview")
    [e] = [e for e in p["effects"] if e["kind"] == "email not sent yet"]
    assert e["note"] == "Cancelled: never sent." and e["title"].endswith("waiting to be sent")


def test_backups_age_out_by_the_first_day_of_the_third_month_after():
    assert backups_age_out_by(datetime(2026, 11, 15, tzinfo=UTC)) == date(2027, 2, 1)
    assert backups_age_out_by(datetime(2026, 3, 31, tzinfo=UTC)) == date(2026, 6, 1)
    assert backups_age_out_by(datetime(2026, 12, 1, tzinfo=UTC)) == date(2027, 3, 1)


def test_the_age_out_date_matches_the_rotation_itself(monkeypatch):
    """The worst case, by the rotation code: deleted on the last evening of a month, after that
    night's backup, then nightly backups. The last backup holding it goes exactly then, not before."""
    from datetime import timedelta
    from pathlib import Path

    from app.db import backup_store

    monkeypatch.setattr(backup_store, "problem_with", lambda s, now: None)  # every file usable
    deleted = datetime(2026, 11, 30, 23, 0, tzinfo=UTC)
    nights = [datetime(2026, 10, 1, 2, 0, tzinfo=UTC) + timedelta(days=d) for d in range(200)]
    stored = [backup_store.Stored(stamp=t, dump=Path(f"{t:%Y%m%d}.dump"), manifest=Path("m")) for t in nights]
    holding = {s.stamp for s in stored if s.stamp < deleted}

    def kept_on(day: datetime) -> set:
        plan = backup_store.retention([s for s in stored if s.stamp <= day], now=day)
        return {s.stamp for s in plan.keep} & holding

    until = datetime.combine(backups_age_out_by(deleted), datetime.min.time(), UTC)
    assert kept_on(until - timedelta(days=1))  # still there the day before
    assert not kept_on(until + timedelta(hours=3))  # gone once that night's backup is made and pruned


def test_after_deleting_as_previewed_sign_in_fails_the_link_is_gone_and_no_email_is_left(client):
    """What the list said happens: the shared link stops working, the waiting email is never sent
    (its row goes with the account, so the worker can't pick it up), and signing in fails."""
    from tests.test_shares import answer_question, open_link, share

    h = nurse(client)
    link = share(client, h, answer_question(client, h)["id"], sentences=[0])
    gone = share(client, h, answer_question(client, h, qid="m-pressure-1")["id"], sentences=[0])
    # Closed (no more feedback) still opens, so it's counted; revoked already doesn't, so it isn't.
    for s in (link, gone):
        assert client.post(f"/api/v1/me/shares/{s['share']['id']}/close", headers=h).status_code == 200
    assert client.post(f"/api/v1/me/shares/{gone['share']['id']}/revoke", headers=h).status_code == 200
    assert open_link(client, link["token"]).status_code == 200
    assert open_link(client, gone["token"]).status_code == 410  # revoked: gone already
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "ada@example.com"))
        db.add(EmailJob(kind="verify_email", user_id=user.id, status="pending", payload={}))
        db.commit()
    p = get_preview(client, h, f"{DELETE_ME}/delete-preview")
    said = {e["kind"]: e for e in p["effects"]}
    assert said["shared link"]["title"] == "1 link you shared"
    assert said["shared link"]["note"] == "They stop working at once."
    assert said["email not sent yet"]["title"] == "1 email waiting to be sent"
    assert said["signed-in device"]["note"] == "Every device is signed out."
    done = client.request(
        "DELETE",
        DELETE_ME,
        headers=h,
        json={"password": PASSWORD, "confirm": "DELETE", "expected_fingerprint": p["fingerprint"]},
    )
    assert done.status_code == 204, done.text
    assert open_link(client, link["token"]).status_code == 404
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(EmailJob)) == 0
    login = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert login.status_code == 401
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401  # the old token is refused too


def test_an_application_archive_preview_lists_its_offer_comparisons(client):
    from tests.test_offer_comparisons import doc, new, offer, put

    h = nurse(client)
    a = application(client, h)
    c = new(client, h)
    linked = put(client, h, c, doc(offer("a", application_id=a["id"]), title="Spring offers"))
    assert linked.status_code == 200, linked.text
    p = get_preview(client, h, f"{APPS}/{a['id']}/archive-preview")
    [kept] = [e for e in p["effects"] if e["kind"] == "offer comparison"]
    assert (kept["effect"], kept["title"], kept["note"]) == ("kept", "Spring offers", "Still compares it.")
    assert carry_out(client, h, f"{APPS}/{a['id']}/archive-as-previewed", p["fingerprint"]).status_code == 200
    # It still compares it, as the list said.
    again = client.get(f"/api/v1/me/offer-comparisons/{c['id']}", headers=h).json()
    assert again["applications"] == {a["id"]: f"{a['role_title']} at {a['employer']}"}

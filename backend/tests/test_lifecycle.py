"""Archive and delete, previewed by the plan that carries them out (Volume 12, prompt 9;
docs/LIFECYCLE.md): the preview lists every one of the learner's records an application delete or a
note archive touches, by title, kind and effect; carrying it out works the plan out again, refuses a
changed scope with the new plan, and does exactly what it listed in one transaction; a retried
request reports what was done; later and retried requests can't recreate what was deleted; another
account's ids are "not found". Synthetic data only."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    AcceptedAction,
    Application,
    ApplicationEvent,
    ExperienceEntry,
    InterviewKit,
    InterviewReflection,
    LifecycleReceipt,
    Note,
    OfferComparison,
    ReflectionAction,
    ScheduleEntry,
)
from app.services import lifecycle
from tests.conftest import auth_headers, register
from tests.test_actions import accept, improvement
from tests.test_offer_comparisons import MINE, doc, new, offer, put
from tests.test_reflections import REFLECTION
from tests.test_schedule import schedule

APPS = "/api/v1/me/applications"
NOTES = "/api/v1/me/notes"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def application(client, h, **over):
    r = client.post(
        APPS,
        headers=h,
        json={"employer": "Mercy General", "role_title": "Ward nurse", "stage": "interviewing", **over},
    )
    assert r.status_code == 201, r.text
    return r.json()


def add_event(client, h, app_id, title, on_date="2026-11-12"):
    r = client.post(f"{APPS}/{app_id}/events", headers=h, json={"title": title, "on_date": on_date})
    assert r.status_code == 200, r.text
    return next(e for e in r.json()["events"] if e["title"] == title)


def preview(client, h, app_id):
    r = client.get(f"{APPS}/{app_id}/delete-preview", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def delete(client, h, app_id, fingerprint, key=None):
    return client.post(
        f"{APPS}/{app_id}/delete",
        headers=h,
        json={"expected_fingerprint": fingerprint, "client_request_id": key},
    )


def effects(impact):
    return sorted((e["effect"], e["kind"], e["title"]) for e in impact["effects"])


KINDS = {
    "application": Application,
    "interview event": ApplicationEvent,
    "interview-day kit": InterviewKit,
    "reflection": InterviewReflection,
    "note": Note,
    "schedule entry": ScheduleEntry,
    "story": ExperienceEntry,
    "accepted improvement": AcceptedAction,
    "offer comparison": OfferComparison,
}


def check_done(client, out):
    """Each listed item, looked up by its id: what was listed as deleted is gone; everything else
    is still there."""
    with client.app.state.session_factory() as db:
        for e in out["effects"]:
            row = db.get(KINDS[e["kind"]], e["id"])
            assert (row is None) == (e["effect"] == "deleted"), e


def full_application(client, h):
    """An application with what deleting it reaches: two events, a kit (a chosen story and an
    accepted improvement on its checklist), a reflection whose next steps made a note and a schedule
    entry, the second event's preparation on the schedule, a linked story and an offer comparison."""
    story = client.post(
        "/api/v1/me/stories", headers=h, json={"title": "Two call lights", "situation": "A night shift."}
    ).json()
    a = application(client, h, story_ids=[story["id"]])
    panel = add_event(client, h, a["id"], "Panel interview")
    final = add_event(client, h, a["id"], "Final interview", on_date="2030-01-15")
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"]).json()
    kit = client.put(
        f"{APPS}/{a['id']}/events/{panel['id']}/kit",
        headers=h,
        json={
            "story_ids": [story["id"]],
            "checklist": [{"id": "act-1", "origin": "action", "action_id": action["id"], "text": ""}],
        },
    )
    assert kit.status_code == 200, kit.text
    url = f"{APPS}/{a['id']}/events/{panel['id']}/reflection"
    assert client.put(url, headers=h, json=REFLECTION).status_code == 200
    steps = client.post(f"{url}/suggestions", headers=h).json()["actions"]
    note_step = next(s for s in steps if s["kind"] == "note")
    practice_step = next(s for s in steps if s["kind"] == "practice")
    client.patch(f"{url}/actions/{note_step['id']}", headers=h, json={"title": "References for Mercy"})
    assert (
        client.post(
            f"{url}/actions/{note_step['id']}/accept", headers=h, json={"target": "notebook"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{url}/actions/{practice_step['id']}/accept",
            headers=h,
            json={"target": "schedule", "on_date": "2030-01-08"},
        ).status_code
        == 200
    )
    prep = schedule(client, h, kind="application_event", ref=final["id"], on_date="2030-01-14")
    assert prep.status_code == 201, prep.text
    c = new(client, h, title="Two offers")
    linked = put(client, h, c, doc(offer("a", application_id=a["id"]), offer("b"), title="Two offers"))
    assert linked.status_code == 200, linked.text
    with client.app.state.session_factory() as db:
        made = db.scalar(select(ScheduleEntry).where(ScheduleEntry.kind == "question"))
        practice_entry = made.title
    return {
        "app": a,
        "panel": panel,
        "final": final,
        "story": story,
        "action": action,
        "comparison": linked.json(),
        "practice_entry": practice_entry,
        "prep": prep.json(),
    }


def test_the_preview_names_every_effect_and_the_delete_does_exactly_that(client):
    h = nurse(client)
    s = full_application(client, h)
    app_id = s["app"]["id"]
    before = client.get("/api/v1/me/export", headers=h).json()

    p = preview(client, h, app_id)
    assert p["summary"] == "Delete this application, its 2 events, 1 kit and 1 reflection"
    assert p["title"] == "Ward nurse at Mercy General"
    assert effects(p) == sorted(
        [
            ("deleted", "application", "Ward nurse at Mercy General"),
            ("deleted", "interview event", "Final interview (15 January 2030)"),
            ("deleted", "interview event", "Panel interview (12 November 2026)"),
            ("deleted", "interview-day kit", "Kit for Panel interview"),
            ("deleted", "reflection", "Reflection on Panel interview"),
            ("kept", "note", "References for Mercy"),
            ("kept", "schedule entry", s["practice_entry"]),
            ("unlinked", "story", "Two call lights"),
            ("unlinked", "accepted improvement", s["action"]["title"]),
            ("unavailable", "schedule entry", s["prep"]["title"]),
            ("unlinked", "offer comparison", "Two offers"),
        ]
    )
    assert any("can't be undone" in n for n in p["notes"]) and any("Backups" in n for n in p["notes"])
    # Previewing changes nothing.
    assert client.get("/api/v1/me/export", headers=h).json()["applications"] == before["applications"]
    assert preview(client, h, app_id)["fingerprint"] == p["fingerprint"]

    r = delete(client, h, app_id, p["fingerprint"], key="del-1")
    assert r.status_code == 200, r.text
    out = r.json()
    # Item for item, what was done is what was shown.
    assert out["effects"] == p["effects"] and out["summary"] == p["summary"] and out["replayed"] is False
    assert out["message"] == "Deleted Ward nurse at Mercy General."
    check_done(client, out)

    with client.app.state.session_factory() as db:
        assert db.get(Application, app_id) is None
        assert db.scalars(select(ApplicationEvent)).all() == []
        assert db.scalars(select(InterviewKit)).all() == []
        assert db.scalars(select(InterviewReflection)).all() == []
        assert db.scalars(select(ReflectionAction)).all() == []
        assert [n.title for n in db.scalars(select(Note))] == ["References for Mercy"]
        entries = {e.kind: e for e in db.scalars(select(ScheduleEntry))}
        assert set(entries) == {"question", "application_event"}
    # The preparation entry stays, marked no longer available, as listed.
    listed = client.get("/api/v1/me/schedule", headers=h, params={"from": "2030-01-01", "to": "2030-01-31"})
    prep = next(e for e in listed.json() if e["kind"] == "application_event")
    assert prep["available"] is False and prep["title"] == s["prep"]["title"]
    # The story and the accepted improvement stay; the comparison keeps its figures and opens.
    assert client.get(f"/api/v1/me/stories/{s['story']['id']}", headers=h).status_code == 200
    assert client.get(f"/api/v1/me/actions/{s['action']['id']}", headers=h).status_code == 200
    comp = client.get(f"{MINE}/{s['comparison']['id']}", headers=h)
    assert comp.status_code == 200, comp.text
    offers = comp.json()["doc"]["offers"]
    assert [o["application_id"] for o in offers] == [None, None] and offers[0]["label"] == "Offer A"
    assert comp.json()["revision"] == s["comparison"]["revision"] + 1

    # The export afterwards: none of what was deleted, all of what was kept.
    after = client.get("/api/v1/me/export", headers=h).json()
    assert (
        after["applications"] == [] and after["interview_kits"] == [] and after["interview_reflections"] == []
    )
    assert [n["title"] for n in after["notes"]] == ["References for Mercy"]
    assert [st["title"] for st in after["stories"]] == ["Two call lights"]
    assert {e["kind"] for e in after["schedule"]["entries"]} == {"question", "application_event"}
    assert [a["title"] for a in after["accepted_actions"]] == [s["action"]["title"]]
    assert [c["title"] for c in after["offer_comparisons"]] == ["Two offers"]
    assert "Mercy General" not in str(after["offer_comparisons"])


def test_an_application_with_nothing_else_says_so(client):
    h = nurse(client)
    a = application(client, h)
    p = preview(client, h, a["id"])
    assert p["summary"] == "Delete this application"
    assert effects(p) == [("deleted", "application", "Ward nurse at Mercy General")]
    client.post(f"{APPS}/{a['id']}/stage", headers=h, json={"stage": "offer"})
    assert (
        preview(client, h, a["id"])["effects"][0]["note"] == "With its notes and stage history (2 changes)."
    )


def test_a_scope_changed_after_the_preview_is_refused_with_the_new_preview(client):
    h = nurse(client)
    a = application(client, h)
    add_event(client, h, a["id"], "Phone screen")
    seen = preview(client, h, a["id"])
    add_event(client, h, a["id"], "Panel interview")  # another tab, after the preview
    r = delete(client, h, a["id"], seen["fingerprint"], key="del-1")
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    current = r.json()["error"]["details"]["current"]
    assert current["summary"] == "Delete this application, its 2 events"
    assert ("deleted", "interview event", "Panel interview (12 November 2026)") in effects(current)
    assert client.get(f"{APPS}/{a['id']}", headers=h).status_code == 200  # nothing was done
    # A relationship that goes (not only one that arrives) changes the scope too.
    story = client.post("/api/v1/me/stories", headers=h, json={"title": "Night handover"}).json()
    client.put(f"{APPS}/{a['id']}/stories/{story['id']}", headers=h)
    seen = preview(client, h, a["id"])
    client.delete(f"{APPS}/{a['id']}/stories/{story['id']}", headers=h)
    assert delete(client, h, a["id"], seen["fingerprint"]).status_code == 409
    # With the new preview it goes ahead; the refused key wasn't spent.
    fresh = preview(client, h, a["id"])
    assert delete(client, h, a["id"], fresh["fingerprint"], key="del-1").status_code == 200


def test_a_renamed_item_changes_the_preview(client):
    """Titles are part of what's shown, so they're part of what's agreed to."""
    h = nurse(client)
    a = application(client, h)
    seen = preview(client, h, a["id"])
    client.patch(f"{APPS}/{a['id']}", headers=h, json={"role_title": "Charge nurse"})
    assert delete(client, h, a["id"], seen["fingerprint"]).status_code == 409


def test_a_replayed_delete_reports_the_earlier_outcome_and_keeps_no_titles(client):
    h = nurse(client)
    a = application(client, h, client_request_id="create-1")
    add_event(client, h, a["id"], "Panel interview")
    p = preview(client, h, a["id"])
    first = delete(client, h, a["id"], p["fingerprint"], key="del-1").json()
    again = delete(client, h, a["id"], p["fingerprint"], key="del-1")
    assert again.status_code == 200, again.text
    replay = again.json()
    assert (
        replay["replayed"] is True and replay["message"] == "This was already done; nothing was done again."
    )
    assert replay["summary"] == first["summary"] and replay["done_at"] == first["done_at"]
    assert [(e["effect"], e["kind"], e["id"]) for e in replay["effects"]] == [
        (e["effect"], e["kind"], e["id"]) for e in first["effects"]
    ]
    # The receipt keeps what was done by kind and id, not the words of what was deleted.
    with client.app.state.session_factory() as db:
        receipts = db.scalars(select(LifecycleReceipt)).all()
        assert sorted(r.action for r in receipts) == ["delete_application", lifecycle.TOMBSTONE]
        assert "Mercy" not in str([r.impact for r in receipts]) and "Panel" not in str(
            [r.impact for r in receipts]
        )
    # The same key for something else is refused, not replayed.
    other = application(client, h, employer="Elm Clinic")
    r = delete(client, h, other["id"], preview(client, h, other["id"])["fingerprint"], key="del-1")
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"


def test_later_and_retried_requests_cant_recreate_what_was_deleted(client):
    """A create retried after a lost reply, and requests from another tab that still shows the
    application, finish without bringing anything back."""
    h = nurse(client)
    a = application(client, h, client_request_id="create-1")
    ev = add_event(client, h, a["id"], "Panel interview")
    url = f"{APPS}/{a['id']}/events/{ev['id']}"
    client.put(f"{url}/reflection", headers=h, json=REFLECTION)
    step = client.post(f"{url}/reflection/suggestions", headers=h).json()["actions"][0]
    assert delete(client, h, a["id"], preview(client, h, a["id"])["fingerprint"]).status_code == 200

    retry = client.post(
        APPS,
        headers=h,
        json={
            "employer": "Mercy General",
            "role_title": "Ward nurse",
            "stage": "interviewing",
            "client_request_id": "create-1",
        },
    )
    assert retry.status_code == 410 and retry.json()["error"]["code"] == "deleted_earlier"
    assert client.post(f"{APPS}/{a['id']}/events", headers=h, json={"title": "Again"}).status_code == 404
    assert client.put(f"{url}/kit", headers=h, json={"notes": "late"}).status_code == 404
    assert client.put(f"{url}/reflection", headers=h, json=REFLECTION).status_code == 404
    accepted = client.post(
        f"{url}/reflection/actions/{step['id']}/accept", headers=h, json={"target": "notebook"}
    )
    assert accepted.status_code == 404
    assert schedule(client, h, kind="application_event", ref=ev["id"]).status_code == 404
    with client.app.state.session_factory() as db:
        assert db.scalars(select(Application)).all() == []
        assert db.scalars(select(Note)).all() == []
    # A create with a new key is a new application, as always.
    fresh = client.post(
        APPS,
        headers=h,
        json={"employer": "Mercy General", "role_title": "Ward nurse", "client_request_id": "create-2"},
    )
    assert fresh.status_code == 201


def same(r1, r2):
    """The same answer, apart from the request id."""
    e1, e2 = dict(r1.json()["error"]), dict(r2.json()["error"])
    e1.pop("request_id"), e2.pop("request_id")
    return e1 == e2


def test_another_accounts_ids_are_not_found_like_missing_ones(client):
    h = nurse(client)
    other = nurse(client, "bea@example.com")
    a = application(client, h)
    n = client.post(NOTES, headers=h, json={"title": "Mine", "body": "x"}).json()
    missing_app = client.get(f"{APPS}/00000000-0000-0000-0000-000000000000/delete-preview", headers=other)
    theirs_app = client.get(f"{APPS}/{a['id']}/delete-preview", headers=other)
    assert theirs_app.status_code == missing_app.status_code == 404 and same(theirs_app, missing_app)
    fp = preview(client, h, a["id"])["fingerprint"]
    assert delete(client, other, a["id"], fp).status_code == 404
    assert client.delete(f"{APPS}/{a['id']}", headers=other).status_code == 404
    missing_note = client.get(f"{NOTES}/00000000-0000-0000-0000-000000000000/archive-preview", headers=other)
    theirs_note = client.get(f"{NOTES}/{n['id']}/archive-preview", headers=other)
    assert theirs_note.status_code == missing_note.status_code == 404 and same(theirs_note, missing_note)
    note_fp = client.get(f"{NOTES}/{n['id']}/archive-preview", headers=h).json()["fingerprint"]
    r = client.post(f"{NOTES}/{n['id']}/archive", headers=other, json={"expected_fingerprint": note_fp})
    assert r.status_code == 404
    assert client.get(f"{APPS}/{a['id']}", headers=h).status_code == 200
    assert client.get(f"{NOTES}/{n['id']}", headers=h).json()["archived"] is False


def test_another_accounts_records_are_never_counted(client):
    """Even a row of theirs that names this application's event (written straight to the database)
    isn't listed, counted or touched."""
    h = nurse(client)
    other = nurse(client, "bea@example.com")
    a = application(client, h)
    ev = add_event(client, h, a["id"], "Panel interview")
    theirs = schedule(client, other, kind="question").json()
    with client.app.state.session_factory() as db:
        row = db.get(ScheduleEntry, theirs["id"])
        row.kind, row.ref = "application_event", ev["id"]
        db.commit()
    p = preview(client, h, a["id"])
    assert [e for e in p["effects"] if e["kind"] == "schedule entry"] == []
    assert delete(client, h, a["id"], p["fingerprint"]).status_code == 200
    with client.app.state.session_factory() as db:
        assert db.get(ScheduleEntry, theirs["id"]) is not None


def test_a_failure_part_way_leaves_nothing_half_done(client, monkeypatch):
    h = nurse(client)
    s = full_application(client, h)
    app_id = s["app"]["id"]
    p = preview(client, h, app_id)

    def boom(*args, **kwargs):  # after the comparison is unlinked, before the application goes
        raise RuntimeError("disk full")

    monkeypatch.setattr(lifecycle, "forget", boom)
    with pytest.raises(RuntimeError):
        delete(client, h, app_id, p["fingerprint"], key="del-1")
    monkeypatch.undo()
    assert client.get(f"{APPS}/{app_id}", headers=h).status_code == 200
    comp = client.get(f"{MINE}/{s['comparison']['id']}", headers=h).json()
    assert (
        comp["doc"]["offers"][0]["application_id"] == app_id
        and comp["revision"] == s["comparison"]["revision"]
    )
    with client.app.state.session_factory() as db:
        assert db.scalars(select(LifecycleReceipt)).all() == []
    # Nothing was spent: the same request now goes through.
    assert delete(client, h, app_id, p["fingerprint"], key="del-1").json()["replayed"] is False


def test_the_older_delete_carries_out_the_same_plan(client):
    h = nurse(client)
    a = application(client, h, client_request_id="create-1")
    c = new(client, h, title="Two offers")
    put(client, h, c, doc(offer("a", application_id=a["id"])))
    assert client.delete(f"{APPS}/{a['id']}", headers=h).status_code == 204
    assert client.get(f"{MINE}/{c['id']}", headers=h).json()["doc"]["offers"][0]["application_id"] is None
    retry = client.post(
        APPS,
        headers=h,
        json={"employer": "Mercy General", "role_title": "Ward nurse", "client_request_id": "create-1"},
    )
    assert retry.status_code == 410


def test_receipts_and_tombstones_go_after_a_week(client):
    h = nurse(client)
    a = application(client, h, client_request_id="create-1")
    assert (
        delete(client, h, a["id"], preview(client, h, a["id"])["fingerprint"], key="del-1").status_code == 200
    )
    with client.app.state.session_factory() as db:
        assert lifecycle.purge(db) == 0
        assert (
            lifecycle.purge(db, now=datetime.now(UTC) + timedelta(days=lifecycle.RECEIPT_DAYS, minutes=1))
            == 2
        )
        db.commit()


# --- archiving a note -------------------------------------------------------------------------------


def note_preview(client, h, note_id):
    r = client.get(f"{NOTES}/{note_id}/archive-preview", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def archive(client, h, note_id, fingerprint, key=None):
    return client.post(
        f"{NOTES}/{note_id}/archive",
        headers=h,
        json={"expected_fingerprint": fingerprint, "client_request_id": key},
    )


def test_archiving_a_pinned_note_previews_hiding_and_unpinning_and_erases_nothing(client):
    h = nurse(client)
    n = client.post(NOTES, headers=h, json={"title": "Handover phrases", "body": "SBAR first."}).json()
    client.patch(f"{NOTES}/{n['id']}", headers=h, json={"pinned": True})
    p = note_preview(client, h, n["id"])
    assert p["summary"] == "Archive this note"
    assert effects(p) == [
        ("archived", "note", "Handover phrases"),
        ("unlinked", "pin", "Pinned to the top of your notes"),
    ]
    assert "Unarchive it any time; nothing is erased." in p["effects"][0]["note"]
    assert p["notes"] == [
        "Archiving isn't deleting: the note stays in your data export and can still go in a practice packet."
    ]
    out = archive(client, h, n["id"], p["fingerprint"], key="arch-1").json()
    assert out["effects"] == p["effects"] and out["message"] == "Archived Handover phrases."
    got = client.get(f"{NOTES}/{n['id']}", headers=h).json()
    assert got["archived"] is True and got["pinned"] is False and got["body"] == "SBAR first."
    assert [x["id"] for x in client.get(NOTES, headers=h).json()["items"]] == []
    assert [x["title"] for x in client.get("/api/v1/me/export", headers=h).json()["notes"]] == [
        "Handover phrases"
    ]
    # A retry reports it; archiving again is "already archived", and does nothing.
    assert archive(client, h, n["id"], p["fingerprint"], key="arch-1").json()["replayed"] is True
    again = note_preview(client, h, n["id"])
    assert again["summary"] == "This note is already archived" and again["effects"] == []
    assert archive(client, h, n["id"], p["fingerprint"]).status_code == 409  # the scope changed
    # Unarchiving brings it back, unpinned, as the preview said.
    client.patch(f"{NOTES}/{n['id']}", headers=h, json={"archived": False})
    assert client.get(f"{NOTES}/{n['id']}", headers=h).json()["pinned"] is False


def test_a_note_made_by_a_reflection_step_says_the_step_stays_done(client):
    h = nurse(client)
    a = application(client, h)
    ev = add_event(client, h, a["id"], "Panel interview")
    url = f"{APPS}/{a['id']}/events/{ev['id']}/reflection"
    client.put(url, headers=h, json=REFLECTION)
    step = next(
        s for s in client.post(f"{url}/suggestions", headers=h).json()["actions"] if s["kind"] == "note"
    )
    made = client.post(f"{url}/actions/{step['id']}/accept", headers=h, json={"target": "notebook"}).json()
    note_id = next(s for s in made["actions"] if s["id"] == step["id"])["applied_ref"]
    p = note_preview(client, h, note_id)
    assert ("kept", "reflection next step", step["title"]) in effects(p)
    assert archive(client, h, note_id, p["fingerprint"]).status_code == 200
    after = client.get(url, headers=h).json()
    assert next(s for s in after["actions"] if s["id"] == step["id"])["status"] == "accepted"


def test_the_notes_own_archive_does_what_the_preview_lists(client):
    """The note page's flag and a bulk archive use the same change as the preview's plan."""
    h = nurse(client)
    n = client.post(NOTES, headers=h, json={"title": "Pinned", "body": "x"}).json()
    client.patch(f"{NOTES}/{n['id']}", headers=h, json={"pinned": True})
    listed = {e["kind"] for e in note_preview(client, h, n["id"])["effects"]}
    assert listed == {"note", "pin"}
    got = client.patch(f"{NOTES}/{n['id']}", headers=h, json={"archived": True}).json()
    assert got["archived"] is True and got["pinned"] is False


def test_a_deleted_note_cant_be_archived(client):
    h = nurse(client)
    n = client.post(NOTES, headers=h, json={"title": "Gone", "body": "x"}).json()
    fp = note_preview(client, h, n["id"])["fingerprint"]
    client.delete(f"{NOTES}/{n['id']}", headers=h)
    assert client.get(f"{NOTES}/{n['id']}/archive-preview", headers=h).status_code == 404
    assert archive(client, h, n["id"], fp).status_code == 404


@pytest.mark.parametrize("same_request", [True, False])
def test_two_deletes_at_once_do_it_once(client, monkeypatch, same_request):
    """Another delete finishes while this one waits for the row: the same request (a resend) is
    answered with what the first did; a different one finds nothing to delete. Neither is a 500."""
    from app.models import User
    from app.schemas.lifecycle import LifecycleIn

    h = nurse(client)
    a = application(client, h)
    add_event(client, h, a["id"], "Panel interview")
    fp = preview(client, h, a["id"])["fingerprint"]
    real = lifecycle.lock_for_update
    fired = []

    def the_other_one_finishes_first(db, row):
        if not fired:
            fired.append(True)
            with client.app.state.session_factory() as other:
                me = other.get(User, other.get(Application, a["id"]).user_id)
                body = LifecycleIn(expected_fingerprint=fp, client_request_id="del-1")
                lifecycle.Lifecycle(other, me).delete_application(a["id"], body)
        return real(db, row)

    monkeypatch.setattr(lifecycle, "lock_for_update", the_other_one_finishes_first)
    r = delete(client, h, a["id"], fp, key="del-1" if same_request else "del-2")
    monkeypatch.undo()
    if same_request:
        assert r.status_code == 200 and r.json()["replayed"] is True
    else:
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    with client.app.state.session_factory() as db:
        assert db.scalars(select(Application)).all() == []
        assert [x.client_request_id for x in db.scalars(select(LifecycleReceipt))] == ["del-1"]

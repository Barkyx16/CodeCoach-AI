"""Private real-interview reflections: incomplete is fine, observations kept apart from
interpretations, suggestions only from what was written and never applied on their own, one
action accepted once, outcomes that touch the application only when asked, archived
applications still readable, nothing logged, owner-only, exported and deleted."""

import contextlib
import logging

from sqlalchemy import select

from app.models import InterviewReflection, Note, ReflectionAction, ScheduleEntry
from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def event(client, h):
    a = client.post(
        APPS,
        headers=h,
        json={"employer": "Mercy General", "role_title": "Ward nurse", "stage": "interviewing"},
    ).json()
    ev = client.post(
        f"{APPS}/{a['id']}/events", headers=h, json={"title": "Panel interview", "on_date": "2026-11-12"}
    ).json()["events"][0]
    return a, ev, f"{APPS}/{a['id']}/events/{ev['id']}/reflection"


REFLECTION = {
    "questions": [
        "Tell me about a time patient assessment mattered",
        "How would you handle a medication error?",
    ],
    "topics": ["patient assessment", "quantum accounting"],
    "clear": "My opening about the ward",
    "difficult": "The question about medication errors",
    "observations": [
        {"text": "They asked for another example", "kind": "observed"},
        {"text": "They disliked me", "kind": "interpretation"},
    ],
    "follow_ups": "Send my references by Friday",
    "practice": ["handover"],
    "expected_revision": 0,
}


def test_an_empty_or_incomplete_reflection_is_fine_and_saves_are_revision_checked(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    empty = client.get(url, headers=h)
    assert empty.status_code == 200 and empty.headers["cache-control"] == "no-store"
    assert empty.json()["saved"] is False and empty.json()["role_title"] == "Ward nurse"
    one = client.put(url, headers=h, json={"clear": "  Only this  ", "expected_revision": 0}).json()
    assert one["saved"] and one["clear"] == "Only this" and one["questions"] == [] and one["revision"] == 1
    stale = client.put(url, headers=h, json={"difficult": "x", "expected_revision": 0})
    assert stale.status_code == 409 and stale.json()["error"]["details"]["current_revision"] == 1
    full = client.put(url, headers=h, json={**REFLECTION, "expected_revision": 1}).json()
    assert [o["kind"] for o in full["observations"]] == ["observed", "interpretation"]
    assert full["event_title"] == "Panel interview" and full["stage"] == "interviewing"


def test_suggestions_come_only_from_what_was_written_and_are_never_applied(client):
    h = nurse(client)
    _, _, url = event(client, h)
    assert client.post(f"{url}/suggestions", headers=h).status_code == 400  # nothing saved yet
    client.put(url, headers=h, json=REFLECTION)
    out = client.post(f"{url}/suggestions", headers=h).json()
    kinds = {a["kind"] for a in out["actions"]}
    assert {"practice", "gap", "note"} <= kinds
    assert all(a["status"] == "suggested" and a["applied_ref"] is None for a in out["actions"])
    gap = next(a for a in out["actions"] if a["kind"] == "gap")
    assert "quantum accounting" in gap["title"] and gap["targets"] == ["notebook"]
    practice = next(a for a in out["actions"] if a["kind"] == "practice")
    assert practice["href"].startswith("/careers/registered-nurse/questions/")
    assert not any("disliked" in a["detail"] for a in out["actions"])  # interpretations are never acted on
    with client.app.state.session_factory() as db:
        assert db.scalars(select(Note)).all() == [] and db.scalars(select(ScheduleEntry)).all() == []
    again = client.post(f"{url}/suggestions", headers=h).json()
    assert len(again["actions"]) == len(out["actions"])  # regenerating doesn't duplicate


def test_accept_once_edit_dismiss_and_no_duplicates(client):
    h = nurse(client)
    _, _, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    actions = client.post(f"{url}/suggestions", headers=h).json()["actions"]
    note = next(a for a in actions if a["kind"] == "note")
    edited = client.patch(
        f"{url}/actions/{note['id']}", headers=h, json={"title": "References for Mercy"}
    ).json()
    assert next(a for a in edited["actions"] if a["id"] == note["id"])["title"] == "References for Mercy"
    first = client.post(f"{url}/actions/{note['id']}/accept", headers=h, json={"target": "notebook"}).json()
    second = client.post(f"{url}/actions/{note['id']}/accept", headers=h, json={"target": "notebook"}).json()
    a1 = next(a for a in first["actions"] if a["id"] == note["id"])
    assert (
        a1["status"] == "accepted"
        and a1["applied_ref"] == next(a for a in second["actions"] if a["id"] == note["id"])["applied_ref"]
    )
    with client.app.state.session_factory() as db:
        notes = db.scalars(select(Note)).all()
        assert len(notes) == 1 and notes[0].title == "References for Mercy"
    assert (
        client.patch(f"{url}/actions/{note['id']}", headers=h, json={"status": "dismissed"}).status_code
        == 409
    )
    practice = next(a for a in actions if a["kind"] == "practice")
    assert (
        client.post(
            f"{url}/actions/{practice['id']}/accept", headers=h, json={"target": "schedule"}
        ).status_code
        == 400
    )  # needs a date
    sched = client.post(
        f"{url}/actions/{practice['id']}/accept",
        headers=h,
        json={"target": "schedule", "on_date": "2030-01-08"},
    ).json()
    assert next(a for a in sched["actions"] if a["id"] == practice["id"])["target"] == "schedule"
    gap = next(a for a in actions if a["kind"] == "gap")
    assert (
        client.post(f"{url}/actions/{gap['id']}/accept", headers=h, json={"target": "saved"}).status_code
        == 400
    )
    dismissed = client.patch(f"{url}/actions/{gap['id']}", headers=h, json={"status": "dismissed"}).json()
    assert next(a for a in dismissed["actions"] if a["id"] == gap["id"])["status"] == "dismissed"
    regenerated = client.post(f"{url}/suggestions", headers=h).json()
    assert (
        next(a for a in regenerated["actions"] if a["id"] == gap["id"])["status"] == "dismissed"
    )  # never resurrected


def test_outcomes_change_the_application_only_when_asked(client):
    h = nurse(client)
    a, _, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    waiting = client.put(
        f"{url}/outcome", headers=h, json={"outcome": "awaiting", "update_application": True}
    ).json()
    assert (
        waiting["outcome"] == "awaiting" and waiting["outcome_history"][0]["applied_to_application"] is False
    )
    assert (
        client.get(f"{APPS}/{a['id']}", headers=h).json()["stage"] == "interviewing"
    )  # a wait is not a rejection
    no = client.put(f"{url}/outcome", headers=h, json={"outcome": "not_selected"}).json()
    assert no["outcome_history"][-1]["applied_to_application"] is False
    assert client.get(f"{APPS}/{a['id']}", headers=h).json()["stage"] == "interviewing"
    yes = client.put(
        f"{url}/outcome", headers=h, json={"outcome": "offer", "update_application": True}
    ).json()
    assert yes["outcome_history"][-1]["applied_to_application"] is True
    app = client.get(f"{APPS}/{a['id']}", headers=h).json()
    assert (
        app["stage"] == "offer" and app["history"][0]["note"] == "Recorded from your interview reflection"
    )  # newest first


def test_archived_applications_keep_their_reflections_and_search_is_private(client):
    h = nurse(client)
    a, _, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    client.post(f"{APPS}/{a['id']}/archive", headers=h)
    r = client.get(url, headers=h).json()
    assert r["application_archived"] is True and r["clear"] == "My opening about the ward"
    found = client.get("/api/v1/me/reflections", headers=h, params={"q": "medication"}).json()
    assert [x["event_id"] for x in found] == [r["event_id"]] and found[0]["application_archived"] is True
    assert client.get("/api/v1/me/reflections", headers=h, params={"include_archived": False}).json() == []
    assert client.get("/api/v1/me/reflections", headers=h, params={"q": "nothing like this"}).json() == []


def test_hints_about_identifiers_and_nothing_logged(client, caplog):
    h = nurse(client)
    _, _, url = event(client, h)
    secret = "Mr Patient Example, MRN 12345678, call 07700 900123 or bob@example.com"
    with caplog.at_level(logging.DEBUG):
        r = client.put(url, headers=h, json={"difficult": secret, "expected_revision": 0}).json()
    assert len(r["warnings"]) == 2
    assert "12345678" not in caplog.text and "bob@example.com" not in caplog.text


def test_owner_only_export_and_deletion(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    a, ev, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    client.post(f"{url}/suggestions", headers=h)
    assert client.get(url, headers=other).status_code == 404
    assert client.put(url, headers=other, json={"expected_revision": 0}).status_code == 404
    assert client.get("/api/v1/me/reflections", headers=other).json() == []
    exported = client.get("/api/v1/me/export", headers=h).json()["interview_reflections"]
    assert exported[0]["questions"] == REFLECTION["questions"] and exported[0]["actions"]
    client.delete(f"{APPS}/{a['id']}/events/{ev['id']}", headers=h)
    with client.app.state.session_factory() as db:
        assert (
            db.scalars(select(InterviewReflection)).all() == []
            and db.scalars(select(ReflectionAction)).all() == []
        )


# --- Interview Workflow pack: deleted stories, concurrent accepts, removed results, outcomes --------


def test_a_deleted_story_doesnt_block_saving_and_is_counted(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    _, _, url = event(client, h)
    keep = client.post("/api/v1/me/stories", headers=h, json={"title": "Two call lights"}).json()
    gone = client.post("/api/v1/me/stories", headers=h, json={"title": "Night handover"}).json()
    saved = client.put(url, headers=h, json={**REFLECTION, "story_ids": [keep["id"], gone["id"]]}).json()
    client.delete(f"/api/v1/me/stories/{gone['id']}", headers=h)
    now = client.get(url, headers=h).json()
    assert now["story_ids"] == [keep["id"]] and now["missing_stories"] == 1
    # A tab opened before the delete still sends the old list: the words are saved, the deleted
    # story is unlinked (before: 404 "Story not found", and the reflection couldn't be saved at all).
    r = client.put(
        url,
        headers=h,
        json={
            **REFLECTION,
            "clear": "Still saved",
            "story_ids": [keep["id"], gone["id"]],
            "expected_revision": saved["revision"],
        },
    )
    assert r.status_code == 200 and r.json()["clear"] == "Still saved"
    assert r.json()["story_ids"] == [keep["id"]] and r.json()["missing_stories"] == 0
    # A story that was never linked, or another account's, is still refused.
    theirs = client.post("/api/v1/me/stories", headers=other, json={"title": "Not yours"}).json()
    for bad in (theirs["id"], "00000000-0000-0000-0000-000000000000"):
        r = client.put(url, headers=h, json={**REFLECTION, "story_ids": [bad], "expected_revision": 2})
        assert r.status_code == 404


def test_two_accepts_at_once_create_one_note(client, monkeypatch):
    """The other request accepts the step between this one's read and its write: this one must find
    it accepted and create nothing (a read-then-create would make a second note)."""
    from app.services import reflections as svc

    h = nurse(client)
    _, ev, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    step = next(
        a for a in client.post(f"{url}/suggestions", headers=h).json()["actions"] if a["kind"] == "note"
    )
    real = svc.Reflections._targets
    fired = []

    def other_request_accepts_first(a):
        if not fired:
            fired.append(True)
            with client.app.state.session_factory() as db:
                row = db.get(ReflectionAction, step["id"])
                user_id = db.get(InterviewReflection, ev["id"]).user_id
                note = Note(user_id=user_id, title=row.title, body="other request", tags=[])
                db.add(note)
                db.flush()
                row.status, row.target, row.applied_ref = "accepted", "notebook", note.id
                db.commit()
        return real(a)

    monkeypatch.setattr(svc.Reflections, "_targets", staticmethod(other_request_accepts_first))
    out = client.post(f"{url}/actions/{step['id']}/accept", headers=h, json={"target": "notebook"}).json()
    monkeypatch.setattr(svc.Reflections, "_targets", staticmethod(real))
    with client.app.state.session_factory() as db:
        notes = db.scalars(select(Note)).all()
    assert len(notes) == 1 and notes[0].body == "other request"
    accepted = next(a for a in out["actions"] if a["id"] == step["id"])
    assert accepted["status"] == "accepted" and accepted["applied_ref"] == notes[0].id


def test_a_removed_result_is_shown_as_removed_and_not_recreated(client):
    h = nurse(client)
    _, _, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    actions = client.post(f"{url}/suggestions", headers=h).json()["actions"]
    note_step = next(a for a in actions if a["kind"] == "note")
    out = client.post(
        f"{url}/actions/{note_step['id']}/accept", headers=h, json={"target": "notebook"}
    ).json()
    accepted = next(a for a in out["actions"] if a["id"] == note_step["id"])
    assert accepted["applied_available"] is True
    assert client.delete(f"/api/v1/me/notes/{accepted['applied_ref']}", headers=h).status_code in (200, 204)
    now = next(a for a in client.get(url, headers=h).json()["actions"] if a["id"] == note_step["id"])
    assert now["status"] == "accepted" and now["applied_available"] is False  # history kept, truthfully
    again = client.post(f"{url}/actions/{note_step['id']}/accept", headers=h, json={"target": "notebook"})
    assert again.status_code == 200
    with client.app.state.session_factory() as db:
        notes = db.scalars(select(Note)).all()
    # No second note, and the deleted one stays deleted (restorable from the notebook's own undo).
    assert len(notes) == 1 and notes[0].deleted_at is not None
    # A suggested step has no result yet: nothing is claimed either way.
    assert all(a["applied_available"] is None for a in again.json()["actions"] if a["status"] != "accepted")


def test_an_outcome_and_its_stage_change_are_saved_together_or_not_at_all(client):
    from sqlalchemy import event as sa_event

    h = nurse(client)
    a, _, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)

    def boom(*_):
        raise RuntimeError("the reflection's save fails")

    sa_event.listen(InterviewReflection, "before_update", boom)
    try:
        with contextlib.suppress(RuntimeError):
            client.put(f"{url}/outcome", headers=h, json={"outcome": "offer", "update_application": True})
    finally:
        sa_event.remove(InterviewReflection, "before_update", boom)
    app = client.get(f"{APPS}/{a['id']}", headers=h).json()
    # Before: the stage had already been committed on its own, so the application said "offer"
    # while the reflection didn't.
    assert app["stage"] == "interviewing"
    assert [s["to_stage"] for s in app["history"]] == ["interviewing"]
    assert client.get(url, headers=h).json()["outcome"] == "unknown"


def test_repeating_an_outcome_adds_no_history_and_moves_nothing_again(client):
    h = nurse(client)
    a, _, url = event(client, h)
    client.put(url, headers=h, json=REFLECTION)
    first = client.put(
        f"{url}/outcome", headers=h, json={"outcome": "offer", "update_application": True}
    ).json()
    again = client.put(
        f"{url}/outcome", headers=h, json={"outcome": "offer", "update_application": True}
    ).json()
    assert len(first["outcome_history"]) == len(again["outcome_history"]) == 1
    assert first["outcome_history"][0]["applied_to_application"] is True
    app = client.get(f"{APPS}/{a['id']}", headers=h).json()
    assert [s["to_stage"] for s in app["history"]] == ["offer", "interviewing"]  # newest first
    # A real change is still recorded, and waiting never moves the application.
    later = client.put(
        f"{url}/outcome", headers=h, json={"outcome": "awaiting", "update_application": True}
    ).json()
    assert [h_["outcome"] for h_ in later["outcome_history"]] == ["offer", "awaiting"]
    assert client.get(f"{APPS}/{a['id']}", headers=h).json()["stage"] == "offer"

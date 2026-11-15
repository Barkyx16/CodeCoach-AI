"""More archive and delete previews (Volume 13, prompt 5; docs/LIFECYCLE.md): deleting a story,
deleting a note (restorable for 10 minutes) and archiving a target, each previewed by the plan that
carries it out. The preview lists every one of the learner's records the change touches; carrying it
out works the plan out again, refuses a changed scope with the new plan, and does exactly what it
listed; a retried request reports what was done; another account's ids are "not found". Synthetic
data only."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import (
    Application,
    ExperienceEntry,
    InterviewKit,
    InterviewReflection,
    LifecycleReceipt,
    Note,
    PracticeAnswer,
    RoleTarget,
    SourceReview,
    StoryRevision,
)
from app.services import lifecycle
from tests.test_lifecycle import add_event, application, effects, nurse
from tests.test_requirement_versions import story as target_story
from tests.test_roadmap import STRONG
from tests.test_targets import create, req

APPS = "/api/v1/me/applications"
STORIES = "/api/v1/me/stories"
NOTES = "/api/v1/me/notes"
TARGETS = "/api/v1/targets"
TRIAGE = "Perform patient assessment and triage for incoming patients"
TRACK = "registered-nurse"


def get_preview(client, h, url):
    r = client.get(url, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def carry_out(client, h, url, fingerprint, key=None):
    return client.post(url, headers=h, json={"expected_fingerprint": fingerprint, "client_request_id": key})


def edit_story(client, h, sid, rev, **fields):
    r = client.patch(f"{STORIES}/{sid}", headers=h, json={"expected_revision": rev, **fields})
    assert r.status_code == 200, r.text
    return r.json()


def export(client, h):
    return client.get("/api/v1/me/export", headers=h).json()


# --- deleting a story ------------------------------------------------------------------------------------


def story_in_use(client, h):
    """A story linked to a target's requirement, chosen by a kit, linked to an application and a
    reflection, and rehearsed by a practice answer; edited once (two saved versions)."""
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid, title="Two call lights")
    sid = next(e["id"] for e in t["experience"] if e["title"] == "Two call lights")
    edit_story(client, h, sid, 1, result="Both patients were safe within ten minutes.")
    a = application(client, h)
    assert client.put(f"{APPS}/{a['id']}/stories/{sid}", headers=h).status_code == 200
    ev = add_event(client, h, a["id"], "Panel interview")
    kit = client.put(f"{APPS}/{a['id']}/events/{ev['id']}/kit", headers=h, json={"story_ids": [sid]})
    assert kit.status_code == 200, kit.text
    refl = client.put(
        f"{APPS}/{a['id']}/events/{ev['id']}/reflection",
        headers=h,
        json={"story_ids": [sid], "clear": "My opening about the ward", "expected_revision": 0},
    )
    assert refl.status_code == 200, refl.text
    ans = client.post(
        f"/api/v1/careers/{TRACK}/questions/e-accuracy-0/answers",
        headers=h,
        json={"answer": STRONG, "story_id": sid},
    )
    assert ans.status_code == 201, ans.text
    return {"target": t, "rid": rid, "story": sid, "app": a, "event": ev, "answer": ans.json()}


def test_a_story_delete_preview_lists_each_link_and_the_delete_does_exactly_that(client):
    h = nurse(client)
    w = story_in_use(client, h)
    sid = w["story"]
    url = f"{STORIES}/{sid}/delete-preview"
    p = get_preview(client, h, url)
    assert p["action"] == "delete_story" and p["title"] == "Two call lights"
    assert p["summary"] == "Delete this story, its 1 requirement link and its revisions"
    assert effects(p) == sorted(
        [
            ("deleted", "story", "Two call lights"),
            ("deleted", "requirement link", f"Its link to “{TRIAGE}”"),
            ("kept", "interview-day kit", "Kit for Panel interview"),
            ("unlinked", "application", "Ward nurse at Mercy General"),
            ("unavailable", "reflection", "Reflection on Panel interview"),
            ("unlinked", "practice answer", "An answer that rehearsed it"),
        ]
    )
    deleted = next(e for e in p["effects"] if e["kind"] == "story")
    assert deleted["note"] == "With its 2 saved versions."
    kept = next(e for e in p["effects"] if e["kind"] == "interview-day kit")
    assert kept["id"] == w["event"]["id"] and "Keeps what it prepared from this story" in kept["note"]
    assert "This can't be undone. Archive keeps it out of the way instead." in p["notes"]
    kit_before = client.get(f"{APPS}/{w['app']['id']}/events/{w['event']['id']}/kit", headers=h).json()

    out = carry_out(client, h, f"{STORIES}/{sid}/delete", p["fingerprint"], key="sdel-1")
    assert out.status_code == 200, out.text
    out = out.json()
    assert out["effects"] == p["effects"] and out["message"] == "Deleted Two call lights."
    assert out["restorable_until"] is None
    # Item by item: deleted is gone, unlinked no longer names it, kept is as it was.
    with client.app.state.session_factory() as db:
        assert db.get(ExperienceEntry, sid) is None
        assert db.scalars(select(StoryRevision).where(StoryRevision.story_id == sid)).all() == []
        assert sid not in (db.get(Application, w["app"]["id"]).story_ids or [])
        [refl] = db.scalars(select(InterviewReflection)).all()
        assert sid in refl.story_ids  # what it recorded: it says the story was deleted since
        answer = db.get(PracticeAnswer, w["answer"]["id"])
        assert answer is not None and answer.story_id is None and answer.score == w["answer"]["score"]
        kit = db.scalar(select(InterviewKit).where(InterviewKit.event_id == w["event"]["id"]))
        assert sid in kit.story_ids  # the kit keeps what it prepared, as listed
        assert (
            db.scalar(
                select(SourceReview.id).where(
                    SourceReview.holder_kind == "requirement_link", SourceReview.source_id == sid
                )
            )
            is None
        )
    refl = client.get(f"{APPS}/{w['app']['id']}/events/{w['event']['id']}/reflection", headers=h).json()
    assert refl["story_ids"] == [] and refl["missing_stories"] == 1  # as listed: it says so
    kit_after = client.get(f"{APPS}/{w['app']['id']}/events/{w['event']['id']}/kit", headers=h).json()
    assert all(s["id"] != sid for s in kit_after["stories"])
    [prepared] = [s for s in kit_after["kept_stories"] if s["id"] == sid]
    assert prepared["title"] == next(s for s in kit_before["stories"] if s["id"] == sid)["title"]
    t = client.get(f"{TARGETS}/{w['target']['id']}", headers=h).json()
    assert all(e["id"] != sid for e in t["experience"])
    assert any(r["id"] == w["rid"] for r in t["requirement_list"])  # the requirement stays
    # The export holds none of what was deleted and all of what was kept.
    doc = export(client, h)
    assert all(s["title"] != "Two call lights" for s in doc["stories"])
    assert [a["employer"] for a in doc["applications"]] == ["Mercy General"]
    [kept] = doc["interview_answers"]  # the answer stays, no longer naming the story
    assert kept["id"] == w["answer"]["id"] and kept["story"] is None and kept["score"] == w["answer"]["score"]


def test_a_story_with_nothing_else_says_so(client):
    h = nurse(client)
    s = client.post(STORIES, headers=h, json={"title": "Night handover", "situation": "A quiet ward."}).json()
    p = get_preview(client, h, f"{STORIES}/{s['id']}/delete-preview")
    assert p["summary"] == "Delete this story, its revisions"
    assert effects(p) == [("deleted", "story", "Night handover")]


def test_a_story_scope_changed_after_the_preview_is_refused_with_nothing_done(client):
    h = nurse(client)
    s = client.post(STORIES, headers=h, json={"title": "Night handover", "situation": "A quiet ward."}).json()
    p = get_preview(client, h, f"{STORIES}/{s['id']}/delete-preview")
    a = application(client, h)
    client.put(f"{APPS}/{a['id']}/stories/{s['id']}", headers=h)  # linked since the preview
    r = carry_out(client, h, f"{STORIES}/{s['id']}/delete", p["fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    current = r.json()["error"]["details"]["current"]
    assert ("unlinked", "application", "Ward nurse at Mercy General") in effects(current)
    with client.app.state.session_factory() as db:
        assert db.get(ExperienceEntry, s["id"]) is not None
        assert s["id"] in db.get(Application, a["id"]).story_ids
    # A renamed story changes the preview too.
    edit_story(client, h, s["id"], 1, title="Night handover, renamed")
    again = carry_out(client, h, f"{STORIES}/{s['id']}/delete", current["fingerprint"])
    assert again.status_code == 409


def test_a_replayed_story_delete_reports_what_was_done_and_cant_recreate_it(client):
    h = nurse(client)
    made = client.post(
        STORIES,
        headers=h,
        json={"title": "Night handover", "situation": "A quiet ward.", "client_request_id": "screate-1"},
    )
    assert made.status_code == 201, made.text
    sid = made.json()["id"]
    p = get_preview(client, h, f"{STORIES}/{sid}/delete-preview")
    first = carry_out(client, h, f"{STORIES}/{sid}/delete", p["fingerprint"], key="sdel-1").json()
    again = carry_out(client, h, f"{STORIES}/{sid}/delete", p["fingerprint"], key="sdel-1")
    assert again.status_code == 200, again.text
    assert again.json()["replayed"] is True and again.json()["done_at"] == first["done_at"]
    # Without the key it's simply gone.
    assert carry_out(client, h, f"{STORIES}/{sid}/delete", p["fingerprint"]).status_code == 404
    # A late retry of the create that made it is refused, not made again.
    late = client.post(
        STORIES,
        headers=h,
        json={"title": "Night handover", "situation": "A quiet ward.", "client_request_id": "screate-1"},
    )
    assert late.status_code == 410 and late.json()["error"]["code"] == "deleted_earlier"
    with client.app.state.session_factory() as db:
        receipts = db.scalars(select(LifecycleReceipt)).all()
        assert sorted(r.action for r in receipts) == ["delete_story", lifecycle.STORY_TOMBSTONE]
        assert "Night handover" not in str([r.impact for r in receipts])


def test_the_older_story_delete_carries_out_the_same_plan(client):
    h = nurse(client)
    w = story_in_use(client, h)
    assert client.delete(f"{STORIES}/{w['story']}", headers=h).status_code == 204
    with client.app.state.session_factory() as db:
        assert db.get(ExperienceEntry, w["story"]) is None
        assert w["story"] not in (db.get(Application, w["app"]["id"]).story_ids or [])
        assert db.get(PracticeAnswer, w["answer"]["id"]).story_id is None
        kit = db.scalar(select(InterviewKit).where(InterviewKit.event_id == w["event"]["id"]))
        assert w["story"] in kit.story_ids


def test_another_accounts_story_note_and_target_are_not_found_like_missing_ones(client):
    h = nurse(client)
    s = client.post(STORIES, headers=h, json={"title": "Night handover", "situation": "A quiet ward."}).json()
    n = client.post(NOTES, headers=h, json={"title": "Handover phrases", "body": "SBAR first."}).json()
    t = create(client, h)
    other = nurse(client, email="bea@example.com")
    for base, ident, verb in (
        (STORIES, s["id"], "delete"),
        (NOTES, n["id"], "delete"),
        (TARGETS, t["id"], "archive"),
    ):
        for target in (ident, "00000000-0000-0000-0000-000000000000"):
            pre = client.get(f"{base}/{target}/{verb}-preview", headers=other)
            assert pre.status_code == 404, (base, pre.text)
            done = carry_out(client, other, f"{base}/{target}/{verb}", "f" * 64)
            assert done.status_code == 404, (base, done.text)
    with client.app.state.session_factory() as db:
        assert db.get(ExperienceEntry, s["id"]) is not None
        assert db.get(Note, n["id"]).deleted_at is None
        assert db.get(RoleTarget, t["id"]).archived is False


def test_another_accounts_records_are_never_listed(client):
    h = nurse(client)
    s = client.post(STORIES, headers=h, json={"title": "Night handover", "situation": "A quiet ward."}).json()
    other = nurse(client, email="bea@example.com")
    refused = client.post(
        APPS, headers=other, json={"employer": "Elm Clinic", "role_title": "Nurse", "story_ids": [s["id"]]}
    )
    assert refused.status_code == 404  # they can't link to this account's story
    theirs = application(client, other)
    with client.app.state.session_factory() as db:
        row = db.get(Application, theirs["id"])
        row.story_ids = [s["id"]]  # as if it had been stored anyway
        db.commit()
    p = get_preview(client, h, f"{STORIES}/{s['id']}/delete-preview")
    assert effects(p) == [("deleted", "story", "Night handover")]


# --- deleting a note (restorable for 10 minutes) --------------------------------------------------------


def test_a_note_delete_preview_says_how_long_undo_lasts_and_restore_brings_it_back_exactly(client):
    h = nurse(client)
    n = client.post(
        NOTES, headers=h, json={"title": "Handover phrases", "body": "SBAR first.", "tags": ["handover"]}
    ).json()
    client.patch(f"{NOTES}/{n['id']}", headers=h, json={"pinned": True})
    before = client.get(f"{NOTES}/{n['id']}", headers=h).json()
    p = get_preview(client, h, f"{NOTES}/{n['id']}/delete-preview")
    assert p["action"] == "delete_note"
    assert p["summary"] == "Delete this note (you can undo it for 10 minutes)"
    assert effects(p) == [
        ("deleted", "note", "Handover phrases"),
        ("kept", "pin", "Pinned to the top of your notes"),
        ("kept", "practice packet", "Practice packets"),
    ]
    assert p["effects"][0]["note"].startswith("Restorable for 10 minutes after you delete it (Undo)")
    t0 = datetime.now(UTC)
    out = carry_out(client, h, f"{NOTES}/{n['id']}/delete", p["fingerprint"], key="ndel-1")
    assert out.status_code == 200, out.text
    out = out.json()
    assert out["effects"] == p["effects"]
    until = datetime.fromisoformat(out["restorable_until"])
    assert t0 + timedelta(minutes=9, seconds=55) <= until <= datetime.now(UTC) + timedelta(minutes=10)
    assert out["message"] == "Deleted Handover phrases. You can undo it for 10 minutes."
    assert client.get(f"{NOTES}/{n['id']}", headers=h).status_code == 404
    assert [x["title"] for x in export(client, h)["notes"]] == []
    # A retry reports it, with the same window.
    again = carry_out(client, h, f"{NOTES}/{n['id']}/delete", p["fingerprint"], key="ndel-1").json()
    assert again["replayed"] is True and again["done_at"] == out["done_at"]
    # Undo within the window: back exactly as before, pin and all.
    back = client.post(f"{NOTES}/{n['id']}/restore", headers=h)
    assert back.status_code == 200, back.text
    after = client.get(f"{NOTES}/{n['id']}", headers=h).json()
    drop = {"updated_at", "revision"}
    assert {k: v for k, v in after.items() if k not in drop} == {
        k: v for k, v in before.items() if k not in drop
    }
    assert after["pinned"] is True
    assert [x["title"] for x in export(client, h)["notes"]] == ["Handover phrases"]


def test_after_the_window_a_deleted_note_cant_be_restored(client):
    h = nurse(client)
    n = client.post(NOTES, headers=h, json={"title": "Gone soon", "body": "x"}).json()
    p = get_preview(client, h, f"{NOTES}/{n['id']}/delete-preview")
    assert carry_out(client, h, f"{NOTES}/{n['id']}/delete", p["fingerprint"]).status_code == 200
    with client.app.state.session_factory() as db:
        db.get(Note, n["id"]).deleted_at = datetime.now(UTC) - timedelta(minutes=11)
        db.commit()
    assert client.post(f"{NOTES}/{n['id']}/restore", headers=h).status_code == 404


def test_a_note_scope_changed_after_the_preview_is_refused_with_nothing_done(client):
    h = nurse(client)
    n = client.post(NOTES, headers=h, json={"title": "Handover phrases", "body": "x"}).json()
    p = get_preview(client, h, f"{NOTES}/{n['id']}/delete-preview")
    client.patch(f"{NOTES}/{n['id']}", headers=h, json={"pinned": True})  # pinned since the preview
    r = carry_out(client, h, f"{NOTES}/{n['id']}/delete", p["fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    assert ("kept", "pin", "Pinned to the top of your notes") in effects(
        r.json()["error"]["details"]["current"]
    )
    assert client.get(f"{NOTES}/{n['id']}", headers=h).status_code == 200


def test_the_notes_own_delete_keeps_its_pin_for_undo(client):
    """The older delete (no preview) carries out the same plan: hidden, its pin kept."""
    h = nurse(client)
    n = client.post(NOTES, headers=h, json={"title": "Pinned", "body": "x"}).json()
    client.patch(f"{NOTES}/{n['id']}", headers=h, json={"pinned": True})
    r = client.delete(f"{NOTES}/{n['id']}", headers=h)
    assert r.status_code == 200 and r.json()["restorable_until"]
    assert client.post(f"{NOTES}/{n['id']}/restore", headers=h).json()["pinned"] is True


# --- archiving a target -----------------------------------------------------------------------------------


def test_a_target_archive_preview_lists_what_it_hides_and_keeps_and_is_reversible(client):
    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid, title="Two call lights")
    sid = next(e["id"] for e in t["experience"] if e["title"] == "Two call lights")
    a = application(client, h, target_id=t["id"])
    p = get_preview(client, h, f"{TARGETS}/{t['id']}/archive-preview")
    assert p["action"] == "archive_target" and p["summary"] == "Archive this target"
    listed = effects(p)
    assert ("archived", "target", "ED Nurse") in listed
    assert ("unlinked", "active target", "Your active target") in listed  # it was the active one
    assert ("kept", "story", "Two call lights") in listed
    assert ("kept", "application", "Ward nurse at Mercy General") in listed
    assert ("kept", "practice", "Answers and rounds you practised for it") in listed
    reqs = [e for e in p["effects"] if e["kind"] == "requirement"]
    assert {e["id"] for e in reqs} == {r["id"] for r in t["requirement_list"] if not r["removed"]}
    assert all(e["effect"] == "kept" for e in reqs)
    out = carry_out(client, h, f"{TARGETS}/{t['id']}/archive", p["fingerprint"], key="tarch-1")
    assert out.status_code == 200, out.text
    assert out.json()["effects"] == p["effects"]
    got = client.get(f"{TARGETS}/{t['id']}", headers=h).json()
    assert got["archived"] is True and got["selected"] is False
    assert len(got["requirement_list"]) == len(t["requirement_list"])
    with client.app.state.session_factory() as db:
        assert db.get(ExperienceEntry, sid).target_id == t["id"]
        assert db.get(Application, a["id"]).target_id == t["id"]
    assert [x["title"] for x in export(client, h)["target_roles"]] == ["ED Nurse"]
    # A retry reports it; archiving again is "already archived", and does nothing.
    replay = carry_out(client, h, f"{TARGETS}/{t['id']}/archive", p["fingerprint"], key="tarch-1").json()
    assert replay["replayed"] is True
    again = get_preview(client, h, f"{TARGETS}/{t['id']}/archive-preview")
    assert again["summary"] == "This target is already archived"
    assert all(e["effect"] == "kept" for e in again["effects"])
    # Reversible: unarchiving brings it back with everything, but not as the active target.
    back = client.patch(f"{TARGETS}/{t['id']}", headers=h, json={"archived": False})
    assert back.status_code == 200, back.text
    back = back.json()
    assert back["archived"] is False and back["selected"] is False
    assert [r["id"] for r in back["requirement_list"]] == [r["id"] for r in t["requirement_list"]]


def test_a_target_scope_changed_after_the_preview_is_refused_with_nothing_done(client):
    h = nurse(client)
    t = create(client, h)
    p = get_preview(client, h, f"{TARGETS}/{t['id']}/archive-preview")
    application(client, h, target_id=t["id"])  # linked since the preview
    r = carry_out(client, h, f"{TARGETS}/{t['id']}/archive", p["fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    assert client.get(f"{TARGETS}/{t['id']}", headers=h).json()["archived"] is False


def test_the_targets_own_archive_does_what_the_preview_lists(client):
    h = nurse(client)
    t = create(client, h)
    listed = {
        (e["effect"], e["kind"])
        for e in get_preview(client, h, f"{TARGETS}/{t['id']}/archive-preview")["effects"]
    }
    assert {("archived", "target"), ("unlinked", "active target")} <= listed
    got = client.patch(f"{TARGETS}/{t['id']}", headers=h, json={"archived": True}).json()
    assert got["archived"] is True and got["selected"] is False

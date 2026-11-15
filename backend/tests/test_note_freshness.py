"""A note knows where it came from (Volume 13, prompt 6; docs/STORY_FRESHNESS.md, "Notes"): a note
captured from a question, a lesson or a coding problem says when that source has a newer version
that matters, shows what changed when the content keeps both versions, and "Mark reviewed" is
recorded once, bound to the version shown, until the source changes again. The note itself never
changes. Synthetic data only."""

import dataclasses
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import Note, Problem, SourceReview, TestCase, User
from app.services import note_freshness
from tests.test_content_quality import admin, nurse

NURSE = "registered-nurse"
QID = "m-pressure-0"
NOTES = "/api/v1/me/notes"
CORRECT = f"/api/v1/admin/content/question/{NURSE}/{QID}/corrections"


def question_note(client, h, **over):
    r = client.post(
        NOTES,
        headers=h,
        json={
            "title": "Staying calm",
            "body": "Name the risk first, then the plan.",
            "reflection": "I rushed this last time.",
            "source": {"type": "question", "id": QID, "track": NURSE},
            "excerpt": "Tell me about a time you worked under pressure.",
            "excerpt_kind": "quote",
            **over,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def correct(
    client,
    root,
    significant=True,
    prompt="Describe a shift when the pressure was on and you kept patients safe.",
):
    r = client.post(
        CORRECT,
        headers=root,
        json={"prompt": prompt, "change_note": "Clearer about patient safety.", "significant": significant},
    )
    assert r.status_code == 200, r.text
    return r.json()


def note(client, h, nid):
    r = client.get(f"{NOTES}/{nid}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def review(client, h, nid, version):
    return client.post(f"{NOTES}/{nid}/source-review", headers=h, json={"reviewed_version": version})


def rows(client, nid):
    with client.app.state.session_factory() as db:
        return db.scalars(select(SourceReview).where(SourceReview.holder_id == nid)).all()


def stored(client, nid):
    with client.app.state.session_factory() as db:
        n = db.get(Note, nid)
        return (n.title, n.body, n.reflection, n.excerpt, n.tags, n.revision, n.updated_at, n.source_version)


def updated_ids(client, h):
    return [x["id"] for x in client.get(NOTES, headers=h, params={"source_updated": True}).json()["items"]]


def test_a_new_version_asks_shows_the_change_and_marking_reviewed_is_recorded_once(client):
    h = nurse(client)
    n = question_note(client, h)
    other = client.post(NOTES, headers=h, json={"title": "Unrelated", "body": "x"}).json()
    f = note(client, h, n["id"])["freshness"]
    assert (f["state"], f["captured_version"], f["current_version"]) == ("current", 1, 1)
    assert f["text"] == "Up to date with the question (version 1)."
    assert n["source"]["version"] == "1"  # captured with the note
    before = stored(client, n["id"])

    root = admin(client)
    correct(client, root)
    got = note(client, h, n["id"])
    f = got["freshness"]
    assert f["state"] == "needs_review" and got["source_updated"] is True
    assert f["text"] == (
        "The question changed since you captured this note (version 1, now 2). Review whether your note still fits."
    )
    assert f["comparable"] is True and f["change_notes"] == ["Version 2: Clearer about patient safety."]
    [change] = f["changes"]
    assert change["field"] == "Question" and change["after"].startswith("Describe a shift when the pressure")
    assert change["before"] != change["after"]
    listed = {x["id"]: x["source_updated"] for x in client.get(NOTES, headers=h).json()["items"]}
    assert listed == {n["id"]: True, other["id"]: False}
    assert updated_ids(client, h) == [n["id"]]

    first = review(client, h, n["id"], 2)
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "current" and first.json()["text"].startswith(
        "You marked it reviewed at version 2"
    )
    again = review(client, h, n["id"], 2)  # the same from another tab: nothing more is recorded
    assert again.status_code == 200 and again.json()["state"] == "current"
    [r] = rows(client, n["id"])
    assert (r.decision, r.from_revision, r.to_revision, r.source_kind, r.source_id) == (
        "reviewed",
        1,
        2,
        "question",
        f"{NURSE}/{QID}",
    )
    # The note itself is byte for byte the same: text, excerpt, tags, revision, when it was updated.
    assert stored(client, n["id"]) == before
    assert updated_ids(client, h) == []
    assert note(client, h, n["id"])["source_updated"] is False


def test_a_typo_correction_never_asks(client):
    h = nurse(client)
    n = question_note(client, h)
    correct(client, admin(client), significant=False)
    f = note(client, h, n["id"])["freshness"]
    assert f["state"] == "current" and "only for typos or wording marked minor" in f["text"]
    assert updated_ids(client, h) == []


def test_the_notice_comes_back_after_a_further_change_and_only_then(client):
    h = nurse(client)
    n = question_note(client, h)
    root = admin(client)
    correct(client, root)
    assert review(client, h, n["id"], 2).status_code == 200
    correct(
        client,
        root,
        significant=False,
        prompt="Describe a shift when the pressure was on, and you kept patients safe.",
    )
    assert note(client, h, n["id"])["freshness"]["state"] == "current"  # a minor fix: still reviewed
    correct(client, root, prompt="Tell me about a busy shift where you had to keep several patients safe.")
    f = note(client, h, n["id"])["freshness"]
    assert f["state"] == "needs_review" and f["current_version"] == 4 and f["reviewed_version"] == 2
    assert f["text"].startswith(
        "The question changed again since you marked it reviewed at version 2 (now version 4)."
    )
    assert [c["field"] for c in f["changes"]] == ["Question"]  # from what was reviewed to now


def test_a_source_edited_while_reviewing_records_the_version_shown_and_says_the_newer_one(client):
    h = nurse(client)
    n = question_note(client, h)
    root = admin(client)
    correct(client, root)
    shown = note(client, h, n["id"])["freshness"]["current_version"]
    correct(client, root, prompt="Tell me about a busy shift where you had to keep several patients safe.")
    r = review(client, h, n["id"], shown)
    assert r.status_code == 200
    out = r.json()
    assert out["state"] == "needs_review" and out["reviewed_version"] == 2 and out["current_version"] == 3
    assert "(now version 3)" in out["text"]
    [row] = rows(client, n["id"])
    assert row.to_revision == 2  # the review is for the version shown, never the newer one
    assert review(client, h, n["id"], 4).status_code == 400  # a version that doesn't exist yet


def test_a_note_from_before_versions_were_captured_reads_not_known(client):
    h = nurse(client)
    n = question_note(client, h)
    with client.app.state.session_factory() as db:
        db.execute(update(Note).where(Note.id == n["id"]).values(source_version=None))
        db.commit()
    correct(client, admin(client))
    f = note(client, h, n["id"])["freshness"]
    assert f["state"] == "unknown" and "isn't known" in f["text"] and "Up to date" not in f["text"]
    assert f["captured_version"] is None and f["current_version"] == 2
    assert updated_ids(client, h) == []  # not known isn't "updated" either
    # Marking it reviewed starts from now: later changes are said.
    assert review(client, h, n["id"], 2).json()["state"] == "current"
    assert rows(client, n["id"])[0].from_revision is None


def test_a_retired_source_is_said_and_the_note_still_opens(client):
    h = nurse(client)
    n = question_note(client, h)
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{QID}/retire",
        headers=admin(client),
        json={"reason": "Too vague."},
    )
    assert r.status_code == 200, r.text
    got = note(client, h, n["id"])
    assert got["freshness"]["state"] == "retired" and "Too vague." in got["freshness"]["text"]
    assert got["body"] == "Name the risk first, then the plan."


def test_a_source_that_left_the_library_is_said(client):
    h = nurse(client)
    n = question_note(client, h)
    with client.app.state.session_factory() as db:
        db.execute(update(Note).where(Note.id == n["id"]).values(source_id="gone-0"))
        db.commit()
    f = note(client, h, n["id"])["freshness"]
    assert f["state"] == "unavailable" and "no longer in the library" in f["text"]
    assert review(client, h, n["id"], 1).status_code == 404


def test_a_lesson_change_is_said_without_a_side_by_side(client, monkeypatch):
    h = nurse(client)
    r = client.post(
        NOTES, headers=h, json={"title": "SBAR", "source": {"type": "lesson", "id": "rn-sbar-handoff"}}
    )
    nid = r.json()["id"]
    assert note(client, h, nid)["freshness"]["state"] == "current"
    real = note_freshness.get_unit

    def revised(unit_id):
        u = real(unit_id)
        return (
            dataclasses.replace(u, version=2, changes=(*u.changes, "Reworded the SBAR example.")) if u else u
        )

    monkeypatch.setattr(note_freshness, "get_unit", revised)
    f = note(client, h, nid)["freshness"]
    assert f["state"] == "needs_review" and f["kind"] == "lesson" and f["comparable"] is False
    assert f["changes"] == [] and f["change_notes"] == ["Version 2: Reworded the SBAR example."]
    assert "so what changed can't be shown side by side" in f["text"]
    assert review(client, h, nid, 2).json()["state"] == "current"


def test_a_coding_problem_is_versioned_by_its_tests(client):
    h = nurse(client)
    r = client.post(
        NOTES, headers=h, json={"title": "HashMap trick", "source": {"type": "problem", "id": "two-sum"}}
    )
    nid = r.json()["id"]
    assert r.json()["source"]["version"] == "1"
    with client.app.state.session_factory() as db:
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    f = note(client, h, nid)["freshness"]
    assert f["state"] == "needs_review" and f["kind"] == "problem" and f["comparable"] is False
    assert "coding problem doesn't keep its earlier wording" in f["text"]


def test_interview_notes_have_no_source_versions(client):
    h = nurse(client)
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    r = client.post(
        NOTES, headers=h, json={"title": "Round", "source": {"type": "interview", "id": iv["id"]}}
    )
    assert r.json()["freshness"] is None
    assert review(client, h, r.json()["id"], 1).status_code == 400


def test_another_accounts_notes_and_reviews_are_never_read(client):
    h = nurse(client)
    n = question_note(client, h)
    correct(client, admin(client))
    bea = nurse(client, "bea@example.com", "Bea")
    assert review(client, bea, n["id"], 2).status_code == 404
    assert client.get(f"{NOTES}/{n['id']}", headers=bea).status_code == 404
    # Bea's own review row naming Ada's note (as if one had been stored) never counts for Ada.
    with client.app.state.session_factory() as db:
        bea_user = db.scalar(select(User).where(User.email == "bea@example.com"))
        db.add(
            SourceReview(
                user_id=bea_user.id,
                holder_kind="note",
                holder_id=n["id"],
                source_kind="question",
                source_id=f"{NURSE}/{QID}",
                from_revision=1,
                to_revision=2,
                to_digest="x",
                decision="reviewed",
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    assert note(client, h, n["id"])["freshness"]["state"] == "needs_review"


def test_the_export_carries_the_captured_version_and_each_review(client):
    h = nurse(client)
    n = question_note(client, h)
    correct(client, admin(client))
    review(client, h, n["id"], 2)
    doc = client.get("/api/v1/me/export", headers=h).json()
    [exported] = doc["notes"]
    assert exported["source"]["version"] == "1"
    [r] = exported["source_reviews"]
    assert (r["decision"], r["from_version"], r["to_version"]) == ("reviewed", 1, 2) and r["at"]
    assert doc["source_reviews"] == []  # that list is decisions about stories


def test_a_notes_reviews_go_with_it(client):
    h = nurse(client)
    n = question_note(client, h)
    correct(client, admin(client))
    review(client, h, n["id"], 2)
    assert client.delete(f"{NOTES}/{n['id']}", headers=h).status_code == 200
    with client.app.state.session_factory() as db:
        db.execute(
            update(Note)
            .where(Note.id == n["id"])
            .values(deleted_at=datetime.now(UTC) - timedelta(minutes=11))
        )
        db.commit()
    client.get(NOTES, headers=h)  # the notebook removes notes past their undo window
    with client.app.state.session_factory() as db:
        assert db.get(Note, n["id"]) is None
    assert rows(client, n["id"]) == []


def test_a_restored_note_keeps_its_reviews(client):
    """Undo within the window brings the note back with its reviews (they were never removed)."""
    h = nurse(client)
    n = question_note(client, h)
    correct(client, admin(client))
    review(client, h, n["id"], 2)
    client.delete(f"{NOTES}/{n['id']}", headers=h)
    assert client.post(f"{NOTES}/{n['id']}/restore", headers=h).status_code == 200
    assert note(client, h, n["id"])["freshness"]["state"] == "current"


def test_two_tabs_marking_it_reviewed_at_once_record_it_once(client, monkeypatch):
    """The other tab's review lands between this one reading the reviews and saving its own: the
    unique row refuses the second, and the answer is the recorded state, not an error."""
    h = nurse(client)
    n = question_note(client, h)
    correct(client, admin(client))
    real = note_freshness.NoteFreshnessService.reviews
    raced = []

    def the_other_tab_first(self, note_ids):
        if not raced:
            raced.append(True)
            with client.app.state.session_factory() as db:
                uid = db.get(Note, n["id"]).user_id
                db.add(
                    SourceReview(
                        user_id=uid,
                        holder_kind="note",
                        holder_id=n["id"],
                        source_kind="question",
                        source_id=f"{NURSE}/{QID}",
                        from_revision=1,
                        to_revision=2,
                        to_digest="other-tab",
                        decision="reviewed",
                        created_at=datetime.now(UTC),
                    )
                )
                db.commit()
            return {}
        return real(self, note_ids)

    monkeypatch.setattr(note_freshness.NoteFreshnessService, "reviews", the_other_tab_first)
    r = review(client, h, n["id"], 2)
    monkeypatch.undo()
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "current"
    assert [x.to_digest for x in rows(client, n["id"])] == ["other-tab"]

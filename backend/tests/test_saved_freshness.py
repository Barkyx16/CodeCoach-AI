"""A saved item knows its version (Volume 14, prompt 7; docs/STORY_FRESHNESS.md, "Saved items and
collections"): a saved question or coding problem, on the saved list and in each collection, says
when its source has a newer version that matters since it was saved, by the notes' own rule;
"Mark reviewed" is recorded once for the version shown and clears it until a further change. A
saved item is never changed, moved or unsaved by this. A restore keeps each note's and saved
item's version and reviews. Synthetic data only."""

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models import Bookmark, CollectionItem, Problem, SourceReview, TestCase
from app.services import note_freshness
from tests.test_content_quality import admin, nurse
from tests.test_note_freshness import NOTES, NURSE, QID, correct, question_note, review

SAVED = "/api/v1/me/bookmarks"
COLLECTIONS = "/api/v1/me/collections"
QUESTION = {"item_type": "question", "track": NURSE, "ref_id": QID}
PROBLEM = {"item_type": "problem", "track": "", "ref_id": "two-sum"}


def save(client, h, item=QUESTION):
    r = client.put(SAVED, headers=h, json=item)
    assert r.status_code == 200, r.text
    return next(b for b in r.json() if b["ref_id"] == item["ref_id"])


def saved(client, h, ref_id=QID):
    return next(b for b in client.get(SAVED, headers=h).json() if b["ref_id"] == ref_id)


def review_saved(client, h, version, item=QUESTION):
    return client.post(f"{SAVED}/review", headers=h, json={**item, "reviewed_version": version})


def collection(client, h, name="Night shift prep", items=(QUESTION,)):
    c = client.post(COLLECTIONS, headers=h, json={"name": name}).json()
    for item in items:
        r = client.post(f"{COLLECTIONS}/{c['id']}/items", headers=h, json=item)
        assert r.status_code in (200, 201), r.text
    return client.get(f"{COLLECTIONS}/{c['id']}", headers=h).json()


def item_of(client, h, cid, ref_id=QID):
    c = client.get(f"{COLLECTIONS}/{cid}", headers=h).json()
    return next(i for i in c["item_list"] if i["ref_id"] == ref_id)


def review_item(client, h, cid, item_id, version):
    return client.post(
        f"{COLLECTIONS}/{cid}/items/{item_id}/review", headers=h, json={"reviewed_version": version}
    )


def reviews(client, holder_id):
    with client.app.state.session_factory() as db:
        return db.scalars(select(SourceReview).where(SourceReview.holder_id == holder_id)).all()


def test_a_change_that_matters_shows_on_the_saved_list_and_in_a_collection_until_reviewed(client):
    h = nurse(client)
    b = save(client, h)
    c = collection(client, h)
    [item] = c["item_list"]
    assert (b["content_version"], b["freshness"]["state"]) == (1, "current")
    assert (item["content_version"], item["freshness"]["state"]) == (1, "current")
    assert b["freshness"]["text"] == "Up to date with the question (version 1)."

    root = admin(client)
    correct(client, root)
    b = saved(client, h)
    f = b["freshness"]
    assert f["state"] == "needs_review" and (f["captured_version"], f["current_version"]) == (1, 2)
    assert f["text"] == (
        "The question changed since you saved this item (version 1, now 2). "
        "Review whether it's still what you saved it for."
    )
    assert f["change_notes"] == ["Version 2: Clearer about patient safety."]
    [change] = f["changes"]
    assert change["field"] == "Question" and change["after"].startswith("Describe a shift when the pressure")
    fi = item_of(client, h, c["id"])["freshness"]
    assert fi["state"] == "needs_review" and fi["text"].endswith(
        "Review whether it still belongs in this collection."
    )

    # Mark reviewed on the saved list: recorded once, the badge goes; the collection keeps its own.
    first = review_saved(client, h, 2)
    assert first.status_code == 200, first.text
    assert first.json()["freshness"]["state"] == "current"
    assert first.json()["freshness"]["text"].startswith("You marked it reviewed at version 2")
    assert review_saved(client, h, 2).status_code == 200
    assert [r.to_revision for r in reviews(client, b["id"])] == [2]
    assert item_of(client, h, c["id"])["freshness"]["state"] == "needs_review"
    r = review_item(client, h, c["id"], item["id"], 2)
    assert r.status_code == 200 and r.json()["item_list"][0]["freshness"]["state"] == "current"

    # Nothing about the saved item changed: same row, same place, still saved.
    again = saved(client, h)
    assert (again["id"], again["created_at"], again["content_version"]) == (b["id"], b["created_at"], 1)
    got = item_of(client, h, c["id"])
    assert (got["id"], got["position"], got["content_version"]) == (item["id"], 0, 1)

    # A further change brings it back, and only then.
    correct(client, root, prompt="Describe a hard shift and how you kept every patient safe.")
    f = saved(client, h)["freshness"]
    assert (
        f["state"] == "needs_review"
        and "changed again since you marked it reviewed at version 2" in f["text"]
    )


def test_a_typo_fix_never_asks(client):
    h = nurse(client)
    save(client, h)
    correct(client, admin(client), significant=False)
    f = saved(client, h)["freshness"]
    assert f["state"] == "current" and "only for typos or wording marked minor" in f["text"]


def test_items_saved_before_versions_were_recorded_read_not_known_never_up_to_date(client):
    h = nurse(client)
    b = save(client, h)
    c = collection(client, h)
    with client.app.state.session_factory() as db:
        db.execute(update(Bookmark).where(Bookmark.id == b["id"]).values(content_version=None))
        db.execute(
            update(CollectionItem).where(CollectionItem.collection_id == c["id"]).values(content_version=None)
        )
        db.commit()
    f = saved(client, h)["freshness"]
    assert f["state"] == "unknown" and f["captured_version"] is None
    assert "this item was saved before versions were recorded" in f["text"]
    assert item_of(client, h, c["id"])["freshness"]["state"] == "unknown"
    assert (
        "this item was added before versions were recorded"
        in item_of(client, h, c["id"])["freshness"]["text"]
    )
    assert review_saved(client, h, 1).json()["freshness"]["state"] == "current"


def test_a_saved_problem_is_versioned_by_its_tests(client):
    h = nurse(client)
    b = save(client, h, PROBLEM)
    assert b["content_version"] == 1  # recorded when saved, as questions already were
    with client.app.state.session_factory() as db:
        pid = db.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        db.execute(update(TestCase).where(TestCase.problem_id == pid).values(version=2))
        db.commit()
    f = saved(client, h, "two-sum")["freshness"]
    assert f["state"] == "needs_review" and f["kind"] == "problem" and f["comparable"] is False
    assert "coding problem doesn't keep its earlier wording" in f["text"]
    assert review_saved(client, h, 2, PROBLEM).json()["freshness"]["state"] == "current"


def test_retired_and_removed_sources_are_said_not_hidden(client):
    h = nurse(client)
    save(client, h)
    b2 = save(client, h, {**QUESTION, "ref_id": "m-pressure-1"})
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{QID}/retire",
        headers=admin(client),
        json={"reason": "Too vague."},
    )
    assert r.status_code == 200, r.text
    f = saved(client, h)["freshness"]
    assert (
        f["state"] == "retired"
        and "Too vague." in f["text"]
        and "it stays saved until you remove it" in f["text"]
    )
    with client.app.state.session_factory() as db:
        db.execute(update(Bookmark).where(Bookmark.id == b2["id"]).values(ref_id="gone-0"))
        db.commit()
    gone = saved(client, h, "gone-0")
    assert (
        gone["freshness"]["state"] == "unavailable"
        and "no longer in the library" in gone["freshness"]["text"]
    )
    assert len(client.get(SAVED, headers=h).json()) == 2  # both still listed


def test_a_drill_has_no_versions(client):
    h = nurse(client)
    b = save(client, h, {"item_type": "drill", "track": "", "ref_id": "example"})
    assert b["freshness"] is None and b["content_version"] is None
    r = review_saved(client, h, 1, {"item_type": "drill", "track": "", "ref_id": "example"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_versioned"


def test_two_tabs_marking_it_reviewed_at_once_record_it_once(client, monkeypatch):
    h = nurse(client)
    b = save(client, h)
    correct(client, admin(client))
    real = note_freshness.SourceFreshness.reviews
    raced = []

    def the_other_tab_first(self, ids):
        if not raced and self.holder.kind == "bookmark":
            raced.append(True)
            with client.app.state.session_factory() as db:
                uid = db.get(Bookmark, b["id"]).user_id
                db.add(
                    SourceReview(
                        user_id=uid,
                        holder_kind="bookmark",
                        holder_id=b["id"],
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
        return real(self, ids)

    monkeypatch.setattr(note_freshness.SourceFreshness, "reviews", the_other_tab_first)
    r = review_saved(client, h, 2)
    monkeypatch.undo()
    assert r.status_code == 200, r.text
    assert r.json()["freshness"]["state"] == "current"
    assert [x.to_digest for x in reviews(client, b["id"])] == ["other-tab"]


def test_a_saved_item_added_to_a_collection_keeps_the_version_it_was_saved_at(client):
    """So the badge means the same in both places: added from the saved list, a collection takes the
    version the saved item was last seen at (saved or reviewed), not the version now."""
    h = nurse(client)
    save(client, h)
    correct(client, admin(client))
    first = collection(client, h, "Added after the change")
    [item] = first["item_list"]
    assert item["content_version"] == 1 and item["freshness"]["state"] == "needs_review"
    review_saved(client, h, 2)
    second = collection(client, h, "Added after reviewing")
    assert second["item_list"][0]["content_version"] == 2
    assert second["item_list"][0]["freshness"]["state"] == "current"
    # Not saved: added at the version now.
    third = collection(client, h, "Not saved first", items=({**QUESTION, "ref_id": "m-pressure-1"},))
    assert third["item_list"][0]["content_version"] == 1  # m-pressure-1 is at version 1
    # The same through the bulk add.
    c = client.post(COLLECTIONS, headers=h, json={"name": "Bulk"}).json()
    r = client.post(f"{COLLECTIONS}/{c['id']}/items/batch", headers=h, json={"add": [QUESTION]})
    assert r.status_code == 200, r.text
    assert r.json()["collection"]["item_list"][0]["content_version"] == 2


def test_another_accounts_items_are_not_found_and_their_reviews_are_never_read(client):
    owner = nurse(client, "owner@example.com")
    save(client, owner)
    c = collection(client, owner)
    item = c["item_list"][0]
    other = nurse(client, "other@example.com")
    assert review_saved(client, other, 1).status_code == 404  # not saved by them
    assert review_item(client, other, c["id"], item["id"], 1).status_code == 404
    save(client, other)
    correct(client, admin(client))
    review_saved(client, owner, 2)
    assert saved(client, other)["freshness"]["state"] == "needs_review"  # the owner's review isn't theirs


def test_removing_a_saved_item_or_a_collection_item_takes_its_reviews(client):
    h = nurse(client)
    b = save(client, h)
    c = collection(client, h)
    item = c["item_list"][0]
    correct(client, admin(client))
    review_saved(client, h, 2)
    review_item(client, h, c["id"], item["id"], 2)
    client.delete(SAVED, headers=h, params=QUESTION)
    client.delete(f"{COLLECTIONS}/{c['id']}/items/{item['id']}", headers=h)
    assert reviews(client, b["id"]) == [] and reviews(client, item["id"]) == []
    again = save(client, h)
    assert again["content_version"] == 2 and again["freshness"]["state"] == "current"  # saved now


def test_the_export_carries_versions_and_reviews_and_a_restore_keeps_them(client):
    from tests.test_restore import apply

    h = nurse(client)
    save(client, h)
    save(client, h, PROBLEM)
    collection(client, h)
    n = question_note(client, h)
    plain = question_note(client, h, title="Another", body="Not reviewed.")
    correct(client, admin(client))
    review_saved(client, h, 2)
    review(client, h, n["id"], 2)
    raw = client.get("/api/v1/me/export", headers=h, params={"version": 2}).content
    doc = client.get("/api/v1/me/export", headers=h).json()
    [q] = [b for b in doc["bookmarks"] if b["type"] == "question"]
    assert q["version"] == 1 and [r["to_version"] for r in q["source_reviews"]] == [2]
    [p] = [b for b in doc["bookmarks"] if b["type"] == "problem"]
    assert p["version"] == 1 and p["source_reviews"] == []
    [it] = doc["collections"][0]["items"]
    assert it["version"] == 1 and it["source_reviews"] == []

    fresh = nurse(client, "fresh@example.com")
    r = apply(client, fresh, raw, ["notes", "bookmarks"])
    assert r.status_code in (200, 201), r.text
    b = saved(client, fresh)
    assert b["content_version"] == 1  # the version it was saved at, not the version now
    assert b["freshness"]["state"] == "current" and b["freshness"]["reviewed_version"] == 2
    assert saved(client, fresh, "two-sum")["content_version"] == 1
    notes = {x["title"]: x for x in client.get(NOTES, headers=fresh).json()["items"]}
    reviewed = client.get(f"{NOTES}/{notes['Staying calm']['id']}", headers=fresh).json()["freshness"]
    assert reviewed["state"] == "current" and reviewed["captured_version"] == 1
    assert [x["to_version"] for x in reviewed["reviews"]] == [2]
    not_reviewed = client.get(f"{NOTES}/{notes['Another']['id']}", headers=fresh).json()["freshness"]
    assert not_reviewed["state"] == "needs_review"  # it still asks: the restore didn't take version 2
    assert plain


def test_a_file_version_the_source_never_had_reads_not_known(client):
    """A version from a file is kept only if the source has had it; otherwise "not known", never
    up to date."""
    import json

    from tests.test_restore import apply

    h = nurse(client)
    save(client, h)
    doc = client.get("/api/v1/me/export", headers=h).json()
    doc["bookmarks"][0]["version"] = 7
    doc["bookmarks"][0]["source_reviews"] = [
        {"decision": "reviewed", "from_version": 1, "to_version": 9, "at": "x"}
    ]
    fresh = nurse(client, "fresh@example.com")
    r = apply(client, fresh, json.dumps(doc).encode(), ["bookmarks"])
    assert r.status_code in (200, 201), r.text
    b = saved(client, fresh)
    assert b["content_version"] is None and b["freshness"]["state"] == "unknown"
    assert b["freshness"]["reviews"] == []

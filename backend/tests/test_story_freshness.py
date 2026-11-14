"""Linked evidence freshness (Volume 12, prompt 8; docs/STORY_FRESHNESS.md): a kit's chosen story and
a requirement linked to a story say when the story changed in a way that matters, keep what they
were prepared from, and refresh or keep only when the learner decides, bound to the revision they
reviewed. Synthetic data only."""

import pytest
from sqlalchemy import delete, func, select, update

from app.models import ExperienceEntry, InterviewKit, SourceReview, StoryRevision, User
from app.schemas.freshness import SourceReviewIn
from app.services.kits import Kits
from tests.test_kits import event, nurse
from tests.test_requirement_versions import items, save
from tests.test_requirement_versions import story as target_story
from tests.test_targets import create, req

STORIES = "/api/v1/me/stories"
TRIAGE = "Perform patient assessment and triage for incoming patients"


def a_story(client, h, title="Two call lights", **over):
    body = {
        "title": title,
        "situation": "Two patients called at once.",
        "action": "I triaged by risk.",
        "result": "Both were safe.",
        "short_version": "I triaged by risk.",
        **over,
    }
    r = client.post(STORIES, headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def edit(client, h, sid, rev, **fields):
    r = client.patch(f"{STORIES}/{sid}", headers=h, json={"expected_revision": rev, **fields})
    assert r.status_code == 200, r.text
    return r.json()


def kit_with(client, h, *story_ids):
    _, ev, url = event(client, h)
    r = client.put(url, headers=h, json={"story_ids": list(story_ids), "expected_revision": 0})
    assert r.status_code == 200, r.text
    return ev, url


def chosen(kit, sid):
    return next(s for s in kit["stories"] if s["id"] == sid)


def review(client, h, url, sid, rev, decision="refresh"):
    return client.post(
        f"{url}/stories/{sid}/review", headers=h, json={"reviewed_revision": rev, "decision": decision}
    )


def lineage_rows(client, **where):
    with client.app.state.session_factory() as db:
        stmt = select(func.count()).select_from(SourceReview)
        for k, v in where.items():
            stmt = stmt.where(getattr(SourceReview, k) == v)
        return db.scalar(stmt)


# --- kits -------------------------------------------------------------------------------------------


def test_a_relevant_change_asks_for_a_review_with_what_changed_and_keeps_what_was_prepared(client):
    h = nurse(client)
    s = a_story(client, h)
    _, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Both were safe within ten minutes.")
    kit = client.get(url, headers=h).json()
    st = chosen(kit, s["id"])
    f = st["freshness"]
    assert f["state"] == "needs_review"
    assert f["text"] == (
        "The story changed since you chose it for this kit (version 1, now 2). Review whether it still fits."
    )
    assert f["changes"] == [
        {"field": "Result", "before": "Both were safe.", "after": "Both were safe within ten minutes."}
    ]
    # The kit keeps what it prepared; the story itself is the live reference beside it.
    assert st["prepared"] == {
        "revision": 1,
        "title": "Two call lights",
        "short_version": "I triaged by risk.",
    }
    assert st["chosen_revision"] == 1 and st["revision"] == 2


def test_a_metadata_only_change_raises_nothing(client):
    h = nurse(client)
    s = a_story(client, h)
    _, url = kit_with(client, h, s["id"])
    edit(
        client,
        h,
        s["id"],
        1,
        tags=["triage"],
        notes="Private: ask Sam about it.",
        competencies=["prioritization"],
    )
    f = chosen(client.get(url, headers=h).json(), s["id"])["freshness"]
    assert f["state"] == "current" and f["changes"] == []
    assert f["text"] == (
        "Up to date: the story changed since (version 1, now 2), but only in details this doesn't use, like tags or notes."
    )
    # Spacing alone isn't a change either.
    edit(client, h, s["id"], 2, result="Both  were safe. ")
    assert chosen(client.get(url, headers=h).json(), s["id"])["freshness"]["state"] == "current"


def test_refreshing_is_deliberate_bound_to_the_reviewed_revision_and_recorded_once(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, action="I triaged by risk and called for help.")
    # Nothing refreshes by itself: reading or saving the kit for another reason changes nothing.
    client.put(url, headers=h, json={"notes": "Bring ID", "expected_revision": 1})
    held = chosen(client.get(url, headers=h).json(), s["id"])
    assert held["freshness"]["state"] == "needs_review"
    assert held["prepared"] == {
        "revision": 1,
        "title": "Two call lights",
        "short_version": "I triaged by risk.",
    }
    r = review(client, h, url, s["id"], 2)
    assert r.status_code == 200, r.text
    st = chosen(r.json(), s["id"])
    assert st["freshness"]["state"] == "current" and st["chosen_revision"] == 2
    assert st["prepared"]["revision"] == 2
    [entry] = st["freshness"]["lineage"]
    assert entry["decision"] == "refreshed" and (entry["from_revision"], entry["to_revision"]) == (1, 2)
    assert entry["text"].startswith("Refreshed from version 1 to version 2 on ") and entry["text"].endswith(
        ", by you."
    )
    # Twice is one refresh.
    again = review(client, h, url, s["id"], 2)
    assert again.status_code == 200 and lineage_rows(client, holder_id=ev["id"]) == 1


def test_a_newer_revision_while_reviewing_is_said_and_nothing_changes(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    before = client.get(url, headers=h).json()
    edit(client, h, s["id"], 2, result="Safe, and documented.")  # another tab, while this one reviewed v2
    r = review(client, h, url, s["id"], 2)
    assert r.status_code == 409 and r.json()["error"]["code"] == "source_changed"
    assert r.json()["error"]["details"]["current_revision"] == 3
    assert "now version 3; you reviewed version 2" in r.json()["error"]["message"]
    after = client.get(url, headers=h).json()
    assert chosen(after, s["id"])["chosen_revision"] == 1 and after["revision"] == before["revision"]
    assert lineage_rows(client, holder_id=ev["id"]) == 0


def test_two_tabs_refreshing_at_once_give_one_result(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    app_id = url.split("/")[5]
    factory = client.app.state.session_factory
    with factory() as a, factory() as b:
        user_id = a.scalar(select(ExperienceEntry.user_id).where(ExperienceEntry.id == s["id"]))
        kb = Kits(b, b.get(User, user_id))
        b.get(InterviewKit, ev["id"])  # tab B has the kit open from before tab A's refresh
        Kits(a, a.get(User, user_id)).review_story(
            app_id, ev["id"], s["id"], SourceReviewIn(reviewed_revision=2, decision="refresh")
        )
        out = kb.review_story(
            app_id, ev["id"], s["id"], SourceReviewIn(reviewed_revision=2, decision="refresh")
        )
    assert chosen(out.model_dump(), s["id"])["chosen_revision"] == 2
    assert lineage_rows(client, holder_id=ev["id"], decision="refreshed") == 1


def test_a_failure_during_refresh_leaves_the_kit_exactly_as_it_was(client, monkeypatch):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    before = client.get(url, headers=h).json()

    def broken(self, story, revision):
        raise RuntimeError("disk full")

    monkeypatch.setattr(Kits, "_snapshot_at", broken)
    with pytest.raises(RuntimeError):
        review(client, h, url, s["id"], 2)
    monkeypatch.undo()
    assert client.get(url, headers=h).json() == before
    assert lineage_rows(client, holder_id=ev["id"]) == 0


def test_keeping_the_earlier_revision_is_recorded_and_clears_the_review_until_it_changes_again(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    r = review(client, h, url, s["id"], 2, decision="keep")
    st = chosen(r.json(), s["id"])
    assert st["freshness"]["state"] == "kept" and st["chosen_revision"] == 1
    assert st["freshness"]["text"].startswith("You kept version 1 on ")
    assert "version 2 was the latest then" in st["freshness"]["text"]
    assert st["freshness"]["lineage"][0]["decision"] == "kept"
    assert st["prepared"]["revision"] == 1  # what the kit prepared is still there
    # A tag doesn't bring the question back; new words do.
    edit(client, h, s["id"], 2, tags=["triage"])
    assert chosen(client.get(url, headers=h).json(), s["id"])["freshness"]["state"] == "kept"
    edit(client, h, s["id"], 3, result="Safe, and documented.")
    f = chosen(client.get(url, headers=h).json(), s["id"])["freshness"]
    assert f["state"] == "needs_review"
    assert (
        f["text"]
        == "The story changed again since you kept version 1 (now version 4). Review whether it still fits."
    )
    assert lineage_rows(client, holder_id=ev["id"], decision="kept") == 1


def test_a_deleted_story_says_so_and_keeps_what_the_kit_prepared_until_removed(client):
    h = nurse(client)
    s = a_story(client, h)
    _, url = kit_with(client, h, s["id"])
    client.delete(f"{STORIES}/{s['id']}", headers=h)
    kit = client.get(url, headers=h).json()
    assert kit["stories"] == [] and kit["missing_stories"] == 0
    [kept] = kit["kept_stories"]
    assert (kept["id"], kept["revision"], kept["title"], kept["short_version"]) == (
        s["id"],
        1,
        "Two call lights",
        "I triaged by risk.",
    )
    assert kept["text"] == "This story is no longer available. What the kit prepared from it is kept here."
    # Saving the kit doesn't drop it; removing it is its own choice.
    saved = client.put(url, headers=h, json={"notes": "x", "expected_revision": kit["revision"]}).json()
    assert [k["id"] for k in saved["kept_stories"]] == [s["id"]]
    assert review(client, h, url, s["id"], 1).status_code == 404  # nothing to refresh from
    gone = client.delete(f"{url}/stories/{s['id']}/kept", headers=h)
    assert gone.status_code == 200 and gone.json()["kept_stories"] == []


def test_kits_from_before_say_freshness_is_unknown_and_pruned_versions_are_said(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    with client.app.state.session_factory() as db:
        db.execute(
            update(InterviewKit)
            .where(InterviewKit.event_id == ev["id"])
            .values(story_revisions=None, story_snapshots=None)
        )
        db.commit()
    f = chosen(client.get(url, headers=h).json(), s["id"])["freshness"]
    assert f["state"] == "unknown" and f["prepared_revision"] is None
    assert (
        f["text"]
        == "Whether the story changed since isn't known: this was prepared before story versions were recorded."
    )
    # Prepared from version 1, then version 1 isn't kept any more: the change is said, not shown.
    s2 = a_story(client, h, title="Night handover")
    _, url2 = kit_with(client, h, s2["id"])
    edit(client, h, s2["id"], 1, result="Handed over safely.")
    with client.app.state.session_factory() as db:
        db.execute(
            delete(StoryRevision).where(StoryRevision.story_id == s2["id"], StoryRevision.revision == 1)
        )
        db.commit()
    f2 = chosen(client.get(url2, headers=h).json(), s2["id"])["freshness"]
    assert f2["state"] == "needs_review" and f2["changes"] == []
    assert f2["text"].endswith("The earlier version isn't kept any more, so what changed can't be shown.")


def test_the_older_reread_path_is_recorded_as_a_refresh(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    r = client.put(url, headers=h, json={"reviewed_story_ids": [s["id"]], "expected_revision": 1}).json()
    assert chosen(r, s["id"])["freshness"]["state"] == "current"
    assert lineage_rows(client, holder_id=ev["id"], decision="refreshed") == 1


def test_another_accounts_story_kit_and_links_are_refused(client):
    h = nurse(client)
    s = a_story(client, h)
    _, url = kit_with(client, h, s["id"])
    other = nurse(client, email="grace@example.com")
    assert review(client, other, url, s["id"], 1).status_code == 404
    assert client.delete(f"{url}/stories/{s['id']}/kept", headers=other).status_code == 404
    t = create(client, h)
    linked = target_story(client, h, t, req(t, TRIAGE)["id"])
    e = linked["experience"][0]
    r = client.post(
        f"/api/v1/targets/{t['id']}/experience/{e['id']}/review",
        headers=other,
        json={"reviewed_revision": 1, "decision": "refresh", "requirement_ids": [req(t, TRIAGE)["id"]]},
    )
    assert r.status_code == 404
    assert lineage_rows(client) == 0


# --- requirement links --------------------------------------------------------------------------------


def link_of(t, story_id, rid):
    e = next(x for x in t["experience"] if x["id"] == story_id)
    return next(link for link in e["requirement_links"] if link["requirement_id"] == rid)


def test_a_requirement_link_asks_for_a_review_when_the_story_changes_and_not_for_tags(client):
    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    assert link_of(t, e["id"], rid)["story_freshness"]["state"] == "current"
    edit(client, h, e["id"], 1, tags=["triage"])  # from the story bank: metadata only
    t = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    assert link_of(t, e["id"], rid)["story_freshness"]["state"] == "current"
    edit(client, h, e["id"], 2, result="Stable within the hour.")
    t = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    link = link_of(t, e["id"], rid)
    f = link["story_freshness"]
    assert f["state"] == "needs_review"
    assert (
        f["text"] == "The story changed since you linked it (version 1, now 3). Review whether it still fits."
    )
    assert f["changes"] == [{"field": "Result", "before": "Stable.", "after": "Stable within the hour."}]
    # The requirement's own version is a separate thing, and unchanged.
    assert (link["linked_version"], link["current_version"], link["status"]) == (1, 1, "current")


def test_a_requirement_link_refreshes_or_keeps_deliberately(client):
    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    edit(client, h, e["id"], 1, result="Stable within the hour.")
    url = f"/api/v1/targets/{t['id']}/experience/{e['id']}/review"
    stale = client.post(
        url, headers=h, json={"reviewed_revision": 1, "decision": "refresh", "requirement_ids": [rid]}
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "source_changed"
    assert lineage_rows(client, holder_id=rid) == 0
    unlinked = client.post(
        url,
        headers=h,
        json={
            "reviewed_revision": 2,
            "decision": "refresh",
            "requirement_ids": [req(t, "Current RN license")["id"]],
        },
    )
    assert unlinked.status_code == 404
    kept = client.post(
        url, headers=h, json={"reviewed_revision": 2, "decision": "keep", "requirement_ids": [rid]}
    )
    assert link_of(kept.json(), e["id"], rid)["story_freshness"]["state"] == "kept"
    done = client.post(
        url, headers=h, json={"reviewed_revision": 2, "decision": "refresh", "requirement_ids": [rid]}
    )
    f = link_of(done.json(), e["id"], rid)["story_freshness"]
    assert f["state"] == "current" and f["prepared_revision"] == 2
    assert [x["decision"] for x in f["lineage"]] == ["refreshed", "kept"]
    client.post(
        url, headers=h, json={"reviewed_revision": 2, "decision": "refresh", "requirement_ids": [rid]}
    )
    assert lineage_rows(client, holder_id=rid, decision="refreshed") == 1


def test_links_from_before_say_freshness_is_unknown(client):
    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    with client.app.state.session_factory() as db:
        db.execute(
            update(ExperienceEntry).where(ExperienceEntry.id == e["id"]).values(requirement_versions=None)
        )
        db.commit()
    t = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    assert link_of(t, e["id"], rid)["story_freshness"]["state"] == "unknown"


def test_the_export_keeps_what_was_prepared_and_every_decision(client):
    h = nurse(client)
    s = a_story(client, h)
    ev, url = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    review(client, h, url, s["id"], 2, decision="keep")
    doc = client.get("/api/v1/me/export", headers=h).json()
    [k] = doc["interview_kits"]
    assert k["stories_as_prepared"][s["id"]]["revision"] == 1
    [d] = doc["source_reviews"]
    assert d == {
        "holder": f"kit:{ev['id']}",
        "story": s["id"],
        "decision": "kept",
        "from_revision": 1,
        "to_revision": 2,
        "at": d["at"],
    }


def test_editing_the_story_in_the_workspace_doesnt_silently_refresh_its_links(client):
    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    edited = client.put(
        f"/api/v1/targets/{t['id']}/experience/{e['id']}",
        headers=h,
        json={
            "title": e["title"],
            "situation": "A night shift.",
            "action": "I escalated early.",
            "result": "Stable.",
            "requirement_ids": [rid],
            "expected_revision": 1,
        },
    )
    assert edited.status_code == 200, edited.text
    f = link_of(edited.json(), e["id"], rid)["story_freshness"]
    assert f["state"] == "needs_review" and f["prepared_revision"] == 1 and f["current_revision"] == 2
    assert lineage_rows(client) == 0


def test_reusing_a_link_for_a_new_wording_keeps_its_story_freshness(client):
    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    its = items(t)
    next(i for i in its if i["id"] == rid)["text"] = (
        "Perform patient assessment and triage for every incoming patient"
    )
    t = save(client, h, t, its).json()
    assert link_of(t, e["id"], rid)["status"] == "earlier_wording"
    reused = client.post(
        f"/api/v1/targets/{t['id']}/experience/{e['id']}/requirements/{rid}/reuse", headers=h
    ).json()
    link = link_of(reused, e["id"], rid)
    # The requirement's version moved on; the story's own freshness is untouched by that.
    assert link["status"] == "current" and link["linked_version"] == 2
    assert link["story_freshness"]["state"] == "current" and link["story_freshness"]["prepared_revision"] == 1


def test_two_tabs_refreshing_a_link_at_once_give_one_result(client, monkeypatch):
    """Both read the link's decisions before either wrote (simulated: the second sees none), so the
    second one's own duplicate check can't help; the database's uniqueness gives one result."""
    from app.schemas.roles import StoryLinksReviewIn
    from app.services.roles import RoleTargets
    from app.services.story_freshness import StoryFreshness

    h = nurse(client)
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    edit(client, h, e["id"], 1, result="Stable within the hour.")
    body = StoryLinksReviewIn(reviewed_revision=2, decision="refresh", requirement_ids=[rid])
    factory = client.app.state.session_factory
    with factory() as a, factory() as b:
        user_id = a.scalar(select(ExperienceEntry.user_id).where(ExperienceEntry.id == e["id"]))
        RoleTargets(a, judge_enabled=False).review_story_links(a.get(User, user_id), t["id"], e["id"], body)
        monkeypatch.setattr(StoryFreshness, "decisions", lambda self, *args: [])  # read before A's write
        out = RoleTargets(b, judge_enabled=False).review_story_links(
            b.get(User, user_id), t["id"], e["id"], body
        )
    assert out.id == t["id"]
    assert lineage_rows(client, holder_id=rid, decision="refreshed") == 1


def test_decisions_go_with_what_they_were_about_and_nothing_else(client):
    h = nurse(client)
    # A kit decision, and a link decision, on the same story.
    t = create(client, h)
    rid = req(t, TRIAGE)["id"]
    t = target_story(client, h, t, rid)
    e = t["experience"][0]
    ev, url = kit_with(client, h, e["id"])
    edit(client, h, e["id"], 1, result="Stable within the hour.")
    assert review(client, h, url, e["id"], 2, decision="keep").status_code == 200
    link = client.post(
        f"/api/v1/targets/{t['id']}/experience/{e['id']}/review",
        headers=h,
        json={"reviewed_revision": 2, "decision": "keep", "requirement_ids": [rid]},
    )
    assert link.status_code == 200
    assert lineage_rows(client) == 2
    # The story is deleted: its links go with it, and their decisions; the kit keeps its own.
    client.delete(f"{STORIES}/{e['id']}", headers=h)
    assert lineage_rows(client, holder_kind="requirement_link") == 0
    assert lineage_rows(client, holder_kind="kit", holder_id=ev["id"]) == 1
    # Removing what the kit kept removes its decisions too.
    client.delete(f"{url}/stories/{e['id']}/kept", headers=h)
    assert lineage_rows(client) == 0
    # An application's kits go with it, and their decisions.
    s = a_story(client, h)
    ev2, url2 = kit_with(client, h, s["id"])
    edit(client, h, s["id"], 1, result="Safe.")
    review(client, h, url2, s["id"], 2, decision="keep")
    assert lineage_rows(client, holder_id=ev2["id"]) == 1
    app_id = url2.split("/")[5]
    assert client.delete(f"/api/v1/me/applications/{app_id}", headers=h).status_code == 204
    assert lineage_rows(client) == 0

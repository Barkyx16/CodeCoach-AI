"""Interview-day kits: useful with only a role and a time, suggestions labelled and grounded in
the learner's own job target, nothing verified on their behalf, private links, owner-only."""

from sqlalchemy import select

from app.models import InterviewKit
from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"
JD = "Registered Nurse, Medical Ward. Responsibilities: assess and prioritise patient care. We offer a structured induction and preceptorship. 12-hour shifts."


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def event(client, h, **over):
    a = client.post(
        APPS, headers=h, json={"employer": "Mercy General", "role_title": "Ward nurse", **over}
    ).json()
    ev = client.post(
        f"{APPS}/{a['id']}/events",
        headers=h,
        json={
            "title": "Panel interview",
            "on_date": "2026-11-12",
            "local_time": "10:00",
            "timezone": "Europe/London",
        },
    ).json()["events"][0]
    return a, ev, f"{APPS}/{a['id']}/events/{ev['id']}/kit"


def test_a_kit_is_useful_with_only_a_role_and_a_time_and_stores_nothing_until_changed(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    r = client.get(url, headers=h)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    kit = r.json()
    assert kit["saved"] is False and kit["format"] == "unknown" and kit["role_title"] == "Ward nurse"
    assert kit["starts_at"].startswith("2026-11-12T10:00:00")
    assert all(c["origin"] == "suggested" and not c["done"] for c in kit["checklist"])
    assert "Find out whether it's remote, by phone or in person" in [c["text"] for c in kit["checklist"]]
    assert {q["group"] for q in kit["questions"]} >= {"role", "team", "training", "workflow", "next_steps"}
    with client.app.state.session_factory() as db:
        assert db.scalars(select(InterviewKit)).all() == []


def test_questions_come_from_your_own_target_and_never_claim_employer_facts(client):
    h = nurse(client)
    t = client.post("/api/v1/targets", headers=h, json={"title": "Ward nurse", "description": JD}).json()
    a, ev, url = event(client, h, target_id=t["id"])
    kit = client.get(url, headers=h).json()
    from_target = [q for q in kit["questions"] if q["id"].startswith("s-req-")]
    origin = {f"s-req-{r['id'][:8]}": r["origin"] for r in t["requirement_list"]}
    expected = {
        "explicit": "Based on a requirement in the job description you pasted",
        "user": "Based on a requirement you added to your job target",
        "inferred": "Based on a skill commonly expected in this career (not from the job description)",
    }
    # Each says where it really came from: a skill inferred from the career profile is never
    # presented as something the employer wrote.
    assert from_target and all(q["note"].startswith(expected[origin[q["id"]]]) for q in from_target)
    assert {origin[q["id"]] for q in from_target} >= {"inferred"}
    training = next(q for q in kit["questions"] if q["group"] == "training")
    assert (
        "mentions “induction”" in training["note"] and training["excluded"] is False
    )  # pointed out, not hidden
    workflow = next(q for q in kit["questions"] if q["group"] == "workflow")
    assert "shifts" in workflow["note"]


def test_switching_format_swaps_untouched_suggestions_and_keeps_yours(client):
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    checklist = kit["checklist"]
    checklist[0]["done"] = True  # the learner ticked "Confirm the date…"
    checklist.append({"id": "u-1", "text": "Print my registration card", "origin": "yours"})
    saved = client.put(url, headers=h, json={"checklist": checklist}).json()
    assert saved["saved"] is True
    remote = client.put(url, headers=h, json={"format": "remote"}).json()
    texts = [c["text"] for c in remote["checklist"]]
    assert "Print my registration card" in texts and "Check your microphone and camera" in texts
    assert "Find out whether it's remote, by phone or in person" not in texts
    assert (
        next(c for c in remote["checklist"] if c["text"] == "Confirm the date, time and time zone")["done"]
        is True
    )


def test_editing_hiding_reordering_and_excluding_are_kept(client):
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    qs = kit["questions"]
    qs.reverse()  # priority is the order you save
    qs[0]["excluded"] = True
    qs.append(
        {"id": "u-q", "text": "How is feedback given to new nurses?", "group": "training", "origin": "yours"}
    )
    cl = kit["checklist"]
    cl[1]["hidden"] = True
    out = client.put(
        url,
        headers=h,
        json={"questions": qs, "checklist": cl, "interviewers": [{"name": "", "role": "Ward manager"}]},
    ).json()
    assert [q["id"] for q in out["questions"]] == [q["id"] for q in qs]
    assert out["questions"][0]["excluded"] and out["questions"][-1]["origin"] == "yours"
    assert out["checklist"][1]["hidden"] and out["interviewers"] == [{"name": "", "role": "Ward manager"}]


def test_links_are_checked_and_stories_must_be_yours(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    _, _, url = event(client, h)
    for bad in ("javascript:alert(1)", "zoommtg://x", "https://exa mple.com"):
        assert client.put(url, headers=h, json={"meeting_link": bad}).status_code == 422, bad
    assert (
        client.put(url, headers=h, json={"meeting_link": "https://meet.example.com/abc?pwd=1"}).json()[
            "meeting_link"
        ]
        == "https://meet.example.com/abc?pwd=1"
    )
    assert client.put(url, headers=h, json={"clear_meeting_link": True}).json()["meeting_link"] is None
    mine = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": "Two call lights", "short_version": "I triaged by risk."},
    ).json()
    theirs = client.post("/api/v1/me/stories", headers=other, json={"title": "Not yours"}).json()
    assert client.put(url, headers=h, json={"story_ids": [theirs["id"]]}).status_code == 404
    out = client.put(url, headers=h, json={"story_ids": [mine["id"]]}).json()
    assert out["stories"] == [
        {
            "id": mine["id"],
            "title": "Two call lights",
            "short_version": "I triaged by risk.",
            "archived": False,
            "revision": 1,
            "chosen_revision": 1,  # the version it was when chosen
            # As the kit prepared it, and whether that still matches (docs/STORY_FRESHNESS.md).
            "prepared": {"revision": 1, "title": "Two call lights", "short_version": "I triaged by risk."},
            "freshness": {
                "state": "current",
                "text": "Up to date with the story (version 1).",
                "prepared_revision": 1,
                "current_revision": 1,
                "changes": [],
                "lineage": [],
            },
        }
    ]


def test_kits_are_private_exported_and_deleted(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    a, ev, url = event(client, h)
    client.put(
        url, headers=h, json={"notes": "Ask about parking.", "meeting_link": "https://meet.example.com/x"}
    )
    assert client.get(url, headers=other).status_code == 404
    assert client.put(url, headers=other, json={"notes": "x"}).status_code == 404
    exported = client.get("/api/v1/me/export", headers=h).json()["interview_kits"]
    assert exported[0]["notes"] == "Ask about parking."
    assert (
        exported[0]["revision"] == 1
        and exported[0]["saved_for_event_time"] == "2026-11-12|10:00|Europe/London"
    )
    assert exported[0]["story_versions_when_chosen"] == {}
    # Deleting the event deletes its kit.
    client.delete(f"{APPS}/{a['id']}/events/{ev['id']}", headers=h)
    with client.app.state.session_factory() as db:
        assert db.scalars(select(InterviewKit)).all() == []


def test_a_format_change_saved_with_the_whole_kit_still_gets_that_formats_suggestions(client):
    # The page saves everything at once: the new format together with the checklist it showed.
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    out = client.put(
        url,
        headers=h,
        json={"format": "in_person", "checklist": kit["checklist"], "questions": kit["questions"]},
    ).json()
    texts = [c["text"] for c in out["checklist"]]
    assert "Check the address and how long it takes to get there" in texts
    assert "Find out whether it's remote, by phone or in person" not in texts


# --- Interview Workflow pack: conflict-safe saves, what a kit was saved against --------------------


def test_a_stale_save_is_refused_and_changes_nothing(client):
    h = nurse(client)
    _, _, url = event(client, h)
    kit = client.get(url, headers=h).json()
    assert kit["revision"] == 0  # never saved
    first = client.put(url, headers=h, json={"notes": "Tab A", "expected_revision": 0}).json()
    assert first["revision"] == 1
    # Tab B loaded the kit before tab A saved, and saves an older copy.
    stale = client.put(url, headers=h, json={"notes": "Tab B", "expected_revision": 0})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_revision"
    details = stale.json()["error"]["details"]
    # The saved version comes back with the refusal, so the page can show both and let the learner choose.
    assert details["current_revision"] == 1 and details["current"]["notes"] == "Tab A"
    assert client.get(url, headers=h).json()["notes"] == "Tab A"  # nothing overwritten
    # Reloading, then saving against the current revision, works.
    assert client.put(url, headers=h, json={"notes": "Tab B", "expected_revision": 1}).json()["revision"] == 2


def test_a_save_that_loses_a_race_is_a_conflict_not_a_lost_update(client, monkeypatch):
    """Both tabs pass the revision check; the other one commits first. The losing UPDATE matches no
    row (the revision moved), so it's refused instead of overwriting."""
    from app.services import kits as kits_service

    h = nurse(client)
    _, ev, url = event(client, h)
    client.put(url, headers=h, json={"notes": "Saved", "expected_revision": 0})
    real = kits_service.Kits._story_revisions

    def other_tab_commits_first(self, kit, before, reviewed):
        with client.app.state.session_factory() as db:
            row = db.get(InterviewKit, ev["id"])
            row.notes = "Other tab"
            db.commit()
        return real(self, kit, before, reviewed)

    monkeypatch.setattr(kits_service.Kits, "_story_revisions", other_tab_commits_first)
    r = client.put(url, headers=h, json={"notes": "This tab", "expected_revision": 1})
    monkeypatch.setattr(kits_service.Kits, "_story_revisions", real)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"
    assert r.json()["error"]["details"]["current_revision"] == 2
    assert r.json()["error"]["details"]["current"]["notes"] == "Other tab"
    assert client.get(url, headers=h).json()["notes"] == "Other tab"


def test_two_first_saves_at_once_give_one_kit_and_a_conflict(client, monkeypatch):
    from app.services import kits as kits_service

    h = nurse(client)
    _, ev, url = event(client, h)
    user_id = client.get("/api/v1/auth/me", headers=h).json()["id"]
    real = kits_service.Kits._story_revisions

    def other_tab_creates_it(self, kit, before, reviewed):
        with client.app.state.session_factory() as db:
            db.add(InterviewKit(event_id=ev["id"], user_id=user_id, notes="Other tab"))
            db.commit()
        return real(self, kit, before, reviewed)

    monkeypatch.setattr(kits_service.Kits, "_story_revisions", other_tab_creates_it)
    r = client.put(url, headers=h, json={"notes": "This tab", "expected_revision": 0})
    monkeypatch.setattr(kits_service.Kits, "_story_revisions", real)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"  # not a 500
    with client.app.state.session_factory() as db:
        assert [k.notes for k in db.scalars(select(InterviewKit))] == ["Other tab"]


def test_a_rescheduled_interview_shows_in_the_kit_without_touching_what_you_ticked(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    kit = client.get(url, headers=h).json()
    ticked = [{**c, "done": c["text"] == "Confirm the date, time and time zone"} for c in kit["checklist"]]
    saved = client.put(url, headers=h, json={"checklist": ticked, "expected_revision": 0}).json()
    assert saved["rescheduled_from"] is None
    client.put(
        f"{APPS}/{a['id']}/events/{ev['id']}",
        headers=h,
        json={
            "title": "Panel interview",
            "on_date": "2026-11-13",
            "local_time": "14:30",
            "timezone": "Europe/London",
        },
    )
    moved = client.get(url, headers=h).json()
    # The kit reads the event live, and says what it was saved against.
    assert (moved["on_date"], moved["local_time"]) == ("2026-11-13", "14:30")
    assert moved["rescheduled_from"] == {
        "on_date": "2026-11-12",
        "local_time": "10:00",
        "timezone": "Europe/London",
    }
    # The learner's tick is theirs: not silently undone.
    assert next(c for c in moved["checklist"] if c["text"].startswith("Confirm the date"))["done"] is True
    again = client.put(url, headers=h, json={"notes": "Checked the new time", "expected_revision": 1}).json()
    assert again["rescheduled_from"] is None


def test_a_kit_saved_before_snapshots_existed_claims_nothing(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    client.put(url, headers=h, json={"notes": "Old kit"})
    with client.app.state.session_factory() as db:  # as a kit saved before the upgrade looks
        row = db.get(InterviewKit, ev["id"])
        row.event_when, row.story_revisions = None, None
        db.commit()
    client.put(
        f"{APPS}/{a['id']}/events/{ev['id']}",
        headers=h,
        json={"title": "Panel interview", "on_date": "2026-11-20"},
    )
    assert client.get(url, headers=h).json()["rescheduled_from"] is None  # unknown, not guessed


def test_story_changes_after_choosing_are_visible_and_deleted_ones_are_kept(client):
    h = nurse(client)
    _, _, url = event(client, h)
    s1 = client.post("/api/v1/me/stories", headers=h, json={"title": "Two call lights"}).json()
    s2 = client.post("/api/v1/me/stories", headers=h, json={"title": "Night handover"}).json()
    s3 = client.post("/api/v1/me/stories", headers=h, json={"title": "Family meeting"}).json()
    kit = client.put(
        url, headers=h, json={"story_ids": [s1["id"], s2["id"], s3["id"]], "expected_revision": 0}
    ).json()
    assert [s["chosen_revision"] for s in kit["stories"]] == [1, 1, 1]
    # Renamed and rewritten after it was chosen.
    client.patch(
        f"/api/v1/me/stories/{s1['id']}",
        headers=h,
        json={"title": "Two call lights at once", "result": "Both patients safe.", "expected_revision": 1},
    )
    client.post(f"/api/v1/me/stories/{s2['id']}/archive", headers=h)
    client.delete(f"/api/v1/me/stories/{s3['id']}", headers=h)
    now = client.get(url, headers=h).json()
    by_id = {s["id"]: s for s in now["stories"]}
    assert by_id[s1["id"]]["title"] == "Two call lights at once"  # a live reference, not a copy
    assert (by_id[s1["id"]]["revision"], by_id[s1["id"]]["chosen_revision"]) == (2, 1)
    assert by_id[s2["id"]]["archived"] is True  # still shown, so it can be unticked
    # Deleted: no longer a live story, but what the kit prepared from it is kept (STORY_FRESHNESS.md).
    assert s3["id"] not in by_id and now["missing_stories"] == 0
    assert [(k["id"], k["title"], k["revision"]) for k in now["kept_stories"]] == [
        (s3["id"], "Family meeting", 1)
    ]
    # Saving something else doesn't quietly mark the change as reread...
    kept = client.put(url, headers=h, json={"notes": "x", "expected_revision": 1}).json()
    assert next(s for s in kept["stories"] if s["id"] == s1["id"])["chosen_revision"] == 1
    # A page opened before the delete still sends the deleted one: saved, and it's dropped.
    stale_list = client.put(
        url, headers=h, json={"story_ids": [s1["id"], s2["id"], s3["id"]], "expected_revision": 2}
    )
    assert stale_list.status_code == 200 and stale_list.json()["missing_stories"] == 0
    assert [k["id"] for k in stale_list.json()["kept_stories"]] == [s3["id"]]  # until it's removed
    # ...saying so does.
    reread = client.put(
        url, headers=h, json={"reviewed_story_ids": [s1["id"]], "expected_revision": 3}
    ).json()
    assert next(s for s in reread["stories"] if s["id"] == s1["id"])["chosen_revision"] == 2


def test_a_long_requirement_still_gives_a_valid_suggestion(client):
    h = nurse(client)
    t = client.post("/api/v1/targets", headers=h, json={"title": "Ward nurse", "description": JD}).json()
    long_text = ("Coordinate safe discharge planning with families, social work and community teams " * 4)[
        :300
    ]
    r = client.post(
        f"/api/v1/targets/{t['id']}/requirements",
        headers=h,
        json={"text": long_text, "category": "responsibility"},
    )
    assert r.status_code in (200, 201), r.text
    from app.models import TargetRequirement

    with client.app.state.session_factory() as db:  # only the long one is left to suggest from
        for req in db.scalars(select(TargetRequirement).where(TargetRequirement.text != long_text)):
            req.removed = True
        db.commit()
    _, _, url = event(client, h, target_id=t["id"])
    kit = client.get(url, headers=h)
    assert kit.status_code == 200  # before: a validation error (question over 300, note over 200)
    from_req = [q for q in kit.json()["questions"] if q["id"].startswith("s-req-")]
    assert len(from_req) == 1 and from_req[0]["text"].endswith("…” day to day?")
    for q in kit.json()["questions"]:
        assert len(q["text"]) <= 300 and (q["note"] is None or len(q["note"]) <= 200)

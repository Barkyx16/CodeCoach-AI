"""Accepted improvements (Volume 12, prompt 1; docs/ACCEPTED_ACTIONS.md): one accepted suggestion is
one action with one id, shown by the plan, the schedule and a kit checklist without copies; accepting
again (another tab, a lost reply, at the same moment) finds the same action; rescheduling moves an
occurrence; a weekly action's occurrences are done one at a time; edits are revision-checked; the
feedback it came from stays as it was; another account's ids are 404."""

from sqlalchemy import delete

from app.models import AcceptedAction, PracticeSession
from app.services import actions as actions_service
from app.services.ics import escape
from tests.conftest import auth_headers, register
from tests.test_kits import event
from tests.test_review import STRONG, WEAK, round_with

BASE = "/api/v1/me/actions"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def improvement(client, h):
    """A finished round with something to improve, and its first suggested improvement."""
    iv = round_with(client, h, [STRONG, WEAK, WEAK, None, STRONG])
    review = client.get(f"/api/v1/interviews/{iv}/review", headers=h).json()
    return iv, review["improvements"][0]


def accept(client, h, iv, key, **over):
    return client.post(BASE, headers=h, json={"source": {"interview_id": iv, "key": key}, **over})


def test_accepting_the_same_suggestion_again_is_the_same_action_and_the_feedback_is_untouched(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    assert imp["key"] and imp["action_id"] is None
    first = accept(client, h, iv, imp["key"])
    assert first.status_code == 201, first.text
    action = first.json()
    # Again (a double click, a second tab, a resend after a lost reply): the same action, 200.
    again = accept(client, h, iv, imp["key"])
    assert again.status_code == 200 and again.json()["id"] == action["id"]
    assert len(client.get(BASE, headers=h).json()) == 1
    # Where it came from, as it read; the review still says exactly what it said, now with the link.
    src = action["source"]
    assert src["interview_id"] == iv and src["label"] == imp["title"] and src["why"] == imp["why"]
    assert src["versions"] and all(v["version"] >= 1 for v in src["versions"]) and src["available"]
    assert action["title"] == imp["title"] and action["status"] == "open" and action["occurrences"] == []
    assert action["practice_href"] == f"/interviews/{iv}/retry/{imp['practice']['retry_index']}"
    after = client.get(f"/api/v1/interviews/{iv}/review", headers=h).json()["improvements"][0]
    assert {k: v for k, v in after.items() if k != "action_id"} == {
        k: v for k, v in imp.items() if k != "action_id"
    }
    assert after["action_id"] == action["id"]


def test_two_accepts_at_the_same_moment_make_one_action(client, monkeypatch):
    h = nurse(client)
    iv, imp = improvement(client, h)
    first = accept(client, h, iv, imp["key"]).json()
    # The second request's "is it there yet?" ran before the first committed: it inserts, the
    # uniqueness check refuses it, and it answers with the first one's action.
    real = actions_service.Actions._existing
    calls = {"n": 0}

    def late(self, interview_id, key):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(self, interview_id, key)

    monkeypatch.setattr(actions_service.Actions, "_existing", late)
    second = accept(client, h, iv, imp["key"])
    assert second.status_code == 200 and second.json()["id"] == first["id"]
    assert len(client.get(BASE, headers=h).json()) == 1


def test_a_suggestion_not_in_the_review_and_an_unfinished_interview_are_refused(client):
    h = nurse(client)
    iv, _ = improvement(client, h)
    assert accept(client, h, iv, "point:Something never suggested").status_code == 404
    running = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()["id"]
    assert accept(client, h, running, "unanswered").status_code == 409


def test_rescheduling_moves_one_occurrence_with_one_calendar_event(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"]).json()
    put = client.post(
        f"{BASE}/{action['id']}/occurrences",
        headers=h,
        json={"on_date": "2026-11-20", "client_request_id": "occ-once-1"},
    )
    assert put.status_code == 200, put.text
    [occ] = put.json()["occurrences"]
    # A one-off is scheduled once: the second goes to the existing occurrence instead.
    again = client.post(f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-21"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_scheduled"
    # The same request sent again (its reply was lost) is answered with what it made.
    replay = client.post(
        f"{BASE}/{action['id']}/occurrences",
        headers=h,
        json={"on_date": "2026-11-20", "client_request_id": "occ-once-1"},
    )
    assert replay.status_code == 200 and [o["id"] for o in replay.json()["occurrences"]] == [occ["id"]]
    for day in ("2026-11-22", "2026-11-24"):
        moved = client.patch(
            f"/api/v1/me/schedule/{occ['id']}", headers=h, json={"on_date": day, "all_day": True}
        )
        assert moved.status_code == 200, moved.text
    now = client.get(f"{BASE}/{action['id']}", headers=h).json()
    assert [(o["id"], o["on_date"], o["sequence"]) for o in now["occurrences"]] == [
        (occ["id"], "2026-11-24", 2)
    ]
    assert now["id"] == action["id"] and len(client.get(BASE, headers=h).json()) == 1
    ics = client.get("/api/v1/me/schedule/export.ics", headers=h, params={"ids": occ["id"]})
    assert ics.status_code == 200, ics.text
    assert ics.text.count("BEGIN:VEVENT") == 1 and "SEQUENCE:2" in ics.text
    # The calendar file escapes commas and semicolons in text (RFC 5545), so compare escaped.
    assert f"CodeCoach: {escape(imp['title'])}" in ics.text.replace("\r\n ", "")
    # A title with commas (some improvements have one, e.g. "Follows up, documents and prevents a
    # repeat"): the same event, renamed, escaped (CI run 310 drew one).
    renamed = client.patch(
        f"{BASE}/{action['id']}",
        headers=h,
        json={"title": "Follows up, documents and prevents a repeat", "expected_revision": now["revision"]},
    )
    assert renamed.status_code == 200, renamed.text
    ics = client.get("/api/v1/me/schedule/export.ics", headers=h, params={"ids": occ["id"]}).text
    assert "CodeCoach: Follows up\\, documents and prevents a repeat" in ics.replace("\r\n ", "")


def test_a_weekly_action_is_done_one_occurrence_at_a_time_and_undo_restores_it(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"], recurrence="weekly").json()
    made = client.post(
        f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-16", "weeks": 3}
    ).json()
    occ = made["occurrences"]
    assert [o["on_date"] for o in occ] == ["2026-11-16", "2026-11-23", "2026-11-30"]
    assert len({o["id"] for o in occ}) == 3
    done = client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/complete", headers=h).json()
    assert [o["completed_at"] is not None for o in done["occurrences"]] == [True, False, False]
    assert done["status"] == "open"  # a weekly action isn't "done" because one week was
    # Saying the whole weekly action is done isn't how it works: one occurrence at a time.
    whole = client.post(f"{BASE}/{action['id']}/complete", headers=h)
    assert whole.status_code == 409 and whole.json()["error"]["code"] == "weekly_action"
    undone = client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/reopen", headers=h).json()
    assert [o["completed_at"] for o in undone["occurrences"]] == [None, None, None]
    # The schedule says the same about each occurrence.
    client.post(f"{BASE}/{action['id']}/occurrences/{occ[1]['id']}/complete", headers=h)
    entries = client.get(
        "/api/v1/me/schedule", headers=h, params={"from": "2026-11-15", "to": "2026-12-01"}
    ).json()
    mine = {e["id"]: e for e in entries if e["kind"] == "accepted_action"}
    assert [mine[o["id"]]["done_at"] is not None for o in occ] == [False, True, False]
    assert all(mine[o["id"]]["title"] == imp["title"] for o in occ)


def test_a_one_off_done_anywhere_is_done_everywhere_and_a_rename_shows_everywhere(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"]).json()
    occ = client.post(f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-20"}).json()[
        "occurrences"
    ][0]
    _, _, kit = event(client, h)
    saved = client.put(
        kit,
        headers=h,
        json={
            "checklist": [{"id": "act-1", "origin": "action", "action_id": action["id"], "text": "ignored"}]
        },
    )
    assert saved.status_code == 200, saved.text
    item = saved.json()["checklist"][0]
    assert (
        item["text"] == imp["title"]
        and item["action"]["done"] is False
        and item["action"]["occurrences_total"] == 1
    )
    # Done from the schedule's occurrence: the action, the kit and the schedule all say so.
    client.post(f"{BASE}/{action['id']}/occurrences/{occ['id']}/complete", headers=h)
    assert client.get(f"{BASE}/{action['id']}", headers=h).json()["status"] == "done"
    item = client.get(kit, headers=h).json()["checklist"][0]
    assert item["done"] and item["action"]["done"] and item["action"]["occurrences_done"] == 1
    entry = client.get(f"/api/v1/me/schedule/{occ['id']}", headers=h).json()
    assert entry["done_at"] is not None
    # Reopened from the plan: open everywhere again.
    client.post(f"{BASE}/{action['id']}/reopen", headers=h)
    assert client.get(kit, headers=h).json()["checklist"][0]["done"] is False
    assert client.get(f"/api/v1/me/schedule/{occ['id']}", headers=h).json()["done_at"] is None
    # Renamed once: the kit item and the schedule entry read the new title (nothing was copied).
    cur = client.get(f"{BASE}/{action['id']}", headers=h).json()
    client.patch(
        f"{BASE}/{action['id']}",
        headers=h,
        json={"title": "Close every answer with the outcome", "expected_revision": cur["revision"]},
    )
    assert client.get(kit, headers=h).json()["checklist"][0]["text"] == "Close every answer with the outcome"
    assert (
        client.get(f"/api/v1/me/schedule/{occ['id']}", headers=h).json()["title"]
        == "Close every answer with the outcome"
    )


def test_a_stale_edit_is_refused_with_both_versions_and_a_lost_reply_reads_as_saved(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"]).json()
    rev = action["revision"]
    first = client.patch(
        f"{BASE}/{action['id']}",
        headers=h,
        json={"notes": "Use STAR.", "expected_revision": rev, "client_request_id": "act-edit-1"},
    )
    assert first.status_code == 200 and first.json()["revision"] == rev + 1
    # The same save sent again (its reply was lost): it went through, not a conflict.
    replay = client.patch(
        f"{BASE}/{action['id']}",
        headers=h,
        json={"notes": "Use STAR.", "expected_revision": rev, "client_request_id": "act-edit-1"},
    )
    assert replay.status_code == 200 and replay.json()["save_replay"]["accepted_revision"] == rev + 1
    # Another tab still on the old revision: refused, with the saved action to compare.
    stale = client.patch(
        f"{BASE}/{action['id']}", headers=h, json={"notes": "Older tab's words", "expected_revision": rev}
    )
    assert stale.status_code == 409
    err = stale.json()["error"]
    assert err["code"] == "stale_revision" and err["details"]["current"]["notes"] == "Use STAR."
    assert client.get(f"{BASE}/{action['id']}", headers=h).json()["notes"] == "Use STAR."


def test_an_action_says_what_it_came_from_when_the_interview_is_gone(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"]).json()
    with client.app.state.session_factory() as db:
        db.execute(delete(PracticeSession).where(PracticeSession.id == iv))
        db.commit()
    after = client.get(f"{BASE}/{action['id']}", headers=h).json()
    assert after["source"]["available"] is False
    assert (
        after["source"]["label"] == imp["title"]
        and after["source"]["interview_title"] == "Registered Nurse interview"
    )


def test_another_accounts_actions_occurrences_and_interviews_are_not_found(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"], recurrence="weekly").json()
    occ = client.post(
        f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-16", "weeks": 2}
    ).json()["occurrences"][0]
    bea = nurse(client, "bea@example.com")
    aid, oid = action["id"], occ["id"]
    for method, path, body in (
        ("get", f"{BASE}/{aid}", None),
        ("patch", f"{BASE}/{aid}", {"title": "Mine now", "expected_revision": action["revision"]}),
        ("post", f"{BASE}/{aid}/complete", None),
        ("post", f"{BASE}/{aid}/reopen", None),
        ("post", f"{BASE}/{aid}/occurrences", {"on_date": "2026-12-01"}),
        ("post", f"{BASE}/{aid}/occurrences/{oid}/complete", None),
        ("post", f"{BASE}/{aid}/occurrences/{oid}/reopen", None),
        ("patch", f"/api/v1/me/schedule/{oid}", {"on_date": "2026-12-02", "all_day": True}),
    ):
        r = getattr(client, method)(path, headers=bea, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code)
        assert action["title"] not in r.text
    assert accept(client, bea, iv, imp["key"]).status_code == 404
    assert client.get(BASE, headers=bea).json() == []
    # Her own kit can't hold Ada's action either.
    _, _, kit = event(client, bea)
    r = client.put(kit, headers=bea, json={"checklist": [{"id": "x", "origin": "action", "action_id": aid}]})
    assert r.status_code == 404
    # And Ada's own occurrence id under another of her actions is not that action's.
    _, imp2 = improvement(client, h)
    other = client.get(f"/api/v1/interviews/{iv}/review", headers=h).json()["improvements"]
    if len(other) > 1:
        second = accept(client, h, iv, other[1]["key"]).json()
        assert client.post(f"{BASE}/{second['id']}/occurrences/{oid}/complete", headers=h).status_code == 404
    assert imp2


def test_actions_are_exported_linked_and_counted(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"], recurrence="weekly").json()
    client.post(f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-16", "weeks": 2})
    doc = client.get("/api/v1/me/export", headers=h).json()
    [exported] = doc["accepted_actions"]
    assert exported["title"] == imp["title"] and exported["source"]["improvement"] == imp["title"]
    assert exported["recurrence"] == "weekly" and len(exported["occurrences"]) == 2
    v2 = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    [a2] = v2["accepted_actions"]
    assert all(link["state"] == "present" for link in a2["links"]["occurrences"])
    kinds = {
        e["links"]["activity"]["state"] for e in v2["schedule"]["entries"] if e["kind"] == "accepted_action"
    }
    assert kinds == {"present"}
    counts = {
        c["key"]: c["count"] for c in client.get("/api/v1/me/data-summary", headers=h).json()["categories"]
    }
    assert counts["accepted_actions"] == 1


def test_accepted_actions_go_with_the_account(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    accept(client, h, iv, imp["key"])
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code in (200, 204), gone.text
    with client.app.state.session_factory() as db:
        assert db.query(AcceptedAction).count() == 0


def test_once_or_weekly_can_change_only_before_anything_is_scheduled_or_done(client):
    h = nurse(client)
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"]).json()
    weekly = client.patch(
        f"{BASE}/{action['id']}",
        headers=h,
        json={"recurrence": "weekly", "expected_revision": action["revision"]},
    )
    assert weekly.status_code == 200 and weekly.json()["recurrence"] == "weekly"
    client.post(f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-16", "weeks": 2})
    cur = client.get(f"{BASE}/{action['id']}", headers=h).json()
    back = client.patch(
        f"{BASE}/{action['id']}", headers=h, json={"recurrence": "once", "expected_revision": cur["revision"]}
    )
    assert back.status_code == 409 and back.json()["error"]["code"] == "has_occurrences"
    assert client.get(f"{BASE}/{action['id']}", headers=h).json()["recurrence"] == "weekly"

"""Archiving and deleting an accepted improvement, previewed (Volume 14, prompt 5;
docs/ACCEPTED_ACTIONS.md, "Archive and delete"; docs/LIFECYCLE.md), and bringing one back from a
version 2 backup by id. Each listed effect happens; a scope changed after the preview is refused; a
retry answers with what was done; another account's improvement is not found. Synthetic data only."""

from sqlalchemy import func, select

from app.models import AcceptedAction, ScheduleEntry
from tests.test_actions import BASE, accept
from tests.test_kits import nurse
from tests.test_packet_plans import a_kit, weekly_action
from tests.test_restore import apply

SCHEDULE = "/api/v1/me/schedule"


def preview(client, h, action_id, kind="archive"):
    r = client.get(f"{BASE}/{action_id}/{kind}-preview", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def carry_out(client, h, action_id, impact, kind="archive", key=None):
    body = {"expected_fingerprint": impact["fingerprint"]} | ({"client_request_id": key} if key else {})
    return client.post(f"{BASE}/{action_id}/{kind}", headers=h, json=body)


def week(client, h):
    return client.get(SCHEDULE, headers=h, params={"from": "2026-11-15", "to": "2026-11-30"}).json()


def kit_item(client, h, kit):
    a, ev = kit
    kit = client.get(f"/api/v1/me/applications/{a['id']}/events/{ev['id']}/kit", headers=h).json()
    return next(c for c in kit["checklist"] if c["origin"] == "action")


def test_the_archive_preview_lists_occurrences_kits_and_the_suggestion(client):
    h = nurse(client)
    action, occ = weekly_action(client, h, weeks=2)
    client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/complete", headers=h)
    a_kit(client, h, action_id=action["id"])
    p = preview(client, h, action["id"])
    kinds = [(e["effect"], e["kind"]) for e in p["effects"]]
    assert kinds[0] == ("archived", "accepted improvement")
    occurrences = [e for e in p["effects"] if e["kind"] == "occurrence"]
    assert [e["title"] for e in occurrences] == ["2026-11-16 (done)", "2026-11-23 (not done yet)"]
    assert all(e["effect"] == "kept" and "Marks of done are kept" in e["note"] for e in occurrences)
    [kit] = [e for e in p["effects"] if e["kind"] == "kit checklist item"]
    assert kit["effect"] == "kept" and kit["note"] == "Stays, labelled archived."
    [suggestion] = [e for e in p["effects"] if e["kind"] == "suggestion"]
    assert suggestion["note"] == "The interview's review still shows it as accepted."


def test_archiving_takes_it_off_the_plan_and_schedule_and_unarchiving_brings_it_back(client):
    h = nurse(client)
    action, occ = weekly_action(client, h, weeks=2)
    client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/complete", headers=h)
    ev = a_kit(client, h, action_id=action["id"])
    assert len(week(client, h)) == 2
    r = carry_out(client, h, action["id"], preview(client, h, action["id"]))
    assert r.status_code == 200, r.text
    got = client.get(f"{BASE}/{action['id']}", headers=h).json()
    assert got["archived_at"] is not None
    assert week(client, h) == []  # off the schedule and Today
    # Kept: its occurrences with their marks of done, and its place on the kit, labelled.
    assert [o["completed_at"] is not None for o in got["occurrences"]] == [True, False]
    item = kit_item(client, h, ev)
    assert item["action"]["archived"] is True and item["text"] == action["title"]
    # It can't be scheduled while archived.
    more = client.post(
        f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-12-01", "weeks": 1}
    )
    assert more.status_code == 409 and more.json()["error"]["code"] == "action_archived"
    # Unarchive: back, with its occurrences as they were.
    back = client.post(f"{BASE}/{action['id']}/unarchive", headers=h)
    assert back.status_code == 200 and back.json()["archived_at"] is None
    assert len(week(client, h)) == 2
    assert [o["completed_at"] is not None for o in back.json()["occurrences"]] == [True, False]
    assert kit_item(client, h, ev)["action"]["archived"] is False


def test_deleting_removes_its_occurrences_keeps_the_kit_item_and_frees_the_suggestion(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=2)
    ev = a_kit(client, h, action_id=action["id"])
    p = preview(client, h, action["id"], "delete")
    assert [
        (e["effect"], e["kind"]) for e in p["effects"] if e["kind"] in ("occurrence", "kit checklist item")
    ] == [
        ("deleted", "occurrence"),
        ("deleted", "occurrence"),
        ("kept", "kit checklist item"),
    ]
    assert "backups CodeCoach made earlier keep a copy until they age out" in p["notes"][0]
    r = carry_out(client, h, action["id"], p, "delete")
    assert r.status_code == 200, r.text
    assert client.get(f"{BASE}/{action['id']}", headers=h).status_code == 404
    assert week(client, h) == []
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ScheduleEntry)) == 0
    assert kit_item(client, h, ev)["text"] == "An improvement you removed"
    # The suggestion can be accepted again, as a new improvement.
    iv, key = action["source"]["interview_id"], action["source"]["key"]
    review = client.get(f"/api/v1/interviews/{iv}/review", headers=h).json()
    assert next(i for i in review["improvements"] if i["key"] == key)["action_id"] is None
    again = accept(client, h, iv, key)
    assert again.status_code == 201 and again.json()["id"] != action["id"]


def test_a_scope_changed_after_the_preview_is_refused_with_the_new_one(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=1)
    p = preview(client, h, action["id"], "delete")
    client.post(f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-30", "weeks": 1})
    r = carry_out(client, h, action["id"], p, "delete")
    assert r.status_code == 409 and r.json()["error"]["code"] == "impact_changed"
    current = r.json()["error"]["details"]["current"]
    assert len([e for e in current["effects"] if e["kind"] == "occurrence"]) == 2
    assert client.get(f"{BASE}/{action['id']}", headers=h).status_code == 200  # nothing done


def test_a_retry_answers_with_what_was_done(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=1)
    p = preview(client, h, action["id"], "delete")
    first = carry_out(client, h, action["id"], p, "delete", key="delete-action-0001")
    again = carry_out(client, h, action["id"], p, "delete", key="delete-action-0001")
    assert first.status_code == again.status_code == 200
    assert again.json()["replayed"] is True and again.json()["fingerprint"] == p["fingerprint"]


def test_another_accounts_improvement_is_not_found(client):
    owner = nurse(client, "owner@example.com")
    action, _ = weekly_action(client, owner, weeks=1)
    other = nurse(client, "other@example.com")
    for kind in ("archive", "delete"):
        assert client.get(f"{BASE}/{action['id']}/{kind}-preview", headers=other).status_code == 404
        r = client.post(
            f"{BASE}/{action['id']}/{kind}", headers=other, json={"expected_fingerprint": "0" * 32}
        )
        assert r.status_code == 404
    assert client.post(f"{BASE}/{action['id']}/unarchive", headers=other).status_code == 404
    assert client.get(f"{BASE}/{action['id']}", headers=owner).status_code == 200


def test_a_version_2_backup_brings_a_deleted_improvement_back_with_the_same_ids(client):
    h = nurse(client)
    action, occ = weekly_action(client, h, weeks=2)
    client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/complete", headers=h)
    ev = a_kit(client, h, action_id=action["id"])
    raw = client.get("/api/v1/me/export", headers=h, params={"version": 2}).content
    assert (
        carry_out(client, h, action["id"], preview(client, h, action["id"], "delete"), "delete").status_code
        == 200
    )
    assert kit_item(client, h, ev)["text"] == "An improvement you removed"

    r = apply(client, h, raw, ["accepted_actions"])
    assert r.status_code in (200, 201), r.text
    assert r.json()["counts"]["accepted_actions"]["added"] == 1
    back = client.get(f"{BASE}/{action['id']}", headers=h).json()  # the same id
    assert back["title"] == action["title"] and back["recurrence"] == "weekly"
    assert [o["id"] for o in back["occurrences"]] == [o["id"] for o in occ]  # the same ids
    assert [o["completed_at"] is not None for o in back["occurrences"]] == [True, False]
    assert kit_item(client, h, ev)["text"] == action["title"]  # the kit names it again
    # The same file again: it's already there.
    again = apply(client, h, raw, ["accepted_actions"])
    assert again.json()["counts"]["accepted_actions"]["added"] == 1  # the first batch, answered again
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AcceptedAction)) == 1


def test_restoring_an_improvement_already_there_or_from_elsewhere_adds_nothing(client):
    h = nurse(client)
    weekly_action(client, h, weeks=1)
    raw = client.get("/api/v1/me/export", headers=h, params={"version": 2}).content
    preview_body = client.post(
        "/api/v1/me/restore/preview", headers={**h, "Content-Type": "application/json"}, content=raw
    ).json()
    cat = next(c for c in preview_body["categories"] if c["key"] == "accepted_actions")
    assert (cat["found"], cat["new"], cat["duplicates"]) == (1, 0, 1)
    # Another account: its interview isn't there, so there's nothing to link it to.
    other = nurse(client, "fresh@example.com")
    body = client.post(
        "/api/v1/me/restore/preview", headers={**other, "Content-Type": "application/json"}, content=raw
    ).json()
    cat = next(c for c in body["categories"] if c["key"] == "accepted_actions")
    assert cat["new"] == 0 and cat["skipped"] == [
        {"reason": "Its interview isn't in this account, so there's nothing to link it to", "count": 1}
    ]
    # A version 1 file has no ids, so it can't bring improvements back.
    v1 = client.get("/api/v1/me/export", headers=h).content
    body = client.post(
        "/api/v1/me/restore/preview", headers={**h, "Content-Type": "application/json"}, content=v1
    ).json()
    cat = next(c for c in body["categories"] if c["key"] == "accepted_actions")
    assert cat["skipped"][0]["reason"].startswith("Restored from a version 2 export only")


def test_undoing_the_restore_removes_what_it_added_if_unchanged(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=1)
    raw = client.get("/api/v1/me/export", headers=h, params={"version": 2}).content
    carry_out(client, h, action["id"], preview(client, h, action["id"], "delete"), "delete")
    batch = apply(client, h, raw, ["accepted_actions"]).json()
    assert client.get(f"{BASE}/{action['id']}", headers=h).status_code == 200
    r = client.post(f"/api/v1/me/restore/batches/{batch['id']}/remove", headers=h)
    assert r.status_code == 200, r.text
    assert client.get(f"{BASE}/{action['id']}", headers=h).status_code == 404
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ScheduleEntry)) == 0

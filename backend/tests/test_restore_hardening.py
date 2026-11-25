"""Restore hardening from the security pass of 2026-11-21 (docs/BACKUP_FORMAT.md): a backup file
whose accepted action or occurrence names an id another account already has restores with new ids
(the insert decides, not a read: under row-level security another account's row is invisible to a
read, and keeping the id used to fail the whole restore, saying the id exists); and an action's
practice link is kept only in a form the app makes itself (a retry of its own interview, or a
coding problem), so a crafted file can't put another site or a `javascript:` URL behind the
button. Synthetic accounts only; on PostgreSQL this runs with row-level security on."""

from __future__ import annotations

import json

import pytest

from tests.conftest import auth_headers, register
from tests.test_actions import improvement
from tests.test_requirement_versions import accepted_action_for, create

NURSE = "registered-nurse"
P = "/api/v1/me/restore"


def nurse(client, email):
    return auth_headers(register(client, email=email, display_name=email.split("@")[0], career_track=NURSE))


def restore(client, h, doc):
    return client.post(
        P,
        headers={**h, "Content-Type": "application/json"},
        params={"categories": ["accepted_actions"]},
        content=json.dumps(doc).encode(),
    )


def action_file(interview, key, *, action_id=None, practice=None, occurrence_id=None):
    item = {
        "id": action_id or "aaaaaaaa-0000-4000-8000-000000000001",
        "title": "Practise the handoff",
        "recurrence": "weekly",
        "source": {"kind": "interview_improvement", "interview": interview, "key": key, "improvement": "x"},
    }
    if practice is not None:
        item["practice"] = practice
    if occurrence_id:
        item["occurrences"] = [{"schedule_entry": occurrence_id, "date": "2026-12-04"}]
    return {"export_version": 2, "accepted_actions": [item]}


def test_ids_another_account_has_are_given_new_ones_and_the_restore_succeeds(client):
    ada, bea = nurse(client, "ada@example.com"), nurse(client, "bea@example.com")
    _, _, theirs, _ = accepted_action_for(client, ada, create(client, ada))
    their_occurrence = client.post(
        f"/api/v1/me/actions/{theirs['id']}/occurrences", headers=ada, json={"on_date": "2026-12-02"}
    ).json()["occurrences"][0]["id"]
    interview, imp = improvement(client, bea)
    r = restore(
        client,
        bea,
        action_file(interview, imp["key"], action_id=theirs["id"], occurrence_id=their_occurrence),
    )
    assert r.status_code == 201, r.text
    [mine] = client.get("/api/v1/me/actions", headers=bea).json()
    assert mine["id"] != theirs["id"]
    occurrences = client.get(f"/api/v1/me/actions/{mine['id']}", headers=bea).json()["occurrences"]
    assert [o["id"] for o in occurrences] != [their_occurrence] and len(occurrences) == 1
    # Ada's action and its occurrence are as they were.
    again = client.get(f"/api/v1/me/actions/{theirs['id']}", headers=ada).json()
    assert again["title"] == theirs["title"] and [o["id"] for o in again["occurrences"]] == [their_occurrence]


def test_a_free_id_is_kept(client):
    bea = nurse(client, "bea@example.com")
    interview, imp = improvement(client, bea)
    free = "abcdef01-2345-4678-9abc-def012345678"
    assert restore(client, bea, action_file(interview, imp["key"], action_id=free)).status_code == 201
    assert [a["id"] for a in client.get("/api/v1/me/actions", headers=bea).json()] == [free]


@pytest.mark.parametrize(
    "practice",
    [
        "javascript:alert(document.domain)",
        "https://evil.example/login",
        "//evil.example",
        "/settings/restore",
        "/interviews/00000000-0000-4000-8000-000000000000/retry/0",  # not this action's interview
        "/problems/two-sum?next=https://evil.example",
    ],
)
def test_a_practice_link_the_app_wouldnt_make_is_dropped(client, practice):
    bea = nurse(client, "bea@example.com")
    interview, imp = improvement(client, bea)
    r = restore(client, bea, action_file(interview, imp["key"], practice=practice))
    assert r.status_code == 201, r.text
    [a] = client.get("/api/v1/me/actions", headers=bea).json()
    assert a["practice_href"] is None


@pytest.mark.parametrize("practice", ["/problems/two-sum", "/problems", "retry"])
def test_the_links_the_app_makes_are_kept(client, practice):
    bea = nurse(client, "bea@example.com")
    interview, imp = improvement(client, bea)
    link = f"/interviews/{interview}/retry/1" if practice == "retry" else practice
    assert restore(client, bea, action_file(interview, imp["key"], practice=link)).status_code == 201
    [a] = client.get("/api/v1/me/actions", headers=bea).json()
    assert a["practice_href"] == link

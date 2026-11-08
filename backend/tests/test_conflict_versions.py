"""A refused stale save says what it lost to: every 409 stale_revision carries the saved version
(`details.current`), so the page can show the learner's version and the saved one side by side and
let them choose, instead of "overwrite or discard" blind. Notes already did this (note_conflict).

Synthetic accounts only. One test per kind of record that has revision-checked saves."""

from __future__ import annotations

from tests.conftest import auth_headers, register


def conflict(r):
    assert r.status_code == 409, r.text
    error = r.json()["error"]
    assert error["code"] == "stale_revision"
    return error["details"]


def test_a_story(client):
    h = auth_headers(register(client))
    story = client.post("/api/v1/me/stories", headers=h, json={"title": "Original"}).json()
    newer = client.patch(
        f"/api/v1/me/stories/{story['id']}",
        headers=h,
        json={"expected_revision": 1, "title": "Saved elsewhere"},
    ).json()
    details = conflict(
        client.patch(
            f"/api/v1/me/stories/{story['id']}", headers=h, json={"expected_revision": 1, "title": "Mine"}
        )
    )
    assert details["current_revision"] == newer["revision"] == 2
    assert details["current"]["title"] == "Saved elsewhere" and details["current"]["revision"] == 2
    # Restoring an old version from a stale page is refused the same way.
    details = conflict(
        client.post(
            f"/api/v1/me/stories/{story['id']}/revisions/1/restore", headers=h, json={"expected_revision": 1}
        )
    )
    assert details["current"]["title"] == "Saved elsewhere"


def test_a_story_edited_on_the_target_page(client):
    h = auth_headers(register(client))
    target = client.post(
        "/api/v1/targets",
        headers=h,
        json={
            "title": "Backend engineer",
            "description": "Build APIs. Write tests.",
            "track": "software-engineer",
        },
    ).json()
    target = client.post(
        f"/api/v1/targets/{target['id']}/experience",
        headers=h,
        json={"title": "Migration", "requirement_ids": []},
    ).json()
    entry = target["experience"][0]
    client.patch(
        f"/api/v1/me/stories/{entry['id']}", headers=h, json={"expected_revision": 1, "title": "Newer"}
    )
    details = conflict(
        client.put(
            f"/api/v1/targets/{target['id']}/experience/{entry['id']}",
            headers=h,
            json={"title": "Older tab", "requirement_ids": [], "expected_revision": 1},
        )
    )
    assert details["current_revision"] == 2 and details["current"]["title"] == "Newer"


def test_a_whiteboard_draft(client):
    from tests.test_whiteboard import DIAGRAM, P

    h = auth_headers(register(client))
    url = f"/api/v1/me/whiteboard/{P}/draft"
    client.put(
        url, headers=h, json={"diagram": DIAGRAM, "explanation": "Saved elsewhere", "expected_revision": 0}
    )
    details = conflict(
        client.put(url, headers=h, json={"diagram": DIAGRAM, "explanation": "Mine", "expected_revision": 0})
    )
    assert details["current_revision"] == 1 and details["current"]["explanation"] == "Saved elsewhere"


def test_a_reflection(client):
    from tests.test_reflections import REFLECTION, event

    h = auth_headers(register(client, email="nurse@example.com"))
    _, _, url = event(client, h)
    client.put(url, headers=h, json={**REFLECTION, "follow_ups": "Saved elsewhere"})
    details = conflict(client.put(url, headers=h, json={**REFLECTION, "follow_ups": "Mine"}))
    assert details["current_revision"] == 1 and details["current"]["follow_ups"] == "Saved elsewhere"


def test_another_account_never_sees_the_saved_version(client):
    owner = auth_headers(register(client, email="owner@example.com"))
    other = auth_headers(register(client, email="other@example.com"))
    story = client.post("/api/v1/me/stories", headers=owner, json={"title": "Private"}).json()
    r = client.patch(
        f"/api/v1/me/stories/{story['id']}", headers=other, json={"expected_revision": 1, "title": "x"}
    )
    assert r.status_code == 404 and "Private" not in r.text  # ownership is checked before the revision

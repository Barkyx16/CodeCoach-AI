"""Account export version 2: the version 1 data plus ids and typed links between records, opt-in.
Synthetic accounts only. Restore still reads only version 1 and refuses version 2 before writing."""

import copy
import json

from sqlalchemy import func, select

from app.cli import main as cli
from app.models import Note
from app.services.export_v2 import validate_export
from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"
NURSE = "registered-nurse"
Q = f"{NURSE}/m-pressure-0"
JD = "Registered Nurse, Medical Ward. Responsibilities: assess and prioritise patient care. 12-hour shifts."


def nurse(client, email):
    return auth_headers(register(client, email=email, career_track=NURSE))


def linked_account(client, h):
    """A target, three stories (one deleted later), an application with two interviews, a kit, a
    reflection with an accepted note (then binned) and a saved question, and two schedule entries."""
    t = client.post("/api/v1/targets", headers=h, json={"title": "Ward nurse", "description": JD}).json()
    s1 = client.post("/api/v1/me/stories", headers=h, json={"title": "Two call lights"}).json()
    s2 = client.post("/api/v1/me/stories", headers=h, json={"title": "Night handover"}).json()
    s3 = client.post("/api/v1/me/stories", headers=h, json={"title": "Family meeting"}).json()
    a = client.post(
        APPS,
        headers=h,
        json={
            "employer": "Synthetic Hospital",
            "role_title": "Ward nurse",
            "stage": "interviewing",
            "target_id": t["id"],
            "story_ids": [s1["id"], s3["id"]],
        },
    ).json()
    ev1 = client.post(
        f"{APPS}/{a['id']}/events",
        headers=h,
        json={"title": "Panel", "on_date": "2026-11-12", "local_time": "10:00", "timezone": "Europe/London"},
    ).json()["events"][0]
    ev2 = client.post(f"{APPS}/{a['id']}/events", headers=h, json={"title": "Second round"}).json()
    ev2 = next(e for e in ev2["events"] if e["title"] == "Second round")
    kit_url = f"{APPS}/{a['id']}/events/{ev1['id']}/kit"
    client.put(kit_url, headers=h, json={"story_ids": [s1["id"], s2["id"]], "expected_revision": 0})
    r_url = f"{APPS}/{a['id']}/events/{ev1['id']}/reflection"
    client.put(
        r_url,
        headers=h,
        json={
            "topics": ["patient assessment"],
            "follow_ups": "Send references",
            "story_ids": [s1["id"]],
            "expected_revision": 0,
        },
    )
    steps = client.post(f"{r_url}/suggestions", headers=h).json()["actions"]
    note_step = next(x for x in steps if x["kind"] == "note")
    practice = next(x for x in steps if x["kind"] == "practice")
    accepted = client.post(
        f"{r_url}/actions/{note_step['id']}/accept", headers=h, json={"target": "notebook"}
    )
    note_id = next(x for x in accepted.json()["actions"] if x["id"] == note_step["id"])["applied_ref"]
    client.post(f"{r_url}/actions/{practice['id']}/accept", headers=h, json={"target": "saved"})
    client.delete(f"/api/v1/me/notes/{note_id}", headers=h)  # in the bin: not in the file
    client.delete(f"/api/v1/me/stories/{s3['id']}", headers=h)  # deleted: a missing link
    prep = client.post(
        "/api/v1/me/schedule",
        headers=h,
        json={"kind": "application_event", "ref": ev1["id"], "on_date": "2026-11-11", "all_day": True},
    ).json()
    q = client.post(
        "/api/v1/me/schedule",
        headers=h,
        json={"kind": "question", "ref": Q, "on_date": "2026-11-10", "all_day": True},
    ).json()
    return {
        "target": t,
        "stories": (s1, s2, s3),
        "app": a,
        "events": (ev1, ev2),
        "note": note_id,
        "prep": prep,
        "q": q,
        "steps": (note_step, practice),
    }


def test_version_1_stays_the_default_and_unchanged(client):
    h = nurse(client, "v1@example.com")
    linked_account(client, h)
    r = client.get("/api/v1/me/export", headers=h)
    assert r.headers["content-disposition"] == 'attachment; filename="codecoach-data.json"'
    v1 = r.json()
    assert v1["export_version"] == 1 and "identities" not in v1
    app = v1["applications"][0]
    assert "id" not in app and "links" not in app and "id" not in app["events"][0]
    assert isinstance(app["target"], str) and isinstance(app["stories"], list)  # the version 1 fields


def test_version_2_links_records_and_says_what_each_link_points_to(client):
    h = nurse(client, "v2@example.com")
    x = linked_account(client, h)
    r = client.get("/api/v1/me/export", headers=h, params={"version": 2})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"] == 'attachment; filename="codecoach-data-v2.json"'
    doc = r.json()
    assert doc["export_version"] == 2 and doc["identities"]["restore"].startswith("not supported")
    s1, s2, s3 = x["stories"]
    ev1, ev2 = x["events"]

    app = doc["applications"][0]
    # Every version 1 field is still there, unchanged; ids and links are added.
    assert app["target"] == x["target"]["id"] and app["stories"] == [s1["id"], s3["id"]]
    assert app["id"] == x["app"]["id"] and [e["id"] for e in app["events"]] == [ev1["id"], ev2["id"]]
    assert app["links"]["target"] == {"type": "target", "id": x["target"]["id"], "state": "present"}
    assert [(s["id"], s["state"]) for s in app["links"]["stories"]] == [
        (s1["id"], "present"),
        (s3["id"], "missing"),
    ]

    kit = doc["interview_kits"][0]
    assert kit["links"]["event"] == {"type": "application_event", "id": ev1["id"], "state": "present"}
    assert [(s["id"], s["state"], s["version_when_chosen"]) for s in kit["links"]["stories"]] == [
        (s1["id"], "present", 1),
        (s2["id"], "present", 1),
    ]

    refl = doc["interview_reflections"][0]
    assert refl["links"]["application"]["state"] == refl["links"]["event"]["state"] == "present"
    by_step = {a["id"]: a for a in refl["actions"]}
    note_step, practice = x["steps"]
    # The accepted note was binned since: the link is kept as history, marked missing, not recreated.
    assert by_step[note_step["id"]]["links"]["created"] == {
        "type": "note",
        "id": x["note"],
        "state": "missing",
    }
    assert by_step[practice["id"]]["links"]["created"]["type"] == "bookmark"
    assert by_step[practice["id"]]["links"]["created"]["state"] == "present"
    assert x["note"] not in {n["id"] for n in doc["notes"]}

    entries = {e["id"]: e for e in doc["schedule"]["entries"]}
    assert entries[x["prep"]["id"]]["links"]["activity"] == {
        "type": "application_event",
        "id": ev1["id"],
        "state": "present",
    }
    assert entries[x["q"]["id"]]["links"]["activity"] == {"type": "question", "id": Q, "state": "public"}

    assert validate_export(doc) == []


def test_another_accounts_records_never_appear_or_resolve(client):
    a = nurse(client, "owner@example.com")
    b = nurse(client, "other@example.com")
    linked_account(client, a)
    theirs = linked_account(client, b)
    text = json.dumps(client.get("/api/v1/me/export", headers=a, params={"version": 2}).json())
    for ident in (
        theirs["app"]["id"],
        theirs["target"]["id"],
        theirs["events"][0]["id"],
        theirs["prep"]["id"],
        *(s["id"] for s in theirs["stories"]),
    ):
        assert ident not in text


def test_no_keys_tokens_or_credentials_in_either_version(client):
    h = nurse(client, "keys@example.com")
    linked_account(client, h)
    for params in ({}, {"version": 2}):
        text = client.get("/api/v1/me/export", headers=h, params=params).text
        for secret in (
            "client_request_id",
            "request_fingerprint",
            "password",
            "refresh_token",
            "access_token",
            "token_version",
        ):
            assert secret not in text, (params, secret)


def test_the_validator_finds_each_kind_of_broken_reference(client):
    h = nurse(client, "check@example.com")
    linked_account(client, h)
    good = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    assert validate_export(good) == []

    def broken(change):
        doc = copy.deepcopy(good)
        change(doc)
        return {i["rule"] for i in validate_export(doc)}

    story_id = good["stories"][0]["id"]
    assert "duplicate_id" in broken(lambda d: d["stories"].append(copy.deepcopy(d["stories"][0])))
    assert "missing_id" in broken(lambda d: d["notes"].append({"title": "no id"}))
    # A link that says "present" for an id that's a different kind of record.
    assert "wrong_type" in broken(
        lambda d: d["applications"][0]["links"].update(
            target={"type": "target", "id": story_id, "state": "present"}
        )
    )
    assert "dangling" in broken(
        lambda d: d["applications"][0]["links"].update(
            target={"type": "target", "id": "nope", "state": "present"}
        )
    )
    # A link that says its target isn't in the file, though it is.
    assert "inconsistent_state" in broken(
        lambda d: d["applications"][0]["links"]["stories"].append(
            {"type": "story", "id": story_id, "state": "missing"}
        )
    )
    assert "unknown_type" in broken(
        lambda d: d["applications"][0]["links"].update(
            target={"type": "employer", "id": "x", "state": "present"}
        )
    )
    assert "unknown_state" in broken(
        lambda d: d["applications"][0]["links"].update(target={"type": "target", "id": "x", "state": "maybe"})
    )
    assert "malformed_link" in broken(lambda d: d["applications"][0]["links"].update(target="not-an-object"))
    assert {i["rule"] for i in validate_export({**good, "export_version": 1})} == {"not_version_2"}


def test_restore_refuses_version_2_before_writing_anything(client):
    h = nurse(client, "restore@example.com")
    linked_account(client, h)
    raw = client.get("/api/v1/me/export", headers=h, params={"version": 2}).content
    with client.app.state.session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Note))
    for path, params in (("/api/v1/me/restore/preview", {}), ("/api/v1/me/restore", {"categories": "notes"})):
        r = client.post(path, headers={**h, "Content-Type": "application/json"}, params=params, content=raw)
        assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_version"
        assert "version 2" in r.json()["error"]["message"] and r.json()["error"]["details"] == {
            "supported": [1]
        }
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Note)) == before
    # Version 1 is still read.
    v1 = client.get("/api/v1/me/export", headers=h).content
    ok = client.post(
        "/api/v1/me/restore/preview", headers={**h, "Content-Type": "application/json"}, content=v1
    )
    assert ok.status_code == 200


def test_the_cli_check_is_read_only_and_reports_problems(client, tmp_path, capsys):
    h = nurse(client, "cli@example.com")
    linked_account(client, h)
    doc = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(doc))
    doc["applications"][0]["links"]["target"]["id"] = "not-here"
    bad.write_text(json.dumps(doc))
    assert cli(["cli", "check-export", str(good)]) == 0
    assert cli(["cli", "check-export", str(bad)]) == 1
    assert "dangling" in capsys.readouterr().out

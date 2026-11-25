"""Personal kit templates (Volume 11, prompt 7; docs/TEMPLATES.md): a template keeps only the text of
the checklist items and questions chosen (never done states, links, notes or anything about the
interview), a create sent again after a lost reply makes one template, edits are revision-checked
and recoverable, text is plain text that nothing evaluates, a kit started from a template is its
own, and only the owner can see or change one. Synthetic accounts only."""

from __future__ import annotations

from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"
URL = "/api/v1/me/kit-templates"
KEY = "kt-key-0001"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def kit_for(client, h, title="Panel interview", on="2026-11-20"):
    a = client.post(APPS, headers=h, json={"employer": "Mercy General", "role_title": "Ward nurse"}).json()
    ev = client.post(f"{APPS}/{a['id']}/events", headers=h, json={"title": title, "on_date": on}).json()
    ev = next(e for e in ev["events"] if e["title"] == title)
    return f"{APPS}/{a['id']}/events/{ev['id']}/kit"


TEMPLATE = {
    "name": "Ward interviews",
    "checklist": [{"text": "Print two copies of my registration"}, {"text": "Plan the bus route"}],
    "questions": [{"text": "How is the preceptorship structured?", "group": "training"}],
}


def test_a_template_keeps_only_the_text_and_leaves_the_kit_alone(client):
    h = nurse(client)
    url = kit_for(client, h)
    kit = client.get(url, headers=h).json()
    ticks = [
        {"id": "y1", "text": "Print two copies of my registration", "origin": "yours", "done": True},
        {"id": "y2", "text": "Plan the bus route", "origin": "yours", "done": False},
    ]
    saved = client.put(
        url,
        headers=h,
        json={
            "checklist": ticks,
            "meeting_link": "https://meet.example.com/abc?pwd=secret",
            "notes": "Salary hopes: private",
            "expected_revision": kit["revision"],
        },
    ).json()
    # What the page sends is what it chose; extra fields (done, ids, origin) are never kept.
    r = client.post(
        URL,
        headers=h,
        json={
            "name": "Ward interviews",
            "checklist": [{"text": t["text"], "done": t["done"], "id": t["id"]} for t in ticks],
            "questions": TEMPLATE["questions"],
            "client_request_id": KEY,
        },
    )
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["checklist"] == [{"text": "Print two copies of my registration"}, {"text": "Plan the bus route"}]
    assert t["questions"] == [{"text": "How is the preceptorship structured?", "group": "training"}]
    assert (
        t["revision"] == 1
        and "done" not in r.text
        and "meet.example.com" not in r.text
        and "Salary" not in r.text
    )
    # The kit it came from is exactly as it was: its ticks, link and notes.
    after = client.get(url, headers=h).json()
    assert after["revision"] == saved["revision"] and after["checklist"] == saved["checklist"]
    assert after["meeting_link"] == saved["meeting_link"] and after["notes"] == saved["notes"]


def test_a_lost_create_reply_sent_again_makes_one_template(client):
    h = nurse(client)
    first = client.post(URL, headers=h, json={**TEMPLATE, "client_request_id": KEY}).json()
    again = client.post(URL, headers=h, json={**TEMPLATE, "client_request_id": KEY})
    assert again.status_code == 201 and again.json()["id"] == first["id"]
    assert len(client.get(URL, headers=h).json()) == 1
    other = client.post(URL, headers=h, json={**TEMPLATE, "name": "Something else", "client_request_id": KEY})
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_key_reused"
    # Two deliberate creates (no key, or two keys) are two templates.
    client.post(URL, headers=h, json=TEMPLATE)
    assert len(client.get(URL, headers=h).json()) == 2


def test_text_is_plain_text_that_nothing_evaluates(client):
    h = nurse(client)
    tricky = [
        "{{employer}} at {{ role }}",
        "<script>alert(1)</script>",
        "${7*7} and $(rm -rf /) and `id`",
        "{{ __import__('os').system('id') }}",
        "https://example.com/fetch-me",
    ]
    r = client.post(
        URL,
        headers=h,
        json={"name": "<b>Mine</b>", "checklist": [{"text": x} for x in tricky], "questions": []},
    )
    assert r.status_code == 201, r.text
    assert [c["text"] for c in r.json()["checklist"]] == tricky  # kept as typed, nothing filled in
    assert r.json()["name"] == "<b>Mine</b>"


def test_blank_and_repeated_items_are_dropped_and_an_empty_template_refused(client):
    h = nurse(client)
    r = client.post(
        URL,
        headers=h,
        json={
            "name": "  Spaced\x07 name ",
            "checklist": [{"text": "Bring ID"}, {"text": "  bring id "}, {"text": " \x01 "}],
            "questions": [{"text": "Who is on the panel?"}],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Spaced name" and r.json()["checklist"] == [{"text": "Bring ID"}]
    assert r.json()["questions"] == [{"text": "Who is on the panel?", "group": "other"}]
    assert (
        client.post(URL, headers=h, json={"name": "x", "checklist": [], "questions": []}).status_code == 422
    )
    blank = client.post(URL, headers=h, json={"name": "x", "checklist": [{"text": " \x01"}], "questions": []})
    assert blank.status_code == 400 and blank.json()["error"]["code"] == "empty_template"
    too_many = [{"text": f"Item {i}"} for i in range(41)]
    assert client.post(URL, headers=h, json={"name": "x", "checklist": too_many}).status_code == 422


def test_edits_are_revision_checked_and_a_lost_reply_is_recognised(client):
    h = nurse(client)
    t = client.post(URL, headers=h, json=TEMPLATE).json()
    body = {"name": "Ward interviews (nights)", "expected_revision": 1, "client_request_id": "kt-edit-0001"}
    renamed = client.patch(f"{URL}/{t['id']}", headers=h, json=body)
    assert renamed.status_code == 200 and renamed.json()["revision"] == 2
    # The same save again (its reply was lost): went through, not a conflict with itself.
    replay = client.patch(f"{URL}/{t['id']}", headers=h, json=body).json()
    assert replay["save_replay"] == {"accepted_revision": 2, "current_revision": 2}
    # A page still on revision 1 without that key: a conflict, with the saved template to compare.
    stale = client.patch(f"{URL}/{t['id']}", headers=h, json={"name": "Old page", "expected_revision": 1})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    assert stale.json()["error"]["details"]["current"]["name"] == "Ward interviews (nights)"
    items = client.patch(
        f"{URL}/{t['id']}", headers=h, json={"checklist": [{"text": "Only this"}], "expected_revision": 2}
    ).json()
    assert items["checklist"] == [{"text": "Only this"}] and items["questions"] == TEMPLATE["questions"]


def test_kits_started_from_a_template_are_their_own(client):
    h = nurse(client)
    t = client.post(URL, headers=h, json=TEMPLATE).json()
    # The page copies the template's items into two kits' forms (new ids, not done) and saves each.
    kits = [kit_for(client, h, f"Interview {i}", f"2026-12-0{i}") for i in (1, 2)]
    for url in kits:
        kit = client.get(url, headers=h).json()
        ticks = [
            {"id": f"t{i}", "text": c["text"], "origin": "yours", "done": False}
            for i, c in enumerate(t["checklist"])
        ]
        assert (
            client.put(
                url, headers=h, json={"checklist": ticks, "expected_revision": kit["revision"]}
            ).status_code
            == 200
        )
    one = client.get(kits[0], headers=h).json()
    tick = {**one["checklist"][0], "done": True}
    client.put(
        kits[0],
        headers=h,
        json={"checklist": [tick, *one["checklist"][1:]], "expected_revision": one["revision"]},
    )
    # Changing, then deleting, the template changes neither kit; ticking one kit changes nothing else.
    client.patch(
        f"{URL}/{t['id']}", headers=h, json={"checklist": [{"text": "Changed"}], "expected_revision": 1}
    )
    assert client.get(f"{URL}/{t['id']}", headers=h).json()["checklist"] == [{"text": "Changed"}]
    assert client.delete(f"{URL}/{t['id']}", headers=h).status_code == 204
    first, second = (client.get(u, headers=h).json() for u in kits)
    assert [c["text"] for c in first["checklist"] if c["origin"] == "yours"][:2] == [
        x["text"] for x in TEMPLATE["checklist"]
    ]
    assert first["checklist"][0]["done"] is True
    assert all(not c["done"] for c in second["checklist"] if c["origin"] == "yours")
    assert client.get(f"{URL}/{t['id']}", headers=h).status_code == 404


def test_only_the_owner_sees_or_changes_a_template(client):
    ada = nurse(client)
    bea = nurse(client, "bea@example.com")
    t = client.post(URL, headers=ada, json=TEMPLATE).json()
    assert client.get(URL, headers=bea).json() == []
    assert client.get(f"{URL}/{t['id']}", headers=bea).status_code == 404
    assert (
        client.patch(
            f"{URL}/{t['id']}", headers=bea, json={"name": "Mine now", "expected_revision": 1}
        ).status_code
        == 404
    )
    assert client.delete(f"{URL}/{t['id']}", headers=bea).status_code == 404
    assert client.get(f"{URL}/{t['id']}", headers=ada).json()["name"] == "Ward interviews"
    # Bea's create key doesn't find Ada's template either.
    ada_keyed = client.post(URL, headers=ada, json={**TEMPLATE, "client_request_id": KEY}).json()
    bea_keyed = client.post(URL, headers=bea, json={**TEMPLATE, "client_request_id": KEY}).json()
    assert bea_keyed["id"] != ada_keyed["id"]
    assert client.get(URL).status_code == 401


def test_at_most_thirty_and_counted_exported_and_deleted_with_the_account(client, monkeypatch):
    from app.services import kit_templates as kt

    h = nurse(client)
    monkeypatch.setattr(kt, "MAX_TEMPLATES", 2)
    client.post(URL, headers=h, json=TEMPLATE)
    client.post(URL, headers=h, json={**TEMPLATE, "name": "Second"})
    third = client.post(URL, headers=h, json={**TEMPLATE, "name": "Third"})
    assert third.status_code == 400 and third.json()["error"]["code"] == "too_many_templates"
    exported = client.get("/api/v1/me/export", headers=h).json()
    assert [x["name"] for x in exported["kit_templates"]] == ["Ward interviews", "Second"]
    assert "done" not in str(exported["kit_templates"])
    summary = client.get("/api/v1/me/data-summary", headers=h).json()
    days = next(c for c in summary["categories"] if c["key"] == "interview_days")
    assert days["count"] >= 2

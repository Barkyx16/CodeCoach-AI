"""Kit templates come back from a backup file (Volume 20, prompt 7; docs/TEMPLATES.md,
docs/BACKUP_FORMAT.md). A template is the learner's own checklist and questions and links to nothing
by id, so a restore brings it back, previewed and undoable like every other category. Each is checked
as saving one is (the same schema and cleaning), so a file can't make a template the page couldn't;
one over a limit is listed as not restored, with the limit. "The same" as one already here is the
same name, checklist and questions, in the same order, after that cleaning: it isn't added twice.
Each starts at revision 1; its history and times aren't carried. Lines keep their order and groups.
No kit is made from one; existing templates are never changed; the undo takes away only those still
as added, and kits made from one keep their content. Version 1 and 2 files alike. Synthetic data only."""

from __future__ import annotations

import json

from sqlalchemy import select

from app.models import InterviewKit, KitTemplate, User
from app.schemas.kit_templates import MAX_TEMPLATE_ITEMS
from app.services.kit_templates import MAX_TEMPLATES
from app.services.restore import NOT_RESTORED, NOTES
from tests.test_kit_templates import URL as TEMPLATES
from tests.test_kit_templates import kit_for
from tests.test_listed_names import listing
from tests.test_packet import packet
from tests.test_restore import P, apply, backup, nurse, preview

CAT = ["kit_templates"]
PANEL = {
    "name": "Panel day",
    "checklist": [{"text": "Bring my ID badge"}, {"text": "Print the job posting"}],
    "questions": [
        {"text": "How is the team's handover done?", "group": "team"},
        {"text": "What does success look like in six months?", "group": "role"},
        {"text": "What happens in the first week?", "group": "next_steps"},
    ],
}
PHONE = {"name": "Phone screen", "checklist": [{"text": "Charge the phone"}], "questions": []}


def make(client, h, body):
    r = client.post(TEMPLATES, headers=h, json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def mine(client, email) -> list[KitTemplate]:
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        out = list(
            db.scalars(select(KitTemplate).where(KitTemplate.user_id == uid).order_by(KitTemplate.name))
        )
        db.expunge_all()
        return out


def category(body):
    return next(c for c in body["categories"] if c["key"] == "kit_templates")


def a_file(client, version=1) -> bytes:
    """Ada saves two templates and edits one twice, so the file carries revision 3."""
    a = nurse(client)
    made = make(client, a, PANEL)
    for rev in (1, 2):
        r = client.patch(
            f"{TEMPLATES}/{made['id']}", headers=a, json={"name": "Panel day", "expected_revision": rev}
        )
        assert r.status_code == 200, r.text
    make(client, a, PHONE)
    if version == 1:
        return backup(client, a)
    return json.dumps(client.get("/api/v1/me/export", params={"version": 2}, headers=a).json()).encode()


def edited(raw: bytes, change) -> bytes:
    doc = json.loads(raw)
    change(doc["kit_templates"])
    return json.dumps(doc).encode()


def test_the_preview_offers_the_templates_and_says_what_comes_back(client):
    raw = a_file(client)
    b = nurse(client, email="bea@example.com")
    body = preview(client, b, raw).json()
    cat = category(body)
    assert (cat["found"], cat["new"], cat["duplicates"], cat["skipped"]) == (2, 2, 0, [])
    assert sorted(cat["samples"]) == ["Panel day", "Phone screen"]
    assert cat["note"] == NOTES["kit_templates"] and "revision 1" in cat["note"] and "No kit" in cat["note"]
    assert "kit_templates" not in NOT_RESTORED
    assert not [u for u in body["not_restored"] if u["key"] == "kit_templates"]


def test_applying_makes_each_at_revision_1_in_the_files_order_and_groups(client):
    raw = a_file(client)
    b = nurse(client, email="bea@example.com")
    r = apply(client, b, raw, CAT)
    assert r.status_code in (200, 201), r.text
    assert r.json()["counts"]["kit_templates"] == {"added": 2, "duplicates": 0, "skipped": 0}
    panel, phone = mine(client, "bea@example.com")
    assert (panel.name, panel.revision, phone.name, phone.revision) == ("Panel day", 1, "Phone screen", 1)
    assert panel.checklist == PANEL["checklist"] and panel.questions == PANEL["questions"]
    # No kit is made, and the page reads it as one it saved.
    with client.app.state.session_factory() as db:
        assert db.scalars(select(InterviewKit)).all() == []
    got = client.get(f"{TEMPLATES}/{panel.id}", headers=b).json()
    assert [q["group"] for q in got["questions"]] == ["team", "role", "next_steps"]


def test_the_same_template_isnt_added_twice_and_an_existing_one_is_never_changed(client):
    raw = a_file(client)
    b = nurse(client, email="bea@example.com")
    here = make(client, b, PANEL)  # the same name, checklist and questions, in the same order
    # The same items under another name, or in another order, are other templates.
    cat = category(preview(client, b, raw).json())
    assert (cat["new"], cat["duplicates"]) == (1, 1)
    apply(client, b, raw, CAT)
    names = [t.name for t in mine(client, "bea@example.com")]
    assert names == ["Panel day", "Phone screen"]
    kept = client.get(f"{TEMPLATES}/{here['id']}", headers=b).json()
    assert kept["revision"] == here["revision"] and kept["updated_at"] == here["updated_at"]
    # The same file again adds nothing.
    assert category(preview(client, b, raw).json())["new"] == 0
    reordered = edited(raw, lambda ts: ts[0]["questions"].reverse())
    assert category(preview(client, b, reordered).json())["new"] == 1


def test_a_file_is_checked_as_saving_one_is(client):
    raw = a_file(client)
    b = nurse(client, email="bea@example.com")

    def tamper(ts):
        ts[0]["questions"].append({"text": "x" * 301, "group": "team"})  # longer than the form allows
        ts[1]["checklist"] = [{"text": f"Item {i}"} for i in range(MAX_TEMPLATE_ITEMS + 1)]
        ts.append({"name": "   ", "checklist": [{"text": "Only spaces for a name"}], "questions": []})
        ts.append({"name": "Nothing in it", "checklist": [{"text": "  \x07 "}], "questions": []})
        ts.append({"name": "Odd group", "checklist": [], "questions": [{"text": "Hi?", "group": "secret"}]})
        ts.append({"name": "Cleaned", "checklist": [{"text": " Bring \x00water "}, {"text": "bring water"}]})

    cat = category(preview(client, b, edited(raw, tamper)).json())
    assert {s["reason"]: s["count"] for s in cat["skipped"]} == {
        "A question longer than 300 characters": 1,
        f"More than {MAX_TEMPLATE_ITEMS} checklist items": 1,
        "No name": 1,
        "No checklist item or question": 1,
        "Malformed": 1,
    }
    assert cat["new"] == 1
    apply(client, b, edited(raw, tamper), CAT)
    [only] = mine(client, "bea@example.com")
    assert (only.name, only.checklist) == ("Cleaned", [{"text": "Bring water"}])  # as saving cleans it


def test_over_the_accounts_limit_the_rest_are_listed_with_the_limit(client):
    raw = a_file(client)
    b = nurse(client, email="bea@example.com")
    for i in range(MAX_TEMPLATES - 1):
        make(client, b, {"name": f"Mine {i}", "checklist": [{"text": f"Item {i}"}], "questions": []})
    cat = category(preview(client, b, raw).json())
    assert cat["new"] == 1
    assert cat["skipped"] == [{"reason": f"Over the limit of {MAX_TEMPLATES} kit templates", "count": 1}]
    apply(client, b, raw, CAT)
    assert len(mine(client, "bea@example.com")) == MAX_TEMPLATES


def test_a_version_2_file_is_read_too(client):
    raw = a_file(client, version=2)
    b = nurse(client, email="bea@example.com")
    assert category(preview(client, b, raw).json())["new"] == 2
    apply(client, b, raw, CAT)
    assert len(mine(client, "bea@example.com")) == 2


def test_another_accounts_templates_are_never_touched(client):
    raw = a_file(client)
    before = [(t.id, t.revision, t.name) for t in mine(client, "ada@example.com")]
    b = nurse(client, email="bea@example.com")
    batch = apply(client, b, raw, CAT).json()
    assert client.post(f"{P}/batches/{batch['id']}/remove", headers=b).json()["removal"]["removed"] == 2
    assert [(t.id, t.revision, t.name) for t in mine(client, "ada@example.com")] == before


def test_the_undo_removes_what_it_added_keeps_one_changed_since_and_kits_keep_theirs(client):
    raw = a_file(client)
    b = nurse(client, email="bea@example.com")
    batch = apply(client, b, raw, CAT).json()
    panel, phone = mine(client, "bea@example.com")
    # A kit started from the restored template: the page copies its items into the kit's form.
    url = kit_for(client, b)
    put = client.put(
        url,
        headers=b,
        json={
            "checklist": [{"id": "c1", "text": panel.checklist[0]["text"], "origin": "yours"}],
            "questions": [
                {"id": "q1", "text": panel.questions[0]["text"], "group": "team", "origin": "yours"}
            ],
        },
    )
    assert put.status_code == 200, put.text
    renamed = client.patch(
        f"{TEMPLATES}/{phone.id}", headers=b, json={"name": "Phone call", "expected_revision": 1}
    )
    assert renamed.status_code == 200, renamed.text
    out = client.post(f"{P}/batches/{batch['id']}/remove", headers=b).json()
    assert out["removal"] == {"removed": 1, "kept_edited": 1, "already_gone": 0}
    assert [t.name for t in mine(client, "bea@example.com")] == ["Phone call"]
    kit = client.get(url, headers=b).json()
    assert [c["text"] for c in kit["checklist"]] == ["Bring my ID badge"]
    assert [q["text"] for q in kit["questions"]] == ["How is the team's handover done?"]


def test_names_you_listed_are_still_kept_out_of_what_leaves_the_app(client):
    raw = edited(
        a_file(client),
        lambda ts: ts[0]["questions"].append({"text": "Ask Priya Raman about nights", "group": "team"}),
    )
    b = nurse(client, email="bea@example.com")
    listing(client, b, "Priya Raman")
    apply(client, b, raw, CAT)
    panel = next(t for t in mine(client, "bea@example.com") if t.name == "Panel day")
    assert panel.questions[-1]["text"] == "Ask Priya Raman about nights"  # your own copy keeps it
    url = kit_for(client, b)
    put = client.put(
        url,
        headers=b,
        json={
            "checklist": [],
            "questions": [
                {"id": "q1", "text": panel.questions[-1]["text"], "group": "team", "origin": "yours"}
            ],
        },
    )
    assert put.status_code == 200, put.text
    event_id = url.rstrip("/").split("/")[-2]
    got = packet(client, b, [{"type": "kit", "id": event_id}]).json()
    text = json.dumps(got["items"])
    assert "Priya" not in text and "Ask [name] about nights" in text


def test_a_failure_part_way_adds_no_template(client, monkeypatch):
    from app.services import restore as rs

    raw = a_file(client)
    b = nurse(client, email="bea@example.com")
    real = rs.Restore._add_kit_templates
    calls = []

    def second_fails(self, item):
        calls.append(item["name"])
        if len(calls) == 2:
            raise RuntimeError("synthetic failure")
        return real(self, item)

    monkeypatch.setattr(rs.Restore, "_add_kit_templates", second_fails)
    r = apply(client, b, raw, CAT)
    assert r.json()["error"]["code"] == "restore_failed"
    assert mine(client, "bea@example.com") == []  # the first one made is rolled back with the rest

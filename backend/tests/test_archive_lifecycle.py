"""Archive as a presentation lifecycle (Volume 11, prompt 4; docs/ARCHIVE.md): an offer comparison
leaves the active list and comes back with the same id, revision, document and links; asking twice
is safe; an archive never overwrites a save made elsewhere; another account can't archive or
restore it; deleting stays deletion; the export says which are archived; "Continue your work" and
search leave archived records out (search only unless asked); an application's stage and its
story links survive archiving. Synthetic accounts only."""

from __future__ import annotations

from .conftest import auth_headers, register
from .test_offer_comparisons import MINE, doc, new, offer, put

APPS = "/api/v1/me/applications"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def ids(client, h, archived=False):
    r = client.get(MINE, headers=h, params={"archived": archived})
    assert r.status_code == 200, r.text
    return [c["id"] for c in r.json()]


def test_an_archived_comparison_leaves_the_list_and_comes_back_unchanged(client):
    h = nurse(client)
    app = client.post(
        APPS, headers=h, json={"employer": "Northfield", "role_title": "Ward nurse", "stage": "offer"}
    ).json()
    c = new(client, h, title="Two offers")
    saved = put(
        client,
        h,
        c,
        doc(offer("a", application_id=app["id"], currency="GBP", pay_amount=30000, pay_period="year")),
    ).json()
    assert saved["revision"] == 2 and saved["archived"] is False

    r = client.post(f"{MINE}/{c['id']}/archive", headers=h)
    assert r.status_code == 200, r.text
    archived = r.json()
    assert archived["archived"] is True
    assert (archived["id"], archived["revision"], archived["doc"], archived["applications"]) == (
        saved["id"],
        saved["revision"],
        saved["doc"],
        saved["applications"],
    )  # nothing but the flag
    assert archived["updated_at"] == saved["updated_at"]  # not a save
    assert ids(client, h) == [] and ids(client, h, archived=True) == [c["id"]]
    assert client.get(f"{MINE}/{c['id']}", headers=h).json()["archived"] is True  # still opens

    again = client.post(f"{MINE}/{c['id']}/archive", headers=h)  # asking twice is the same
    assert again.status_code == 200 and again.json() == archived

    back = client.post(f"{MINE}/{c['id']}/unarchive", headers=h).json()
    assert back["archived"] is False and back["doc"] == saved["doc"] and back["revision"] == saved["revision"]
    assert ids(client, h) == [c["id"]] and ids(client, h, archived=True) == []
    assert client.get(f"{APPS}/{app['id']}", headers=h).json()["stage"] == "offer"  # the link changed nothing


def test_an_archive_never_overwrites_a_save_made_elsewhere(client):
    h = nurse(client)
    c = new(client, h, title="Mine")
    # Device A opened revision 1; device B archives; A's save still goes through and stays archived.
    assert client.post(f"{MINE}/{c['id']}/archive", headers=h).status_code == 200
    r = put(client, h, c, doc(offer("a", currency="GBP", pay_amount=1, pay_period="year")))
    assert r.status_code == 200, r.text
    assert (r.json()["revision"], r.json()["archived"]) == (2, True)
    # Device B, holding revision 1, restores: the flag changes, A's revision 2 is kept.
    back = client.post(f"{MINE}/{c['id']}/unarchive", headers=h).json()
    assert (back["revision"], back["doc"]["offers"][0]["pay_amount"]) == (2, 1)
    # A stale save is still refused as before: archiving didn't loosen the revision check.
    assert put(client, h, c, doc(), base=1).status_code == 409


def test_only_the_owner_can_archive_or_restore_and_deletion_stays_deletion(client):
    ada = nurse(client)
    bea = nurse(client, "bea@example.com")
    c = new(client, ada, title="Ada's")
    for action in ("archive", "unarchive"):
        assert client.post(f"{MINE}/{c['id']}/{action}", headers=bea).status_code == 404
    assert client.post(f"{MINE}/{c['id']}/archive").status_code == 401
    assert ids(client, ada) == [c["id"]]  # untouched
    assert ids(client, bea, archived=True) == []

    assert client.post(f"{MINE}/{c['id']}/archive", headers=ada).status_code == 200
    assert client.delete(f"{MINE}/{c['id']}", headers=ada).status_code == 204
    assert ids(client, ada, archived=True) == []  # deleted is gone, not archived
    assert client.post(f"{MINE}/{c['id']}/unarchive", headers=ada).status_code == 404  # no revival


def test_the_export_says_which_comparisons_are_archived(client):
    h = nurse(client)
    kept = new(client, h, title="Active one")
    shelved = new(client, h, title="Archived one")
    client.post(f"{MINE}/{shelved['id']}/archive", headers=h)
    exported = client.get("/api/v1/me/export", headers=h).json()["offer_comparisons"]
    assert {e["title"]: e["archived"] for e in exported} == {
        kept["doc"]["title"]: False,
        shelved["doc"]["title"]: True,
    }


def test_archived_records_leave_continue_your_work_and_come_back_when_restored(client):
    h = nurse(client)
    note = client.post("/api/v1/me/notes", headers=h, json={"title": "Sepsis signs", "body": "x"}).json()
    story = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": "Night shift", "situation": "s", "task": "t", "action": "a", "result": "r"},
    ).json()
    app = client.post(APPS, headers=h, json={"employer": "Northfield", "role_title": "Ward nurse"}).json()
    ev = client.post(
        f"{APPS}/{app['id']}/events", headers=h, json={"title": "Panel", "on_date": "2026-12-15"}
    ).json()["events"][0]
    client.put(f"{APPS}/{app['id']}/events/{ev['id']}/kit", headers=h, json={"notes": "x"})
    comp = new(client, h, title="Offers")

    def listed():
        r = client.get("/api/v1/me/recent-work", headers=h, params={"limit": 12})
        assert r.status_code == 200, r.text
        return {i["type"] for i in r.json()["items"]}

    assert {"note", "story", "application", "kit", "offer_comparison"} <= listed()
    client.patch(f"/api/v1/me/notes/{note['id']}", headers=h, json={"archived": True})
    client.post(f"/api/v1/me/stories/{story['id']}/archive", headers=h)
    client.post(f"{APPS}/{app['id']}/archive", headers=h)
    client.post(f"{MINE}/{comp['id']}/archive", headers=h)
    assert (
        listed() & {"note", "story", "application", "kit", "offer_comparison"} == set()
    )  # the kit went with its application

    client.post(f"{APPS}/{app['id']}/unarchive", headers=h)
    client.post(f"{MINE}/{comp['id']}/unarchive", headers=h)
    assert {"application", "kit", "offer_comparison"} <= listed()


def test_an_archived_application_keeps_its_stage_and_an_archived_story_stays_linked(client):
    h = nurse(client)
    story = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": "Night shift", "situation": "s", "task": "t", "action": "a", "result": "r"},
    ).json()
    app = client.post(
        APPS, headers=h, json={"employer": "Northfield", "role_title": "Ward nurse", "stage": "interviewing"}
    ).json()
    ev = client.post(
        f"{APPS}/{app['id']}/events", headers=h, json={"title": "Panel", "on_date": "2026-12-15"}
    ).json()["events"][0]
    kit_url = f"{APPS}/{app['id']}/events/{ev['id']}/kit"
    assert client.put(kit_url, headers=h, json={"story_ids": [story["id"]]}).status_code == 200

    client.post(f"/api/v1/me/stories/{story['id']}/archive", headers=h)
    kit = client.get(kit_url, headers=h).json()
    linked = [s for s in kit["stories"] if s["id"] == story["id"]]
    assert linked and linked[0]["archived"] is True  # still linked, labelled

    archived_app = client.post(f"{APPS}/{app['id']}/archive", headers=h).json()
    assert (archived_app["stage"], archived_app["archived"]) == ("interviewing", True)  # not a business stage
    restored = client.post(f"{APPS}/{app['id']}/unarchive", headers=h).json()
    assert restored["id"] == app["id"] and restored["stage"] == "interviewing"
    assert [e["id"] for e in restored["events"]] == [ev["id"]]  # the same events, not copies

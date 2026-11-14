"""Where a story is used, and linking stories to applications one at a time (Volume 11, prompt 6;
docs/BACKLINKS.md). The story page lists your applications, interview kits and reflections that
point at the story: titles and dates only, your own records only, one level, at most 20 of each with
a count of all; renamed, archived and deleted records show as they are now. Linking and unlinking
an application's stories is per story and repeat-safe, both ends must be yours, and a page showing
an older list can't undo a link made elsewhere. Synthetic accounts only."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from tests.conftest import auth_headers, register

APPS = "/api/v1/me/applications"
STORIES = "/api/v1/me/stories"
NOTE = "Private: the charge nurse's name and my salary hopes"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def story(client, h, title="Two call lights at once"):
    r = client.post(STORIES, headers=h, json={"title": title, "situation": "A busy night shift on the ward"})
    assert r.status_code == 201, r.text
    return r.json()


def application(client, h, employer="Mercy General", role="Ward nurse"):
    r = client.post(APPS, headers=h, json={"employer": employer, "role_title": role, "notes": NOTE})
    assert r.status_code == 201, r.text
    return r.json()


def event(client, h, a, title="Panel interview", on="2026-11-20"):
    r = client.post(f"{APPS}/{a['id']}/events", headers=h, json={"title": title, "on_date": on})
    return next(e for e in r.json()["events"] if e["title"] == title)


def link(client, h, a, s):
    return client.put(f"{APPS}/{a['id']}/stories/{s['id']}", headers=h)


def unlink(client, h, a, sid):
    return client.delete(f"{APPS}/{a['id']}/stories/{sid}", headers=h)


def used_in(client, h, s):
    return client.get(f"{STORIES}/{s['id']}/used-in", headers=h)


def test_a_story_lists_the_applications_kits_and_reflections_that_use_it(client):
    h = nurse(client)
    s = story(client, h)
    other = story(client, h, "Night handover")
    a = application(client, h)
    b = application(client, h, "St Mary's", "Charge nurse")
    assert link(client, h, a, s).status_code == 200
    link(client, h, b, other)  # uses another story only
    ev = event(client, h, a)
    kit = client.put(
        f"{APPS}/{a['id']}/events/{ev['id']}/kit", headers=h, json={"story_ids": [s["id"]], "notes": NOTE}
    )
    assert kit.status_code == 200, kit.text
    refl = client.put(
        f"{APPS}/{a['id']}/events/{ev['id']}/reflection",
        headers=h,
        json={"story_ids": [s["id"]], "clear": NOTE, "expected_revision": 0},
    )
    assert refl.status_code == 200, refl.text

    r = used_in(client, h, s)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["applications"] == [
        {
            "id": a["id"],
            "role_title": "Ward nurse",
            "employer": "Mercy General",
            "stage": "saved",
            "archived": False,
        }
    ]
    assert body["kits"] == [
        {
            "application_id": a["id"],
            "event_id": ev["id"],
            "event_title": "Panel interview",
            "event_on": "2026-11-20",
            "role_title": "Ward nurse",
            "employer": "Mercy General",
            "application_archived": False,
        }
    ]
    assert [x["event_id"] for x in body["reflections"]] == [ev["id"]]
    assert (body["applications_total"], body["kits_total"], body["reflections_total"], body["limit"]) == (
        1,
        1,
        1,
        20,
    )
    # Titles and dates only: nothing private from the records or the story is copied in.
    assert "salary" not in r.text and "busy night" not in r.text
    # One level: the other story's application isn't reached through anything.
    assert b["id"] not in r.text
    assert [x["id"] for x in used_in(client, h, other).json()["applications"]] == [b["id"]]


def test_renamed_archived_and_deleted_records_show_as_they_are_now(client):
    h = nurse(client)
    s = story(client, h)
    a = application(client, h)
    link(client, h, a, s)
    ev = event(client, h, a)
    client.put(f"{APPS}/{a['id']}/events/{ev['id']}/kit", headers=h, json={"story_ids": [s["id"]]})
    client.put(
        f"{APPS}/{a['id']}/events/{ev['id']}/reflection",
        headers=h,
        json={"story_ids": [s["id"]], "expected_revision": 0},
    )
    # Renaming the application changes the label, not the link; the reflection keeps what it recorded.
    client.patch(f"{APPS}/{a['id']}", headers=h, json={"role_title": "Senior ward nurse"})
    client.post(f"{APPS}/{a['id']}/archive", headers=h)
    body = used_in(client, h, s).json()
    assert (
        body["applications"][0]["role_title"] == "Senior ward nurse" and body["applications"][0]["archived"]
    )
    assert body["kits"][0]["role_title"] == "Senior ward nurse" and body["kits"][0]["application_archived"]
    assert body["reflections"][0]["role_title"] == "Ward nurse"  # as recorded at the time
    # Renaming or archiving the story keeps every link.
    renamed = client.patch(
        f"{STORIES}/{s['id']}",
        headers=h,
        json={"title": "Two call lights, renamed", "expected_revision": s["revision"]},
    )
    assert renamed.status_code == 200, renamed.text
    client.post(f"{STORIES}/{s['id']}/archive", headers=h)
    app = client.get(f"{APPS}/{a['id']}", headers=h).json()
    assert app["stories"] == [{"id": s["id"], "title": "Two call lights, renamed", "archived": True}]
    assert used_in(client, h, s).json()["applications_total"] == 1
    # Deleting the application takes its kit and reflection with it: nothing is left pointing.
    client.delete(f"{APPS}/{a['id']}", headers=h)
    body = used_in(client, h, s).json()
    assert (body["applications_total"], body["kits_total"], body["reflections_total"]) == (0, 0, 0)


def test_a_deleted_story_has_no_page_and_can_still_be_unlinked(client):
    h = nurse(client)
    s = story(client, h)
    a = application(client, h)
    link(client, h, a, s)
    client.delete(f"{STORIES}/{s['id']}", headers=h)
    assert used_in(client, h, s).status_code == 404
    assert client.get(f"{APPS}/{a['id']}", headers=h).json()["stories"] == []  # drops out, isn't revived
    r = unlink(client, h, a, s["id"])  # the id left behind can be taken out
    assert r.status_code == 200 and r.json()["stories"] == []
    assert link(client, h, a, s).status_code == 404  # and can't be linked again


def test_only_your_own_records_are_listed_or_linked(client):
    ada = nurse(client)
    bea = nurse(client, "bea@example.com")
    mine = story(client, ada)
    theirs = story(client, bea, "Bea's story")
    adas = application(client, ada)
    beas = application(client, bea, "Bea's employer")
    link(client, bea, beas, theirs)
    # Another account's story: not found, whoever's application it would go on.
    assert used_in(client, ada, theirs).status_code == 404
    assert link(client, ada, adas, theirs).status_code == 404
    assert link(client, bea, beas, mine).status_code == 404
    # Another account's application: not found, linking or unlinking.
    assert link(client, ada, beas, mine).status_code == 404
    assert unlink(client, ada, beas, theirs["id"]).status_code == 404
    assert client.get(f"{APPS}/{beas['id']}", headers=bea).json()["stories"][0]["id"] == theirs["id"]
    # Nothing of Bea's is counted on Ada's story, even a record of hers that holds Ada's story id
    # (the API never lets it, but older or restored data could): and neither request works signed out.
    from app.models import Application

    with client.app.state.session_factory() as db:
        db.get(Application, beas["id"]).story_ids = [theirs["id"], mine["id"]]
        db.commit()
    link(client, ada, adas, mine)
    body = used_in(client, ada, mine).json()
    assert body["applications_total"] == 1 and "Bea" not in str(body)
    assert client.get(f"{STORIES}/{mine['id']}/used-in").status_code == 401
    assert client.put(f"{APPS}/{adas['id']}/stories/{mine['id']}").status_code == 401


def test_linking_is_per_story_and_repeat_safe(client):
    h = nurse(client)
    s1, s2 = story(client, h, "First"), story(client, h, "Second")
    a = application(client, h)
    first = link(client, h, a, s1).json()
    again = link(client, h, a, s1).json()  # a lost reply, sent again
    assert [x["id"] for x in again["stories"]] == [s1["id"]] and again["updated_at"] == first["updated_at"]
    # A page still showing the list from before links the second story: the first stays linked
    # (a whole-list save from that page would have sent only what it showed).
    assert [x["id"] for x in link(client, h, a, s2).json()["stories"]] == [s1["id"], s2["id"]]
    # Unlinking twice, or a story that was never linked, changes nothing more.
    assert [x["id"] for x in unlink(client, h, a, s1["id"]).json()["stories"]] == [s2["id"]]
    assert [x["id"] for x in unlink(client, h, a, s1["id"]).json()["stories"]] == [s2["id"]]
    assert unlink(client, h, a, "never-linked").status_code == 200
    # Unlinking leaves the story itself alone.
    assert client.get(f"{STORIES}/{s1['id']}", headers=h).json()["title"] == "First"


def test_an_application_links_at_most_twenty_stories(client):
    h = nurse(client)
    a = application(client, h)
    stories = [story(client, h, f"Story {i}") for i in range(21)]
    for s in stories[:20]:
        assert link(client, h, a, s).status_code == 200
    r = link(client, h, a, stories[20])
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_stories"
    assert "up to 20 stories" in r.json()["error"]["message"]
    assert link(client, h, a, stories[0]).status_code == 200  # one already linked is still fine


def test_the_lists_are_bounded_with_a_count_of_all(client):
    h = nurse(client)
    s = story(client, h)
    apps = [application(client, h, f"Employer {i}") for i in range(23)]
    for a in apps:
        link(client, h, a, s)
    body = used_in(client, h, s).json()
    assert len(body["applications"]) == 20 and body["applications_total"] == 23
    # Newest first: the one linked last was changed last.
    assert body["applications"][0]["id"] == apps[-1]["id"]


def test_two_links_at_once_both_stay(client):
    h = nurse(client)
    a = application(client, h)
    stories = [story(client, h, f"Story {i}") for i in range(4)]
    with ThreadPoolExecutor(4) as pool:
        replies = list(pool.map(lambda s: link(client, h, a, s), stories))
    assert all(r.status_code == 200 for r in replies), [r.text for r in replies]
    linked = {x["id"] for x in client.get(f"{APPS}/{a['id']}", headers=h).json()["stories"]}
    assert linked == {s["id"] for s in stories}


def test_an_older_application_with_no_list_at_all_can_link_and_unlink(client):
    from app.models import Application

    h = nurse(client)
    s = story(client, h)
    a = application(client, h)
    with client.app.state.session_factory() as db:
        db.get(Application, a["id"]).story_ids = None
        db.commit()
    assert [x["id"] for x in link(client, h, a, s).json()["stories"]] == [s["id"]]
    with client.app.state.session_factory() as db:
        db.get(Application, a["id"]).story_ids = None
        db.commit()
    assert unlink(client, h, a, s["id"]).json()["stories"] == []
    assert used_in(client, h, s).json()["applications_total"] == 0

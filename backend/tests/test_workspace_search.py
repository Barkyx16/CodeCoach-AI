"""Search your own saved work (Volume 11, prompt 3; docs/WORKSPACE_SEARCH.md): each kind found by
its own fields, every word required, archived only when asked, another account's matching text
invisible in results, counts and snippets, punctuation and LIKE wildcards matched literally, markup
returned as plain text, bounded input, one failing kind named, the words never in a URL or the
log, and a limit on how often. Synthetic accounts only."""

from __future__ import annotations

import logging

from app.services import workspace_search as ws

from .conftest import auth_headers, register

URL = "/api/v1/me/search"
APPS = "/api/v1/me/applications"


def acct(client, email):
    return auth_headers(register(client, email=email, career_track="registered-nurse"))


def find(client, h, q, **body):
    r = client.post(URL, headers=h, json={"q": q, **body})
    assert r.status_code == 200, r.text
    return r.json()


def seed(client, h, word="otter"):
    made = {}
    r = client.post(
        "/api/v1/me/notes",
        headers=h,
        json={
            "title": "Sepsis signs",
            "body": f"Watch for a rising lactate; the {word} mnemonic helps.",
            "tags": ["ward"],
        },
    )
    made["note"] = r.json()["id"]
    r = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={
            "title": f"Night shift {word}",
            "situation": "A busy ward",
            "task": "t",
            "action": "a",
            "result": "r",
        },
    )
    made["story"] = r.json()["id"]
    app = client.post(
        APPS, headers=h, json={"employer": f"{word.capitalize()} Health", "role_title": "Ward nurse"}
    ).json()
    made["application"] = app["id"]
    ev = client.post(
        f"{APPS}/{app['id']}/events", headers=h, json={"title": "Panel interview", "on_date": "2026-12-15"}
    )
    made["event"] = ev.json()["events"][0]["id"]
    assert (
        client.put(
            f"{APPS}/{app['id']}/events/{made['event']}/kit", headers=h, json={"notes": "x"}
        ).status_code
        == 200
    )
    return made


def test_each_kind_is_found_by_its_own_fields_and_every_word_counts(client):
    h = acct(client, "ada@example.com")
    made = seed(client, h)
    body = find(client, h, "otter")
    by_type = {i["type"]: i for i in body["items"]}
    assert set(by_type) == {"note", "story", "kit", "application"}
    assert body["counts"] == {"notes": 1, "stories": 1, "kits": 1, "applications": 1}
    note = by_type["note"]
    assert (note["id"], note["matched"]) == (made["note"], ["text"])
    assert "otter mnemonic" in note["snippet"]
    assert by_type["story"]["matched"] == ["title"] and by_type["story"]["id"] == made["story"]
    kit = by_type["kit"]
    assert (kit["id"], kit["parent_id"], kit["title"]) == (
        made["event"],
        made["application"],
        "Interview-day kit: Panel interview",
    )
    assert kit["detail"] == "Otter Health · on 2026-12-15"
    assert by_type["application"]["detail"] == "Stage: Saved"
    assert body["items"][0]["matched"] == ["title"]  # a title match ranks above a match in the text
    # Every word must appear: "otter lactate" is only in the note.
    assert [i["type"] for i in find(client, h, "otter lactate")["items"]] == ["note"]
    assert find(client, h, "otter zebra")["items"] == []
    # Tags are searched for notes; the kinds asked for are the only ones searched.
    assert [i["type"] for i in find(client, h, "ward", kinds=["notes"])["items"]] == ["note"]
    assert set(find(client, h, "otter", kinds=["stories", "kits"])["counts"]) == {"stories", "kits"}


def test_another_accounts_matching_text_is_invisible_in_results_counts_and_snippets(client):
    ada = acct(client, "ada@example.com")
    bea = acct(client, "bea@example.com")
    seed(client, ada, word="otter")
    seed(client, bea, word="otter")  # the same words, in another account
    client.post("/api/v1/me/notes", headers=bea, json={"title": "Bea only", "body": "otter BEA-PRIVATE-7781"})
    mine = find(client, ada, "otter")
    assert mine["counts"] == {"notes": 1, "stories": 1, "kits": 1, "applications": 1}
    assert "BEA-PRIVATE" not in str(mine) and "Bea only" not in str(mine)
    assert (
        find(client, ada, "BEA-PRIVATE-7781")["items"] == []
        and find(client, ada, "BEA-PRIVATE-7781")["counts"]["notes"] == 0
    )
    assert client.post(URL, json={"q": "otter"}).status_code == 401


def test_archived_only_when_asked_and_deleted_never(client):
    h = acct(client, "ada@example.com")
    made = seed(client, h)
    client.patch(f"/api/v1/me/notes/{made['note']}", headers=h, json={"archived": True})
    assert client.post(f"{APPS}/{made['application']}/archive", headers=h).status_code == 200
    plain = {i["type"] for i in find(client, h, "otter")["items"]}
    assert plain == {"story"}  # the archived note, the archived application and its kit are left out
    every = find(client, h, "otter", include_archived=True)["items"]
    assert {i["type"]: i["state"] for i in every} == {
        "note": "archived",
        "story": None,
        "kit": "archived",
        "application": "archived",
    }
    client.delete(f"/api/v1/me/notes/{made['note']}", headers=h)  # deleted, even in its undo window
    assert "note" not in {i["type"] for i in find(client, h, "otter", include_archived=True)["items"]}


def test_punctuation_wildcards_and_markup_are_plain_text(client):
    h = acct(client, "ada@example.com")
    client.post(
        "/api/v1/me/notes",
        headers=h,
        json={"title": "C++ and 100% effort", "body": "<script>alert(1)</script> under_score"},
    )
    client.post("/api/v1/me/notes", headers=h, json={"title": "Plain", "body": "nothing special here"})
    assert [i["title"] for i in find(client, h, "c++")["items"]] == ["C++ and 100% effort"]
    assert [i["title"] for i in find(client, h, "100%")["items"]] == ["C++ and 100% effort"]
    assert find(client, h, "%%")["items"] == []  # LIKE wildcards are matched literally
    assert find(client, h, "_n")["items"] == []
    assert [i["title"] for i in find(client, h, "under_score")["items"]] == ["C++ and 100% effort"]
    hit = find(client, h, "<script>")["items"][0]
    assert hit["snippet"].startswith(
        "<script>alert(1)</script>"
    )  # returned as text; the page shows it as text
    assert find(client, h, "'; drop table notes; --")["items"] == []
    assert len(find(client, h, "plain")["items"]) == 1  # still there


def test_the_database_step_alone_matches_wildcards_literally(client):
    """The exact check after the database would also catch a LIKE wildcard; this checks the
    database step on its own, so neither layer leans on the other."""
    h = acct(client, "ada@example.com")
    client.post("/api/v1/me/notes", headers=h, json={"title": "Plain", "body": "nothing special"})
    me = client.get("/api/v1/auth/me", headers=h).json()
    with client.app.state.session_factory() as db:
        user = db.get(ws.User, me["id"])
        assert [c.title for c in ws._notes(db, user, ["plain"], False)] == ["Plain"]
        assert ws._notes(db, user, ["%%"], False) == []
        assert ws._notes(db, user, ["_lain"], False) == []


def test_input_is_bounded(client):
    h = acct(client, "ada@example.com")
    assert client.post(URL, headers=h, json={"q": "a"}).status_code == 422  # too short to be useful
    assert client.post(URL, headers=h, json={"q": "   "}).status_code == 422
    assert client.post(URL, headers=h, json={"q": "x" * 201}).status_code == 422
    assert client.post(URL, headers=h, json={"q": "otter", "limit": 51}).status_code == 422
    assert client.post(URL, headers=h, json={"q": "otter", "kinds": ["passwords"]}).status_code == 422
    r = client.post(URL, headers=h, json={"q": "a"})
    assert "a" not in [d.get("input") for d in r.json()["error"]["details"]]  # the input isn't echoed back
    words = find(client, h, "y" * 100 + " " + " ".join(f"w{i}" for i in range(12)))["words"]
    assert len(words) == ws.MAX_WORDS and words[0] == "y" * ws.MAX_WORD and words[-1] == "w6"


def test_one_kind_failing_is_named_and_the_rest_still_searched(client, monkeypatch):
    h = acct(client, "ada@example.com")
    seed(client, h)

    def broken(db, user, words, archived):
        db.execute(
            ws.select(ws.func.count()).select_from(ws.Note).where(ws.Note.title == ws.func.no_such_function())
        )
        return []

    label, _ = ws.SOURCES["notes"]
    monkeypatch.setitem(ws.SOURCES, "notes", (label, broken))
    body = find(client, h, "otter")
    assert body["unavailable"] == ["notes"]
    assert {i["type"] for i in body["items"]} == {"story", "kit", "application"}  # read after the failure


def test_the_words_are_not_logged_or_put_in_a_url(client, caplog, monkeypatch):
    h = acct(client, "ada@example.com")
    seed(client, h)

    def broken(db, user, words, archived):
        raise RuntimeError("boom")

    monkeypatch.setitem(ws.SOURCES, "stories", ("stories", broken))
    with caplog.at_level(logging.DEBUG):
        r = client.post(URL, headers=h, json={"q": "otter SECRET-TERM-5521"})
    assert r.status_code == 200
    assert "SECRET-TERM-5521" not in caplog.text and "otter" not in caplog.text
    assert "workspace search: stories couldn't be read" in caplog.text
    assert (
        client.get(URL, headers=h, params={"q": "otter"}).status_code == 405
    )  # never a GET with the words in it


def test_searching_is_rate_limited_per_account(client):
    h = acct(client, "ada@example.com")
    other = acct(client, "bea@example.com")
    codes = [client.post(URL, headers=h, json={"q": "otter"}).status_code for _ in range(121)]
    assert codes[:120] == [200] * 120 and codes[120] == 429
    limited = client.post(URL, headers=h, json={"q": "otter"})
    assert limited.json()["error"]["details"]["retry_after_seconds"] >= 1
    assert (
        client.post(URL, headers=other, json={"q": "otter"}).status_code == 200
    )  # someone else isn't held up

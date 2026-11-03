"""The personal notebook: capture from sources, search/filter, conflicts, undo, privacy, export."""

from datetime import UTC, datetime, timedelta

from app.models import Note
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def create(client, h, **body):
    r = client.post("/api/v1/me/notes", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_capture_from_each_source_keeps_a_stable_reference_and_snapshot(client):
    h = nurse(client)
    q = create(
        client,
        h,
        title="Escalate early",
        body="Next time I should call sooner.",
        source={"type": "question", "id": "e-good-0", "track": NURSE},
        excerpt="What does good patient assessment look like?",
        excerpt_kind="quote",
        tags=["Escalation", " escalation ", "SBAR"],
    )
    assert q["source"] == {
        "type": "question",
        "id": "e-good-0",
        "track": NURSE,
        "version": None,
        "title": "What good patient assessment looks like",
        "href": f"/careers/{NURSE}/questions/e-good-0",
        "available": True,
        "career_title": "Registered Nurse",
    }
    assert q["tags"] == ["escalation", "sbar"] and q["excerpt_kind"] == "quote" and q["revision"] == 1
    p = create(
        client,
        h,
        title="HashMap trick",
        source={"type": "problem", "id": "two-sum"},
        excerpt="Map<Integer,Integer> m;",
        excerpt_kind="code",
    )
    assert p["source"]["href"] == "/problems/two-sum" and p["source"]["title"] == "Two Sum"
    lesson = create(client, h, title="SBAR", source={"type": "lesson", "id": "rn-sbar-handoff"})
    assert lesson["source"]["version"] == "1" and lesson["source"]["track"] == NURSE
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()
    r = create(
        client, h, title="Round notes", source={"type": "interview", "id": iv["id"], "question_index": 1}
    )
    assert r["source"]["href"] == f"/interviews/{iv['id']}?item=q1" and r["source"]["title"].endswith(
        "question 2"
    )
    # Sources must exist (and interviews must be yours).
    for bad in (
        {"type": "question", "id": "nope", "track": NURSE},
        {"type": "problem", "id": "nope"},
        {"type": "lesson", "id": "nope"},
        {"type": "interview", "id": "nope"},
    ):
        assert (
            client.post("/api/v1/me/notes", headers=h, json={"title": "x", "source": bad}).status_code == 404
        )


def test_search_filters_and_pinning(client):
    h = nurse(client)
    a = create(
        client,
        h,
        title="Triage order",
        body="ABCs first",
        tags=["triage"],
        source={"type": "question", "id": "e-good-0", "track": NURSE},
    )
    create(
        client,
        h,
        title="Two pointers",
        body="sorted arrays",
        tags=["arrays"],
        source={"type": "problem", "id": "two-sum"},
    )
    c = create(client, h, title="Old idea", body="Something about triage", tags=["triage"])

    def ids(**params):
        return [n["id"] for n in client.get("/api/v1/me/notes", headers=h, params=params).json()["items"]]

    assert set(ids(q="triage")) == {a["id"], c["id"]}
    assert ids(career=NURSE) == [a["id"]]
    assert len(ids(source_type="problem")) == 1
    assert ids(source_type="question", source_id="e-good-0") == [a["id"]]
    assert set(ids(tag="triage")) == {a["id"], c["id"]}
    page = client.get("/api/v1/me/notes", headers=h).json()
    assert {t["tag"]: t["count"] for t in page["tags"]} == {"triage": 2, "arrays": 1}
    assert page["careers"] == [{"tag": NURSE, "count": 1}] and page["pinned_limit"] == 5
    # Pinned first; archived notes leave the default list but stay findable.
    client.patch(f"/api/v1/me/notes/{c['id']}", headers=h, json={"pinned": True})
    assert ids()[0] == c["id"]
    client.patch(f"/api/v1/me/notes/{a['id']}", headers=h, json={"archived": True})
    assert a["id"] not in ids() and ids(status="archived") == [a["id"]] and a["id"] in ids(status="all")


def test_pinning_is_limited(client):
    h = nurse(client)
    notes = [create(client, h, title=f"n{i}") for i in range(6)]
    for n in notes[:5]:
        assert (
            client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json={"pinned": True}).status_code == 200
        )
    r = client.patch(f"/api/v1/me/notes/{notes[5]['id']}", headers=h, json={"pinned": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "pin_limit"


def test_an_edit_from_an_older_revision_is_refused_with_the_current_note(client):
    h = nurse(client)
    n = create(client, h, title="Draft", body="v1")
    tab_a = client.patch(
        f"/api/v1/me/notes/{n['id']}", headers=h, json={"base_revision": 1, "body": "edited in tab A"}
    ).json()
    assert tab_a["revision"] == 2 and tab_a["body"] == "edited in tab A"
    stale = client.patch(
        f"/api/v1/me/notes/{n['id']}", headers=h, json={"base_revision": 1, "body": "older text from tab B"}
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "note_conflict"
    assert stale.json()["error"]["details"]["current"]["body"] == "edited in tab A"
    assert client.get(f"/api/v1/me/notes/{n['id']}", headers=h).json()["body"] == "edited in tab A"
    # Choosing "keep mine" resends against the current revision.
    kept = client.patch(
        f"/api/v1/me/notes/{n['id']}", headers=h, json={"base_revision": 2, "body": "older text from tab B"}
    ).json()
    assert kept["body"] == "older text from tab B" and kept["revision"] == 3
    # Text changes need a base revision; pin/archive don't.
    assert client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json={"title": "x"}).status_code == 400
    flagged = client.patch(f"/api/v1/me/notes/{n['id']}", headers=h, json={"archived": True}).json()
    assert flagged["archived"] and flagged["revision"] == 3  # flags don't bump the revision
    assert (
        client.patch(
            f"/api/v1/me/notes/{n['id']}", headers=h, json={"base_revision": 3, "body": "ok"}
        ).status_code
        == 200
    )


def test_delete_has_an_undo_window_then_purges(client):
    h = nurse(client)
    n = create(client, h, title="Gone soon")
    d = client.delete(f"/api/v1/me/notes/{n['id']}", headers=h).json()
    assert datetime.fromisoformat(d["restorable_until"]) > datetime.now(UTC) + timedelta(minutes=9)
    assert client.get(f"/api/v1/me/notes/{n['id']}", headers=h).status_code == 404
    assert client.get("/api/v1/me/notes", headers=h).json()["total"] == 0
    back = client.post(f"/api/v1/me/notes/{n['id']}/restore", headers=h)
    assert back.status_code == 200 and back.json()["title"] == "Gone soon"
    # After the window the note can't be restored and is purged.
    client.delete(f"/api/v1/me/notes/{n['id']}", headers=h)
    db = client.app.state.session_factory()
    db.query(Note).update({"deleted_at": datetime.now(UTC) - timedelta(minutes=11)})
    db.commit()
    assert client.post(f"/api/v1/me/notes/{n['id']}/restore", headers=h).status_code == 404
    client.get("/api/v1/me/notes", headers=h)
    assert db.query(Note).count() == 0
    db.close()


def test_markdown_and_excerpts_are_stored_as_untrusted_text_and_bounded(client):
    h = nurse(client)
    evil = "<script>alert(1)</script> [x](javascript:alert(1)) <img src=x onerror=alert(1)>"
    n = create(client, h, title="<b>t</b>", body=evil, excerpt=evil, excerpt_kind="quote")
    assert n["body"] == evil and n["title"] == "<b>t</b>"  # stored verbatim; the browser renders it safely
    assert client.post("/api/v1/me/notes", headers=h, json={"body": "x" * 20_001}).status_code == 422
    assert (
        client.post("/api/v1/me/notes", headers=h, json={"tags": [str(i) for i in range(13)]}).status_code
        == 422
    )
    assert client.post("/api/v1/me/notes", headers=h, json={"excerpt": "x" * 4_001}).status_code == 422


def test_key_points_are_suggested_without_changing_the_note(client):
    h = nurse(client)
    body = "Today was rough.\nNext time I should escalate earlier.\n- Use SBAR on every call\nThe weather was nice."
    n = create(client, h, title="Shift", body=body)
    r = client.post(f"/api/v1/me/notes/{n['id']}/key-points", headers=h).json()
    assert r["points"] == ["Next time I should escalate earlier.", "Use SBAR on every call"]
    assert "no AI model" in r["method"]
    unchanged = client.get(f"/api/v1/me/notes/{n['id']}", headers=h).json()
    assert unchanged["body"] == body and unchanged["key_points"] is None and unchanged["revision"] == 1
    accepted = client.patch(
        f"/api/v1/me/notes/{n['id']}", headers=h, json={"base_revision": 1, "key_points": r["points"]}
    ).json()
    assert accepted["key_points"] == r["points"] and accepted["body"] == body


def test_a_retired_source_keeps_the_note(client):
    h = nurse(client)
    n = create(client, h, title="Keep me", source={"type": "question", "id": "e-good-0", "track": NURSE})
    db = client.app.state.session_factory()
    db.query(Note).update({"source_id": "retired-question"})
    db.commit()
    db.close()
    got = client.get(f"/api/v1/me/notes/{n['id']}", headers=h).json()
    assert got["title"] == "Keep me" and not got["source"]["available"] and got["source"]["href"] is None
    assert got["source"]["title"] == "What good patient assessment looks like"  # the snapshot stays


def test_another_account_can_never_read_or_change_a_note(client):
    ada = nurse(client, "ada@example.com")
    bob = nurse(client, "bob@example.com")
    n = create(client, ada, title="Private", body="secret")
    iv = client.post("/api/v1/interviews", headers=ada, json={"kind": "questions"}).json()
    for method, path, body in [
        ("get", f"/api/v1/me/notes/{n['id']}", None),
        ("patch", f"/api/v1/me/notes/{n['id']}", {"base_revision": 1, "body": "mine now"}),
        ("delete", f"/api/v1/me/notes/{n['id']}", None),
        ("post", f"/api/v1/me/notes/{n['id']}/restore", None),
        ("post", f"/api/v1/me/notes/{n['id']}/key-points", None),
    ]:
        kwargs = {"headers": bob} | ({"json": body} if body else {})
        assert getattr(client, method)(path, **kwargs).status_code == 404, (method, path)
    assert client.get("/api/v1/me/notes", headers=bob).json()["total"] == 0
    # Bob can't attach a note to Ada's interview either.
    r = client.post(
        "/api/v1/me/notes", headers=bob, json={"title": "x", "source": {"type": "interview", "id": iv["id"]}}
    )
    assert r.status_code == 404
    assert client.get(f"/api/v1/me/notes/{n['id']}", headers=ada).json()["body"] == "secret"
    assert client.get("/api/v1/me/notes").status_code == 401


def test_notes_are_exported_and_deleted_with_the_account(client):
    h = nurse(client)
    create(client, h, title="Exported", body="text", tags=["a"], source={"type": "problem", "id": "two-sum"})
    gone = create(client, h, title="Deleted")
    client.delete(f"/api/v1/me/notes/{gone['id']}", headers=h)
    data = client.get("/api/v1/me/export", headers=h).json()
    assert [n["title"] for n in data["notes"]] == ["Exported"]
    assert data["notes"][0]["source"]["id"] == "two-sum"
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    db = client.app.state.session_factory()
    assert db.query(Note).count() == 0
    db.close()

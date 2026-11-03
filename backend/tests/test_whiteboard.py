"""Whiteboard practice: bounded, plain-text diagrams; conflict-safe drafts; attempts frozen with
their versions; feedback that points at real elements and never judges looks or certifies a
design; imports that can't carry anything active; owner-only."""

from sqlalchemy import select

from app.models import WhiteboardAttempt, WhiteboardDraft
from tests.conftest import auth_headers, register

URL = "/api/v1/me/whiteboard"
P = "sd-url-shortener"
DIAGRAM = {
    "nodes": [
        {"id": "n1", "label": "Browser", "kind": "client", "x": 40, "y": 40},
        {"id": "n2", "label": "Shorten API", "kind": "service", "x": 240, "y": 40},
        {"id": "n3", "label": "Redis cache", "kind": "cache", "x": 440, "y": 40},
        {"id": "n4", "label": "URL database", "kind": "database", "x": 440, "y": 200},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "label": "create / redirect"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "lookup"},
        {"id": "e3", "source": "n2", "target": "n4", "label": "store mapping"},
    ],
    "notes": {
        "capacity": "About 100 new links/s and 10,000 redirects/s.",
        "tradeoffs": "A cache because reads far outnumber writes.",
    },
}
EXPLAIN = "I put a cache in front of the database because redirects outnumber new links a hundred to one, so most lookups never reach the database."


def coder(client, email="lin@example.com"):
    return auth_headers(register(client, email=email, display_name="Lin"))


def test_prompts_are_scoped_honestly_by_career(client):
    se = client.get(f"{URL}/prompts", headers=coder(client)).json()
    assert [p["id"] for p in se["prompts"]] == ["sd-url-shortener", "sd-rate-limiter", "sd-notifications"]
    nurse = auth_headers(register(client, email="ada@example.com", career_track="registered-nurse"))
    n = client.get(f"{URL}/prompts", headers=nurse).json()
    assert "Process maps for other careers aren't offered" in n["note"]


def test_drafts_save_with_revisions_and_refuse_stale_writes(client):
    h = coder(client)
    empty = client.get(f"{URL}/{P}/draft", headers=h).json()
    assert empty["revision"] == 0 and empty["diagram"]["nodes"] == []
    one = client.put(
        f"{URL}/{P}/draft",
        headers=h,
        json={"diagram": DIAGRAM, "explanation": "draft", "expected_revision": 0},
    )
    assert one.status_code == 200 and one.json()["revision"] == 1
    stale = client.put(f"{URL}/{P}/draft", headers=h, json={"diagram": DIAGRAM, "expected_revision": 0})
    assert stale.status_code == 409 and stale.json()["error"]["details"] == {"current_revision": 1}
    assert client.get(f"{URL}/{P}/draft", headers=h).json()["diagram"]["nodes"][0]["label"] == "Browser"
    assert client.get(f"{URL}/nope/draft", headers=h).status_code == 404


def test_imports_are_bounded_plain_text_and_strict(client):
    h = coder(client)
    bad = [
        {**DIAGRAM, "script": "<script>alert(1)</script>"},  # unknown field
        {**DIAGRAM, "nodes": [{"id": "n1", "label": "x" * 61, "kind": "client", "x": 0, "y": 0}]},
        {**DIAGRAM, "nodes": [{"id": "n1", "label": "A", "kind": "iframe", "x": 0, "y": 0}]},
        {**DIAGRAM, "nodes": [{"id": "N 1", "label": "A", "kind": "client", "x": 0, "y": 0}]},
        {
            **DIAGRAM,
            "nodes": [{"id": f"n{i}", "label": "A", "kind": "client", "x": 0, "y": 0} for i in range(41)],
        },
        {**DIAGRAM, "nodes": [{"id": "n1", "label": "A", "kind": "client", "x": -5, "y": 0}]},
    ]
    for d in bad:
        assert (
            client.put(f"{URL}/{P}/draft", headers=h, json={"diagram": d, "expected_revision": 0}).status_code
            == 422
        )
    ok = {
        **DIAGRAM,
        "nodes": [
            {**DIAGRAM["nodes"][0], "label": "<img src=x onerror=alert(1)>\x00"},
            *DIAGRAM["nodes"][1:],
        ],
    }
    saved = client.put(f"{URL}/{P}/draft", headers=h, json={"diagram": ok, "expected_revision": 0}).json()
    assert (
        saved["diagram"]["nodes"][0]["label"] == "<img src=x onerror=alert(1)>"
    )  # kept as text, never rendered as HTML


def test_feedback_needs_reasoning_first_and_points_at_real_elements(client):
    h = coder(client)
    short = client.post(
        f"{URL}/{P}/attempts", headers=h, json={"diagram": DIAGRAM, "explanation": "It scales."}
    )
    assert short.status_code == 400 and short.json()["error"]["code"] == "explanation_required"
    r = client.post(f"{URL}/{P}/attempts", headers=h, json={"diagram": DIAGRAM, "explanation": EXPLAIN})
    assert r.status_code == 201, r.text
    fb = r.json()["feedback"]
    assert fb["checks"] == [
        {"ok": True, "message": "4 components and 3 connections, all named and connected.", "refs": []}
    ]
    rubric = {x["requirement"]: x for x in fb["rubric"]}
    assert rubric["read-heavy"]["addressed"] and "n3" in [e["id"] for e in rubric["read-heavy"]["evidence"]]
    assert rubric["store"]["addressed"] and "n4" in [e["id"] for e in rubric["store"]["evidence"]]
    assert rubric["failure"]["addressed"] is False and rubric["failure"]["evidence"] == []
    assert all(x["ok"] for x in fb["reasoning"])
    assert any("never judges how the diagram looks" in x for x in fb["limitations"])
    assert r.json()["prompt_version"] == 1 and r.json()["rubric_version"] == 1


def test_broken_connections_are_reported_as_checks_not_quality(client):
    h = coder(client)
    broken = {
        **DIAGRAM,
        "edges": [*DIAGRAM["edges"], {"id": "e9", "source": "n1", "target": "n99", "label": ""}],
        "nodes": [*DIAGRAM["nodes"], {"id": "n5", "label": "", "kind": "other", "x": 0, "y": 300}],
    }
    fb = client.post(
        f"{URL}/{P}/attempts", headers=h, json={"diagram": broken, "explanation": EXPLAIN}
    ).json()["feedback"]
    messages = {c["message"]: c["refs"] for c in fb["checks"]}
    assert messages["Connection e9 points to a component that isn't there (n99)."] == ["e9"]
    assert messages["Some components have no name."] == ["n5"]


def test_an_attempt_is_frozen_and_an_edited_draft_is_marked_different(client):
    h = coder(client)
    client.put(
        f"{URL}/{P}/draft",
        headers=h,
        json={"diagram": DIAGRAM, "explanation": EXPLAIN, "expected_revision": 0},
    )
    a = client.post(
        f"{URL}/{P}/attempts", headers=h, json={"diagram": DIAGRAM, "explanation": EXPLAIN}
    ).json()
    assert client.get(f"{URL}/{P}/draft", headers=h).json()["differs_from_last_attempt"] is False
    edited = {
        **DIAGRAM,
        "nodes": [
            *DIAGRAM["nodes"],
            {"id": "n5", "label": "Replica", "kind": "database", "x": 600, "y": 200},
        ],
    }
    client.put(
        f"{URL}/{P}/draft",
        headers=h,
        json={"diagram": edited, "explanation": EXPLAIN, "expected_revision": 1},
    )
    assert client.get(f"{URL}/{P}/draft", headers=h).json()["differs_from_last_attempt"] is True
    again = client.get(f"{URL}/attempts/{a['id']}", headers=h).json()
    assert len(again["diagram"]["nodes"]) == 4 and again["feedback"] == a["feedback"]
    listed = client.get(f"{URL}/{P}/attempts", headers=h).json()
    assert listed[0]["addressed"] == 4 and listed[0]["total"] == 5


def test_privacy_export_and_deletion(client):
    a = coder(client)
    b = coder(client, email="bo@example.com")
    client.put(f"{URL}/{P}/draft", headers=a, json={"diagram": DIAGRAM, "expected_revision": 0})
    att = client.post(
        f"{URL}/{P}/attempts", headers=a, json={"diagram": DIAGRAM, "explanation": EXPLAIN}
    ).json()
    assert client.get(f"{URL}/attempts/{att['id']}", headers=b).status_code == 404
    assert client.get(f"{URL}/{P}/draft", headers=b).json()["revision"] == 0
    assert client.get(f"{URL}/{P}/attempts", headers=b).json() == []
    exported = client.get("/api/v1/me/export", headers=a).json()["whiteboard"]
    assert exported["drafts"][0]["prompt"] == P and exported["attempts"][0]["feedback"]["rubric_version"] == 1
    client.request(
        "DELETE", "/api/v1/auth/me", headers=a, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert (
            db.scalars(select(WhiteboardDraft)).all() == []
            and db.scalars(select(WhiteboardAttempt)).all() == []
        )


def test_validate_checks_a_file_without_saving_anything(client):
    h = coder(client)
    ok = client.post(f"{URL}/validate", headers=h, json={**DIAGRAM, "notes": {"capacity": "  10 rps\x07 "}})
    assert (
        ok.status_code == 200
        and ok.json()["notes"]["capacity"] == "10 rps"
        and ok.json()["format"] == "codecoach-whiteboard"
    )
    assert client.post(f"{URL}/validate", headers=h, json={**DIAGRAM, "version": 2}).status_code == 422
    assert client.post(f"{URL}/validate", headers=h, json={**DIAGRAM, "extra": True}).status_code == 422
    assert client.post(f"{URL}/validate", json=DIAGRAM).status_code == 401
    with client.app.state.session_factory() as db:
        assert db.scalars(select(WhiteboardDraft)).all() == []


def test_a_words_only_answer_still_gets_feedback(client):
    h = coder(client)
    empty = {"nodes": [], "edges": [], "notes": {"capacity": "10,000 redirects a second"}}
    r = client.post(f"{URL}/{P}/attempts", headers=h, json={"diagram": empty, "explanation": EXPLAIN})
    assert r.status_code == 201
    fb = r.json()["feedback"]
    assert fb["checks"] == [
        {
            "ok": False,
            "message": "The diagram is empty, so only your notes and explanation were read.",
            "refs": [],
        }
    ]
    rubric = {x["requirement"]: x for x in fb["rubric"]}
    assert rubric["read-heavy"]["evidence"][0]["kind"] == "explanation" and rubric["store"]["addressed"]


def test_groups_are_counted_but_never_required(client):
    h = coder(client)
    grouped = {
        **DIAGRAM,
        "nodes": [{**n, "group": "Read path"} if n["id"] in ("n2", "n3") else n for n in DIAGRAM["nodes"]],
    }
    fb = client.post(
        f"{URL}/{P}/attempts", headers=h, json={"diagram": grouped, "explanation": EXPLAIN}
    ).json()["feedback"]
    assert fb["checks"][0]["message"] == "4 components in 1 group and 3 connections, all named and connected."

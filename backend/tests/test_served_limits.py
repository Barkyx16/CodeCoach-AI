"""The limits forms state, served (Volume 17, prompt 7; docs/API.md, "Limits"): `GET /limits` gives
each by a stable name, with what it counts; every served value is the one the server enforces (read
here independently of how it's served, and checked where a request field refuses one past it); the
refusal says the same thing as the form; it's public and cached like the catalogue; and no client
constant named like a limit holds a served limit's value unless it says it's the client's own.
Synthetic data only."""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.routes.meta import LimitName
from app.schemas import applications as app_schemas
from app.schemas import content as content_schemas
from app.schemas import explore as explore_schemas
from app.schemas import packet as packet_schemas
from app.schemas import roles as roles_schemas
from app.schemas import shares as share_schemas
from app.schemas.careers import AnswerRequest
from app.schemas.interview import RoundAnswer
from app.schemas.review import RetryIn
from app.schemas.roadmap import GoalsIn
from app.services import applications as applications_service
from app.services import explore, restore
from app.whiteboard import diagram
from tests.conftest import auth_headers, register

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
CLIENT_OWN = "the client's own"

# Where the server enforces each, read here on its own (not through app/services/limits.py).
ENFORCED = {
    "collections_per_account": explore.MAX_COLLECTIONS,
    "items_per_collection": explore.MAX_ITEMS,
    "items_per_batch": explore_schemas.BATCH_LIMIT,
    "stories_per_application": app_schemas.MAX_LINKED_STORIES,
    "target_description_chars": roles_schemas.MAX_DESCRIPTION,
    "report_details_chars": content_schemas.MAX_DETAILS,
    "report_excerpt_chars": content_schemas.MAX_EXCERPT,
    "backup_file_bytes": restore.MAX_BYTES,
    "packet_items": packet_schemas.PACKET_ITEMS,
    "packet_kits": packet_schemas.PACKET_KITS,
    "share_feedback_field_chars": share_schemas.MAX_FIELD,
    "share_feedback_comments": share_schemas.MAX_COMMENTS,
    "whiteboard_components": diagram.MAX_NODES,
    "whiteboard_connections": diagram.MAX_EDGES,
}


def served(client) -> dict[str, dict]:
    r = client.get("/api/v1/limits")
    assert r.status_code == 200, r.text
    return {x["name"]: x for x in r.json()["limits"]}


def test_every_served_limit_is_the_one_the_server_enforces(client):
    got = served(client)
    assert list(got) == list(typing.get_args(LimitName))  # each by its stable name, once
    for name, value in ENFORCED.items():
        assert got[name]["value"] == value, name
    assert all(x["counts"] for x in got.values())


def test_where_a_request_field_enforces_it_one_more_is_refused(client):
    got = {k: v["value"] for k, v in served(client).items()}
    n = got["answer_chars"]
    AnswerRequest(answer="x" * n)
    for model in (AnswerRequest, RetryIn):  # every answer form reads the one number
        with pytest.raises(ValidationError):
            model(answer="x" * (n + 1))
    with pytest.raises(ValidationError):
        RoundAnswer(question_index=0, answer="x" * (n + 1))
    f = got["goal_focus_areas"]
    GoalsIn(focus_areas=[f"skill {i}" for i in range(f)])
    with pytest.raises(ValidationError):
        GoalsIn(focus_areas=[f"skill {i}" for i in range(f + 1)])


def test_the_refusal_says_what_the_form_says(client, monkeypatch):
    got = served(client)
    h = auth_headers(register(client))
    for i in range(got["collections_per_account"]["value"]):
        assert client.post("/api/v1/me/collections", headers=h, json={"name": f"C{i}"}).status_code == 201
    r = client.post("/api/v1/me/collections", headers=h, json={"name": "One more"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "too_many_collections"
    c = got["collections_per_account"]
    assert f"up to {c['value']} {c['counts']}" in r.json()["error"]["message"]
    # Items in a collection and stories per application: the refusal names what the form counts.
    monkeypatch.setattr(explore, "MAX_ITEMS", 0)
    cid = client.get("/api/v1/me/collections", headers=h).json()[0]["id"]
    full = client.post(
        f"/api/v1/me/collections/{cid}/items",
        headers=h,
        json={"item_type": "problem", "track": "", "ref_id": "two-sum"},
    )
    assert full.json()["error"]["code"] == "collection_full"
    assert full.json()["error"]["message"].endswith(f" {got['items_per_collection']['counts']}.")
    assert got["stories_per_application"]["value"] == applications_service.MAX_LINKED_STORIES


def test_it_is_public_and_cached_like_the_catalogue(client):
    r = client.get("/api/v1/limits")
    assert r.status_code == 200
    assert r.headers["cache-control"].startswith("public, max-age=")
    assert r.headers.get("etag")


NAMED = re.compile(r"^\s*(?:export\s+)?const\s+([A-Z][A-Z0-9_]*)\s*=\s*([0-9_][0-9_\s*]*);", re.M)


def client_copies(values: set[int]) -> list[str]:
    """Client constants named like a limit (MAX…, …LIMIT…) whose value is a served limit's, unless the
    comment just above says it's the client's own."""
    out = []
    for path in FRONTEND.rglob("*.ts*"):
        rel = path.relative_to(FRONTEND).as_posix()
        if rel.startswith("test/") or ".test." in rel or rel == "api/schema.d.ts":
            continue
        text = path.read_text(encoding="utf8")
        for m in NAMED.finditer(text):
            name, expr = m.group(1), m.group(2).replace("_", "").split("*")
            if "MAX" not in name and "LIMIT" not in name:
                continue
            value = 1
            for part in expr:
                value *= int(part.strip())
            above = text[: m.start()].splitlines()[-4:]
            if value in values and not any(CLIENT_OWN in line.lower() for line in above):
                out.append(f"{rel}: {name} = {value}")
    return out


def test_no_client_copy_of_a_served_limit(client):
    values = {x["value"] for x in served(client).values()}
    assert client_copies(values) == []

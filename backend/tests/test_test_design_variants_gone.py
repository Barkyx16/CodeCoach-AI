"""The faulty versions are shown only where the showing is recorded (Volume 20, prompt 4;
docs/TEST_DESIGN.md): the public route that served them with nothing recorded answers 410 with a plain
explanation, at the same path, signed in or not, and records nothing. No public response carries a
faulty version's title or defect; the exercise's public summary still says how many there are. Signed
in, the page's POST still shows them and records the showing first. An unknown exercise is still a
404. Synthetic accounts only."""

from __future__ import annotations

import json

from sqlalchemy import func, select

from app.api.routes.test_design import VARIANTS_GONE
from app.models import TestDesignReveal
from app.testdesign import BY_SLUG
from tests.conftest import auth_headers, register
from tests.test_test_design import COUNT

PUBLIC = "/api/v1/test-design"


def reveals(client) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(TestDesignReveal))


def test_the_public_route_answers_gone_with_the_reason_and_records_nothing(client):
    r = client.get(f"{PUBLIC}/{COUNT}/variants")
    assert r.status_code == 410
    body = r.json()["error"]
    assert body["code"] == "faulty_versions_need_sign_in" and body["message"] == VARIANTS_GONE
    assert "Sign in" in body["message"] and "recorded as help" in body["message"]
    # Signed in, an old page calling it gets the same answer, and nothing is recorded.
    h = auth_headers(register(client, career_track="software-engineer"))
    assert client.get(f"{PUBLIC}/{COUNT}/variants", headers=h).status_code == 410
    assert reveals(client) == 0
    assert client.get(f"{PUBLIC}/no-such/variants").status_code == 404


def test_no_public_response_carries_a_faulty_version_and_the_count_stays(client):
    ex = BY_SLUG[COUNT]
    listed = client.get(PUBLIC).json()
    one = client.get(f"{PUBLIC}/{COUNT}").json()
    gone = client.get(f"{PUBLIC}/{COUNT}/variants").json()
    text = json.dumps([listed, one, gone])
    for v in ex.variants:
        assert v.title not in text and v.defect not in text
    assert next(e for e in listed if e["slug"] == COUNT)["variant_count"] == len(ex.variants)
    assert one["variant_count"] == len(ex.variants)


def test_signed_in_the_recorded_showing_still_shows_them(client):
    h = auth_headers(register(client, career_track="software-engineer"))
    r = client.post(f"/api/v1/me/test-design/{COUNT}/variants", headers=h)
    assert r.status_code == 200
    assert [v["title"] for v in r.json()["variants"]] == [v.title for v in BY_SLUG[COUNT].variants]
    assert reveals(client) == 1


def test_the_api_document_says_gone_and_offers_no_list(client):
    doc = client.get("/openapi.json").json()
    op = doc["paths"][f"{PUBLIC}/{{slug}}/variants"]["get"]
    assert "200" not in op["responses"] and {"404", "410"} <= set(op["responses"])
    assert "recorded" in op["summary"]

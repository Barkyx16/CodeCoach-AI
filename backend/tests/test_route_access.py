"""Route-table checks: whatever is added to the API later, (1) every route needs a signed-in
account unless it is on the explicit public list below, and (2) another account reading any GET
route with your record ids gets nothing back. Complements the per-feature privacy tests and the
database's row-level security (test_row_level_security.py). Synthetic accounts only."""

import re

from fastapi.routing import APIRoute

from app.api.deps import get_current_user, get_optional_user, require_admin
from app.careers.questions import questions_for
from tests.conftest import auth_headers, register

# Reviewed: what anyone may call without signing in. Adding a route here is a decision.
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("GET", "/metrics"),  # token-protected when METRICS_TOKEN is set (required in production)
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/guest"),
    ("POST", "/api/v1/auth/refresh"),  # the HttpOnly cookie is the credential
    ("POST", "/api/v1/auth/verify-email"),  # the emailed link token is the credential
    ("POST", "/api/v1/auth/password-reset"),
    ("POST", "/api/v1/auth/password-reset/confirm"),  # the emailed reset token is the credential
    ("GET", "/api/v1/problems"),
    ("GET", "/api/v1/problems/counts"),
    ("GET", "/api/v1/topics"),
    ("GET", "/api/v1/problems/{slug}"),
    ("GET", "/api/v1/careers"),
    ("GET", "/api/v1/careers/{slug}/questions"),
    ("GET", "/api/v1/careers/{slug}/questions/counts"),
    ("GET", "/api/v1/careers/{slug}/questions/{question_id}"),
    ("GET", "/api/v1/careers/{slug}/questions/{question_id}/criteria"),
    ("GET", "/api/v1/careers/{slug}/questions/{question_id}/versions/{version}"),
    ("GET", "/api/v1/careers/{slug}/explore"),
    ("GET", "/api/v1/content/{content_type}/{content_id:path}/meta"),
    ("GET", "/api/v1/learn"),
    ("GET", "/api/v1/learn/related"),
    ("GET", "/api/v1/learn/units/{unit_id}"),
    ("GET", "/api/v1/scenarios"),
    ("GET", "/api/v1/scenarios/{scenario_id}"),
    ("GET", "/api/v1/interviews/formats"),
    ("GET", "/api/v1/capabilities"),
    ("POST", "/api/v1/shared/open"),  # the 256-bit link secret (in the body) is the credential
    ("POST", "/api/v1/shared/feedback"),
}


def api_routes(app):
    def flat(routes):
        for r in routes:
            if hasattr(r, "original_router"):  # FastAPI keeps included routers wrapped
                yield from flat(r.original_router.routes)
            else:
                yield r

    return [r for r in flat(app.routes) if isinstance(r, APIRoute)]


def dependencies(dependant, found=None):
    found = set() if found is None else found
    for d in dependant.dependencies:
        found.add(d.call)
        dependencies(d, found)
    return found


def route_table(app):
    for r in api_routes(app):
        deps = dependencies(r.dependant)
        kind = "admin" if require_admin in deps else "user" if get_current_user in deps else "public"
        for method in sorted(r.methods - {"HEAD", "OPTIONS"}):
            yield method, r.path, kind, get_optional_user in deps


def concrete(path, values=None):
    values = values or {}
    return re.sub(r"{(\w+)(?::\w+)?}", lambda m: str(values.get(m.group(1), "1")), path)


def test_only_the_reviewed_routes_are_public(client):
    public = {(m, p) for m, p, kind, _ in route_table(client.app) if kind == "public"}
    assert public == PUBLIC, f"newly public: {public - PUBLIC}; no longer public: {PUBLIC - public}"
    assert len(list(route_table(client.app))) > 150  # the walk really saw the API


def test_every_other_route_refuses_anonymous_callers(client):
    for method, path, kind, _ in route_table(client.app):
        if kind == "public":
            continue
        r = client.request(method, concrete(path))
        expected = 404 if kind == "admin" else 401  # admin routes don't admit they exist
        assert r.status_code == expected, (method, path, r.status_code, r.text[:200])


TRACK = "registered-nurse"
SECRET = "ADA-PRIVATE-5519"


def seed(client, h):
    """One of each kind of record a GET route takes an id for, owned by `h`."""
    ids = {}
    a = client.post(
        "/api/v1/me/applications", headers=h, json={"employer": f"Hospital {SECRET}", "role_title": "Nurse"}
    ).json()
    ids["app_id"] = a["id"]
    ev = client.post(
        f"/api/v1/me/applications/{a['id']}/events",
        headers=h,
        json={"title": f"Interview {SECRET}", "on_date": "2026-12-15"},
    ).json()
    ids["event_id"] = ev["events"][0]["id"]
    ids["note_id"] = client.post(
        "/api/v1/me/notes", headers=h, json={"title": f"Note {SECRET}", "body": SECRET}
    ).json()["id"]
    ids["collection_id"] = client.post(
        "/api/v1/me/collections", headers=h, json={"name": f"List {SECRET}"}
    ).json()["id"]
    ids["target_id"] = client.post(
        "/api/v1/targets", headers=h, json={"title": f"Ward nurse {SECRET}", "description": "Work in a team."}
    ).json()["id"]
    ids["story_id"] = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": f"Story {SECRET}", "situation": SECRET, "task": "t", "action": "a", "result": "r"},
    ).json()["id"]
    ids["entry_id"] = client.post(
        "/api/v1/me/schedule",
        headers=h,
        json={"kind": "application_event", "ref": ids["event_id"], "on_date": "2026-12-13", "all_day": True},
    ).json()["id"]
    q = next(q for q in questions_for(TRACK) if q.kind == "behavioral")
    ans = client.post(
        f"/api/v1/careers/{TRACK}/questions/{q.id}/answers",
        headers=h,
        json={
            "answer": f"On a night shift ({SECRET}) I checked observations, called the team, and he was stable."
        },
    ).json()
    ids["answer_id"] = ans["id"]
    ids["slug"], ids["question_id"] = TRACK, q.id
    ids["interview_id"] = client.post("/api/v1/interviews", headers=h, json={"kind": "questions"}).json()[
        "id"
    ]
    ids["index"] = 0
    ids["submission_id"] = client.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": f"// {SECRET}"}
    ).json()["id"]
    hint = client.post(
        "/api/v1/ai/hint",
        headers=h,
        json={"problem_slug": "two-sum", "level": 1, "source_code": f"// {SECRET}"},
    )
    assert hint.status_code == 200, hint.text
    history = client.get("/api/v1/me/ai-history", headers=h).json()
    items = history["items"] if isinstance(history, dict) else history
    ids["interaction_id"] = items[0]["id"]
    return ids


PUBLIC_PARAMS = {"slug", "question_id", "prompt_id", "drill_id", "unit_id", "scenario_id"}
# GET routes with record ids this walk doesn't make; each has its own cross-account test.
NOT_WALKED = {
    "/api/v1/me/shares/{share_id}": "test_shares.py",
    "/api/v1/me/scenario-attempts/{attempt_id}": "test_scenarios.py",
    "/api/v1/me/whiteboard/attempts/{attempt_id}": "test_whiteboard.py",
}


def test_another_account_reads_nothing_of_yours_on_any_get_route(client):
    ada = auth_headers(register(client, email="ada@example.com", career_track=TRACK))
    bea = auth_headers(register(client, email="bea@example.com", career_track=TRACK))
    ids = seed(client, ada)
    walked, skipped = 0, set()
    for method, path, kind, _ in route_table(client.app):
        if method != "GET" or kind != "user":
            continue
        private = set(re.findall(r"{(\w+)(?::\w+)?}", path)) - PUBLIC_PARAMS
        if not private:
            continue  # lists and pages of the caller's own data: nothing of anyone else's to name
        if not private <= ids.keys():
            skipped.add(path)
            continue
        own = client.get(concrete(path, ids), headers=ada)
        r = client.get(concrete(path, ids), headers=bea)
        walked += 1
        # The ids are real: the owner's request finds the record (some answer 409 "not finished yet").
        assert own.status_code not in (401, 403, 404), (path, own.status_code, own.text[:200])
        assert r.status_code in (403, 404), (path, r.status_code)
        assert SECRET not in r.text, path
        for value in (str(ids[p]) for p in private if p != "index"):
            assert value not in r.text, (path, "an id came back")
    assert walked >= 15, walked
    assert skipped == set(NOT_WALKED), (
        f"GET routes with ids this walk doesn't cover: {sorted(skipped - set(NOT_WALKED))}"
    )

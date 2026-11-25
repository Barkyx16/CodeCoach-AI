"""Response caching: the shared public catalogue is cached (in process, and by browsers with an
ETag), personalised pages only for anonymous callers, and every other API response is no-store,
so no browser, proxy or CDN keeps private data. A correction or retirement is served at once.
Synthetic accounts only."""

from sqlalchemy import delete

from app.content import state as content_state
from app.models import ContentStatus
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
QID = "m-pressure-0"
QUESTIONS = f"/api/v1/careers/{NURSE}/questions?difficulty=medium&page_size=100"


def ids(r):
    return [x["id"] for x in r.json()["items"]]


def test_the_shared_catalogue_is_cached_and_revalidates_with_an_etag(client):
    first = client.get("/api/v1/careers")
    assert first.status_code == 200 and first.headers["x-cache"] == "miss"
    assert first.headers["cache-control"] == "public, max-age=60"
    etag = first.headers["etag"]
    second = client.get("/api/v1/careers")
    assert second.headers["x-cache"] == "hit" and second.content == first.content
    assert second.headers["etag"] == etag
    not_modified = client.get("/api/v1/careers", headers={"If-None-Match": etag})
    assert not_modified.status_code == 304 and not_modified.content == b""
    # The same for a signed-in caller: this list doesn't depend on who asks.
    h = auth_headers(register(client))
    assert client.get("/api/v1/careers", headers=h).headers["x-cache"] == "hit"
    # Each query string is its own entry.
    assert client.get("/api/v1/problems?page_size=5").headers["x-cache"] == "miss"
    assert client.get("/api/v1/problems?page_size=6").headers["x-cache"] == "miss"


def test_private_and_auth_responses_are_never_stored(client):
    h = auth_headers(register(client, email="ada@example.com"))
    for r in (
        client.get("/api/v1/auth/me", headers=h),
        client.get("/api/v1/me/notes", headers=h),
        client.get("/api/v1/me/progress", headers=h),
        client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "CorrectHorse42"}),
        client.get("/health"),
        client.get("/api/v1/capabilities"),
    ):
        assert r.headers["cache-control"] == "no-store", r.url
        assert "etag" not in r.headers and "x-cache" not in r.headers
    # A route's own header is kept as it set it.
    export = client.get("/api/v1/me/export", headers=h)
    assert export.headers["cache-control"] == "no-store"


def test_personalised_pages_are_cached_only_for_anonymous_callers(client):
    h = auth_headers(register(client, email="ada@example.com", career_track=NURSE))
    anon = client.get(QUESTIONS)
    assert anon.headers["x-cache"] == "miss" and "Authorization" in anon.headers["vary"]
    assert client.get(QUESTIONS).headers["x-cache"] == "hit"
    mine = client.get(QUESTIONS, headers=h)
    assert mine.status_code == 200
    assert mine.headers["cache-control"] == "no-store" and "x-cache" not in mine.headers


def test_errors_are_not_cached(client):
    for _ in range(2):
        r = client.get("/api/v1/problems/no-such-problem")
        assert (
            r.status_code == 404 and r.headers["cache-control"] == "no-store" and "x-cache" not in r.headers
        )


def test_a_retirement_is_served_at_once_and_one_from_another_replica_soon(client, monkeypatch):
    assert QID in ids(client.get(QUESTIONS))
    assert client.get(QUESTIONS).headers["x-cache"] == "hit"
    with client.app.state.session_factory() as db:
        db.add(
            ContentStatus(
                content_type="question", content_id=f"{NURSE}/{QID}", reason="Synthetic retirement."
            )
        )
        db.commit()
    # Written by "another replica": this process doesn't know yet. Its snapshot is at most
    # MAX_AGE_S old, then the next read refreshes it and the cache key changes.
    monkeypatch.setattr(content_state, "MAX_AGE_S", 0.0)
    after = client.get(QUESTIONS)
    assert after.headers["x-cache"] == "miss" and QID not in ids(after)
    # Triage in this process invalidates at once (what the admin routes call).
    with client.app.state.session_factory() as db:
        db.execute(delete(ContentStatus))
        db.commit()
    content_state.invalidate()
    assert QID in ids(client.get(QUESTIONS))


def test_logs_and_metrics_still_name_the_route_on_a_hit(client):
    for _ in range(3):
        client.get("/api/v1/topics")
    samples = [
        line
        for line in client.get("/metrics").text.splitlines()
        if line.startswith("codecoach_http_requests_total") and 'route="/api/v1/topics"' in line
    ]
    assert samples and float(samples[0].rsplit(" ", 1)[1]) == 3.0

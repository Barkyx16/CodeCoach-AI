def test_health_is_minimal(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_checks_database(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] == "ok"
    assert r.json()["checks"]["schema"] == "unmanaged"  # tests make tables with create_all


def test_readiness_says_when_the_schema_is_behind_this_code(client):
    """Release Readiness brief 02: new code on the previous schema fails on columns the migration
    adds, so it isn't ready until the migration has run. An unknown (newer) revision is an
    application revert onto an expanded schema, which the additive migrations support."""
    from sqlalchemy import text

    from app.api.routes.health import _revisions

    heads, everything = _revisions()
    head = next(iter(heads))
    older = next(iter(everything - heads))
    db = client.app.state.session_factory()
    db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db.commit()
    try:
        for at, status, schema in (
            (head, 200, "current"),
            (older, 503, "behind"),
            ("f00dfeedbeef", 200, "newer"),
        ):
            db.execute(text("DELETE FROM alembic_version"))
            db.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": at})
            db.commit()
            r = client.get("/health/ready")
            assert (r.status_code, r.json()["checks"]["schema"]) == (status, schema)
            assert at not in r.text  # no revision is named
    finally:
        db.execute(text("DROP TABLE alembic_version"))
        db.commit()
        db.close()


def test_the_code_knows_its_own_migration_head():
    from app.api.routes.health import _revisions

    heads, everything = _revisions()
    assert heads == {"9a0b1c2d3e4f"} and "b165a5a80342" in everything


def test_request_id_is_generated_and_echoed(client):
    r = client.get("/health")
    assert len(r.headers["X-Request-ID"]) >= 8
    r = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert r.headers["X-Request-ID"] == "trace-abc-12345"


def test_malformed_request_id_is_replaced(client):
    r = client.get("/health", headers={"X-Request-ID": "bad id with spaces\n"})
    assert r.headers["X-Request-ID"] != "bad id with spaces\n"


def test_unknown_route_uses_error_envelope(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == r.headers["X-Request-ID"]


def test_validation_errors_use_envelope(client):
    r = client.get("/api/v1/problems", params={"page": 0})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"][-1] == "page"


def test_cors_allows_configured_origin_only(make_client):
    c = make_client(cors_origins="http://localhost:5173,https://codecoach.example.com")
    ok = c.options(
        "/api/v1/problems",
        headers={"Origin": "https://codecoach.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "https://codecoach.example.com"
    bad = c.options(
        "/api/v1/problems", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in bad.headers


def test_metrics_use_route_templates(client):
    client.get("/api/v1/problems/two-sum")
    client.get("/api/v1/problems/does-not-exist-123")
    text = client.get("/metrics").text
    assert 'route="/api/v1/problems/{slug}"' in text
    assert "does-not-exist-123" not in text


def test_openapi_documents_every_route(client):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    for path in [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/problems",
        "/api/v1/problems/{slug}",
        "/api/v1/submissions",
        "/api/v1/ai/hint",
        "/api/v1/ai/review",
        "/api/v1/me/progress",
        "/api/v1/me/recommendations",
    ]:
        assert path in paths, path
    assert "ErrorEnvelope" in spec["components"]["schemas"]


def test_production_refuses_default_secret():
    import pytest

    from app.config import Settings

    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(environment="production", _env_file=None)


def test_anthropic_provider_requires_key():
    import pytest

    from app.config import Settings

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(ai_provider="anthropic", anthropic_api_key=None, _env_file=None)


def test_readiness_is_503_not_an_error_when_the_database_is_down(client, monkeypatch):
    """Verification brief 05: through a real server the unreachable database came back as 500,
    because the request dependency read content state before the check. Readiness now opens its
    own session inside its own error handling."""
    from sqlalchemy.exc import OperationalError

    class Down:
        def execute(self, *a, **k):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self):
            pass

    monkeypatch.setattr(client.app.state, "session_factory", lambda: Down())
    r = client.get("/health/ready")
    assert (r.status_code, r.json()) == (503, {"status": "unavailable", "checks": {"database": "fail"}})
    assert client.get("/health").status_code == 200  # liveness is its own, separate policy

"""INSTANCE_LABEL lets a test suite recognise its own server (frontend/e2e/global-setup.ts) instead
of reusing a developer's server, or an orphan with the wrong configuration, on the same port."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import PRODUCTION_BASE


def test_the_label_is_sent_only_when_set(make_settings):
    with TestClient(create_app(make_settings(instance_label="e2e"))) as c:
        assert c.get("/health").headers["X-CodeCoach-Instance"] == "e2e"
        assert c.get("/api/v1/capabilities").headers["X-CodeCoach-Instance"] == "e2e"
    with TestClient(create_app(make_settings())) as c:
        assert "X-CodeCoach-Instance" not in c.get("/health").headers


def test_production_refuses_a_test_label():
    with pytest.raises(ValueError, match="INSTANCE_LABEL is for test servers only"):
        Settings(**{**PRODUCTION_BASE, "instance_label": "e2e"}, _env_file=None)

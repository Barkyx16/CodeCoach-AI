"""docs/openapi.json is the contract the frontend is built against. This test fails when the
API changes without the committed spec being regenerated (`python -m app.cli openapi`)."""

import json

import pytest

from app.cli import OPENAPI_PATH


def test_committed_openapi_matches_code(client):
    if not OPENAPI_PATH.exists():
        pytest.skip("docs/openapi.json not present (e.g. inside the Docker build context)")
    committed = json.loads(OPENAPI_PATH.read_text())
    assert committed == client.app.openapi(), "API changed: run `python -m app.cli openapi` and commit the result"

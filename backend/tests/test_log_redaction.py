"""Redaction at the real logging boundary (Verification brief 09): synthetic markers for answer
text, request keys and the bearer token must not appear in anything the app writes to its logs,
on any path: a save, a replay, a conflict, a validation error, a grading failure and a database
failure (whose error message would otherwise carry the statement's parameters). Synthetic data."""

from __future__ import annotations

import io
import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.careers.questions import questions_for
from app.observability import JsonFormatter
from tests.conftest import auth_headers, register

ANSWER = (
    "Last winter on a busy ward ZZANSWERMARKERZZ I noticed a patient's breathing change during my night "
    "round. I checked his observations again, raised the bed, started oxygen as prescribed and called the "
    "doctor using SBAR. Within the hour his saturation was back to 96%, and I learned to escalate early."
)
KEY = "op-ZZKEYMARKERZZ-01"
URL = f"/api/v1/careers/registered-nurse/questions/{questions_for('registered-nurse')[0].id}/answers"


@pytest.fixture
def emitted():
    """Everything the app's loggers write, formatted by the app's own JSON formatter."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("codecoach")
    root.addHandler(handler)
    yield buf
    root.removeHandler(handler)


def _assert_clean(text: str, token: str) -> None:
    for marker in ("ZZANSWERMARKERZZ", "ZZKEYMARKERZZ", token):
        assert marker not in text, f"{marker[:16]}… appeared in the logs"


def test_save_replay_conflict_and_validation_paths_log_no_text_keys_or_tokens(client, emitted):
    token = register(client)["access_token"]
    h = auth_headers({"access_token": token})
    for path in (URL, URL + "/keyed"):
        body = {"answer": ANSWER, "client_request_id": KEY if path == URL else KEY + "k"}
        assert client.post(path, headers=h, json=body).status_code == 201
        assert client.post(path, headers=h, json=body).status_code == 200
        assert client.post(path, headers=h, json={**body, "answer": ANSWER + " x"}).status_code == 409
    bad = client.post(URL, headers=h, json={"answer": ANSWER, "client_request_id": "bad ZZKEYMARKERZZ"})
    assert bad.status_code == 422
    logged = emitted.getvalue()
    _assert_clean(logged, token)
    assert '"span": "answer.save"' in logged and '"result": "replayed"' in logged  # categories kept


@pytest.mark.parametrize("failure", ["grading", "database"])
def test_failures_are_logged_without_the_request_s_text_or_key(client, monkeypatch, emitted, failure):
    token = register(client)["access_token"]
    h = auth_headers({"access_token": token})
    if failure == "grading":

        def boom(*a, **k):
            raise RuntimeError("grading failed")

        monkeypatch.setattr("app.api.routes.careers.graded_answer", boom)
    else:
        # A real driver error through the engine: with the table gone, the key lookup fails, and
        # SQLAlchemy's message would carry the statement and its parameters (the key, the text).
        db = client.app.state.session_factory()
        cascade = " CASCADE" if db.get_bind().dialect.name == "postgresql" else ""
        db.execute(text(f"DROP TABLE practice_answers{cascade}"))
        db.commit()
        db.close()
    with pytest.raises((RuntimeError, DBAPIError)):  # the test client re-raises it
        client.post(URL, headers=h, json={"answer": ANSWER, "client_request_id": KEY})
    logged = emitted.getvalue()
    assert "unhandled error" in logged  # the failure is still reported
    _assert_clean(logged, token)

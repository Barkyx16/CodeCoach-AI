"""The opt-in access log file (Volume 9, prompt 9): each request's start and finish, with the
request id, method and path only, so a test that saw a read hang can tell whether it reached the
server. Off unless configured."""

import json
import logging

import pytest

from app.observability import access_log


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def _reset_access_log():
    yield
    for h in list(access_log.handlers):
        if getattr(h, "_codecoach_access_file", False):
            access_log.removeHandler(h)
            h.close()
    access_log.setLevel(logging.NOTSET)
    access_log.propagate = True


def test_start_and_finish_are_written_without_query_strings_or_headers(make_client, tmp_path):
    target = tmp_path / "access.log"
    client = make_client(access_log_file=str(target))
    r = client.get("/health?secret=do-not-log", headers={"Authorization": "Bearer do-not-log"})
    assert r.status_code == 200
    lines = _lines(target)
    started = [line for line in lines if line["msg"] == "request_started" and line["path"] == "/health"]
    finished = [line for line in lines if line["msg"] == "request" and line["path"] == "/health"]
    assert len(started) == 1 and len(finished) == 1
    assert started[0]["request_id"] == finished[0]["request_id"] == r.headers["X-Request-ID"]
    assert started[0]["at"] <= finished[0]["at"] and finished[0]["status"] == 200
    text = target.read_text(encoding="utf-8")
    assert "do-not-log" not in text and "secret" not in text and "Bearer" not in text


def test_off_by_default(make_client):
    client = make_client()
    client.get("/health")
    assert not any(getattr(h, "_codecoach_access_file", False) for h in access_log.handlers)
    assert not access_log.isEnabledFor(logging.DEBUG)

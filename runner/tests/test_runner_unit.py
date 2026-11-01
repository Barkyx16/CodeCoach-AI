import base64
import io
import tarfile
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sandbox import (
    EXIT_COMPILE_ERROR,
    RUN_MARKER,
    SandboxResult,
    _Capped,
    build_command,
    classify,
    pack_sources,
)
from tests.conftest import TOKEN, make_settings

FILES = {"Solution.java": "class Solution {}", "Main.java": "public final class Main {}"}


# --- command construction: every isolation control must be present ------------------------


def test_command_contains_every_isolation_flag():
    cmd = build_command(make_settings(), "cc-sbx-test")
    joined = " ".join(cmd)
    for flag in [
        "--runtime=runsc",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user 65534:65534",
        "--log-driver=none",
        "--memory=512m",
        "--memory-swap=512m",
        "--pids-limit=64",
        "--cpus=1.0",
        "--rm",
        "-i",
    ]:
        assert flag in joined, flag
    tmpfs = cmd[cmd.index("--tmpfs") + 1]
    assert tmpfs.startswith("/tmp:") and "noexec" in tmpfs and "nosuid" in tmpfs and "size=64m" in tmpfs
    assert "-v" not in cmd and "--volume" not in joined and "--mount" not in joined  # no host paths
    assert "--privileged" not in joined
    assert cmd[-1] == "codecoach-java-sandbox:21"


def test_runc_is_refused_unless_explicitly_allowed():
    with pytest.raises(ValueError, match="not an isolation boundary"):
        make_settings(sandbox_runtime="runc")
    assert make_settings(sandbox_runtime="runc", allow_insecure_runtime=True).sandbox_runtime == "runc"


def test_token_must_be_long():
    with pytest.raises(ValueError):
        make_settings(runner_token="short")


def test_sources_travel_as_base64_tar():
    packed = pack_sources(FILES)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(packed))) as tar:
        assert sorted(tar.getnames()) == ["Main.java", "Solution.java"]
        assert tar.extractfile("Solution.java").read().decode() == FILES["Solution.java"]


# --- classification --------------------------------------------------------------------------


def c(exit_code, stdout="", stderr="", **kw):
    return classify(
        exit_code,
        stdout,
        stderr,
        timed_out=kw.get("timed_out", False),
        truncated=kw.get("truncated", False),
        duration_ms=1,
    )


def test_classification():
    started = RUN_MARKER + "\n"
    assert c(0, stderr=started).status == "ok"
    assert c(1, stderr=started).status == "ok"  # learner exit codes are judged by the API
    assert c(EXIT_COMPILE_ERROR, stderr="Solution.java:1: error").status == "compile_error"
    assert c(EXIT_COMPILE_ERROR, stderr=started).status == "ok"  # System.exit(91) can't fake a compile error
    assert c(3, stdout="Terminating due to java.lang.OutOfMemoryError").status == "memory_limit"
    assert c(137, stderr=started).status == "memory_limit"
    assert c(137, timed_out=True).status == "timeout"
    assert c(0, truncated=True).status == "output_limit"
    assert c(125).status == "sandbox_error"  # docker itself failed
    assert c(90).status == "sandbox_error"


def test_run_marker_is_stripped_from_stderr():
    res = c(0, stderr=RUN_MARKER + "\nboom\n")
    assert res.run_started and res.stderr == "boom\n"


def test_capped_reader_keeps_limit_and_signals_once():
    calls = []
    cap = _Capped(limit=10)
    cap.pump(io.BytesIO(b"a" * 25), lambda: calls.append(1))
    assert bytes(cap.data) == b"a" * 10 and cap.overflowed and calls == [1]
    exact = _Capped(limit=10)
    exact.pump(io.BytesIO(b"b" * 10), lambda: calls.append(2))
    assert not exact.overflowed


# --- HTTP API with a fake sandbox --------------------------------------------------------------


class FakeSandbox:
    def __init__(self, gate: threading.Event | None = None):
        self.calls = []
        self.gate = gate

    def run(self, files, nonce, time_limit_s=None):
        self.calls.append((files, nonce, time_limit_s))
        if self.gate:
            self.gate.wait(5)
        return SandboxResult(
            status="ok",
            exit_code=0,
            stdout="out",
            stderr="",
            compile_output=None,
            run_started=True,
            output_truncated=False,
            duration_ms=12,
        )


def client(sandbox=None, **settings):
    app = create_app(make_settings(**settings), sandbox=sandbox or FakeSandbox(), cleanup=False)
    return TestClient(app)


AUTH = {"Authorization": f"Bearer {TOKEN}"}
BODY = {"files": FILES, "nonce": "0123456789abcdef"}


def test_run_requires_the_token():
    c_ = client()
    assert c_.post("/v1/run", json=BODY).status_code == 401
    assert c_.post("/v1/run", json=BODY, headers={"Authorization": "Bearer " + "x" * 40}).status_code == 401
    r = c_.post("/v1/run", json=BODY, headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_request_validation():
    c_ = client()
    extra = {**BODY, "files": {**FILES, "Evil.java": "x"}}
    assert c_.post("/v1/run", json=extra, headers=AUTH).status_code == 422
    missing = {**BODY, "files": {"Solution.java": "x"}}
    assert c_.post("/v1/run", json=missing, headers=AUTH).status_code == 422
    assert c_.post("/v1/run", json={**BODY, "nonce": "not-hex!"}, headers=AUTH).status_code == 422
    assert c_.post("/v1/run", json={**BODY, "time_limit_s": 999}, headers=AUTH).status_code == 422


def test_source_size_limit():
    c_ = client(max_source_bytes=1024)
    big = {**BODY, "files": {**FILES, "Solution.java": "x" * 2000}}
    assert c_.post("/v1/run", json=big, headers=AUTH).status_code == 413


def test_backpressure_when_at_capacity():
    gate = threading.Event()
    sandbox = FakeSandbox(gate)
    c_ = client(sandbox, max_concurrency=1)
    first = threading.Thread(target=lambda: c_.post("/v1/run", json=BODY, headers=AUTH))
    first.start()
    while not sandbox.calls:
        pass
    busy = c_.post("/v1/run", json=BODY, headers=AUTH)
    gate.set()
    first.join()
    assert busy.status_code == 503


def test_health_and_no_public_docs():
    c_ = client()
    assert c_.get("/health").json() == {"status": "ok"}
    assert c_.get("/docs").status_code == 404 and c_.get("/openapi.json").status_code == 404

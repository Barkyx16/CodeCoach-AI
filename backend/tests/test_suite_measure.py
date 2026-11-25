"""The suite's own measurement (Volume 13, prompt 9; tests/suite_measure.py, docs/CI.md): a test file
that leaves a test client entered or a database connection open is reported against that file, and
a tidy one isn't; a thread left running is listed at the end, and its stack is written while the
process waits for it to exit."""

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

LEAKY = """
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

_kept = []


def test_leaves_a_client_entered():
    client = TestClient(FastAPI())
    client.__enter__()  # never exited
    _kept.append(client)


def test_leaves_a_connection_open(tmp_path):
    connection = create_engine(f"sqlite:///{tmp_path}/x.db").connect()
    connection.execute(text("select 1"))
    _kept.append(connection)  # never closed
"""

TIDY = """
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


_kept = []


def test_closes_what_it_opens(tmp_path):
    with TestClient(FastAPI()) as client:
        pass
    _kept.append(client)  # still referenced, but exited: not open
    engine = create_engine(f"sqlite:///{tmp_path}/y.db")
    with engine.connect() as connection:
        connection.execute(text("select 1"))
    engine.dispose()
"""


def test_a_leaked_client_and_connection_are_reported_against_their_file(tmp_path):
    (tmp_path / "test_leaky.py").write_text(LEAKY)
    (tmp_path / "test_tidy.py").write_text(TIDY)
    out = tmp_path / "measure.json"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.suite_measure",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tmp_path),
            "-c",
            "/dev/null",
            str(tmp_path / "test_leaky.py"),
            str(tmp_path / "test_tidy.py"),
        ],
        cwd=BACKEND,
        env={**__import__("os").environ, "SUITE_MEASURE_OUT": str(out)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    files = {Path(f["file"]).name: f for f in json.loads(out.read_text())["files"]}
    assert files["test_leaky.py"]["clients_left_open"] == 1
    assert files["test_leaky.py"]["connections_left_open"] >= 1
    # Where it was opened: the test's own line.
    assert any(
        site.startswith("test_leaky.py:") and "in test_leaves_a_connection_open" in site
        for site in files["test_leaky.py"]["left_open_at"]
    )
    assert (files["test_tidy.py"]["clients_left_open"], files["test_tidy.py"]["connections_left_open"]) == (
        0,
        0,
    )
    assert "left open after a file's tests (clients, connections):" in run.stdout
    assert "test_leaky.py" in run.stdout.split("left open after a file's tests")[1]


LINGERING = """
import threading
import time


def keep_waiting():
    time.sleep(4)


def test_leaves_a_thread_running():
    threading.Thread(target=keep_waiting, name="left-running", daemon=False).start()
"""


def test_a_thread_left_running_is_listed_and_its_stack_written_while_the_process_exits(tmp_path):
    (tmp_path / "test_lingering.py").write_text(LINGERING)
    out, stacks = tmp_path / "measure.json", tmp_path / "stacks.txt"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.suite_measure",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tmp_path),
            "-c",
            "/dev/null",
            str(tmp_path / "test_lingering.py"),
        ],
        cwd=BACKEND,
        env={
            **__import__("os").environ,
            "SUITE_MEASURE_OUT": str(out),
            "SUITE_MEASURE_EXIT_STACKS": str(stacks),
            "SUITE_MEASURE_EXIT_EVERY": "1",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "left-running (waited for at exit)" in json.loads(out.read_text())["threads_at_end"]
    assert "threads still running: left-running (waited for at exit)" in run.stdout
    # Written while the interpreter waited for it: the thread's own frame is there.
    assert "in keep_waiting" in stacks.read_text()


APPS = """
pytest_plugins = ["tests.conftest"]


def test_one(client):
    assert client.get("/health").status_code == 200


def test_two(client):
    assert client.get("/health").status_code == 200
"""


def test_apps_made_through_the_fixtures_are_freed_once_their_tests_end(tmp_path):
    """The suite's largest leak (docs/CI.md, "Suite time and memory"): FastAPI's module-level caches
    kept every test's app alive. With conftest clearing them, none is alive at the end."""
    (tmp_path / "test_apps.py").write_text(APPS)
    out = tmp_path / "measure.json"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.suite_measure",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tmp_path),
            "-c",
            "/dev/null",
            str(tmp_path / "test_apps.py"),
        ],
        cwd=BACKEND,
        env={**__import__("os").environ, "SUITE_MEASURE_OUT": str(out)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "2 passed" in run.stdout
    assert json.loads(out.read_text())["apps_alive"] == 0

"""The real thing: API → worker → runner service (HTTP) → Docker + gVisor → verdict.

Starts runner/ as a real uvicorn process. Skipped unless Docker has the runsc runtime and the
codecoach-java-sandbox:21 image is built (CI's `sandbox` job sets both up).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.db.seed import SEED_DIR
from app.models import Problem
from app.services.judge.runner_client import HttpRunner
from app.worker import JudgeWorker
from tests.conftest import auth_headers, register

RUNNER_DIR = Path(__file__).resolve().parents[2] / "runner"
REFERENCE_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "reference"
TOKEN = "s" * 40


def _sandbox_ready() -> bool:
    if shutil.which("docker") is None or not RUNNER_DIR.exists():
        return False
    info = subprocess.run(
        ["docker", "info", "--format", "{{json .Runtimes}}"], capture_output=True, text=True
    )
    img = subprocess.run(["docker", "image", "inspect", "codecoach-java-sandbox:21"], capture_output=True)
    return info.returncode == 0 and "runsc" in info.stdout and img.returncode == 0


pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(not _sandbox_ready(), reason="needs Docker + gVisor + sandbox image"),
]


@pytest.fixture(scope="module")
def runner_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "RUNNER_TOKEN": TOKEN, "MAX_CONCURRENCY": "4", "WALL_TIMEOUT_S": "20"}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app_factory",
            "--factory",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=RUNNER_DIR,
        env=env,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(url + "/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("runner did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
def judge(make_client, runner_url):
    c = make_client(
        execution_enabled=True,
        runner_token=TOKEN,
        runner_url=runner_url,
        max_pending_per_user=50,
        submission_rate_limit_per_minute=100,
        judge_time_limit_s=8,
    )
    worker = JudgeWorker(c.app.state.session_factory, HttpRunner(runner_url, TOKEN), c.app.state.settings)
    headers = auth_headers(register(c))

    def run(slug: str, code: str) -> dict:
        sub = c.post("/api/v1/submissions", headers=headers, json={"problem_slug": slug, "source_code": code})
        assert sub.status_code == 202, sub.text
        assert worker.process_one()
        return c.get(f"/api/v1/submissions/{sub.json()['id']}", headers=headers).json()

    run.client = c
    return run


@pytest.mark.parametrize("slug", sorted(json.loads(p.read_text())["slug"] for p in SEED_DIR.glob("*.json")))
def test_every_reference_solution_passes_in_the_sandbox(judge, slug):
    done = judge(slug, (REFERENCE_DIR / f"{slug}.java").read_text())
    assert done["status"] == "PASSED", done
    assert done["result"]["passed_count"] == done["result"]["total_count"]


def test_starter_code_fails(judge):
    with judge.client.app.state.session_factory() as db:
        starter = db.scalar(select(Problem).where(Problem.slug == "two-sum")).starter_code
    done = judge("two-sum", starter)
    assert done["status"] == "FAILED" and done["result"]["passed_count"] == 0


def test_compile_error(judge):
    done = judge("two-sum", "class Solution { public int[] twoSum(int[] nums, int target) { return null } }")
    assert done["status"] == "COMPILE_ERROR"
    assert (
        "Solution.java" in done["result"]["stderr_excerpt"]
        and "/tmp/src" not in done["result"]["stderr_excerpt"]
    )


def test_infinite_loop_is_time_limited(judge):
    done = judge(
        "two-sum", "class Solution { public int[] twoSum(int[] nums, int target) { while (true) {} } }"
    )
    assert done["status"] == "TIME_LIMIT"


def test_runtime_exception_is_reported_per_test(judge):
    code = "class Solution { public int max(int[] nums) { return nums[nums.length]; } }"
    done = judge("find-largest-number", code)
    assert done["status"] == "FAILED"
    first = done["result"]["public_results"][0]
    assert first["exception"] == "ArrayIndexOutOfBoundsException" and first["exception_message"]


def test_memory_bomb(judge):
    code = (
        "import java.util.*; class Solution { public int max(int[] nums) {"
        " List<long[]> hog = new ArrayList<>(); while (true) hog.add(new long[1 << 20]); } }"
    )
    assert judge("find-largest-number", code)["status"] == "MEMORY_LIMIT"


def test_forgery_attempt_from_inside_the_sandbox(judge):
    code = (
        'class Solution { static { for (int i = 0; i < 7; i++) System.out.println("@@CC:@@ {\\"index\\": " + i + '
        '", \\"ok\\": true, \\"output\\": [0, 1]}"); System.setOut(new java.io.PrintStream(new java.io.ByteArrayOutputStream())); }'
        " public int[] twoSum(int[] nums, int target) { return new int[] {0, 1}; } }"
    )
    done = judge("two-sum", code)
    assert done["status"] == "FAILED"  # [0, 1] is right for some tests only, and forged lines were ignored
    assert 0 < done["result"]["passed_count"] < done["result"]["total_count"]

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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.db.seed import SEED_DIR
from app.models import Problem, SubmissionMode, SubmissionStatus
from app.models import TestVisibility as Visibility  # aliased: pytest would collect Test*
from app.services.judge.judge import Verdict, judge_submission
from app.services.judge.runner_client import HttpRunner, RunnerUnavailable
from app.worker import JudgeWorker
from tests.conftest import auth_headers, register

RUNNER_DIR = Path(__file__).resolve().parents[2] / "runner"
REFERENCE_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "reference"
TOKEN = "s" * 40
RUNNER_CONCURRENCY = 4


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
    env = {
        **os.environ,
        "RUNNER_TOKEN": TOKEN,
        "MAX_CONCURRENCY": str(RUNNER_CONCURRENCY),
        "WALL_TIMEOUT_S": "20",
    }
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
    for _ in range(600):  # up to ~60 s: the runner warms the sandbox up before it serves
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

    def run(slug: str, code: str, mode: str = "submit") -> dict:
        sub = c.post(
            "/api/v1/submissions",
            headers=headers,
            json={"problem_slug": slug, "source_code": code, "mode": mode},
        )
        assert sub.status_code == 202, sub.text
        assert worker.process_one()
        return c.get(f"/api/v1/submissions/{sub.json()['id']}", headers=headers).json()

    run.client = c
    run.headers = headers
    return run


SEED_PROBLEMS = {
    seed["slug"]: seed for seed in (json.loads(f.read_text()) for f in sorted(SEED_DIR.glob("*.json")))
}
JUDGE_TIME_LIMIT_S = 8  # same as the `judge` fixture


def _judge_reference(runner: HttpRunner, slug: str) -> Verdict:
    """The production judge (`judge_submission`) on a reference solution, minus the database."""
    seed = SEED_PROBLEMS[slug]
    tests = [
        SimpleNamespace(
            input=t["input"], expected_output=t["expected_output"], visibility=Visibility(t["visibility"])
        )
        for t in seed["tests"]
    ]
    submission = SimpleNamespace(
        mode=SubmissionMode.SUBMIT,
        source_code=(REFERENCE_DIR / f"{slug}.java").read_text(),
        problem=SimpleNamespace(signature=seed["signature"], test_cases=tests),
    )
    for attempt in range(10):
        try:
            return judge_submission(submission, runner, JUDGE_TIME_LIMIT_S)
        except RunnerUnavailable:  # at capacity: back off and retry, like the worker does
            time.sleep(0.5 * (attempt + 1))
    return judge_submission(submission, runner, JUDGE_TIME_LIMIT_S)


@pytest.fixture(scope="module")
def reference_verdicts(runner_url) -> dict[str, Verdict]:
    """Judge all references in the real sandbox, as many at once as the runner allows.

    One by one through the API (a fresh app and seeded database per problem) took ~5 s each,
    about half an hour for 300 problems. The API → worker path is covered by the tests below.
    """
    runner = HttpRunner(runner_url, TOKEN)
    try:
        with ThreadPoolExecutor(max_workers=RUNNER_CONCURRENCY) as pool:
            return dict(
                zip(
                    SEED_PROBLEMS, pool.map(lambda s: _judge_reference(runner, s), SEED_PROBLEMS), strict=True
                )
            )
    finally:
        runner.close()


@pytest.mark.parametrize("slug", sorted(SEED_PROBLEMS))
def test_every_reference_solution_passes_in_the_sandbox(reference_verdicts, slug):
    verdict = reference_verdicts[slug]
    assert verdict.status == SubmissionStatus.PASSED, (verdict.status, verdict.result)
    assert verdict.result.passed_count == verdict.result.total_count == len(SEED_PROBLEMS[slug]["tests"])


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


def _eval_samples() -> list[dict]:
    evals = Path(__file__).resolve().parents[1] / "evals"
    return [
        s
        for f in ("review_set.json", "holdout_set.json", "medium_set.json")
        for s in json.loads((evals / f).read_text())["samples"]
    ]


@pytest.mark.parametrize("sample", _eval_samples(), ids=lambda s: s["id"])
def test_eval_set_verdict_labels_match_the_real_judge(judge, sample):
    """The AI-eval ground truth is itself verified: every labelled sample is judged in gVisor."""
    done = judge(sample["problem"], sample["code"])
    assert done["status"] == sample["verdict"], (sample["id"], done["status"], done["result"])


# --- "Explain my failure" on real javac and JVM output -----------------------------------------
# (slug, code, expected verdict, expected cause, expected line_hint, text the headline must contain)
FAILURES = [
    (
        "find-largest-number",
        "class Solution {\n    public int max(int[] nums) {\n        int best = nums[0];\n"
        "        for (int x : nums) if (x > best) bset = x;\n        return best;\n    }\n}",
        "COMPILE_ERROR",
        "compile-error",
        4,
        "`bset`",
    ),
    (
        "contains-duplicate",
        "class Solution {\n    public boolean containsDuplicate(int[] nums) {\n"
        "        HashSet<Integer> seen = new HashSet<>();\n"
        "        for (int x : nums) if (!seen.add(x)) return true;\n        return false;\n    }\n}",
        "COMPILE_ERROR",
        "compile-error",
        3,
        "import",
    ),
    (
        "find-largest-number",
        "class Solution {\n    public int maximum(int[] nums) {\n        return 0;\n    }\n}",
        "COMPILE_ERROR",
        "compile-error",
        None,
        "signature",
    ),
    (
        "find-largest-number",
        "class Solution {\n    public int max(int[] nums) {\n        int best = Integer.MIN_VALUE;\n"
        "        for (int i = 0; i <= nums.length; i++) {\n            best = Math.max(best, nums[i]);\n"
        "        }\n        return best;\n    }\n}",
        "FAILED",
        "index-out-of-bounds",
        5,
        "out of range",
    ),
    (
        "climbing-stairs",
        "class Solution {\n    public int climbStairs(int n) {\n"
        "        return climbStairs(n - 1) + climbStairs(n - 2);\n    }\n}",
        "RUNTIME_ERROR",
        "recursion-depth",
        3,
        "stack overflow",
    ),
    (
        "first-unique-character",
        "import java.util.*;\nclass Solution {\n    public int firstUniqChar(String s) {\n"
        "        Map<Character, Integer> count = new HashMap<>();\n"
        "        for (char c : s.toCharArray()) count.put(c, count.get(c) + 1);\n"
        "        for (int i = 0; i < s.length(); i++) if (count.get(s.charAt(i)) == 1) return i;\n"
        "        return -1;\n    }\n}",
        "FAILED",
        "null-reference",
        5,
        "null",
    ),
    (
        "two-sum",
        "import java.util.*;\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n"
        "        Map<Integer, Integer> seen = new HashMap<>();\n"
        "        for (int i = 0; i < nums.length; i++) {\n"
        "            Integer j = seen.get(target - nums[i]);\n"
        "            if (j != null) return new int[] {i, j};\n            seen.put(nums[i], i);\n"
        "        }\n        return null;\n    }\n}",
        "FAILED",
        "wrong-answer",
        None,
        "reversed",
    ),
    (
        "binary-search",
        "class Solution {\n    public int search(int[] nums, int target) {\n"
        "        int lo = 0, hi = nums.length - 1;\n        while (lo <= hi) {\n"
        "            int mid = (lo + hi) / 2;\n            if (nums[mid] == target) return mid;\n"
        "            if (nums[mid] < target) lo = mid; else hi = mid;\n        }\n        return -1;\n    }\n}",
        "TIME_LIMIT",
        "time-limit",
        4,
        "infinite loop",
    ),
    (
        "binary-search",
        "class Solution {\n    public int search(int[] nums, int target) {\n"
        "        int lo = 0, hi = nums.length - 1;\n        while (lo < hi) {\n"
        "            int mid = lo + (hi - lo) / 2;\n            if (nums[mid] == target) return mid;\n"
        "            if (nums[mid] < target) lo = mid + 1; else hi = mid - 1;\n"
        "        }\n        return -1;\n    }\n}",
        "FAILED",
        "hidden-edge-case",
        None,
        "hidden edge case",
    ),
]


@pytest.mark.parametrize(
    ("slug", "code", "verdict", "cause", "line", "headline"),
    FAILURES,
    ids=[f"{f[0]}-{f[3]}" for f in FAILURES],
)
def test_explain_failure_on_real_judge_output(judge, slug, code, verdict, cause, line, headline):
    done = judge(slug, code)
    assert done["status"] == verdict, done
    c = judge.client
    r = c.post("/api/v1/ai/explain-failure", headers=judge.headers, json={"submission_id": done["id"]})
    assert r.status_code == 200, r.text
    e = r.json()["explanation"]
    assert e["cause"] == cause, e
    assert e["line_hint"] == line, e
    assert headline.lower() in e["headline"].lower(), e
    # Neither the submission result nor the explanation may contain a hidden test's input.
    with c.app.state.session_factory() as db:
        p = db.scalar(select(Problem).where(Problem.slug == slug))
        hidden = [t.input for t in p.test_cases if t.visibility.value == "hidden"]
    blob = json.dumps(done) + json.dumps(e)
    for h in hidden:
        for value in h.values():
            if isinstance(value, list) and len(value) >= 2:
                assert json.dumps(value) not in blob, f"hidden input {value} leaked"
                assert ", ".join(map(str, value)) not in blob, f"hidden input {value} leaked"


def test_run_mode_executes_public_tests_only_in_the_sandbox(judge):
    """Run: the reference solution passes exactly the public tests; nothing counts as solved."""
    done = judge("binary-search", (REFERENCE_DIR / "binary-search.java").read_text(), mode="run")
    assert done["status"] == "PASSED" and done["mode"] == "run"
    r = done["result"]
    assert r["total_count"] == r["passed_count"] == len(r["public_results"]) == 3
    assert r["hidden_total"] == 0
    assert judge.client.get("/api/v1/me/progress", headers=judge.headers).json()["solved"] == 0
    # A code bug is reported the same way as for a submission, with the line it threw on.
    bad = judge(
        "find-largest-number",
        "class Solution {\n    public int max(int[] nums) {\n        return nums[nums.length];\n    }\n}",
        mode="run",
    )
    assert bad["status"] == "FAILED" and bad["result"]["public_results"][0]["line"] == 3

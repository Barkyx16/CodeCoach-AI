"""Compile and run the repository's own reference solutions against every seeded test case.

Why: test data is only trustworthy if a known-good solution passes all of it. This catches
typos in expected outputs before a learner ever sees a wrong verdict.

Safety: this runs ONLY trusted code that is checked into this repository
(app/seed/reference/*.java). It is a developer and CI tool, not the submission runner, and it
must never be pointed at user-submitted code. See docs/security/threat-model.md.

Usage:  python scripts/verify_reference_solutions.py
"""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.judge.harness import build_driver, judge_cases  # noqa: E402

PROBLEMS_DIR = BACKEND_DIR / "app" / "seed" / "problems"
REFERENCE_DIR = BACKEND_DIR / "app" / "seed" / "reference"


def java_available() -> bool:
    return shutil.which("javac") is not None and shutil.which("java") is not None


def check_problem(problem_file: Path, timeout_s: float = 30.0) -> list[str]:
    """Return a list of human-readable failures (empty means every test passed)."""
    problem = json.loads(problem_file.read_text())
    slug = problem["slug"]
    reference = REFERENCE_DIR / f"{slug}.java"
    if not reference.exists():
        return [f"{slug}: missing reference solution {reference.name}"]

    tests = problem["tests"]
    driver = build_driver(problem["signature"], [t["input"] for t in tests])
    with tempfile.TemporaryDirectory(prefix=f"cc-ref-{slug}-") as tmp:
        work = Path(tmp)
        (work / "Solution.java").write_text(reference.read_text())
        (work / "Main.java").write_text(driver)
        compiled = subprocess.run(
            ["javac", "-d", str(work), str(work / "Solution.java"), str(work / "Main.java")],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if compiled.returncode != 0:
            return [f"{slug}: compile error\n{compiled.stderr[:2000]}"]
        nonce = secrets.token_hex(16)
        ran = subprocess.run(
            ["java", "-cp", str(work), "Main"],
            input=nonce + "\n",
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    outcomes = judge_cases([t["expected_output"] for t in tests], ran.stdout, nonce)
    failures = []
    for outcome in outcomes:
        if not outcome.passed:
            t = tests[outcome.index]
            failures.append(
                f"{slug} test #{outcome.index} ({t['visibility']}): input={t['input']} "
                f"expected={t['expected_output']!r} actual={outcome.actual!r} "
                f"exception={outcome.exception!r} missing={outcome.missing}"
            )
    return failures


def main() -> int:
    if not java_available():
        print("javac/java not found on PATH; install a JDK (17+) to run this check.")
        return 2
    files = sorted(PROBLEMS_DIR.glob("*.json"))
    all_failures: list[str] = []
    for f in files:
        failures = check_problem(f)
        status = "ok" if not failures else f"{len(failures)} failure(s)"
        print(f"{f.stem:40s} {status}")
        all_failures.extend(failures)
    if all_failures:
        print("\n".join(all_failures))
        return 1
    print(f"All {len(files)} reference solutions pass every test case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

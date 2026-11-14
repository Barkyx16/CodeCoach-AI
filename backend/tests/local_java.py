"""A Runner that compiles and runs the files with the local JDK: for tests of code paths whose
result depends on what Java actually does (test design's distinctions). Not a sandbox, and never
used by the app; tests that use it are skipped without a JDK (CI installs one)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from app.services.judge.runner_client import RunnerResult


def jdk_available() -> bool:
    return shutil.which("javac") is not None and shutil.which("java") is not None


class LocalJavaRunner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, files: dict[str, str], nonce: str, time_limit_s: float) -> RunnerResult:
        self.calls.append({"files": files, "nonce": nonce, "time_limit_s": time_limit_s})
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="cc-local-java-") as tmp:
            work = Path(tmp)
            for name, text in files.items():
                (work / name).write_text(text)
            compiled = subprocess.run(
                ["javac", "-d", str(work), *[str(work / n) for n in files]],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if compiled.returncode != 0:
                return RunnerResult(
                    "compile_error", compiled.returncode, "", "", compiled.stderr, False, False, 0
                )
            try:
                ran = subprocess.run(
                    ["java", "-cp", str(work), "Main"],
                    input=nonce + "\n",
                    capture_output=True,
                    text=True,
                    timeout=max(time_limit_s, 1.0) * 4,  # a JVM start on a busy machine isn't the code's time
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                return RunnerResult(
                    "timeout", None, out, "", None, True, False, int((time.monotonic() - started) * 1000)
                )
        return RunnerResult(
            "ok",
            ran.returncode,
            ran.stdout,
            ran.stderr,
            None,
            True,
            False,
            int((time.monotonic() - started) * 1000),
        )

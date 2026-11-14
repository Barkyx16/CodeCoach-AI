"""Run one untrusted Java submission inside a fresh, locked-down gVisor container.

Isolation layers (each one independently limits damage):

  --runtime=runsc            gVisor: syscalls are served by a user-space kernel, not the host's
  --network=none             no network interface at all (no exfiltration, no mining pools)
  --read-only                read-only root filesystem
  --tmpfs /tmp (size, noexec, nosuid)   the only writable place; capped; can't run dropped binaries
  --memory / --memory-swap   hard RAM cap, no swap
  --pids-limit               stops fork bombs
  --cpus                     CPU share cap
  --ulimit nofile/fsize      caps open files and file sizes
  --cap-drop=ALL             no Linux capabilities
  --security-opt=no-new-privileges   setuid binaries can't escalate
  --user 65534:65534         runs as "nobody"
  --log-driver=none          program output never lands on the host's disk
  wall-clock timeout         the container is killed (docker kill) when time is up
  output cap                 stdout/stderr are truncated and the run is killed on a flood

Source code reaches the container over stdin (base64 tar), so there are no bind mounts: nothing
from the host filesystem is visible inside the sandbox.
"""

from __future__ import annotations

import base64
import io
import logging
import subprocess
import tarfile
import threading
import time
import uuid
from dataclasses import dataclass, field

from app.config import RunnerSettings

logger = logging.getLogger("runner.sandbox")

EXIT_BAD_INPUT = 90
EXIT_COMPILE_ERROR = 91
EXIT_JVM_OOM = 3  # -XX:+ExitOnOutOfMemoryError
EXIT_SIGKILL = 137  # OOM killer or our docker kill
RUN_MARKER = "@@SANDBOX:RUN@@"
LABEL = "codecoach.sandbox=1"


@dataclass
class SandboxResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    compile_output: str | None
    run_started: bool
    output_truncated: bool
    duration_ms: int


def pack_sources(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, content in sorted(files.items()):
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o444
            tar.addfile(info, io.BytesIO(data))
    return base64.b64encode(buf.getvalue())


def build_command(settings: RunnerSettings, name: str) -> list[str]:
    return [
        settings.docker_bin,
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--label",
        LABEL,
        f"--runtime={settings.sandbox_runtime}",
        "--network=none",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={settings.tmpfs_mb}m,mode=1777",
        f"--memory={settings.memory_mb}m",
        f"--memory-swap={settings.memory_mb}m",
        f"--pids-limit={settings.pids_limit}",
        f"--cpus={settings.cpus}",
        "--ulimit",
        "nofile=256:256",
        "--ulimit",
        f"fsize={settings.tmpfs_mb * 1024 * 1024}",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user",
        "65534:65534",
        "--log-driver=none",
        "--env",
        f"HEAP_MB={settings.heap_mb}",
        settings.sandbox_image,
    ]


@dataclass
class _Capped:
    """Collects at most `limit` bytes from a stream and drains (discards) the rest."""

    limit: int
    data: bytearray = field(default_factory=bytearray)
    overflowed: bool = False

    def pump(self, stream, on_overflow) -> None:
        while chunk := stream.read(8192):
            room = self.limit - len(self.data)
            if room > 0:
                self.data += chunk[:room]
            if len(chunk) > room and not self.overflowed:
                self.overflowed = True
                on_overflow()


class DockerSandbox:
    def __init__(self, settings: RunnerSettings, popen=subprocess.Popen, clock=time.monotonic):
        self.settings = settings
        self._popen = popen
        self._clock = clock

    def run(self, files: dict[str, str], nonce: str, time_limit_s: float | None = None) -> SandboxResult:
        timeout = min(time_limit_s or self.settings.wall_timeout_s, self.settings.wall_timeout_s)
        name = f"cc-sbx-{uuid.uuid4().hex[:16]}"
        payload = nonce.encode() + b"\n" + pack_sources(files)
        start = self._clock()
        proc = self._popen(
            build_command(self.settings, name),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        killed = threading.Event()
        # Which limit stopped the run first. A flood triggers `docker kill`, which can take a few
        # seconds under gVisor; if the wall clock also runs out meanwhile, the flood still wins.
        first_limit: list[str] = []
        lock = threading.Lock()

        def kill(reason: str) -> None:
            with lock:
                if killed.is_set():
                    return
                killed.set()
                first_limit.append(reason)
            subprocess.run([self.settings.docker_bin, "kill", name], capture_output=True, check=False)

        out = _Capped(self.settings.output_limit_bytes)
        err = _Capped(self.settings.output_limit_bytes)
        readers = [
            threading.Thread(target=out.pump, args=(proc.stdout, lambda: kill("output")), daemon=True),
            threading.Thread(target=err.pump, args=(proc.stderr, lambda: kill("output")), daemon=True),
        ]
        for r in readers:
            r.start()
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass  # container exited early; the exit code tells us why

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill("timeout")
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        finally:
            for r in readers:
                r.join(timeout=5)
            subprocess.run([self.settings.docker_bin, "rm", "-f", name], capture_output=True, check=False)

        duration_ms = int((self._clock() - start) * 1000)
        timed_out = first_limit[:1] == ["timeout"]
        stdout = out.data.decode("utf-8", errors="replace")
        stderr = err.data.decode("utf-8", errors="replace")
        return classify(
            proc.returncode,
            stdout,
            stderr,
            timed_out=timed_out,
            truncated=out.overflowed or err.overflowed,
            duration_ms=duration_ms,
        )


def classify(
    exit_code: int | None, stdout: str, stderr: str, *, timed_out: bool, truncated: bool, duration_ms: int
) -> SandboxResult:
    run_started = RUN_MARKER in stderr
    compile_output = None
    if timed_out:
        status = "timeout"
    elif truncated:
        status = "output_limit"
    elif exit_code == EXIT_COMPILE_ERROR and not run_started:
        status, compile_output = "compile_error", stderr
    elif exit_code == EXIT_JVM_OOM and "OutOfMemoryError" in (stdout + stderr):
        # -XX:+ExitOnOutOfMemoryError prints its notice on stdout and exits with code 3.
        status = "memory_limit"
    elif exit_code == EXIT_SIGKILL:
        status = "memory_limit"  # killed by the cgroup OOM killer (we didn't time it out)
    elif exit_code == EXIT_BAD_INPUT or not run_started:
        # Learner code only runs after the entrypoint prints RUN_MARKER. Ending without it (and
        # without a compile error, timeout, output flood or OOM kill) means the code never ran:
        # Docker unreachable (exit 1), image missing or docker itself failing (125/126/127), or
        # a bad payload (90). Never the learner's fault, so the API retries it as infrastructure.
        status = "sandbox_error"
    else:
        status = "ok"  # includes non-zero exits from learner code; the API judges
    return SandboxResult(
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr.replace(RUN_MARKER + "\n", ""),
        compile_output=compile_output,
        run_started=run_started,
        output_truncated=truncated,
        duration_ms=duration_ms,
    )


def docker_reachable(settings: RunnerSettings, timeout_s: float = 3.0) -> bool:
    """True when the Docker daemon answers. Used by the readiness probe."""
    try:
        return (
            subprocess.run(
                [settings.docker_bin, "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                timeout=timeout_s,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def cleanup_stale(settings: RunnerSettings) -> int:
    """Remove sandbox containers left behind by a crash (called at startup)."""
    found = subprocess.run(
        [settings.docker_bin, "ps", "-aq", "--filter", f"label={LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    if found:
        subprocess.run([settings.docker_bin, "rm", "-f", *found], capture_output=True, check=False)
    return len(found)

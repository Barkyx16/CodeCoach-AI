"""Threat-model checks (blueprint §07) against the REAL sandbox: Docker + gVisor.

Each test submits deliberately hostile Java and asserts the control from docs/SECURITY.md §4
held. Marked `sandbox`; skipped automatically where gVisor isn't installed. CI runs them in a
dedicated job that installs gVisor.
"""

import pytest

from app.sandbox import DockerSandbox
from tests.conftest import make_settings, requires_sandbox

pytestmark = [pytest.mark.sandbox, requires_sandbox]

NONCE = "0123456789abcdef"

# A tiny driver: echoes the nonce it read from stdin, then calls Solution.go() once.
DRIVER = """
import java.io.*;
public final class Main {
    public static void main(String[] a) throws Exception {
        String nonce = new BufferedReader(new InputStreamReader(System.in)).readLine();
        PrintStream out = System.out;
        out.println("NONCE=" + nonce);
        String r;
        try { r = String.valueOf(Solution.go()); } catch (Throwable t) { r = "THREW " + t.getClass().getSimpleName() + ": " + t.getMessage(); }
        out.println("RESULT=" + r);
    }
}
"""


def solution(body: str) -> str:
    return (
        "import java.util.*; import java.io.*; import java.net.*; import java.nio.file.*;\n"
        "class Solution { static Object go() throws Exception { " + body + " } }"
    )


@pytest.fixture(scope="module")
def sandbox() -> DockerSandbox:
    return DockerSandbox(
        make_settings(wall_timeout_s=20, memory_mb=512, heap_mb=192, output_limit_bytes=64 * 1024)
    )


def run(sandbox, body: str, **kw):
    return sandbox.run({"Solution.java": solution(body), "Main.java": DRIVER}, NONCE, **kw)


def result_line(res) -> str:
    return next((line for line in res.stdout.splitlines() if line.startswith("RESULT=")), "")


def test_happy_path_and_nonce_delivery(sandbox):
    res = run(sandbox, "return 6 * 7;")
    assert res.status == "ok" and res.exit_code == 0 and res.run_started
    assert f"NONCE={NONCE}" in res.stdout and result_line(res) == "RESULT=42"


def test_runs_inside_gvisor_as_nobody(sandbox):
    res = run(sandbox, 'return System.getProperty("os.version") + "|" + System.getProperty("user.name");')
    assert result_line(res) == "RESULT=4.19.0-gvisor|nobody" or (
        "gvisor" in result_line(res) and "nobody" in result_line(res)
    )


def test_compile_error_is_reported_without_running(sandbox):
    res = sandbox.run({"Solution.java": "class Solution { int x = ; }", "Main.java": DRIVER}, NONCE)
    assert res.status == "compile_error" and not res.run_started
    assert "Solution.java" in (res.compile_output or "") and "error" in (res.compile_output or "")


def test_infinite_loop_hits_wall_clock_limit(sandbox):
    res = run(sandbox, "while (true) {}", time_limit_s=6)
    assert res.status == "timeout"
    assert res.duration_ms < 20_000


def test_memory_bomb_is_stopped(sandbox):
    res = run(sandbox, "List<long[]> hog = new ArrayList<>(); while (true) hog.add(new long[1 << 20]);")
    assert res.status == "memory_limit"


def test_fork_bomb_is_contained_by_pid_limit(sandbox):
    body = (
        "List<Process> ps = new ArrayList<>(); int n = 0;"
        'try { for (int i = 0; i < 500; i++) { ps.add(new ProcessBuilder("sleep", "30").start()); n++; } }'
        'catch (Throwable t) { return "stopped after " + n; } return "spawned " + n;'
    )
    res = run(sandbox, body, time_limit_s=15)
    assert res.status in ("ok", "timeout")
    line = result_line(res)
    assert "spawned 500" not in line  # the pids cgroup refused new processes


def test_no_network_access(sandbox):
    body = (
        'try (Socket s = new Socket()) { s.connect(new InetSocketAddress("1.1.1.1", 80), 2000); return "CONNECTED"; }'
        'catch (Exception e) { return "blocked " + e.getClass().getSimpleName(); }'
    )
    res = run(sandbox, body)
    assert result_line(res).startswith("RESULT=blocked")


def test_no_dns(sandbox):
    body = (
        'try { InetAddress.getByName("example.com"); return "RESOLVED"; }'
        'catch (Exception e) { return "blocked " + e.getClass().getSimpleName(); }'
    )
    assert result_line(run(sandbox, body)).startswith("RESULT=blocked")


def test_root_filesystem_is_read_only(sandbox):
    body = (
        'try { Files.writeString(Path.of("/opt/judge/run.sh"), "pwned"); return "WROTE"; }'
        'catch (Exception e) { return "denied " + e.getClass().getSimpleName(); }'
    )
    assert result_line(run(sandbox, body)).startswith("RESULT=denied")


def test_tmp_is_noexec(sandbox):
    body = (
        'Path p = Path.of("/tmp/x.sh"); Files.writeString(p, "#!/bin/sh\\necho ran\\n"); p.toFile().setExecutable(true);'
        'try { Process pr = new ProcessBuilder("/tmp/x.sh").start(); pr.waitFor(); return "EXEC exit=" + pr.exitValue(); }'
        'catch (Exception e) { return "denied " + e.getClass().getSimpleName(); }'
    )
    line = result_line(run(sandbox, body))
    assert line.startswith("RESULT=denied") or "exit=126" in line


def test_tmp_is_size_capped(sandbox):
    body = (
        "byte[] mb = new byte[1 << 20]; int written = 0;"
        'try (OutputStream o = Files.newOutputStream(Path.of("/tmp/big"))) { for (int i = 0; i < 1024; i++) { o.write(mb); written++; } }'
        'catch (Exception e) { return "stopped at " + written + "MB"; } return "wrote " + written + "MB";'
    )
    line = result_line(run(sandbox, body))
    assert line.startswith("RESULT=stopped at") and int(line.split()[2].rstrip("MB")) <= 64


def test_host_files_are_not_visible(sandbox, tmp_path_factory):
    """A canary file written on the host must not be visible inside the sandbox (no bind
    mounts), and the Docker socket must not be reachable."""
    import uuid
    from pathlib import Path

    canary = Path("/var/tmp") / f"cc-canary-{uuid.uuid4().hex}"
    canary.write_text("host secret")
    try:
        body = (
            f'boolean canary = Files.exists(Path.of("{canary}"));'
            'boolean sock = Files.exists(Path.of("/var/run/docker.sock")) || Files.exists(Path.of("/run/docker.sock"));'
            'return canary || sock ? "VISIBLE canary=" + canary + " sock=" + sock : "isolated";'
        )
        assert result_line(run(sandbox, body)) == "RESULT=isolated"
    finally:
        canary.unlink()


def test_no_secrets_in_environment(sandbox):
    res = run(sandbox, "return System.getenv().keySet().toString();")
    env = result_line(res)
    for leaked in ("TOKEN", "SECRET", "KEY", "PASSWORD", "DATABASE"):
        assert leaked not in env.upper()


def test_nonce_is_not_in_env_or_argv(sandbox):
    body = (
        'String cmd = ProcessHandle.current().info().commandLine().orElse("");'
        'return (System.getenv().toString() + cmd).contains("' + NONCE + '") ? "LEAKED" : "hidden";'
    )
    assert result_line(run(sandbox, body)) == "RESULT=hidden"


def test_output_flood_is_truncated_and_stopped(sandbox):
    res = run(sandbox, 'String s = "x".repeat(1000); while (true) System.out.println(s);')
    assert res.status == "output_limit" and res.output_truncated
    assert len(res.stdout.encode()) <= 64 * 1024


def test_each_run_starts_from_a_clean_sandbox(sandbox):
    run(sandbox, 'Files.writeString(Path.of("/tmp/leftover"), "secret from user A"); return "ok";')
    res = run(sandbox, 'return Files.exists(Path.of("/tmp/leftover")) ? "LEAKED" : "fresh";')
    assert result_line(res) == "RESULT=fresh"

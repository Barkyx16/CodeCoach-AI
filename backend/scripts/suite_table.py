"""Run the backend suite with its time and memory measured (Volume 13, prompt 9; docs/CI.md).

    python scripts/suite_table.py [--out run.json] [pytest arguments...]

Runs pytest with tests/suite_measure.py, prints the per-file table (the ten slowest files and the
ten largest memory growths, and anything left open), and records the run: wall time, the
interpreter's peak memory, how long the process took to exit after printing its summary, and the
pass, skip, xfail and failure counts. The same command on PostgreSQL: set TEST_DATABASE_URL (and
TEST_DATABASE_ADMIN_URL) as for the suite. Exits with pytest's exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
# Pytest's last line, with or without its ===== frame (-q drops it): "3373 passed, 46 skipped in 2836.30s".
SUMMARY = re.compile(r"\b\d+ (passed|failed|errors?)\b.* in ([\d.]+)s")
QUIET = {"-q", "--quiet", "-qq", "-qqq"}
COUNTS = re.compile(r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?|deselected)")


def _first_and_last(text: str, keep: int = 6000) -> str:
    dumps = [d for d in re.split(r"(?=^Timeout \()", text, flags=re.M) if d.strip()]
    if len(dumps) <= 2:
        return text[: 2 * keep]
    return f"{dumps[0][:keep]}\n... {len(dumps) - 2} more ...\n{dumps[-1][:keep]}"


def table(record: dict, top: int = 10) -> str:
    files = record["files"]
    lines = [
        f"wall {record['wall_seconds']:.0f} s, peak RSS {record['peak_rss_mb'] or 0:.0f} MB, exit after the summary "
        f"{record['exit_delay_seconds'] if record['exit_delay_seconds'] is not None else '?'} s, apps alive at the end "
        f"{record['apps_alive']}",
        f"counts: {record['counts']}; the measurement's own garbage collections "
        f"{record.get('measure_gc_seconds') if record.get('measure_gc_seconds') is not None else '?'} s",
        "threads still running at the end: " + (", ".join(record.get("threads_at_end") or []) or "none"),
        "",
        f"{'seconds':>8} {'setup':>7} {'tests':>5}  slowest files",
    ]
    for f in sorted(files, key=lambda f: -f["seconds"])[:top]:
        lines.append(f"{f['seconds']:8.1f} {f['setup_seconds']:7.1f} {f['tests']:5}  {f['file']}")
    if files and files[0].get("objects_after"):
        lines += [
            "",
            f"live Python objects after the first file {files[0]['objects_after']:,}, after the last "
            f"{files[-1]['objects_after']:,}",
        ]
    lines += ["", f"{'MB':>8}  largest memory growth"]
    for f in sorted(files, key=lambda f: -f["growth_mb"])[:top]:
        lines.append(f"{f['growth_mb']:8.1f}  {f['file']}")
    leaky = [f for f in files if f["clients_left_open"] > 0 or f["connections_left_open"] > 0]
    lines += ["", "left open after a file (clients, connections):" + ("" if leaky else " none")]
    lines += [f"{f['clients_left_open']:8} {f['connections_left_open']:5}  {f['file']}" for f in leaky]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="suite-run.json", help="where to write the run's record")
    known, pytest_args = parser.parse_known_args(argv)
    # It already runs pytest with -q; one more would hide pytest's summary line, and with it the
    # counts and the exit delay (Volume 16, prompt 1). Dropped, and said.
    quiet = [a for a in pytest_args if a in QUIET]
    pytest_args = [a for a in pytest_args if a not in QUIET]
    if quiet:
        print(
            f"suite_table runs pytest with -q already; ignoring {' '.join(quiet)} (it would hide the summary line)"
        )
    measure = Path(tempfile.mkstemp(suffix=".json")[1])
    stacks = Path(tempfile.mkstemp(suffix=".txt")[1])
    env = {**os.environ, "SUITE_MEASURE_OUT": str(measure), "SUITE_MEASURE_EXIT_STACKS": str(stacks)}
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "tests.suite_measure",
        "-q",
        "-p",
        "no:cacheprovider",
        *pytest_args,
    ]
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    summary_at = None
    pytest_seconds = None
    counts: dict[str, int] = {}
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        if found := SUMMARY.search(line.strip()):
            summary_at = time.monotonic()
            pytest_seconds = float(found.group(2))
            counts = {
                kind.rstrip("s") if kind.startswith("error") else kind: int(n)
                for n, kind in COUNTS.findall(line)
            }
    code = proc.wait()
    ended = time.monotonic()
    data = json.loads(measure.read_text()) if measure.exists() and measure.stat().st_size else {"files": []}
    measure.unlink(missing_ok=True)
    exit_stacks = stacks.read_text(errors="replace") if stacks.exists() else ""
    stacks.unlink(missing_ok=True)
    counts_from = "summary"
    if not counts:  # no summary line (an interrupted run): the plugin's own per-file outcomes
        counts_from = "plugin"
        for f in data.get("files", []):
            for kind, n in (f.get("outcomes") or {}).items():
                counts[kind] = counts.get(kind, 0) + n
    record = {
        "wall_seconds": round(ended - started, 1),
        "exit_delay_seconds": round(ended - summary_at, 1) if summary_at else None,
        "pytest_seconds": pytest_seconds,
        "peak_rss_mb": data.get("peak_rss_mb"),
        "apps_alive": data.get("apps_alive"),
        "clients_left_open": data.get("clients_left_open"),
        "measure_gc_seconds": data.get("measure_gc_seconds"),
        "threads_at_end": data.get("threads_at_end"),
        # Each thread's stack, every few seconds while the process was exiting (empty: it exited
        # before the first). The first and last are kept: what it began with and what it ended on.
        "exit_stacks": _first_and_last(exit_stacks),
        "counts": counts,
        "counts_from": counts_from,
        "database": "postgresql" if os.environ.get("TEST_DATABASE_URL") else "sqlite",
        "files": data.get("files", []),
    }
    Path(known.out).write_text(json.dumps(record, indent=1))
    print("\n" + table(record))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

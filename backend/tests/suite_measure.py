"""Where the backend suite spends time and memory (Volume 13, prompt 9; docs/CI.md, "Suite time and
memory").

A pytest plugin, off unless asked for: `pytest -p tests.suite_measure` (scripts/suite_table.py runs
it so). For each test file it records the wall time, the time spent setting tests up (fixtures), the
process's resident memory before and after, the live Python objects after, and what its tests left
behind: test clients still
entered, database connections still open, and apps still alive after a garbage collection. At the
end it lists the threads still running (a non-daemon one keeps the process from exiting), and with
SUITE_MEASURE_EXIT_STACKS=<file> it writes every thread's stack to that file every few seconds after
the last hook, so whatever the interpreter is doing while it exits is on record. The time its own
garbage collections take (between files) is counted apart, so it isn't charged to a file or
mistaken for the suite's. The numbers go to SUITE_MEASURE_OUT (default .suite-measure.json) and a
short table is printed after the summary. It never changes, skips or reorders a test.
"""

from __future__ import annotations

import faulthandler
import gc
import json
import os
import resource
import sys
import threading
import time
import weakref
from collections import Counter
from dataclasses import asdict, dataclass, field

import pytest
from sqlalchemy import event
from sqlalchemy.pool import Pool
from starlette.testclient import TestClient

_PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def rss_mb() -> float:
    """Resident memory now, MB (Linux /proc; elsewhere the peak so far)."""
    try:
        with open("/proc/self/statm", encoding="ascii") as f:
            return int(f.read().split()[1]) * _PAGE / 1e6
    except OSError:
        return peak_mb()


def peak_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1e6 if os.uname().sysname == "Darwin" else peak / 1e3  # bytes on macOS, KB on Linux


# --- what tests leave open ---------------------------------------------------------------------

_entered: weakref.WeakSet[TestClient] = weakref.WeakSet()
_apps: weakref.WeakSet = weakref.WeakSet()
_connections = {"open": 0}
_opened_at: dict[int, str] = {}  # id of each open DBAPI connection -> where it was opened
_TESTS = os.sep + "tests" + os.sep
_APP = os.sep + "app" + os.sep


def _where() -> str:
    """The nearest test frame that led here (else the nearest app frame): where a connection was opened."""
    frame = sys._getframe(2)
    app_site = None
    while frame is not None:
        name = frame.f_code.co_filename
        base = os.path.basename(name)
        if (_TESTS in name or base.startswith("test_")) and base != "suite_measure.py":
            short = name.split(_TESTS, 1)[1] if _TESTS in name else base
            return f"{short}:{frame.f_lineno} in {frame.f_code.co_name}"
        if app_site is None and _APP in name:
            app_site = f"app/{name.split(_APP, 1)[1]}:{frame.f_lineno} in {frame.f_code.co_name}"
        frame = frame.f_back
    return app_site or "outside the tests and the app"


_enter, _exit = TestClient.__enter__, TestClient.__exit__


def _tracked_enter(self, *a, **k):
    _entered.add(self)
    _apps.add(self.app)
    return _enter(self, *a, **k)


def _tracked_exit(self, *a, **k):
    _entered.discard(self)
    return _exit(self, *a, **k)


TestClient.__enter__ = _tracked_enter  # type: ignore[method-assign]
TestClient.__exit__ = _tracked_exit  # type: ignore[method-assign]


@event.listens_for(Pool, "connect")
def _connect(dbapi_connection, *_a) -> None:
    _connections["open"] += 1
    _opened_at[id(dbapi_connection)] = _where()


@event.listens_for(Pool, "close")
def _close(dbapi_connection, *_a) -> None:
    _connections["open"] -= 1
    _opened_at.pop(id(dbapi_connection), None)


@event.listens_for(Pool, "close_detached")
def _close_detached(dbapi_connection, *_a) -> None:
    _connections["open"] -= 1
    _opened_at.pop(id(dbapi_connection), None)


@dataclass
class FileStats:
    file: str
    tests: int = 0
    seconds: float = 0.0
    setup_seconds: float = 0.0
    rss_before_mb: float = 0.0
    rss_after_mb: float = 0.0
    clients_left_open: int = 0
    connections_left_open: int = 0
    apps_alive: int = 0
    # Live Python objects after the file's collection: flat while resident memory rises means the
    # allocator kept freed memory, not that something leaked.
    objects_after: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)
    left_open_at: dict[str, int] = field(default_factory=dict)  # where they were opened, and how many

    @property
    def growth_mb(self) -> float:
        return round(self.rss_after_mb - self.rss_before_mb, 1)


class SuiteMeasure:
    def __init__(self) -> None:
        self.files: dict[str, FileStats] = {}
        self.current: FileStats | None = None
        self.started = time.monotonic()
        self.connections_at_start = 0
        self.clients_at_start = 0
        self.open_at_start: set[int] = set()
        self.gc_seconds = 0.0  # this plugin's own collections, between files

    def _collect(self) -> None:
        t0 = time.monotonic()
        gc.collect()
        self.gc_seconds += time.monotonic() - t0

    def _close_file(self) -> None:
        f = self.current
        if f is None:
            return
        self._collect()
        f.rss_after_mb = round(rss_mb(), 1)
        f.clients_left_open = len(_entered) - self.clients_at_start
        f.connections_left_open = _connections["open"] - self.connections_at_start
        f.left_open_at = dict(
            Counter(site for key, site in _opened_at.items() if key not in self.open_at_start)
        )
        f.apps_alive = len(_apps)
        f.objects_after = len(gc.get_objects())
        self.current = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        path = item.nodeid.split("::", 1)[0]
        if self.current is None or self.current.file != path:
            self._close_file()
            self._collect()
            self.connections_at_start = _connections["open"]
            self.open_at_start = set(_opened_at)
            self.clients_at_start = len(_entered)
            self.current = self.files.setdefault(path, FileStats(file=path, rss_before_mb=round(rss_mb(), 1)))
        t0 = time.monotonic()
        yield
        self.current.tests += 1
        self.current.seconds += time.monotonic() - t0

    def pytest_runtest_logreport(self, report) -> None:
        if self.current is None:
            return
        if report.when == "setup":
            self.current.setup_seconds += report.duration
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            outcome = "xfailed" if hasattr(report, "wasxfail") and report.skipped else report.outcome
            if report.when == "setup" and outcome == "failed":
                outcome = "error"  # pytest's own word for a test that couldn't be set up
            self.current.outcomes[outcome] = self.current.outcomes.get(outcome, 0) + 1

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        self._close_file()
        out = os.environ.get("SUITE_MEASURE_OUT", ".suite-measure.json")
        record = {
            "seconds": round(time.monotonic() - self.started, 1),
            "peak_rss_mb": round(peak_mb(), 1),
            "rss_at_end_mb": round(rss_mb(), 1),
            "clients_left_open": len(_entered),
            "apps_alive": len(_apps),
            "measure_gc_seconds": round(self.gc_seconds, 1),
            "threads_at_end": threads_running(),
            "files": [
                {
                    **asdict(f),
                    "seconds": round(f.seconds, 2),
                    "setup_seconds": round(f.setup_seconds, 2),
                    "growth_mb": f.growth_mb,
                }
                for f in self.files.values()
            ],
        }
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=1)

    def pytest_terminal_summary(self, terminalreporter) -> None:
        files = list(self.files.values())
        tr = terminalreporter
        tr.section("suite time and memory (tests/suite_measure.py)")
        tr.write_line(
            f"peak RSS {peak_mb():.0f} MB, RSS now {rss_mb():.0f} MB, apps still alive {len(_apps)}, "
            f"this plugin's own garbage collections {self.gc_seconds:.0f} s"
        )
        tr.write_line("threads still running: " + (", ".join(threads_running()) or "none"))
        tr.write_line("slowest files (s, of which setting up):")
        for f in sorted(files, key=lambda f: -f.seconds)[:10]:
            tr.write_line(f"  {f.seconds:7.1f} {f.setup_seconds:7.1f}  {f.file} ({f.tests})")
        tr.write_line("largest memory growth (MB):")
        for f in sorted(files, key=lambda f: -f.growth_mb)[:10]:
            tr.write_line(f"  {f.growth_mb:7.1f}  {f.file}")
        leaky = [f for f in files if f.clients_left_open > 0 or f.connections_left_open > 0]
        tr.write_line("left open after a file's tests (clients, connections):" + ("" if leaky else " none"))
        for f in leaky:
            tr.write_line(f"  {f.clients_left_open} {f.connections_left_open}  {f.file}")
            for site, n in sorted(f.left_open_at.items()):
                tr.write_line(f"        {n} opened at {site}")


def threads_running() -> list[str]:
    """Every thread but this one, named, and whether the interpreter waits for it at exit."""
    return [
        f"{t.name} ({'daemon' if t.daemon else 'waited for at exit'})"
        for t in threading.enumerate()
        if t is not threading.main_thread()
    ]


_exit_stacks: list = []


def pytest_configure(config) -> None:
    config.pluginmanager.register(SuiteMeasure(), "suite-measure")


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config) -> None:
    """The last hook: from here on, the process is exiting. Every few seconds until it has, write
    each thread's stack (faulthandler, so it works while the interpreter is finalizing)."""
    path = os.environ.get("SUITE_MEASURE_EXIT_STACKS")
    if path:
        fh = open(path, "w", encoding="utf-8")  # noqa: SIM115 - kept open until the process ends
        _exit_stacks.append(fh)
        faulthandler.dump_traceback_later(
            float(os.environ.get("SUITE_MEASURE_EXIT_EVERY", "3")), repeat=True, file=fh
        )

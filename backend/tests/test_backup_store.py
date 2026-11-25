"""The backup folder: retention keeps the right backups and deletes only what it says it will; the
health check catches a missed night, a damaged file and an unreadable manifest. Plain files
only (fake encrypted bytes with real manifests), so this runs everywhere. tests/test_backup.py
covers making and restoring real backups."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.db.backup import major_of
from app.db.backup_store import check, prune, retention, scan

BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 8, 3, 30, tzinfo=UTC)


def make(folder: Path, when: datetime, payload: bytes | None = None, manifest: bool = True) -> str:
    """One backup pair as backup-database names it, with a manifest that matches the bytes."""
    name = "codecoach-" + when.strftime("%Y%m%dT%H%M%SZ")
    data = payload if payload is not None else os.urandom(64)
    (folder / f"{name}.dump.age").write_bytes(data)
    if manifest:
        (folder / f"{name}.manifest.json").write_text(
            json.dumps(
                {
                    "format": "codecoach-backup/1",
                    "created_at": when.isoformat(),
                    "dump_file": f"{name}.dump.age",
                    "encrypted_sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        )
    return name


def nightly(folder: Path, days: int, last: datetime = NOW) -> list[str]:
    """`days` nightly backups ending at `last`, newest first."""
    return [make(folder, last - timedelta(days=d)) for d in range(days)]


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    # No database settings are needed: these commands only read the folder.
    return subprocess.run(
        [sys.executable, "-m", "app.cli", *args], cwd=BACKEND, capture_output=True, text=True, timeout=60
    )


def test_retention_keeps_the_newest_of_each_recent_day_week_and_month(tmp_path):
    names = nightly(tmp_path, 120)  # four months of nightly backups
    plan = retention(scan(tmp_path)[0], now=NOW)
    kept = {s.name: why for s, why in plan.keep.items()}

    assert kept[names[0]][0] == "newest"
    days = [n for n, why in kept.items() if "daily" in why]
    assert sorted(days, reverse=True) == names[:7]  # the last 7 nights
    weeks = sorted({s.stamp.isocalendar()[:2] for s, why in plan.keep.items() if "weekly" in why})
    assert len(weeks) == 4
    months = sorted({(s.stamp.year, s.stamp.month) for s, why in plan.keep.items() if "monthly" in why})
    assert months == [(2026, 9), (2026, 10), (2026, 11)]
    # The newest in each month is the one kept for it: 30 Sep and 31 Oct.
    monthly = sorted(s.stamp.date().isoformat() for s, why in plan.keep.items() if "monthly" in why)
    assert monthly == ["2026-09-30", "2026-10-31", "2026-11-08"]
    assert len(plan.keep) + len(plan.delete) == 120
    assert len(plan.keep) <= 1 + 7 + 4 + 3


def test_backups_that_stop_never_expire_by_time_alone(tmp_path):
    """Retention counts backups, not the calendar: weeks without a new backup delete nothing, and
    the last 7 nights before backups stopped are all still there."""
    names = nightly(tmp_path, 10, last=NOW - timedelta(days=40))
    plan = retention(scan(tmp_path)[0], now=NOW)
    kept = {s.name for s in plan.keep}
    assert set(names[:7]) <= kept
    # Of the 3 older ones, only the newest of an ISO week or a month stays.
    assert all(
        any(r in ("weekly", "monthly") for r in why)
        for s, why in plan.keep.items()
        if s.name not in names[:7]
    )


def test_a_dry_run_deletes_nothing_and_apply_deletes_exactly_the_plan(tmp_path):
    nightly(tmp_path, 30)
    half = make(tmp_path, NOW - timedelta(days=90), manifest=False)  # a dump without its manifest
    (tmp_path / "codecoach-by-hand.dump.age").write_bytes(b"x")  # named by hand
    (tmp_path / "notes.txt").write_text("not a backup")
    before = sorted(p.name for p in tmp_path.iterdir())

    dry = prune(tmp_path, now=NOW)
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert dry.delete and [s.name for s in dry.held] == [half]
    assert {p.name for p in dry.other} == {"codecoach-by-hand.dump.age", "notes.txt"}

    done = prune(tmp_path, apply=True, now=NOW)
    assert [s.name for s in done.delete] == [s.name for s in dry.delete]
    left = {p.name for p in tmp_path.iterdir()}
    for s in done.delete:
        assert f"{s.name}.dump.age" not in left and f"{s.name}.manifest.json" not in left
    for s in done.keep:
        assert {f"{s.name}.dump.age", f"{s.name}.manifest.json"} <= left
    assert {"codecoach-by-hand.dump.age", "notes.txt", f"{half}.dump.age"} <= left
    assert prune(tmp_path, apply=True, now=NOW).delete == []  # a second run has nothing left to do


def test_retention_refuses_negative_counts_and_keeps_a_lone_backup(tmp_path):
    only = make(tmp_path, NOW)
    with pytest.raises(ValueError):
        retention(scan(tmp_path)[0], daily=-1, now=NOW)
    with pytest.raises(ValueError, match="at least 1"):  # a typo can't shrink the set to one backup
        retention(scan(tmp_path)[0], daily=0, now=NOW)
    plan = retention(scan(tmp_path)[0], daily=1, weekly=0, monthly=0, within=timedelta(0), now=NOW)
    assert [s.name for s in plan.keep] == [only]
    assert plan.delete == []  # the newest is always kept


def test_a_second_backup_the_same_day_survives_and_a_named_one_is_never_pruned(tmp_path):
    """A backup made by hand before an upgrade must outlive the next scheduled run that day."""
    nightly(tmp_path, 10)
    by_hand = make(tmp_path, NOW - timedelta(hours=3))  # a few hours before the newest
    (tmp_path / "pre-upgrade-20261101.dump.age").write_bytes(b"x")  # backup-database --name
    (tmp_path / "pre-upgrade-20261101.manifest.json").write_text("{}")
    plan = prune(tmp_path, apply=True, now=NOW)
    assert plan.keep[next(s for s in plan.keep if s.name == by_hand)] == ["recent"]
    assert (tmp_path / "pre-upgrade-20261101.dump.age").exists()

    # A day later the extra one is past the 24 hours, and only the newest of its day stays.
    later = make(tmp_path, NOW + timedelta(days=1))
    plan = prune(tmp_path, apply=True, now=NOW + timedelta(days=1))
    assert by_hand not in {s.name for s in plan.keep} and later in {s.name for s in plan.keep}
    assert (tmp_path / "pre-upgrade-20261101.dump.age").exists()


def test_the_check_passes_for_a_fresh_intact_backup(tmp_path):
    nightly(tmp_path, 3)
    health = check(tmp_path, now=NOW + timedelta(hours=2))
    assert health.ok, health.problems
    assert any("2.0 h old" in n for n in health.notes)


def test_the_check_fails_for_a_missed_night_a_damaged_file_or_an_unreadable_manifest(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not check(empty, now=NOW).ok

    old = tmp_path / "old"
    old.mkdir()
    nightly(old, 3, last=NOW - timedelta(hours=30))
    health = check(old, now=NOW)
    assert not health.ok and "30 h old" in health.problems[0]

    damaged = tmp_path / "damaged"
    damaged.mkdir()
    name = nightly(damaged, 2)[0]
    dump = damaged / f"{name}.dump.age"
    dump.write_bytes(dump.read_bytes()[:-10])  # a truncated copy
    health = check(damaged, now=NOW)
    assert not health.ok and "doesn't match its manifest" in health.problems[0]

    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    name = nightly(unreadable, 1)[0]
    (unreadable / f"{name}.manifest.json").write_text("{not json")
    assert not check(unreadable, now=NOW).ok


def test_check_all_reads_every_backup_and_finds_an_older_damaged_one(tmp_path):
    names = nightly(tmp_path, 4)
    older = tmp_path / f"{names[2]}.dump.age"
    older.write_bytes(b"damaged")
    assert check(tmp_path, now=NOW).ok  # only the newest by default
    health = check(tmp_path, verify_all=True, now=NOW)
    assert not health.ok and names[2] in health.problems[0]


def test_the_commands_exit_nonzero_for_a_scheduler_and_dry_run_by_default(tmp_path):
    nightly(tmp_path, 20, last=datetime.now(UTC) - timedelta(minutes=5))
    ok = cli("check-backups", "--dir", str(tmp_path))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "OK" in ok.stdout and "Not proof of recovery" in ok.stdout

    stale = cli("check-backups", "--dir", str(tmp_path), "--max-age-hours", "0.01")
    assert stale.returncode == 1 and "FAIL" in stale.stdout

    count = len(list(tmp_path.iterdir()))
    dry = cli("prune-backups", "--dir", str(tmp_path))
    assert dry.returncode == 0 and "Dry run" in dry.stdout
    assert len(list(tmp_path.iterdir())) == count

    applied = cli("prune-backups", "--dir", str(tmp_path), "--apply")
    assert applied.returncode == 0 and "Deleted" in applied.stdout
    assert len(list(tmp_path.iterdir())) < count

    missing = cli("check-backups", "--dir", str(tmp_path / "nope"))
    assert missing.returncode == 1
    assert cli("prune-backups").returncode == 2
    # A hand-made name is checked before anything connects or writes.
    bad = cli("backup-database", "--out", str(tmp_path), "--recipients", "r.txt", "--name", "../escape")
    assert bad.returncode == 2 and "--name" in bad.stdout


def test_versions_are_read_from_the_tools_own_output():
    assert major_of("pg_dump (PostgreSQL) 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)") == 16
    assert major_of("pg_restore (PostgreSQL) 17.6 (Debian 17.6-0+deb13u1)") == 17
    assert major_of("pg_dump (PostgreSQL) 16.4 (Debian 16.4-1.pgdg130+1)") == 16
    assert major_of("not a version") is None


def test_the_backup_image_pins_the_compose_servers_major_version():
    """Debian's postgresql-client is a newer major than the server: its backups of a 16 server
    could only be restored into 17 or newer. The image pins the server's major instead."""
    root = BACKEND.parent
    server = re.search(r"image: postgres:(\d+)", (root / "deploy/docker-compose.production.yml").read_text())
    pinned = re.search(r"ARG PG_MAJOR=(\d+)", (root / "backend/Dockerfile").read_text())
    assert server and pinned and server.group(1) == pinned.group(1)


# --- The boundaries (docs/BACKUP.md "Retention contract") ------------------------------------


def stamp_names(plan, attr="keep"):
    return {s.name for s in getattr(plan, attr)}


def test_the_24_hour_window_is_inclusive_at_exactly_24_hours():
    for offset, kept in (
        (timedelta(hours=24) - timedelta(seconds=1), True),
        (timedelta(hours=24), True),
        (timedelta(hours=24) + timedelta(seconds=1), False),
    ):
        folder = Path(tempfile.mkdtemp())
        # Same calendar day as the newest is avoided, so only the window can keep it.
        newest = make(folder, NOW)
        older = make(folder, NOW - offset)
        plan = retention(scan(folder)[0], daily=1, weekly=0, monthly=0, now=NOW)
        assert newest in stamp_names(plan)
        assert (older in stamp_names(plan)) is kept, offset


def test_a_backup_dated_in_the_future_is_held_and_cant_hide_missed_nights(tmp_path):
    """Before: one backup stamped by a wrong clock made the check say OK forever (negative age)."""
    real = make(tmp_path, NOW - timedelta(days=5))
    future = make(tmp_path, NOW + timedelta(days=400))
    plan = retention(scan(tmp_path)[0], now=NOW)
    assert future in {s.name for s in plan.held} and "future" in next(iter(plan.held.values()))
    assert next(iter(plan.keep)).name == real  # the anchor is the newest *usable* backup
    health = check(tmp_path, now=NOW)
    assert not health.ok
    assert any("future" in p for p in health.problems) and any("120 h old" in p for p in health.problems)
    # A few minutes of clock skew between machines is tolerated.
    skewed = make(tmp_path, NOW + timedelta(minutes=5))
    assert next(iter(retention(scan(tmp_path)[0], now=NOW).keep)).name == skewed


def test_partial_or_unreadable_artifacts_are_held_never_deleted_and_never_the_anchor(tmp_path):
    nightly(tmp_path, 20)
    newest = "codecoach-" + (NOW + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
    # A newer pair whose dump is shorter than the manifest says: an interrupted copy.
    data = os.urandom(64)
    (tmp_path / f"{newest}.dump.age").write_bytes(data[:40])
    (tmp_path / f"{newest}.manifest.json").write_text(
        json.dumps(
            {
                "format": "codecoach-backup/1",
                "created_at": (NOW + timedelta(hours=1)).isoformat(),
                "dump_file": f"{newest}.dump.age",
                "encrypted_sha256": hashlib.sha256(data).hexdigest(),
                "encrypted_bytes": 64,
            }
        )
    )
    garbled = make(tmp_path, NOW - timedelta(days=30))
    (tmp_path / f"{garbled}.manifest.json").write_text("{not json")
    plan = prune(tmp_path, apply=True, now=NOW + timedelta(hours=2))
    assert {newest, garbled} <= {s.name for s in plan.held}
    assert next(iter(plan.keep)).name != newest
    assert (tmp_path / f"{newest}.dump.age").exists() and (tmp_path / f"{garbled}.dump.age").exists()
    health = check(tmp_path, now=NOW + timedelta(hours=2))
    assert not health.ok and any(newest in p and "size" in p for p in health.problems)


def test_nothing_is_deleted_when_the_newest_backup_fails_its_hash(tmp_path):
    names = nightly(tmp_path, 30)
    newest = tmp_path / f"{names[0]}.dump.age"
    newest.write_bytes(os.urandom(64))  # same size, different bytes: only the hash can tell
    before = sorted(p.name for p in tmp_path.iterdir())
    plan = prune(tmp_path, apply=True, now=NOW)
    assert plan.refused and "doesn't match its manifest" in plan.refused
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    out = cli("prune-backups", "--dir", str(tmp_path), "--apply")
    assert out.returncode == 1 and "Nothing deleted" in out.stdout


def test_a_backup_completing_during_a_prune_is_never_deleted(tmp_path, monkeypatch):
    import app.db.backup_store as store

    nightly(tmp_path, 30)
    writing = "codecoach-" + (NOW + timedelta(minutes=1)).strftime("%Y%m%dT%H%M%SZ")
    (tmp_path / f"{writing}.dump.age").write_bytes(b"being written")  # no manifest yet: held
    (tmp_path / f".{writing}.manifest.json.partial").write_text("{")  # the atomic write in flight
    real = store.retention

    def finish_mid_prune(*args, **kwargs):
        plan = real(*args, **kwargs)
        later = make(tmp_path, NOW + timedelta(minutes=2))  # completes after the scan
        finish_mid_prune.later = later
        return plan

    monkeypatch.setattr(store, "retention", finish_mid_prune)
    plan = store.prune(tmp_path, apply=True, now=NOW + timedelta(minutes=3))
    assert writing in {s.name for s in plan.held}
    assert (tmp_path / f"{writing}.dump.age").exists()
    assert (tmp_path / f".{writing}.manifest.json.partial").exists()  # a temp file is never ours
    assert (tmp_path / f"{finish_mid_prune.later}.dump.age").exists()


def test_a_failed_deletion_is_reported_and_fails_the_command(tmp_path, monkeypatch):
    nightly(tmp_path, 30)
    real_unlink = Path.unlink
    victim: list[str] = []

    def unlink(self, missing_ok=False):
        if self.name.endswith(".dump.age") and not victim:
            victim.append(self.name)
            raise PermissionError("read-only")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    plan = prune(tmp_path, apply=True, now=NOW)
    assert [name for name, _ in plan.failed] == victim
    stuck = victim[0].removesuffix(".dump.age")
    assert (tmp_path / f"{stuck}.manifest.json").exists()  # its manifest stays with it


def test_an_unreadable_folder_is_an_error_not_an_empty_store(tmp_path, monkeypatch):
    nightly(tmp_path, 3)

    def refuse(self):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "iterdir", refuse)
    with pytest.raises(PermissionError):
        scan(tmp_path)


def test_a_symlink_named_like_a_backup_is_left_alone_and_its_target_untouched(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "precious.bin"
    target.write_bytes(b"not a backup")
    store = tmp_path / "store"
    store.mkdir()
    nightly(store, 30)
    link = "codecoach-" + (NOW - timedelta(days=200)).strftime("%Y%m%dT%H%M%SZ")
    (store / f"{link}.dump.age").symlink_to(target)
    (store / f"{link}.manifest.json").symlink_to(target)
    plan = prune(store, apply=True, now=NOW)
    assert link not in {s.name for s in [*plan.keep, *plan.delete, *plan.held]}
    assert (store / f"{link}.dump.age").is_symlink() and target.read_bytes() == b"not a backup"


def test_the_check_reports_recency_integrity_and_the_last_restore_separately(tmp_path):
    from app.db.backup import RESTORE_LOG

    names = nightly(tmp_path, 3)
    health = check(tmp_path, now=NOW + timedelta(hours=1))
    assert health.ok
    assert any(n.startswith("recency:") for n in health.notes)
    assert any("none recorded" in n for n in health.notes)
    (tmp_path / RESTORE_LOG).write_text(
        json.dumps(
            [
                {
                    "restored_at": (NOW - timedelta(days=40)).isoformat(),
                    "backup": names[2],
                    "tables": 55,
                    "rows": 9,
                },
            ]
        )
    )
    health = check(tmp_path, now=NOW + timedelta(hours=1))
    assert health.ok  # an old rehearsal is a warning, not a failed night
    assert any("40 days ago" in n and "rehearse again" in n for n in health.notes)
    assert RESTORE_LOG not in " ".join(str(p) for p in scan(tmp_path)[1])  # not "other": not a backup
    assert any(n.startswith("storage:") for n in health.notes)

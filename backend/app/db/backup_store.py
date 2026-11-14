"""The backup folder: what's in it, which backups to keep, and whether the newest is fresh and
intact. `backup-database` makes the backups (app/db/backup.py); this decides what happens to them
afterwards. docs/BACKUP.md is the runbook, and its "Retention contract" section says the same as
this docstring in prose.

What's managed. Only pairs that `backup-database` names itself:
    codecoach-YYYYMMDDTHHMMSSZ.dump.age + codecoach-YYYYMMDDTHHMMSSZ.manifest.json
Everything else is listed and never deleted: a backup named by hand (`--name pre-upgrade-…`, the
"pinned" backups), a stray file, a symlink, the restore log, a temporary file.

What counts as a usable backup. Both files present and regular (not symlinks), and a readable
manifest of this format that names this dump. When the manifest records the encrypted size (every
backup since this check was added), the file is exactly that size. A stamp more than 10 minutes in
the future (a wrong clock) doesn't count either. Anything else is *held*: never deleted, never
the anchor of the policy, and reported, so a bad or partial artifact can't move the cutoff and
erase good recovery points. Only a hash check proves the bytes. Pruning runs one on the newest
backup before deleting anything.

Retention, over usable backups only, newest first by the UTC stamp in the name (the backing-up
machine's clock when the backup started):
- the newest, always;
- every backup made at most 24 hours before it (inclusive: exactly 24 h is kept);
- the newest backup of each of the last 7 days, 4 ISO weeks and 3 months (UTC) that have a
  backup.
It counts backups, not the calendar. If backups stop, nothing older expires while they're
stopped. `--keep-daily` can't be below 1, so a typo can't shrink the set to one backup. Pruning
is a dry run unless told to delete. It deletes nothing at all when the newest backup fails its
hash check. A deletion that fails is reported and makes the command fail.

Concurrency: `backup-database` writes the dump first and the manifest last, atomically (a
temporary name, then a rename). So a backup being written is half a pair, held, until it's
complete. A prune only deletes backups it saw complete when it started.

The health check reports three separate things:
- recency: the newest usable backup's age;
- integrity: its hash, or every backup's with --all;
- the last restore rehearsal recorded in the folder.
It never decrypts: the server holds only public keys. Passing it isn't recovery; a restore is.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db.backup import RESTORE_LOG, _sha256

NAME = re.compile(r"^codecoach-(\d{8}T\d{6}Z)\.(dump\.age|manifest\.json)$")
FORMAT = "codecoach-backup/1"
CLOCK_SKEW = timedelta(minutes=10)


@dataclass(frozen=True)
class Stored:
    """One backup in the folder, named by `backup-database`."""

    stamp: datetime
    dump: Path | None
    manifest: Path | None

    @property
    def name(self) -> str:
        return "codecoach-" + self.stamp.strftime("%Y%m%dT%H%M%SZ")

    @property
    def complete(self) -> bool:
        return self.dump is not None and self.manifest is not None


def scan(folder: Path) -> tuple[list[Stored], list[Path]]:
    """The managed backups, newest first, and every other file in the folder. A listing that
    fails raises: an unreadable folder is never treated as an empty one."""
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} isn't a folder")
    parts: dict[str, dict[str, Path]] = {}
    other: list[Path] = []
    for path in sorted(folder.iterdir()):
        m = NAME.match(path.name)
        if not m or path.is_symlink() or not path.is_file():
            if path.name != RESTORE_LOG:
                other.append(path)
            continue
        parts.setdefault(m.group(1), {})[m.group(2)] = path
    stored = [
        Stored(
            datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC),
            found.get("dump.age"),
            found.get("manifest.json"),
        )
        for stamp, found in parts.items()
    ]
    stored.sort(key=lambda s: s.stamp, reverse=True)
    return stored, other


def read_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("not a backup manifest")
    made = datetime.fromisoformat(data["created_at"])
    data["created_at"] = made if made.tzinfo else made.replace(tzinfo=UTC)  # a naive time is UTC
    return data


def problem_with(s: Stored, now: datetime) -> str | None:
    """Why this pair isn't a usable backup, or None. Cheap: no hashing."""
    if not s.complete:
        return "half a pair (being written, or interrupted)"
    assert s.dump is not None and s.manifest is not None
    try:
        data = read_manifest(s.manifest)
    except Exception:  # noqa: BLE001 - any unreadable manifest is the same problem
        return "its manifest isn't readable"
    if data.get("dump_file") != s.dump.name:
        return "its manifest describes a different file"
    expected = data.get("encrypted_bytes")
    if isinstance(expected, int) and s.dump.stat().st_size != expected:
        return "its size doesn't match the manifest (incomplete or damaged)"
    if s.stamp > now + CLOCK_SKEW:
        return "dated in the future (the clock that made it was wrong?)"
    return None


@dataclass
class Plan:
    keep: dict[Stored, list[str]] = field(default_factory=dict)  # backup -> why: newest, daily, ...
    delete: list[Stored] = field(default_factory=list)
    held: dict[Stored, str] = field(default_factory=dict)  # not usable: never deleted, with why
    other: list[Path] = field(default_factory=list)  # not ours (named, stray): never deleted
    refused: str | None = None  # set when prune deletes nothing at all, and why
    failed: list[tuple[str, str]] = field(default_factory=list)  # (file, error class) on --apply


def retention(
    stored: list[Stored],
    daily: int = 7,
    weekly: int = 4,
    monthly: int = 3,
    within: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> Plan:
    """Which backups to keep, delete or hold (nothing is deleted here)."""
    if daily < 1:
        raise ValueError("--keep-daily must be at least 1, so the last nights are always kept")
    if min(weekly, monthly) < 0 or within < timedelta(0):
        raise ValueError("keep counts and the recent window can't be negative")
    now = now or datetime.now(UTC)
    plan = Plan()
    usable: list[Stored] = []
    for s in stored:
        problem = problem_with(s, now)
        if problem is None:
            usable.append(s)
        else:
            plan.held[s] = problem
    usable.sort(key=lambda s: s.stamp, reverse=True)
    if not usable:
        return plan
    plan.keep[usable[0]] = ["newest"]
    for s in usable[1:]:
        if usable[0].stamp - s.stamp > within:
            break
        plan.keep[s] = ["recent"]
    rules: list[tuple[str, int, Callable[[datetime], Hashable]]] = [
        ("daily", daily, lambda t: t.date()),
        ("weekly", weekly, lambda t: tuple(t.isocalendar())[:2]),
        ("monthly", monthly, lambda t: (t.year, t.month)),
    ]
    for rule, count, period in rules:
        seen: set[Hashable] = set()
        for s in usable:  # newest first: the first one seen in a period is its newest
            key = period(s.stamp)
            if key in seen:
                continue
            if len(seen) >= count:
                break
            seen.add(key)
            plan.keep.setdefault(s, []).append(rule)
    plan.delete = [s for s in usable if s not in plan.keep]
    return plan


def _intact(s: Stored) -> bool:
    assert s.dump is not None and s.manifest is not None
    try:
        return _sha256(s.dump) == read_manifest(s.manifest).get("encrypted_sha256")
    except OSError:
        return False


def prune(
    folder: Path,
    daily: int = 7,
    weekly: int = 4,
    monthly: int = 3,
    within: timedelta = timedelta(hours=24),
    apply: bool = False,
    now: datetime | None = None,
) -> Plan:
    """Compute the plan for `folder`. With apply=True, delete what it says to delete, unless the
    newest backup fails its hash check. Each backup's dump goes first, then its manifest, so an
    interrupted prune leaves at most a manifest without its dump: held next time, never mistaken
    for a backup."""
    stored, other = scan(folder)
    plan = retention(stored, daily, weekly, monthly, within, now)
    plan.other = other
    newest = next(iter(plan.keep), None)
    if plan.delete and newest is not None and not _intact(newest):
        plan.refused = (
            f"the newest backup ({newest.name}) doesn't match its manifest, so nothing is deleted: "
            "the older ones may be all there is"
        )
        return plan
    if apply:
        for s in plan.delete:
            for path in (s.dump, s.manifest):
                if path is None:
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    plan.failed.append((path.name, type(exc).__name__))
                    break  # keep the manifest when the dump couldn't go
    return plan


@dataclass
class Health:
    ok: bool
    newest: Stored | None
    problems: list[str]
    notes: list[str]


def last_restore(folder: Path) -> dict[str, Any] | None:
    try:
        records = json.loads((folder / RESTORE_LOG).read_text())
        return records[-1] if isinstance(records, list) and records else None
    except (OSError, ValueError):
        return None


def check(
    folder: Path,
    max_age: timedelta = timedelta(hours=26),
    verify_all: bool = False,
    now: datetime | None = None,
) -> Health:
    """Is the newest usable backup recent and intact? With verify_all, every usable backup's hash
    is checked too (slower: it reads every file). Also reports the last restore rehearsal."""
    now = now or datetime.now(UTC)
    stored, other = scan(folder)
    plan = retention(stored, now=now)
    usable = list(plan.keep) + plan.delete
    usable.sort(key=lambda s: s.stamp, reverse=True)
    problems: list[str] = []
    notes: list[str] = []
    newest = usable[0] if usable else None
    for s, why in sorted(plan.held.items(), key=lambda kv: kv[0].stamp, reverse=True):
        if newest is None or s.stamp > newest.stamp:
            # A newer backup that isn't usable: last night's backup is bad or half-written.
            (
                notes if why.startswith("half a pair") and s.stamp > now - timedelta(hours=2) else problems
            ).append(f"{s.name}: {why}")
        else:
            notes.append(f"{s.name} is held, not deleted: {why}")
    if newest is None:
        problems.append(f"no usable backup in {folder}")
        return Health(False, None, problems, notes)
    for s in usable if verify_all else [newest]:
        if not _intact(s):
            problems.append(f"{s.name} doesn't match its manifest's hash (truncated or damaged)")
    assert newest.manifest is not None
    age = now - read_manifest(newest.manifest)["created_at"]
    hours = age.total_seconds() / 3600
    if age > max_age:
        problems.append(
            f"the newest usable backup is {hours:.0f} h old (limit {max_age.total_seconds() / 3600:.0f} h)"
        )
    else:
        notes.append(f"recency: the newest usable backup is {newest.name}, {hours:.1f} h old")
    restored = last_restore(folder)
    if restored is None:
        notes.append("restore rehearsal: none recorded in this folder (docs/BACKUP.md: rehearse monthly)")
    else:
        when = datetime.fromisoformat(restored["restored_at"])
        days = (now - when).total_seconds() / 86400
        notes.append(
            f"restore rehearsal: {days:.0f} days ago, from {restored.get('backup', '?')}"
            + (" (older than a month: rehearse again)" if days > 31 else "")
        )
    managed = sum(p.stat().st_size for s in stored for p in (s.dump, s.manifest) if p is not None)
    pinned = sum(p.stat().st_size for p in other if p.is_file() and not p.is_symlink())
    notes.append(
        f"storage: {len(stored)} managed backup(s), {managed / 1e6:.1f} MB; "
        f"{len(other)} other file(s) (named backups never pruned), {pinned / 1e6:.1f} MB"
    )
    return Health(not problems, newest, problems, notes)

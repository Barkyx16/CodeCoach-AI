"""The backup folder: what's in it, which backups to keep, and whether the newest is fresh and
intact. `backup-database` makes the backups (app/db/backup.py); this decides what happens to them
afterwards. docs/BACKUP.md is the runbook.

Only pairs that `backup-database` names itself are managed:
    codecoach-YYYYMMDDTHHMMSSZ.dump.age + codecoach-YYYYMMDDTHHMMSSZ.manifest.json
Anything else in the folder is listed and never deleted: a backup named by hand, a stray file, or
half a pair (a dump without its manifest, or the reverse).

Retention keeps, of the complete pairs:
- the newest, always, and every backup made in the 24 hours before it (so a second backup on the
  same day, e.g. by hand before an upgrade, survives the next run);
- the newest backup of each of the last N days, ISO weeks and months **that have a backup**.
A backup named by hand (`backup-database --name pre-upgrade-…`) isn't managed: it stays until you
delete it. Retention counts backups, not the calendar. So if backups stop, nothing older expires while they're
stopped; the folder keeps what it had until new backups replace it. Pruning is a dry run unless
told to delete.

The health check reads the newest complete pair. It fails when the backup is older than the limit
or its manifest is unreadable, and when the encrypted file's SHA-256 doesn't match the manifest
(truncated or damaged, e.g. by an incomplete copy). It never decrypts anything: the server only
holds public keys. Passing the check isn't recovery: only a restore rehearsal proves that.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db.backup import _sha256

NAME = re.compile(r"^codecoach-(\d{8}T\d{6}Z)\.(dump\.age|manifest\.json)$")
FORMAT = "codecoach-backup/1"


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
    """The managed backups, newest first, and every other file in the folder."""
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} isn't a folder")
    parts: dict[str, dict[str, Path]] = {}
    other: list[Path] = []
    for path in sorted(folder.iterdir()):
        m = NAME.match(path.name)
        if not m or not path.is_file():
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


@dataclass
class Plan:
    keep: dict[Stored, list[str]] = field(default_factory=dict)  # backup -> why: newest, daily, ...
    delete: list[Stored] = field(default_factory=list)
    incomplete: list[Stored] = field(default_factory=list)  # half a pair: never deleted
    other: list[Path] = field(default_factory=list)  # not ours: never deleted


def retention(
    stored: list[Stored],
    daily: int = 7,
    weekly: int = 4,
    monthly: int = 3,
    within: timedelta = timedelta(hours=24),
) -> Plan:
    """Which complete backups to keep and which to delete (nothing is deleted here)."""
    if min(daily, weekly, monthly) < 0 or within < timedelta(0):
        raise ValueError("keep counts and the recent window can't be negative")
    plan = Plan(incomplete=[s for s in stored if not s.complete])
    complete = sorted((s for s in stored if s.complete), key=lambda s: s.stamp, reverse=True)
    if not complete:
        return plan
    plan.keep[complete[0]] = ["newest"]
    for s in complete[1:]:
        if complete[0].stamp - s.stamp > within:
            break
        plan.keep[s] = ["recent"]
    rules: list[tuple[str, int, Callable[[datetime], Hashable]]] = [
        ("daily", daily, lambda t: t.date()),
        ("weekly", weekly, lambda t: tuple(t.isocalendar())[:2]),
        ("monthly", monthly, lambda t: (t.year, t.month)),
    ]
    for rule, count, period in rules:
        seen: set[Hashable] = set()
        for s in complete:  # newest first: the first one seen in a period is its newest
            key = period(s.stamp)
            if key in seen:
                continue
            if len(seen) >= count:
                break
            seen.add(key)
            plan.keep.setdefault(s, []).append(rule)
    plan.delete = [s for s in complete if s not in plan.keep]
    return plan


def prune(
    folder: Path,
    daily: int = 7,
    weekly: int = 4,
    monthly: int = 3,
    within: timedelta = timedelta(hours=24),
    apply: bool = False,
) -> Plan:
    """Compute the plan for `folder`; with apply=True, delete what it says to delete. Each backup's
    dump goes first and then its manifest, so an interrupted prune leaves at most a manifest
    without its dump: reported as incomplete next time, never mistaken for a backup."""
    stored, other = scan(folder)
    plan = retention(stored, daily, weekly, monthly, within)
    plan.other = other
    if apply:
        for s in plan.delete:
            for path in (s.dump, s.manifest):
                if path is not None:
                    path.unlink(missing_ok=True)
    return plan


@dataclass
class Health:
    ok: bool
    newest: Stored | None
    problems: list[str]
    notes: list[str]


def _read_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("not a backup manifest")
    made = datetime.fromisoformat(data["created_at"])
    data["created_at"] = made if made.tzinfo else made.replace(tzinfo=UTC)  # a naive time is UTC
    return data


def check(
    folder: Path,
    max_age: timedelta = timedelta(hours=26),
    verify_all: bool = False,
    now: datetime | None = None,
) -> Health:
    """Is the newest backup recent, readable and intact? With verify_all, every complete backup's
    hash is checked too (slower: it reads every file)."""
    now = now or datetime.now(UTC)
    stored, other = scan(folder)
    complete = [s for s in stored if s.complete]
    problems: list[str] = []
    notes: list[str] = []
    if not complete:
        return Health(False, None, [f"no complete backup in {folder}"], notes)
    newest = complete[0]
    for s in stored:
        if not s.complete and s.stamp > newest.stamp:
            notes.append(f"{s.name} is half a pair (an interrupted backup?); the check uses {newest.name}")
    for s in complete if verify_all else [newest]:
        assert s.manifest is not None and s.dump is not None
        try:
            data = _read_manifest(s.manifest)
        except Exception:  # noqa: BLE001 - any unreadable manifest is the same problem
            problems.append(f"{s.manifest.name} isn't a readable backup manifest")
            continue
        if data.get("dump_file") != s.dump.name:
            problems.append(f"{s.manifest.name} describes a different file")
        elif _sha256(s.dump) != data.get("encrypted_sha256"):
            problems.append(f"{s.dump.name} doesn't match its manifest (truncated or damaged)")
        if s is newest:
            age = now - data["created_at"]
            hours = age.total_seconds() / 3600
            if age > max_age:
                problems.append(
                    f"the newest backup is {hours:.0f} h old (limit {max_age.total_seconds() / 3600:.0f} h)"
                )
            else:
                notes.append(f"newest: {newest.name}, {hours:.1f} h old")
    if other:
        notes.append(f"{len(other)} other file(s) in the folder, not managed here")
    return Health(not problems, newest, problems, notes)

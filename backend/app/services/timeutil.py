"""Local dates and times, as people write them, turned into exact instants without surprises.

A learner says "Tuesday 9:30 in Chicago". That's a calendar date, a wall-clock time and an IANA
time zone. Converting it to an instant can go wrong twice a year:

- **Nonexistent** (clocks go forward): 2:30 doesn't happen on that day. We refuse it with a clear
  message instead of quietly moving it an hour.
- **Ambiguous** (clocks go back): 1:30 happens twice. We ask which one (`fold` 0 = the first,
  1 = the second) instead of guessing.

Nothing here ever moves an event to another day.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from app.errors import AppError

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def zone(name: str) -> ZoneInfo:
    """A real IANA zone name, or a 400. (Abbreviations like "EST" are refused: they're ambiguous.)"""
    if not name or "/" not in name and name != "UTC" or name not in _zones():
        raise AppError(
            f"Unknown time zone: {name!r}. Use a name like Europe/London.", code="invalid_timezone"
        )
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover - guarded by the set above
        raise AppError(f"Unknown time zone: {name!r}.", code="invalid_timezone") from exc


_ZONES: set[str] | None = None


def _zones() -> set[str]:
    global _ZONES
    if _ZONES is None:
        _ZONES = available_timezones() | {"UTC"}
    return _ZONES


def parse_hhmm(value: str) -> time:
    m = _HHMM.match(value or "")
    if not m:
        raise AppError("Times are 24-hour HH:MM, for example 09:30 or 14:00.", code="invalid_time")
    return time(int(m.group(1)), int(m.group(2)))


def local_to_utc(on: date, hhmm: str, tz_name: str, fold: int | None = None) -> datetime:
    """The UTC instant of a wall-clock time on a date in a zone. Raises on nonexistent times, and
    on ambiguous ones unless `fold` says which occurrence is meant."""
    tz = zone(tz_name)
    t = parse_hhmm(hhmm)
    first = datetime.combine(on, t, tzinfo=tz).replace(fold=0)
    second = first.replace(fold=1)
    u0, u1 = first.astimezone(UTC), second.astimezone(UTC)
    # A time that doesn't exist comes back as a different wall-clock time after a round trip.
    back = u0.astimezone(tz)
    if (back.date(), back.hour, back.minute) != (on, t.hour, t.minute) and (
        u1.astimezone(tz).hour,
        u1.astimezone(tz).minute,
    ) != (t.hour, t.minute):
        raise AppError(
            f"{hhmm} doesn't exist in {tz_name} on {on.isoformat()}: the clocks go forward then. Choose another time.",
            code="nonexistent_time",
        )
    if u0 != u1:
        if fold is None:
            raise AppError(
                f"{hhmm} happens twice in {tz_name} on {on.isoformat()} (the clocks go back). Say which one you mean.",
                code="ambiguous_time",
                details={
                    "first": u0.isoformat(),
                    "second": u1.isoformat(),
                    "first_offset": first.strftime("%z"),
                    "second_offset": second.strftime("%z"),
                },
            )
        return u1 if fold == 1 else u0
    return u0


def utc_offset(on: date, hhmm: str, tz_name: str, fold: int = 0) -> str:
    """The offset in effect at that wall-clock time, for display ("+01:00")."""
    dt = datetime.combine(on, parse_hhmm(hhmm), tzinfo=zone(tz_name)).replace(fold=fold)
    raw = dt.strftime("%z")
    return f"{raw[:3]}:{raw[3:]}"

"""Writing iCalendar (RFC 5545) files by hand: small, dependency-free and tested.

Only what the learner selected goes in: a title, the time, a status and a link back to the
schedule page. No account details, tokens or notes. Timed events are written in UTC (`Z`), which
every calendar understands without time zone tables; all-day events are plain dates. `UID` stays
the same for an entry forever and `SEQUENCE` grows with every change, so a calendar that
supports it treats a re-import as an update or a cancellation. Many calendars only copy a file
once, though, so later edits may not reach them; the page says so.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

PRODID = "-//CodeCoach AI//Schedule//EN"


@dataclass(frozen=True)
class IcsEvent:
    uid: str
    sequence: int
    summary: str
    status: str  # CONFIRMED | CANCELLED
    all_day: bool
    on_date: date
    starts_at: datetime | None
    minutes: int
    url: str | None = None
    description: str | None = None


def escape(text: str) -> str:
    """TEXT values: backslash, semicolon, comma and newlines are escaped."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after CRLF + space, never splitting
    a UTF-8 character."""
    out: list[str] = []
    current = ""
    size = 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        limit = 75 if not out else 74  # continuation lines start with a space
        if size + n > limit:
            out.append(current)
            current, size = ch, n
        else:
            current += ch
            size += n
    out.append(current)
    return "\r\n ".join(out)


def _utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def calendar(events: Iterable[IcsEvent], now: datetime | None = None) -> str:
    stamp = _utc(now or datetime.now(UTC))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for e in events:
        lines += ["BEGIN:VEVENT", f"UID:{e.uid}", f"DTSTAMP:{stamp}", f"SEQUENCE:{e.sequence}"]
        if e.all_day or e.starts_at is None:
            lines += [
                f"DTSTART;VALUE=DATE:{e.on_date.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(e.on_date + timedelta(days=1)).strftime('%Y%m%d')}",
            ]
        else:
            lines += [
                f"DTSTART:{_utc(e.starts_at)}",
                f"DTEND:{_utc(e.starts_at + timedelta(minutes=e.minutes))}",
            ]
        lines += [f"SUMMARY:{escape(e.summary)}", f"STATUS:{e.status}"]
        if e.description:
            lines.append(f"DESCRIPTION:{escape(e.description)}")
        if e.url:
            lines.append(f"URL:{e.url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)

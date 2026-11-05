# Schedule: practice on a calendar you control

Put existing activities on dates and times you choose, see the week in your own time zone, and
download calendar files. It works without connecting a calendar account or allowing
notifications.

## What can be scheduled

Existing activities only, by their ids: a step from your **practice plan**, a question in your
**review queue**, any **question** or **coding problem** (from its page: "Add to schedule"), or
**preparation** for an interview event of one of your **applications**. Nothing new is invented;
the entry links back to the activity (for interview preparation, that interview's kit). A
preparation entry is a time slot of its own: rescheduling the interview doesn't move it.

**Scheduling something isn't doing it.** An entry shows as *Done* only when the activity itself
was done by its own rules: the plan step was completed by the plan, or you answered the question
(or submitted the problem) after you scheduled it. Interview preparation has no completion rule,
so it never claims to be done.

- Moving an entry changes its date, time, zone or length. Cancelling keeps it (shown with "Show
  cancelled") so a calendar file can cancel it too. A cancelled entry isn't moved back; schedule
  the activity again instead.
- A repeated click, or a retry after a dropped connection, creates one entry
  (`client_request_id`).
- **Overlaps** between timed entries are explained ("Overlaps with Two Sum. Nothing was moved")
  and never fixed for you.

## Time zones

- Your schedule has an explicit IANA time zone (for example `America/Chicago`). Until you choose
  one, the page uses your device's zone and says so; the zone is shown above the week.
- A **timed** entry stores what you chose (date, wall-clock time, zone) and the exact instant.
  An **all-day** entry is just a date.
- **Travelling or changing zone**: timed entries stay at the same moment (an 18:30 Chicago
  entry shows as 09:30 the next morning in Tokyo, with "(18:30 America/Chicago)" beside it);
  all-day entries keep their date. If your device is in a different zone from your schedule,
  the page says so and offers to switch; switching changes only how times are shown.
- **Daylight saving**: a time that doesn't exist (the hour skipped when clocks go forward) is
  refused with a message, and a time that happens twice (when clocks go back) asks which one,
  showing both UTC offsets. Nothing is ever moved silently or onto another day.
- Each timed entry appears on the day it falls on in your schedule's zone.

## Calendar files (.ics)

"Download this week (.ics)" and the ".ics" button on an entry give a standards-compliant
iCalendar file (RFC 5545):

- `UID` is fixed per entry and `SEQUENCE` grows with every change, so calendars that support it
  update or cancel the same event when you import again. A week's file includes cancelled
  entries with `STATUS:CANCELLED`.
- Timed events are written in UTC (`…Z`), all-day events as dates (`VALUE=DATE`, ending the next
  day). Text is escaped, lines are folded at 75 bytes without splitting a character, and lines end
  with CRLF (all tested).
- Only the entries you chose are included, with a title, the time, a status and a link to the
  schedule page. No notes, email address or anything secret.
- **It's a file, not a live connection.** Importing copies the events once; later changes here
  may not reach your calendar (download again; some calendars then update the same events,
  others add copies). CodeCoach never connects to or changes an outside calendar.

## Reminders, honestly

- **Off by default.** When you turn them on, reminders appear **only inside CodeCoach while it's
  open in a browser tab**, a set time before a timed entry starts.
- No emails, push notifications, browser notifications or calendar invitations are sent. There's
  no delivery worker, so nothing is ever "queued" or reported as delivered.
- Quiet hours (which can cross midnight) are respected, nothing is reminded about once it's done
  or cancelled, and each reminder shows once per version of an entry (moving it can remind
  again). Dismissed reminders are remembered for the tab's session.

## Privacy and data

Entries and settings are private to you (404 for anyone else), in the data export, and deleted
with your account.

## Verified, and not

- Backend: 11 tests on SQLite and PostgreSQL (settings and opt-in reminders, a scheduled question
  that's done only once answered, all-day vs timed, nonexistent and ambiguous times, the day
  after a change, moves and cancellations with UID/SEQUENCE, repeated clicks, overlaps not moved,
  own-only activities and entries, a zone change keeping entries in place, the `.ics` file's
  structure, escaping, 75-byte folding of multi-byte text, selection and no private data, export
  and deletion).
- Frontend: 11 tests (dates across month, year and DST; the day an entry falls on in another
  zone; reminders off by default, skipped when done/cancelled/past/already shown, quiet hours
  across midnight; scheduling from a page; the ambiguous-time choice; overlap wording and the
  week download; the zone-mismatch banner; reminders shown and dismissed).
- Playwright (Chromium, browser in Chicago time): scheduling from a question, the 01:30
  fall-back choice, an overlap, a week file with exact UTC times, a move with the same UID and a
  higher SEQUENCE, a cancellation kept for the calendar, viewing from Tokyo, and a real reminder
  appearing only after turning them on, at 320px in the light theme; axe scans.
- **Not verified:** importing the files into real calendar apps (Google, Apple, Outlook) wasn't
  possible here, so behaviour on re-import is described as "may"; Safari/Firefox.

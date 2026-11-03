# Applications: a private tracker of real applications

A simple pipeline for the jobs the learner has applied for (or wants to), connected to their
preparation. It records what the **learner says** has happened. It never submits an
application, contacts an employer, reads an email account, scrapes job sites, or guesses an
outcome.

## Applications and job targets are different things

- A **job target** (`/targets`) describes *preparation*: a pasted job description, its
  requirements and the practice that covers them.
- An **application** (`/applications`) describes *what happened*: employer, role title, an
  optional posting link, the date the learner applied (unknown is fine), the stage, the next
  action with an optional due date, private notes, and interview events.

An application can link to one target and to stories from the story bank. Links are by id, so
nothing is copied: renaming a story shows the new title, deleting a target just unlinks it.

## Stages

`saved`, `applied`, `interviewing`, `offer`, `closed`, `withdrawn`. Each is what the learner
recorded. Silence is never read as a rejection, and nothing becomes "applied" because a draft was
written.

- **History**: every change is kept (append-only) with the role title and employer *as they were
  at that moment*, so later renames never rewrite it. Moving to the stage it's already in changes
  nothing (a double click or a second tab).
- **Corrections**: "This corrects a mistake" records the fix as its own entry, marked
  *Correction*.
- **Archive** hides an application without losing anything; **Delete** asks first and removes the
  application, its events and its history.

## Board and list

- The **board** has a column per stage. Cards can be **dragged** between columns, and every card
  has a **"Move … to" menu** that makes exactly the same change from the keyboard. A move shows
  at once and is put back, with a message, if it can't be saved.
- The **list** is a table with sortable columns (role, employer, stage, applied, next action,
  updated; `aria-sort` on the active column). Unknown dates sort last either way.
- View, search, stage filter, archived and sort are in the address, so Back, reload and sharing a
  bookmark keep them; the scroll position comes back on Back.
- **Next actions** lists the soonest due actions. Due dates are calendar dates compared with
  *today in the learner's time zone* (at 23:30 UTC it's already tomorrow in Tokyo); overdue ones
  read neutrally ("Was due 2 days ago").

## Interview events and time

Each interview (or phone screen, assessment) is its own event: a title, kind, an optional date,
an optional local time and the IANA time zone it's in, and notes.

- With a date, a time and a zone, the exact instant is stored (UTC) next to what the learner
  typed. Unknown dates or times stay unknown; no instant is invented.
- Zones must be real IANA names; abbreviations like "EST" are refused because they're ambiguous.
- **A time that doesn't exist** (the hour skipped when clocks go forward) is refused with a
  message: it's never quietly moved an hour.
- **A time that happens twice** (when clocks go back) asks which one is meant, showing both UTC
  offsets; the learner's choice is stored.
- The calendar and reminders (V2-04) build on these events.

## Preparing

"Prepare for this stage" links into existing practice: the linked target's preparation map,
the story bank, a mock interview, interview questions, and each linked story. Returning comes
back to the application.

## Message drafts, never sent

"Write a message" makes a **thank-you** or **follow-up** draft from facts typed right there
(recipient, when, one thing to mention, your name). Only those facts are used; missing ones stay
out or appear as "[Your name]". The draft can be edited, **copied** or **downloaded** as a text
file. It isn't stored, and CodeCoach never sends it. Writing a draft never changes the stage.

## Privacy and data

- Every application, event and stage change is scoped to its owner (404 for anyone else).
- Posting links must be `http(s)` and are never fetched; they open in a new tab with
  `noopener noreferrer`. Contact details aren't asked for and draft text isn't kept.
- Creating an application takes a `client_request_id` so a retry after a dropped connection
  creates it once; events do the same.
- Applications, events and history are in the data export and deleted with the account.

## Verified, and not

- Backend: 8 tests on SQLite and PostgreSQL (safe retries, history and corrections, renames not
  rewriting history, unknown dates, exact event instants, refused nonexistent and ambiguous
  times, invalid zones and times, separate interviews and retried events, own-only links that
  aren't copies, link schemes, archive, privacy across every route, export and deletion).
- Frontend: 10 tests (drag and keyboard moves making the same change, a failed move put back,
  view/filter/sort in the address, the ambiguous-time choice, drafts from typed facts only and
  no stage change, time-zone "today", neutral due wording, sorting with unknown dates last).
- Playwright (Chromium): a real pointer drag and a keyboard move, list sorting across a reload,
  a correction and a rename in the history, a Chicago fall-back interview needing a choice, two
  separate interviews, a linked story in the preparation links, copy (read back from the
  clipboard) and download of a draft with the stage unchanged, another account refused,
  archiving; the board and detail at 320px in the light theme; axe scans.
- Found and fixed while testing: the list's sort arrow was read as part of the column name
  ("Role ↓"); link checkboxes didn't change until the server answered.
- Not verified: Safari/Firefox drag and drop, touch dragging on real phones (the "Move to" menu is
  the supported way on touch screens), screen readers.

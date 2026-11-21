# Interview-day kit

One practical page for a real interview the learner recorded on an application: logistics, an
editable checklist, questions to ask, the examples to bring, a calm final view and a printable
pack. It builds on the application's interview events, the linked job target and the story bank.
It isn't a second tracker, a device-setup wizard or a readiness score.

## Opening a kit

"Interview-day kit" on any interview event of an application. It's useful with only the role
and a time: until the learner changes something, the kit is just suggestions (nothing is
stored). The first save stores it.

## Logistics

- Format: remote, in person, by phone or not known yet (a phone screen starts as "by phone").
- Location, a meeting link and interviewers' names and roles, all optional and as the learner
  knows them; unknown names are fine.
- The meeting link must be `http(s)`. CodeCoach never opens or fetches it; it's shown on the
  kit page and left out of the printout unless chosen. Responses are `Cache-Control: no-store`.
- Text is treated as untrusted and shown as plain text.

## Checklist

Suggestions depend on the format (remote: open the link ahead of time, check microphone and
camera, a quiet place; in person: address and travel time, arriving early, documents they asked
for; by phone: battery and signal) plus confirming the time, rereading the job description,
choosing examples and questions. Items are labelled **Suggested** or **Yours**, can be ticked,
hidden and restored, and the learner can add their own. Switching the format swaps the untouched
suggestions and keeps the learner's own items and anything they ticked or hid.

An **improvement you accepted** from an interview review can be added too ("Add an improvement
you accepted"). The item holds only the action's id: its words and its state are the action's
(docs/ACCEPTED_ACTIONS.md), so ticking it marks the action done everywhere, a weekly one shows how
many weeks are done, and kit templates leave it out.

**A tick means the learner ticked it.** CodeCoach doesn't check a camera, a network, documents
or travel. For the microphone, the kit links to the existing check in the mock interview setup
instead of duplicating it.

## Questions to ask

- Suggestions are grouped (the role, the team, training and support, how the work runs, next
  steps). Up to three are built from the learner's own job target requirements, each saying which
  requirement it came from. Nothing about the employer is invented.
- If the job description already mentions a topic (for example "induction" or "shifts"), the
  question says so ("check whether it already answers this"). It's never hidden automatically.
- The learner edits, reorders (Up/Down buttons, keyboard friendly), excludes and adds questions.
  The saved order is the priority.

## Before the interview

A compact view at the top: the date, time and zone, the format and location, the meeting link
(folded on small screens), the examples chosen (with their short rehearsal version), the
questions selected and what's left on the checklist. Neutral encouragement only: no confidence
scores and no claims about how it will go. Private notes are folded by default on small
screens.

## Printable pack

The preview on the page **is** the printed pack (the same component; print styles hide
everything else), so what prints can't differ from what's shown. The learner chooses what goes
in; the meeting link, interviewer names and private notes are **off** until chosen. Printing
uses the browser's print dialog, which also offers "Save as PDF" (selectable text). The pack says
"Your own preparation notes. Not sent to anyone." With unsaved changes the "Print…" button is
disabled, and the pack itself prints only a notice ("This kit has unsaved changes, so it isn't
printed"), so the browser's own Print (Ctrl/Cmd+P) can't print unsaved content as if it were
saved. The print styles apply only to a page that has a pack; any other page prints normally.
A real PDF of the pack is checked by `e2e/kit-pdf.spec.ts` (see `INTERVIEW_WORKFLOW.md`).

**Saving** is conflict-safe: each save sends the revision the page loaded, and a kit saved since
(another tab) is a 409 `stale_revision` that changes nothing. The page keeps the learner's edits
and offers "Save mine over it" (an explicit overwrite) or "Discard mine and load the saved kit".
A kit records the interview time it was last saved for and each chosen story's version, so a
reschedule or an edited story is shown, never silently applied or hidden.

## Privacy and data

Kits are owner-only (404 otherwise), in the data export, and deleted with their interview event,
their application or the account. Nothing is sent to anyone: no invitations, reminders or
messages. Preparation time can be put on the schedule from the interview event.

## Verified, and not

- Backend: 7 tests on SQLite and PostgreSQL (useful with only a role and time and nothing stored
  until a change; questions grounded in the learner's own target and "already mentioned" hints
  that never hide anything; a format change swapping only untouched suggestions, including when
  saved together with the whole kit; editing, hiding, reordering and excluding; link schemes;
  stories must be the learner's own; privacy, export and cascade deletion).
- Frontend: 3 tests (labels, a tick being only the learner's, saved order and choices; private
  details kept out of the print preview until chosen; not-found for someone else's interview).
- Playwright (Chromium): from an application's interview to a saved kit with a remote format,
  ticks, a hidden item, a keyboard reorder, an added question and a chosen story, kept across a
  reload; print media shows only the pack and leaves out the meeting link until it's chosen;
  another account refused; the way back to the application; 320px in the light theme with
  private notes folded; axe scans.
- Found while testing: saving a new format together with the page's checklist overwrote the new
  suggestions (fixed, with a test); a story link in the summary relied on colour alone
  (underlined now).
- Not verified: printing to paper or a real PDF viewer (Chromium's print media was used), screen
  readers, Safari/Firefox.

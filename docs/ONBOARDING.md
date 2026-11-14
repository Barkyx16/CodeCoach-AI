# First session: welcome, guided tour and Help

An optional introduction that ends in a real activity from the learner's own job, and a Help
page for the core actions. Nothing in it is required: the library and every page work without
it.

## The welcome (`/welcome`)

Shown after creating an account (once the email step is done or put off) and after a deliberate
guest demo ("Try it now" on the home page, or "Continue as guest" on the sign-in pages). A page
that sent someone to sign in still gets them back instead. Returning sign-ins go to the
dashboard.

- **Your job** is shown first, with "Change job" (the same career setting as in Settings). The
  starter below changes with it.
- **Answer one question now / problem now**: a real, easy item from the learner's own bank
  (`GET /me/onboarding` → `starter`). Written careers get an easy knowledge question; careers
  with coding get an easy problem (Two Sum when it exists and isn't retired). A nurse is never
  introduced through Java. Retired content is never offered. The time is labelled an estimate.
- Before anything is promised, the page says what feedback it really gets: the built-in rubric
  coach for written answers (not an AI model, not a hiring decision); for code, the server's
  judge, or, when this server can't judge code, that attempts are saved without a verdict.
- **Show me around first** starts the guided tour on that same page.
- **Browse the library** goes straight to Practice.
- **Not now** goes to the dashboard. Guests are told how long a guest account is kept
  (`GUEST_RETENTION_DAYS`) and how to keep their work.

## The guided tour

Five steps on the real question page (written careers) or the real coding workspace:

| Written | Coding |
| --- | --- |
| Read the question | The problem |
| Your answer | The editor (incl. the Ctrl+M Tab exit) |
| Your draft is kept | Your draft is kept |
| Getting feedback | Checking your code (worded from the judge's actual state) |
| What to do next (after feedback) | The coach |

- Each step highlights the real element (`data-tour` attributes) and scrolls it between the
  sticky header and the panel.
- The panel is **docked** to the bottom of the screen, not floating over content. The page gains
  bottom padding and `scroll-padding-bottom` equal to its height, so tabbing to any control, or
  scrolling to it, never leaves it behind the panel (WCAG 2.4.11). Nothing is disabled while the
  tour is open: learners can type, get feedback or submit at any step.
- **Missing elements** (feedback not given yet, another tab on a phone, hidden by focus mode)
  don't break it: the step says where the element is or when it appears.
- **Keyboard**: each step's heading takes focus; Back / Next / Finish are ordinary buttons;
  Esc inside the panel or "Leave the introduction" leaves it, and focus returns to where it
  was (or the start of the main content).
- **Refresh and resume**: the step is saved on the server, so a reload or another device
  continues at the same step. Leaving pauses it; the dashboard offers "Resume" once (dismissible)
  and Help can resume or replay it.
- If saving fails (offline), the tour still moves and can always be left on that page.

## After a career change

If a learner who has been welcomed switches job, the dashboard offers that job's format
introduction once ("You're now practising for Registered Nurse… Your earlier practice is
kept"), with "Take the tour" or "Not now". Nothing is reset.

## Help (`/help`)

Organised topics (choosing practice, saving work, feedback, voice, history, account and data,
getting more help), searchable by keyword, each answer linking to the real page. Every claim
describes the current product, for example "CodeCoach never receives audio". There is no contact
channel, live chat or promised response time, and the page says so; the only support links are
Report an issue and the project's GitHub repository. A test checks every internal Help link
points at a real route. Help is linked from the header and from Settings → Account.

## What's recorded

One row per account in `user_onboarding` (see DATABASE.md), created on the first choice:

- the tour's status (`not_started`, `in_progress`, `paused`, `completed`, `skipped`), kind and
  step, and when it started and finished;
- the start choice (`practice`, `intro`, `library`, `later`) and when the welcome was answered;
- which careers' introductions have been seen, and which reminders were dismissed.

That's all. **No answer text, no keystrokes, no page views and no third-party analytics.** The
tour never creates practice activity, scores or progress (a backend test compares progress and
activity before and after a full tour). "Has done a first real activity" is worked out when
asked, from the timestamps of the learner's own answers and submissions. Tour completion, a
completed answer and skill progress are separate facts. The row is in the data export and is
deleted with the account.

## Verified, and not

- Backend: 10 tests on SQLite and PostgreSQL (starter per career and for guests, retired
  starter skipped, transitions and idempotence, clamping, invalid input, no progress side
  effects, first activity, career-change introduction, privacy, export and deletion).
- Frontend: 10 integration tests (welcome for a nurse and a coding guest, honest judging note,
  library and "Not now", load failure, tour steps with focus, highlight, missing target, Esc,
  resume after refresh, leaving when saving fails, wrong-kind pages, dashboard reminders, career
  intro, Help search and link validity, replay).
- Playwright (Chromium): a nurse from sign-up through the tour to real feedback, then signing in
  again goes to the dashboard; a coding guest's workspace tour with a reload, leaving, resuming
  and dismissing; a guest changing job on the welcome and taking the tour at 320px in the light
  theme, with axe scans of the welcome, the tour and Help.
- Not verified: screen readers (none available here), Safari and Firefox, real phones.

# Accessibility and reading preferences

What CodeCoach does for keyboard users, screen-reader users, people who need larger text or
less motion, and people on small screens; how it's checked; and what hasn't been checked. This
is an engineering record, not a conformance claim: passing automated checks (axe-core, contrast
math, scripted keyboard journeys) is not the same as an accessibility assessment by disabled
users, and no formal audit or certification has been done.

## Reading and display preferences

**Settings → Display & reading.** Presentation only: kept in this browser (`localStorage`,
key `codecoach.display.v1`), never sent to the server, not part of career data or exports.

| Setting | Options | What it changes |
| --- | --- | --- |
| Theme | Match device (default), Light, Dark | Colour tokens. "Match device" follows the OS and switches live when it changes. |
| Contrast | Standard, Higher | Stronger text, borders and focus ring. Not a filter: separate colour values, each checked (below). |
| Text size | Default, Large (112.5%), Larger (125%) | The root font size; every app size is in `rem`, so all text scales. The code editor keeps its own font size (Settings → Editor). |
| Reading layout | Standard, Spacious | More line height and paragraph spacing in the main content. |
| Motion | Follow device, Reduce | Turns off transitions and animations. The device's reduced-motion setting is honoured either way. |

- **Applied before the first paint** by `public/display-init.js` (a tiny same-origin script, so
  the Content-Security-Policy is unchanged): no flash of the wrong theme.
- **Validated:** each saved field is checked against its allowed values; anything unknown or
  malformed falls back to the default for that field (`parseDisplayPrefs`). Voice settings got
  the same treatment (`parseVoicePrefs`): a corrupted value can't, say, turn on reading aloud.
- **Every combination stays readable:** the options only choose between colour sets whose
  contrast is verified (below); text size and spacing don't affect colour.
- **Honest persistence:** the section says "Saved in this browser." or, when storage is
  blocked (private modes, blocked site data), that settings apply for this visit only.
- **Reset to defaults** removes the saved value.

### Contrast

`src/test/contrast.test.ts` reads the real colours from `src/styles/tokens.css` and computes
WCAG contrast ratios for every text colour (text, muted, subtle, link, success, warning, danger,
info) on every background (page, card, raised card), for coloured text on its own translucent
tint (badges, banners, the active nav item; the tint is composited as the browser does), and for
white text on the primary button, in all four themes. Minimums: 4.5:1 in the standard themes,
7:1 in the higher-contrast themes. 172 checks.

## Focus mode

A **Focus mode** toggle on the written-question page, the live interview round (incl. panels and
follow-ups), the coding interview and the coding workspace. It hides the site navigation,
breadcrumbs, the practice queue bar, "Learn first", save and notes panels, past answers, the
"best score" badge, the panel roster and the engagement indicator.

- **Never hidden:** the question, the answer box and its draft, submit/skip/end controls, the
  timer and deadline, recording/listening status, errors (including save failures), hints/tips
  and the coach in the workspace, and two ways out (the header's "Exit focus mode" and the
  toggle itself, a toggle button with a fixed name and `aria-pressed`).
- **Esc** exits (except inside the code editor, where Esc belongs to the editor; the header
  button still works). Exiting returns keyboard focus to the toggle.
- **Scoped to the page:** navigating elsewhere ends it, and so does the page no longer offering
  it (an interview round turning into its results at the same address).
- Drafts are untouched: focus mode only hides other elements; nothing re-mounts the answer box.

## Fixed in the audit

Found by walking registration, career choice, the question explorer, a written answer, a coding
problem, both interview kinds, reviews, notes, saved items and Settings with the keyboard, at
320px with the largest text, and in all four themes.

| Problem | Fix |
| --- | --- |
| Buttons that show a spinner set `disabled` while busy; Chrome drops focus from a disabled button, so after every request (submit an answer, save, start an interview) keyboard focus jumped to the top of the page | A busy button is `aria-disabled` + `aria-busy`, stays focusable and ignores presses |
| The code editor trapped Tab: the "Tab moves focus" toggle wasn't in our slimmed Monaco bundle, so there was no way out with Tab | Bundled Monaco's toggle (**Ctrl+M**, Mac **Ctrl+Shift+M**); the editor's accessible name says so, and a visible hint appears while the editor has focus and reflects the current mode |
| Live regions that changed on every keystroke: the workspace's "Unsaved changes / Saving… / Draft saved" and the note editor's save state; the microphone test level (every animation frame) | Not live any more; a save failure or note conflict is announced once (`role="alert"`); the mic test announces "we can hear you" once |
| Removing a bookmark, a collection item, or undoing a note deletion removed the focused button and dropped focus to the page | Focus moves to the next item's Remove, the list heading or the page title, with a status message |
| Cancel (or Esc) on "Delete collection?" lost focus | Returns to the Delete button |
| A failed bookmark removal was silent (the row came back but its error was in the removed row) | Error shown at the list level |
| Answer errors weren't tied to the answer box | The error has an id and the textarea's `aria-describedby` includes it (`aria-invalid` on validation errors), in question pages, rounds, follow-ups and the coding interview |
| Browser tab title "Page not found" on Notes, Saved, Learn, Scenarios, questions and other newer pages | Every route has a title; a unit test fails if a route is added without one |
| At 320px with large text: the header's Menu button, the difficulty tabs, long buttons and the History filters overflowed sideways | Brand name truncates, tabs and buttons wrap, filters stack |
| Focus rings were box-shadows only, which Windows High Contrast (forced colours) removes | A transparent outline is drawn too; it takes a system colour in that mode |
| Font sizes in `px` (209 declarations) didn't follow a text-size setting; some colours were hard-coded | Converted to `rem`; colours moved to theme tokens |
| After an answer was sent, the emptied box disabled "Get feedback" and focus fell to the page; the feedback appeared with its summary already inside a `role="status"`, which screen readers often don't announce (2026-11-04) | Focus moves to the feedback heading (or to "Before you read the feedback" when reflecting first, then to the feedback); covered by `careers.test.tsx` ("Answering with the keyboard") and checked in `e2e/a11y.spec.ts`, which now scans a written answer with its feedback on screen |

Already in place and re-checked: skip link (first Tab stop), landmarks and headings,
labelled fields with hints/errors linked (`Field`), the mobile menu (Esc closes and returns
focus, outside click closes), keyboard tab lists (arrow keys, Home/End), disclosures with
`aria-expanded`, transcripts as a `log` in speaking order with text for everything spoken,
interviewer audio only after the learner turns "read aloud" on (off by default), confirmation
for destructive actions, horizontal scrolling only inside code blocks and tables.

## How it's checked

Automated, run in CI or locally:

- `npm test` (Vitest): display preferences (validation, applying, saving, reset, keyboard radio
  groups, blocked storage), voice-setting validation, focus mode (draft kept, essentials kept,
  focus returned, Esc, ends on navigation), focus after removals and dialogs, every route's
  title, contrast (172 ratios).
- `npm run e2e` (Playwright, real backend, Chromium), `e2e/display.spec.ts`:
  - keyboard only: filtered question list → tabs with arrow keys → question → answer → a failed
    submit (error announced and linked, draft kept, focus kept) → retry → feedback → focus mode
    on and Esc off → Back to the filtered list;
  - keyboard only: start a mock interview, answer with Ctrl+Enter, focus mode (timer, recording
    status, End early and exit still visible), end early;
  - the code editor: Tab indents, Ctrl+M then Tab leaves, Shift+Tab back in, Ctrl+M restores;
    "Editor settings" disclosure by keyboard;
  - Settings by keyboard, applied before render after a reload, then axe-core WCAG 2.1 A/AA
    scans of six pages in Light, Light + higher contrast and Dark + higher contrast;
  - the largest text at 320px and 640px wide (≈ a 1280px window at 200% zoom) on ten pages,
    focus mode and a live round: no sideways scrolling;
  - reduced motion from the device setting and from the app setting;
  - storage blocked entirely: the app works, Settings says preferences won't be kept;
  - forced colours: the focus indicator is still drawn.
- `e2e/a11y.spec.ts`: axe-core scans of every main screen in the default theme on desktop and a
  phone (since 2026-11-04 including a written answer with its feedback), and the skip link.
- `src/test/integration/careers.test.tsx`, "Answering with the keyboard": Enter in the answer
  box is a new line, never a submission (dictation inserts line breaks); keyboard submit moves
  focus to the feedback; a failed send keeps the text, the focus and the linked error, and a
  second Enter sends it. `e2e/mobile.spec.ts`: menu dismissal and focus return at 320–768px.

### Checks done by hand (this session, in this environment)

- Looked at screenshots of: the landing page and History at 320px with the largest text (light),
  Settings → Display & reading, a question in focus mode (dark + higher contrast), the coding
  workspace in focus mode with the editor's keyboard hint (light + higher contrast), and a live
  round in and out of focus mode.
- Read Chromium's accessibility tree (the structure a screen reader uses) for a question page, a
  live round in focus mode and interview results: landmarks, headings, names, the reading order
  of question → answer → actions, and status messages.
- Exploratory axe-core scans of 21 pages in all four themes (no violations) and a reflow sweep of
  21 pages at 320px and 640px with the largest text and spacious layout (the overflows listed
  above, all fixed).

### Not checked

- **No screen reader was used.** None is installed in this environment (no NVDA, JAWS,
  VoiceOver, Orca or TalkBack), so announcements and reading order were checked through the
  accessibility tree and ARIA roles, not by listening.
- **Chromium only.** Firefox and Safari/WebKit weren't run; real iOS/Android devices weren't
  used (the phone checks are Chromium with a phone viewport).
- **Browser zoom** was approximated by viewport width and the text-size setting, not the
  browser's zoom control; OS-level text scaling wasn't tested.
- **Forced colours** was checked for the focus indicator only, with Chromium's emulation.
- Speech input and the interviewer's voice depend on the browser's speech APIs, which this
  headless browser doesn't provide; voice paths are covered with fakes in unit tests.
- Testing with disabled users hasn't happened. That is the check that matters most.

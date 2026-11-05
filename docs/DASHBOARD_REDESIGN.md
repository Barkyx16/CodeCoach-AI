# Dashboard redesign (Pristine Dashboard Blueprint)

Applies the blueprint's dashboard prompts (2 to 6) to the existing app. It's a frontend refinement:
no backend contract, scoring or plan rule changed. Two deliberate deviations, both the owner's
later instructions:

- **Colour:** the blueprint's "keep the blue brand" predates the purple-and-black theme. Its palette
  roles (one primary, success only for confirmed success, quiet decorative borders, stronger control
  borders, three text levels) are mapped onto the purple tokens in `src/styles/tokens.css`.
- **Navigation:** the blueprint's 224 px sidebar (prompt 1) isn't built. The owner chose a top bar
  of four headings with hover panels (`src/app/MainNav.tsx`), which already groups every
  destination, keeps account controls on the right and gives narrow screens a labelled drawer.

## What changed

| Blueprint | Implementation |
|---|---|
| One page title with career and level | "Your interview practice" and "Registered Nurse · Easy level" (coding: "Coding problems · last active …"). The name moved to the account area. |
| Mock interview secondary; the recommendation owns the only filled action | The header keeps one outlined "Mock interview". "Practice questions" / "Practice now" were removed from the header (the library is under Practice → Questions). |
| Today flattened: no outer card, green stripe or dashed goal banner | `TodayCard.tsx`: "Today's practice", a labelled time selector, then an 8/4 split of the recommendation and a support rail. |
| Time available: one labelled single-select group | A `fieldset` with legend "Time available" and radios "5 min", "15 min", "30 min", styled as a segmented control. Arrow keys move the choice. |
| Quiet metadata, the task leads | `ActivityCard.tsx` (`featured`): type with icon, skill (hidden when it repeats the type), duration, then the title at 24/32. |
| Short reason and a visible completion rule | The plan's reason and "Done when:" are both shown in full. A "How this counts" disclosure wasn't added: the two lines are already short, and a disclosure would repeat them. |
| Start practice / Choose another / More options | One filled "Start practice"; "Choose another" (the existing swap) as a quiet text action; "More options" (`components/MoreOptions.tsx`, a disclosure) holds "Add to schedule" and "Skip for now", still separate actions. Escape closes it and returns focus. |
| Next item and session estimate | A footer under the recommendation: "Next: {title} · About N min" (expands to the follow-up with its own actions) and "Session estimate: about N min". It sits beside the recommendation's article, not inside it, so the follow-up's buttons aren't read as the recommendation's. |
| Weekly target keeps its own meaning | Rail card "This week": minutes / weekly planned minutes with a real bar, activities completed, days to the interview if set, reviews due, "Your full plan". |
| Optional setup becomes compact support | Rail card "Make the plan yours": "Set my goals" and "Not now" (accessible name "Not now, use a starter plan", the existing action). Shown only until goals are saved or skipped. |
| Compact, truthful metrics | Four tiles in a row (2×2 below 1024 px), a 32/40 tabular number, one-line detail: "of N unique questions", "Questions with a best score of 85 or more", the ended-early count when there is one, skills practised with the current level. |
| First-use message without another bordered box | One quiet line with an icon and "Answer a question" / "Start a problem". |
| More ways links become calm destination cards | `MorePractice.tsx`: one link per format with an icon, a one-line description and an arrow (same routes). |

Shared styles: the dashboard's layout lives in `src/styles/dashboard.css`, scoped to `.dashboard`,
`.today` and the new components. The old Today, More-ways and first-use rules were removed from
`plan.css`, `features.css` and `details.css`. `ActivityCard` is also used on the plan page, which
gets the same action layout.

## Meaning kept

- Real zeros stay zeros. Loading shows "Planning your session…", not 0, and the rail isn't drawn
  until the plan arrives. A failed plan shows the error and "Try again", after the client's usual
  retries.
- The time budget (5/15/30) and the session estimate stay separate and labelled: a 30-minute
  budget can hold an 18-minute session.
- Goals stay optional, and "Not now" still saves the starter-plan choice.
- Schedule, swap and skip remain distinct actions with their old behaviour.
- Metric definitions are unchanged: unique questions, the eligible-score rule for strong answers,
  completed interviews with the ended-early count, skills practised.

## Checks actually run

Viewport and state matrix (Chromium via Playwright, dark theme, built site against a fresh SQLite API):

| Check | Result |
|---|---|
| 320, 390, 768, 1024, 1280, 1440 px | no page-level horizontal overflow; "Start practice" 44 px tall, full width below 768 px |
| 200% zoom of a 1440 window (720 CSS px) | no horizontal overflow |
| Long recommendation title (synthetic) at 390 and 1440 | wraps and grows the card; no overflow or overlap |
| Populated (synthetic numbers via route interception) | 23 answered, 6 strong, 42 / 60 min, 4 activities, 9 days to the interview, shown as given |
| Loading (plan delayed) | "Planning your session…", no invented zeros |
| Plan error (500) | error with reference and "Try again" after 3 requests |
| Keyboard | arrow keys change the time choice; More options opens, Tab reaches "Add to schedule", Escape closes it and returns focus |
| Page errors during the runs | none |

Repository checks: frontend type check and lint pass; 660 unit tests pass (69 files),
including a new test for the time-available group, the single filled action and the More options
menu (Escape returns focus); the production build passes; bundle budgets pass (shell 294.3 KB of
300 KB, largest lazy chunk 674.5 KB of 700 KB). End-to-end (Playwright, real backend): the full
suite ran with 83 passed, 3 skipped and 9 failed. All 9 were tests still asserting the old wording
(the "…'s progress" heading and "each counted once however many tries"). They were updated to the
new wording and re-run with the other dashboard-related files (careers, learner journey, refresh
recovery, session, plan, journey, progress): 16 passed. CI on the pushed commit is reported in the
commit history and the progress log.

## Limits

- Chromium only. WebKit and Firefox aren't installed here; Safari wasn't checked by tests, only by
  the owner opening the site.
- No physical phone, screen reader or on-screen keyboard. 200% zoom was approximated by the
  equivalent CSS width, not the browser's zoom.
- Populated, long-title, loading and error states used synthetic responses in the browser; the
  backend wasn't changed to produce them.
- The app shell's bundle is 294.3 KB gzip against a 300 KB budget, so there's little headroom.

## Screenshots

Dark theme, 1440 px unless noted.

- Before: [dashboard-before-1440](screenshots/dashboard-before-1440.webp)
- After, new account: [dashboard-after-1440](screenshots/dashboard-after-1440.webp)
- After, phone width 390 px (top): [dashboard-after-390](screenshots/dashboard-after-390.webp)
- After, populated with synthetic numbers: [dashboard-populated-1440](screenshots/dashboard-populated-1440.webp)
- More options open: [dashboard-more-options-1440](screenshots/dashboard-more-options-1440.webp)

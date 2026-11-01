# CodeCoach AI — Frontend & Design Handoff

**Audience:** the design partner (ChatGPT) doing the visual design and layout pass.
**Split of ownership:**

| Owned by the design pass | Owned by engineering (don't change without a code change) |
|---|---|
| Colors, type, spacing, radii, shadows, motion (`src/styles/tokens.css`) | Data fetching, state, routing, auth (`src/api`, `src/auth`, `src/app`) |
| Layout and visual styling (`src/styles/*.css`) | Component *behavior* and props (`src/features/**/*.tsx`) |
| UX copy suggestions (send as a list; engineering applies them) | Accessible names, roles and labels that tests depend on (see §7) |
| Iconography, illustrations, empty-state art | API contract (`docs/API.md`, `docs/openapi.json`) |

The app is **fully functional today** with a working dark theme, so the design pass is a
restyle, not a build. Screenshots of the current state are in [`docs/screenshots/`](screenshots/).

---

## 1. Tech overview (what you're styling)

- React 18 + TypeScript + Vite. Plain CSS with BEM-style class names, **no CSS-in-JS**, no
  Tailwind. Every visual value comes from CSS custom properties in `tokens.css`.
- Monaco (the VS Code editor) for Java, themed in `src/features/workspace/monacoSetup.ts`
  (`codecoach-dark`). Editor colors are set there in hex, not via CSS variables, because
  Monaco needs literal colors.
- Resizable three-panel workspace on desktop (`react-resizable-panels`), tabs on screens ≤ 900px wide.
- Run it: `cd frontend && npm install && npm run dev`, with the backend on :8000
  (see the root README). Or `docker compose up --build` and open http://localhost:3000.

```
src/
  styles/tokens.css      ← start here: every color, size, radius, shadow, duration
  styles/base.css        ← element defaults, page container, utilities
  styles/components.css  ← buttons, badges, cards, inputs, banners, states
  styles/layout.css      ← header / nav / app shell
  styles/features.css    ← per-screen styles (landing, library, workspace, dashboard, history)
  components/            ← Button, Badge, Card, Field, Spinner, States (Loading/Error/Empty)
  features/<screen>/     ← screen components
```

## 2. Design tokens

All tokens are in `src/styles/tokens.css`. Rename nothing (components reference these
names); change values freely.

| Group | Tokens |
|---|---|
| Surfaces | `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-surface-sunken`, `--color-border`, `--color-border-strong` |
| Text | `--color-text`, `--color-text-muted`, `--color-text-subtle`, `--color-text-inverse` |
| Brand / actions | `--color-primary`, `--color-primary-hover`, `--color-primary-soft`, `--color-accent` |
| Semantic | `--color-success`, `--color-warning`, `--color-danger`, `--color-info` (+ `-soft` tints) |
| Difficulty | `--color-easy`, `--color-medium`, `--color-hard` |
| Data viz | `--viz-solved`, `--viz-attempted`, `--viz-track`, `--viz-heat-0` … `--viz-heat-4` |
| Type | `--font-sans`, `--font-mono`, `--text-xs` … `--text-3xl`, `--leading-*`, `--weight-*` |
| Spacing | `--space-1` (4px) … `--space-16` (64px) |
| Shape / depth | `--radius-sm/md/lg/full`, `--shadow-sm/md`, `--focus-ring` |
| Motion | `--duration-fast/normal`, `--ease-standard` (zeroed under `prefers-reduced-motion`) |
| Layout | `--header-height`, `--content-max-width` |

**Chart colors were validated** (the dataviz palette checker) against `--color-surface`
`#0d1628`: the solved/attempted pair is an ordinal blue ramp; the heatmap is a single-hue
sequential ramp whose zero step deliberately fades into the surface. **If you change
`--color-surface` or any `--viz-*` value, keep these rules:** one hue, light = more on dark
backgrounds, the non-zero steps at least 2:1 against the surface, and visibly different
adjacent steps. Don't introduce a rainbow, and don't reuse status colors (success, warning,
danger) as chart series.

Fonts: the stack names Inter and JetBrains Mono but **doesn't load them** (no external font
requests, which keeps the CSP strict). To use them, self-host the files under `public/fonts`
and add `@font-face` rules to `base.css`.

## 3. Screens and states

Every screen must have a designed version of each state listed. All of them already exist
functionally, and the screenshot column shows the current look.

### 3.1 Landing — `/` (`features/landing/LandingPage.tsx`) · `01-landing.png`
Hero (eyebrow, H1, lead, two CTAs), a static workspace preview, and four "how it works" steps.
- Primary CTA **"Try it now, no sign-up"** creates a guest session and opens Two Sum. For
  signed-in users it reads "Open a problem".
- States: default · CTA loading · CTA error (inline message under the buttons).

### 3.2 Auth — `/login`, `/register` (`features/auth/AuthPages.tsx`)
A centered card form. Register shows password rules as help text, and server-side
validation errors appear under the relevant field (`.field__error`, with `aria-invalid` on
the input).
- States: idle · submitting (button spinner) · field errors · general error (e.g. wrong
  password) · rate-limited ("Too many attempts…").
- Both pages offer **Continue as guest**.

### 3.3 Problem library — `/problems` (`features/problems/ProblemListPage.tsx`) · `04-library-filtered.png`
Search box, difficulty select, topic chips (toggle, with counts), a problem list, pagination,
and a *Recommended for you* sidebar when signed in.
- Each row: status icon (✓ solved · ◐ attempted · • in progress · blank), title, one-line
  summary, up to 2 topic tags, difficulty badge.
- States: loading · error with retry · empty ("No problems match" + Clear filters) ·
  refetching (list dims via `[aria-busy="true"]`).
- Filters live in the URL (`?topic=stacks&difficulty=easy&q=sum&page=2`).

### 3.4 Workspace — `/problems/:slug` (`features/workspace/*`) · `02-workspace-review.png`, `05-mobile-workspace.png`
The core screen. Desktop: **Statement | Editor over Results | Coach**, all resizable.
Mobile (≤ 900px): tabs **Problem | Code | Coach**.

| Region | Contents | States to design |
|---|---|---|
| Statement | Title, difficulty, topics, Markdown body, examples, constraints, method signature, public tests, hidden-test count | loading, not found |
| Editor toolbar | "Java", save status (*Draft saved* / *Saving…* / *Unsaved changes*), Reset, **Submit** | submitting |
| Editor | Monaco. Lines flagged by a review get `.editor-line--flagged` and `.editor-glyph--flagged` | flagged line |
| Results | Empty hint (shows the Ctrl/⌘+Enter shortcut) · status badge + spinner while judging ("Waiting for a judge…", "Running your code against the tests…") · verdict sentence · "x/y tests passed", "hidden: a/b", runtime · per-public-test rows ✓/✗ with expected vs. actual, the exception and its message, or "this test never ran" · **Compiler output** block for compile errors · when a deployment has execution off: the "Saved, but not run yet" banner (`08-judged-pass.png`) | Queued, Running, Passed, Failed, Compile error, Runtime error, Time limit, Memory limit, Judge error, execution off |
| Coach: Hints tab | Ladder of unlocked hints (Level N · Name, focus area, hint text, encouragement); one button for the next level; a warning before level 4 ("explains the full solution") | none unlocked · some · all unlocked · loading · budget exhausted (button disabled + message) · signed-out prompt |
| Coach: Review tab | Run button · summary · 3 complexity tiles (Time and Space with targets, Confidence; the time tile gets a warning border when it misses the target) · issue list (severity badge, category, **"line N" link that highlights the editor line**, detail, → suggestion) · strengths · Next step banner · disclaimer | not run · loading · result · error |
| Usage | "47/50 left" in the coach header | — |

### 3.5 Dashboard — `/dashboard` (`features/dashboard/*`) · `03-dashboard.png`
KPI row (Solved, Current streak, Acceptance rate, Coaching used) · Activity heatmap
(28 days, hover text, **Show table** toggle) · Up next (recommendations with a reason and a
kind badge: Finish it / Weak spot / Next step) · Solved by difficulty (single-series bars, no
legend) · By topic (solved + attempted segmented bars with a legend; figures always printed
beside the bars).
- States: loading · error · brand-new user (empty-state banner + "Start a problem") ·
  acceptance shows "—" until something is judged.

### 3.6 History — `/history` (`features/history/HistoryPage.tsx`)
Tabs: **Submissions** (table: problem, status, submitted, runtime) and **AI feedback**
(expandable cards; reviews re-render with the same review component).
- States: loading · error · empty for each tab · pagination.

### 3.7 Mock interview — `/interviews`, `/interviews/:id` (`features/interview/*`) · `06-interview-live.png`, `07-interview-feedback.png`
- **Start (`/interviews`):** problem select (or "Pick one for me"), time limit as a segmented
  radio group (15/30/45), a "How it works" card listing the 5 phases, and recent interviews.
  States: idle · starting · "already in progress" banner with a **Resume it** link · error.
- **Live session:** top bar (problem, difficulty, link to the statement, **phase stepper**,
  countdown clock that turns warning-colored under 2 minutes, End early, Finish & get feedback).
  Left: phase hint ("Now: …"), chat transcript (interviewer bubbles left, candidate bubbles
  right, phase dividers, typing indicator), composer (Ctrl/⌘+Enter to send, messages-left
  counter). Right: Monaco editor (code is shared with the interviewer on each message).
  States: sending (optimistic bubble + typing dots) · error (text is restored to the box) ·
  wrapped up (Finish becomes primary) · expired (auto-switches to results).
- **Results:** overall badge + confidence, summary, a **rubric chart** (5 single-series bars,
  1–4 scale, score and words printed beside each bar, evidence under it), What went well,
  Focus next time, a collapsible transcript, and the final code.
- History has an **Interviews** tab using the same row component.

### 3.8 Global
- Header: brand, nav (Practice, plus Interview, Dashboard and History when signed in), account area
  (name, or a "Guest" badge, with Sign out; signed-out users see Sign in and Create account).
- Session-ended banner under the header when a token expires or is revoked.
- 404 page. A skip-to-content link (visible on keyboard focus).

## 4. Component inventory

| Component | File | Variants / props |
|---|---|---|
| Button | `components/Button.tsx` | `variant`: primary · secondary · ghost · danger; `size`: sm · md; `loading` |
| Badge | `components/Badge.tsx` | tones: neutral · success · danger · warning · info · difficulty-easy/medium/hard. Also `DifficultyBadge`, `StatusBadge` (9 judge statuses), `TopicTag` |
| Card | `components/Card.tsx` | — |
| Field | `components/Field.tsx` | label, optional, hint, error (wired with `aria-describedby`) |
| Spinner | `components/Spinner.tsx` | sm · md |
| Loading / Error / Empty / Inline error | `components/States.tsx` | Error shows a friendly title, the message, and the request id as "Reference" |
| Banner | CSS only (`.banner`, `--warning`, `--danger`, `--success`) | — |
| Tabs, Chips, Pagination, Data table | CSS only (`.tabs/.tab`, `.chip`, `.pagination`, `.data-table`) | — |

## 5. Interaction and accessibility requirements (keep these)

- **Keyboard:** everything reachable by Tab; visible focus (`--focus-ring`);
  Ctrl/⌘+Enter submits from the editor; panels resize with the keyboard (library built-in).
- **Never color alone:** status badges have text; problem status icons have `aria-label`s;
  issues show the severity as text; charts print figures beside bars and offer a table view.
- **Contrast:** body text ≥ 4.5:1 and large text and UI ≥ 3:1 against its surface.
- **Motion:** respect `prefers-reduced-motion` (durations already go to 0).
- **Live regions:** save status, submission results and review results use `aria-live` /
  `role="status"`. Keep those wrappers.

## 6. Responsive breakpoints in use
`≤ 960px` library sidebar stacks · `≤ 900px` workspace switches to tabs · `≤ 860px`
dashboard is one column · `≤ 720px` header hides the brand name and user name ·
`≤ 600px` filters stack and row topic tags hide.

## 7. Rules that keep the tests green

The automated tests (48 unit/integration + 4 Playwright end-to-end) find elements **by their
accessible role and name**, not by CSS. Restyling is safe as long as you **don't change**:
- visible button, tab and link text used as names (e.g. "Get a hint", "Unlock level 2: Concept",
  "Review my code", "Submit", "Show table", "Sign in", "Create account", "Try it now, no sign-up",
  "Start interview", "Send", "Finish & get feedback", "Resume it"),
- headings' text, form labels ("Email", "Password", "Name"),
- `aria-label`s on regions ("AI coach", "Summary", "Problem list", "Workspace" tablist,
  "Interview progress", "Rubric scores, out of 4", "Your answer"), and `role="timer"` on the clock,
- the class names `.monaco-editor`, `.editor-line--flagged` and `heat-cell` test ids.

If copy changes are wanted, list them and engineering will update the tests in the same change.
Run `npm test && npm run e2e` to check.

## 8. Ideas for the design pass (optional)
Self-hosted fonts · a logo mark · illustrations for empty states · a richer landing hero
(animated hint-ladder demo) · celebratory state when a problem is solved (once the judge
ships) · a light theme (add a `[data-theme="light"]` token block, and re-validate the chart
colors for the light surface).

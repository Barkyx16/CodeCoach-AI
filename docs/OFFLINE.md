# Installable app and offline use

CodeCoach can be installed as an app where the browser supports it, and keeps working in a
limited, honest way without a connection. This page says exactly what works offline, how it's
built, what is stored on the device and how it is cleared.

## What works offline

| Works without a connection | Needs the server |
| --- | --- |
| Opening the app, once it has loaded fully online in this browser | Signing in, registering, checking a session |
| Lessons, questions and coding problems you chose to **Save for offline** | Anything you didn't save (it says so and links to what is saved) |
| Writing an answer draft and editing code: kept on this device, labelled "Draft saved on this device, not sent yet" | Feedback on an answer, the AI coach, code reviews |
| Editing a note you already saved: "Offline: saved on this device. Sync pending", sent once when the connection returns | Creating a new note (kept on the device; you press "Save now" when back online) |
| Reading the lesson and choosing check answers | Grading the lesson check |
| | Running and judging code (Run and Submit are paused, with the reason shown) |
| | Mock interviews, follow-ups, voice (speech recognition needs the network), shared links |
| | Your history, analytics, plan, notes list, saved collections and other account pages |

Nothing is ever graded, judged or scored on the device, and a draft is never shown as sent.

## How it's built

- **Manifest and icons**: `public/manifest.webmanifest` (standalone display, 192/512 PNG icons
  plus a maskable one, rendered from the SVG mark by `scripts/render-icons.mjs`), an Apple touch
  icon and a theme colour in `index.html`.
- **Service worker** (`public/sw.js`, production builds only; the dev server doesn't register it):
  - Precaches a small public shell: `index.html`, the files it loads, fonts, icons. The list
    and a version hash are filled in after `vite build` by the `offlineShell` plugin in
    `vite.config.ts`, which fails the build if the placeholders aren't replaced.
  - Navigations are network-first and fall back to the cached `index.html` offline.
  - Other built files (`/assets/*`, e.g. the code editor) are cached the first time they're used,
    but only files that belong to the current build; on update, unchanged ones are carried over
    and the rest deleted.
  - It **never handles API requests** (cross-origin, or `/api/` on the same origin) or anything
    but GET, and there is no catch-all handler, so private responses can't enter its caches.
    Where the browser supports service-worker static routing (Chromium), `/api/*` requests are
    also routed straight to the network without waking the worker. A
    Playwright test visits the dashboard, history and notes and then checks that no cached URL is
    an API URL.
- **Save for offline** (`src/features/offline/offlineStore.ts`): the page fetches the **public**
  copy of a lesson, question or problem without credentials (so it can't contain a personal best
  score or answers) and stores it in its own cache, `codecoach-offline-v1`, with the date and
  version. At most 50 items. Lesson, question and problem queries try the network first and use
  the saved copy only when the network fails. The Saved for offline page (`/offline`) lists items
  with sizes and the browser's storage estimate, and removes them one by one or all at once.
  When it's opened online it checks every saved item again: anything retired or no longer public
  (404/403/410) is removed from the device and reported.
- **No silent replays**: React Query runs with `networkMode: "always"`, so requests fail fast
  offline (no endless spinners), and mutations are never paused and replayed on reconnect. An
  answer, a code submission or an interview turn is only sent when the learner presses the
  button again. Retries that are safe are explicit: code submissions reuse their request id;
  a note edit is guarded by its revision, so a newer version saved elsewhere becomes a
  side-by-side choice (the existing conflict view) instead of being overwritten.
- **Offline isn't signed out**: when the server can't be reached the session isn't ended. The
  app remembers which account last used the device (id and display name only, never a token,
  key `codecoach.device-user.v1`), shows "Offline" with that name, keeps that account's drafts
  visible, and checks the session again when the connection returns. Account pages show "This
  page needs a connection" instead of redirecting to sign-in. While the browser reports being
  offline the app doesn't send refresh requests at all, and when the network returns it first
  checks that the API answers (a plain `GET /health`) before using the one-use refresh cookie.
  Testing showed why: the first request after reconnecting can go out on a connection that died
  while offline and be resent by the browser; a resent refresh looks exactly like a stolen
  cookie, and the server's reuse protection ends the session.
- **Updates**: a new version installs in the background and waits. A banner offers "Update now"
  or "Later"; nothing reloads on its own. Drafts are already on the device, so updating keeps
  them; if something on the page couldn't be stored (storage blocked or full), "Update now" asks
  first, and closing the tab triggers the browser's "leave this page?" prompt.
- **Install**: the "Install the app" setting appears only when the browser has offered it
  (Chromium's `beforeinstallprompt`); otherwise Settings explains how to install on iPhone/iPad
  (Share, Add to Home Screen) and that desktop Firefox doesn't install web apps.
- **Headers**: `nginx.conf` serves `sw.js` and the manifest with `Cache-Control: no-cache` (so
  updates are noticed) and the manifest as `application/manifest+json`. The existing CSP already
  allows `worker-src 'self'`.

## What's stored on the device, and when it's cleared

| Stored | Where | Cleared |
| --- | --- | --- |
| App shell and built files | Cache Storage `codecoach-shell-<version>`, `codecoach-assets-<version>` | Replaced on each update |
| Saved public lessons, questions, problems | Cache Storage `codecoach-offline-v1` | When you remove them, or when they're retired |
| Answer, code, lesson-exercise and interview-round drafts; note recovery copies | localStorage, keyed by account | Sent and cleared, or **deleted when you sign out** (after a warning if any are unsent) |
| Which account last used the device | localStorage `codecoach.device-user.v1` | On sign-out |
| Display, editor and voice preferences | localStorage | Kept: device settings, not account data |

Drafts are keyed by account, so another account signing in on the same device never sees
them. Signing out deletes the signed-out account's drafts from the device; public saved pages
stay (they're not personal).

## Checks

- `npm test`: the offline store (public copies fetched without credentials, list/read/remove,
  network-first fallback, retired items removed on reconnect), the Saved for offline page, an
  offline launch keeping the last account's draft with feedback paused and no refresh sent,
  account pages offline, mutations never replayed, the sign-out policy and its warning, the
  update banner (waits; asks when a draft couldn't be kept), and note sync on reconnect.
- `npm run e2e` (projects `pwa` and `pwa-mobile`, the production build on port 4173, real API):
  first load installs the worker; saved lesson, question and problem work offline; a draft stays
  and feedback is disabled; an unsaved page and an account page say what they need; a new tab
  opened with no network loads the saved list (with an axe scan); no API response is in any
  cache; reconnecting restores the session and the draft can be sent; a note edited offline
  syncs on reconnect and an edit made on another device becomes a conflict choice; signing out
  deletes the drafts and the next account sees none; blocked storage is reported and closing
  the tab asks first; an update waits, keeps the page and the draft, and applies on request;
  the manifest and icons are valid and a phone-sized offline launch reflows.

## Limits and checks not done

- **No real devices.** Installation, home-screen launch and OS-level offline on iOS, Android,
  macOS or Windows weren't tested; the phone checks are Chromium with a phone viewport and
  Playwright's network emulation. The install prompt isn't offered in headless Chromium, so the
  "Install CodeCoach" button was not exercised; the fallback instructions were.
- Safari and Firefox weren't run. Safari limits storage for sites that aren't installed and may
  clear it after a period of no use; that's outside the app's control.
- Playwright's offline emulation doesn't drop open connections the way a real network loss does,
  and doesn't stop every request a service worker passes through; the tests also refuse the API
  at Playwright's routing layer while "offline". The offline journeys were run 5 times each in a
  row without a failure after the reachability fix (they failed about 1 run in 4 before it).
- Reloading at the exact moment the app re-checks a session after reconnecting can lose the
  rotated refresh cookie; the server's reuse protection then ends the session and you sign in
  again. This is deliberate: an abandoned refresh is indistinguishable from a stolen cookie.
- Storage estimates come from `navigator.storage.estimate()` and are approximate; some browsers
  don't provide them, and the page then doesn't show one.

# Email verification as a recovery journey (Volume 7, prompt 5)

A learner who signs up knows where the code was sent, what the app knows about that email, and
what to do next. A link that doesn't work says why, and the learner ends up where they were going,
whichever tab or device the link was opened on. This builds on the existing outbox, SMTP outcomes,
correlation ids and "Check your email" page (docs/EMAIL.md). There is no new transport, worker or
token scheme.

**This is not evidence that email reaches an inbox.** No real email was sent. The browser tests
read emails from the file capture transport (`EMAIL_BACKEND=file`). The original "verification
emails never arrive" issue stays open until an authorized live send to an inbox you own is checked
(docs/EMAIL.md, "Delivery status").

## What the learner sees

- **Where it went, masked.** "We send a 6-digit code to a•••e@example.com". The domain is shown, so
  a typo there is visible. **Show full address** shows the whole address (the signed-in owner's own).
- **What became of the latest email**, from `GET /api/v1/auth/verify-email/status`, in the outbox's
  own terms:

  | State | Wording |
  |---|---|
  | queued | Sending it now. The page looks again every 3 s (every 15 s after about two minutes) until it changes |
  | retrying | Not sent yet; the first try didn't go through; it's tried again automatically (with the next try's time) |
  | sent to provider | Sent at 10:42: our mail server handed it to your email provider. We can't see whether it has reached your inbox. |
  | kept locally | Not emailed: printed in the `./dev.sh` window (console), or saved under `EMAIL_FILE_DIR` (file) |
  | failed | We couldn't send it. Send a new code; if that doesn't arrive either, try again later. |
  | unknown | We have no record of the latest email. |

  Nothing says "delivered". No SMTP code, host or error class reaches the page. Those stay in
  `email-status` and the logs.
- **How long the code works**, and that only the newest email's code and link work. If none
  works now: "Your last code no longer works. Send a new one."
- **Send a new code**:
  - waits for the server's cooldown from the moment the page opens (not only after a click);
  - sends one request however often it's pressed;
  - announces the masked address it went to;
  - on failure, says so and comes back. It never shows a success it didn't get.
- **Not in your inbox?** offers:
  - spam or junk, and searching for "CodeCoach AI";
  - checking the address;
  - changing it in Settings (password required, the existing rule);
  - a new code;
  - carrying on and confirming later, or signing out.

  There are no invented delays, and no guesses presented as a diagnosis.
- **On a development server** the page says the email stayed on that computer, and where: the
  terminal running `./dev.sh`, or the `EMAIL_FILE_DIR` folder. No page or API response ever
  carries a code or link. Production refuses to start without SMTP, so learners there are never
  promised an email the server can't send. Operators see the problem at startup and in
  `preflight`.

## Links that don't work

`POST /api/v1/auth/verify-email` answers `400 invalid_verification_token` with `details.reason`:

| Reason | Screen | The way on |
|---|---|---|
| `malformed` (caught in the browser before sending) | This link is incomplete | Enter the code instead (or Continue, if already confirmed) |
| `unknown` | We don't recognise this link | Get a new code / Sign in |
| `expired` | This link has expired (links work for N hours) | Get a new code / Sign in to get a new code |
| `superseded` | A newer email replaced this link | the same |
| `already_verified` | This email is already confirmed | Continue / Sign in |
| `address_changed` | This link is for an earlier request | Get a new code |
| `stopped` (too many wrong codes) | This link no longer works | Get a new code |

Only someone holding the link (a 256-bit secret) can ask, so the reason reveals nothing about other
accounts. A made-up link gets the same answer whoever asks.

**Another account's link, opened while signed in**, isn't used straight away: `409
verification_link_other_account` with the link's address masked (`a•••@e•••.com`). The screen says
who is signed in and that nothing has changed. **Confirm that account's email** sends it again with
`other_account_ok`. That confirms the other account's address, and this session stays as it was,
with no details of that account. **Don't use it** goes back.

Only the account's own signed-in session gets the account back from a link. Anyone else learns that
it worked, and a masked address. Before this change the link endpoint returned the full account
(`UserOut`: address, name, career track, pending address) to anyone holding the link.

## Getting back to where the learner was going

- `safeReturnPath` (`frontend/src/lib/links.ts`) accepts only an in-app path. These fall back to
  the default:
  - `//host` and `/\host` (both leave the site in a browser);
  - absolute URLs;
  - control characters (`/\t/host` becomes `//host` in a browser);
  - the sign-in screens, which would loop.

  It applies to `from` after sign-in and to `next` after verification.
- `from` is carried between **Sign in** and **Create account**. So "signed out on /history → sign in
  → create an account → confirm" ends on /history.
- The page remembers where this account was going (`frontend/src/auth/emailVerified.ts`: per
  account, this browser, re-checked when read). So **a link opened in a new tab** continues there.
- **The tab still waiting moves on by itself.** The confirming tab announces it through this
  browser's storage. The waiting tab refreshes the account and says "You confirmed it in another tab
  or on another device". Settings updates too. Another device finds out when its tab is focused
  again (the status is re-read on focus).
- **A link pasted into a tab already on "Check your email"** changes only the `#token` part. The page
  now notices, and checks the link again if it's pasted twice. The browser test found this: before
  the fix, nothing happened.

## Tests

- **Backend**, `backend/tests/test_verification_journey.py` (16), plus updated
  `test_email_verification.py` and `test_account_recovery.py`. Covered:
  - queued, then kept locally;
  - a worker failure (fake SMTP 451): retrying, then failed, never sent, nothing about the server
    in the answer;
  - a 250, sent to provider; a 550, failed;
  - no record, unknown; a cancelled change not mistaken for this address;
  - the cooldown: matches `Retry-After`, and a second click gets 429;
  - a raced duplicate send: one email;
  - a delayed older message can't verify and says it was superseded;
  - an older email for a replaced change can't move the account;
  - every link reason; too many wrong codes stop the link;
  - another account's link: 409, nothing changed, then `other_account_ok`;
  - the owner's own session gets the account;
  - no response carries a code or link, even on a console server;
  - public answers (password reset, a made-up link) don't reveal whether an address has an account.
- **Frontend**, `frontend/src/test/integration/verificationJourney.test.tsx` (38), plus updated
  `account.test.tsx`. Covered:
  - each delivery state's wording, polling while queued, the console and file notes;
  - the help;
  - the cooldown on open; one request for three clicks; a failed resend;
  - each link screen and its way on; the cut link caught without a request; a lost answer retried;
  - the other-account flow, sent as this session;
  - a remembered destination in a new tab, and the signal to other tabs;
  - the waiting tab moving on, ignoring another account's signal, and on focus;
  - Sign in → Create account → confirm returning to /history; an outside `from` refused;
  - a link pasted into the same tab;
  - `safeReturnPath` cases.
- **Browser**, `frontend/e2e/verification-journey.spec.ts`: two tests against the real API and the
  file capture transport.
  - Signed out on /history → create an account → masked status, kept-locally wording, the cooldown,
    the help, axe → the link in a second tab → the first tab moves on → both continue to /history.
    The same link again says it's already confirmed; a cut link says it's incomplete (axe).
  - A second browser context signed in as another account opens the first account's link: asked
    first (axe), confirmed, still signed in as itself, its own email still pending. The first
    account's tab shows it confirmed.

## Verified (locally, on `43731c8`)

- Backend, the whole suite on SQLite: 2488 passed, 422 skipped (PostgreSQL-only), 2 expected
  failures. On PostgreSQL 16, as an app role without RLS bypass: the verification, account recovery,
  password reset and route access tests, 55 passed.
- Frontend: lint, types, the API contract (`api:check`), 802/802 unit and integration tests, the
  production build, and the bundle budgets (shell 211.5 KB, largest lazy chunk 674.5 KB of 700 KB,
  gzipped).
- Browser (Chromium, desktop, real API, file capture transport): the whole desktop suite, 88 passed
  (3 judge tests skipped; CI's sandbox job runs them), including both new tests with axe.
- Secret scan: no new findings.

## Limits

- **Inbox receipt is unverified.** See the top of this page. "Sent to provider" is the most this code
  can claim; a provider's delivery events would be needed for more (docs/EMAIL.md).
- **The waiting tab learns on the next signal**: instantly in the same browser, on focus on
  another device. There is no push between devices.
- **Where the learner was going is remembered per browser.** A link opened on a phone continues
  to the dashboard there.
- **A link opened while the session's access token has just expired** is sent without the session.
  It still works, as a signed-out confirmation, and the page then reads the account again.
- **The status keeps finished outbox records for a week** (`KEEP_FINISHED`). After that, an old
  email's state is "unknown".

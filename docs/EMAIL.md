# Email: verification codes and password resets

CodeCoach sends three kinds of email: a 6-digit verification code (with a link) after sign-up,
a password-reset link, and a notice to the old address when someone changes their email.

## On your own computer (`./dev.sh`): nothing is sent

Unless a mail server is set up, nothing leaves your computer. Each email is printed in the
Terminal window running `./dev.sh`, in a box like this:

```
┌────────────────────────────────────────────────────────────────────────
│ EMAIL (not sent: this server has no mail server set up; see docs/EMAIL.md)
│ To:      you@example.com
│ Subject: 123456 is your CodeCoach AI verification code
│ …
└────────────────────────────────────────────────────────────────────────
```

Type that code on the "Check your email" page (or open the link in the box). The page itself
also says that the email wasn't sent, when that's the case.

## Sending real emails

The app sends through any SMTP mail server. Put the settings in a file named `.env` in the
project folder (next to `.env.example`, which lists every setting). That file is never
committed: `.gitignore` excludes it. Then restart `./dev.sh`.

**Never paste a password into a chat, an issue or a commit.** It goes only in `.env`, or, for a
deployed site, in the host's secret settings.

### Quickest, for testing: a Gmail account

Gmail needs an "app password", not your normal one: turn on 2-Step Verification for the Google
account, then create an app password at https://myaccount.google.com/apppasswords.

```
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your.address@gmail.com
SMTP_PASSWORD=the-16-character-app-password
EMAIL_FROM=CodeCoach AI <your.address@gmail.com>
APP_BASE_URL=http://localhost:5173
```

Gmail limits how much one account can send per day and is meant for personal use, so use it
only for testing.

### For a real launch: an email service

Use a transactional email service, which gives you SMTP settings. Examples: Amazon SES, Postmark,
Resend or SendGrid. Each one has you prove you own your domain (a few DNS records), so emails
come from `no-reply@yourdomain` and land in inboxes, not spam. Use the same settings as above
with their host, port, username and password, and set `APP_BASE_URL` to the site's real `https://`
address. Production refuses to start without SMTP or with a non-https `APP_BASE_URL`, so emailed
links can't point anywhere else.

### How the connection is protected

`SMTP_SECURITY` chooses the mode:

| Mode | Port | When to use it |
|---|---|---|
| `starttls` (default) | usually 587 | most providers |
| `ssl` | usually 465 | providers that use implicit TLS |
| `none` | | a local test server only. Production refuses it |

In both encrypted modes the server's certificate **and** hostname are verified. Before
2026-11-08, the STARTTLS path used Python's unverified default, which accepted any certificate; a
test now shows the old call accepting a self-signed one. `SMTP_CA_BUNDLE` adds a private CA (for
an internal relay). Nothing turns verification off. `SMTP_TIMEOUT_SECONDS` (10) bounds each
attempt.

Production also refuses:
- `EMAIL_FROM` on `@localhost`;
- `SMTP_SECURITY=none`;
- any backend other than `smtp`.

### Check it before you rely on it

```bash
python -m app.cli check-email                 # settings by name and presence only, never values
python -m app.cli check-email --connect       # connect, verify TLS, sign in; sends nothing
python -m app.cli check-email --send-test you@example.com   # sends ONE test email
```

`--send-test` reports at most "the mail server ACCEPTED the test email". That's not proof it
arrived: check the inbox, and the spam folder.

## What each stage means

| Job status | Meaning | Known? |
|---|---|---|
| `pending` | queued; the first try runs right after the response, retries back off (30 s, 2, 10, 30 min) | yes |
| `accepted` | the mail server answered 250: it **took** the message | yes |
| delivered to the inbox | the receiving server stored it | **not known**: needs a provider's delivery events |
| read | the person opened it | **not known**, and not tracked |
| `rejected` | the mail server refused it for good (a 5xx, e.g. no such mailbox); not retried | yes |
| `failed` | still failing after 5 attempts (an outage, a 4xx, a timeout, a bad SMTP password) | yes |
| `dropped` | too old to be useful (a reset link past its 30 minutes) | yes |
| `skipped` | nothing to send (already verified, no such account, or a duplicate within a minute) | yes |

Each email carries a `Message-ID` (`<codecoach.JOB_ID@your-domain>`), stored on its job, so a
provider's logs can be matched to the job. Logs name the job, its kind and an SMTP code or error
class. They never contain an address, subject, code or link (`tests/test_email_transport.py`).

## Verification: the states

| State | What's true | What the person sees |
|---|---|---|
| unverified, code on its way | a job is queued; when it runs, a fresh code and link are made and sent | "A 6-digit code is on its way to …", "Send a new code", and "Wrong address? Change it in Settings" |
| code issued | one live code per address: HMAC-hashed with the server key, 48 hours, at most 5 guesses | the same page survives a refresh (it reads the signed-in account, nothing local) |
| resend | allowed once a minute per account (`429 resend_cooldown` with `Retry-After` before that); a new code replaces every older one | the button counts down; an older code typed later is answered "replaced by a newer one" |
| verified | set only by the server, after a correct code or a valid link | "verified" appears only after the server says so |

Rules enforced on the server:
- A code or link works once. Each is claimed with one conditional database update, so two
  parallel requests can't both use it.
- Wrong guesses are counted the same way, before the code is compared, so parallel guesses can't
  share a count. Before 2026-11-08 they could: a test against the old code saw "4 tries left"
  twice.
- An address that changed since a link was sent makes that link invalid.
- Nothing in the app is restricted to verified accounts; verification is encouraged, not
  required ([SECURITY.md](SECURITY.md)). So nothing needs enforcing beyond the rules above.
- Changing a mistyped address needs the signed-in account and its password (Settings). Knowing
  an account's id is never enough. See "Changing the email" below.

## Changing the email (and recovering an account)

A change of address waits for the new address to confirm. Until then nothing about the account
changes: it signs in with the current address, and password resets go there.

| State | What's true | What the person sees (Settings, Email) |
|---|---|---|
| no change asked | `pending_email` is empty | the current address and its badge |
| change asked | needs the password; `pending_email` holds the new address; a code and link go there; a **verified** current address gets a notice that names the new one and links to "reset your password" | "Changing to new@…, Waiting for the code", "Enter the code", "Cancel this change" |
| confirmed | the right code (signed in) or link (any device) swaps the address, marks it verified, clears `pending_email`, and tells the old address it changed | the new address, verified |
| cancelled | the person cancels, asks for a different address, a password reset or a password change happens, or the new address is taken by someone else before it confirms: `pending_email` is cleared and its codes and links stop working | the current address, unchanged |

Rules enforced on the server (`tests/test_account_recovery.py`, `tests/test_email_verification.py`):
- The address only changes when a code or link sent **to the new address** is used. A code sent
  to an address that's no longer pending is refused.
- A second request replaces the first: the first address's codes stop working.
- The notice to the old address names the new one only if the old address was verified. An
  unverified address may have been mistyped, so it might belong to someone else.
- A password reset from the current address, or a password change in Settings, cancels a pending
  change. The emailed link works without signing in, so ending sessions alone wouldn't stop
  whoever asked for the change. A test without that rule saw the pending change survive a
  password change.
- If someone else signs up with the new address before it confirms, the change is cancelled with
  `409 email_taken` and the account keeps its address.
- Resending a code goes to the pending address, with the same one-a-minute limit.

### Which sessions end

| Event | Other devices | This device |
|---|---|---|
| password reset (emailed link) | signed out | (signed out; sign in with the new password) |
| password change (Settings) | signed out | stays signed in with a fresh session |
| "Sign out of all devices" | signed out | signed out |
| email change confirmed | **stay signed in** | stays signed in |
| change asked or cancelled | stay signed in | stays signed in |

A confirmed email change keeps sessions because it proved control of both the account (password)
and the new address (code). If someone else made the change, the old address got a notice when it
was asked for, and again when it was confirmed. Its owner can then reset the password from the
current address while the change is pending, which cancels it, or ask support afterwards. That
second path is manual: there is no self-service "undo" link in the notice yet.

Not covered: recovery when the person has lost both the password and access to the address.
That needs a human check; the app has no support console for it.

## How sending works

Emails are saved as jobs before they're sent, then retried with backoff if the mail server is
down, so a restart or an outage doesn't lose them ([HARDENING.md](HARDENING.md), "Background
jobs"). A job never holds the code or the link itself. Those are made when the email is
actually sent.

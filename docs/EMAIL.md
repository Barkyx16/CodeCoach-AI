# Email: verification codes and password resets

CodeCoach sends three kinds of email: a 6-digit verification code (with a link) after sign-up,
a password-reset link, and a notice to the old address when someone changes their email.

## Delivery status (2026-11-08): what's proven, and what isn't

| Question | Answer | Evidence |
|---|---|---|
| Why didn't the verification code arrive on your Mac? | A local run (`./dev.sh`) without mail settings uses the **console** backend: nothing is sent. The code is printed in the dev.sh window, in a block headed "EMAIL (not sent: this server has no mail server set up)", and the "Check your email" page says so. | `tests/test_email_dev.py` |
| Is real sending implemented? | Yes: SMTP with a verified certificate (STARTTLS or implicit TLS), sign-in, a Message-ID per email. | `tests/test_email_transport.py` (against a local fake mail server with a throwaway CA) |
| Are the stages kept apart? | Queued → sending → **accepted** (the mail server took it, which isn't an inbox) / rejected (permanent, never retried) / failed (after 5 attempts, with backoff). A worker restart delivers once; resends have a cooldown; codes expire, can't be reused, and five wrong ones kill a code. A send being accepted never verifies an account: only the code or link does. | the same file, plus `test_email_verification.py`, `test_email_delivery_problems.py`, `test_account_recovery.py`: **47 passed** on this tree |
| Do codes or links leak into logs? | Not on any path tested: the logs carry the job, Message-ID, stage and error class, never the address, subject or code. | `test_logs_never_carry_the_address_subject_or_code` |
| Is a provider configured here? | **No.** This sandbox has no provider account, and no credentials were requested or used. | — |
| Has a real email reached an inbox? | **Unverified.** Nothing real has been sent. | needs the steps below |

What closes the last two rows (your decisions; nothing here can do them):
1. Choose a provider: any SMTP relay. [Sending real emails](#sending-real-emails) has the
   settings, with a Gmail app password as the quickest way to test on your own computer. For
   launch, verify a sender domain with an email service: DNS records (SPF, DKIM, DMARC), in
   your DNS.
2. Put its settings in the server's `deploy/.env.app` or your host's secret settings, never in a
   chat or a commit: `EMAIL_BACKEND=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`,
   `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`.
3. `python -m app.cli check-email --connect` (connects, TLS, signs in, sends nothing), then
   `check-email --send-test you@your-domain` to **an inbox you own**. Check it arrived, and not
   in spam.
4. Sign up once through the real site with that address and use the code. Until then, "accepted
   by the provider" is the most this code can claim.

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

## When emails don't arrive

### What the app knows, and what it can't

| Problem | Seen by the app? | Where it shows |
|---|---|---|
| Mail server down, timing out, deferring (4xx), or a bad SMTP password | yes | job `pending` with `last_error`, then `failed` after 5 attempts |
| Mail server refused the recipient for good (5xx at send time) | yes | job `rejected`, never retried |
| Accepted, then bounced later by the receiving server | **no** | the provider's dashboard, or a bounce email to the sender address |
| Delivered to the inbox, or to spam | **no** | the provider's dashboard |
| The person marked it as spam (complaint) | **no** | the provider's dashboard |

The "no" rows need the provider's delivery events (webhooks). They aren't connected, because
no provider has been chosen yet. Until then those states stay unknown, and nothing in the app
calls an email "delivered".

### Diagnosing (on the server)

```bash
python -m app.cli email-status                         # counts by status + the 20 newest jobs
python -m app.cli email-status --account ada@example.com
python -m app.cli email-status --message-id '<codecoach.JOB_ID@your-domain>'
```

Each line shows:
- the job and its kind;
- status, attempts and the error class or SMTP code;
- the account id;
- the recipient's domain only (`to=*@gmail.com`);
- the Message-ID, which is how the email appears in a provider's logs.

It never shows an address's local part, a subject, a code or a link. There's no web page for
this: it needs shell access to the server.

### Recovering after an outage

An outage ends with each email in `failed` after 5 attempts (30 s, 2, 10, 30 min apart). It
never resends endlessly (`tests/test_email_delivery_problems.py`). Once the mail server works
again:

```bash
python -m app.cli check-email --connect      # it really works now
python -m app.cli email-retry --failed       # verification emails from the last 24 h (--hours N)
```

- Each retried email is sent once.
- A code that outlived its 48 hours is dropped rather than sent, and an address verified
  meanwhile is skipped.
- Reset links and change notices aren't retried: their addresses were cleared when the job
  finished, and a reset link would usually be past its 30 minutes anyway. People can request a
  reset again, and "Send a new code" works for verification.
- `rejected` emails are never retried. The address should be corrected (Settings → Email).

### Sender domain: SPF, DKIM, DMARC

Before launch, mail must come from your own domain, authenticated:
- **SPF**: a TXT record that lists the servers allowed to send for the domain.
- **DKIM**: a public key in DNS; the provider signs each message with the private half.
- **DMARC**: a TXT record at `_dmarc.<domain>` saying what receivers do when SPF/DKIM fail, and
  where to send reports. Start with `p=none` and tighten after a few weeks of clean reports.

Every transactional provider (Amazon SES, Postmark, Resend, SendGrid, …) shows the exact records
to add once you register your domain with it. No records are listed here, because none come from
a real provider configuration. Nothing in DNS has been changed.

### When a provider is chosen (blocked until then)

These steps need the provider's account and documentation:
1. Its SMTP settings go in `deploy/.env.app` (above).
2. Its delivery webhooks: verify each request with **that provider's documented signature
   scheme** over the raw request bytes, and reject replays (event ids, timestamps). Match
   events to jobs by Message-ID, and keep the most severe or latest state when events arrive out
   of order.
3. A hard bounce or complaint should stop further mail to that address. It must never change
   the account's email or its security settings. Only signed events count, and no response
   reveals whether an address has an account.
4. Tests with the provider's signed sample events or its sandbox.

Until then, the outbox's own statuses are the whole truth the app has.

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

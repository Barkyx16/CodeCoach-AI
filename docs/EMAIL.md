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

## How sending works

Emails are saved as jobs before they're sent, then retried with backoff if the mail server is
down, so a restart or an outage doesn't lose them ([HARDENING.md](HARDENING.md), "Background
jobs"). A job never holds the code or the link itself. Those are made when the email is
actually sent.

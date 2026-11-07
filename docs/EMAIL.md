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

## How sending works

Emails are saved as jobs before they're sent, then retried with backoff if the mail server is
down, so a restart or an outage doesn't lose them ([HARDENING.md](HARDENING.md), "Background
jobs"). A job never holds the code or the link itself. Those are made when the email is
actually sent.

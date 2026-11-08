# Launch readiness (Volume 5): handoff

Ten prompts, from "verification emails never arrive" to a launch preflight. Each section says:
- what changed;
- which **real defects** were found, and how each was shown before being fixed;
- how far it's verified. The levels are:
  - **local** (this sandbox: SQLite, PostgreSQL 16 with an ordinary role, Docker);
  - **CI** (needs a push: none has run on these commits);
  - **deployment** (none exists).

Nothing here was deployed, purchased, emailed for real or published. The DNS is unchanged, and
authentication is still the app's own; no move to Clerk or Firebase. The one push in this batch
was `b43c664`, early on. Every later commit is local, awaiting your go-ahead.

## Per prompt

| # | Prompt | What changed | Real defects found (and shown first) | Verified |
|---|---|---|---|---|
| 1 | Make verification emails arrive | SMTP with **verified** TLS (starttls/ssl), typed outcomes (accepted / rejected / failed), a Message-ID per job, `check-email [--connect] [--send-test]`, a start-up notice when nothing is sent | STARTTLS used Python's unverified default and accepted a self-signed certificate (a test runs the old call); `sent` claimed more than the mail server's 250 | local; **live delivery not verified** (no provider) |
| 2 | Finish verification | A server-side resend cooldown with a countdown; replaced codes explained; a path to fix a mistyped address | Parallel wrong guesses beat the 5-try limit ("4 tries left" twice); resend said "sent" during the cooldown while sending nothing | local |
| 8 | Account recovery | An email change waits for the new address's code; the old address is warned and told; a password reset or change cancels a pending change; reset links are claimed atomically | The change switched the address at once; a notice to an unverified old address leaked the new one; a password change left a pending change alive, and its link works signed out (a test without the fix shows it surviving) | local, SQLite + PostgreSQL |
| 3 | Durable production storage | `deploy/docker-compose.production.yml` (owner and app roles, a named volume, a one-shot migrate job, API readiness), the role init script, `grant-app-role`, `check-rls --strict`, an optional `copy-database`; production refuses SQLite; tests refuse a non-test database | A single env file would have put the owner and superuser passwords into the API container (split into two files; the rehearsal checks the container) | local + **Docker rehearsal**; not a deployment |
| 5 | RLS in the running app | Request and worker scopes: a signed-out request and the worker see **no** learner rows; one named read-only maintenance step; the judge binds the user it works for | Before this, "no user" meant every row, for any request that forgot to authenticate, and for the worker | local PostgreSQL: one-connection pool, errors, timeouts, cancellation, concurrency, two sensitivity tests; the full PG suite (2,764 tests) passed with it |
| 4 | Persistence audit | A per-feature table; row-locked revision checks; the story edit from the target page checked; note creates repeat-safe; sign-out clears every draft | Two simultaneous note saves both "succeeded" and one vanished (a test reproduces it without the lock); the target page skipped the story's revision check; an autosave retry made a second note; five kinds of drafts outlived sign-out on shared devices | local; e2e with two browser contexts and a third account |
| 7 | Backup and recovery | `backup-database` (age-encrypted, snapshot-consistent, with a manifest); `restore-database` into a separate empty database only, refusing first; a rehearsal with timing | A plain `pg_dump` as the owner is refused under FORCEd RLS (the tool handles it) | local, disposable databases: 57,703 rows restored in 1.40 s; **no schedule or off-site copy exists** |
| 9 | Privacy and retention | A data-flow and retention map; expired tokens purged; late judge results discarded; a Settings panel worded from the same facts | Expired sign-in tokens, reset links and codes were kept forever; a judge result after an account's deletion crashed on the foreign key | local |
| 6 | Bounces and delivery problems | `email-status` (redacted, Message-ID correlation), `email-retry --failed`, an outage test, SPF/DKIM/DMARC guidance | A first retry design re-triggered the duplicate check and would have crashed on reset jobs (caught by its own test, fixed before commit) | local; **webhooks and bounce events blocked until a provider is chosen** |
| 10 | Launch preflight | `preflight` (ready / blocked / optional / unverified), `scripts/rehearse_launch.py`, docs/LAUNCH.md | During a database outage, writes got a bare 500 (now a retryable `503 database_unavailable`) | local Docker rehearsal: 10/10 |

## Migrations (in order; all additive, all reversible)

- `b165a5a80342`: email jobs get `message_id`; `sent` becomes `accepted`.
- `dd8a6dc39c8f`: `users.pending_email`, `pending_email_at`.
- `7c1d2e3f4a5b`: RLS policies with scopes, and the read-only maintenance policy (PostgreSQL only).
- `4e5f6a7b8c9d`: `notes.client_request_id`, unique per user.

`alembic upgrade head`, `alembic check` (models match) and `downgrade base` pass on a disposable
PostgreSQL database. The API is additive: `api_compat.py --strict` against the last pushed
contract reports 0 breaking changes.

## Final checks on `1a0ec4a`

See the section appended below once the runs finish.

## What's needed from you

1. **A push**, so CI runs these commits (I haven't pushed).
2. **A mail provider.** Then a test send to an inbox you own; DNS records from the provider; its
   webhooks for bounces.
3. **A host** (and a managed PostgreSQL, or the compose file on a VM), plus a backup schedule
   with off-site storage.

docs/LAUNCH.md has the runbook; STORAGE, ROW_LEVEL_SECURITY, PERSISTENCE, BACKUP, PRIVACY and
EMAIL have the details.

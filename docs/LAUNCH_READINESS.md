# Launch readiness (Volume 5): handoff

Ten prompts, from "verification emails never arrive" to a launch preflight. Each section says:
- what changed;
- which **real defects** were found, and how each was shown before being fixed;
- how far it's verified. The levels are:
  - **local** (this sandbox: SQLite, PostgreSQL 16 with an ordinary role, Docker);
  - **CI** (needs a push: none has run on these commits);
  - **deployment** (none exists).

Nothing here was deployed, purchased, emailed for real or published. The DNS is unchanged, and
authentication is still the app's own; no move to Clerk or Firebase.

Pushed, with your go-ahead: everything up to `cab6094`. CI passed all 7 jobs on it (run 229, the
push). The commits after it are local, awaiting your go-ahead (see "After the batch").

## Per prompt

| # | Prompt | What changed | Real defects found (and shown first) | Verified |
|---|---|---|---|---|
| 1 | Make verification emails arrive | SMTP with **verified** TLS (starttls/ssl), typed outcomes (accepted / rejected / failed), a Message-ID per job, `check-email [--connect] [--send-test]`, a start-up notice when nothing is sent | STARTTLS used Python's unverified default and accepted a self-signed certificate (a test runs the old call); `sent` claimed more than the mail server's 250 | local; **live delivery not verified** (no provider) |
| 2 | Finish verification | A server-side resend cooldown with a countdown; replaced codes explained; a path to fix a mistyped address | Parallel wrong guesses beat the 5-try limit ("4 tries left" twice); resend said "sent" during the cooldown while sending nothing | local |
| 8 | Account recovery | An email change waits for the new address's code; the old address is warned and told; a password reset or change cancels a pending change; reset links are claimed atomically | The change switched the address at once; a notice to an unverified old address leaked the new one; a password change left a pending change alive, and its link works signed out (a test without the fix shows it surviving) | local, SQLite + PostgreSQL |
| 3 | Durable production storage | `deploy/docker-compose.production.yml` (owner and app roles, a named volume, a one-shot migrate job, API readiness), the role init script, `grant-app-role`, `check-rls --strict`, an optional `copy-database`; production refuses SQLite; tests refuse a non-test database | A single env file would have put the owner and superuser passwords into the API container (split into two files; the rehearsal checks the container) | local + **Docker rehearsal**; not a deployment |
| 5 | RLS in the running app | Request and worker scopes: a signed-out request and the worker see **no** learner rows; one named read-only maintenance step; the judge binds the user it works for | Before this, "no user" meant every row, for any request that forgot to authenticate, and for the worker | local PostgreSQL: one-connection pool, errors, timeouts, cancellation, concurrency, two sensitivity tests; the full PG suite (2,764 tests) passed with it |
| 4 | Persistence audit | A per-feature table; row-locked revision checks; the story edit from the target page checked; note creates repeat-safe; sign-out clears every draft | Two simultaneous note saves both "succeeded" and one vanished (a test reproduces it without the lock); the target page skipped the story's revision check; an autosave retry made a second note; five kinds of drafts outlived sign-out on shared devices | local; e2e with two browser contexts and a third account |
| 7 | Backup and recovery | `backup-database` (age-encrypted, snapshot-consistent, with a manifest); `restore-database` into a separate empty database only, refusing first; a rehearsal with timing; later a scheduled backup job (below) | A plain `pg_dump` as the owner is refused under FORCEd RLS (the tool handles it) | local, disposable databases: 57,703 rows restored in 1.40 s; **nothing schedules it on a real host, no off-site copy** |
| 9 | Privacy and retention | A data-flow and retention map; expired tokens purged; late judge results discarded; a Settings panel worded from the same facts | Expired sign-in tokens, reset links and codes were kept forever; a judge result after an account's deletion crashed on the foreign key | local |
| 6 | Bounces and delivery problems | `email-status` (redacted, Message-ID correlation), `email-retry --failed`, an outage test, SPF/DKIM/DMARC guidance | A first retry design re-triggered the duplicate check and would have crashed on reset jobs (caught by its own test, fixed before commit) | local; **webhooks and bounce events blocked until a provider is chosen** |
| 10 | Launch preflight | `preflight` (ready / blocked / optional / unverified), `scripts/rehearse_launch.py`, docs/LAUNCH.md | During a database outage, writes got a bare 500 (now a retryable `503 database_unavailable`) | local Docker rehearsal: 10/10 |

## After the batch: gaps closed while checking that everything runs

Each of these was found by running something, not by reading.

| Commit | What | How it was found |
|---|---|---|
| `55eee32` | The web image's Content-Security-Policy allowed only `http://localhost:8000`, so a browser on the real site would have blocked every API call. It now allows exactly the API origin the image was built for. | starting the production web image in the compose rehearsal |
| `09f4f5e` | The launch rehearsal serves the API over HTTPS, so the Secure session cookie behaves as in production: still signed in after a restart, signed out by a reset, kept through a database outage. The compose rehearsal also checks the web service. | — |
| `d7f7a52` | Scheduled backups: a compose `backup` job (as the owner, encrypted to public keys), retention (`prune-backups`) and a health check (`check-backups`) for the scheduler's alert. Rehearsed: two runs, then a restore of the newest into a separate database. | The rehearsal's own check: the first retention would have deleted a backup made by hand before an upgrade, at the next run that day. Now the last 24 h are kept and `--name` backups are never pruned. |
| `4ded096` | Behind the production proxy each visitor gets their own rate limit. Before, the API saw everyone as Docker's gateway, so the whole site shared one sign-in limit of 10 a minute. | a request through Docker's published port logged as `172.17.0.1` |
| (next) | The backup image's client tools are pinned to the server's PostgreSQL 16. `backup-database` and `restore-database` refuse mismatched versions before writing anything. Before, every backup it made could only have been restored into PostgreSQL 17 or newer. | **CI** (run 231): the compose rehearsal's restore failed on `SET transaction_timeout`. Reproduced here with PostgreSQL 17's tools. |
| `6d9911b` | The "Add to a collection" picker no longer shows a dropdown with one choice when there are no collections. The controls audit's signed-out pass now clears cookies, and a missing control fails in 15 s instead of 30 min. | The controls audit flagged the picker. Its first run then stalled: its "signed-out" pages were still signed in through a leftover cookie. |

## Migrations (in order; all additive, all reversible)

- `b165a5a80342`: email jobs get `message_id`; `sent` becomes `accepted`.
- `dd8a6dc39c8f`: `users.pending_email`, `pending_email_at`.
- `7c1d2e3f4a5b`: RLS policies with scopes, and the read-only maintenance policy (PostgreSQL only).
- `4e5f6a7b8c9d`: `notes.client_request_id`, unique per user.

`alembic upgrade head`, `alembic check` (models match) and `downgrade base` pass on a disposable
PostgreSQL database. The API is additive: `api_compat.py --strict` against the last pushed
contract reports 0 breaking changes.

## Final checks

Local runs, on this sandbox (4 vCPU, Python 3.13, Node 22, PostgreSQL 16, Docker 29.9 with
gVisor):

| Check | Result |
|---|---|
| Backend, SQLite, full suite (`cab6094`) | **2,403 passed**, 35 skipped (PostgreSQL- or sandbox-only), 2 expected failures (known rubric residuals) |
| Backend, PostgreSQL with RLS enforced, full suite plus rehearsals | **2,436 passed**, 1 skipped, 2 expected failures. Run on the code just before `cab6094`; the six files `cab6094` touches were rerun on it on PostgreSQL: 82 passed |
| Backend sandbox tests (`-m sandbox`): the real gVisor runner and judge | **384 passed** (every reference solution, limits, compile errors, memory bombs, forgery attempts, `judge-check`) |
| Backend lint (ruff), format, types (mypy app evals) | clean |
| Migrations: `upgrade head`, `alembic check`, `downgrade base` on a disposable database | clean; models match |
| API compatibility against the last pushed contract | 0 breaking |
| Frontend lint, typecheck, unit tests | clean; **709 / 709**. One earlier run under heavy machine load had a timing failure in `coachFallback.test.tsx`; it passed 3/3 alone and in the next full run |
| Frontend build and bundle budgets | pass (shell 207.5 KB / 300 KB; largest lazy chunk 674.5 KB / 700 KB) |
| Browser end-to-end suite (Playwright, Chromium) | **98 passed**, 3 opt-in skipped; then the opt-ins: judge with the real sandbox **2 passed**, controls audit below |
| Secret scan (detect-secrets against the baseline) | no new findings (one test URL reworded) |
| Launch rehearsal (`scripts/rehearse_launch.py`), the API over HTTPS | **10 / 10** |
| Production compose rehearsal with all four services | pass; it found the CSP bug fixed in `55eee32` |
| Backup rehearsal (5,000 synthetic accounts) | backup 0.59 s, restore 1.40 s, verified |

CI on `cab6094` (run 229, push): all 7 jobs passed:
- backend: lint, types, SQLite, PostgreSQL with RLS enforced, migrations, reference solutions,
  content gates;
- frontend;
- Docker images;
- runner;
- dependency audit and secret scan;
- end-to-end;
- the gVisor sandbox with the real judge.

The pull-request run of the same commit (230) failed once, in
`test_overload.py::test_a_request_that_cannot_get_a_database_connection_is_shed_with_503`
(5.89 s against a 5 s bound, a runner stall; 0.8 s locally, and it passed in run 229). It was
re-run without changing the test. The commits after `cab6094` have had no CI run yet. This file
states only what was confirmed.

## What's needed from you

1. **A push of the commits after `cab6094`**, so CI runs them (CI now also runs the compose
   rehearsal with the real backup image).
2. **A mail provider.** Then a test send to an inbox you own; DNS records from the provider; its
   webhooks for bounces.
3. **A host** (and a managed PostgreSQL, or the compose file on a VM). Then the nightly backup
   job in its scheduler (the cron line is in BACKUP.md), and **off-site storage** for the copies.

docs/LAUNCH.md has the runbook; STORAGE, ROW_LEVEL_SECURITY, PERSISTENCE, BACKUP, PRIVACY and
EMAIL have the details.

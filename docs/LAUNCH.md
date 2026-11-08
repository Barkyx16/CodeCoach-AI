# Launch preflight and runbook

One command checks the environment it runs in, and a rehearsal runs the intended production
configuration end to end on one machine. Neither deploys, buys, emails or publishes anything.
Passing unit tests is not a launch check: CI's results say the code works, and this page is about
whether a given environment is ready.

## The preflight

```bash
python -m app.cli preflight                       # in the environment to check (e.g. inside the api container)
python -m app.cli preflight --connect-email       # also connect to the mail server: TLS + sign-in, sends nothing
python -m app.cli preflight --backup-manifest /var/backups/codecoach/<newest>.manifest.json
python -m app.cli preflight --json                # the same, machine-readable
```

Every check ends in one of:
- **ready**: checked here, and it holds.
- **blocked**: checked here, and launch waits. The command exits 1.
- **optional**: an extra that's off by choice.
- **unverified**: can't be proven from here. The reason names the evidence that would prove it.

It reads settings by name and presence, never by value (`tests/test_preflight.py` checks no
secret's value appears).

| Area | Ready when | Otherwise |
|---|---|---|
| configuration | `ENVIRONMENT=production`, and every production guard passed while the settings loaded (secret strength, https, SMTP with TLS, no SQLite, no `AUTO_MIGRATE`, metrics token…) | blocked |
| secrets | every secret the configuration needs is present (`SECRET_KEY`, SMTP, `METRICS_TOKEN`, and the AI key or runner token if those features are on) | blocked, naming the missing ones |
| links | `APP_BASE_URL` is https | blocked |
| mail transport | with `--connect-email`: connected, encrypted with a verified certificate, signed in | unverified without the flag; blocked on failure (error class only) |
| mail delivery | never "ready" from here: a server accepting mail isn't an inbox | unverified: send one test, check inbox and spam, and the provider's SPF/DKIM/DMARC status |
| database | PostgreSQL answers | blocked: SQLite or unreachable |
| migrations | schema at this code's head | blocked: behind, newer or unmanaged |
| row-level security | enforced on all 30 tables for this role | blocked |
| database role | owns nothing, can't create objects or roles (least privilege) | blocked |
| backups | never "ready": a backup isn't a recovery | unverified with a manifest under 26 h old; blocked when older or unreadable |
| background jobs | the API runs the outbox and housekeeping itself, judge or not | unverified when `BACKGROUND_JOBS_IN_API=false` |
| outbox | nothing overdue by 15 min, no failures in 24 h | blocked, with the command to run |
| AI coach | — | optional with the built-in coach; unverified with Claude (no paid call is made) |
| code execution | — | optional when off; unverified when on (`judge-check` proves it) |

## The rehearsal (isolated, production-shaped)

`backend/scripts/rehearse_launch.py` sets up the environment below. Everything in it is
disposable and removed at the end:
- PostgreSQL 16 in a docker container, with the roles made by `deploy/postgres-init/10-roles.sh`;
- migrate, seed and grant run as the owner;
- the API as its own process with `ENVIRONMENT=production`, connected as the app role, served
  over HTTPS (uvicorn's TLS with the throwaway certificate), so the Secure session cookie behaves
  as behind a real https proxy;
- a real SMTP conversation over STARTTLS with a verified (throwaway) certificate. No message
  leaves the machine.

It then runs the preflight and the journey below.

**Run of 2026-11-08** on this sandbox:
- Linux 6.18, 4 vCPU, Python 3.13.18, PostgreSQL 16 (postgres:16-alpine), Docker 29.9.2,
  age 1.1.1;
- code at `56d5a36` plus the uncommitted preflight work, committed next as the "Launch
  preflight" commit;
- output (abridged):

```
READY      configuration      ENVIRONMENT=production, and every production start-up guard passed
READY      secrets            present (names only): SECRET_KEY, SMTP_PASSWORD, SMTP_USERNAME, METRICS_TOKEN
READY      links              APP_BASE_URL is https
READY      mail transport     the mail server answered: connected, encrypted, certificate verified, signed in (nothing sent)
UNVERIFIED mail delivery      a server accepting mail isn't delivery: …
READY      database           PostgreSQL answers
READY      migrations         the schema is at this code's migration head
READY      row-level security enforced on 30 tables
READY      database role      codecoach_app owns nothing and can't create objects (least privilege)
UNVERIFIED backups            a backup from 0 h ago exists; recovery is proven only by a restore rehearsal
READY      background jobs    the API runs the outbox and housekeeping itself; no judge needed
READY      outbox             nothing overdue, no failures in the last 24 h
OPTIONAL   AI coach           the built-in coach; Claude isn't enabled
OPTIONAL   code execution     off: code is saved, not run
PASS  preflight has nothing blocked
PASS  sign up and verify with the emailed code
PASS  save work
PASS  a second account can't see or change it
PASS  restart (SIGKILL): still signed in (token and refresh cookie), work intact
PASS  recover with an emailed reset link  (a reset signs out every session, by design)
PASS  mail outage: signed up meanwhile; the code arrives once when mail is back
PASS  database outage: 503 while down, then back with nothing lost and nobody signed out  (ready=503, write=503, refresh=503 while down; refresh=200 after)
PASS  worker interruption: the claimed job is delivered once after its lease
PASS  delete the account: gone, can't sign in, the second account unaffected
10 passed, 0 failed. Container, keys, mail and processes removed.
```

The first run found a real defect: during the database outage, a write got a bare 500
("unexpected error"). Database unavailability is now a retryable `503 database_unavailable`
with `Retry-After: 5`, never with the database's own message: a lost or refused connection, a
cancelled or timed-out statement, a shutdown, a deadlock, or SQLite's "locked". A bug, such as
a missing table, is still a 500 that gets logged and investigated (`test_storage.py`,
`test_tracing.py`, `test_log_redaction.py`). The frontend already treats a 503 as "try again", not as a sign-out.

What this rehearsal does **not** show:
- **Real email.** The mail server is a local fake with a throwaway CA. Real delivery needs a
  provider account and a test send to an inbox you own.
- **Launch-day rate limits.** `AUTH_RATE_LIMIT_PER_MINUTE` is raised so one script can sign up
  several accounts.
- **A real host.** No CDN, load balancer, managed database or failover.

## Runbook

**Before launch:**
1. Choose a host and a mail provider. Register the sender domain with the provider and add the
   DNS records it gives you ([EMAIL.md](EMAIL.md)).
2. Fill `deploy/.env.production` and `deploy/.env.app` from the `*.example` files, on the server.
3. `docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build`
   ([STORAGE.md](STORAGE.md)).
4. In the api container: `python -m app.cli preflight --connect-email`. Fix every **blocked**.
5. Close each **unverified** with its evidence:
   - `check-email --send-test` to an inbox you own: arrives, not in spam;
   - the nightly backup job in the host's scheduler with an alert on failure, a first run, then
     a restore rehearsal ([BACKUP.md](BACKUP.md) "Scheduling");
   - one AI hint if Claude is on;
   - `judge-check` if execution is on.
6. Put an https proxy in front, sign up with a real account you own, and walk through sign-up,
   verification, a saved note, sign-out and sign-in.

**When something breaks:**

| Symptom | First command | Then |
|---|---|---|
| Codes or links don't arrive | `python -m app.cli email-status` | `check-email --connect`; after an outage, `email-retry --failed` ([EMAIL.md](EMAIL.md)) |
| `/health/ready` is 503 | `docker compose … ps`, `… logs db` | the database is back → readiness returns by itself; schema behind → run `migrate` |
| A migration failed | `docker compose … logs migrate` | nothing changed (one transaction): fix the cause, `up` again |
| Lost the disk, or a bad change to data | — | restore the newest backup into a new database and switch to it ([BACKUP.md](BACKUP.md)) |
| Worried about isolation | `python -m app.cli check-rls --strict` (as the API's role) | [ROW_LEVEL_SECURITY.md](ROW_LEVEL_SECURITY.md) |

## Remaining launch blockers (as of this batch)

1. **No host or managed database chosen**, so nothing is deployed. The production compose is
   prepared and rehearsed locally only.
2. **No mail provider**: no real email has been sent, SPF/DKIM/DMARC aren't set, and bounces are
   invisible until its webhooks are connected ([EMAIL.md](EMAIL.md)).
3. **No backup schedule on a host, and no off-site storage.** The backup job, its retention,
   its check and the cron line are ready and rehearsed. Scheduling them needs the host, and
   off-site copies need a storage provider ([BACKUP.md](BACKUP.md)).
4. **CI** has not run on these commits: they're local until you approve a push.

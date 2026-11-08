# Where data lives, and how it survives

The backend already saves accounts and learning work. Every account, sign-in session, answer,
draft saved to the account, plan, story, note, application and result is a row in a database.
That database is SQLite on a quick local run and PostgreSQL everywhere else. This page covers
where that database is in each setup, what survives what, how production is configured, and
what was actually tested. Which features keep work in the browser only is covered per feature in
[PERSISTENCE.md](PERSISTENCE.md).

## The data paths

| Setup | Database | Where the data is | Who connects | Schema made by |
|---|---|---|---|---|
| `./dev.sh` (your computer) | SQLite | `backend/codecoach.db` | the API, as the file's user | start-up: `create_all`, then missing columns added, then seed (`AUTO_MIGRATE`, on outside production) |
| `docker compose up` (root `docker-compose.yml`, for development) | PostgreSQL 16 | Docker volume `<project>_pgdata` | `codecoach`, the image's **superuser**, so row-level security does not apply | the `migrate` service: `alembic upgrade head` + seed |
| Tests (`pytest`) | SQLite, or PostgreSQL via `TEST_DATABASE_URL` | a temporary file per test, or that database, **emptied before every test** | the test role | `create_all` |
| Storage rehearsals (`tests/test_storage.py`, `scripts/rehearse_production_storage.sh`) | PostgreSQL | disposable `codecoach_rehearsal_*` databases, roles and volume, dropped afterwards | as in production | as in production |
| Production (prepared: `deploy/docker-compose.production.yml`) | PostgreSQL 16 | Docker volume `codecoach_pgdata` (or a managed PostgreSQL, same roles) | the API as `codecoach_app`, which owns nothing | the one-shot `migrate` job, as `codecoach_owner` |

Nothing in the app writes user data to the server's own disk. The only file output is the `file`
email backend, which saves emails for tests and e2e runs, and production refuses it. Logs go to
stdout.

### Keeping them apart
- The test suite refuses a `TEST_DATABASE_URL` whose database name lacks "test", because it empties
  that database (`tests/conftest.py`).
- Production refuses SQLite, the example passwords, `AUTO_MIGRATE=true` and non-SMTP email
  (`app/config.py`).
- Staging: run the production compose on a different host, or under a different project and
  volume name (`-p codecoach_staging` plus a `volumes.pgdata.name` override), with its own
  `.env.production` and `.env.app`. Its passwords and `SECRET_KEY` must differ from production's,
  so a staging token or link can never work in production. Never point staging at the production
  database.
- The rehearsals only touch names starting `codecoach_rehearsal`.

## What survives what

| Event | `./dev.sh` (SQLite) | compose (dev or production) |
|---|---|---|
| Stop and restart the API (Ctrl+C, crash, `kill -9`) | kept | kept |
| Restart or recreate containers, `docker compose down` then `up`, rebuild images, upgrade the app | n/a | kept: the data is in the named volume |
| Database container removed and recreated | n/a | kept: same volume |
| Database unreachable for a while | n/a | not lost; `/health/ready` answers 503 until it's back, then 200 |
| A failed migration | n/a | nothing changes: PostgreSQL rolls the whole upgrade back |
| Deleting `backend/codecoach.db` | **gone** | n/a |
| `docker compose down -v`, `docker volume rm …` | n/a | **gone**, and `down -v` can delete the on-host backups volume (`codecoach_backups`) too |
| Host disk lost | **gone** | **gone** unless backed up ([BACKUP.md](BACKUP.md)) |

Routine start-up never deletes anything. `dev.sh`, both compose files, the init script and the
image are checked for volume removal, dropped tables or databases, and deleted database files
(`test_routine_startup_never_deletes_data`).

**Ephemeral disks.** Many hosts give a container a fresh filesystem on every deploy or restart
(most "platform" hosts, and any container without a volume). A SQLite file there would be wiped.
That's why production refuses SQLite: the database must be PostgreSQL on a volume or a managed
service.

## Production: two roles, one job, one API

```
db (postgres:16, volume codecoach_pgdata, no published port)
 └─ first start on an empty volume: deploy/postgres-init/10-roles.sh
      creates codecoach_owner and codecoach_app (no superuser, no BYPASSRLS, no CREATEROLE/CREATEDB),
      makes the owner own the database's schema, gives the app role CONNECT + USAGE only
migrate (one-shot, as codecoach_owner)
 └─ alembic upgrade head → python -m app.cli seed → python -m app.cli grant-app-role codecoach_app
api (as codecoach_app; starts only after migrate exits 0; healthy = /health/ready is 200)
backup (profile "backup": not started by `up`; the host's scheduler runs it, as codecoach_owner)
 └─ backup-database → prune-backups --apply → check-backups, into the volume codecoach_backups
```

- **The owner** owns the tables. Only the migrate job connects as it.
- **The app role** can read and write rows, and nothing more. It can't alter or drop tables,
  create objects, change the migration ledger, or turn row-level security off. It isn't a
  superuser and has no BYPASSRLS, so the RLS policies apply to it. `grant-app-role` refuses to
  grant to a superuser or BYPASSRLS role, and refuses when it's connected as that role itself.
- **Credentials stay apart.** Compose reads the database passwords from `deploy/.env.production`
  (`--env-file`) and puts each into the URL of the one container that needs it. The API's
  settings come from `deploy/.env.app`. So the API container never holds the owner's or the
  superuser's password; the rehearsal checks its environment for both. Both files are
  gitignored; the `*.example` files name every setting without values.
- **Client addresses (the trust chain).** Rate limits are per visitor address, so the API must
  see the visitor, not the proxy:
  - **The chain:** browser → your https reverse proxy on the host → Docker's published port
    `127.0.0.1:8000` → the API container. Docker's port publishing makes every connection arrive
    from the network's gateway (172.x.0.1), never 127.0.0.1. So with uvicorn's default
    (`FORWARDED_ALLOW_IPS=127.0.0.1`), every visitor shared the gateway's address and its
    sign-in limit (10 a minute, for the whole site). Found while preparing this layout,
    before any deployment.
  - **The fix:** the api service sets `FORWARDED_ALLOW_IPS` to the private ranges, which cover
    the gateway on any Docker network. uvicorn reads `X-Forwarded-For` from the right and stops
    at the first address it doesn't trust: the one your proxy appended. So anything a client
    puts in front of it (forged, malformed) is ignored.
  - **Your proxy** must append the client's address (nginx: `proxy_set_header X-Forwarded-For
    $proxy_add_x_forwarded_for;`) or replace the header with it (Caddy's default). Then a
    client can't choose its own rate-limit address.
  - **Who else is trusted:** anything with a private address that can reach the API's port.
    That's only this compose project's own containers and processes on this host, because the
    port is published on 127.0.0.1. Loopback binding narrows that, but doesn't make every
    process on the host trustworthy.
  - **Known limit:** a visitor whose own address is private (the API serving a LAN) is skipped
    as if it were a proxy, so the entry to its left, which it could forge, is used instead.
    Narrow the setting to the gateway itself in `.env.production` (e.g.
    `FORWARDED_ALLOW_IPS=172.18.0.1`; `docker network inspect codecoach_default` shows it).
  - **Not covered:** a load balancer or CDN in front of your proxy adds a hop. Add its addresses
    too, or every visitor appears as the load balancer. Untested here.
  - **Links and cookies don't depend on any of this.** Emailed links come from `APP_BASE_URL`,
    and the session cookie's `Secure` flag from `COOKIE_SECURE`, never from a forwarded Host or
    scheme.
  - **Evidence:**
    - `tests/test_client_addresses.py` feeds the compose file's value to uvicorn's own
      middleware: gateways believed, forged and malformed prefixes ignored, IPv6, the private
      network limit;
    - the compose rehearsal's step 2c, through Docker: the forwarded address is seen; one
      visitor using up the sign-in limit gets 429 with `Retry-After` while another signs in
      normally; and 20 wrong passwords for one account from 20 addresses still pause that
      account for a 21st;
    - the same rehearsal with `FORWARDED_ALLOW_IPS=127.0.0.1` fails at that step: the API
      sees `172.18.0.1`.
    - The preflight's "client addresses" line says whether the setting is present, never its
      value.
- **Checks:**
  - `python -m app.cli check-rls --strict` fails unless the connected role is the least-privilege
    app role.
  - At start-up, the API logs a warning in production when its role owns tables (development
    connects as the owner, logged at INFO).

### Procedure

First start, and every upgrade:
1. Back up first if there's data, by name so pruning keeps it ([BACKUP.md](BACKUP.md)):
   `docker compose … --profile backup run --rm -T backup python -m app.cli backup-database --out /backups --recipients /run/codecoach/recipients.txt --name pre-upgrade-<date>`
2. `docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build`
3. `migrate` runs and exits. If it fails, the API keeps running the old containers or doesn't
   start: `docker compose … logs migrate`. A failed migration leaves the schema and the data as
   they were (PostgreSQL DDL is transactional), so fix the cause and run `up` again.
4. The new API starts once `migrate` succeeds. It is healthy once `/health/ready` returns 200.
5. Check:
   - `docker compose … exec api python -m app.cli check-rls --strict`
   - `docker compose … exec api python -m app.cli check-email --connect` ([EMAIL.md](EMAIL.md))

Readiness (`/health/ready`):

| Database | Schema vs this code | Answer |
|---|---|---|
| unreachable | — | 503 `database: fail` |
| answers | behind (migration not run, or failed) | 503 `schema: behind` |
| answers | current | 200 |
| answers | newer (the app was rolled back onto an expanded schema) | 200, `schema: newer` |

`/health` (liveness) stays 200 while the process runs, so an orchestrator restarts a dead
process, not one waiting for its database.

**With a managed PostgreSQL** (any provider), create the two roles with the same statements as
`deploy/postgres-init/10-roles.sh`. Run the same three migrate commands as the owner from your
deploy pipeline, and give the API only the app role's URL. Nothing was provisioned for this
work: choosing a host and buying a database are your decisions.

## Optional: moving development data to PostgreSQL

Only if you want accounts made on a local run to exist on the new server. A SQLite file can't be
loaded into PostgreSQL directly: types, sequences and the migration ledger differ. So the copy
reads each row through this version's models.

```bash
# 1. Bring the dev database up to this version: start ./dev.sh once (it adds missing columns), stop it.
# 2. A freshly migrated, EMPTY PostgreSQL database (not seeded yet), as its owner:
DATABASE_URL=postgresql+psycopg://codecoach_owner:…@host/codecoach alembic upgrade head
# 3. Dry run: lists what would be copied and what's skipped; writes nothing.
DATABASE_URL=… python -m app.cli copy-database --from sqlite:///backend/codecoach.db
# 4. Copy, then seed and grant:
DATABASE_URL=… python -m app.cli copy-database --from sqlite:///backend/codecoach.db --apply
DATABASE_URL=… python -m app.cli seed && DATABASE_URL=… python -m app.cli grant-app-role codecoach_app
```

The copy refuses, before writing anything, when:
- the source has a table or column this version doesn't know, or lacks one it needs;
- the target isn't at this version's migration head, or already has rows;
- source and target are the same database.

It runs in one transaction and keeps nothing unless every table's row count matches. It continues
the id sequences after the copied ids and never changes the source.

It deliberately leaves behind sign-in sessions, emailed codes and links, queued emails and rate
counters. People sign in again on the new server, and nothing old is emailed from it.
Passwords keep working: they are stored as hashes. Codes and links signed with the old
`SECRET_KEY` don't carry over, by design.

## Evidence

| What | How | Status |
|---|---|---|
| Saved work survives a killed (`SIGKILL`) and restarted API process | `test_saved_work_survives_a_killed_and_restarted_api`: real uvicorn processes | verified locally on SQLite and PostgreSQL |
| The app role owns nothing, can't alter, drop or create tables, change the migration ledger or grant itself BYPASSRLS, and its data survives restarts; `check-rls --strict` fails for the owner and passes for the app role | `test_the_api_runs_as_an_app_role_that_owns_nothing_and_its_data_survives_restarts` (the real init script, alembic, seed, grant-app-role, uvicorn) | verified locally on PostgreSQL 16; in CI once pushed (CI gains `TEST_DATABASE_ADMIN_URL`) |
| Production start-up warns when connected as the owner | `test_startup_warns_in_production_when_the_api_connects_as_the_owner` | verified locally |
| An older schema upgrades in place with data intact; a failed migration changes nothing; readiness goes 503 (behind) → 200 (current) | `test_an_older_schema_upgrades_in_place_and_a_failed_migration_changes_nothing` | verified locally on PostgreSQL 16 |
| Readiness is 503 with an unreachable database and 200 once it answers | `test_readiness_is_503_while_the_database_is_unreachable_and_200_once_it_answers` | verified locally |
| The copy moves accounts and work, refuses unsafe cases, and orders self-referencing rows | the `test_copy_*` tests, SQLite→SQLite and SQLite→PostgreSQL | verified locally |
| The production compose: migrate job as owner, API as app role, no owner or superuser password in the API, data surviving an API restart, the database container recreated, and `down`/`up`; readiness following the database; the scheduled backup job, and a restore of its newest backup into a separate database | `scripts/rehearse_production_storage.sh` on Docker in this sandbox, and in CI's Docker job once pushed | rehearsed locally (log below); **not a deployment** |

Rehearsal output (2026-11-08, Docker 29.9 in this sandbox):

```
== 1. start db, migrate (owner) and api (app role)
ok: API ready
ok: migrate job exited 0
== 2. what the API container holds
ok: API connects as codecoach_app; neither the owner's nor the superuser's password is in its environment
Row-level security is enforced.
Role codecoach_app owns nothing and can't create objects: a least-privilege app role.
== 2b. the web service
ok: the built app is served
ok: app routes fall back to the app (/dashboard)
ok: the CSP allows exactly the API origin the build calls (PUBLIC_API_URL)
ok: framing and sniffing blocked
== 2c. client addresses through Docker's published port
ok: the API sees the visitor's forwarded address, not Docker's gateway: rate limits are per visitor
ok: visitor A is limited (429, Retry-After) while visitor B still signs in normally: separate limits
ok: the per-account limit holds no matter how many addresses the attempts come from
== 3. save work, then restart and recreate
ok: after an API restart
ok: after the database container was removed and recreated
ok: after docker compose down and up (the volume is kept)
== 4. readiness follows the database
database stopped: /health/ready=503 /health=200
database back: /health/ready=200
== 5. the scheduled backup, then a restore into a separate database
ok: two runs of the backup job: each backed up as the owner, pruned (kept 2) and checked
ok: the API container has no backups volume
ok: the newest backup restored into a separate database; row counts and policies match
ok: the saved note is in the restored copy
ok: no password in the backup or restore output
```

One caveat about that run: the API and web images came from the repository's Dockerfiles plus
two lines each that trust this sandbox's network proxy, for `pip` and `npm` (`IMAGE=…`,
`WEB_IMAGE=…`). The backup image's `pg_dump` 16 and `age` were copied from this machine
(`BACKUP_IMAGE=…`), because Debian's package mirror isn't reachable from the sandbox. CI builds
the unmodified Dockerfiles and runs the same rehearsal.

The web step found a real production bug. The web image's Content-Security-Policy hard-coded
`connect-src 'self' http://localhost:8000`, so a browser on the real site would have blocked
every call to `PUBLIC_API_URL`. The image now writes the API origin of its build into the policy.
Only a plain http(s) origin is accepted: a malformed URL fails the build.

## Limits

- **Not deployed.** No host, managed database, DNS, TLS proxy or backup schedule exists yet:
  choosing and paying for them is yours. Until then, "verified" means on this machine and in CI.
- **A single database.** No replica and no failover: if the host's disk is lost, so is everything
  since the last backup.
- The development compose file still connects as the image's superuser, so row-level security
  doesn't apply there. That's acceptable for development only; use the production layout for
  anything with real users.
- The copy command loads each table into memory. That's fine for a development database, but it
  isn't meant for large data sets.

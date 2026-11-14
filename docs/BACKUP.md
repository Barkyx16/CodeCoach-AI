# Server backups and recovery

This page is about recovering the **whole server**: every account, after a lost disk, a bad
migration or a deleted volume. It is not the per-account export in Settings ("Download your
data", [BACKUP_FORMAT.md](BACKUP_FORMAT.md)). That export gives one person their own records.
It can't rebuild the database: no other accounts, no sign-in data, no schema, sequences or
security policies.

> Status: the tools, the procedure and a scheduled backup job (the compose service `backup`)
> exist, and were rehearsed on disposable databases on this machine. **Nothing is scheduled on a
> real host, no backup is copied off-site, and no production restore has happened.** Those need
> a host and a storage provider. A backup that was made, or even uploaded, isn't a recovery
> until a restore from it has been rehearsed.

## What a backup contains

| Part | In the backup? | How it comes back |
|---|---|---|
| Every table's rows (accounts, password hashes, all learning work, queued emails, sign-in sessions) | yes: `pg_dump --format=custom`, snapshot-consistent | `pg_restore` in one transaction |
| Schema, indexes, constraints, the migration revision (`alembic_version`) | yes | restored; readiness then compares it with the code |
| Sequences (integer ids) | yes, with their current values | restored |
| Row-level security: `ENABLE`/`FORCE`, both policies on every learner table in `db/rls.py` (`PROTECTED_TABLES`) | yes | restored; the restore counts the policies against the manifest |
| Table ownership and grants to the app role | yes | restored, **if the roles exist first** (the restore refuses otherwise) |
| The roles themselves, and their passwords | **no**: roles are server-wide, not part of one database | `deploy/postgres-init/10-roles.sh`, or `CREATE ROLE … NOSUPERUSER NOBYPASSRLS` with new passwords |
| `CONNECT` on the database for the app role | **no** (a database-level grant) | the restore re-grants it to every role the manifest lists |
| `SECRET_KEY`, SMTP password, the database passwords (`deploy/.env.app`, `deploy/.env.production`) | **no**: they are secrets | keep them in a password manager or the host's secret store. Losing `SECRET_KEY` doesn't lose data, but everyone signs in again and old emailed links stop working |
| Files on the server's disk | nothing to back up: the app stores no user files there ([STORAGE.md](STORAGE.md)) | — |

Each backup is two files with one name:
- `codecoach-<UTC time>.dump.age`: the dump, encrypted.
- `codecoach-<UTC time>.manifest.json`: plain JSON with no user data. It records:
  - the time and migration revision;
  - the PostgreSQL and `pg_dump` versions;
  - row counts per table and the number of policies;
  - which roles own or were granted the tables;
  - SHA-256 hashes of the encrypted file and of the plaintext dump.

## Encryption and keys

Backups are encrypted with [age](https://age-encryption.org) to one or more **public** keys
(the "recipients" file). The machine that makes backups only ever holds public keys, so whoever
copies its backup folder can't read the backups. Decrypting needs the matching **private** key
(the "identity" file). age encryption is authenticated: a backup altered after it was made fails
to decrypt instead of restoring something wrong.

```bash
age-keygen -o codecoach-backup-identity.txt   # on a machine you trust, NOT the server
grep 'public key' codecoach-backup-identity.txt | cut -d' ' -f4 > recipients.txt   # this goes on the server
```

- Keep the identity file away from the server and away from the backups: in a password manager
  and on an offline copy, with at least two people able to reach it. **Lose it, and every backup
  made for it is unreadable.**
- Several recipients (one per line) let more than one holder restore.
- To rotate: make a new key pair, put the new public key in `recipients.txt`, and keep the old
  identity until the last backup made with it has expired.

## Making a backup

Run it as the table owner (or a superuser) so it sees every row. The tables FORCE row-level
security, so a plain `pg_dump` as their owner is refused: the tool passes
`--enable-row-security`, and with no RLS scope the owner sees everything
([ROW_LEVEL_SECURITY.md](ROW_LEVEL_SECURITY.md)). Needs `age`, and a `pg_dump` of **exactly the
server's major version**. The command refuses any other `pg_dump`, before writing anything. A
newer `pg_dump` can read the server, but its archive can't be read by the server's own
`pg_restore`, and a newer `pg_restore` can't restore into the older server. So that backup could
only ever be restored into a newer PostgreSQL. The `backup` image pins its client tools to the
server's major (`PG_MAJOR` in `backend/Dockerfile`, checked against the compose file by a test
and by CI).

```bash
DATABASE_URL=postgresql+psycopg://codecoach_owner:…@host:5432/codecoach \
  python -m app.cli backup-database --out /var/backups/codecoach --recipients /etc/codecoach/recipients.txt
```

- The plaintext never touches the disk: the dump is hashed and encrypted as it streams.
- A backup never overwrites another.
- A failed dump keeps nothing, whatever fails: `pg_dump`, `age` (e.g. no usable key) or the pipe
  between them. The compose rehearsal found that an `age` failure used to leave a partial dump
  behind, and the next restore picked it as the newest backup. Fixed, with a regression test.
- Before an upgrade or a risky change, make one by name: `--name pre-upgrade-20261108`. Pruning
  never touches a named backup; delete it yourself when it's no longer needed.

## Scheduling, retention and alerts

The production compose file has a `backup` service. It isn't started by `up`; the host's
scheduler runs it. Each run, as the table owner:
1. makes a backup into the volume `codecoach_backups`, encrypted to the public keys in
   `deploy/backup-recipients.txt` (the private key never comes to the server);
2. prunes: `prune-backups --apply`;
3. checks the newest: `check-backups`.

Any step failing exits non-zero, and so does the run. The API container can't see the backups
volume and never holds the owner's password.

```bash
# Once: the public key(s) on the server (from "Encryption and keys" above).
cp recipients.txt deploy/backup-recipients.txt
# Nightly, from the host's crontab (03:17 UTC; any quiet hour works):
17 3 * * * cd /srv/codecoach && docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml --profile backup run --rm -T backup >> /var/log/codecoach-backup.log 2>&1 || <your alert command>
```

`<your alert command>` is whatever the host offers: a mail command, a monitoring push, a chat
webhook. None is configured: that depends on the host. A systemd timer works the same way, with
`OnFailure=` for the alert.

**Retention contract** (`prune-backups`; a dry run unless `--apply`):

| Question | Answer |
|---|---|
| What's managed | Only `codecoach-<UTC time>.dump.age` + `.manifest.json` pairs that `backup-database` named. |
| What's never deleted | A named backup (`--name …`: the way to pin one), any other file, a symlink (even one named like a backup; its target is never touched), a temporary file, and the restore log. |
| What counts as usable | Both files are regular files. The manifest is readable, of this format, and names this dump. The dump is exactly the size the manifest records (every backup since that check exists). The stamp isn't more than 10 minutes in the future. |
| What isn't usable | It's **held**: never deleted, never the reference point, and listed by `prune-backups` and `check-backups`. A half-written, truncated, garbled or future-dated artifact can't move the cutoff and erase good backups. |
| Time source | The UTC stamp in the name: the backing-up machine's clock when the backup started. Periods are UTC days, ISO weeks and months. |
| What's kept | The newest usable backup; every one made at most 24 h before it (inclusive: exactly 24 h is kept; `--keep-within-hours`); the newest of each of the last 7 days, 4 weeks and 3 months that have a backup. |
| Minimum | `--keep-daily` can't be below 1, so a typo can't shrink retention to a single backup. |
| Before deleting | The newest backup's hash is checked. If it doesn't match its manifest, nothing at all is deleted. |
| Failures | A folder that can't be listed is an error, never an empty store. A file that can't be deleted is named, and the command exits 1. A dump goes before its manifest, so an interrupted prune never leaves something that looks complete. |
| Concurrency | `backup-database` writes the dump first and the manifest last, under a temporary name and then renamed. A backup being written is half a pair, so it's held. A prune only deletes what it saw complete when it started. |

It counts backups, not the calendar: if backups stop, nothing more expires while they're stopped.
Named backups grow the folder until deleted by hand. `check-backups` prints how much space the
managed and the other files take. Every rule above has a test (`tests/test_backup_store.py`):
- either side of the 24 h cutoff and exactly on it;
- a future date;
- partial and garbled files;
- a damaged newest backup;
- a backup completing during a prune;
- a failed deletion;
- an unreadable folder;
- symlinks.

**Checks** (`check-backups --dir DIR [--max-age-hours 26] [--all]`, exit 1 on a problem). It
reports three things separately:
- **recency**: the newest *usable* backup is under 26 hours old. A newer artifact that isn't
  usable (last night's, truncated) and a future-dated one are problems: before this, one
  backup stamped by a wrong clock made the check pass forever;
- **integrity**: that backup's SHA-256 matches its manifest. A truncated or damaged copy fails;
- **the last restore rehearsal** recorded in the folder (`codecoach-restores.json`, written by
  `restore-database`). It warns when that's older than a month, but doesn't fail the night.

`--all` checks every backup's hash. Run it against an off-site copy after downloading it. It
decrypts nothing, so passing isn't recovery: rehearse a restore monthly (below).

**Off-site copies: not set up.** A backup on the server's disk survives a bad change or a dropped
table, not a lost disk. Copy each new backup elsewhere (object storage in another account or
region) with that provider's tool, e.g. `rclone copy` from the `codecoach_backups` volume after
the nightly run. Give it its own lifecycle rule matching the retention above. The files are
already encrypted, so the storage provider can't read them. This needs a provider account:
your decision, not made here.

## Restoring

Always into a **new, empty** database, never over the live one. The tool refuses both. It also
refuses, before writing anything, when:
- the encrypted file doesn't match its manifest (damaged or truncated);
- the identity file is missing, or decryption fails (wrong key or tampering);
- the backup's schema is newer than this code;
- a role the backup needs doesn't exist on the server.

```bash
# 1. The roles exist (a new server: the init script; the same server: they already do).
# 2. An empty database owned by the owner role:
createdb -O codecoach_owner codecoach_restored            # as an admin
# 3. Restore (connected as the owner):
RESTORE_DATABASE_URL=postgresql+psycopg://codecoach_owner:…@host:5432/codecoach_restored \
DATABASE_URL=…the live database, so the tool can refuse it… \
  python -m app.cli restore-database codecoach-20261108T031700Z.dump.age --identity codecoach-backup-identity.txt
# (add --recovery when this copy will serve users; without it, a rehearsal)
```

With the production compose layout, the backup service can do it. Bring the identity file to
the server only for the restore, and remove it afterwards:

```bash
DC="docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml"
$DC exec db createdb -U postgres -O codecoach_owner codecoach_restored
export RESTORE_DATABASE_URL=postgresql+psycopg://codecoach_owner:…@db:5432/codecoach_restored
$DC --profile backup run --rm -T -e RESTORE_DATABASE_URL -v "$PWD/identity.txt:/run/identity.txt:ro" backup \
  python -m app.cli restore-database /backups/codecoach-20261108T031700Z.dump.age --identity /run/identity.txt
```

The restore:
- decrypts to a private temporary folder (deleted afterwards) and checks the plaintext hash;
- runs `pg_restore --single-transaction`, so a failure leaves the database empty;
- re-grants `CONNECT`;
- checks every table's row count and the policy count against the manifest;
- confirms row-level security is in place on every protected table;
- reports the schema state. If the backup is older than the code, run `alembic upgrade head` on
  the copy next.

The restore records itself in the backup folder (`codecoach-restores.json`: the time, the
backup's name, table and row counts; no user data). So `check-backups` can say when recovery was
last rehearsed.

**The restored copy's outbox: held, never replayed.** The backup holds the outbox as it was:
emails not yet sent then (waiting, retrying, or mid-send) come back with it. The old server may
have sent them since, or they may no longer be wanted. So the restore **holds** every unfinished
email on the copy, in the same step that checks the schema, before any app or worker can start
there. No worker claims a held email, however many start or restart. Each stays held until you
decide. The restore says how many it held, and records the number and the restore's purpose in
`codecoach-restores.json`. In the compose rehearsal: two verification emails.

**Rehearsal or recovery.** By default a restore is a **rehearsal**: a copy to inspect, whose
addresses are still real people's. A rehearsal's held emails can be suppressed, but releasing
them while the app sends over SMTP is refused, dry run included. To rehearse a release, point the
copy's app at a capture transport (`EMAIL_BACKEND=file`). For a real recovery, a copy that will
serve users, add `--recovery` to `restore-database`. Its held emails can then be released.

While any email is held, `preflight` reports **blocked** (outbox: "N emails held after a restore").
**To confirm mail is still paused**: `email-quarantine` lists the held emails, and each one's
attempts stay as they were. `email-status` shows the counts by status: `held`, and no `pending` or
`sending` from before the restore.

To decide, as the app role against the copy (inside the API container, for example). Shell
access to the server and the app's database credentials are the authorization, as for every
operator command; there is no web route:

```bash
python -m app.cli email-quarantine                      # what's held: job, kind, age, *@domain, what it was doing, what release would do
python -m app.cli email-quarantine --release --kind verify_email          # dry run: which would go
python -m app.cli email-quarantine --release --job <id> --job <id> --apply # send these (a recovery)
python -m app.cli email-quarantine --suppress --kind email_changed --apply # never send these
```

- **The listing shows the domain, never the address.** It shows the job id, kind, age and
  attempts. It shows which restore held the email, and what the email was doing at backup time:
  - `pending`: never tried;
  - `retrying`: tried, failed, due again;
  - `sending`: leased mid-send.

  It also says what releasing would do, by the outbox's own rules.
- **Nothing changes without `--apply`.** `--kind` or `--job` (repeatable) narrows the choice.
  Running a command twice is harmless: it acts only on emails that are still held.
- **Release** makes the email due now, and the next outbox pass sends it.
  - A verification or reset email gets a fresh code or link at send time: the outbox never
    stores a usable one, and a code from before the backup is never revived.
  - Some emails are not sent, and the listing says so first:
    - an email older than its kind's limit (verification 48 h, reset 30 min, notices 3 days) is
      dropped;
    - a verification email for an address verified since (or an account gone) is skipped.
  - A released email that fails is retried as normal; it isn't held again.
- **Suppress** finishes the email as `dropped`, clears its stored addresses, and keeps the decision
  on the job (`suppressed:<purpose>:<was>`) until finished jobs are purged (7 days). It's never sent.
- **Each decision is logged**: `codecoach.email_ops`, "released held emails" or "suppressed held
  emails". The log line has the job ids and the count, never an address.

**Mid-send at backup time is ambiguous.** A job leased mid-send (`was sending`) may have been
accepted by the mail server after the snapshot, so it may already have arrived. SMTP has no
idempotency, so nothing can promise exactly-once delivery across a historical restore. Releasing
it resends it with the same Message-ID (`<codecoach.JOB_ID@domain>`). A mail client or provider
can match the copy to the original by that ID, but nothing stops a second copy arriving. The
listing says so for that email. Suppress it unless it's a fresh-code verification email: a
second verification email is only a nuisance, and its new code supersedes the old one.

**An interrupted release.** The release is one statement, so all the chosen emails are released
or none is. If the process dies before you see its output, run the same command again: the
emails already released aren't held any more, so it does nothing for them. A worker that died
mid-send leaves its email leased. When the 5-minute lease runs out, the next pass sends it once.
`email-status --job <id>` shows where each one is.

Rule of thumb for a recovery: release verification emails for accounts that still need one (the
code is new anyway). Suppress change-of-address notices and anything the old server most likely
sent already. A user can always ask for a new verification or reset email from the app. For a
rehearsal, suppress everything.

Only a restore holds emails. Ordinary restarts, deploys and new workers send queued mail as usual.

**Other side effects after a restore.** This list is every process in this repository that
starts with the app and can act on something:

| Producer | Starts on its own | Acts on | On a restored copy |
|---|---|---|---|
| Email outbox (the API's jobs thread, `python -m app.worker`) | yes, every 5 s | people's inboxes, through SMTP | **held** until decided (above) |
| Judge worker (`python -m app.worker`, when `EXECUTION_ENABLED`) | yes | your own sandbox runner | submissions queued or running at backup time are judged on the copy. Results are written to the copy; nobody is contacted |
| Housekeeping (the jobs thread: every 10 min and daily) | yes | the copy's own rows | deletes expired rate-limit counters and tokens, and email jobs finished over 7 days ago. On its first daily pass, which runs as soon as the app starts, it also deletes guest accounts inactive for `GUEST_RETENTION_DAYS`, counted from now, not from the backup. A copy of an old backup can lose guests the live server still had |
| AI provider calls | no: only inside a learner's request | the provider's API (billed) | nothing on start |
| Share links, calendar files, exports | no: served on request | nothing outside | nothing on start |

Not covered: anything outside this repository. That includes a cron job on the host, a mail
provider's own retry queue, a reverse proxy's cache, and whatever a provider does with mail it
had already accepted. This is targeted protection against replaying the outbox. It doesn't claim
that a point-in-time recovery is free of side effects.

**4. Before switching anyone to it:**
- start the app against the copy, as the app role: `check-rls --strict` and `/health/ready`;
- decide on the held emails (`email-quarantine`, above) until `preflight` no longer blocks on them;
- sign in with a test account;
- spot-check another account's data stays out of reach.

Then switch `DATABASE_URL` (or rename databases) during a short maintenance window. Anything
written after the backup was taken is lost. That's the recovery point.

**Rehearse monthly**, on a separate database: restore the newest backup and run step 4.
`scripts/rehearse_backup.py` does the whole cycle on disposable data.

## Recovery objectives: targets, not achievements

| | Target (proposed) | Measured so far |
|---|---|---|
| Recovery point (data you can lose) | ≤ 24 h, with nightly backups | none yet: the job exists, nothing schedules it on a real host |
| Recovery time (until the app is back) | ≤ 2 h, including fetching the backup and checks | restore of 57,703 rows in 1.40 s (below); not measured at production size or over a network |

Rehearsal on this machine (2026-11-08, PostgreSQL 16, `scripts/rehearse_backup.py`, 5,000
synthetic accounts × 10 notes plus 2 real accounts, in disposable databases):

```
dataset: 57703 rows in 55 tables          encrypted backup: 0.8 MB
backup (dump + encrypt): 0.59 s
restore: checks 0.17 s, decrypt 0.01 s, restore 1.11 s, verify 0.08 s, total 1.40 s
app on the copy: ready, sign-ins, isolation, check-rls: 2.28 s
verification: readiness 200; both accounts see only their own notes; cross-read 404; check-rls --strict passes
```

These numbers are for a small, very compressible synthetic dataset on a local disk. Measure
again at real size before relying on the 2-hour target.

## Tests (`tests/test_backup.py`, disposable databases)

| Case | Result |
|---|---|
| Valid backup restores into a separate database; the app runs on it as the app role; two accounts each see only their own notes; cross-read and cross-update are 404; new rows get fresh ids | pass |
| The dump is encrypted (no address in its bytes); the manifest holds no user data | pass |
| A flipped byte, a truncated file, a missing manifest | refused as damaged or incomplete; target untouched |
| An altered file with a recomputed manifest hash | refused: decryption fails |
| A missing identity file; someone else's key | refused |
| A schema newer than the code | refused |
| A role the backup needs is missing | refused |
| The live database, or any non-empty target | refused |
| Overwriting a backup; a dump that fails | refused; nothing kept |
| The CLI prints neither password | pass |
| A `pg_dump` whose major version isn't the server's | refused; nothing written |
| A `pg_restore` older than the backup's `pg_dump`, or newer than the target server | refused; target untouched |
| An email unsent at backup time | held on the copy (an email already sent is untouched); the restored app's own outbox pass, as the app role, sends nothing | pass |

And the held emails (`tests/test_restore_quarantine.py`, against a real SMTP conversation; SQLite and PostgreSQL as the app role):

| Case | Result |
|---|---|
| Held emails of every unsent kind (never tried, retrying, leased mid-send, too old, verified since): two workers, then a restarted one | no message sent; all still held |
| The listing | what each was doing (pending, retrying, sending); held by a rehearsal (the default); what release would do: sent with a fresh code, dropped as too old, skipped as verified since, and "may already have arrived" for the one leased mid-send only; domain only, never an address |
| Release (recovery): a dry run, then three of five with `--apply`, then the same again | the dry run changes nothing; one is sent with a new code, the too-old one is dropped and the verified one skipped (nothing goes out for either); the repeat is a no-op; the other two stay held |
| Release of a rehearsal's emails over SMTP, dry run or `--apply` | refused; still held. Suppress allowed, kept on the job (`suppressed:rehearsal:pending`), logged with the job id and no address |
| Release of a rehearsal's emails into a capture transport (`EMAIL_BACKEND=file`) | allowed; captured, nothing leaves |
| A released email whose send fails | retried as normal (pending), not held again |
| An interrupted release: a worker claims a released email and dies mid-send | running the release again is a no-op; nothing is sent while the lease holds; after it, sent exactly once; the rest stay held |
| Verification after a restore: the backup's code had expired | the old code doesn't verify; the released email's new code does |
| Suppress | never sent; addresses cleared; a repeat is a no-op; a sent email isn't touched |
| No restore | nothing held; queued mail goes out |
| `preflight` while emails are held | blocked, naming the held emails |
| The CLI | a dry run by default; domain only; a rehearsal's release over SMTP exits 1 ("Not released"); a recovery's releases; `--release --suppress` together and `--kind` without a value refused |

And the backup folder (`tests/test_backup_store.py`, plain files, runs everywhere):

| Case | Result |
|---|---|
| 120 nightly backups → the newest, the last 7 nights, the newest of 4 weeks and of 3 months | pass |
| Backups that stopped 40 days ago: the last 7 nights before they stopped are all kept | pass |
| A second backup the same day survives; a named backup and stray files are never deleted | pass |
| Dry run deletes nothing; `--apply` deletes exactly the plan, dump before manifest | pass |
| Check: fresh and intact passes; 30 h old, truncated, unreadable manifest, empty folder fail | pass |
| `--all` finds an older damaged backup that the default check skips | pass |

All verified locally on PostgreSQL 16; in CI once pushed (`TEST_DATABASE_ADMIN_URL` is set
there).

The whole scheduled path runs in the production compose rehearsal
(`scripts/rehearse_production_storage.sh`, step 5):
1. two runs of the `backup` service, each backing up as the owner, pruning and checking;
2. a run that can't encrypt (no usable key) exits non-zero, so the scheduler's alert would fire;
3. the API container has no backups volume;
4. the newest backup restores into a separate database with a key the server never held;
5. `check-backups` then reports the rehearsal;
6. the **app itself starts on the restored copy as its app role**: `check-rls --strict` passes,
   account A signs in and sees its own note, and account B's note is a 404;
7. the signup emails that were unsent at backup time are **held** on the copy (none pending).
   After the restored API has run its 5-second email loop more than once, they are exactly as
   they were, with no attempt made. Then `email-quarantine`, in the API image as the app role:
   - it lists them by domain only, held by a rehearsal;
   - releasing them over SMTP is refused (exit 1);
   - a dry run changes nothing;
   - `--suppress --apply` finishes them;
8. a damaged copy of the backup is refused, and its target database stays empty;
9. no password and no private key appears in any output.

Compatibility matrix (each line is from the tools' own output):

| Where | Server | `pg_dump` / `pg_restore` | `age` | Result |
|---|---|---|---|---|
| This sandbox, 2026-11-08 (tools copied from the host into a sandbox-only image) | 16.15 | 16.15 (Ubuntu) | 1.1.1 | every step passes |
| CI run 231 on `6d9911b` (the real stage, Debian's client) | 16 (postgres:16-alpine) | 17 | Debian's | **restore failed**: `SET transaction_timeout` |
| CI run 233 on `a60edca` (the real stage, PGDG client pinned to 16) | 16 | 16 (exact-major check passed) | Debian's | steps 1–5 of that version of the rehearsal pass; steps 6–8 were added after it and run in CI with the next push |
| Locally, PostgreSQL 17's own tools against our 16 | 16.15 | 17.11 | — | `pg_restore` 17 → 16 fails (`transaction_timeout`); `pg_restore` 16 can't read the 17 archive |

The sandbox image is a stand-in: its tools were copied from this machine, because the package
mirrors aren't reachable from here. Only CI's runs prove the image that would actually ship.

CI's first run of it found a real defect. The stage installed Debian's `postgresql-client`,
which is version 17. Its backups of the 16 server succeeded, but the restore failed with
`unrecognized configuration parameter "transaction_timeout"`. Reproduced here with PostgreSQL
17's tools: `pg_restore` 17 can't restore into 16, and `pg_restore` 16 can't read a `pg_dump` 17
archive (`unsupported version (1.16) in file header`). Every backup it made could only have
been restored into PostgreSQL 17 or newer. Now:
- the image installs the 16 client from PostgreSQL's own apt repository;
- `backup-database` refuses a mismatched `pg_dump`;
- `restore-database` refuses a `pg_restore` that can't read the backup, or that is newer than
  the target server.

All before writing anything (`tests/test_backup.py`).

## Limits

- **No continuous archiving (point-in-time recovery).** Up to a day of writes can be lost
  between nightly backups. A managed PostgreSQL usually offers PITR; turn it on when choosing
  one.
- Nothing schedules the backup job, copies backups off-site or sends an alert until there's a
  host and a storage provider. The job, the cron line and the checks are ready.
- Upgrading PostgreSQL to a new major version means changing `PG_MAJOR` with the server image
  (a test fails until both match). Restore older backups with the `pg_restore` of the version
  that made them (the manifest's `pg_dump_version`) into a server of that version, then upgrade.
- Deleted accounts stay in older backups until those expire (up to about 3 months with the
  proposed retention). A restore brings them back, so after a restore, delete again any
  account deleted after that backup was taken. [PRIVACY.md](PRIVACY.md) explains this to
  users.
- Restores were rehearsed on one machine, against the same PostgreSQL version.

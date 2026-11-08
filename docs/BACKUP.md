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
| Row-level security: `ENABLE`/`FORCE`, both policies on all 30 learner tables | yes | restored; the restore counts the policies against the manifest |
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
- A failed dump keeps nothing.
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

**Retention** (`prune-backups`; a dry run unless `--apply`):
- the newest backup, and every backup made in the 24 hours before it (`--keep-within-hours`);
- the newest of each of the last 7 days, 4 ISO weeks and 3 months that have a backup
  (`--keep-daily`, `--keep-weekly`, `--keep-monthly`).

It counts backups, not the calendar. If backups stop, nothing more expires while they're stopped.
It only manages `codecoach-<UTC time>` pairs. A named backup, half a pair, or any other file is
listed and left alone. A backup's dump is deleted before its manifest, so an interrupted prune
never leaves something that looks complete.

**Checks** (`check-backups --dir DIR [--max-age-hours 26] [--all]`, exit 1 on a problem):
- the newest backup is under 26 hours old;
- its manifest is readable;
- the encrypted file's SHA-256 matches the manifest. A truncated or damaged copy fails.

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

**4. Before switching anyone to it:**
- start the app against the copy, as the app role: `check-rls --strict` and `/health/ready`;
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

The whole scheduled path ran in the production compose rehearsal
(`scripts/rehearse_production_storage.sh`, step 5). Two runs of the `backup` service each backed
up as the owner, pruned and checked. The API container had no backups volume. The newest backup
restored into a separate database with a key the server never held, with the rehearsal's saved
note in it, and no password appeared in any output. In this sandbox the image's `pg_dump` and
`age` came from the host (`pg_dump` 16), because the package mirror isn't reachable from here.
CI builds the real `backup` stage and runs the same rehearsal.

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

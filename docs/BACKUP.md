# Server backups and recovery

This page is about recovering the **whole server**: every account, after a lost disk, a bad
migration or a deleted volume. It is not the per-account export in Settings ("Download your
data", [BACKUP_FORMAT.md](BACKUP_FORMAT.md)). That export gives one person their own records.
It can't rebuild the database: no other accounts, no sign-in data, no schema, sequences or
security policies.

> Status: the tools and the procedure exist and were rehearsed on disposable databases on this
> machine. **No backup schedule, off-site storage or production restore exists yet.** Those need
> a host. A backup that was made, or even uploaded, isn't a recovery until a restore from it has
> been rehearsed.

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
([ROW_LEVEL_SECURITY.md](ROW_LEVEL_SECURITY.md)). Needs `pg_dump` (same major version as the
server, or newer) and `age`.

```bash
DATABASE_URL=postgresql+psycopg://codecoach_owner:…@host:5432/codecoach \
  python -m app.cli backup-database --out /var/backups/codecoach --recipients /etc/codecoach/recipients.txt
```

- The plaintext never touches the disk: the dump is hashed and encrypted as it streams.
- A backup never overwrites another.
- A failed dump keeps nothing.

**Proposed schedule.** None is installed yet: pick it with the host.
- Nightly, e.g. cron `17 3 * * *`.
- Copied off the host to storage in a different account or region. A backup on the same disk
  dies with it.
- Kept 7 daily, 4 weekly and 3 monthly, then deleted.
- Alert when a night's backup is missing.

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
| Recovery point (data you can lose) | ≤ 24 h, with nightly backups | none: no schedule is running |
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

All verified locally on PostgreSQL 16; in CI once pushed (`TEST_DATABASE_ADMIN_URL` is set
there).

## Limits

- **No continuous archiving (point-in-time recovery).** Up to a day of writes can be lost
  between nightly backups. A managed PostgreSQL usually offers PITR; turn it on when choosing
  one.
- No schedule, off-site copy or alerting exists until there's a host.
- Deleted accounts stay in older backups until those expire (up to about 3 months with the
  proposed retention). A restore brings them back, so after a restore, delete again any
  account deleted after that backup was taken. [PRIVACY.md](PRIVACY.md) explains this to
  users.
- Restores were rehearsed on one machine, against the same PostgreSQL version.

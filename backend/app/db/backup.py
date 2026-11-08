"""Operational database backups: the whole PostgreSQL database, encrypted, with a manifest, and
a restore that only ever writes into a separate, empty database.

This is NOT the per-account export (Settings → "Download your data", docs/BACKUP_FORMAT.md). That
gives one person their own records. This is what you need when the server or its disk is lost:
every account, the schema at its migration revision, sequences, row-level security policies and
grants. docs/BACKUP.md is the runbook.

A backup is two files with one name:
- `NAME.dump.age`: `pg_dump --format=custom` output, encrypted with age to one or more
  recipients (public keys). The machine making backups holds only public keys, so it can't
  decrypt them. The private key (identity) lives somewhere else (docs/BACKUP.md).
- `NAME.manifest.json`: plain JSON with no user data: when it was made, the migration revision,
  the PostgreSQL version, row counts per table, the roles that own or were granted the tables,
  and SHA-256 hashes of both the encrypted file and the plaintext dump.

Versions: `pg_dump` must be the server's major version. A newer one dumps fine, but its archive can't
be read by the server's own `pg_restore`. And a newer `pg_restore` can't restore into the older server:
it sends settings that server doesn't know. So a mismatched backup could only ever be restored into a
newer PostgreSQL. `backup()` refuses a mismatch before writing anything, rather than leaving it to be
found on the day of a restore.

`restore()` refuses before writing anything when:
- the encrypted file doesn't match its manifest (damaged or incomplete);
- the identity file is missing;
- decryption fails (wrong key, or tampering: age is authenticated);
- the decrypted dump doesn't match the manifest;
- the backup's schema is newer than this code;
- `pg_restore` is older than the `pg_dump` that made the backup, or newer than the target server;
- the target is the live database, or isn't empty;
- a role the backup needs doesn't exist on the target server.

After restoring, it checks every table's row count against the manifest and confirms the RLS
policies came back.

Runs `pg_dump`, `pg_restore` and `age` as subprocesses; database URLs reach them through
environment variables, never the command line, so passwords don't appear in process lists.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.engine import Connection, Engine

CHUNK = 1 << 20
# Successful restores are recorded next to the backups they came from, so `check-backups` can say
# when recovery was last rehearsed. Not a backup: pruning never touches it.
RESTORE_LOG = "codecoach-restores.json"


class BackupError(RuntimeError):
    """A backup or restore refused or failed; the message says why, never with a secret in it."""


def _libpq_env(url: str) -> dict[str, str]:
    """The connection as libpq environment variables (PGHOST, PGPASSWORD, ...), for pg_dump and
    pg_restore, so no password is ever an argument."""
    u = make_url(url)
    env = {
        **os.environ,
        "PGHOST": u.host or "localhost",
        "PGPORT": str(u.port or 5432),
        "PGDATABASE": u.database or "",
    }
    if u.username:
        env["PGUSER"] = u.username
    if u.password:
        env["PGPASSWORD"] = u.password
    return env


def _need(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise BackupError(f"`{tool}` isn't installed on this machine (docs/BACKUP.md lists what's needed)")
    return path


def major_of(version_output: str) -> int | None:
    """The major version in `pg_dump --version` style output, e.g. "pg_dump (PostgreSQL) 16.4 (Debian …)"."""
    m = re.search(r"\(PostgreSQL\)\s+(\d+)", version_output)
    return int(m.group(1)) if m else None


def _tool_major(tool: str) -> int:
    out = subprocess.run([tool, "--version"], capture_output=True, text=True).stdout
    major = major_of(out)
    if major is None:
        raise BackupError(f"couldn't tell which version `{Path(tool).name}` is")
    return major


def _server_major(conn: Connection) -> int:
    return int(conn.execute(text("SHOW server_version_num")).scalar_one()) // 10000


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _inventory(engine: Engine) -> dict[str, Any]:
    with engine.connect() as conn:
        return _inventory_on(conn)


def _inventory_on(conn: Connection) -> dict[str, Any]:
    """What a restore must bring back: tables and their row counts, owners, grantees, policies,
    the migration revision."""
    tables = [
        r[0]
        for r in conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        )
    ]
    counts = {t: conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar_one() for t in tables}
    owners = sorted(
        {
            r[0]
            for r in conn.execute(
                text("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'")
            )
        }
    )
    grantees = sorted(
        {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT DISTINCT grantee FROM information_schema.role_table_grants "
                    "WHERE table_schema = 'public' AND grantee <> 'PUBLIC'"
                )
            )
        }
        - set(owners)
    )
    policies = conn.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")).scalar_one()
    revision = (
        sorted(r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version")))
        if "alembic_version" in tables
        else []
    )
    server = conn.execute(text("SHOW server_version")).scalar_one()
    return {
        "tables": counts,
        "table_owners": owners,
        "granted_roles": grantees,
        "policies": policies,
        "schema_revision": revision,
        "server_version": server,
    }


class _Hash:
    """SHA-256 of the plaintext dump as it streams past, and its size."""

    def __init__(self) -> None:
        self._h = hashlib.sha256()
        self.plain_bytes = 0

    def update(self, chunk: bytes) -> None:
        self._h.update(chunk)
        self.plain_bytes += len(chunk)

    def hexdigest(self) -> str:
        return self._h.hexdigest()


def _dump_to(
    pg_dump: str, age: str, database_url: str, recipients: Path, dump_file: Path, snapshot: str, plain: _Hash
) -> None:
    """Stream pg_dump through age into `dump_file`. On ANY failure (pg_dump, age, a broken pipe
    because one of them died, an exception here) nothing is kept: the partial file is deleted and
    both processes are reaped. A partial dump left behind would look like the newest backup."""
    kept = False
    dump_err = age_err = ""
    dump_rc = encrypt_rc = -1
    broken = False
    try:
        with dump_file.open("xb") as out:
            encrypt = subprocess.Popen(
                [age, "--encrypt", "-R", str(recipients)],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=subprocess.PIPE,
            )
            # --enable-row-security: the tables FORCE row-level security, so a plain pg_dump as their
            # owner is refused. With no RLS scope set the owner sees every row (db/rls.py).
            dump = subprocess.Popen(
                [
                    pg_dump,
                    "--format=custom",
                    "--enable-row-security",
                    "--no-password",
                    f"--snapshot={snapshot}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=_libpq_env(database_url),
            )
            assert dump.stdout and encrypt.stdin
            try:
                try:
                    while chunk := dump.stdout.read(CHUNK):
                        plain.update(chunk)
                        encrypt.stdin.write(chunk)
                except BrokenPipeError:  # age exited early (no usable key, disk full, ...)
                    broken = True
                try:
                    encrypt.stdin.close()
                except BrokenPipeError:
                    broken = True
            finally:
                if dump.poll() is None and broken:
                    dump.kill()
                dump_err = dump.stderr.read().decode(errors="replace") if dump.stderr else ""
                age_err = encrypt.stderr.read().decode(errors="replace") if encrypt.stderr else ""
                dump_rc, encrypt_rc = dump.wait(), encrypt.wait()
        kept = dump_rc == 0 and encrypt_rc == 0 and not broken
    finally:
        if not kept:
            dump_file.unlink(missing_ok=True)
    if not kept:
        # The first real cause: age's message when it failed (it names files, never keys), else
        # pg_dump's. Never the database URL: it reaches pg_dump through the environment only.
        source = age_err if (encrypt_rc != 0 or broken) and age_err.strip() else dump_err
        detail = (
            source.strip().splitlines()[-1]
            if source.strip()
            else f"pg_dump exited {dump_rc}, age exited {encrypt_rc}"
        )
        raise BackupError(f"backup failed, nothing kept: {detail}")


@dataclass
class Backup:
    dump: Path
    manifest: Path
    seconds: float
    manifest_data: dict[str, Any] = field(default_factory=dict)


def manifest_path(dump: Path) -> Path:
    return dump.with_name(dump.name.removesuffix(".dump.age") + ".manifest.json")


def backup(database_url: str, out_dir: Path, recipients_file: Path, name: str | None = None) -> Backup:
    """Dump, encrypt to the recipients' public keys, and write the manifest. The plaintext dump
    never touches the disk: pg_dump's output is hashed and fed to age as it streams."""
    pg_dump, age = _need("pg_dump"), _need("age")
    if not recipients_file.is_file():
        raise BackupError("the recipients file (age public keys) doesn't exist")
    started = time.monotonic()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dump_file = out_dir / f"{name or 'codecoach-' + stamp}.dump.age"
    if dump_file.exists():
        raise BackupError(f"{dump_file.name} already exists: backups are never overwritten")
    plain = _Hash()
    # One snapshot for the manifest's counts and for pg_dump: the counts describe exactly what's
    # in the dump, even while people keep writing.
    engine = create_engine(database_url, isolation_level="REPEATABLE READ")
    snapshot_conn = engine.connect()
    try:
        server_major, dump_major = _server_major(snapshot_conn), _tool_major(pg_dump)
        if dump_major != server_major:
            raise BackupError(
                f"pg_dump {dump_major} doesn't match the server's PostgreSQL {server_major}: a backup it made "
                f"could only be restored into PostgreSQL {dump_major} or newer. Use pg_dump {server_major} "
                "(docs/BACKUP.md)"
            )
        snapshot = snapshot_conn.execute(text("SELECT pg_export_snapshot()")).scalar_one()
        inventory = _inventory_on(snapshot_conn)
        _dump_to(pg_dump, age, database_url, recipients_file, dump_file, snapshot, plain)
    finally:
        snapshot_conn.close()
        engine.dispose()
    data = {
        "format": "codecoach-backup/1",
        "created_at": datetime.now(UTC).isoformat(),
        "dump_file": dump_file.name,
        "encrypted_sha256": _sha256(dump_file),
        "encrypted_bytes": dump_file.stat().st_size,
        "plaintext_sha256": plain.hexdigest(),
        "plaintext_bytes": plain.plain_bytes,
        "pg_dump_version": subprocess.run(
            [pg_dump, "--version"], capture_output=True, text=True
        ).stdout.strip(),
        **inventory,
    }
    manifest = manifest_path(dump_file)
    # The manifest is the completion marker: written under a temporary name (which pruning never
    # touches), then renamed, so nobody ever sees half a manifest.
    partial = manifest.with_name("." + manifest.name + ".partial")
    partial.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(partial, manifest)
    return Backup(dump_file, manifest, time.monotonic() - started, data)


@dataclass
class Restored:
    timings: dict[str, float]
    tables: int
    rows: int
    schema: str  # current | behind (migrate next) | ...
    notes: list[str]
    held_emails: int = 0  # unsent at backup time, held on the copy (email-quarantine)


def _check_target(target_url: str, live_url: str | None) -> Engine:
    if live_url:
        t, live = make_url(target_url), make_url(live_url)
        if (t.host, t.port or 5432, t.database) == (live.host, live.port or 5432, live.database):
            raise BackupError(
                "the target is the live database (DATABASE_URL): restore into a separate, empty one"
            )
    engine = create_engine(target_url)
    try:
        if inspect(engine).get_table_names():
            raise BackupError(
                "the target database isn't empty: restore only into a new, empty database "
                "(nothing is ever restored over existing data)"
            )
    except BackupError:
        engine.dispose()
        raise
    return engine


def restore(
    dump_file: Path,
    identity_file: Path,
    target_url: str,
    live_url: str | None = None,
    known_revisions: frozenset[str] | None = None,
) -> Restored:
    """Restore into `target_url`, a separate, empty database. Every check that can fail without
    writing runs first."""
    from app.db import rls

    pg_restore, age = _need("pg_restore"), _need("age")
    timings: dict[str, float] = {}
    notes: list[str] = []
    t0 = time.monotonic()

    manifest_file = manifest_path(dump_file)
    if not dump_file.is_file() or not manifest_file.is_file():
        raise BackupError("the backup is incomplete: the encrypted dump or its manifest is missing")
    try:
        manifest = json.loads(manifest_file.read_text())
    except (OSError, ValueError):
        raise BackupError("the manifest isn't readable JSON: the backup is damaged or incomplete") from None
    if not isinstance(manifest, dict) or manifest.get("format") != "codecoach-backup/1":
        raise BackupError("not a CodeCoach backup manifest")
    needed = ("encrypted_sha256", "plaintext_sha256", "tables", "table_owners", "granted_roles", "policies")
    if missing := [k for k in needed if k not in manifest]:
        raise BackupError(
            f"the manifest is incomplete (no {', '.join(missing)}): the backup can't be checked, so it isn't restored"
        )
    if _sha256(dump_file) != manifest["encrypted_sha256"]:
        raise BackupError("the encrypted dump doesn't match its manifest: it's damaged or incomplete")
    if not identity_file.is_file():
        raise BackupError(
            "the identity file (the age private key) is missing: without it nothing can be restored"
        )

    if known_revisions is None:
        from app.api.routes.health import _revisions

        found = _revisions()
        known_revisions = found[1] if found else frozenset()
    revision = set(manifest.get("schema_revision") or [])
    if revision and not revision <= known_revisions:
        raise BackupError(
            "the backup's schema revision is newer than this code: restore it with the version of "
            "CodeCoach that made it, then upgrade"
        )

    engine = _check_target(target_url, live_url)
    try:
        with engine.connect() as conn:
            present = {r[0] for r in conn.execute(text("SELECT rolname FROM pg_roles"))}
            target_major = _server_major(conn)
        restore_major = _tool_major(pg_restore)
        made_with = major_of(manifest.get("pg_dump_version", ""))
        if made_with is not None and restore_major < made_with:
            raise BackupError(
                f"this backup was made with pg_dump {made_with}, which pg_restore {restore_major} can't "
                f"read: restore it with pg_restore {made_with} (into PostgreSQL {made_with} or newer)"
            )
        if restore_major > target_major:
            raise BackupError(
                f"pg_restore {restore_major} can't restore into PostgreSQL {target_major} (it sends settings "
                f"{target_major} doesn't know): use pg_restore {target_major}"
            )
        missing_roles = [r for r in manifest["table_owners"] + manifest["granted_roles"] if r not in present]
        if missing_roles:
            raise BackupError(
                "roles the backup needs don't exist on this server: "
                + ", ".join(missing_roles)
                + " (create them first: deploy/postgres-init/10-roles.sh, or CREATE ROLE ... NOSUPERUSER NOBYPASSRLS)"
            )
        timings["checks"] = time.monotonic() - t0

        with tempfile.TemporaryDirectory(prefix="codecoach-restore-") as tmp:
            os.chmod(tmp, 0o700)
            plain = Path(tmp) / "dump"
            t1 = time.monotonic()
            with plain.open("xb") as out:
                done = subprocess.run(
                    [age, "--decrypt", "-i", str(identity_file)],
                    stdin=dump_file.open("rb"),
                    stdout=out,
                    stderr=subprocess.PIPE,
                )
            if done.returncode != 0:
                raise BackupError("decryption failed: wrong identity file, or the backup was altered")
            if _sha256(plain) != manifest["plaintext_sha256"]:
                raise BackupError("the decrypted dump doesn't match its manifest")
            timings["decrypt"] = time.monotonic() - t1

            t2 = time.monotonic()
            restored = subprocess.run(
                [
                    pg_restore,
                    "--exit-on-error",
                    "--single-transaction",
                    "--no-password",
                    "--dbname",
                    make_url(target_url).database or "",
                    str(plain),
                ],
                env=_libpq_env(target_url),
                capture_output=True,
                text=True,
            )
            if restored.returncode != 0:
                last = (
                    restored.stderr.strip().splitlines()[-1]
                    if restored.stderr.strip()
                    else "pg_restore failed"
                )
                raise BackupError(f"restore failed and was rolled back (one transaction): {last}")
            timings["restore"] = time.monotonic() - t2

        t3 = time.monotonic()
        database = make_url(target_url).database
        with engine.begin() as conn:
            for role in manifest["granted_roles"]:  # database-level CONNECT isn't part of a dump
                conn.execute(text(f'GRANT CONNECT ON DATABASE "{database}" TO "{role}"'))
        after = _inventory(engine)
        short = {t: n for t, n in manifest["tables"].items() if after["tables"].get(t, -1) != n}
        if short:
            raise BackupError(f"row counts differ after the restore: {sorted(short)}")
        if after["policies"] != manifest["policies"]:
            raise BackupError("row-level security policies didn't all come back")
        status = rls.rls_status(engine)
        if status.get("missing"):
            raise BackupError(f"row-level security is missing on: {status['missing']}")
        timings["verify"] = time.monotonic() - t3
    finally:
        engine.dispose()

    from sqlalchemy.orm import Session

    from app.api.routes.health import schema_state

    check = create_engine(target_url)
    try:
        with Session(bind=check) as db:
            schema = schema_state(db)
            # Before anything can start on the copy: emails that were unsent at backup time are
            # held, not sent by the first worker that starts (email-quarantine decides).
            from app.services.email_ops import hold_unsent

            held = hold_unsent(db)
    finally:
        check.dispose()
    if held:
        notes.append(
            f"{held} email(s) unsent at backup time are held, not sent: review them with "
            "`python -m app.cli email-quarantine`, then release or suppress them (docs/BACKUP.md)"
        )
    if schema == "behind":
        notes.append(
            "the backup's schema is older than this code: run `alembic upgrade head` on the restored copy"
        )
    timings["total"] = time.monotonic() - t0
    rows = sum(after["tables"].values())
    if not _record_restore(dump_file, len(after["tables"]), rows, schema, held):
        notes.append(f"couldn't record this rehearsal in {RESTORE_LOG} (the backup folder is read-only?)")
    return Restored(timings, len(after["tables"]), rows, schema, notes, held)


def _record_restore(dump_file: Path, tables: int, rows: int, schema: str, held: int = 0) -> bool:
    """Append this restore to the backup folder's log (no user data: names and counts)."""
    log = dump_file.parent / RESTORE_LOG
    try:
        records = json.loads(log.read_text()) if log.exists() else []
        if not isinstance(records, list):
            records = []
        records.append(
            {
                "restored_at": datetime.now(UTC).isoformat(),
                "backup": dump_file.name.removesuffix(".dump.age"),
                "tables": tables,
                "rows": rows,
                "schema": schema,
                "held_emails": held,
            }
        )
        partial = log.with_name("." + log.name + ".partial")
        partial.write_text(json.dumps(records[-50:], indent=2) + "\n")
        os.replace(partial, log)
        return True
    except (OSError, ValueError):
        return False

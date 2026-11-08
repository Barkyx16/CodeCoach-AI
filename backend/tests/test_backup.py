"""Operational backups: an encrypted full-database backup restores into a separate, empty
database, and the app runs against the copy. Two restored accounts keep their own records and
can't reach each other's. The restore refuses a damaged or incomplete backup, a missing or wrong
key, a schema newer than the code, a non-empty or live target, and missing roles. It never writes
before refusing.

Needs PostgreSQL (TEST_DATABASE_ADMIN_URL, as tests/test_storage.py) and the `age` and `pg_dump`
tools. Synthetic accounts only; every database and role is disposable and dropped."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.db.backup import BackupError, backup, restore
from app.main import create_app
from tests.conftest import auth_headers, register
from tests.test_storage import ADMIN_URL, needs_admin, rehearsal, run  # noqa: F401  (rehearsal: a fixture)

pytestmark = [
    needs_admin,
    pytest.mark.skipif(not (shutil.which("age") and shutil.which("pg_dump")), reason="needs age and pg_dump"),
]


@pytest.fixture
def keys(tmp_path) -> tuple[Path, Path]:
    """An age key pair: recipients (public, on the server) and identity (private, kept elsewhere)."""
    identity = tmp_path / "keys" / "identity.txt"
    identity.parent.mkdir()
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    public = next(
        line.split(": ", 1)[1] for line in identity.read_text().splitlines() if "public key" in line
    )
    recipients = tmp_path / "recipients.txt"
    recipients.write_text(public + "\n")
    return recipients, identity


@pytest.fixture
def source(rehearsal, make_settings):  # noqa: F811
    """A production-shaped database (owner + app role) with two accounts' work in it."""
    rehearsal.init_roles()
    run(["alembic", "upgrade", "head"], rehearsal.owner_url)
    run(["app.cli", "seed"], rehearsal.owner_url)
    run(["app.cli", "grant-app-role", rehearsal.app], rehearsal.owner_url)
    with TestClient(create_app(make_settings(database_url=rehearsal.app_url, auto_migrate=False))) as c:
        for email in ("ada@example.com", "bea@example.com"):
            h = auth_headers(register(c, email=email))
            for i in (1, 2):
                assert (
                    c.post("/api/v1/me/notes", headers=h, json={"title": f"{email} note {i}"}).status_code
                    == 201
                )
    return rehearsal


@pytest.fixture
def empty_target(source):
    """A second disposable database, empty, owned by the same owner role."""
    name = f"{source.db}_restore_{secrets.token_hex(2)}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"CREATE DATABASE {name} OWNER {source.owner}"))
    url = source.owner_url.rsplit("/", 1)[0] + f"/{name}"
    try:
        yield url
    finally:
        with admin.connect() as c:
            c.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d"), {"d": name}
            )
            c.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        admin.dispose()


def as_app(url: str, owner: str, app_role: str, app_pw: str) -> str:
    return (
        url.replace(f"{owner}:", f"{app_role}:").split("@", 1)[0].rsplit(":", 1)[0]
        + f":{app_pw}@"
        + url.split("@", 1)[1]
    )


def test_a_backup_restores_into_a_separate_database_and_the_app_runs_on_it(
    source, empty_target, keys, tmp_path, make_settings, capsys
):
    recipients, identity = keys
    made = backup(source.owner_url, tmp_path / "backups", recipients)
    manifest = made.manifest_data
    assert manifest["tables"]["users"] == 2 and manifest["tables"]["notes"] == 4
    assert manifest["table_owners"] == [source.owner] and source.app in manifest["granted_roles"]
    assert manifest["policies"] == 60  # 30 learner tables x (owner-only + maintenance read)
    assert b"ada@example.com" not in made.dump.read_bytes()  # encrypted, not just compressed
    assert "ada@example.com" not in made.manifest.read_text()  # the manifest holds no user data

    done = restore(made.dump, identity, empty_target, live_url=source.owner_url)
    assert done.schema == "current" and done.rows == sum(manifest["tables"].values())
    with capsys.disabled():
        print(
            f"\n[backup] {made.seconds:.2f} s; [restore] "
            + ", ".join(f"{k} {v:.2f} s" for k, v in done.timings.items())
        )

    # The app, as the ordinary app role, against the restored copy.
    restored_app = as_app(empty_target, source.owner, source.app, source.app_pw)
    status = run(["app.cli", "check-rls", "--strict"], restored_app)
    assert "Row-level security is enforced." in status.stdout
    with TestClient(create_app(make_settings(database_url=restored_app, auto_migrate=False))) as c:
        assert c.get("/health/ready").json()["checks"] == {"database": "ok", "schema": "current"}
        mine = {}
        for email in ("ada@example.com", "bea@example.com"):
            r = c.post("/api/v1/auth/login", json={"email": email, "password": "CorrectHorse42"})
            assert r.status_code == 200, r.text
            h = auth_headers(r.json())
            notes = c.get("/api/v1/me/notes", headers=h).json()["items"]
            assert sorted(n["title"] for n in notes) == [f"{email} note 1", f"{email} note 2"]
            mine[email] = (h, notes[0]["id"])
        # Each restored account keeps to its own records.
        ada_h, ada_note = mine["ada@example.com"]
        bea_h, bea_note = mine["bea@example.com"]
        assert c.get(f"/api/v1/me/notes/{ada_note}", headers=bea_h).status_code == 404
        assert c.patch(f"/api/v1/me/notes/{bea_note}", headers=ada_h, json={"title": "x"}).status_code == 404
        # New work on the copy gets fresh ids (sequences came back too).
        assert c.post("/api/v1/me/notes", headers=ada_h, json={"title": "after restore"}).status_code == 201


def test_the_restore_refuses_before_writing_anything(source, empty_target, keys, tmp_path):
    recipients, identity = keys
    made = backup(source.owner_url, tmp_path / "backups", recipients)

    def refused(dump: Path, key: Path = identity, target: str = empty_target, match: str = "") -> None:
        with pytest.raises(BackupError, match=match):
            restore(dump, key, target, live_url=source.owner_url)
        with create_engine(target).connect() as conn:  # and nothing was written
            assert (
                conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")).scalar() == 0
            )

    def variant(name: str, data: bytes, manifest: dict | None = None) -> Path:
        dump = tmp_path / "variants" / f"{name}.dump.age"
        dump.parent.mkdir(exist_ok=True)
        dump.write_bytes(data)
        body = manifest or json.loads(made.manifest.read_text())
        (dump.parent / f"{name}.manifest.json").write_text(json.dumps(body))
        return dump

    original = made.dump.read_bytes()
    manifest = json.loads(made.manifest.read_text())

    # Damaged or incomplete: the hash in the manifest catches it before decrypting.
    flipped = bytearray(original)
    flipped[len(flipped) // 2] ^= 0xFF
    refused(variant("flipped", bytes(flipped)), match="damaged or incomplete")
    refused(variant("truncated", original[: len(original) // 2]), match="damaged or incomplete")
    no_manifest = tmp_path / "lonely.dump.age"
    no_manifest.write_bytes(original)
    refused(no_manifest, match="incomplete")
    # Altered together with its manifest's hash: age's authentication refuses it.
    import hashlib

    forged = variant(
        "forged", bytes(flipped), {**manifest, "encrypted_sha256": hashlib.sha256(bytes(flipped)).hexdigest()}
    )
    refused(forged, match="decryption failed")

    # Keys: missing, or someone else's.
    refused(made.dump, key=tmp_path / "nowhere.txt", match="identity file")
    other = tmp_path / "other-identity.txt"
    subprocess.run(["age-keygen", "-o", str(other)], check=True, capture_output=True)
    refused(made.dump, key=other, match="decryption failed")

    # A schema this code doesn't know (a backup from a newer version).
    refused(
        variant("newer", original, {**manifest, "schema_revision": ["ffffffffffff"]}),
        match="newer than this code",
    )

    # A role the backup needs that this server lacks.
    refused(
        variant("roles", original, {**manifest, "granted_roles": ["codecoach_rehearsal_nobody"]}),
        match="roles",
    )

    # Versions (CI's rehearsal found this with Debian's pg_restore 17 and a PostgreSQL 16 server):
    # a pg_restore older than the backup's pg_dump can't read it, and a newer one than the target
    # server sends settings it doesn't know. Both refused before writing anything.
    refused(
        variant("from-17", original, {**manifest, "pg_dump_version": "pg_dump (PostgreSQL) 99.1"}),
        match="made with pg_dump 99",
    )
    import app.db.backup as backup_module

    real_major = backup_module._tool_major
    try:
        backup_module._tool_major = lambda tool: 99  # a pg_restore newer than the server
        refused(made.dump, match="pg_restore 99 can't restore into PostgreSQL")
    finally:
        backup_module._tool_major = real_major

    # Never over the live database, never over one that has data.
    with pytest.raises(BackupError, match="live database"):
        restore(made.dump, identity, source.owner_url, live_url=source.owner_url)
    with pytest.raises(BackupError, match="isn't empty"):
        restore(made.dump, identity, source.owner_url, live_url=None)

    # And after all of that, the real backup still restores.
    assert restore(made.dump, identity, empty_target, live_url=source.owner_url).schema == "current"


def test_a_backup_never_overwrites_one_and_a_failed_dump_keeps_nothing(source, keys, tmp_path):
    recipients, _ = keys
    first = backup(source.owner_url, tmp_path / "b", recipients, name="nightly")
    with pytest.raises(BackupError, match="already exists"):
        backup(source.owner_url, tmp_path / "b", recipients, name="nightly")
    assert first.dump.exists()
    broken = source.owner_url.rsplit("/", 1)[0] + "/codecoach_rehearsal_does_not_exist"
    with pytest.raises(Exception):  # noqa: B017 - connection refused before anything is written
        backup(broken, tmp_path / "c", recipients)
    assert not list((tmp_path / "c").glob("*.dump.age"))


def test_a_pg_dump_that_doesnt_match_the_server_is_refused_before_anything_is_written(
    source, keys, tmp_path, monkeypatch
):
    """Its backup could only ever be restored into a newer PostgreSQL, found out on the worst day."""
    import app.db.backup as backup_module

    monkeypatch.setattr(backup_module, "_tool_major", lambda tool: 99)
    with pytest.raises(BackupError, match="pg_dump 99 doesn't match the server's PostgreSQL"):
        backup(source.owner_url, tmp_path / "b", keys[0])
    assert not list((tmp_path / "b").glob("*"))


def test_the_cli_says_what_happened_and_prints_no_secrets(source, empty_target, keys, tmp_path):
    recipients, identity = keys
    made = run(
        ["app.cli", "backup-database", "--out", str(tmp_path / "cli"), "--recipients", str(recipients)],
        source.owner_url,
    )
    assert "Backup written" in made.stdout and "Not proof of recovery" in made.stdout
    dump = next((tmp_path / "cli").glob("*.dump.age"))
    import os

    env = {**os.environ, "RESTORE_DATABASE_URL": empty_target, "DATABASE_URL": source.owner_url}
    done = subprocess.run(
        [os.sys.executable, "-m", "app.cli", "restore-database", str(dump), "--identity", str(identity)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "counts and row-level security policies match" in done.stdout
    for secret in (source.owner_pw, source.app_pw):
        assert secret not in made.stdout + done.stdout + done.stderr

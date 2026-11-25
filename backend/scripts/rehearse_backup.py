"""Rehearse an encrypted backup and an isolated restore at a realistic size, and time it.

    TEST_DATABASE_ADMIN_URL=postgresql+psycopg://admin:...@localhost:5432/postgres \\
        python scripts/rehearse_backup.py [--users 5000] [--notes-per-user 10]

Everything is disposable and synthetic: a `codecoach_rehearsal_bk_*` source and target database,
and owner and app roles made by deploy/postgres-init/10-roles.sh. All of them are dropped at the
end, pass or fail. Steps, each timed:
1. Production-shaped source: roles, `alembic upgrade head`, seed, grant-app-role.
2. Two real accounts through the API (they can sign in), plus N synthetic accounts with notes
   inserted in bulk.
3. `backup-database` (pg_dump, snapshot-consistent, encrypted with age to a fresh key).
4. `restore-database` into an empty second database (checks, decrypt, pg_restore in one
   transaction, verify counts and policies).
5. The app on the restored copy, as the app role: readiness, both real accounts sign in and see
   only their own notes, cross-reads are 404, `check-rls --strict` passes.
Prints a report. It measures this machine, not a production server or network.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.db.backup import backup, restore  # noqa: E402
from app.main import create_app  # noqa: E402

PASSWORD = "CorrectHorse42"


def sh(args: list[str], url: str) -> str:
    env = {**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "development"}
    done = subprocess.run([sys.executable, "-m", *args], cwd=BACKEND, env=env, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"{' '.join(args)} failed:\n{done.stdout}{done.stderr}")
    return done.stdout


def settings(url: str) -> Settings:
    return Settings(
        environment="test",
        database_url=url,
        secret_key="rehearsal-secret-key-that-is-long-enough-0123456789",
        auto_migrate=False,
        background_jobs_in_api=False,
        email_backend="file",  # synthetic emails go to a throwaway folder, not the terminal
        email_file_dir=tempfile.mkdtemp(prefix="codecoach-rehearsal-mail-"),
        auth_rate_limit_per_minute=1000,
        _env_file=None,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=5000)
    ap.add_argument("--notes-per-user", type=int, default=10)
    args = ap.parse_args()
    admin_url = os.environ.get("TEST_DATABASE_ADMIN_URL")
    if not admin_url:
        print("set TEST_DATABASE_ADMIN_URL (a role that can create databases and roles)")
        return 2
    admin = make_url(admin_url)
    suffix = secrets.token_hex(3)
    src_db, dst_db = f"codecoach_rehearsal_bk_{suffix}", f"codecoach_rehearsal_bk_{suffix}_restored"
    owner, app_role = f"codecoach_rehearsal_owner_{suffix}", f"codecoach_rehearsal_app_{suffix}"
    owner_pw, app_pw = secrets.token_hex(16), secrets.token_hex(16)

    def url(user: str, pw: str, db: str) -> str:
        return admin.set(
            drivername="postgresql+psycopg", username=user, password=pw, database=db
        ).render_as_string(hide_password=False)

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    report: list[tuple[str, str]] = []
    timed: dict[str, float] = {}
    try:
        with engine.connect() as c:
            c.execute(text(f"CREATE DATABASE {src_db}"))
        env = {
            **os.environ,
            "PGHOST": admin.host or "localhost",
            "PGPORT": str(admin.port or 5432),
            "PGPASSWORD": admin.password or "",
            "POSTGRES_USER": admin.username or "",
            "POSTGRES_DB": src_db,
            "CODECOACH_OWNER_ROLE": owner,
            "CODECOACH_APP_ROLE": app_role,
            "CODECOACH_OWNER_PASSWORD": owner_pw,
            "CODECOACH_APP_PASSWORD": app_pw,
        }
        subprocess.run(
            ["sh", str(REPO / "deploy/postgres-init/10-roles.sh")], env=env, check=True, capture_output=True
        )
        src_owner, src_app = url(owner, owner_pw, src_db), url(app_role, app_pw, src_db)
        t = time.monotonic()
        sh(["alembic", "upgrade", "head"], src_owner)
        sh(["app.cli", "seed"], src_owner)
        sh(["app.cli", "grant-app-role", app_role], src_owner)
        timed["migrate + seed + grant"] = time.monotonic() - t

        with TestClient(create_app(settings(src_app))) as c:
            for email in ("ada@example.com", "bea@example.com"):
                r = c.post(
                    "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": None}
                )
                h = {"Authorization": f"Bearer {r.json()['access_token']}"}
                c.post("/api/v1/me/notes", headers=h, json={"title": f"{email}'s note"})
        t = time.monotonic()
        with create_engine(src_owner).begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, auth_provider_id, password_hash, is_guest, token_version, created_at, is_admin) "
                    "SELECT 'bulk-' || g, 'bulk' || g || '@example.com', 'local:bulk-' || g, 'x', false, 0, now(), false "
                    "FROM generate_series(1, :n) g"
                ),
                {"n": args.users},
            )
            conn.execute(
                text(
                    "INSERT INTO notes (id, user_id, title, body, reflection, tags, pinned, archived, revision, created_at, updated_at) "
                    "SELECT 'bulk-' || u || '-' || k, 'bulk-' || u, 'Synthetic note ' || k, repeat('synthetic text ', 40), "
                    "'', '[]', false, false, 1, now(), now() FROM generate_series(1, :n) u, generate_series(1, :k) k"
                ),
                {"n": args.users, "k": args.notes_per_user},
            )
        timed["bulk insert"] = time.monotonic() - t

        with tempfile.TemporaryDirectory() as tmp:
            identity, recipients = Path(tmp) / "identity.txt", Path(tmp) / "recipients.txt"
            subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
            recipients.write_text(
                next(
                    line.split(": ", 1)[1]
                    for line in identity.read_text().splitlines()
                    if "public key" in line
                )
                + "\n"
            )
            made = backup(src_owner, Path(tmp) / "backups", recipients)
            timed["backup (dump + encrypt)"] = made.seconds
            rows = sum(made.manifest_data["tables"].values())
            report.append(("dataset", f"{rows} rows in {len(made.manifest_data['tables'])} tables"))
            report.append(("encrypted backup", f"{made.dump.stat().st_size / 1e6:.1f} MB"))

            with engine.connect() as c:
                c.execute(text(f"CREATE DATABASE {dst_db} OWNER {owner}"))
            dst_owner, dst_app = url(owner, owner_pw, dst_db), url(app_role, app_pw, dst_db)
            done = restore(made.dump, identity, dst_owner, live_url=src_owner)
            for k, v in done.timings.items():
                timed[f"restore: {k}"] = v

        t = time.monotonic()
        with TestClient(create_app(settings(dst_app))) as c:
            assert c.get("/health/ready").status_code == 200
            seen = {}
            for email in ("ada@example.com", "bea@example.com"):
                r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
                assert r.status_code == 200, r.text
                h = {"Authorization": f"Bearer {r.json()['access_token']}"}
                items = c.get("/api/v1/me/notes", headers=h).json()["items"]
                assert [n["title"] for n in items] == [f"{email}'s note"], items
                seen[email] = (h, items[0]["id"])
            assert (
                c.get(
                    f"/api/v1/me/notes/{seen['ada@example.com'][1]}", headers=seen["bea@example.com"][0]
                ).status_code
                == 404
            )
        strict = sh(["app.cli", "check-rls", "--strict"], dst_app)
        assert "least-privilege" in strict
        timed["app on the copy: ready, sign-ins, isolation, check-rls"] = time.monotonic() - t
        report.append(
            (
                "verification",
                "readiness 200; both accounts see only their own notes; cross-read 404; check-rls --strict passes",
            )
        )
    finally:
        with engine.connect() as c:
            for db in (dst_db, src_db):
                c.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d"),
                    {"d": db},
                )
                c.execute(text(f"DROP DATABASE IF EXISTS {db}"))
            for role in (owner, app_role):
                c.execute(text(f"DROP ROLE IF EXISTS {role}"))
        engine.dispose()

    print(
        f"Backup rehearsal ({args.users} synthetic users x {args.notes_per_user} notes, plus 2 real accounts)"
    )
    for k, v in report:
        print(f"  {k}: {v}")
    for k, v in timed.items():
        print(f"  {k}: {v:.2f} s")
    print("Disposable databases and roles dropped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

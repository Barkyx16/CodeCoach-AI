"""Launch rehearsal: the intended production configuration, isolated on this machine, with a real
account journey and three injected faults. Prints a pass/fail report; everything it made is
removed at the end, pass or fail.

    python scripts/rehearse_launch.py        # needs docker, openssl, and the backend's virtualenv

The environment, all disposable and synthetic:
- PostgreSQL 16 in a docker container (`codecoach_rehearsal_launch_*`), roles made by the real
  deploy/postgres-init/10-roles.sh, migrated, seeded and granted as the owner.
- The API as its own uvicorn process with ENVIRONMENT=production. It passes every production
  guard and connects as the app role.
- Mail: a real SMTP conversation with verified STARTTLS (tests/smtp_fake.py, a throwaway CA).
  Nothing leaves the machine.

Steps:
- preflight, then an owned account: sign up, verify with the emailed code, save work;
- a second account: it can't see or change the first one's work;
- restart the API (SIGKILL): nobody is signed out, nothing is lost;
- password recovery by email;
- mail outage, then recovery: the email arrives once;
- database outage, then recovery: no lost data, nobody signed out;
- worker interruption (a job claimed by a process that died): delivered once after its lease;
- account deletion: the second account is unaffected.

One thing differs from a real launch: AUTH_RATE_LIMIT_PER_MINUTE is raised, so one script can
run the journey. The API is served over HTTPS (uvicorn's own TLS, with the throwaway
certificate), so the Secure refresh cookie works as it would behind a real https proxy. The
refresh is checked after the restart, during and after the database outage, and after the
password reset.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from email import message_from_bytes
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from tests.smtp_fake import FakeSMTPServer, make_certificate  # noqa: E402

PASSWORD, NEW_PASSWORD = "CorrectHorse42", "BatteryStaple99"
results: list[tuple[str, bool, str]] = []


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}", flush=True)


def sh(args: list[str], env: dict, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(args, cwd=BACKEND, env=env, capture_output=True, text=True)
    if check and done.returncode:
        raise SystemExit(f"{' '.join(args[:4])} failed:\n{done.stdout[-2000:]}{done.stderr[-2000:]}")
    return done


class Api:
    """The API over HTTPS (uvicorn's own TLS, the rehearsal's throwaway certificate), so the
    Secure refresh cookie behaves as it would behind a real https proxy."""

    def __init__(self, env: dict, cert: tuple[Path, Path]):
        self.env, self.port, self.cert = env, free_port(), cert
        self.base = f"https://localhost:{self.port}"
        self.proc: subprocess.Popen | None = None

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base, timeout=10, verify=str(self.cert[0]))

    def ready(self, timeout: float = 1) -> int:
        return httpx.get(self.base + "/health/ready", timeout=timeout, verify=str(self.cert[0])).status_code

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                str(self.port),
                "--ssl-certfile",
                str(self.cert[0]),
                "--ssl-keyfile",
                str(self.cert[1]),
            ],  # fmt: skip
            cwd=BACKEND,
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(150):
            try:
                if self.ready() == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        raise SystemExit("the API didn't become ready")

    def kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGKILL)
            self.proc.wait(10)


def code_for(smtp: FakeSMTPServer, to: str, after: int = 0, timeout: float = 30) -> tuple[str, int]:
    """The newest verification code sent to `to`, waiting for it; and how many mails `to` got."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        mine = [m for m in smtp.messages if message_from_bytes(m)["To"] == to]
        if len(mine) > after:
            body = message_from_bytes(mine[-1]).get_payload(decode=True).decode()
            found = re.search(r"verification code is: (\d{6})|#token=([\w-]+)", body)
            if found:
                return found.group(1) or found.group(2), len(mine)
        time.sleep(0.25)
    raise AssertionError(f"no email arrived for {to}")


def main() -> int:
    for tool in ("docker", "openssl"):
        if shutil.which(tool) is None:
            print(f"needs {tool}")
            return 2
    tmp = Path(tempfile.mkdtemp(prefix="codecoach-launch-"))
    suffix = secrets.token_hex(3)
    container = f"codecoach_rehearsal_launch_{suffix}"
    pg_port, smtp_port = free_port(), free_port()
    superuser_pw, owner_pw, app_pw = (secrets.token_hex(16) for _ in range(3))
    cert = make_certificate(tmp, "localhost")
    smtp = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], port=smtp_port)
    api: Api | None = None
    try:
        sh(
            [
                "docker", "run", "-d", "--name", container,
                "-e", f"POSTGRES_PASSWORD={superuser_pw}", "-e", "POSTGRES_DB=codecoach",
                "-e", f"CODECOACH_OWNER_PASSWORD={owner_pw}", "-e", f"CODECOACH_APP_PASSWORD={app_pw}",
                "-v", f"{REPO / 'deploy' / 'postgres-init'}:/docker-entrypoint-initdb.d:ro",
                "-p", f"127.0.0.1:{pg_port}:5432", "postgres:16-alpine",
            ],
            dict(os.environ),
        )  # fmt: skip
        for _ in range(120):
            ok = sh(
                ["docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "codecoach"],
                dict(os.environ),
                check=False,
            )
            if ok.returncode == 0:
                break
            time.sleep(0.5)
        time.sleep(1.5)  # the image restarts the server once after running the init scripts
        owner_url = f"postgresql+psycopg://codecoach_owner:{owner_pw}@127.0.0.1:{pg_port}/codecoach"
        app_url = f"postgresql+psycopg://codecoach_app:{app_pw}@127.0.0.1:{pg_port}/codecoach"
        prod = {
            **os.environ,
            "ENVIRONMENT": "production",
            "AUTO_MIGRATE": "false",
            "SECRET_KEY": secrets.token_urlsafe(48),
            "APP_BASE_URL": "https://rehearsal.invalid",
            "CORS_ORIGINS": "https://rehearsal.invalid",
            "METRICS_TOKEN": secrets.token_hex(32),
            "EMAIL_BACKEND": "smtp",
            "SMTP_HOST": "localhost",
            "SMTP_PORT": str(smtp_port),
            "SMTP_SECURITY": "starttls",
            "SMTP_CA_BUNDLE": str(cert[0]),
            "SMTP_USERNAME": "rehearsal",
            "SMTP_PASSWORD": secrets.token_hex(16),
            "SMTP_TIMEOUT_SECONDS": "2",
            "EMAIL_FROM": "CodeCoach AI <no-reply@rehearsal.invalid>",
            "AUTH_RATE_LIMIT_PER_MINUTE": "200",
        }
        for k in ("DATABASE_URL", "TEST_DATABASE_URL", "EMAIL_FILE_DIR"):
            prod.pop(k, None)
        migrate = {**prod, "DATABASE_URL": owner_url}
        sh([sys.executable, "-m", "alembic", "upgrade", "head"], migrate)
        sh([sys.executable, "-m", "app.cli", "seed"], migrate)
        sh([sys.executable, "-m", "app.cli", "grant-app-role", "codecoach_app"], migrate)
        run_env = {**prod, "DATABASE_URL": app_url}

        # A backup first, so preflight has a manifest to look at.
        identity, recipients = tmp / "identity.txt", tmp / "recipients.txt"
        subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
        recipients.write_text(
            next(x.split(": ", 1)[1] for x in identity.read_text().splitlines() if "public key" in x) + "\n"
        )
        sh(
            [
                sys.executable,
                "-m",
                "app.cli",
                "backup-database",
                "--out",
                str(tmp / "backups"),
                "--recipients",
                str(recipients),
            ],
            migrate,
        )
        manifest = next((tmp / "backups").glob("*.manifest.json"))
        pre = sh(
            [
                sys.executable,
                "-m",
                "app.cli",
                "preflight",
                "--connect-email",
                "--backup-manifest",
                str(manifest),
                "--json",
            ],
            run_env,
            check=False,
        )
        checks = json.loads(pre.stdout[pre.stdout.index("[") :])
        print("\n== preflight (this environment)")
        for c in checks:
            print(f"   {c['status'].upper():<10} {c['area']:<18} {c['reason']}")
        blocked = [c["area"] for c in checks if c["status"] == "blocked"]
        record("preflight has nothing blocked", not blocked, ", ".join(blocked))

        print("\n== journey")
        api = Api(run_env, cert)
        api.start()
        c, cb = api.client(), api.client()  # one per account: each holds its own session cookie
        REFRESH = {"X-Requested-With": "codecoach"}

        def refresh(client: httpx.Client) -> int:
            return client.post("/api/v1/auth/refresh", headers=REFRESH).status_code

        def headers(token: str) -> dict:
            return {"Authorization": f"Bearer {token}"}

        a_mail, b_mail = f"owner-{suffix}@example.com", f"second-{suffix}@example.com"
        r = c.post(
            "/api/v1/auth/register", json={"email": a_mail, "password": PASSWORD, "display_name": "Owner"}
        )
        a = r.json()["access_token"]
        code, _ = code_for(smtp, a_mail)
        r = c.post("/api/v1/auth/verify-email/code", headers=headers(a), json={"code": code})
        record(
            "sign up and verify with the emailed code",
            r.status_code == 200 and r.json()["email_verified"] is True,
        )
        note = c.post(
            "/api/v1/me/notes",
            headers=headers(a),
            json={"title": "Owner's private note", "body": "synthetic"},
        ).json()
        record("save work", bool(note.get("id")))

        b = cb.post(
            "/api/v1/auth/register", json={"email": b_mail, "password": PASSWORD, "display_name": "Second"}
        ).json()["access_token"]
        cross = cb.get(f"/api/v1/me/notes/{note['id']}", headers=headers(b))
        change = cb.patch(
            f"/api/v1/me/notes/{note['id']}", headers=headers(b), json={"base_revision": 1, "title": "x"}
        )
        listing = cb.get("/api/v1/me/notes", headers=headers(b)).json()["items"]
        record(
            "a second account can't see or change it",
            cross.status_code == 404 and change.status_code == 404 and listing == [],
        )

        api.kill()
        api.start()
        me = c.get("/api/v1/auth/me", headers=headers(a))
        kept = c.get(f"/api/v1/me/notes/{note['id']}", headers=headers(a))
        after_restart = refresh(c)  # the Secure refresh cookie, over https
        record(
            "restart (SIGKILL): still signed in (token and refresh cookie), work intact",
            me.status_code == 200
            and kept.json().get("title") == "Owner's private note"
            and after_restart == 200,
        )

        c.post("/api/v1/auth/password-reset", json={"email": a_mail})
        token, _ = code_for(smtp, a_mail, after=1)
        r = c.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
        stale_session = refresh(c)  # the reset ended every session, this one's cookie included
        old_pw = c.post("/api/v1/auth/login", json={"email": a_mail, "password": PASSWORD})
        login = c.post("/api/v1/auth/login", json={"email": a_mail, "password": NEW_PASSWORD})
        record(
            "recover with an emailed reset link",
            r.status_code == 204
            and stale_session == 401
            and old_pw.status_code == 401
            and login.status_code == 200,
            "(a reset signs out every session, by design)",
        )
        a = login.json()["access_token"]

        print("\n== faults")
        smtp.close()  # mail outage
        c_mail = f"third-{suffix}@example.com"
        r = c.post(
            "/api/v1/auth/register", json={"email": c_mail, "password": PASSWORD, "display_name": None}
        )
        third = r.json()["access_token"]
        signed_in = c.get("/api/v1/auth/me", headers=headers(third)).status_code == 200
        time.sleep(1)
        smtp = FakeSMTPServer(certfile=cert[0], keyfile=cert[1], port=smtp_port)  # the mail server is back
        db = ["docker", "exec", container, "psql", "-U", "postgres", "-d", "codecoach", "-Atc"]
        sh([*db, "UPDATE email_jobs SET next_attempt_at = now() WHERE status = 'pending'"], dict(os.environ))
        code, n = code_for(smtp, c_mail, timeout=40)
        verified = (
            c.post("/api/v1/auth/verify-email/code", headers=headers(third), json={"code": code}).status_code
            == 200
        )
        time.sleep(6)  # another jobs-thread pass: nothing is sent twice
        again = len([m for m in smtp.messages if message_from_bytes(m)["To"] == c_mail])
        record(
            "mail outage: signed up meanwhile; the code arrives once when mail is back",
            signed_in and verified and again == 1,
        )

        sh(["docker", "stop", container], dict(os.environ))  # database outage
        during = api.ready(timeout=10)
        refresh_during = refresh(c)  # an outage must not end the session (the app keeps it on a 503)
        failed_write = c.post(
            "/api/v1/me/notes", headers=headers(a), json={"title": "during the outage"}
        ).status_code
        subprocess.run(["docker", "start", container], check=True, capture_output=True)
        for _ in range(120):
            try:
                if api.ready(timeout=2) == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        after = c.get(f"/api/v1/me/notes/{note['id']}", headers=headers(a))
        refresh_after = refresh(c)
        record(
            "database outage: 503 while down, then back with nothing lost and nobody signed out",
            during == 503
            and failed_write >= 500
            and after.status_code == 200
            and after.json()["title"] == "Owner's private note"
            and refresh_during == 503
            and refresh_after == 200,
            f"(ready={during}, write={failed_write}, refresh={refresh_during} while down; refresh={refresh_after} after)",
        )

        d_mail = f"fourth-{suffix}@example.com"
        api.kill()  # the process running jobs dies...
        sh(
            [
                *db,
                f"INSERT INTO users (id, email, auth_provider_id, password_hash, is_guest, token_version, created_at, is_admin) VALUES ('rehearsal-d', '{d_mail}', 'local:rehearsal-d', 'x', false, 0, now(), false)",
            ],
            dict(os.environ),
        )
        sh(
            [*db, "INSERT INTO email_jobs (id, kind, user_id, payload, status, attempts, next_attempt_at, created_at) "
                  "VALUES ('rehearsal-job', 'verify_email', 'rehearsal-d', '{}', 'sending', 1, now() - interval '1 second', now())"],
            dict(os.environ),
        )  # ...mid-send: claimed, its lease run out  # fmt: skip
        api.start()  # a new process takes over
        _, got = code_for(smtp, d_mail, timeout=40)
        time.sleep(6)
        total = len([m for m in smtp.messages if message_from_bytes(m)["To"] == d_mail])
        status = sh(
            [*db, "SELECT status FROM email_jobs WHERE id = 'rehearsal-job'"], dict(os.environ)
        ).stdout.strip()
        record(
            "worker interruption: the claimed job is delivered once after its lease",
            got == 1 and total == 1 and status == "accepted",
        )

        print("\n== deletion")
        r = c.request(
            "DELETE",
            "/api/v1/auth/me",
            headers=headers(a),
            json={"password": NEW_PASSWORD, "confirm": "DELETE"},
        )
        gone = c.get("/api/v1/auth/me", headers=headers(a)).status_code
        login = c.post("/api/v1/auth/login", json={"email": a_mail, "password": NEW_PASSWORD}).status_code
        left = sh(
            [*db, f"SELECT count(*) FROM notes WHERE id = '{note['id']}'"], dict(os.environ)
        ).stdout.strip()
        b_ok = c.get("/api/v1/auth/me", headers=headers(b)).status_code == 200
        record(
            "delete the account: gone, can't sign in, the second account unaffected",
            r.status_code == 204 and gone == 401 and login == 401 and left == "0" and b_ok,
        )
    except AssertionError as exc:
        record("journey step", False, str(exc))
    finally:
        if api:
            api.kill()
        smtp.close()
        subprocess.run(["docker", "rm", "-f", "-v", container], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [n for n, ok, _ in results if not ok]
    print(
        f"\n{len(results) - len(failed)} passed, {len(failed)} failed. Container, keys, mail and processes removed."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

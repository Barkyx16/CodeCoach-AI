"""Rehearse a database-level backup and restore of saved answers on disposable PostgreSQL databases.

    createdb codecoach_rehearsal_src && createdb codecoach_rehearsal_dst
    python scripts/rehearse_restore.py postgresql+psycopg://user:pass@localhost:5432/codecoach_rehearsal_src \\
        postgresql+psycopg://user:pass@localhost:5432/codecoach_rehearsal_dst

Both must be local ``codecoach_rehearsal_*`` databases. The source's ``public`` schema is emptied and
migrated to head, the target is overwritten by the restore. Never point either at shared data.

1. Through the API (the current code), two synthetic accounts save: a keyed answer each with the
   same key string, a resend of each, an explicit revision, a too-short answer.
2. ``pg_dump --format=custom`` of the source, ``pg_restore --clean --if-exists`` into the target.
3. Logical comparison, not byte comparison: per-table row counts; every answer's id, owner, key,
   fingerprint, revision link, score and stored feedback; the migration revision.
4. ``check-answers`` on the restored copy: no violations.
5. Smoke on the restored copy: each account signs in, resends its keyed request and gets its own
   original answer back (200, replayed); the question summaries say the same as before.

This is a local rehearsal of standard PostgreSQL tools. It says nothing about a production backup
schedule, recovery time or data loss window, none of which exists in this repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
LONG = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)
SHORT = "I would check the patient and call the doctor."
KEY = "op-restore-shared-01"
PASSWORD = "CorrectHorse42"


def _guard(url: str) -> sa.engine.URL:
    u = make_url(url)
    if not (u.database or "").startswith("codecoach_rehearsal_") or u.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("refused: only local databases named codecoach_rehearsal_* may be used")
    return u


def _pg_env(u: sa.engine.URL) -> dict[str, str]:
    return {
        **os.environ,
        "PGPASSWORD": u.password or "",
        "PGHOST": u.host or "",
        "PGPORT": str(u.port or 5432),
        "PGUSER": u.username or "",
    }


def _client(url: str):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        environment="test",
        database_url=url,
        ai_provider="offline",
        auth_rate_limit_per_minute=1000,
        secret_key="rehearsal-secret-key-that-is-long-enough-0123456789",
        _env_file=None,
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


def _snapshot(eng: sa.Engine) -> dict:
    with eng.connect() as c:
        tables = [t for t in sa.inspect(eng).get_table_names() if t != "alembic_version"]
        counts = {t: c.execute(sa.text(f'select count(*) from "{t}"')).scalar_one() for t in sorted(tables)}
        answers = c.execute(
            sa.text(
                "select id, user_id, client_request_id, request_fingerprint, revises_answer_id, score, "
                "feedback::text, answer from practice_answers order by id"
            )
        ).all()
        version = c.execute(sa.text("select version_num from alembic_version")).scalar()
    return {
        "counts": counts,
        "answers": hashlib.sha256(repr(answers).encode()).hexdigest(),
        "version": version,
        "answer_rows": len(answers),
    }


def _rehearse(src: str, dst: str, out: dict) -> int:
    su, du = _guard(src), _guard(dst)
    if su.database == du.database:
        raise SystemExit("refused: source and target must be different databases")
    out.update({"source": su.database, "target": du.database})
    ok = True

    def step(name: str, passed: bool, **detail) -> None:
        nonlocal ok
        ok &= passed
        out["steps"].append({"step": name, "passed": passed, **detail})

    seng = sa.create_engine(su)
    with seng.begin() as c:
        c.execute(sa.text("drop schema public cascade"))
        c.execute(sa.text("create schema public"))
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={src}", "upgrade", "head"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    step("source migrated to head", r.returncode == 0)

    from app.careers.questions import questions_for

    qid = questions_for("registered-nurse")[0].id
    url = f"/api/v1/careers/registered-nurse/questions/{qid}/answers"
    accounts = {}
    with _client(src) as c:
        for who in ("ada", "bo"):
            email = f"{who}-restore@example.com"
            t = c.post(
                "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": who}
            )
            h = {"Authorization": f"Bearer {t.json()['access_token']}"}
            first = c.post(url, headers=h, json={"answer": LONG, "client_request_id": KEY}).json()
            again = c.post(url, headers=h, json={"answer": LONG, "client_request_id": KEY})
            c.post(
                url,
                headers=h,
                json={"answer": LONG + " Then I documented it.", "revises_answer_id": first["id"]},
            )
            c.post(url, headers=h, json={"answer": SHORT})
            summary = next(
                q
                for q in c.get(
                    "/api/v1/careers/registered-nurse/questions", headers=h, params={"page_size": 200}
                ).json()["items"]
                if q["id"] == qid
            )
            accounts[who] = {
                "email": email,
                "first": first["id"],
                "replayed": again.status_code == 200,
                "summary": {k: summary[k] for k in ("best_score", "best_scored", "score_status")},
            }
    step(
        "seeded through the API",
        all(a["replayed"] for a in accounts.values()) and accounts["ada"]["first"] != accounts["bo"]["first"],
        accounts={k: {"summary": v["summary"]} for k, v in accounts.items()},
    )
    before = _snapshot(seng)

    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "rehearsal.dump"
        r1 = subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", f"--file={dump}", su.database],
            env=_pg_env(su),
            capture_output=True,
            text=True,
        )
        r2 = subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--no-owner", f"--dbname={du.database}", str(dump)],
            env=_pg_env(du),
            capture_output=True,
            text=True,
        )
        step(
            "pg_dump and pg_restore",
            r1.returncode == 0 and r2.returncode == 0,
            dump_bytes=dump.stat().st_size if dump.exists() else 0,
            restore_errors=r2.stderr.strip()[-200:],
        )
    deng = sa.create_engine(du)
    after = _snapshot(deng)
    step(
        "logical comparison",
        before == after,
        tables=len(after["counts"]),
        answer_rows=after["answer_rows"],
        version=after["version"],
    )

    from app.db.session import make_session_factory
    from app.services.answer_invariants import check

    with make_session_factory(deng)() as s:
        rep = check(s)
    step("check-answers on the restored copy", rep.ok, scope=rep.summary()["scope"])

    with _client(dst) as c:
        smoke = {}
        for who, a in accounts.items():
            t = c.post("/api/v1/auth/login", json={"email": a["email"], "password": PASSWORD})
            h = {"Authorization": f"Bearer {t.json().get('access_token', '')}"}
            r = c.post(url, headers=h, json={"answer": LONG, "client_request_id": KEY})
            summary = next(
                (
                    q
                    for q in c.get(
                        "/api/v1/careers/registered-nurse/questions", headers=h, params={"page_size": 200}
                    )
                    .json()
                    .get("items", [])
                    if q["id"] == qid
                ),
                {},
            )
            smoke[who] = {
                "login": t.status_code,
                "resend": r.status_code,
                "own_original": r.status_code == 200 and r.json()["id"] == a["first"],
                "summary_same": {k: summary.get(k) for k in a["summary"]} == a["summary"],
            }
    step(
        "smoke on the restored copy",
        all(s["own_original"] and s["summary_same"] and s["login"] == 200 for s in smoke.values()),
        accounts=smoke,
    )
    out["passed"] = ok
    print(json.dumps(out, indent=2))
    seng.dispose()
    deng.dispose()
    return 0 if ok else 1


def main(src: str, dst: str) -> int:
    """Run the rehearsal; if a step raises, print what ran so far, labelled aborted, and fail."""
    out: dict = {"steps": []}
    try:
        return _rehearse(src, dst, out)
    except Exception as exc:  # noqa: BLE001 - reported, then a failing exit status
        out["passed"] = False
        out["aborted"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}"
        print(json.dumps(out, indent=2, default=str))
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))

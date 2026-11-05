"""Rehearse the practice-answer migration (c4d5e6f7a8b9) on a disposable PostgreSQL database.

    createdb codecoach_rehearsal_rr
    python scripts/rehearse_answer_migration.py postgresql+psycopg://user:pass@localhost:5432/codecoach_rehearsal_rr

Refuses any database whose name doesn't start with ``codecoach_rehearsal_`` or that isn't on
localhost, and empties only that database's ``public`` schema. Never point it at shared data.

Steps, each checked (exit 1 on any surprise; a JSON summary is printed):

1. Migrate to the previous head (b7c1d2e3f4a5) and add synthetic answers as older versions stored
   them: scored, too short, legacy with a word count, legacy with nothing recorded.
2. **Interrupted upgrade:** a second connection holds a lock on ``practice_answers`` (as a long
   read would), so the upgrade's ALTER waits and hits ``lock_timeout``. Expected: the upgrade fails,
   the version stays at b7c1d2e3f4a5, no column exists, and every row is byte-for-byte as before.
3. **Retry:** the upgrade runs to head. Old rows gain no key, fingerprint or link; nothing is
   rewritten; ``alembic check`` finds no difference from the models; each legacy row is classified
   by the eligibility rule as documented.
4. **Rollback:** keyed answers and a revision link are added at head, then the migration is
   downgraded. Expected: every answer, its text, score and feedback stay; keys, fingerprints and
   links are dropped. Upgrading again does not bring them back (they are lost, not hidden).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parent.parent
PREVIOUS, HEAD = "b7c1d2e3f4a5", "c4d5e6f7a8b9"
NEW_COLUMNS = {"client_request_id", "request_fingerprint", "revises_answer_id"}
LEGACY = [  # (label, score, feedback changes, expected eligibility)
    ("scored", 72, {"evidence_level": "sufficient", "word_count": 120}, "scored"),
    ("too_short", 35, {"evidence_level": "insufficient", "word_count": 12}, "too_short"),
    ("legacy_count_long", 64, {"word_count": 80}, "scored"),
    ("legacy_count_short", 30, {"word_count": 25}, "too_short"),
    ("legacy_nothing", 50, {}, "unknown"),
]


def _guard(url: str) -> sa.engine.URL:
    u = make_url(url)
    if not (u.database or "").startswith("codecoach_rehearsal_") or u.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("refused: only a local database named codecoach_rehearsal_* may be used")
    return u


def _alembic(url: str, *args: str, lock_timeout_ms: int | None = None) -> subprocess.CompletedProcess:
    target = url
    if lock_timeout_ms is not None:
        target += f"?options=-c%20lock_timeout%3D{lock_timeout_ms}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={target}", *args],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )


def _version(eng: sa.Engine) -> str | None:
    with eng.connect() as c:
        return c.execute(sa.text("select version_num from alembic_version")).scalar()


def _columns(eng: sa.Engine) -> set[str]:
    return {c["name"] for c in sa.inspect(eng).get_columns("practice_answers")}


def _digest(eng: sa.Engine) -> str:
    """Every answer's stored content, as text: a change anywhere changes the digest."""
    with eng.connect() as c:
        rows = c.execute(
            sa.text("select id, user_id, answer, score, feedback::text from practice_answers order by id")
        ).all()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def _count(eng: sa.Engine) -> int:
    with eng.connect() as c:
        return c.execute(sa.text("select count(*) from practice_answers")).scalar_one()


def _seed(eng: sa.Engine) -> tuple[str, dict[str, str]]:
    now = datetime.now(UTC)
    user = str(uuid.uuid4())
    ids = {}
    with eng.begin() as c:
        c.execute(
            sa.text(
                "insert into users (id, auth_provider_id, is_guest, token_version, created_at, email) "
                "values (:id, :ap, false, 0, :now, :email)"
            ),
            {"id": user, "ap": f"rehearsal-{user}", "now": now, "email": "rehearsal@example.com"},
        )
        for label, score, extra, _ in LEGACY:
            ids[label] = str(uuid.uuid4())
            fb = {"rating": "Developing", "points": [], "summary": "synthetic", **extra}
            c.execute(
                sa.text(
                    "insert into practice_answers (id, user_id, track, question_id, difficulty, answer, score, "
                    "feedback, provider, created_at) values (:id, :u, 'registered-nurse', 'rn-rehearsal', "
                    "'easy', :answer, :score, cast(:fb as jsonb), 'offline', :now)"
                ),
                {
                    "id": ids[label],
                    "u": user,
                    "answer": f"(synthetic {label})",
                    "score": score,
                    "fb": json.dumps(fb),
                    "now": now,
                },
            )
    return user, ids


def main(url: str) -> int:
    u = _guard(url)
    eng = sa.create_engine(u)
    out: dict = {"database": u.database, "steps": []}
    ok = True

    def step(name: str, passed: bool, **detail) -> None:
        nonlocal ok
        ok &= passed
        out["steps"].append({"step": name, "passed": passed, **detail})

    with eng.begin() as c:  # empty only this disposable database
        c.execute(sa.text("drop schema public cascade"))
        c.execute(sa.text("create schema public"))
    r = _alembic(url, "upgrade", PREVIOUS)
    step(
        "migrate to the previous head", r.returncode == 0 and _version(eng) == PREVIOUS, version=_version(eng)
    )
    user, ids = _seed(eng)
    before, n = _digest(eng), _count(eng)

    blocker = eng.connect()
    blocker.begin()
    blocker.execute(sa.text("select count(*) from practice_answers"))  # holds ACCESS SHARE
    t0 = time.monotonic()
    r = _alembic(url, "upgrade", HEAD, lock_timeout_ms=1500)
    waited = round(time.monotonic() - t0, 1)
    blocker.rollback()
    blocker.close()
    reason = next((x for x in r.stderr.splitlines() if "lock timeout" in x.lower()), r.stderr.strip()[-200:])
    step(
        "interrupted upgrade rolls back completely",
        r.returncode != 0
        and _version(eng) == PREVIOUS
        and not NEW_COLUMNS & _columns(eng)
        and _digest(eng) == before
        and _count(eng) == n,
        exit_code=r.returncode,
        failure=reason,
        seconds=waited,
        version=_version(eng),
    )

    r = _alembic(url, "upgrade", HEAD)
    with eng.connect() as c:
        nulls = c.execute(
            sa.text(
                "select count(*) from practice_answers where client_request_id is null "
                "and request_fingerprint is null and revises_answer_id is null"
            )
        ).scalar_one()
    step(
        "retry reaches head without rewriting a row",
        r.returncode == 0 and _version(eng) == HEAD and _digest(eng) == before and nulls == n,
        version=_version(eng),
        rows_without_key_or_link=f"{nulls}/{n}",
    )
    r = _alembic(url, "check")
    said = next((x for x in (r.stdout + r.stderr).splitlines() if "upgrade operations" in x), "")
    step(
        "alembic check: models and schema agree", r.returncode == 0 and "No new" in said, output=said.strip()
    )

    sys.path.insert(0, str(BACKEND))
    from app.careers.eligibility import feedback_eligibility

    with eng.connect() as c:
        stored = dict(c.execute(sa.text("select id, feedback from practice_answers")).all())
    got = {label: feedback_eligibility(stored[ids[label]]) for label, *_ in LEGACY}
    want = {label: exp for label, _, _, exp in LEGACY}
    step("legacy rows classified as documented", got == want, classified=got)

    keyed, rev = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.now(UTC)
    with eng.begin() as c:
        for rid, key, parent in ((keyed, "op-rehearsal-1", None), (rev, "op-rehearsal-2", keyed)):
            c.execute(
                sa.text(
                    "insert into practice_answers (id, user_id, track, question_id, difficulty, answer, score, "
                    "feedback, provider, created_at, client_request_id, request_fingerprint, revises_answer_id) "
                    "values (:id, :u, 'registered-nurse', 'rn-rehearsal', 'easy', '(synthetic keyed)', 70, "
                    'cast(\'{"evidence_level": "sufficient", "word_count": 90}\' as jsonb), \'offline\', :now, '
                    ":key, 'v1:synthetic', :parent)"
                ),
                {"id": rid, "u": user, "now": now, "key": key, "parent": parent},
            )
    with_keys, n2 = _digest(eng), _count(eng)
    r = _alembic(url, "downgrade", PREVIOUS)
    step(
        "downgrade keeps every answer and drops keys and links",
        r.returncode == 0
        and _version(eng) == PREVIOUS
        and _count(eng) == n2
        and _digest(eng) == with_keys
        and not NEW_COLUMNS & _columns(eng),
        version=_version(eng),
        answers=f"{_count(eng)}/{n2}",
    )
    r = _alembic(url, "upgrade", HEAD)
    with eng.connect() as c:
        lost = c.execute(
            sa.text(
                "select count(*) from practice_answers where id in (:a, :b) and client_request_id is null"
            ),
            {"a": keyed, "b": rev},
        ).scalar_one()
        links = c.execute(
            sa.text("select count(*) from practice_answers where revises_answer_id is not null")
        ).scalar_one()
    step(
        "re-upgrade: dropped keys and links stay lost",
        r.returncode == 0 and lost == 2 and links == 0,
        keys_lost=lost,
        links_left=links,
    )
    out["passed"] = ok
    print(json.dumps(out, indent=2))
    eng.dispose()
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))

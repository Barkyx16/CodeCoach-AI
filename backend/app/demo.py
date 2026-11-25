"""The portfolio demo (Volume 7, prompt 10; docs/DEMO.md): fictional sample learners, their
example answers, and a guarded, repeatable reset of a demo database.

- **Fictional, and said to be.** The sample learners are made up. Their answers were written for
  the demo and graded by the built-in grader when the demo database was set up; every place that
  shows them says so. They can't sign in (no email, no password).
- **Visitors are isolated.** Each visitor uses their own guest session, with the app's usual
  per-account checks (and row-level security on PostgreSQL). The sample learners' answers are a
  read-only sample, shown to everyone.
- **The reset only touches a demo database.** Before changing anything it checks: the database's
  name contains "demo"; the name was confirmed on the command line; it isn't a production server
  without DEMO_MODE; and it holds no account that isn't a guest or a sample learner. Then it
  empties every table but the problem catalogue, seeds the catalogue and the sample learners with
  fixed ids and times, and checks the result. Two resets give the same fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, delete, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.careers.answers import graded_answer
from app.careers.questions import get_question
from app.config import Settings
from app.db.seed import seed_problems
from app.models import Base, PracticeAnswer, User

MARKER = "demo:sample-learner:"
EXAMPLE_LABEL = (
    "Example answer, written for this demo by a fictional learner. "
    "The score is CodeCoach's built-in grader's, from when the demo was set up."
)
_NAMESPACE = uuid.UUID("6f1d4c2e-6b7a-4d0e-9a51-3c2f0d9b7e10")
_SEEDED_AT = datetime(2026, 1, 12, 9, 0, tzinfo=UTC)
# Seeded content: kept by a reset (seed_problems upserts it). Everything else is emptied.
CONTENT_TABLES = {"problems", "test_cases"}


@dataclass(frozen=True)
class Example:
    question_id: str
    text: str


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    career_track: str
    summary: str
    start_question_id: str
    problem_slug: str | None
    examples: tuple[Example, ...]


PERSONAS: tuple[Persona, ...] = (
    Persona(
        key="nurse",
        name="Sam Rivera",
        career_track="registered-nurse",
        summary="A fictional registered nurse with two years on a medical ward, preparing to move to an "
        "emergency department.",
        start_question_id="e-steps-0",
        problem_slug=None,
        examples=(
            Example(
                "e-time-0",
                "Last winter, on a night shift, I was looking after five patients on a medical ward. During my "
                "2 a.m. assessment I noticed that one man's breathing had become faster and his oxygen saturation "
                "had dropped to 89%. I was responsible for spotting the change and acting on it. I rechecked his "
                "vital signs, sat him up, started oxygen as prescribed and called the rapid response team. I asked "
                "a colleague to cover my other patients and updated the doctor using SBAR. As a result, he was "
                "stable within thirty minutes and moved to a higher-care bed. I learned to trust a small change in "
                "the numbers and to escalate early.",
            ),
            Example(
                "e-good-0",
                "Good patient assessment means checking the patient properly and writing it down. It is "
                "important to be thorough.",
            ),
        ),
    ),
    Persona(
        key="engineer",
        name="Alex Chen",
        career_track="software-engineer",
        summary="A fictional software engineer with three years building web services, practising Java "
        "problems and how to talk about debugging.",
        start_question_id="e-steps-0",
        problem_slug="two-sum",
        examples=(
            Example(
                "e-time-0",
                "Last spring our checkout service started timing out for about 2% of orders. I was the on-call "
                "engineer, so finding the cause was my job. I compared slow and fast requests in the traces and "
                "saw that the slow ones all loaded a customer's full order history. I reproduced it locally with "
                "a large account, added a test that failed, and changed the query to load only the last 20 "
                "orders. As a result, the timeouts stopped and the 95th-percentile latency fell from 4 seconds "
                "to 300 milliseconds. I learned to start from evidence in the traces rather than my first guess.",
            ),
            Example("e-good-0", "Good debugging is finding the bug quickly and fixing it."),
        ),
    ),
)


def _id(*parts: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, ":".join(parts)))


# --- the target ---------------------------------------------------------------------------


def database_name(url: str) -> str:
    """The database's name: PostgreSQL's database, or a SQLite file's name."""
    parsed = make_url(url)
    name = parsed.database or ""
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def describe_target(url: str) -> str:
    """The target as it's shown before a reset: driver, host and name, never the password."""
    return make_url(url).render_as_string(hide_password=True)


def check_target(settings: Settings, db: Session, url: str, confirm: str | None) -> list[str]:
    """Why a reset of this database is refused (empty: it may go ahead). Reads only."""
    problems: list[str] = []
    name = database_name(url)
    if settings.environment == "production" and not settings.demo_mode:
        problems.append("this is a production server without DEMO_MODE=true: it isn't a demo")
    if "demo" not in name.lower():
        problems.append(f"the database's name must contain 'demo' (it's '{name or 'unnamed'}')")
    if confirm != name:
        problems.append(f"confirm the target by passing --confirm {name}")
    tables = set(inspect(db.get_bind()).get_table_names())
    if "users" in tables:
        users = db.scalar(select(func.count()).select_from(User)) or 0
        samples = (
            db.scalar(select(func.count()).select_from(User).where(User.auth_provider_id.startswith(MARKER)))
            or 0
        )
        with_email = db.scalar(select(func.count()).select_from(User).where(User.email.is_not(None))) or 0
        real = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_guest.is_(False), ~User.auth_provider_id.startswith(MARKER))
            )
            or 0
        )
        if with_email:
            problems.append(
                f"it holds {with_email} account(s) with an email address; a demo database never does"
            )
        elif users and not samples:
            problems.append(
                f"it holds {users} account(s) and none is a demo sample learner: not a demo database"
            )
        elif real:
            problems.append(f"it holds {real} account(s) that are neither guests nor sample learners")
    return problems


# --- the reset ----------------------------------------------------------------------------


def reset(db: Session) -> dict[str, int]:
    """Empty every table but the problem catalogue, then seed it and the sample learners.
    Idempotent: the same ids, times and grades every time. Returns rows per table afterwards."""
    for table in reversed(Base.metadata.sorted_tables):  # children before parents
        if table.name not in CONTENT_TABLES:
            db.execute(delete(table))
    db.commit()
    seed_problems(db)
    for persona in PERSONAS:
        user = User(
            id=_id("user", persona.key),
            auth_provider_id=f"{MARKER}{persona.key}",
            email=None,
            password_hash=None,  # can't sign in
            display_name=f"{persona.name} (fictional)",
            is_guest=False,
            career_track=persona.career_track,
            created_at=_SEEDED_AT,
        )
        db.add(user)
        db.flush()
        for n, example in enumerate(persona.examples):
            question = get_question(persona.career_track, example.question_id)
            if question is None:
                raise RuntimeError(
                    f"demo example question missing: {persona.career_track}/{example.question_id}"
                )
            answer = graded_answer(user.id, question, example.text)
            answer.id = _id("answer", persona.key, example.question_id)
            answer.created_at = _SEEDED_AT + timedelta(days=n + 1)
            db.add(answer)
    db.commit()
    return counts(db)


def counts(db: Session) -> dict[str, int]:
    return {t.name: db.scalar(select(func.count()).select_from(t)) or 0 for t in Base.metadata.sorted_tables}


def fingerprint(db: Session) -> str:
    """A digest of the starting state: rows per table and every sample answer as stored."""
    answers = db.scalars(
        select(PracticeAnswer)
        .where(PracticeAnswer.user_id.in_([_id("user", p.key) for p in PERSONAS]))
        .order_by(PracticeAnswer.id)
    ).all()
    state = {
        "counts": counts(db),
        "answers": [
            [a.id, a.user_id, a.question_id, a.answer, a.score, a.created_at.isoformat(), a.feedback]
            for a in answers
        ],
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def expected_counts() -> dict[str, int]:
    """After a reset: the catalogue, the sample learners and their answers, nothing else."""
    return {"users": len(PERSONAS), "practice_answers": sum(len(p.examples) for p in PERSONAS)}


def verify(db: Session) -> list[str]:
    """What's wrong with the state a reset left (empty: as expected)."""
    found = counts(db)
    wrong = [
        f"{table}: {n} rows, expected {expected_counts()[table]}"
        for table, n in found.items()
        if table in expected_counts() and n != expected_counts()[table]
    ]
    wrong += [
        f"{table}: {n} rows left, expected none"
        for table, n in found.items()
        if table not in CONTENT_TABLES and table not in expected_counts() and n
    ]
    if not found.get("problems"):
        wrong.append("problems: none seeded")
    return wrong


def run_reset(settings: Settings, engine: Engine, confirm: str | None, out=print) -> int:
    """The CLI's demo-reset: show the target, refuse before changing anything, reset, verify."""
    from app.db.session import make_session_factory

    url = settings.database_url
    out(f"Target: {describe_target(url)}")
    with make_session_factory(engine)() as db:
        refused = check_target(settings, db, url, confirm)
        if not refused and "users" not in inspect(engine).get_table_names():
            if not settings.auto_migrate:
                refused = ["the database has no tables: run `alembic upgrade head` first"]
            else:  # a new, empty demo database: create it as the API does at start-up
                from app.db import rls
                from app.db.dev_schema import add_missing_columns

                Base.metadata.create_all(engine)
                add_missing_columns(engine, Base.metadata)
                with engine.begin() as conn:
                    rls.apply(conn)
        if refused:
            out("Refused, nothing was changed:")
            for reason in refused:
                out(f"  - {reason}")
            return 2
        reset(db)
        problems = verify(db)
        if problems:
            out("The reset didn't leave the expected state (is this connection the database owner?):")
            for p in problems:
                out(f"  - {p}")
            return 1
        out(
            f"Demo database reset: {len(PERSONAS)} sample learners, {expected_counts()['practice_answers']} example answers."
        )
        out(f"Starting-state fingerprint: {fingerprint(db)}")
    return 0

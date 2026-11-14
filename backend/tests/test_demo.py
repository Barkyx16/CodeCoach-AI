"""The portfolio demo (Volume 7, prompt 10): a guarded, repeatable reset of a demo database, a
read-only fictional sample, no email, and visitors who can't see each other's work."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.db.session import make_engine, make_session_factory
from app.demo import EXAMPLE_LABEL, PERSONAS, check_target, counts, fingerprint, reset, run_reset
from app.models import Base, EmailJob, PracticeAnswer, RateLimitCounter, User
from tests.conftest import auth_headers

NURSE_ANSWER = (
    "Last winter, on a night shift, I noticed a patient's oxygen had dropped during my assessment. I was "
    "responsible for five patients. I rechecked his vital signs, started oxygen and called the rapid response "
    "team. As a result, he was stable within thirty minutes. I learned to escalate early."
)


def settings_for(url: str, **overrides) -> Settings:
    return Settings(
        database_url=url,
        environment=overrides.pop("environment", "development"),
        secret_key="demo-test-secret-key-that-is-long-enough-0123",
        _env_file=None,
        **overrides,
    )


@pytest.fixture
def demo_db(tmp_path):
    """A fresh SQLite demo database with the app's tables (as the API's start-up makes them)."""
    url = f"sqlite:///{tmp_path / 'codecoach-demo.db'}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    return url, engine


def run(url, engine, confirm, **overrides):
    lines: list[str] = []
    production = overrides.pop("environment", None) == "production"
    settings = settings_for(url, **overrides)
    if production:  # only the environment: the other production checks are tested elsewhere
        settings = settings.model_copy(update={"environment": "production"})
    code = run_reset(settings, engine, confirm, out=lines.append)
    return code, "\n".join(lines)


def users(engine) -> int:
    with make_session_factory(engine)() as db:
        return db.scalar(select(func.count()).select_from(User)) or 0


# --- the target ----------------------------------------------------------------------------


def test_the_target_is_shown_without_its_password_and_must_be_confirmed(demo_db):
    url, engine = demo_db
    code, out = run(url, engine, confirm=None)
    assert code == 2 and "Refused, nothing was changed" in out
    assert "confirm the target by passing --confirm codecoach-demo.db" in out
    assert out.splitlines()[0] == f"Target: {url}"
    pg = "postgresql+psycopg://demo_owner:s3cret-pass@db.internal:5432/codecoach_demo"
    with make_session_factory(engine)() as db:
        reasons = check_target(settings_for(pg), db, pg, confirm="codecoach_demo")
    assert reasons == []
    from app.demo import describe_target

    assert "s3cret-pass" not in describe_target(pg) and "codecoach_demo" in describe_target(pg)


def test_a_database_that_isnt_a_demo_is_refused_before_anything_changes(tmp_path):
    # A real-looking database: a registered account. Even renamed to look like a demo, it's refused.
    for name in ("codecoach.db", "codecoach-demo.db"):
        url = f"sqlite:///{tmp_path / name}"
        engine = make_engine(url)
        Base.metadata.create_all(engine)
        with make_session_factory(engine)() as db:
            person = User(
                email="real.person@example.com", auth_provider_id=f"password:{name}", password_hash="x"
            )
            db.add(person)
            db.flush()
            db.add(
                PracticeAnswer(
                    user_id=person.id,
                    track="registered-nurse",
                    question_id="e-good-0",
                    difficulty="easy",
                    answer="kept",
                    score=50,
                    feedback={},
                    provider="offline",
                )
            )
            db.commit()
        code, out = run(url, engine, confirm=name)
        assert code == 2
        assert "with an email address; a demo database never does" in out
        assert users(engine) == 1  # untouched
        with make_session_factory(engine)() as db:
            assert db.scalar(select(func.count()).select_from(PracticeAnswer)) == 1
    code, out = run(
        f"sqlite:///{tmp_path / 'codecoach.db'}",
        make_engine(f"sqlite:///{tmp_path / 'codecoach.db'}"),
        "codecoach.db",
    )
    assert "the database's name must contain 'demo' (it's 'codecoach.db')" in out


def test_accounts_without_the_sample_learners_mean_it_isnt_a_demo(demo_db):
    url, engine = demo_db
    with make_session_factory(engine)() as db:
        db.add(User(auth_provider_id="guest:someone", is_guest=True))
        db.commit()
    code, out = run(url, engine, confirm="codecoach-demo.db")
    assert code == 2 and "none is a demo sample learner: not a demo database" in out
    assert users(engine) == 1


def test_a_production_server_without_demo_mode_is_refused(demo_db):
    url, engine = demo_db
    code, out = run(url, engine, confirm="codecoach-demo.db", environment="production")
    assert code == 2 and "production server without DEMO_MODE=true" in out
    assert users(engine) == 0


# --- the reset -----------------------------------------------------------------------------


def test_reset_twice_gives_the_same_starting_state_and_clears_visitors(demo_db):
    url, engine = demo_db
    code, out = run(url, engine, confirm="codecoach-demo.db")
    assert code == 0, out
    first = out.splitlines()[-1]
    assert first.startswith("Starting-state fingerprint: ")
    with make_session_factory(engine)() as db:
        state = counts(db)
        assert state["users"] == len(PERSONAS) and state["practice_answers"] == 4 and state["problems"] > 0
        # A visitor's work, and a rate-limit counter, appear...
        visitor = User(auth_provider_id="guest:visitor-1", is_guest=True, career_track="registered-nurse")
        db.add(visitor)
        db.flush()
        db.add(
            PracticeAnswer(
                user_id=visitor.id,
                track="registered-nurse",
                question_id="e-good-0",
                difficulty="easy",
                answer="a visitor's private answer",
                score=40,
                feedback={},
                provider="offline",
            )
        )
        db.add(
            RateLimitCounter(
                key="auth:203.0.113.9",
                window=int(datetime.now(UTC).timestamp()) // 60,
                count=3,
                expires_at=int(datetime.now(UTC).timestamp()) + 120,
            )
        )
        db.commit()
    code, out = run(url, engine, confirm="codecoach-demo.db")
    assert code == 0, out
    assert out.splitlines()[-1] == first  # ...and the reset takes it back to the very same state
    with make_session_factory(engine)() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(PracticeAnswer)
                .where(PracticeAnswer.answer.like("%private%"))
            )
            == 0
        )
        assert db.scalar(select(func.count()).select_from(RateLimitCounter)) == 0
        sample = db.scalars(select(User).where(User.auth_provider_id.like("demo:sample-learner:%"))).all()
        assert all(
            u.email is None and u.password_hash is None and "(fictional)" in (u.display_name or "")
            for u in sample
        )


def test_the_fingerprint_changes_when_the_sample_changes(demo_db):
    url, engine = demo_db
    with make_session_factory(engine)() as db:
        reset(db)
        before = fingerprint(db)
        answer = db.scalars(select(PracticeAnswer)).first()
        assert answer is not None
        answer.score = answer.score + 1
        db.commit()
        assert fingerprint(db) != before


# --- the demo server -----------------------------------------------------------------------


def seeded(client) -> None:
    with client.app.state.session_factory() as db:
        reset(db)


def guest(client, career="registered-nurse") -> dict:
    r = client.post("/api/v1/auth/guest", json={"career_track": career, "display_name": "Demo visitor"})
    assert r.status_code == 201, r.text
    return auth_headers(r.json())


def test_not_a_demo_server_and_not_set_up(make_client):
    plain = make_client()
    assert plain.get("/api/v1/demo").status_code == 404
    assert plain.get("/api/v1/capabilities").json()["demo_mode"] is False
    demo = make_client(demo_mode=True)
    r = demo.get("/api/v1/demo")
    assert r.status_code == 503 and r.json()["error"]["code"] == "demo_not_set_up"


def test_the_sample_is_fictional_labelled_and_read_only(make_client):
    client = make_client(demo_mode=True)
    seeded(client)
    caps = client.get("/api/v1/capabilities").json()
    assert caps["demo_mode"] is True and caps["emails_delivered"] is False
    body = client.get("/api/v1/demo").json()
    assert [p["key"] for p in body["personas"]] == ["nurse", "engineer"]
    nurse = body["personas"][0]
    assert nurse["career_title"] == "Registered Nurse" and nurse["start_question_title"]
    assert len(nurse["examples"]) == 2 and all(e["label"] == EXAMPLE_LABEL for e in nurse["examples"])
    assert all(0 <= e["score"] <= 100 and e["summary"] for e in nurse["examples"])
    assert nurse["examples"][0]["score"] > nurse["examples"][1]["score"]  # a strong and a thin example
    assert any("fictional" in n for n in body["notes"])
    # The sample learners can't sign in.
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "sam.rivera@example.com", "password": "anything"}
        ).status_code
        == 401
    )


def test_a_demo_server_never_sends_email(make_client):
    client = make_client(demo_mode=True)
    seeded(client)
    h = guest(client)
    attempts = {
        "register": client.post(
            "/api/v1/auth/register", json={"email": "v@example.com", "password": "CorrectHorse42"}
        ),
        "upgrade": client.post(
            "/api/v1/auth/upgrade", headers=h, json={"email": "v@example.com", "password": "CorrectHorse42"}
        ),
        "reset": client.post("/api/v1/auth/password-reset", json={"email": "v@example.com"}),
        "resend": client.post("/api/v1/auth/verify-email/resend", headers=h),
        "email": client.post(
            "/api/v1/auth/email", headers=h, json={"email": "v@example.com", "password": "CorrectHorse42"}
        ),
    }
    for name, r in attempts.items():
        assert r.status_code == 403, (name, r.text)
        assert r.json()["error"]["code"] == "demo_mode", name
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(EmailJob)) == 0
        assert db.scalar(select(func.count()).select_from(User).where(User.email.is_not(None))) == 0


def test_two_demo_visitors_cant_see_each_others_work(make_client):
    client = make_client(demo_mode=True)
    seeded(client)
    first, second = guest(client), guest(client)
    q = "/api/v1/careers/registered-nurse/questions/e-time-0/answers"
    assert client.post(q, headers=first, json={"answer": NURSE_ANSWER}).status_code == 201
    iv = client.post("/api/v1/interviews", headers=first, json={"kind": "questions"}).json()
    assert client.get(q, headers=second).json() == []
    assert client.get(f"/api/v1/interviews/{iv['id']}", headers=second).status_code == 404
    assert client.get("/api/v1/me/activity", headers=second).json()["items"] == []
    assert len(client.get(q, headers=first).json()) == 1
    # And the shared sample is the same for both, and not anyone's own work.
    assert client.get("/api/v1/demo").json() == client.get("/api/v1/demo", headers=second).json()

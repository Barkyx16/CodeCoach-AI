"""Application factory. `uvicorn app.main:app --reload` serves the API on :8000;
interactive OpenAPI docs live at /docs (Swagger UI) and /redoc."""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes import (
    ai,
    answer_review,
    applications,
    auth,
    careers,
    content,
    drills,
    explore,
    health,
    interviews,
    kits,
    learn,
    me,
    meta,
    notes,
    onboarding,
    plan,
    problems,
    reflections,
    restore,
    scenarios,
    schedule,
    shares,
    stories,
    submissions,
    targets,
    telemetry,
    whiteboard,
)
from app.config import Settings, get_settings
from app.db import rls
from app.db.dev_schema import add_missing_columns
from app.db.seed import seed_problems
from app.db.session import Base, make_engine, make_session_factory
from app.errors import NotFoundError, install_error_handlers
from app.http_cache import CacheMiddleware, ResponseCache
from app.jobs import JobsRunner
from app.metrics import Metrics
from app.observability import RequestContextMiddleware, configure_logging
from app.services.ai.service import build_provider
from app.services.email import build_email_sender
from app.services.judge.backends import build_backend
from app.services.judge.health import ExecutionHealth
from app.services.rate_limit import DatabaseRateLimiter, SlidingWindowLimiter
from app.tracing import TraceStore

logger = logging.getLogger("codecoach.app")

API_DESCRIPTION = """
CodeCoach AI: practice Java interview problems with a deterministic judge and an AI coach.

**Auth:** send `Authorization: Bearer <access_token>`. Get a token from
`POST /api/v1/auth/register`, `POST /api/v1/auth/login` or `POST /api/v1/auth/guest`.

**Errors:** every non-2xx response is `{"error": {"code", "message", "request_id", "details"}}`.
Branch on `error.code`, not on the message text.

**Correctness:** pass/fail comes only from the test judge. AI feedback is advisory.
"""

TAGS = [
    {"name": "health", "description": "Liveness and readiness probes"},
    {"name": "auth", "description": "Registration, login, guest sessions and token revocation"},
    {"name": "problems", "description": "Curated problem library. Hidden tests are never exposed."},
    {"name": "submissions", "description": "Asynchronous judging jobs and attempt history"},
    {"name": "ai coach", "description": "Progressive hints, structured code reviews, budgets and history"},
    {"name": "interviews", "description": "Timed mock interviews with an AI interviewer and rubric feedback"},
    {"name": "progress", "description": "Analytics and personalized recommendations"},
    {
        "name": "content quality",
        "description": "Content metadata and trust labels, issue reports, and admin triage (corrections, "
        "retirement). Admin routes answer 404 to everyone who isn't an admin.",
    },
    {
        "name": "onboarding",
        "description": "The optional first-session introduction: the learner's choices about it and a real "
        "starter activity for their career. Records no answer text and no practice progress.",
    },
    {
        "name": "stories",
        "description": "The story bank: your own STAR stories, private to you, with every saved version kept. "
        "Writing help is built-in rules (never AI) and changes nothing until you accept it.",
    },
    {
        "name": "applications",
        "description": "A private tracker of real applications as you record them: stages with history, "
        "interview events with exact times, links to targets and stories. Nothing is sent or submitted.",
    },
    {
        "name": "schedule",
        "description": "Existing activities on dates and times you choose, in your time zone, with .ics files. "
        "Scheduling isn't doing; nothing is sent, and reminders exist only inside an open tab.",
    },
    {
        "name": "drills",
        "description": "Short communication drills with career-aware prompts. Feedback describes what's in the "
        "learner's words; measurements are only what was measured; nothing rewards speed.",
    },
    {
        "name": "whiteboard",
        "description": "System-design practice with a small, plain-text diagram: drafts with conflict-safe saves, "
        "attempts frozen with their prompt and rubric versions, and feedback that names the elements it found.",
    },
    {
        "name": "backup",
        "description": "Restore your own notes, stories, bookmarks and applications from a CodeCoach backup: "
        "previewed first, additive only, never trusting ids, roles or results in the file, and removable later.",
    },
    {
        "name": "sharing",
        "description": "Share a chosen answer with a reviewer through an unlisted, revocable link; "
        "collect their structured feedback. The link secret travels in request bodies, never URLs.",
    },
]


def _judge_queue_state(session_factory) -> tuple[int, float]:
    from app.worker import judge_queue_state

    return judge_queue_state(session_factory)


def _start_embedded_worker(settings: Settings, session_factory, traces=None, metrics=None):
    import threading

    from app.services.judge.runner_client import HttpRunner
    from app.worker import JudgeWorker

    assert settings.runner_token is not None
    worker = JudgeWorker(
        session_factory,
        HttpRunner(settings.runner_url, settings.runner_token_value),
        settings,
        traces,
        metrics,
    )
    threading.Thread(target=worker.run_forever, name="judge-worker", daemon=True).start()
    logger.info("embedded judge worker started")
    return worker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(getattr(logging, settings.log_level.upper(), logging.INFO))

    engine = make_engine(
        settings.database_url,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_migrate:
            # Dev convenience. Production: `alembic upgrade head` + `python -m app.cli seed`.
            Base.metadata.create_all(engine)
            add_missing_columns(engine, Base.metadata)  # a database an older run made
            with engine.begin() as conn:
                rls.apply(conn)  # PostgreSQL row-level security, as the migration sets it up
            with session_factory() as session:
                seed_problems(session)
        rls.warn_if_not_enforced(engine, production=settings.environment == "production")
        if settings.email_backend != "smtp":
            logger.warning(
                "email is NOT sent: EMAIL_BACKEND=%s %s messages instead (docs/EMAIL.md)",
                settings.email_backend,
                "prints" if settings.email_backend == "console" else "saves",
            )
        worker = None
        if settings.execution_enabled and settings.embedded_worker:
            worker = _start_embedded_worker(settings, session_factory, app.state.traces, app.state.metrics)
        jobs = None
        if settings.background_jobs_in_api:
            jobs = JobsRunner(session_factory, settings, app.state.email_sender).start()
        logger.info("startup complete")
        yield
        if jobs is not None:
            jobs.stop()
        if worker is not None:
            worker.stop()
        engine.dispose()

    app = FastAPI(
        title="CodeCoach AI API",
        version="0.1.0",
        description=API_DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.ai_provider = build_provider(settings)
    app.state.execution_backend = build_backend(settings)
    app.state.execution_health = ExecutionHealth(settings)
    app.state.email_sender = build_email_sender(settings)
    app.state.auth_limiter = (
        DatabaseRateLimiter(session_factory, settings.auth_rate_limit_per_minute, 60)
        if settings.rate_limit_backend == "database"
        else SlidingWindowLimiter(settings.auth_rate_limit_per_minute, 60.0)
    )
    app.state.practice_limiter = (
        DatabaseRateLimiter(session_factory, settings.practice_answers_per_hour, 3600)
        if settings.rate_limit_backend == "database"
        else SlidingWindowLimiter(settings.practice_answers_per_hour, 3600.0)
    )

    def limiter(limit: int, window_s: int) -> DatabaseRateLimiter | SlidingWindowLimiter:
        if settings.rate_limit_backend == "database":
            return DatabaseRateLimiter(session_factory, limit, window_s)
        return SlidingWindowLimiter(limit, float(window_s))

    app.state.login_failure_limiter = limiter(settings.login_failures_per_account, 900)
    app.state.refresh_limiter = limiter(settings.refresh_rate_limit_per_minute, 60)
    app.state.export_limiter = limiter(settings.exports_per_hour, 3600)
    app.state.restore_limiter = limiter(settings.restores_per_hour, 3600)
    app.state.share_open_limiter = limiter(settings.share_opens_per_10_minutes, 600)
    app.state.share_feedback_limiter = limiter(settings.share_feedback_per_hour, 3600)
    app.state.share_create_limiter = limiter(settings.shares_created_per_hour, 3600)
    app.state.report_limiter = limiter(settings.content_reports_per_hour, 3600)
    app.state.telemetry_limiter = SlidingWindowLimiter(120, 600.0)  # per account: 120 batches / 10 min
    app.state.metrics = Metrics() if settings.metrics_enabled else None
    app.state.traces = (
        TraceStore(settings.trace_store_max_traces, ttl_seconds=settings.trace_store_ttl_seconds)
        if settings.trace_store_max_traces
        else None
    )
    if app.state.metrics is not None:
        app.state.metrics.queue_probe = lambda: _judge_queue_state(session_factory)

    install_error_handlers(app)
    # Innermost: caching of the public catalogue and no-store for everything else (app/http_cache.py).
    app.state.response_cache = ResponseCache()
    app.add_middleware(
        CacheMiddleware, cache=app.state.response_cache, ttl=settings.response_cache_ttl_seconds
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Credentials only matter for the refresh cookie (HttpOnly, SameSite=Strict, path-scoped to
        # /api/v1/auth); everything else authenticates with the in-memory bearer token.
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Requested-With",
            "X-Refresh-Attempt",
            "traceparent",
        ],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
        max_age=600,
    )

    for router in (
        health.router,
        auth.router,
        problems.router,
        careers.router,
        content.router,
        content.admin_router,
        explore.router,
        learn.router,
        notes.router,
        onboarding.router,
        scenarios.router,
        shares.me_router,
        shares.public_router,
        stories.router,
        applications.router,
        kits.router,
        restore.router,
        reflections.router,
        answer_review.router,
        drills.router,
        whiteboard.router,
        schedule.router,
        submissions.router,
        ai.router,
        interviews.router,
        me.router,
        plan.router,
        targets.router,
        meta.router,
        telemetry.router,
    ):
        app.include_router(router)

    if app.state.metrics is not None:

        @app.get("/metrics", include_in_schema=False)
        def metrics(request: Request) -> Response:
            if settings.metrics_token is not None:
                expected = f"Bearer {settings.metrics_token.get_secret_value()}".encode()
                given = request.headers.get("authorization", "").encode()
                if not hmac.compare_digest(given, expected):
                    raise NotFoundError("Not Found")
            return Response(app.state.metrics.render(), media_type=app.state.metrics.content_type)

    return app


app = create_app()

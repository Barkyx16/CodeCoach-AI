"""Application factory. `uvicorn app.main:app --reload` serves the API on :8000;
interactive OpenAPI docs live at /docs (Swagger UI) and /redoc."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes import (
    ai,
    auth,
    careers,
    explore,
    health,
    interviews,
    learn,
    me,
    meta,
    plan,
    problems,
    submissions,
    targets,
)
from app.config import Settings, get_settings
from app.db.seed import seed_problems
from app.db.session import Base, make_engine, make_session_factory
from app.errors import install_error_handlers
from app.metrics import Metrics
from app.observability import RequestContextMiddleware, configure_logging
from app.services.ai.service import build_provider
from app.services.email import build_email_sender
from app.services.judge.backends import build_backend
from app.services.rate_limit import DatabaseRateLimiter, SlidingWindowLimiter

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
]


def _start_embedded_worker(settings: Settings, session_factory):
    import threading

    from app.services.judge.runner_client import HttpRunner
    from app.worker import JudgeWorker

    assert settings.runner_token is not None
    worker = JudgeWorker(session_factory, HttpRunner(settings.runner_url, settings.runner_token), settings)
    threading.Thread(target=worker.run_forever, name="judge-worker", daemon=True).start()
    logger.info("embedded judge worker started")
    return worker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(getattr(logging, settings.log_level.upper(), logging.INFO))

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_migrate:
            # Dev convenience. Production: `alembic upgrade head` + `python -m app.cli seed`.
            Base.metadata.create_all(engine)
            with session_factory() as session:
                seed_problems(session)
        worker = None
        if settings.execution_enabled and settings.embedded_worker:
            worker = _start_embedded_worker(settings, session_factory)
        logger.info("startup complete")
        yield
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
    app.state.metrics = Metrics() if settings.metrics_enabled else None

    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Credentials only matter for the refresh cookie (HttpOnly, SameSite=Strict, path-scoped to
        # /api/v1/auth); everything else authenticates with the in-memory bearer token.
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Requested-With"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    for router in (
        health.router,
        auth.router,
        problems.router,
        careers.router,
        explore.router,
        learn.router,
        submissions.router,
        ai.router,
        interviews.router,
        me.router,
        plan.router,
        targets.router,
        meta.router,
    ):
        app.include_router(router)

    if app.state.metrics is not None:

        @app.get("/metrics", include_in_schema=False)
        def metrics() -> Response:
            return Response(app.state.metrics.render(), media_type=app.state.metrics.content_type)

    return app


app = create_app()

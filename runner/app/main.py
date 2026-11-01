"""Runner HTTP API. Called only by the CodeCoach API/worker over a private network.

POST /v1/run   compile + run one submission in a fresh sandbox (bearer-token protected)
GET  /health   liveness (no details)
"""

from __future__ import annotations

import hmac
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import RunnerSettings, get_settings
from app.sandbox import DockerSandbox, cleanup_stale
from app.schemas import RunRequest, RunResponse

logger = logging.getLogger("runner")
_bearer = HTTPBearer(auto_error=False)


def create_app(
    settings: RunnerSettings | None = None, sandbox: DockerSandbox | None = None, cleanup: bool = True
) -> FastAPI:
    settings = settings or get_settings()
    sandbox = sandbox or DockerSandbox(settings)
    slots = threading.BoundedSemaphore(settings.max_concurrency)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if cleanup:
            removed = cleanup_stale(settings)
            if removed:
                logger.warning("removed %d stale sandbox containers", removed)
        yield

    app = FastAPI(
        title="CodeCoach Runner",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )  # private service: no public docs

    def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
        token = credentials.credentials if credentials else ""
        if not hmac.compare_digest(token.encode(), settings.runner_token.encode()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/run", response_model=RunResponse, dependencies=[Depends(authorize)])
    def run(body: RunRequest, request: Request) -> RunResponse:
        for name, src in body.files.items():
            if len(src.encode("utf-8")) > settings.max_source_bytes:
                raise HTTPException(status_code=413, detail=f"{name} is too large")
        # Never queue unboundedly inside the runner: the API's worker retries later instead.
        if not slots.acquire(timeout=1.0):
            raise HTTPException(status_code=503, detail="runner at capacity")
        try:
            result = sandbox.run(body.files, body.nonce, body.time_limit_s)
        finally:
            slots.release()
        logger.info(
            "run finished status=%s exit=%s ms=%d", result.status, result.exit_code, result.duration_ms
        )
        return RunResponse(**result.__dict__)

    return app


def app_factory() -> FastAPI:
    """Entry point: `uvicorn app.main:app_factory --factory` (reads settings from the environment)."""
    logging.basicConfig(level=logging.INFO)
    return create_app()

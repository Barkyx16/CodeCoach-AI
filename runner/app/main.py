"""Runner HTTP API. Called only by the CodeCoach API/worker over a private network.

POST /v1/run   compile + run one submission in a fresh sandbox (bearer-token protected)
GET  /health   liveness (no details)
"""

from __future__ import annotations

import hmac
import logging
import threading
import time
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import RunnerSettings, get_settings
from app.sandbox import DockerSandbox, cleanup_stale, docker_reachable
from app.schemas import RunRequest, RunResponse

logger = logging.getLogger("runner")
_bearer = HTTPBearer(auto_error=False)

WARMUP_FILES = {
    "Solution.java": "class Solution { int ping() { return 1; } }\n",
    "Main.java": "public final class Main {\n"
    "    public static void main(String[] args) { System.out.println(new Solution().ping()); }\n}\n",
}


def warm_up(sandbox: DockerSandbox, settings: RunnerSettings) -> str:
    """One trivial compile + run, so the cold start isn't charged to a learner's time limit."""
    start = time.perf_counter()
    try:
        result = sandbox.run(WARMUP_FILES, "warmup", settings.wall_timeout_s)
    except Exception as exc:  # noqa: BLE001 - a failed warm-up must never stop the runner starting
        logger.warning("sandbox warm-up failed: %s", exc)
        return "error"
    logger.info(
        "sandbox warm-up status=%s in %d ms", result.status, int((time.perf_counter() - start) * 1000)
    )
    return result.status


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
        if settings.warmup_on_start:
            # Before serving: the container orchestrator only routes work once startup completes.
            await anyio.to_thread.run_sync(warm_up, sandbox, settings)
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

    @app.get("/ready")
    def ready() -> JSONResponse:
        """Can this runner actually start sandboxes? Checks the Docker daemon (no details leak)."""
        ok = docker_reachable(settings)
        return JSONResponse(status_code=200 if ok else 503, content={"status": "ok" if ok else "unavailable"})

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

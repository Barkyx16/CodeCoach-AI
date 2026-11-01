from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    """Is the process up? Deliberately reveals nothing about versions or infrastructure."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (checks the database)")
def ready(request: Request, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means "not ready"
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "checks": {"database": "fail"}}
        )
    return {"status": "ok", "checks": {"database": "ok"}}

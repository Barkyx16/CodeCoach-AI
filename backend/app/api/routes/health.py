from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter(tags=["health"])
BACKEND = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _revisions() -> tuple[frozenset[str], frozenset[str]] | None:
    """This code's migration heads and every revision it knows (from its own migrations folder)."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "migrations"))
        script = ScriptDirectory.from_config(cfg)
        return frozenset(script.get_heads()), frozenset(r.revision for r in script.walk_revisions())
    except Exception:  # noqa: BLE001 - without its migrations the code can't judge the schema
        return None


def schema_state(db: Session) -> str:
    """How the database's migration revision relates to this code:
    current (at this code's head), behind (an older revision this code knows: migrate first),
    newer (a revision this code doesn't know, e.g. after an application revert onto an expanded
    schema), unmanaged (no migration ledger: tables made by create_all in development and tests),
    unknown (this code's migrations couldn't be read)."""
    if not inspect(db.get_bind()).has_table("alembic_version"):
        return "unmanaged"
    known = _revisions()
    if known is None:
        return "unknown"
    heads, everything = known
    at = {row[0] for row in db.execute(text("SELECT version_num FROM alembic_version"))}
    if at and at <= heads:
        return "current"
    if at and at <= everything:
        return "behind"
    return "newer"


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    """Is the process up? Deliberately reveals nothing about versions or infrastructure."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (checks the database and its schema)")
def ready(request: Request, db: Session = Depends(get_db)):
    """Ready when the database answers and its schema isn't older than this code needs. Names no
    revision: only whether the schema is current, behind, newer or unmanaged."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means "not ready"
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "checks": {"database": "fail"}}
        )
    schema = schema_state(db)
    if schema == "behind":  # this code would fail on columns the migration hasn't added yet
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": {"database": "ok", "schema": "behind"}},
        )
    return {"status": "ok", "checks": {"database": "ok", "schema": schema}}

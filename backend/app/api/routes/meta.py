"""What this deployment can do, so clients can show only features that work here."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import APIModel
from app.services.judge.health import MESSAGES, SETUP_HELP

router = APIRouter(prefix="/api/v1", tags=["meta"])


class ExecutionStatus(APIModel):
    state: Literal["ready", "unavailable", "not_configured"]
    reason: Literal[
        "ok", "not_configured", "judge_unreachable", "judge_not_ready", "judge_misconfigured", "queue_delayed"
    ]
    message: str = Field(description="What this means for the learner, in plain words")
    run_available: bool = Field(description="Run (public tests only) can be used right now")
    submit_mode: Literal["judged", "queued_until_available", "saved_only"] = Field(
        description="judged: verdict follows; queued_until_available: judged when the judge is back; "
        "saved_only: no judge on this deployment, attempts are saved without a verdict"
    )
    checked_at: datetime
    setup_help: str | None = Field(description="Development only: how to connect a judge")


class Capabilities(APIModel):
    execution_enabled: bool = Field(
        description="Submissions are judged and `mode: run` is available. When false, submissions "
        "are saved but not run, and runs are refused with 503 `execution_disabled`."
    )
    ai_provider: Literal["offline", "anthropic"] = Field(description="Which AI coach answers by default")
    execution: ExecutionStatus
    guest_retention_days: int = Field(
        description="Guest accounts inactive this long are deleted with their data (0: kept forever)"
    )


@router.get("/capabilities", response_model=Capabilities, summary="Features available on this deployment")
def capabilities(request: Request, db: Session = Depends(get_db)) -> Capabilities:
    # Deliberately coarse: no versions, hostnames, model names, limits or error details.
    settings = request.app.state.settings
    provider = request.app.state.ai_provider.name
    state, reason, checked_at = request.app.state.execution_health.check(db)
    return Capabilities(
        execution_enabled=request.app.state.execution_backend.enabled,
        ai_provider="anthropic" if provider == "anthropic" else "offline",
        execution=ExecutionStatus(
            state=state,
            reason=reason,
            message=MESSAGES[reason],
            run_available=state == "ready" or reason == "queue_delayed",
            submit_mode="judged"
            if state == "ready"
            else "saved_only"
            if state == "not_configured"
            else "queued_until_available",
            checked_at=checked_at,
            setup_help=None if settings.environment == "production" else SETUP_HELP.get(reason),
        ),
        guest_retention_days=settings.guest_retention_days,
    )

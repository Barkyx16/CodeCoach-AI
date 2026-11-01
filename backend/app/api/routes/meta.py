"""What this deployment can do, so clients can show only features that work here."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import Field

from app.schemas.common import APIModel

router = APIRouter(prefix="/api/v1", tags=["meta"])


class Capabilities(APIModel):
    execution_enabled: bool = Field(
        description="Submissions are judged and `mode: run` is available. When false, submissions "
        "are saved but not run, and runs are refused with 503 `execution_disabled`."
    )
    ai_provider: Literal["offline", "anthropic"] = Field(description="Which AI coach answers by default")


@router.get("/capabilities", response_model=Capabilities, summary="Features available on this deployment")
def capabilities(request: Request) -> Capabilities:
    # Deliberately coarse: no versions, hostnames, model names or limits.
    provider = request.app.state.ai_provider.name
    return Capabilities(
        execution_enabled=request.app.state.execution_backend.enabled,
        ai_provider="anthropic" if provider == "anthropic" else "offline",
    )

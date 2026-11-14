"""What this deployment can do, so clients can show only features that work here."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.errors import AppError, NotFoundError
from app.schemas.common import APIModel
from app.services.judge.health import MESSAGES, SETUP_HELP

router = APIRouter(prefix="/api/v1", tags=["meta"])


class DemoNotSetUp(AppError):
    status_code = 503
    code = "demo_not_set_up"


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
    ui_telemetry: bool = Field(
        default=False,
        description="The app may report how its round actions ended (outcome and timing only) to "
        "POST /api/v1/telemetry/ui",
    )
    emails_delivered: bool = Field(
        default=True,
        description="False on a development server with no mail server set up: emails (verification "
        "codes, reset links) are printed in the server's terminal instead of being sent. Always true in "
        "production, which refuses to start without one.",
    )
    answer_request_keys: bool = Field(
        default=False,
        description="Career answers accept `client_request_id`, and this server keeps at most one saved "
        "answer per account and key (a resend returns the saved answer). Absent or false (older "
        "servers): a key is ignored, so it promises nothing.",
    )
    demo_mode: bool = Field(
        default=False,
        description="A portfolio demo with fictional data (GET /api/v1/demo): visitors use guest "
        "sessions, and nothing that sends email is available.",
    )


class DemoExample(APIModel):
    question_id: str
    question_title: str
    answer: str
    score: int
    rating: str
    summary: str
    answered_at: datetime
    label: str = Field(description="Says what this is: an example written for the demo, and who graded it")


class DemoPersona(APIModel):
    key: str
    name: str = Field(description="A fictional learner's name")
    career_track: str
    career_title: str
    summary: str
    start_question_id: str
    start_question_title: str
    problem_slug: str | None = None
    examples: list[DemoExample]


class DemoOut(APIModel):
    personas: list[DemoPersona]
    notes: list[str]


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
        ui_telemetry=settings.ui_telemetry_enabled,
        emails_delivered=settings.email_backend == "smtp" and not settings.demo_mode,
        answer_request_keys=True,
        demo_mode=settings.demo_mode,
    )


@router.get(
    "/demo",
    response_model=DemoOut,
    summary="The demo's fictional sample learners and their example answers (demo servers only)",
    responses={404: {"description": "Not a demo server"}, 503: {"description": "Demo not set up"}},
)
def demo(request: Request, db: Session = Depends(get_db)) -> DemoOut:
    """A read-only sample, the same for every visitor; each visitor's own work is in their own
    guest session. Only the sample learners' rows are read."""
    from sqlalchemy import select

    from app.careers import CATALOG
    from app.careers.questions import get_question
    from app.db import rls
    from app.demo import EXAMPLE_LABEL, MARKER, PERSONAS
    from app.models import PracticeAnswer, User

    if not request.app.state.settings.demo_mode:
        raise NotFoundError("This server isn't running the demo.")
    out: list[DemoPersona] = []
    with rls.maintenance(db, "demo: the fictional sample learners' example answers"):
        for persona in PERSONAS:
            user = db.scalar(select(User).where(User.auth_provider_id == f"{MARKER}{persona.key}"))
            if user is None:
                raise DemoNotSetUp("The demo isn't set up yet: run python -m app.cli demo-reset.")
            answers = db.scalars(
                select(PracticeAnswer)
                .where(PracticeAnswer.user_id == user.id)
                .order_by(PracticeAnswer.created_at)
            ).all()
            start = get_question(persona.career_track, persona.start_question_id)
            out.append(
                DemoPersona(
                    key=persona.key,
                    name=persona.name,
                    career_track=persona.career_track,
                    career_title=CATALOG[persona.career_track].title,
                    summary=persona.summary,
                    start_question_id=persona.start_question_id,
                    start_question_title=start.title if start else persona.start_question_id,
                    problem_slug=persona.problem_slug,
                    examples=[
                        DemoExample(
                            question_id=a.question_id,
                            question_title=(
                                q.title if (q := get_question(a.track, a.question_id)) else a.question_id
                            ),
                            answer=a.answer,
                            score=a.score,
                            rating=str((a.feedback or {}).get("rating", "")),
                            summary=str((a.feedback or {}).get("summary", "")),
                            answered_at=a.created_at,
                            label=EXAMPLE_LABEL,
                        )
                        for a in answers
                    ],
                )
            )
    return DemoOut(
        personas=out,
        notes=[
            "Everyone here is fictional. Your own session is a guest session that only you can see.",
            "No email is sent from this demo, and accounts can't be created here.",
        ],
    )

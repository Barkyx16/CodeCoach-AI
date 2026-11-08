"""Whiteboard practice: drafts with conflict-safe saves, and attempts frozen with their feedback."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.locking import lock_for_update
from app.errors import AppError, ConflictError, NotFoundError
from app.models import User, WhiteboardAttempt, WhiteboardDraft
from app.schemas.whiteboard import (
    WhiteboardAttemptIn,
    WhiteboardAttemptOut,
    WhiteboardAttemptSummary,
    WhiteboardDraftIn,
    WhiteboardDraftOut,
    WhiteboardPrompt,
    WhiteboardPromptList,
    WhiteboardPromptRequirement,
)
from app.whiteboard import BY_ID, PROMPTS, RUBRIC_VERSION, Prompt, prompts_for
from app.whiteboard.diagram import Diagram, digest, evaluate

MIN_EXPLANATION_WORDS = 15
MAX_ATTEMPTS = 50


def prompt_out(p: Prompt) -> WhiteboardPrompt:
    return WhiteboardPrompt(
        id=p.id,
        version=p.version,
        title=p.title,
        objective=p.objective,
        brief=p.brief,
        requirements=[WhiteboardPromptRequirement(id=r.id, text=r.text) for r in p.requirements],
    )


class Whiteboard:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def prompts(self) -> WhiteboardPromptList:
        mine = prompts_for(self.user.career_track)
        if mine:
            return WhiteboardPromptList(
                prompts=[prompt_out(p) for p in mine],
                note="System-design prompts for careers that write code.",
            )
        return WhiteboardPromptList(
            prompts=[prompt_out(p) for p in PROMPTS],
            note="Whiteboard practice covers system design for software careers only. Process maps for other careers aren't offered "
            "until reviewed content exists; these prompts are open to anyone curious.",
        )

    def _prompt(self, prompt_id: str) -> Prompt:
        p = BY_ID.get(prompt_id)
        if p is None:
            raise NotFoundError("Prompt not found")
        return p

    def _last_digest(self, prompt_id: str) -> str | None:
        return self.db.scalar(
            select(WhiteboardAttempt.digest)
            .where(WhiteboardAttempt.user_id == self.user.id, WhiteboardAttempt.prompt_id == prompt_id)
            .order_by(WhiteboardAttempt.created_at.desc())
            .limit(1)
        )

    def draft(self, prompt_id: str) -> WhiteboardDraftOut:
        self._prompt(prompt_id)
        row = self.db.get(WhiteboardDraft, (self.user.id, prompt_id))
        diagram = Diagram.model_validate(row.diagram) if row else Diagram()
        last = self._last_digest(prompt_id)
        return WhiteboardDraftOut(
            prompt_id=prompt_id,
            diagram=diagram,
            explanation=row.explanation if row else "",
            revision=row.revision if row else 0,
            updated_at=row.updated_at if row else None,
            differs_from_last_attempt=last is not None and last != digest(diagram),
        )

    def save_draft(self, prompt_id: str, body: WhiteboardDraftIn) -> WhiteboardDraftOut:
        self._prompt(prompt_id)
        row = lock_for_update(self.db, self.db.get(WhiteboardDraft, (self.user.id, prompt_id)))
        current = row.revision if row else 0
        if body.expected_revision != current:
            raise ConflictError(
                "This diagram was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                # The saved version itself, so the page can show both and let the learner choose.
                details={
                    "current_revision": current,
                    "current": self.draft(prompt_id).model_dump(mode="json"),
                },
            )
        if row is None:
            row = WhiteboardDraft(
                user_id=self.user.id, prompt_id=prompt_id, diagram={}, explanation="", revision=0
            )
            self.db.add(row)
        row.diagram = body.diagram.model_dump()
        row.explanation = body.explanation.strip()
        row.revision = current + 1
        row.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except IntegrityError:  # two first saves at once: the other one created the draft
            self.db.rollback()
            saved = self.draft(prompt_id)
            raise ConflictError(
                "This diagram was saved somewhere else since you opened it. Your changes are still on this page.",
                code="stale_revision",
                details={"current_revision": saved.revision, "current": saved.model_dump(mode="json")},
            ) from None
        return self.draft(prompt_id)

    def attempt(self, prompt_id: str, body: WhiteboardAttemptIn) -> WhiteboardAttemptOut:
        p = self._prompt(prompt_id)
        if len(re.findall(r"\w+", body.explanation)) < MIN_EXPLANATION_WORDS:
            raise AppError(
                f"Explain at least one decision in your own words first (about {MIN_EXPLANATION_WORDS} words or more).",
                code="explanation_required",
            )
        # An empty diagram is allowed: the explanation alone gets feedback, and the checks say the
        # diagram is empty. That keeps a words-only answer possible.
        n = (
            self.db.scalar(
                select(func.count())
                .select_from(WhiteboardAttempt)
                .where(WhiteboardAttempt.user_id == self.user.id)
            )
            or 0
        )
        if n >= MAX_ATTEMPTS * len(PROMPTS):
            raise AppError("You've reached the limit of saved attempts.", code="too_many_attempts")
        a = WhiteboardAttempt(
            user_id=self.user.id,
            prompt_id=p.id,
            prompt_version=p.version,
            rubric_version=RUBRIC_VERSION,
            diagram=body.diagram.model_dump(),
            digest=digest(body.diagram),
            explanation=body.explanation.strip(),
            feedback=evaluate(p, body.diagram, body.explanation),
        )
        self.db.add(a)
        self.db.commit()
        return self._out(a)

    def _out(self, a: WhiteboardAttempt) -> WhiteboardAttemptOut:
        return WhiteboardAttemptOut(
            id=a.id,
            prompt_id=a.prompt_id,
            prompt_version=a.prompt_version,
            rubric_version=a.rubric_version,
            diagram=Diagram.model_validate(a.diagram),
            digest=a.digest,
            explanation=a.explanation,
            feedback=a.feedback,
            created_at=a.created_at,
        )

    def attempts(self, prompt_id: str) -> list[WhiteboardAttemptSummary]:
        self._prompt(prompt_id)
        rows = self.db.scalars(
            select(WhiteboardAttempt)
            .where(WhiteboardAttempt.user_id == self.user.id, WhiteboardAttempt.prompt_id == prompt_id)
            .order_by(WhiteboardAttempt.created_at.desc())
        ).all()
        return [
            WhiteboardAttemptSummary(
                id=a.id,
                prompt_version=a.prompt_version,
                rubric_version=a.rubric_version,
                digest=a.digest,
                addressed=sum(1 for r in a.feedback.get("rubric", []) if r.get("addressed")),
                total=len(a.feedback.get("rubric", [])),
                created_at=a.created_at,
            )
            for a in rows
        ]

    def get_attempt(self, attempt_id: str) -> WhiteboardAttemptOut:
        a = self.db.get(WhiteboardAttempt, attempt_id)
        if a is None or a.user_id != self.user.id:
            raise NotFoundError("Attempt not found")
        return self._out(a)

    def export(self) -> dict:
        return {
            "drafts": [
                {
                    "prompt": d.prompt_id,
                    "diagram": d.diagram,
                    "explanation": d.explanation,
                    "revision": d.revision,
                }
                for d in self.db.scalars(
                    select(WhiteboardDraft).where(WhiteboardDraft.user_id == self.user.id)
                )
            ],
            "attempts": [
                {
                    "prompt": a.prompt_id,
                    "prompt_version": a.prompt_version,
                    "rubric_version": a.rubric_version,
                    "diagram": a.diagram,
                    "explanation": a.explanation,
                    "feedback": a.feedback,
                    "created_at": a.created_at.isoformat(),
                }
                for a in self.db.scalars(
                    select(WhiteboardAttempt).where(WhiteboardAttempt.user_id == self.user.id)
                )
            ],
        }

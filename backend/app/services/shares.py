"""Share an answer with a trusted reviewer through an unlisted link, and collect their feedback.

Security model (docs/SHARING.md):
- The link carries a 256-bit random secret (`secrets.token_urlsafe(32)`) in the URL *fragment*
  (`/shared#t=…`), which browsers never send to servers or in Referer headers. The page posts it
  in a request body, so it never appears in access logs, which record the path only.
- Only its SHA-256 is stored. A lost link can be replaced (which kills the old one), never shown
  again. Sequential or guessable ids are never used to grant access.
- What a reviewer sees is a snapshot the owner chose and previewed: selected sentences of one
  answer, optionally a follow-up and the automated feedback, and an optional note. No account
  details, history, goals, notes, targets or audio.
- Revoking or expiry is checked on every request; responses are `no-store` so nothing can be
  replayed from a cache.
- Feedback is from a person and stays separate: it never changes the answer, scores, plan or
  progress.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.careers import CATALOG
from app.careers.questions import get_question
from app.errors import AppError, ConflictError, GoneError, NotFoundError
from app.models import (
    InterviewStatus,
    InterviewTurn,
    PracticeAnswer,
    PracticeSession,
    Share,
    ShareFeedback,
    User,
)
from app.schemas.shares import (
    FeedbackCommentOut,
    FeedbackIn,
    FeedbackOut,
    FeedbackReceipt,
    RecipientView,
    ReviewerIdentity,
    ShareCreate,
    ShareCreated,
    SharedAIFeedback,
    ShareDetail,
    SharedFollowup,
    SharedPoint,
    SharedQuestion,
    SharedSentence,
    SharedView,
    SharePreview,
    ShareSelection,
    ShareStatus,
    ShareSummary,
)

PROMPTS = ["What was clear?", "What needs more evidence?", "One useful next step"]
MAX_ACTIVE_SHARES = 50
MAX_FEEDBACK_PER_SHARE = 30
SNAPSHOT_VERSION = 1

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _now() -> datetime:
    return datetime.now(UTC)


def split_sentences(text: str) -> list[str]:
    """Deterministic sentence split: the indices are the stable anchors comments refer to."""
    return [part.strip() for part in _SENTENCE_BREAK.split(text.strip()) if part.strip()]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _clean(text: str) -> str:
    """Plain text only (rendered as text, never HTML); control characters removed."""
    return _CONTROL.sub("", text).strip()


def status_of(share: Share, now: datetime | None = None) -> ShareStatus:
    if share.revoked_at is not None:
        return "revoked"
    if (now or _now()) >= share.expires_at:
        return "expired"
    if share.closed_at is not None:
        return "closed"
    return "active"


def view_of(snapshot: dict) -> SharedView:
    ai = snapshot.get("ai_feedback")
    follow = snapshot.get("followup")
    excerpt = [SharedSentence(index=s["index"], text=s["text"]) for s in snapshot["excerpt"]]
    return SharedView(
        kind=snapshot["kind"],
        career_title=snapshot["career_title"],
        question=SharedQuestion(**snapshot["question"]),
        excerpt=excerpt,
        total_sentences=snapshot["total_sentences"],
        omitted_sentences=snapshot["total_sentences"] - len(excerpt),
        followup=SharedFollowup(**follow) if follow else None,
        ai_feedback=(
            SharedAIFeedback(
                score=ai["score"],
                rating=ai["rating"],
                summary=ai["summary"],
                points=[SharedPoint(**p) for p in ai["points"]],
                coach=ai["coach"],
            )
            if ai
            else None
        ),
        note=snapshot.get("note", ""),
        answered_on=snapshot["answered_on"],
        prompts=PROMPTS,
    )


class Shares:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ building the snapshot

    def _answer(self, user: User, answer_id: str) -> PracticeAnswer:
        answer = self.db.get(PracticeAnswer, answer_id)
        if answer is None or answer.user_id != user.id:
            raise NotFoundError("Answer not found")
        return answer

    def _round(self, answer: PracticeAnswer) -> tuple[InterviewTurn, PracticeSession] | None:
        row = self.db.execute(
            select(InterviewTurn, PracticeSession)
            .join(PracticeSession, PracticeSession.id == InterviewTurn.session_id)
            .where(InterviewTurn.answer_id == answer.id, PracticeSession.user_id == answer.user_id)
        ).first()
        return (row[0], row[1]) if row else None

    def _snapshot(self, user: User, sel: ShareSelection) -> tuple[dict, str, list[str], bool, str]:
        answer = self._answer(user, sel.answer_id)
        question = get_question(answer.track, answer.question_id)
        if question is None:
            raise NotFoundError("That question is no longer in the library, so its answer can't be shared.")
        context = self._round(answer)
        if context is not None and context[1].status == InterviewStatus.IN_PROGRESS:
            raise ConflictError(
                "Finish the interview before sharing an answer from it.", code="interview_in_progress"
            )
        sentences = split_sentences(answer.answer)
        chosen = sorted(set(range(len(sentences)) if sel.sentences is None else sel.sentences))
        if any(i < 0 or i >= len(sentences) for i in chosen):
            raise AppError("That sentence isn't part of the answer.", code="unknown_sentence")
        if not chosen:
            raise AppError("Choose at least one sentence to share.", code="empty_selection")

        followup = None
        record = ((context[0].meta or {}).get("followup") if context else None) or {}
        has_followup = record.get("status") == "answered" and bool(record.get("answer"))
        if has_followup and sel.include_followup and context is not None:
            roles = {r["id"]: r["title"] for r in (context[1].plan or {}).get("roles", [])}
            followup = {
                "asked_by": roles.get(record.get("speaker") or "", "Interviewer"),
                "question": record["question"],
                "answer": record["answer"],
            }
        fb = answer.feedback or {}
        ai = (
            {
                "score": answer.score,
                "rating": fb.get("rating", ""),
                "summary": fb.get("summary", ""),
                "points": [
                    {"label": p["label"], "covered": bool(p["covered"])} for p in fb.get("points", [])
                ],
                "coach": answer.provider,
            }
            if sel.include_ai_feedback
            else None
        )
        kind = "interview_answer" if context is not None else "practice_answer"
        career = CATALOG[answer.track].title if answer.track in CATALOG else answer.track
        snapshot = {
            "v": SNAPSHOT_VERSION,
            "kind": kind,
            "career_title": career,
            "question": {
                "title": question.title,
                "prompt": question.prompt,
                "kind": question.kind,
                "difficulty": question.difficulty,
            },
            "excerpt": [{"index": i, "text": sentences[i]} for i in chosen],
            "total_sentences": len(sentences),
            "followup": followup,
            "ai_feedback": ai,
            "note": _clean(sel.note),
            "answered_on": answer.created_at.date().isoformat(),
        }
        source_text = answer.answer + "\x00" + (record.get("answer") or "")
        return snapshot, kind, sentences, has_followup, _digest(source_text)

    def preview(self, user: User, sel: ShareSelection) -> SharePreview:
        snapshot, _kind, sentences, has_followup, _digest_ = self._snapshot(user, sel)
        return SharePreview(
            source_sentences=[SharedSentence(index=i, text=t) for i, t in enumerate(sentences)],
            has_followup=has_followup,
            view=view_of(snapshot),
        )

    # ------------------------------------------------------------------ owner

    def create(self, user: User, body: ShareCreate) -> ShareCreated:
        if not body.acknowledge_link_access:
            raise AppError(
                "Confirm that anyone with the link can see what you selected.",
                code="acknowledgement_required",
            )
        now = _now()
        active = self.db.scalar(
            select(func.count())
            .select_from(Share)
            .where(Share.owner_id == user.id, Share.revoked_at.is_(None), Share.expires_at > now)
        )
        if (active or 0) >= MAX_ACTIVE_SHARES:
            raise ConflictError(
                f"You have {MAX_ACTIVE_SHARES} active links. Revoke some before sharing more.",
                code="share_limit",
            )
        snapshot, kind, _sentences, _has, digest = self._snapshot(user, body)
        token = secrets.token_urlsafe(32)
        share = Share(
            owner_id=user.id,
            token_hash=hash_token(token),
            source_type=kind,
            source_id=body.answer_id,
            source_digest=digest,
            snapshot=snapshot,
            expires_at=now + timedelta(days=body.expires_in_days),
            created_at=now,
        )
        self.db.add(share)
        self.db.commit()
        return ShareCreated(share=self._detail(share), token=token, path=f"/shared#t={token}")

    def _own(self, user: User, share_id: str) -> Share:
        share = self.db.scalar(
            select(Share)
            .options(selectinload(Share.feedback))
            .where(Share.id == share_id, Share.owner_id == user.id)
        )
        if share is None:
            raise NotFoundError("Share not found")
        return share

    def _summary_fields(self, share: Share) -> dict:
        snap = share.snapshot
        return {
            "id": share.id,
            "status": status_of(share),
            "kind": snap["kind"],
            "career_title": snap["career_title"],
            "question_title": snap["question"]["title"],
            "source_answer_id": share.source_id,
            "created_at": share.created_at,
            "expires_at": share.expires_at,
            "closed_at": share.closed_at,
            "revoked_at": share.revoked_at,
            "last_opened_at": share.last_opened_at,
            "feedback_count": len(share.feedback),
            "last_feedback_at": share.feedback[-1].created_at if share.feedback else None,
        }

    def _detail(self, share: Share) -> ShareDetail:
        source = self.db.get(PracticeAnswer, share.source_id)
        changed = False
        if source is not None:
            ctx = self._round(source)
            followup = ((ctx[0].meta or {}).get("followup") if ctx else None) or {}
            changed = _digest(source.answer + "\x00" + (followup.get("answer") or "")) != share.source_digest
        self.db.refresh(share, ["feedback"])
        names = self._names([f.reviewer_id for f in share.feedback])
        return ShareDetail(
            **self._summary_fields(share),
            view=view_of(share.snapshot),
            feedback=[self._feedback_out(share, f, names) for f in share.feedback],
            source_changed=changed,
            source_missing=source is None,
        )

    def mine(self, user: User) -> list[ShareSummary]:
        shares = self.db.scalars(
            select(Share)
            .options(selectinload(Share.feedback))
            .where(Share.owner_id == user.id)
            .order_by(Share.created_at.desc())
        ).all()
        return [ShareSummary(**self._summary_fields(s)) for s in shares]

    def detail(self, user: User, share_id: str) -> ShareDetail:
        return self._detail(self._own(user, share_id))

    def for_answer(self, user: User, answer_id: str) -> list[ShareSummary]:
        shares = self.db.scalars(
            select(Share)
            .options(selectinload(Share.feedback))
            .where(Share.owner_id == user.id, Share.source_id == answer_id)
            .order_by(Share.created_at.desc())
        ).all()
        return [ShareSummary(**self._summary_fields(s)) for s in shares]

    def close(self, user: User, share_id: str) -> ShareDetail:
        share = self._own(user, share_id)
        if share.closed_at is None and share.revoked_at is None:
            share.closed_at = _now()
            self.db.commit()
        return self._detail(share)

    def reopen(self, user: User, share_id: str) -> ShareDetail:
        share = self._own(user, share_id)
        if share.revoked_at is not None:
            raise ConflictError(
                "A revoked link can't be reopened. Share the answer again.", code="share_revoked"
            )
        share.closed_at = None
        self.db.commit()
        return self._detail(share)

    def revoke(self, user: User, share_id: str) -> ShareDetail:
        share = self._own(user, share_id)
        if share.revoked_at is None:
            share.revoked_at = _now()
            self.db.commit()
        return self._detail(share)

    def rotate(self, user: User, share_id: str) -> ShareCreated:
        """A new link for the same snapshot; the old link stops working at once."""
        share = self._own(user, share_id)
        if status_of(share) in ("revoked", "expired"):
            raise ConflictError(
                "This link is turned off. Share the answer again instead.", code="share_inactive"
            )
        token = secrets.token_urlsafe(32)
        share.token_hash = hash_token(token)
        share.link_rotated_at = _now()
        self.db.commit()
        return ShareCreated(share=self._detail(share), token=token, path=f"/shared#t={token}")

    def delete(self, user: User, share_id: str) -> None:
        self.db.delete(self._own(user, share_id))
        self.db.commit()

    def _own_feedback(self, user: User, share_id: str, feedback_id: str) -> tuple[Share, ShareFeedback]:
        share = self._own(user, share_id)
        item = next((f for f in share.feedback if f.id == feedback_id), None)
        if item is None:
            raise NotFoundError("Feedback not found")
        return share, item

    def set_useful(self, user: User, share_id: str, feedback_id: str, useful: bool) -> ShareDetail:
        share, item = self._own_feedback(user, share_id, feedback_id)
        item.useful = useful
        self.db.commit()
        return self._detail(share)

    def delete_feedback(self, user: User, share_id: str, feedback_id: str) -> ShareDetail:
        share, item = self._own_feedback(user, share_id, feedback_id)
        share.feedback.remove(item)
        self.db.commit()
        return self._detail(share)

    # ------------------------------------------------------------------ reviewers (link holders)

    def _by_token(self, token: str) -> Share:
        share = self.db.scalar(select(Share).where(Share.token_hash == hash_token(token)))
        if share is None:
            raise NotFoundError(
                "This link doesn't work. Check that it was copied in full.", code="share_not_found"
            )
        status = status_of(share)
        if status == "revoked":
            raise GoneError("The person who shared this turned the link off.", code="share_revoked")
        if status == "expired":
            raise GoneError("This link has expired.", code="share_expired")
        return share

    @staticmethod
    def _identity(viewer: User | None) -> ReviewerIdentity | None:
        if viewer is None or viewer.is_guest:
            return None
        name = (viewer.display_name or "").strip() or "A CodeCoach user"
        return ReviewerIdentity(kind="account", label=f"{name} (signed-in CodeCoach user)")

    def open(self, token: str, viewer: User | None) -> RecipientView:
        share = self._by_token(token)
        share.last_opened_at = _now()
        self.db.commit()
        status = status_of(share)
        return RecipientView(
            status="closed" if status == "closed" else "active",
            expires_at=share.expires_at,
            view=view_of(share.snapshot),
            reviewer=self._identity(viewer),
        )

    def submit(self, body: FeedbackIn, viewer: User | None) -> FeedbackReceipt:
        share = self._by_token(body.token)
        if status_of(share) == "closed":
            raise ConflictError("The person who shared this isn't taking more feedback.", code="share_closed")
        if viewer is not None and viewer.id == share.owner_id:
            raise ConflictError(
                "This is your own answer: it can't be reviewed with your account.", code="own_share"
            )
        existing = self.db.scalar(
            select(ShareFeedback).where(
                ShareFeedback.share_id == share.id, ShareFeedback.client_request_id == body.client_request_id
            )
        )
        if existing is not None:
            return FeedbackReceipt(feedback=self._feedback_out(share, existing), duplicate=True)

        fields = {k: _clean(getattr(body, k)) for k in ("clear", "needs_evidence", "next_step")}
        anchors = {s["index"] for s in share.snapshot["excerpt"]}
        comments = []
        for c in body.comments:
            if c.sentence not in anchors:
                raise AppError("A comment refers to a sentence that wasn't shared.", code="unknown_sentence")
            text = _clean(c.text)
            if text:
                comments.append({"sentence": c.sentence, "text": text})
        if not any(fields.values()) and not comments:
            raise AppError("Write something in at least one box before sending.", code="empty_feedback")
        count = self.db.scalar(
            select(func.count()).select_from(ShareFeedback).where(ShareFeedback.share_id == share.id)
        )
        if (count or 0) >= MAX_FEEDBACK_PER_SHARE:
            raise ConflictError(
                "This link has received as much feedback as it can take.", code="feedback_limit"
            )

        account = viewer is not None and not viewer.is_guest
        item = ShareFeedback(
            share_id=share.id,
            reviewer_id=viewer.id if account and viewer is not None else None,
            reviewer_kind="account" if account else "guest",
            guest_name=None if account else (_clean(body.guest_name) or None),
            comments=comments,
            client_request_id=body.client_request_id,
            **fields,
        )
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:  # the same retry arrived twice at once
            self.db.rollback()
            item = self.db.scalars(
                select(ShareFeedback).where(
                    ShareFeedback.share_id == share.id,
                    ShareFeedback.client_request_id == body.client_request_id,
                )
            ).one()
            return FeedbackReceipt(feedback=self._feedback_out(share, item), duplicate=True)
        return FeedbackReceipt(feedback=self._feedback_out(share, item), duplicate=False)

    # ------------------------------------------------------------------ presenting feedback

    def _names(self, ids: list[str | None]) -> dict[str, str | None]:
        wanted = {i for i in ids if i}
        if not wanted:
            return {}
        return dict(self.db.execute(select(User.id, User.display_name).where(User.id.in_(wanted))).all())

    def _feedback_out(
        self, share: Share, f: ShareFeedback, names: dict[str, str | None] | None = None
    ) -> FeedbackOut:
        if names is None:
            names = self._names([f.reviewer_id])
        if f.reviewer_kind == "account" and f.reviewer_id is None:
            reviewer = ReviewerIdentity(
                kind="former_account", label="A former CodeCoach user (account deleted)"
            )
        elif f.reviewer_kind == "account":
            name = (names.get(f.reviewer_id or "") or "").strip() or "A CodeCoach user"
            reviewer = ReviewerIdentity(kind="account", label=f"{name} (signed-in CodeCoach user)")
        else:
            label = f"{f.guest_name} (guest, name not verified)" if f.guest_name else "Guest (no name given)"
            reviewer = ReviewerIdentity(kind="guest", label=label)
        quotes = {s["index"]: s["text"] for s in share.snapshot["excerpt"]}
        return FeedbackOut(
            id=f.id,
            reviewer=reviewer,
            clear=f.clear,
            needs_evidence=f.needs_evidence,
            next_step=f.next_step,
            comments=[
                FeedbackCommentOut(
                    sentence=c["sentence"], text=c["text"], quote=quotes.get(c["sentence"], "")
                )
                for c in f.comments
            ],
            created_at=f.created_at,
            useful=f.useful,
        )

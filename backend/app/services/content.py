"""Content quality: metadata and trust labels, issue reports, and triage (see docs/CONTENT_QUALITY.md).

Rules this module keeps:
- Trust labels come only from recorded facts: how the content was made (it's all generated
  today), whether a check actually ran and passed (content_checks), and published corrections.
  Nothing claims expert review, because none has been recorded.
- A report is pinned to the content id and the version the learner saw, never changes a score,
  and its reporter sees only their own words and the public resolution.
- Corrections add a version; answers keep the version they were written against.
- Every triage action is written to content_audit.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.formats import KIND_LABEL
from app.careers.questions import CORRECTABLE_FIELDS, content_key, get_question
from app.careers.skills import question_skills
from app.content import state as content_state
from app.errors import AppError, ConflictError, NotFoundError
from app.models import (
    ContentAudit,
    ContentCheck,
    ContentReport,
    ContentStatus,
    ContentVersion,
    PracticeAnswer,
    Problem,
    TestCase,
    User,
)
from app.schemas.content import (
    AdminReport,
    AdminReportDetail,
    AuditEntry,
    ContentChange,
    ContentMeta,
    CorrectionIn,
    DuplicateIn,
    MyReport,
    ReportGroup,
    ReportIn,
    RetireIn,
    StatusIn,
    TrustLabel,
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
OPEN = ("open", "investigating")


def _now() -> datetime:
    return datetime.now(UTC)


def _clean(text: str | None) -> str:
    """Untrusted text: stored and shown as plain text, control characters removed."""
    return _CONTROL.sub("", text or "").strip()


class Content:
    """What a content id refers to, at its current version."""

    def __init__(
        self,
        content_type: str,
        content_id: str,
        title: str,
        href: str | None,
        version: int,
        career: str | None,
        topic: str | None,
        level: str | None,
        test_count: int = 0,
    ):
        self.content_type = content_type
        self.content_id = content_id
        self.title = title
        self.href = href
        self.version = version
        self.career = career
        self.topic = topic
        self.level = level
        self.test_count = test_count


class ContentService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ resolving content

    def resolve(self, content_type: str, content_id: str) -> Content:
        if content_type == "question":
            track, _, qid = content_id.partition("/")
            q = get_question(track, qid) if track in CATALOG else None
            if q is None:
                raise NotFoundError("Question not found")
            skills = question_skills(q)
            return Content(
                "question",
                content_key(track, qid),
                q.title,
                f"/careers/{track}/questions/{qid}",
                q.version,
                CATALOG[track].title,
                skills[0] if skills else KIND_LABEL.get(q.kind, q.kind),
                q.difficulty,
            )
        if content_type == "problem":
            p = self.db.scalar(select(Problem).where(Problem.slug == content_id))
            if p is None:
                raise NotFoundError("Problem not found")
            version = (
                self.db.scalar(select(func.max(TestCase.version)).where(TestCase.problem_id == p.id)) or 1
            )
            tests = (
                self.db.scalar(select(func.count()).select_from(TestCase).where(TestCase.problem_id == p.id))
                or 0
            )
            return Content(
                "problem",
                p.slug,
                p.title,
                f"/problems/{p.slug}",
                int(version),
                "Software Engineer (coding)",
                p.topics[0] if p.topics else None,
                p.difficulty.value,
                int(tests),
            )
        raise NotFoundError("Unknown content type")

    def meta(self, content_type: str, content_id: str) -> ContentMeta:
        c = self.resolve(content_type, content_id)
        snap = content_state.current()
        retired = snap.retired.get((c.content_type, c.content_id))
        changes = [
            ContentChange(version=x.version, note=x.change_note, significant=x.significant, at=x.created_at)
            for x in snap.corrections.get((c.content_type, c.content_id), [])
        ]
        labels: list[TrustLabel] = []
        if c.content_type == "question":
            labels.append(
                TrustLabel(
                    key="generated",
                    text=f"Generated from the {c.career} career profile by CodeCoach's question templates",
                )
            )
        else:
            labels.append(TrustLabel(key="generated", text="Generated for CodeCoach's coding problem bank"))
            check = self.db.scalar(
                select(ContentCheck).where(
                    ContentCheck.content_type == "problem",
                    ContentCheck.content_id == c.content_id,
                    ContentCheck.check == "reference_solution",
                )
            )
            if check is not None and check.passed and check.content_version == c.version:
                labels.append(
                    TrustLabel(
                        key="reference_verified",
                        text=f"A reference solution passed all {c.test_count} tests (checked {check.checked_at:%b %d, %Y})",
                    )
                )
            else:
                labels.append(
                    TrustLabel(
                        key="tests_not_checked",
                        text="Tests haven't been checked against a reference solution on this server",
                    )
                )
        labels.append(TrustLabel(key="not_expert_reviewed", text="Not reviewed by a subject-matter expert"))
        if changes:
            labels.append(
                TrustLabel(
                    key="corrected",
                    text=f"Corrected {len(changes)} {'time' if len(changes) == 1 else 'times'} after reports; see what changed",
                )
            )
        return ContentMeta(
            content_type=c.content_type,
            content_id=c.content_id,
            version=c.version,
            version_label=f"Version {c.version}"
            if c.content_type == "question"
            else f"Test version {c.version}",
            career=c.career,
            topic=c.topic,
            level=c.level,
            status="retired" if retired is not None else "active",
            retired_reason=retired,
            labels=labels,
            changes=changes,
        )

    # ------------------------------------------------------------------ reports (learners)

    def _audit(
        self,
        actor: User | None,
        action: str,
        report: ContentReport | None = None,
        *,
        content_type: str | None = None,
        content_id: str | None = None,
        detail: dict | None = None,
        internal_note: str | None = None,
    ) -> None:
        self.db.add(
            ContentAudit(
                actor_id=actor.id if actor else None,
                action=action,
                content_type=content_type or (report.content_type if report else ""),
                content_id=content_id or (report.content_id if report else ""),
                report_id=report.id if report else None,
                detail=detail or {},
                internal_note=_clean(internal_note) or None,
            )
        )

    def report(self, user: User, body: ReportIn) -> MyReport:
        c = self.resolve(body.content_type, body.content_id)
        if body.content_version > c.version:
            raise AppError("That version doesn't exist.", code="invalid_version")
        answer_id = None
        if body.context == "feedback":
            if c.content_type != "question" or not body.answer_id:
                raise AppError(
                    "Feedback reports need the answer the feedback was on.", code="answer_required"
                )
            answer = self.db.get(PracticeAnswer, body.answer_id)
            if (
                answer is None
                or answer.user_id != user.id
                or content_key(answer.track, answer.question_id) != c.content_id
            ):
                raise NotFoundError("Answer not found")
            answer_id = answer.id
        mine = self.db.scalar(
            select(ContentReport).where(
                ContentReport.reporter_id == user.id,
                ContentReport.content_type == c.content_type,
                ContentReport.content_id == c.content_id,
                ContentReport.category == body.category,
                ContentReport.context == body.context,
                ContentReport.status.in_(OPEN),
            )
        )
        if mine is not None:
            raise ConflictError(
                "You've already reported this, and it's still open. Its status is in My reports.",
                code="already_reported",
                details={"report_id": mine.id},
            )
        report = ContentReport(
            reporter_id=user.id,
            content_type=c.content_type,
            content_id=c.content_id,
            content_version=body.content_version,
            context=body.context,
            answer_id=answer_id,
            category=body.category,
            details=_clean(body.details),
            excerpt=_clean(body.excerpt) or None,
        )
        # Likely duplicate: the earliest open report on the same thing. Grouped, never deleted.
        primary = self.db.scalar(
            select(ContentReport)
            .where(
                ContentReport.content_type == c.content_type,
                ContentReport.content_id == c.content_id,
                ContentReport.category == body.category,
                ContentReport.status.in_(OPEN),
                ContentReport.duplicate_of.is_(None),
            )
            .order_by(ContentReport.created_at)
        )
        if primary is not None:
            report.duplicate_of = primary.id
        self.db.add(report)
        self.db.flush()
        self._audit(
            user, "reported", report, detail={"category": body.category, "version": body.content_version}
        )
        if primary is not None:
            self._audit(None, "auto_grouped", report, detail={"duplicate_of": primary.id})
        self.db.commit()
        return self._mine_out(report, c)

    def _mine_out(self, r: ContentReport, c: Content | None = None) -> MyReport:
        if c is None:
            try:
                c = self.resolve(r.content_type, r.content_id)
            except NotFoundError:
                c = None
        return MyReport(
            id=r.id,
            content_type=r.content_type,
            content_id=r.content_id,
            content_title=c.title if c else "Content no longer in the library",
            content_href=c.href if c else None,
            content_version=r.content_version,
            category=r.category,
            context=r.context,
            details=r.details,
            excerpt=r.excerpt,
            status=r.status,
            resolution=r.resolution,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    def mine(self, user: User) -> list[MyReport]:
        rows = self.db.scalars(
            select(ContentReport)
            .where(ContentReport.reporter_id == user.id)
            .order_by(ContentReport.created_at.desc())
        ).all()
        return [self._mine_out(r) for r in rows]

    # ------------------------------------------------------------------ triage (admins)

    def _report(self, report_id: str) -> ContentReport:
        r = self.db.get(ContentReport, report_id)
        if r is None:
            raise NotFoundError("Report not found")
        return r

    def _admin_out(self, r: ContentReport, names: dict[str, str | None]) -> AdminReport:
        base = self._mine_out(r)
        duplicates = self.db.scalars(select(ContentReport.id).where(ContentReport.duplicate_of == r.id)).all()
        try:
            current = self.resolve(r.content_type, r.content_id).version
        except NotFoundError:
            current = r.content_version
        return AdminReport(
            **base.model_dump(),
            reporter=(names.get(r.reporter_id) or "").strip() or "A learner",
            duplicate_of=r.duplicate_of,
            duplicates=list(duplicates),
            current_version=current,
        )

    def _names(self, ids: list[str]) -> dict[str, str | None]:
        if not ids:
            return {}
        return dict(self.db.execute(select(User.id, User.display_name).where(User.id.in_(set(ids)))).all())

    def groups(self, status: str | None) -> list[ReportGroup]:
        q = select(ContentReport).order_by(ContentReport.created_at)
        if status == "open":
            q = q.where(ContentReport.status.in_(OPEN))
        elif status:
            q = q.where(ContentReport.status == status)
        rows = self.db.scalars(q).all()
        names = self._names([r.reporter_id for r in rows])
        grouped: dict[tuple[str, str], list[ContentReport]] = {}
        for r in rows:
            grouped.setdefault((r.content_type, r.content_id), []).append(r)
        out = []
        for (ctype, cid), reports in grouped.items():
            first = self._admin_out(reports[0], names)
            out.append(
                ReportGroup(
                    content_type=ctype,
                    content_id=cid,
                    content_title=first.content_title,
                    open_count=sum(r.status in OPEN for r in reports),
                    reports=[first, *[self._admin_out(r, names) for r in reports[1:]]],
                )
            )
        return sorted(out, key=lambda g: (-g.open_count, g.content_title))

    def detail(self, report_id: str) -> AdminReportDetail:
        r = self._report(report_id)
        audit = self.db.scalars(
            select(ContentAudit)
            .where(
                (ContentAudit.report_id == r.id)
                | (
                    (ContentAudit.content_type == r.content_type)
                    & (ContentAudit.content_id == r.content_id)
                    & ContentAudit.report_id.is_(None)
                )
            )
            .order_by(ContentAudit.id)
        ).all()
        names = self._names([r.reporter_id, *[a.actor_id for a in audit if a.actor_id]])
        try:
            meta = self.meta(r.content_type, r.content_id)
        except NotFoundError:
            meta = None
        if meta is None:
            raise NotFoundError("The reported content no longer exists")
        return AdminReportDetail(
            **self._admin_out(r, names).model_dump(),
            audit=[
                AuditEntry(
                    action=a.action,
                    actor=(names.get(a.actor_id or "") or "An admin") if a.actor_id else "System",
                    detail=a.detail,
                    internal_note=a.internal_note,
                    created_at=a.created_at,
                )
                for a in audit
            ],
            meta=meta,
        )

    def _set_status(
        self, admin: User, r: ContentReport, status: str, resolution: str | None, note: str | None
    ) -> None:
        before = r.status
        r.status = status
        if resolution is not None:
            r.resolution = resolution
        r.updated_at = _now()
        self._audit(
            admin,
            "status",
            r,
            detail={"from": before, "to": status, "resolution": resolution},
            internal_note=note,
        )

    def set_status(self, admin: User, report_id: str, body: StatusIn) -> AdminReportDetail:
        r = self._report(report_id)
        resolution = _clean(body.resolution) or None
        if body.status in ("resolved", "not_actionable") and not resolution:
            raise AppError(
                "Say what happened, in plain language: the reporter will read it.", code="resolution_required"
            )
        self._set_status(admin, r, body.status, resolution, body.internal_note)
        if body.include_duplicates and r.duplicate_of is None:
            for d in self.db.scalars(select(ContentReport).where(ContentReport.duplicate_of == r.id)):
                if d.status != body.status:
                    self._set_status(admin, d, body.status, resolution, "Updated with its group")
        self.db.commit()
        return self.detail(r.id)

    def set_duplicate(self, admin: User, report_id: str, body: DuplicateIn) -> AdminReportDetail:
        r = self._report(report_id)
        target = None
        if body.duplicate_of is not None:
            target = self._report(body.duplicate_of)
            if target.duplicate_of is not None:
                target = self._report(target.duplicate_of)  # group under the primary, never a chain
            if target.id == r.id or (target.content_type, target.content_id) != (
                r.content_type,
                r.content_id,
            ):
                raise AppError(
                    "Only reports about the same content can be grouped.", code="invalid_duplicate"
                )
            # Anything grouped under this report moves with it.
            for d in self.db.scalars(select(ContentReport).where(ContentReport.duplicate_of == r.id)):
                d.duplicate_of = target.id
        r.duplicate_of = target.id if target else None
        r.updated_at = _now()
        self._audit(
            admin,
            "grouped" if target else "ungrouped",
            r,
            detail={"duplicate_of": r.duplicate_of},
            internal_note=body.internal_note,
        )
        self.db.commit()
        return self.detail(r.id)

    def _linked_reports(self, ids: list[str], content_type: str, content_id: str) -> list[ContentReport]:
        """The reports a correction or retirement answers, plus their grouped likely duplicates:
        everyone who reported the same problem hears the outcome."""
        reports = [self._report(i) for i in dict.fromkeys(ids)]
        if any((x.content_type, x.content_id) != (content_type, content_id) for x in reports):
            raise AppError("Linked reports must be about this content.", code="invalid_reports")
        seen = {r.id for r in reports}
        for primary in list(reports):
            for d in self.db.scalars(select(ContentReport).where(ContentReport.duplicate_of == primary.id)):
                if d.id not in seen:
                    seen.add(d.id)
                    reports.append(d)
        return reports

    def correct(self, admin: User, track: str, question_id: str, body: CorrectionIn) -> ContentMeta:
        c = self.resolve("question", content_key(track, question_id))
        q = get_question(track, question_id)
        assert q is not None
        changes: dict = {}
        for name in CORRECTABLE_FIELDS:
            value = getattr(body, name)
            if value is None:
                continue
            cleaned = [_clean(v) for v in value if _clean(v)] if isinstance(value, list) else _clean(value)
            current = list(getattr(q, name)) if isinstance(cleaned, list) else getattr(q, name)
            if cleaned and cleaned != current:
                changes[name] = cleaned
        if not changes:
            raise AppError("Nothing changed: edit at least one field.", code="no_change")
        reports = self._linked_reports(body.report_ids, "question", c.content_id)
        version = c.version + 1
        note = _clean(body.change_note)
        self.db.add(
            ContentVersion(
                content_type="question",
                content_id=c.content_id,
                version=version,
                fields=changes,
                change_note=note,
                significant=body.significant,
                created_by=admin.id,
            )
        )
        self._audit(
            admin,
            "corrected",
            content_type="question",
            content_id=c.content_id,
            detail={"version": version, "fields": sorted(changes), "reports": [r.id for r in reports]},
            internal_note=body.internal_note,
        )
        for r in reports:
            if r.status in OPEN:
                self._set_status(admin, r, "resolved", f"Corrected in version {version}: {note}", None)
        self.db.commit()
        content_state.refresh(self.db, force=True)
        return self.meta("question", c.content_id)

    def retire(self, admin: User, content_type: str, content_id: str, body: RetireIn) -> ContentMeta:
        c = self.resolve(content_type, content_id)
        reports = self._linked_reports(body.report_ids, c.content_type, c.content_id)
        reason = _clean(body.reason)
        row = self.db.get(ContentStatus, (c.content_type, c.content_id))
        if row is None:
            row = ContentStatus(content_type=c.content_type, content_id=c.content_id)
            self.db.add(row)
        row.status, row.reason, row.changed_by, row.changed_at = "retired", reason, admin.id, _now()
        self._audit(
            admin,
            "retired",
            content_type=c.content_type,
            content_id=c.content_id,
            detail={"reason": reason, "reports": [r.id for r in reports]},
            internal_note=body.internal_note,
        )
        for r in reports:
            if r.status in OPEN:
                self._set_status(admin, r, "resolved", f"Retired: {reason}", None)
        self.db.commit()
        content_state.refresh(self.db, force=True)
        return self.meta(c.content_type, c.content_id)

    def restore(self, admin: User, content_type: str, content_id: str, note: str | None) -> ContentMeta:
        c = self.resolve(content_type, content_id)
        row = self.db.get(ContentStatus, (c.content_type, c.content_id))
        if row is not None:
            self.db.delete(row)
            self._audit(
                admin, "restored", content_type=c.content_type, content_id=c.content_id, internal_note=note
            )
            self.db.commit()
            content_state.refresh(self.db, force=True)
        return self.meta(c.content_type, c.content_id)


def is_problem_retired(slug: str) -> bool:
    return ("problem", slug) in content_state.current().retired


def retired_problem_slugs() -> set[str]:
    return {cid for (ctype, cid) in content_state.current().retired if ctype == "problem"}

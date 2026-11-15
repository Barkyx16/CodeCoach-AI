"""Restoring your own data from a CodeCoach backup (the file the data export gives you).

The contract (see docs/BACKUP_FORMAT.md):

- A JSON object with `export_version` 1 or 2, at most 5 MB. Nothing else is accepted: no archives, no
  paths, nothing executable.
- Additive only, into the signed-in account. Ids, account details and timestamps in the file are
  never trusted: records get new ids and belong to whoever is signed in.
- Restorable: notes, stories, bookmarks, and applications with their events; from a version 2
  file (which keeps ids), accepted improvements with their occurrences, under their own ids
  (Volume 14, prompt 5). Everything else is listed as not restored, with the reason: account details and roles; practice results and any
  evaluation (they can't be verified from a file, so an edited backup can't create a passing
  verdict or a score); and shares, sessions and the schedule (they could expose data or trigger
  something).
- Duplicates (by a fingerprint of the content) are skipped, so importing a file twice changes
  nothing. A missing question is never swapped for a similar one: a bookmark to it is skipped,
  and a note about it keeps its text without the link.
- A batch is applied in one transaction: all of it, or none of it.
- A batch can remove what it added, but only records still exactly as imported; anything edited
  since is kept.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import get_question
from app.drills import BY_ID as DRILLS
from app.errors import AppError, NotFoundError
from app.models import (
    AcceptedAction,
    Application,
    ApplicationEvent,
    ApplicationStageChange,
    Bookmark,
    ExperienceEntry,
    ImportBatch,
    ImportedRecord,
    Note,
    PracticeSession,
    Problem,
    RoleTarget,
    ScheduleEntry,
    TargetRequirement,
    User,
)
from app.schemas.applications import ApplicationCreate, ApplicationEventIn
from app.schemas.notes import NoteIn, SourceIn
from app.schemas.restore import RestoreBatch, RestoreCategory, RestorePreview, RestoreSkip, RestoreUnsupported
from app.schemas.stories import StoryCreate
from app.services.applications import MAX_APPLICATIONS
from app.services.explore import SAVED
from app.services.note_freshness import (
    NOTE,
    SourceFreshness,
    SourceRef,
    forget,
    known_version,
    problem_versions,
)
from app.services.notes import MAX_NOTES, Notebook, clean_tags
from app.services.stories import MAX_STORIES, record_revision
from app.services.timeutil import local_to_utc

SUPPORTED_VERSIONS = (1, 2)
MAX_OCCURRENCES = 52  # a weekly improvement scheduled for a year
MAX_BYTES = 5 * 1024 * 1024
MAX_PER_CATEGORY = 2000
CATEGORIES: dict[str, str] = {
    "notes": "Notes",
    "stories": "Stories",
    "bookmarks": "Bookmarks",
    "applications": "Applications and their events",
    "accepted_actions": "Accepted improvements, with their occurrences (version 2 files)",
}
_ACCOUNT = "Account details, sign-in and roles are never restored. Your account stays exactly as it is."
_RESULTS = (
    "Practice results and evaluations aren't restored: a file can't prove they happened here, so an "
    "edited backup could otherwise create a pass, a score or progress."
)
_EXPOSE = "Never restored, because it could share data or start something (links, sessions, reminders)."
NOT_RESTORED: dict[str, str] = {
    "profile": _ACCOUNT,
    "onboarding": _ACCOUNT,
    "submissions": _RESULTS,
    "ai_interactions": _RESULTS,
    "practice_sessions": _RESULTS,
    "practice_answers": _RESULTS,
    "answers": _RESULTS,
    "interviews": _RESULTS,
    "goals": _RESULTS,
    "plans": _RESULTS,
    "retries": _RESULTS,
    "review_queue": _RESULTS,
    "scenario_attempts": _RESULTS,
    "learn_events": _RESULTS,
    "progress_events": _RESULTS,
    "drill_attempts": _RESULTS,
    "whiteboard": _RESULTS,
    "code_reviews": _RESULTS,
    "test_design_runs": _RESULTS,
    "work_samples": _RESULTS,
    "comparisons": _RESULTS,
    "offer_rehearsals": _RESULTS,
    "offer_comparisons": "Offer comparisons aren't restored from a file: they hold pay you entered privately; re-enter them.",
    "kit_templates": "Kit templates aren't restored yet: save them again from a kit.",
    "source_reviews": "Decisions about changed stories aren't restored: they belong to kits and links that aren't restored yet.",
    # A note's and a saved item's "Mark reviewed" travel inside them (notes[].source_reviews,
    # bookmarks[].source_reviews): a restore keeps the version each was captured or saved at (never
    # the current one: a version the file doesn't give, or one the source never had, is "not known")
    # and brings back its reviews (Volume 14, prompt 7; docs/STORY_FRESHNESS.md).
    "answer_reviews": _RESULTS,
    "targets": "Job targets aren't restored yet; their requirements link to postings by id.",
    "collections": "Collections aren't restored yet. Bookmarks are, with the version each was saved at and what you reviewed.",
    "shares": _EXPOSE,
    "shared_feedback": _EXPOSE,
    "sessions": _EXPOSE,
    "schedule": _EXPOSE,
    "content_reports": "Reports you sent stay with the original account's history.",
    "interview_kits": "Interview-day kits belong to interview events by id, so they aren't restored yet.",
    "interview_reflections": "Interview reflections belong to interview events by id, so they aren't restored yet.",
}
_META = {"export_version", "exported_at"}


def _sha(parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _s(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _when(v: Any) -> datetime | None:
    """A timestamp from the file, or None if it isn't one (never in the future)."""
    if not isinstance(v, str):
        return None
    try:
        t = datetime.fromisoformat(v)
    except ValueError:
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    return min(t, datetime.now(UTC))


# --- fingerprints: identity (for duplicates) and full (for "unchanged since import") ------------


def note_identity(title: str, body: str, reflection: str) -> str:
    return _sha(["note", title.strip(), body.strip(), reflection.strip()])


def note_full(n: Note) -> str:
    return _sha(
        [
            n.title,
            n.body,
            n.reflection,
            n.tags,
            n.archived,
            n.source_type,
            n.source_id,
            n.excerpt,
            n.deleted_at is None,
        ]
    )


def story_identity(title: str, situation: str, action: str, result: str) -> str:
    return _sha(["story", title.strip().lower(), situation.strip(), action.strip(), result.strip()])


def story_full(e: ExperienceEntry) -> str:
    return _sha(
        [
            e.title,
            e.situation,
            e.task,
            e.action,
            e.result,
            e.reflection,
            e.notes,
            e.evidence,
            e.tags,
            e.competencies,
            e.short_version,
            e.long_version,
            e.archived,
            e.revision,
        ]
    )


def bookmark_identity(item_type: str, track: str, ref_id: str) -> str:
    return _sha(["bookmark", item_type, track, ref_id])


def application_identity(employer: str, role_title: str, applied_on: Any, link: Any) -> str:
    return _sha(
        [
            "application",
            employer.strip().lower(),
            role_title.strip().lower(),
            str(applied_on or ""),
            link or "",
        ]
    )


def action_identity(source_kind: str, source_id: str, source_key: str) -> str:
    """An accepted improvement is the same one if it came from the same suggestion (its source)."""
    return _sha(["accepted_action", source_kind, source_id, source_key])


def action_full(a: AcceptedAction, occurrences: list[ScheduleEntry]) -> str:
    return _sha(
        [
            a.title,
            a.notes,
            a.recurrence,
            a.done_at,
            a.archived_at,
            sorted((e.id, str(e.on_date), e.status, str(e.completed_at)) for e in occurrences),
        ]
    )


def application_full(a: Application) -> str:
    return _sha(
        [
            a.employer,
            a.role_title,
            a.link,
            str(a.applied_on),
            a.stage,
            a.next_action,
            str(a.next_action_due),
            a.notes,
            a.archived,
            [(e.kind, e.title, str(e.on_date), e.local_time, e.timezone, e.notes) for e in a.events],
        ]
    )


@dataclass
class _Plan:
    """What a file would do: for each category, the rows to add and why others are skipped."""

    found: Counter = field(default_factory=Counter)
    adds: dict[str, list[dict]] = field(default_factory=lambda: {k: [] for k in CATEGORIES})
    duplicates: Counter = field(default_factory=Counter)
    skipped: dict[str, Counter] = field(default_factory=lambda: {k: Counter() for k in CATEGORIES})
    unsupported: list[RestoreUnsupported] = field(default_factory=list)
    ignored_fields: int = 0


class Restore:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # --- reading the file ---------------------------------------------------------------------

    @staticmethod
    def parse(raw: bytes) -> dict:
        if len(raw) > MAX_BYTES:
            raise AppError(
                "That file is larger than 5 MB, so it can't be a CodeCoach backup.", code="file_too_large"
            )
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise AppError("That file isn't valid JSON.", code="invalid_json") from None
        if not isinstance(data, dict) or "export_version" not in data:
            raise AppError(
                "This doesn't look like a CodeCoach backup: it has no export_version.", code="not_a_backup"
            )
        version = data["export_version"]
        if version not in SUPPORTED_VERSIONS:
            raise AppError(
                f"Backups of version {version!r} can't be read; this version of CodeCoach reads versions 1 and 2.",
                code="unsupported_version",
                details={"supported": list(SUPPORTED_VERSIONS)},
            )
        return data

    def _existing(self) -> dict[str, set[str]]:
        uid = self.user.id
        notes = self.db.execute(
            select(Note.title, Note.body, Note.reflection).where(
                Note.user_id == uid, Note.deleted_at.is_(None)
            )
        ).all()
        stories = self.db.execute(
            select(
                ExperienceEntry.title,
                ExperienceEntry.situation,
                ExperienceEntry.action,
                ExperienceEntry.result,
            ).where(ExperienceEntry.user_id == uid)
        ).all()
        marks = self.db.execute(
            select(Bookmark.item_type, Bookmark.track, Bookmark.ref_id).where(Bookmark.user_id == uid)
        ).all()
        apps = self.db.execute(
            select(
                Application.employer, Application.role_title, Application.applied_on, Application.link
            ).where(Application.user_id == uid)
        ).all()
        actions = self.db.execute(
            select(AcceptedAction.source_kind, AcceptedAction.source_id, AcceptedAction.source_key).where(
                AcceptedAction.user_id == uid
            )
        ).all()
        return {
            "notes": {note_identity(*r) for r in notes},
            "stories": {story_identity(*r) for r in stories},
            "bookmarks": {bookmark_identity(*r) for r in marks},
            "applications": {application_identity(*r) for r in apps},
            "accepted_actions": {action_identity(*r) for r in actions},
        }

    def _plan(self, data: dict) -> _Plan:
        plan = _Plan()
        for key, value in data.items():
            if key in _META or key in CATEGORIES:
                continue
            n = len(value) if isinstance(value, (list, dict)) else 1
            plan.unsupported.append(
                RestoreUnsupported(
                    key=key, count=n, reason=NOT_RESTORED.get(key, "Not recognised, so it's ignored.")
                )
            )
        seen = self._existing()
        for cat in CATEGORIES:
            rows = data.get(cat) or []
            if not isinstance(rows, list):
                plan.skipped[cat]["Not a list of records"] += 1
                continue
            plan.found[cat] = len(rows)
            for i, row in enumerate(rows):
                if i >= MAX_PER_CATEGORY:
                    plan.skipped[cat][f"More than {MAX_PER_CATEGORY} in one file"] += 1
                    continue
                if not isinstance(row, dict):
                    plan.skipped[cat]["Not a record"] += 1
                    continue
                checked = (
                    self._check_accepted_actions(row, plan, data)
                    if cat == "accepted_actions"
                    else getattr(self, f"_check_{cat}")(row, plan)
                )
                if isinstance(checked, str):
                    plan.skipped[cat][checked] += 1
                    continue
                if checked["identity"] in seen[cat]:
                    plan.duplicates[cat] += 1
                    continue
                seen[cat].add(checked["identity"])
                plan.adds[cat].append(checked)
        return plan

    # --- per-category checks: a dict to add, or the reason it's skipped ---------------------------

    def _check_notes(self, row: dict, plan: _Plan) -> dict | str:
        known = {
            "title",
            "body",
            "reflection",
            "tags",
            "source",
            "excerpt",
            "key_points",
            "pinned",
            "archived",
            "created_at",
            "updated_at",
            "source_reviews",
        }
        plan.ignored_fields += len(set(row) - known)
        try:
            body = NoteIn(
                title=_s(row.get("title")),
                body=_s(row.get("body")),
                reflection=_s(row.get("reflection")),
                tags=[t for t in row.get("tags") or [] if isinstance(t, str)][:12],
                excerpt=row.get("excerpt") if isinstance(row.get("excerpt"), str) else None,
            )
        except ValidationError:
            return "Too long or malformed"
        if not (body.title or body.body or body.reflection):
            return "Empty"
        source, link_note = None, None
        src = row.get("source")
        if (
            isinstance(src, dict)
            and src.get("type") in ("question", "problem", "lesson")
            and isinstance(src.get("id"), str)
        ):
            try:
                resolved = Notebook(self.db)._resolve(
                    self.user, SourceIn(type=src["type"], id=src["id"], track=src.get("career"))
                )
                # The version it was captured at, from the file: never the version now, which would
                # hide a change since. One the source never had, or none, reads "not known".
                raw = src.get("version")
                ref = SourceRef(kind=src["type"], id=resolved[0], track=resolved[1], captured=None)
                problems = problem_versions(self.db, {ref.id} if ref.kind == "problem" else set())
                captured = known_version(
                    ref, int(raw) if isinstance(raw, str) and raw.isdigit() else raw, problems
                )
                source = {
                    "type": src["type"],
                    "id": resolved[0],
                    "track": resolved[1],
                    "version": None if captured is None else str(captured),
                    "title": resolved[3],
                    "reviews": row.get("source_reviews"),
                }
            except (NotFoundError, ValidationError, AppError):
                link_note = "Linked content isn't in the library: kept without the link"
        elif src:
            link_note = "Linked to something that can't be restored: kept without the link"
        return {
            "identity": note_identity(body.title, body.body, body.reflection),
            "body": body,
            "source": source,
            "archived": bool(row.get("archived")),
            "link_note": link_note,
        }

    def _check_stories(self, row: dict, plan: _Plan) -> dict | str:
        fields = (
            "title",
            "track",
            "context",
            "situation",
            "task",
            "action",
            "result",
            "reflection",
            "notes",
            "evidence",
            "competencies",
            "tags",
            "short_version",
            "long_version",
        )
        plan.ignored_fields += len(
            set(row)
            - set(fields)
            - {
                "id",
                "revision",
                "archived",
                "created_at",
                "updated_at",
                "revisions",
                "question_refs",
                "requirement_ids",
                "requirement_versions",  # links to a target's requirements, which aren't restored
                "target_id",
            }
        )
        data = {k: row[k] for k in fields if row.get(k) is not None}
        if data.get("track") not in CATALOG:
            data.pop("track", None)
        try:
            body = StoryCreate.model_validate(data)
        except ValidationError:
            return "Too long or malformed"
        return {
            "identity": story_identity(
                body.title, body.situation or "", body.action or "", body.result or ""
            ),
            "body": body,
            "archived": bool(row.get("archived")),
        }

    def _check_bookmarks(self, row: dict, plan: _Plan) -> dict | str:
        plan.ignored_fields += len(
            set(row) - {"type", "career", "item", "created_at", "version", "source_reviews"}
        )
        kind, track, ref = row.get("type"), row.get("career") or "", row.get("item")
        if (
            kind not in ("question", "problem", "drill")
            or not isinstance(ref, str)
            or not isinstance(track, str)
        ):
            return "Malformed"
        if kind == "question":
            q = get_question(track, ref) if track in CATALOG else None
            if q is None:
                return "The question isn't in the library (it's never swapped for a similar one)"
            src = SourceRef(kind="question", id=ref, track=track, captured=None)
            return {
                "identity": bookmark_identity(kind, track, ref),
                "kind": kind,
                "track": track,
                "ref": ref,
                # The version it was saved at, from the file (docs/STORY_FRESHNESS.md); never now.
                "version": known_version(src, row.get("version"), {}),
                "reviews": row.get("source_reviews"),
            }
        if kind == "problem":
            if self.db.scalar(select(Problem.id).where(Problem.slug == ref)) is None:
                return "The problem isn't in the library"
        elif ref not in DRILLS:
            return "The drill isn't offered any more"
        version = None
        if kind == "problem":
            src = SourceRef(kind="problem", id=ref, track=None, captured=None)
            version = known_version(src, row.get("version"), problem_versions(self.db, {ref}))
        return {
            "identity": bookmark_identity(kind, "", ref),
            "kind": kind,
            "track": "",
            "ref": ref,
            "version": version,
            "reviews": row.get("source_reviews") if kind == "problem" else None,
        }

    def _check_applications(self, row: dict, plan: _Plan) -> dict | str:
        fields = (
            "employer",
            "role_title",
            "link",
            "applied_on",
            "stage",
            "next_action",
            "next_action_due",
            "notes",
        )
        plan.ignored_fields += len(
            set(row) - set(fields) - {"events", "archived", "target", "stories", "stage_history"}
        )
        try:
            body = ApplicationCreate.model_validate({k: row[k] for k in fields if row.get(k) is not None})
        except ValidationError:
            return "Too long or malformed (links must be http or https)"
        events = []
        for ev in row.get("events") or []:
            if not isinstance(ev, dict):
                continue
            try:
                events.append(
                    ApplicationEventIn.model_validate(
                        {
                            "kind": ev.get("kind") or "interview",
                            "title": ev.get("title"),
                            "on_date": ev.get("date"),
                            "local_time": ev.get("time"),
                            "timezone": ev.get("timezone"),
                            "notes": ev.get("notes") or "",
                        }
                    )
                )
            except ValidationError:
                plan.skipped["applications"]["An event was malformed and left out"] += 1
        return {
            "identity": application_identity(body.employer, body.role_title, body.applied_on, body.link),
            "body": body,
            "events": events[:50],
            "archived": bool(row.get("archived")),
        }

    # --- preview ----------------------------------------------------------------------------------

    def _check_accepted_actions(self, row: dict, plan: _Plan, data: dict) -> dict | str:
        """An accepted improvement from a version 2 file: its interview must be one of this
        account's (interviews aren't restored, so one from elsewhere would point at nothing); its id
        is kept unless something else already has it; its occurrences come with it, from the file's
        schedule entries by id. Nothing about done-ness is invented: marks of done are as the file
        says, on dates the file gives."""
        if data.get("export_version") != 2 or not isinstance(row.get("id"), str):
            return "Restored from a version 2 export only (it keeps the ids that link it)"
        raw_src = row.get("source")
        src: dict[str, Any] = raw_src if isinstance(raw_src, dict) else {}
        interview, key = src.get("interview"), src.get("key")
        if (
            src.get("kind") != "interview_improvement"
            or not isinstance(interview, str)
            or not isinstance(key, str)
        ):
            return "Its suggestion isn't named (an export from before version 2 kept it)"
        if len(row["id"]) > 36 or len(interview) > 36 or len(key) > 200:
            return "Not a valid record"
        if (
            self.db.scalar(
                select(func.count())
                .select_from(PracticeSession)
                .where(PracticeSession.id == interview, PracticeSession.user_id == self.user.id)
            )
            or 0
        ) == 0:
            return "Its interview isn't in this account, so there's nothing to link it to"
        title = _s(row.get("title"))[:200]
        if not title:
            return "Not a valid record"
        recurrence = "weekly" if row.get("recurrence") == "weekly" else "once"
        entries = {
            e.get("id"): e
            for e in ((data.get("schedule") or {}).get("entries") or [])
            if isinstance(e, dict) and e.get("kind") == "accepted_action"
        }
        occurrences = []
        for o in (row.get("occurrences") or [])[:MAX_OCCURRENCES]:
            if not isinstance(o, dict) or not isinstance(o.get("schedule_entry"), str):
                continue
            e = entries.get(o["schedule_entry"], {})
            try:
                on = datetime.fromisoformat(str(o.get("date"))).date()
            except ValueError:
                continue
            occurrences.append(
                {
                    "id": o["schedule_entry"][:36],
                    "on_date": on,
                    "all_day": bool(e.get("all_day", True)) if e else True,
                    "local_time": e.get("time") if isinstance(e.get("time"), str) else None,
                    "timezone": e.get("timezone") if isinstance(e.get("timezone"), str) else None,
                    "duration_min": e.get("duration_min") if isinstance(e.get("duration_min"), int) else 30,
                    "status": "cancelled" if o.get("status") == "cancelled" else "scheduled",
                    "completed_at": _when(o.get("completed_at")) if recurrence == "weekly" else None,
                }
            )
        raw_reuse = row.get("requirement_reuse")
        reuse: dict[str, Any] = raw_reuse if isinstance(raw_reuse, dict) else {}
        return {
            "identity": action_identity("interview_improvement", interview, key),
            "id": row["id"],
            "interview": interview,
            "key": key,
            "title": title,
            "notes": _s(row.get("notes"))[:4000],
            "recurrence": recurrence,
            "done_at": _when(row.get("done_at")) if recurrence == "once" else None,
            "archived_at": _when(row.get("archived_at")),
            "practice": row.get("practice") if isinstance(row.get("practice"), str) else None,
            "source": {
                "label": _s(src.get("improvement"))[:200] or title,
                "why": _s(src.get("feedback"))[:2000],
                "versions": [
                    {"question": v["question"], "version": v["version"]}
                    for v in src.get("question_versions") or []
                    if isinstance(v, dict)
                    and isinstance(v.get("question"), str)
                    and isinstance(v.get("version"), int)
                ],
                "interview_title": _s(src.get("interview_title"))[:200] or "An interview",
                "interview_date": src.get("interview_date")
                if isinstance(src.get("interview_date"), str)
                else None,
                "practice_label": src.get("practice_label")
                if isinstance(src.get("practice_label"), str)
                else None,
            },
            "reuse": {k: v for k, v in reuse.items() if isinstance(k, str) and isinstance(v, dict)},
            "occurrences": occurrences,
        }

    def _add_accepted_actions(self, item: dict) -> tuple[str, str, str]:
        from app.services.schedule import Schedule

        uid = self.user.id
        # Its own id, unless something else has it (then a new one: nothing about the other is said).
        aid = item["id"] if self.db.get(AcceptedAction, item["id"]) is None else None
        mine = set(
            self.db.scalars(
                select(TargetRequirement.id)
                .join(RoleTarget, RoleTarget.id == TargetRequirement.target_id)
                .where(RoleTarget.user_id == uid, TargetRequirement.id.in_(list(item["reuse"]) or [""]))
            )
        )
        a = AcceptedAction(
            **({"id": aid} if aid else {}),
            user_id=uid,
            source_kind="interview_improvement",
            source_id=item["interview"],
            source_key=item["key"],
            source={k: v for k, v in item["source"].items() if v is not None},
            title=item["title"],
            notes=item["notes"],
            practice_href=item["practice"],
            recurrence=item["recurrence"],
            done_at=item["done_at"],
            archived_at=item["archived_at"],
            requirement_reuse={k: v for k, v in item["reuse"].items() if k in mine} or None,
        )
        self.db.add(a)
        self.db.flush()
        schedule = Schedule(self.db, self.user)
        made: list[ScheduleEntry] = []
        for o in item["occurrences"]:
            e = ScheduleEntry(
                **({"id": o["id"]} if self.db.get(ScheduleEntry, o["id"]) is None else {}),
                user_id=uid,
                uid=f"{uuid.uuid4()}@codecoach",
                kind="accepted_action",
                ref=a.id,
                title=a.title,
                duration_min=max(5, min(int(o["duration_min"]), 600)),
                notes="",
                status=o["status"],
                sequence=0,
                completed_at=o["completed_at"],
            )
            try:
                schedule._apply_time(e, o["on_date"], o["all_day"], o["local_time"], o["timezone"], None)
            except AppError:
                schedule._apply_time(e, o["on_date"], True, None, None, None)  # a time it can't read: all day
            self.db.add(e)
            made.append(e)
        self.db.flush()
        return "accepted_action", a.id, action_full(a, made)

    def _already(self, sha: str, categories: list[str]) -> ImportBatch | None:
        rows = self.db.scalars(
            select(ImportBatch).where(
                ImportBatch.user_id == self.user.id,
                ImportBatch.file_sha256 == sha,
                ImportBatch.status == "applied",
            )
        )
        return next((b for b in rows if sorted(b.categories) == categories), None)

    def preview(self, raw: bytes) -> RestorePreview:
        data = self.parse(raw)
        plan = self._plan(data)
        profile: dict = data["profile"] if isinstance(data.get("profile"), dict) else {}
        sha = hashlib.sha256(raw).hexdigest()
        return RestorePreview(
            export_version=data["export_version"],
            exported_at=str(data.get("exported_at") or "") or None,
            file_sha256=sha,
            from_other_account=bool(profile.get("id")) and profile.get("id") != self.user.id,
            categories=[self._category(k, plan) for k in CATEGORIES],
            not_restored=plan.unsupported,
            ignored_fields=plan.ignored_fields,
            previous=[
                self._batch_out(b)
                for b in self.db.scalars(
                    select(ImportBatch)
                    .where(ImportBatch.user_id == self.user.id, ImportBatch.file_sha256 == sha)
                    .order_by(ImportBatch.created_at)
                )
            ],
        )

    @staticmethod
    def _category(key: str, plan: _Plan) -> RestoreCategory:
        adds = plan.adds[key]
        linkless = sum(1 for a in adds if a.get("link_note"))
        skipped = [RestoreSkip(reason=r, count=n) for r, n in plan.skipped[key].items() if n]
        if linkless:
            skipped.append(
                RestoreSkip(
                    reason="Added, but the content they pointed to isn't in the library, so the link is left out",
                    count=linkless,
                )
            )
        samples = []
        for a in adds[:5]:
            b = a.get("body")
            samples.append(
                getattr(b, "title", None)
                or getattr(b, "role_title", None)
                or a.get("ref")
                or a.get("title")
                or ""
            )
        return RestoreCategory(
            key=key,
            label=CATEGORIES[key],
            found=plan.found[key],
            new=len(adds),
            duplicates=plan.duplicates[key],
            skipped=skipped,
            samples=[s for s in samples if s],
        )

    # --- applying ---------------------------------------------------------------------------------

    def apply(self, raw: bytes, categories: list[str]) -> tuple[RestoreBatch, bool]:
        """Returns (batch, created). The same file and categories again returns the first batch."""
        chosen = sorted({c for c in categories if c in CATEGORIES})
        if not chosen:
            raise AppError("Choose at least one kind of record to restore.", code="nothing_chosen")
        data = self.parse(raw)
        sha = hashlib.sha256(raw).hexdigest()
        done = self._already(sha, chosen)
        if done is not None:
            return self._batch_out(done), False
        plan = self._plan(data)
        batch = ImportBatch(
            user_id=self.user.id,
            file_sha256=sha,
            export_version=data["export_version"],
            categories=chosen,
            status="applied",
            counts={},
        )
        try:
            self.db.add(batch)
            self.db.flush()
            self._limits(plan, chosen)
            for cat in chosen:
                for item in plan.adds[cat]:
                    kind, rid, full = getattr(self, f"_add_{cat}")(item)
                    self.db.add(
                        ImportedRecord(
                            batch_id=batch.id,
                            user_id=self.user.id,
                            kind=kind,
                            record_id=rid,
                            fingerprint=full,
                        )
                    )
                batch.counts = {
                    **batch.counts,
                    cat: {
                        "added": len(plan.adds[cat]),
                        "duplicates": plan.duplicates[cat],
                        "skipped": sum(plan.skipped[cat].values()),
                    },
                }
            self.db.commit()  # one transaction: everything above, or nothing
        except AppError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            failed = ImportBatch(
                user_id=self.user.id,
                file_sha256=sha,
                export_version=data["export_version"],
                categories=chosen,
                status="failed",
                counts={},
            )
            self.db.add(failed)
            self.db.commit()
            raise AppError(
                "The restore stopped partway, so nothing was changed. You can try again.",
                code="restore_failed",
            ) from None
        return self._batch_out(batch), True

    def _limits(self, plan: _Plan, chosen: list[str]) -> None:
        uid = self.user.id
        checks = {
            "notes": (MAX_NOTES, select(func.count()).select_from(Note).where(Note.user_id == uid)),
            "stories": (
                MAX_STORIES,
                select(func.count()).select_from(ExperienceEntry).where(ExperienceEntry.user_id == uid),
            ),
            "applications": (
                MAX_APPLICATIONS,
                select(func.count()).select_from(Application).where(Application.user_id == uid),
            ),
        }
        for cat, (limit, stmt) in checks.items():
            if cat in chosen and (self.db.scalar(stmt) or 0) + len(plan.adds[cat]) > limit:
                raise AppError(
                    f"Restoring these {CATEGORIES[cat].lower()} would go over the limit of {limit}. Nothing was changed.",
                    code="over_limit",
                )

    def _add_notes(self, item: dict) -> tuple[str, str, str]:
        b: NoteIn = item["body"]
        src = item["source"] or {}
        n = Note(
            user_id=self.user.id,
            title=b.title,
            body=b.body,
            reflection=b.reflection,
            tags=clean_tags(b.tags),
            excerpt=b.excerpt,
            excerpt_kind="quote" if b.excerpt else None,
            archived=item["archived"],
            pinned=False,
            source_type=src.get("type"),
            source_id=src.get("id"),
            source_track=src.get("track"),
            source_version=None if src.get("version") is None else str(src.get("version")),
            source_title=src.get("title"),
        )
        self.db.add(n)
        self.db.flush()
        if src.get("type") in ("question", "problem", "lesson") and src.get("reviews"):
            ref = SourceRef(
                kind=src["type"],
                id=src["id"],
                track=src.get("track"),
                captured=int(src["version"]) if src.get("version") else None,
            )
            fresh = SourceFreshness(self.db, self.user.id, NOTE)
            fresh.restore_reviews(n.id, ref, src["reviews"], fresh.problems_for_refs([ref]))
        return "note", n.id, note_full(n)

    def _add_stories(self, item: dict) -> tuple[str, str, str]:
        b: StoryCreate = item["body"]
        e = ExperienceEntry(
            user_id=self.user.id,
            archived=item["archived"],
            revision=1,
            **{k: v for k, v in b.model_dump(exclude_none=True).items() if hasattr(ExperienceEntry, k)},
        )
        self.db.add(e)
        self.db.flush()
        record_revision(self.db, e, "created", bump=False)
        return "story", e.id, story_full(e)

    def _add_bookmarks(self, item: dict) -> tuple[str, str, str]:
        b = Bookmark(
            user_id=self.user.id,
            item_type=item["kind"],
            track=item["track"],
            ref_id=item["ref"],
            content_version=item["version"],
        )
        self.db.add(b)
        self.db.flush()
        if item.get("reviews") and item["kind"] in ("question", "problem"):
            ref = SourceRef(
                kind=item["kind"], id=item["ref"], track=item["track"] or None, captured=item["version"]
            )
            fresh = SourceFreshness(self.db, self.user.id, SAVED)
            fresh.restore_reviews(b.id, ref, item["reviews"], fresh.problems_for_refs([ref]))
        return "bookmark", b.id, item["identity"]

    def _add_applications(self, item: dict) -> tuple[str, str, str]:
        b: ApplicationCreate = item["body"]
        a = Application(
            user_id=self.user.id,
            employer=b.employer.strip(),
            role_title=b.role_title.strip(),
            link=b.link,
            applied_on=b.applied_on,
            stage=b.stage,
            next_action=(b.next_action or "").strip(),
            next_action_due=b.next_action_due,
            notes=(b.notes or "").strip(),
            story_ids=[],
            archived=item["archived"],
        )
        a.history.append(
            ApplicationStageChange(
                from_stage=None,
                to_stage=b.stage,
                note="Restored from a backup",
                role_title=a.role_title,
                employer=a.employer,
            )
        )
        for ev in item["events"]:
            starts = None
            if ev.on_date and ev.local_time and ev.timezone:
                try:
                    starts = local_to_utc(ev.on_date, ev.local_time, ev.timezone, ev.fold)
                except AppError:
                    starts = (
                        None  # an ambiguous or invalid time keeps its date and words; no instant is guessed
                    )
            a.events.append(
                ApplicationEvent(
                    kind=ev.kind,
                    title=ev.title.strip(),
                    on_date=ev.on_date,
                    local_time=ev.local_time if starts else None,
                    timezone=ev.timezone if starts else None,
                    starts_at=starts,
                    notes=ev.notes.strip(),
                )
            )
        self.db.add(a)
        self.db.flush()
        return "application", a.id, application_full(a)

    # --- batches ----------------------------------------------------------------------------------

    @staticmethod
    def _batch_out(b: ImportBatch) -> RestoreBatch:
        return RestoreBatch(
            id=b.id,
            status=b.status,
            categories=b.categories,
            counts=b.counts,
            removal=b.removal,
            created_at=b.created_at,
            removed_at=b.removed_at,
        )

    def batches(self) -> list[RestoreBatch]:
        rows = self.db.scalars(
            select(ImportBatch)
            .where(ImportBatch.user_id == self.user.id)
            .order_by(ImportBatch.created_at.desc())
        )
        return [self._batch_out(b) for b in rows]

    def remove(self, batch_id: str) -> RestoreBatch:
        """Remove what a batch added, except anything edited since (or already gone)."""
        b = self.db.get(ImportBatch, batch_id)
        if b is None or b.user_id != self.user.id:
            raise NotFoundError("Restore not found")
        if b.status != "applied":
            return self._batch_out(b)
        removed = kept = gone = 0
        for r in self.db.scalars(select(ImportedRecord).where(ImportedRecord.batch_id == b.id)):
            row: Any = None
            if r.kind == "note":
                row = self.db.get(Note, r.record_id)
                current = note_full(row) if row is not None and row.deleted_at is None else None
            elif r.kind == "story":
                row = self.db.get(ExperienceEntry, r.record_id)
                current = story_full(row) if row is not None else None
            elif r.kind == "bookmark":
                row = self.db.get(Bookmark, r.record_id)
                current = r.fingerprint if row is not None else None
            elif r.kind == "accepted_action":
                row = self.db.get(AcceptedAction, r.record_id)
                occ = self._occurrences(r.record_id) if row is not None else []
                current = action_full(row, occ) if row is not None else None
            else:
                row = self.db.get(Application, r.record_id)
                current = application_full(row) if row is not None else None
            if row is None or current is None or getattr(row, "user_id", None) != self.user.id:
                gone += 1
            elif current != r.fingerprint:
                kept += 1  # edited since: never rolled back
            else:
                if r.kind == "note":
                    row.deleted_at = datetime.now(UTC)  # the notebook's own soft delete
                elif r.kind == "bookmark":
                    forget(self.db, self.user.id, SAVED.kind, [row.id])  # its restored reviews too
                    self.db.delete(row)
                elif r.kind == "accepted_action":
                    for e in self._occurrences(row.id):
                        self.db.delete(e)
                    self.db.delete(row)
                else:
                    self.db.delete(row)
                removed += 1
        b.status, b.removed_at = "removed", datetime.now(UTC)
        b.removal = {"removed": removed, "kept_edited": kept, "already_gone": gone}
        self.db.commit()
        return self._batch_out(b)

    def _occurrences(self, action_id: str) -> list[ScheduleEntry]:
        return list(
            self.db.scalars(
                select(ScheduleEntry).where(
                    ScheduleEntry.user_id == self.user.id,
                    ScheduleEntry.kind == "accepted_action",
                    ScheduleEntry.ref == action_id,
                )
            )
        )

    def export(self) -> list[dict]:
        return [
            {
                "id": b.id,
                "status": b.status,
                "categories": b.categories,
                "counts": b.counts,
                "removal": b.removal,
                "created_at": b.created_at.isoformat(),
                "removed_at": b.removed_at.isoformat() if b.removed_at else None,
            }
            for b in self.db.scalars(select(ImportBatch).where(ImportBatch.user_id == self.user.id))
        ]

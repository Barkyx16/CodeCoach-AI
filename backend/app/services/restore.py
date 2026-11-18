"""Restoring your own data from a CodeCoach backup (the file the data export gives you).

The contract (see docs/BACKUP_FORMAT.md):

- A JSON object with `export_version` 1 or 2, at most 5 MB. Nothing else is accepted: no archives, no
  paths, nothing executable.
- Additive only, into the signed-in account. Ids, account details and timestamps in the file are
  never trusted: records get new ids and belong to whoever is signed in.
- Restorable: notes, stories, bookmarks, and applications with their events; from a version 2
  file (which keeps ids), accepted improvements with their occurrences, under their own ids
  (Volume 14, prompt 5), and collections with their items in order, each item's version and
  reviews, under theirs (Volume 15, prompt 6); and which questions were saved for review, each as a
  new item starting afresh (Volume 20, prompt 1: no ladder step, due date, score, review count or point
  comes from a file). Everything else is listed as not restored, with the reason: account details and roles; practice results and any
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
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.questions import content_key, get_question
from app.content import state as content_state
from app.drills import BY_ID as DRILLS
from app.errors import AppError, NotFoundError
from app.models import (
    AcceptedAction,
    Application,
    ApplicationEvent,
    ApplicationStageChange,
    Bookmark,
    CollectionItem,
    DismissedSuggestion,
    ExperienceEntry,
    ImportBatch,
    ImportedRecord,
    ListedName,
    Note,
    PracticeCollection,
    PracticeSession,
    Problem,
    ReviewItem,
    RoleTarget,
    ScheduleEntry,
    SourceReview,
    TargetRequirement,
    User,
)
from app.schemas.applications import ApplicationCreate, ApplicationEventIn
from app.schemas.notes import NoteIn, SourceIn
from app.schemas.restore import RestoreBatch, RestoreCategory, RestorePreview, RestoreSkip, RestoreUnsupported
from app.schemas.stories import StoryCreate
from app.services.applications import MAX_APPLICATIONS
from app.services.dismissals import parse as parse_suggestion
from app.services.explore import IN_COLLECTION, MAX_COLLECTIONS, MAX_ITEMS, SAVED, collection_name_key
from app.services.listed_names import MAX_NAMES
from app.services.listed_names import clean as clean_name
from app.services.listed_names import fold as fold_name
from app.services.note_freshness import (
    NOTE,
    SourceFreshness,
    SourceRef,
    forget,
    known_version,
    problem_versions,
)
from app.services.notes import MAX_NOTES, Notebook, clean_tags
from app.services.review_queue import LADDER
from app.services.review_queue import MAX_ACTIVE as MAX_QUEUE
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
    "collections": "Collections, with their items in order (version 2 files)",
    # Volume 16, prompt 4: what the account chose, not only what it made.
    "listed_names": "Names you listed: replaced with [name] wherever something leaves the app",
    "dismissed_suggestions": "Suggestions you dismissed: not offered again, on any device",
    # Volume 20, prompt 1: which questions you saved for review (a choice, not a result).
    "review_queue": "Questions saved for review, each starting afresh",
}
# What a category brings back and what it doesn't, said in the preview when it needs saying.
NOTES: dict[str, str] = {
    "review_queue": (
        f"Only which questions you saved comes back. Each starts its review ladder afresh, first due "
        f"{LADDER[0]} day after the restore, as a newly saved question is. Ladders, due dates, scores, review "
        "counts and the points each was saved for aren't restored: they come from answers, and a file can't "
        "prove those happened here."
    ),
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
    "shares": _EXPOSE,
    "shared_feedback": _EXPOSE,
    "sessions": _EXPOSE,
    "schedule": _EXPOSE,
    "content_reports": "Reports you sent stay with the original account's history.",
    "lab_reveals": "When you opened a debugging exercise's explanation isn't restored: it describes attempts that stay with the original account.",
    "comparison_openings": "When you opened a sample-answer lesson's explanation isn't restored: it describes readings that stay with the original account.",
    "test_design_reveals": "When a test-design exercise's faulty versions were shown isn't restored: it describes runs that stay with the original account.",
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


def collection_full(c: PracticeCollection, reviews: list[tuple[str, int]]) -> str:
    """A collection as restored: its name, queue, and each item in order with its version, its mark
    of done and its reviews. Any change since (renamed, reordered, an item added, removed, marked done
    or reviewed) keeps it when the restore is removed."""
    return _sha(
        [
            c.name,
            c.queue_position,
            [
                [i.item_type, i.track, i.ref_id, i.position, i.content_version, bool(i.queue_done_at)]
                for i in sorted(c.items, key=lambda i: i.position)
            ],
            sorted(reviews),
        ]
    )


def review_identity(track: str, question_id: str) -> str:
    """A question saved for review is the same one by its career and question, whatever its ladder."""
    return _sha(["review", track, question_id])


def review_full(r: ReviewItem) -> str:
    """A saved question as restored: fresh. Practised, snoozed, given a point or removed since, it's
    changed, and removing the restore keeps it."""
    return _sha(
        [
            r.track,
            r.question_id,
            r.step,
            r.reviews,
            r.last_score,
            str(r.due_at),
            r.snoozed,
            r.criterion,
            r.points,
            r.removed_points,
            r.removed,
        ]
    )


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
    # A collection's items left out or kept as unavailable, by reason (collections themselves are
    # counted in `skipped`).
    item_notes: Counter = field(default_factory=Counter)
    names: set[str] = field(default_factory=set)  # collection names this file would add


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
        collections = self.db.execute(
            select(PracticeCollection.id, PracticeCollection.name).where(PracticeCollection.user_id == uid)
        ).all()
        self._collection_names = {collection_name_key(n) for _, n in collections}
        names = self.db.scalars(select(ListedName.folded).where(ListedName.user_id == uid)).all()
        self._listed_count = len(names)
        dismissed = self.db.scalars(
            select(DismissedSuggestion.key).where(DismissedSuggestion.user_id == uid)
        ).all()
        queue = self.db.execute(
            select(ReviewItem.track, ReviewItem.question_id, ReviewItem.removed).where(
                ReviewItem.user_id == uid
            )
        ).all()
        active = {review_identity(t, q) for t, q, removed in queue if not removed}
        # Taken out of the queue here (and not saved again): a file doesn't put it back.
        self._queue_removed = {review_identity(t, q) for t, q, removed in queue if removed} - active
        return {
            "review_queue": active,
            "listed_names": set(names),
            "dismissed_suggestions": set(dismissed),
            "collections": {f"id:{c}" for c, _ in collections},
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
        self._existing_cache = seen
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
                    else self._check_collections(row, plan, data)
                    if cat == "collections"
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
        # The list of names holds up to MAX_NAMES: the rest are left out and counted, never named.
        room = max(0, MAX_NAMES - self._listed_count)
        if len(plan.adds["listed_names"]) > room:
            over = len(plan.adds["listed_names"]) - room
            plan.adds["listed_names"] = plan.adds["listed_names"][:room]
            plan.skipped["listed_names"][f"Over the list's limit of {MAX_NAMES} names"] += over
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

    def _check_collections(self, row: dict, plan: _Plan, data: dict) -> dict | str:
        """A collection from a version 2 file, with its items in their order. Its id (and its items')
        is kept when the file is this account's and no one has it; a collection already here (the
        same id) is never overwritten, and one with the same name is skipped and said. An item whose
        content left the library entirely is left out with the reason (never swapped for a similar
        one); a retired one is kept, shown as unavailable as the collection shows it today. Items
        name library content, not bookmarks or anything else of an account, so nothing in another
        account is ever linked."""
        if data.get("export_version") != 2:
            return "Restored from a version 2 export only (it keeps the ids and the order)"
        plan.ignored_fields += len(
            set(row) - {"id", "name", "queue_position", "queue_started_at", "created_at", "items"}
        )
        name = " ".join(_s(row.get("name")).split())[:80]
        raw_items = row.get("items")
        if not name or not isinstance(raw_items, list):
            return "Not a valid record"
        cid = row.get("id") if isinstance(row.get("id"), str) and 0 < len(row["id"]) <= 36 else None
        if cid is not None and f"id:{cid}" in self._mine("collections"):
            return {"identity": f"id:{cid}"}  # already here: counted as a duplicate, never overwritten
        key = collection_name_key(name)
        if key in self._collection_names or key in plan.names:
            return "A collection with this name is already here (it's never overwritten or merged)"
        ordered = sorted(
            (
                (r.get("position") if isinstance(r.get("position"), int) else i, i, r)
                for i, r in enumerate(raw_items)
                if isinstance(r, dict)
            ),
            key=lambda t: (t[0], t[1]),
        )
        items: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        problems_now = problem_versions(
            self.db,
            {
                r["item"]
                for _, _, r in ordered
                if r.get("type") == "problem" and isinstance(r.get("item"), str)
            },
        )
        for _, _, r in ordered:
            got = self._collection_item(r, problems_now)
            if isinstance(got, str):
                plan.item_notes[f"Items left out: {got}"] += 1
                continue
            k = (got["kind"], got["track"], got["ref"])
            if k in seen:
                plan.item_notes["Items left out: the same item twice in one collection"] += 1
                continue
            if len(items) >= MAX_ITEMS:
                plan.item_notes[f"Items left out: more than {MAX_ITEMS} in one collection"] += 1
                continue
            seen.add(k)
            if got.pop("retired"):
                plan.item_notes["Items kept but shown as unavailable: retired from the library"] += 1
            items.append(got)
        plan.names.add(key)
        qp = row.get("queue_position")
        return {
            "identity": f"id:{cid}" if cid else _sha(["collection", key]),
            "id": cid,
            "title": name,
            "queue_position": max(0, min(qp, len(items) - 1)) if isinstance(qp, int) and items else 0,
            "queue_started_at": _when(row.get("queue_started_at")),
            "items": items,
        }

    def _check_listed_names(self, row: dict, plan: _Plan) -> dict | str:
        """A name the learner listed, by its letter-case-free form: the same name in any case is the
        one already here. Only counts are ever said about names; they're never in a log, a trace or
        the restore's record (which keeps a digest)."""
        plan.ignored_fields += len(set(row) - {"name", "created_at", "updated_at"})
        try:
            text = clean_name(_s(row.get("name")))
        except AppError:
            return "Not a name the list can hold"
        return {"identity": fold_name(text), "name": text, "created_at": _when(row.get("created_at"))}

    def _check_dismissed_suggestions(self, row: dict, plan: _Plan) -> dict | str:
        """A dismissal by its suggestion's key, checked against the suggestions that exist now: one
        whose question was retired or whose pair was removed is left out, never matched to a similar
        one."""
        plan.ignored_fields += len(set(row) - {"key", "kind", "offered_on", "dismissed_at"})
        key = _s(row.get("key"))
        try:
            parsed = parse_suggestion(key)
        except AppError:
            return "The suggestion it dismissed isn't offered any more (a retired question or a removed pair)"
        return {
            "identity": key,
            "kind": parsed.kind,
            "offered_on": (_s(row.get("offered_on")) or None),
            "dismissed_at": _when(row.get("dismissed_at")),
        }

    def _check_review_queue(self, row: dict, plan: _Plan) -> dict | str:
        """Which question was saved for review, and only that (Volume 20, prompt 1): its ladder, due date,
        score, review count and points are read from nothing, so an edited file can't create progress.
        A question removed from the queue in the file, or here, stays removed."""
        plan.ignored_fields += len(
            set(row)
            - {
                "career",
                "question",
                "due_at",
                "step",
                "last_score",
                "reviews",
                "removed",
                "removed_at",
                "created_at",
                "saved_for_point",
                "saved_for_points",
                "points_removed",
                "recounted",
                "left_out_disputed",
            }
        )
        track, ref = row.get("career"), row.get("question")
        if not isinstance(track, str) or not isinstance(ref, str) or not track or not ref:
            return "Malformed"
        q = get_question(track, ref) if track in CATALOG else None
        if q is None:
            return "The question isn't in the library (it's never swapped for a similar one)"
        if row.get("removed") is True:
            return "Removed from the queue when the file was made: left out"
        identity = review_identity(track, ref)
        if identity in self._queue_removed:
            return "Removed from your queue here: left as it is (put it back from Removed recently)"
        return {"identity": identity, "track": track, "question": ref, "title": q.title}

    def _add_review_queue(self, item: dict) -> tuple[str, str, str]:
        """A new item, as saving the question now would make it: first rung, first due date, no score."""
        now = datetime.now(UTC)
        row = ReviewItem(
            user_id=self.user.id,
            track=item["track"],
            question_id=item["question"],
            step=0,
            due_at=now + timedelta(days=LADDER[0]),
            scheduled_at=now,
            created_at=now,
        )
        self.db.add(row)
        self.db.flush()
        return "review_item", row.id, review_full(row)

    def _add_listed_names(self, item: dict) -> tuple[str, str, str]:
        now = datetime.now(UTC)
        row = ListedName(
            user_id=self.user.id,
            name=item["name"],
            folded=item["identity"],
            created_at=item["created_at"] or now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.flush()
        return "listed_name", row.id, _sha(["listed_name", row.folded])  # a digest: never the name

    def _add_dismissed_suggestions(self, item: dict) -> tuple[str, str, str]:
        row = DismissedSuggestion(
            user_id=self.user.id,
            key=item["identity"],
            kind=item["kind"],
            offered_on=(item["offered_on"] or "")[:200] or None,
            dismissed_at=item["dismissed_at"] or datetime.now(UTC),
        )
        self.db.add(row)
        self.db.flush()
        return "dismissal", row.id, _sha(["dismissal", row.key])

    def _mine(self, cat: str) -> set[str]:
        return self._existing_cache[cat]

    def _collection_item(self, r: dict, problems_now: dict[str, int]) -> dict | str:
        kind, track, ref = r.get("type"), r.get("career") or "", r.get("item")
        if (
            kind not in ("question", "problem", "drill")
            or not isinstance(ref, str)
            or not isinstance(track, str)
        ):
            return "not a valid item"
        retired = False
        version = None
        if kind == "question":
            if (track not in CATALOG) or get_question(track, ref) is None:
                return "the question isn't in the library (it's never swapped for a similar one)"
            retired = ("question", content_key(track, ref)) in content_state.current().retired
            version = known_version(
                SourceRef(kind="question", id=ref, track=track, captured=None), r.get("version"), {}
            )
        elif kind == "problem":
            if (
                ref not in problems_now
                and self.db.scalar(select(Problem.id).where(Problem.slug == ref)) is None
            ):
                return "the problem isn't in the library"
            retired = ("problem", ref) in content_state.current().retired
            version = known_version(
                SourceRef(kind="problem", id=ref, track=None, captured=None), r.get("version"), problems_now
            )
        else:
            track = ""
            if ref not in DRILLS:
                return "the drill isn't offered any more"
        if kind != "question":
            track = ""
        done = _when(r.get("queue_done_at"))
        now = datetime.now(UTC)
        iid = r.get("id") if isinstance(r.get("id"), str) and 0 < len(r["id"]) <= 36 else None
        return {
            "id": iid,
            "kind": kind,
            "track": track,
            "ref": ref,
            "version": version,
            "done_at": min(done, now) if done else None,
            "reviews": r.get("source_reviews") if kind in ("question", "problem") else None,
            "retired": retired,
        }

    def _add_collections(self, item: dict) -> tuple[str, str, str]:
        uid = self.user.id
        # Its own id when the file is this account's and no one else has it (nothing about another
        # account's is said or used); otherwise a new one.
        own = self._from_self

        def insert(model: Any, rid: str | None, **fields: Any) -> Any:
            """With the file's id when it's free; a clash (even with a row this account can't see)
            gets a new id, and nothing about the other is said."""
            if own and rid and self.db.get(model, rid) is None:
                try:
                    with self.db.begin_nested():
                        row = model(id=rid, **fields)
                        self.db.add(row)
                        self.db.flush()
                    return row
                except IntegrityError:
                    pass
            row = model(**fields)
            self.db.add(row)
            self.db.flush()
            return row

        c = insert(
            PracticeCollection,
            item["id"],
            user_id=uid,
            name=item["title"],
            queue_position=item["queue_position"],
            queue_started_at=item["queue_started_at"],
        )
        made: list[tuple[CollectionItem, dict]] = []
        for pos, it in enumerate(item["items"]):
            row = insert(
                CollectionItem,
                it["id"],
                collection_id=c.id,
                item_type=it["kind"],
                track=it["track"],
                ref_id=it["ref"],
                position=pos,
                content_version=it["version"],
                queue_done_at=it["done_at"],
            )
            made.append((row, it))
        refs = [
            SourceRef(kind=it["kind"], id=it["ref"], track=it["track"] or None, captured=it["version"])
            for _, it in made
            if it["reviews"]
        ]
        if refs:
            fresh = SourceFreshness(self.db, uid, IN_COLLECTION)
            problems = fresh.problems_for_refs(refs)
            for row, it in made:
                if it["reviews"]:
                    ref = SourceRef(
                        kind=it["kind"], id=it["ref"], track=it["track"] or None, captured=it["version"]
                    )
                    fresh.restore_reviews(row.id, ref, it["reviews"], problems)
        self.db.flush()
        self.db.refresh(c)
        return "collection", c.id, collection_full(c, self._item_reviews(c))

    def _item_reviews(self, c: PracticeCollection) -> list[tuple[str, int]]:
        ids = {i.id: i.position for i in c.items}
        if not ids:
            return []
        rows = self.db.execute(
            select(SourceReview.holder_id, SourceReview.to_revision).where(
                SourceReview.user_id == self.user.id,
                SourceReview.holder_kind == IN_COLLECTION.kind,
                SourceReview.holder_id.in_(list(ids)),
            )
        ).all()
        return [(str(ids[h]), v) for h, v in rows]

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
        if key == "collections":
            skipped += [RestoreSkip(reason=r, count=n) for r, n in plan.item_notes.items() if n]
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
            note=NOTES.get(key),
        )

    # --- applying ---------------------------------------------------------------------------------

    def apply(self, raw: bytes, categories: list[str]) -> tuple[RestoreBatch, bool]:
        """Returns (batch, created). The same file and categories again returns the first batch."""
        chosen = sorted({c for c in categories if c in CATEGORIES})
        if not chosen:
            raise AppError("Choose at least one kind of record to restore.", code="nothing_chosen")
        data = self.parse(raw)
        raw_profile = data.get("profile")
        profile: dict = raw_profile if isinstance(raw_profile, dict) else {}
        self._from_self = bool(profile) and profile.get("id") == self.user.id
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
            "collections": (
                MAX_COLLECTIONS,
                select(func.count()).select_from(PracticeCollection).where(PracticeCollection.user_id == uid),
            ),
            "review_queue": (
                MAX_QUEUE,
                select(func.count())
                .select_from(ReviewItem)
                .where(ReviewItem.user_id == uid, ReviewItem.removed.is_(False)),
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
        kept_collections: list[str] = []
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
            elif r.kind == "collection":
                row = self.db.get(PracticeCollection, r.record_id)
                current = collection_full(row, self._item_reviews(row)) if row is not None else None
            elif r.kind == "listed_name":
                row = self.db.get(ListedName, r.record_id)  # renamed since: kept
                current = _sha(["listed_name", row.folded]) if row is not None else None
            elif r.kind == "dismissal":
                row = self.db.get(DismissedSuggestion, r.record_id)  # offered again since: already gone
                current = _sha(["dismissal", row.key]) if row is not None else None
            elif r.kind == "review_item":
                # Removed from the queue since: already gone. Practised, snoozed, given a point or
                # planned in the schedule since: changed, so kept.
                row = self.db.get(ReviewItem, r.record_id)
                current = review_full(row) if row is not None and not row.removed else None
                if current is not None and self._scheduled(row.id):
                    current = "scheduled"
            else:
                row = self.db.get(Application, r.record_id)
                current = application_full(row) if row is not None else None
            if row is None or current is None or getattr(row, "user_id", None) != self.user.id:
                gone += 1
            elif current != r.fingerprint:
                kept += 1  # edited since: never rolled back
                if r.kind == "collection":
                    kept_collections.append(row.name)
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
                elif r.kind == "collection":
                    forget(self.db, self.user.id, IN_COLLECTION.kind, [i.id for i in row.items])
                    self.db.delete(row)  # its items with it
                else:
                    self.db.delete(row)
                removed += 1
        b.status, b.removed_at = "removed", datetime.now(UTC)
        b.removal = {"removed": removed, "kept_edited": kept, "already_gone": gone}
        if kept_collections:
            b.removal["kept_collections"] = sorted(kept_collections)  # changed since: kept, by name
        self.db.commit()
        return self._batch_out(b)

    def _scheduled(self, review_item_id: str) -> bool:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(ScheduleEntry)
                .where(
                    ScheduleEntry.user_id == self.user.id,
                    ScheduleEntry.kind == "review_item",
                    ScheduleEntry.ref == review_item_id,
                )
            )
            or 0
        ) > 0

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

"""Versioned job requirements (Volume 12, prompt 5; docs/REQUIREMENT_VERSIONS.md).

A requirement keeps one identity through its edits. A cosmetic edit (spacing, capitals,
punctuation) keeps its version and needs no review; a substantive edit makes the next version and
is recorded with its words. Added, removed and restored are recorded too, so a removed
requirement's history stays readable. History is only added to.

Similar wording may be suggested as "the same requirement", but only the learner's choice links
two: nothing is equated silently. Stories record the version they were linked to; a story linked to
an earlier wording says so, and reusing it for the current wording is a deliberate, recorded step.
Accepted improvements relate to a requirement through the question they practise (the same mapping
attempts use) and keep the version in effect when they were accepted, read from the history; they
can be reused for a newer wording the same deliberate way. Nothing is re-scored or re-linked
automatically.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers.skills import questions_by_skill
from app.errors import AppError, NotFoundError
from app.models import (
    AcceptedAction,
    ExperienceEntry,
    PracticeSession,
    RequirementVersion,
    RoleTarget,
    TargetRequirement,
    User,
)
from app.schemas.roles import (
    ActionLink,
    LinkedAction,
    LinkedStory,
    RequirementChange,
    RequirementHistoryEntry,
    RequirementLink,
    RequirementSetIn,
    RevisionPreview,
    SameAsSuggestion,
)

SUGGEST_AT = 0.5
_QUESTION_HREF = re.compile(r"^/careers/([a-z0-9-]+)/questions/([^/?#]+)")
_RETRY_HREF = re.compile(r"^/interviews/([^/]+)/retry/(\d+)$")
_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "your",
        "their",
        "at",
        "by",
        "or",
        "as",
        "is",
        "are",
        "be",
    ]
)


def normalize(text: str) -> str:
    """What a cosmetic edit can't change: the words, ignoring case, spacing and punctuation."""
    t = unicodedata.normalize("NFKC", text).casefold()
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def is_cosmetic(old: str, new: str) -> bool:
    return normalize(old) == normalize(new)


def _words(text: str) -> set[str]:
    return {w for w in normalize(text).split() if w not in _STOP}


def similarity(a: str, b: str) -> float:
    x, y = _words(a), _words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


class RequirementVersions:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self._rows: dict[str, list[RequirementVersion]] | None = None  # by requirement, per target read
        self._qids: dict[tuple[str, int | None], set[str]] = {}  # (requirement, version) -> questions

    # --- recording --------------------------------------------------------------------------------

    def _has_history(self, r: TargetRequirement) -> bool:
        return (
            self.db.scalar(
                select(RequirementVersion.id).where(RequirementVersion.requirement_id == r.id).limit(1)
            )
            is not None
        )

    def record(self, t: RoleTarget, r: TargetRequirement, state: str, *, same_as: str | None = None) -> None:
        self.db.add(
            RequirementVersion(
                user_id=self.user.id,
                target_id=t.id,
                requirement_id=r.id,
                version=r.version,
                state=state,
                category=r.category,
                text=r.text,
                skills=list(r.skills or []),
                set_revision=t.requirements_revision,
                same_as=same_as,
                created_at=datetime.now(UTC),
            )
        )

    def keep_original(self, t: RoleTarget, r: TargetRequirement) -> None:
        """Before the first recorded change, its words as they were: history from before versions
        were kept starts here, never made up."""
        if r.id and not self._has_history(r):
            self.record(t, r, "original")

    def edit(
        self,
        t: RoleTarget,
        r: TargetRequirement,
        *,
        text: str,
        category: str,
        skills: list[str] | None = None,
    ) -> str:
        """Apply one edit: 'unchanged', 'cosmetic' (same version) or 'changed' (the next version,
        recorded with the skills it maps to: `skills`, or the ones it had)."""
        text = text.strip()
        if text == r.text and category == r.category:
            return "unchanged"
        if category == r.category and is_cosmetic(r.text, text):
            r.text = text
            return "cosmetic"
        self.keep_original(t, r)
        r.version += 1
        r.text, r.category = text, category
        if skills is not None:
            r.skills = skills
        self.db.flush()
        self.record(t, r, "changed")
        return "changed"

    def set_removed(self, t: RoleTarget, r: TargetRequirement, removed: bool) -> str:
        if removed == r.removed:
            return "unchanged"
        self.keep_original(t, r)
        r.removed = removed
        self.record(t, r, "removed" if removed else "restored")
        return "removed" if removed else "restored"

    # --- the whole set: preview, then save --------------------------------------------------------

    def _check(self, t: RoleTarget, body: RequirementSetIn) -> dict[str, TargetRequirement]:
        by_id = {r.id: r for r in t.requirements}
        named = [i.id for i in body.items if i.id is not None]
        unknown = [i for i in named if i not in by_id]
        if unknown:
            # Another target's or another account's id reads the same as one that doesn't exist.
            raise NotFoundError("A requirement in this list isn't one of this target's.")
        if len(named) != len(set(named)) or set(named) != set(by_id):
            raise AppError(
                "Send every requirement of this target once (removed ones too), with any new ones.",
                code="incomplete_requirement_set",
            )
        for m in body.same_as:
            if not (0 <= m.index < len(body.items)) or body.items[m.index].id is not None:
                raise AppError("A suggested match must be for a new requirement.", code="bad_same_as")
            target = by_id.get(m.requirement_id)
            proposed = next((i for i in body.items if i.id == m.requirement_id), None)
            if target is None or proposed is None or not proposed.removed:
                raise AppError(
                    "A new requirement can only be matched to one being removed.", code="bad_same_as"
                )
        return by_id

    def preview(self, t: RoleTarget, body: RequirementSetIn) -> RevisionPreview:
        by_id = self._check(t, body)
        same = {m.index: m.requirement_id for m in body.same_as}
        stories = self._stories(t)
        actions: dict[str, list[LinkedAction]] = {}
        for linked, row, _ in self._action_pairs(t):
            actions.setdefault(linked, []).append(LinkedAction(id=row.id, title=row.title))
        changes: list[RequirementChange] = []
        counts = {"changed": 0, "added": 0, "removed": 0, "restored": 0, "unchanged": 0}
        for i, item in enumerate(body.items):
            text = item.text.strip()
            if item.id is None:
                match = same.get(i)
                if match is not None:
                    r = by_id[match]
                    state, prev, vf, vt = "changed", r.text, r.version, r.version + 1
                else:
                    state, prev, vf, vt = "added", None, None, 1
                rid = match
            else:
                r = by_id[item.id]
                rid = r.id
                if item.removed and not r.removed:
                    state, prev, vf, vt = "removed", None, r.version, r.version
                elif not item.removed and r.removed:
                    state, prev, vf, vt = "restored", None, r.version, r.version
                elif item.removed or text == r.text and item.category == r.category:
                    state, prev, vf, vt = "unchanged", None, r.version, r.version
                elif item.category == r.category and is_cosmetic(r.text, text):
                    state, prev, vf, vt = "cosmetic", r.text, r.version, r.version
                else:
                    state, prev, vf, vt = "changed", r.text, r.version, r.version + 1
            if state == "removed" and any(m.requirement_id == item.id for m in body.same_as):
                continue  # it carries on as the new wording matched to it, counted there
            counts["unchanged" if state == "cosmetic" else state] += 1
            changes.append(
                RequirementChange(
                    index=i,
                    requirement_id=rid,
                    state=state,
                    text=text,
                    previous_text=prev,
                    version_from=vf,
                    version_to=vt,
                    stories=stories.get(rid, [])
                    if rid and state in ("changed", "removed", "restored")
                    else [],
                    actions=actions.get(rid, [])
                    if rid and state in ("changed", "removed", "restored")
                    else [],
                )
            )
        parts = [f"{counts['changed']} changed", f"{counts['added']} added", f"{counts['removed']} removed"]
        if counts["restored"]:
            parts.append(f"{counts['restored']} restored")
        parts.append(f"{counts['unchanged']} unchanged")
        return RevisionPreview(
            summary=", ".join(parts),
            counts=counts,
            changes=changes,
            suggestions=self._suggestions(body, by_id),
            revision=t.requirements_revision,
        )

    def _suggestions(
        self, body: RequirementSetIn, by_id: dict[str, TargetRequirement]
    ) -> list[SameAsSuggestion]:
        """New wording that looks like a requirement being removed: a question, never a decision."""
        removed_now = [
            by_id[i.id] for i in body.items if i.id is not None and i.removed and not by_id[i.id].removed
        ]
        chosen = {m.index for m in body.same_as}
        out = []
        for idx, item in enumerate(body.items):
            if item.id is not None or idx in chosen:
                continue
            best = max(removed_now, key=lambda r: similarity(r.text, item.text), default=None)
            if best is not None and similarity(best.text, item.text) >= SUGGEST_AT:
                out.append(
                    SameAsSuggestion(
                        index=idx,
                        requirement_id=best.id,
                        text=best.text,
                        question=f"This looks like the earlier “{best.text}”. Is it the same requirement?",
                    )
                )
        return out

    def apply(self, t: RoleTarget, body: RequirementSetIn, *, max_requirements: int, skills_for) -> None:
        by_id = self._check(t, body)
        same = {m.index: m.requirement_id for m in body.same_as}
        new_count = sum(1 for i in body.items if i.id is None) - len(same)
        if len(by_id) + new_count > max_requirements:
            raise AppError(
                f"A target can have up to {max_requirements} requirements.", code="too_many_requirements"
            )
        t.requirements_revision += 1
        matched = set(same.values())
        for i, item in enumerate(body.items):
            text = item.text.strip()
            if item.id is not None:
                r = by_id[item.id]
                if r.id in matched:
                    continue  # handled with the new wording it was matched to
                # Words are edited only on a requirement that stays (or comes back): a removed one
                # keeps the words it was removed with.
                if not item.removed:
                    self.edit(t, r, text=text, category=item.category, skills=skills_for(text))
                self.set_removed(t, r, item.removed)
            elif i in same:
                # The learner said it's the same requirement: its next version, same identity.
                r = by_id[same[i]]
                self.keep_original(t, r)
                r.removed = False
                r.version += 1
                r.text, r.category = text, item.category
                r.skills = skills_for(text)
                self.db.flush()
                self.record(t, r, "changed", same_as=r.id)
            else:
                r = TargetRequirement(
                    position=len(t.requirements),
                    category=item.category,
                    text=text,
                    origin="user",
                    quote=None,
                    skills=skills_for(text),
                    version=1,
                )
                t.requirements.append(r)
                self.db.flush()
                self.record(t, r, "added")

    # --- links ------------------------------------------------------------------------------------

    def _stories(self, t: RoleTarget) -> dict[str, list[LinkedStory]]:
        out: dict[str, list[LinkedStory]] = {}
        for e in self.db.scalars(
            select(ExperienceEntry).where(
                ExperienceEntry.target_id == t.id, ExperienceEntry.user_id == self.user.id
            )
        ):
            for rid in e.requirement_ids or []:
                out.setdefault(rid, []).append(LinkedStory(id=e.id, title=e.title))
        return out

    @staticmethod
    def link_versions(t: RoleTarget, previous: dict | None, old_ids: list, new_ids: list) -> dict:
        """Each linked requirement's version: kept for links already there (even if it has a newer
        wording now), the current one for new links."""
        versions = {r.id: r.version for r in t.requirements}
        kept = dict(previous or {})
        out = {}
        for rid in new_ids:
            if rid in old_ids:
                if rid in kept:
                    out[rid] = kept[rid]
                # a link from before versions were kept stays without one
            else:
                out[rid] = {"version": versions.get(rid, 1), "reused_from": None}
        return out

    @staticmethod
    def _status(r: TargetRequirement, v: int | None, reused: int | None, *, before: str) -> tuple[str, str]:
        """How a link reads: about the link, never the learner."""
        if r.removed:
            return "removed", "Linked to a requirement you removed"
        if v is None:
            return "not_recorded", f"{before}: version not recorded"
        if v < r.version:
            return "earlier_wording", f"Linked to an earlier wording (version {v}; now version {r.version})"
        if reused:
            return (
                "current",
                f"Reused for the current wording (version {v}, first linked to version {reused})",
            )
        return "current", f"Linked to the current wording (version {v})"

    @staticmethod
    def links(e: ExperienceEntry, t: RoleTarget) -> list[RequirementLink]:
        by_id = {r.id: r for r in t.requirements}
        recorded = e.requirement_versions or {}
        out = []
        for rid in e.requirement_ids or []:
            r = by_id.get(rid)
            if r is None:
                continue
            rec = recorded.get(rid)
            v = rec.get("version") if isinstance(rec, dict) else None
            reused = rec.get("reused_from") if isinstance(rec, dict) else None
            status, label = RequirementVersions._status(
                r, v, reused, before="Linked before versions were kept"
            )
            out.append(
                RequirementLink(
                    requirement_id=rid,
                    linked_version=v,
                    current_version=r.version,
                    status=status,
                    label=label,
                    reused_from=reused,
                )
            )
        return out

    def reuse(self, t: RoleTarget, e: ExperienceEntry, rid: str) -> None:
        """Deliberately use a story for a requirement's current wording, recorded as a reuse."""
        r = next((x for x in t.requirements if x.id == rid), None)
        if r is None or rid not in (e.requirement_ids or []):
            raise NotFoundError("That story isn't linked to this requirement.")
        if r.removed:
            raise AppError("That requirement was removed.", code="requirement_removed")
        recorded = dict(e.requirement_versions or {})
        rec = recorded.get(rid)
        before = rec.get("version") if isinstance(rec, dict) else None
        if before == r.version:
            return
        recorded[rid] = {"version": r.version, "reused_from": before}
        e.requirement_versions = recorded

    # --- accepted improvements ---------------------------------------------------------------------

    def linked_at(self, t: RoleTarget, question_id: str, at: datetime) -> dict[str, int | None]:
        """The requirements a question practised at a moment (an attempt or an acceptance), each
        with the version then: the mapping of that version, so a later rewording that maps to other
        questions doesn't detach it. Legacy requirements without history use their current mapping."""
        out: dict[str, int | None] = {}
        for r in t.requirements:
            v = self.version_at(t, r.id, at)
            key = (r.id, v)
            if key not in self._qids:
                skills: list | None = r.skills
                if v is not None and v != r.version:
                    rows = [
                        x for x in self._rows_for(t).get(r.id, []) if x.version == v and x.skills is not None
                    ]
                    if rows:
                        skills = rows[-1].skills
                by_skill = questions_by_skill(t.track)
                self._qids[key] = set().union(*(by_skill.get(sk, frozenset()) for sk in skills or []))
            if question_id in self._qids[key]:
                out[r.id] = v
        return out

    def _action_pairs(self, t: RoleTarget) -> list[tuple[str, AcceptedAction, int | None]]:
        """(requirement id, action, version then) for each accepted improvement practising a
        question one of this target's requirements mapped to when it was accepted: its question
        link, or the interview question its retry is."""
        rows = list(
            self.db.scalars(
                select(AcceptedAction)
                .where(AcceptedAction.user_id == self.user.id)
                .order_by(AcceptedAction.created_at, AcceptedAction.id)
            )
        )
        retries = {row.id: m for row in rows if (m := _RETRY_HREF.match(row.practice_href or ""))}
        sessions = (
            {
                s.id: s
                for s in self.db.scalars(
                    select(PracticeSession).where(
                        PracticeSession.user_id == self.user.id,
                        PracticeSession.id.in_({m.group(1) for m in retries.values()}),
                    )
                )
            }
            if retries
            else {}
        )
        out: list[tuple[str, AcceptedAction, int | None]] = []
        for row in rows:
            qid = None
            if m := _QUESTION_HREF.match(row.practice_href or ""):
                qid = m.group(2) if m.group(1) == t.track else None
            elif (m := retries.get(row.id)) and (s := sessions.get(m.group(1))) and s.track == t.track:
                ids = (s.plan or {}).get("question_ids") or []
                index = int(m.group(2))
                qid = ids[index] if 0 <= index < len(ids) else None
            if qid is None:
                continue
            out.extend((rid, row, v) for rid, v in self.linked_at(t, qid, row.created_at).items())
        return out

    def action_links(self, t: RoleTarget) -> list[ActionLink]:
        by_id = {r.id: r for r in t.requirements}
        out = []
        for rid, row, then in self._action_pairs(t):
            r = by_id[rid]
            rec = (row.requirement_reuse or {}).get(rid)
            if isinstance(rec, dict):
                v, reused = rec.get("version"), rec.get("reused_from")
            else:
                v, reused = then, None
            status, label = self._status(r, v, reused, before="Accepted before versions were kept")
            out.append(
                ActionLink(
                    action_id=row.id,
                    title=row.title,
                    requirement_id=rid,
                    linked_version=v,
                    current_version=r.version,
                    status=status,
                    label=label,
                    reused_from=reused,
                )
            )
        return out

    def reuse_action(self, t: RoleTarget, action_id: str, rid: str) -> None:
        """Deliberately use an accepted improvement for a requirement's current wording, recorded."""
        pair = next(
            ((a, v) for r_id, a, v in self._action_pairs(t) if a.id == action_id and r_id == rid), None
        )
        r = next((x for x in t.requirements if x.id == rid), None)
        if pair is None or r is None:
            raise NotFoundError("That improvement isn't linked to this requirement.")
        if r.removed:
            raise AppError("That requirement was removed.", code="requirement_removed")
        row, then = pair
        recorded = dict(row.requirement_reuse or {})
        rec = recorded.get(rid)
        before = rec.get("version") if isinstance(rec, dict) else then
        if before == r.version:
            return
        recorded[rid] = {"version": r.version, "reused_from": before}
        row.requirement_reuse = recorded

    def history(self, t: RoleTarget, rid: str) -> list[RequirementHistoryEntry]:
        r = next((x for x in t.requirements if x.id == rid), None)
        if r is None:
            raise NotFoundError("Requirement not found")
        rows = list(
            self.db.scalars(
                select(RequirementVersion)
                .where(RequirementVersion.requirement_id == rid, RequirementVersion.user_id == self.user.id)
                .order_by(RequirementVersion.created_at, RequirementVersion.version)
            )
        )
        if not rows:
            return [
                RequirementHistoryEntry(
                    version=r.version,
                    state="original",
                    text=r.text,
                    category=r.category,
                    at=None,
                    same_as=None,
                )
            ]
        return [
            RequirementHistoryEntry(
                version=x.version,
                state=x.state,
                text=x.text,
                category=x.category,
                at=x.created_at,
                same_as=x.same_as,
            )
            for x in rows
        ]

    def _rows_for(self, t: RoleTarget) -> dict[str, list[RequirementVersion]]:
        """This target's recorded versions by requirement, oldest first (read once per request)."""
        if self._rows is None:
            self._rows = {}
            for x in self.db.scalars(
                select(RequirementVersion)
                .where(RequirementVersion.target_id == t.id, RequirementVersion.user_id == self.user.id)
                .order_by(RequirementVersion.created_at, RequirementVersion.version)
            ):
                self._rows.setdefault(x.requirement_id, []).append(x)
        return self._rows

    def version_at(self, t: RoleTarget, rid: str, at: datetime) -> int | None:
        """The version a requirement had at a moment (an attempt's time); None if not recorded."""
        rows = self._rows_for(t).get(rid, [])
        if not rows:
            r = next((x for x in t.requirements if x.id == rid), None)
            return r.version if r is not None and r.version == 1 else None
        when = at if at.tzinfo else at.replace(tzinfo=UTC)
        known = [
            x.version
            for x in rows
            if (x.created_at if x.created_at.tzinfo else x.created_at.replace(tzinfo=UTC)) <= when
        ]
        if known:
            return max(known)
        # Before its first recorded row: the wording it started with (its words from before versions
        # were kept, or the wording it was added with).
        first = [x.version for x in rows if x.state in ("original", "added")]
        return min(first) if first else None

"""Target roles: saved postings, reviewable requirements and a preparation map grounded in the
question bank and the learner's recorded attempts.

- Coverage is "practice coverage", computed from real answers and judged code for the skills a
  requirement maps to. It is never a probability of being hired.
- A requirement nothing in the bank practises stays visible as a gap; qualifications (licences,
  certifications, years of experience) are labelled as such rather than "practised".
- Sessions and mock interviews use only the target career's questions, so nursing preparation
  can never fall back to coding.
- Editing the description keeps every requirement and attempt; lines that are no longer in the
  text are flagged, and re-extraction only adds what's new.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.careers import CATALOG
from app.careers.questions import get_question, questions_for
from app.careers.skills import career_skills, questions_by_skill
from app.errors import AppError, NotFoundError
from app.models import (
    ExperienceEntry,
    PracticeAnswer,
    Problem,
    RoleTarget,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    TargetRequirement,
    User,
)
from app.schemas.roadmap import RoundStart
from app.schemas.roles import (
    AttemptOut,
    Coverage,
    ExperienceIn,
    ExperienceOut,
    PracticeLink,
    RequirementIn,
    RequirementOut,
    RequirementPatch,
    SessionPlan,
    TargetIn,
    TargetOut,
    TargetPatch,
    TargetSummary,
)
from app.services.jd_extract import extract, map_skills

MAX_TARGETS = 20
MAX_REQUIREMENTS = 60
MAX_EXPERIENCE = 30
DEFAULT_TRACK = "software-engineer"
PRIORITY = {
    "required_skill": 0,
    "responsibility": 1,
    "competency": 2,
    "tool": 3,
    "preferred_skill": 4,
    "experience": 5,
}
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}
QUALIFICATION = re.compile(
    r"\b(licen[cs]e\w*|certif\w*|degree|diploma|registered|clearance|bachelor|master)\b", re.I
)
CODING_TOPICS: dict[str, tuple[str, ...]] = {
    r"data structure": ("arrays", "hash-maps", "stacks", "heaps"),
    r"algorithm": ("sorting", "binary-search", "dynamic-programming", "graphs"),
    r"dynamic programming": ("dynamic-programming",),
    r"\bgraphs?\b": ("graphs",),
    r"\bstrings?\b|text processing": ("strings",),
    r"\barrays?\b": ("arrays",),
    r"hash ?maps?|hash tables?": ("hash-maps",),
    r"recursion|recursive": ("recursion", "backtracking"),
    r"problem[- ]solving": ("arrays", "strings"),
}
JUDGED = {
    SubmissionStatus.PASSED,
    SubmissionStatus.FAILED,
    SubmissionStatus.COMPILE_ERROR,
    SubmissionStatus.RUNTIME_ERROR,
    SubmissionStatus.TIME_LIMIT,
    SubmissionStatus.MEMORY_LIMIT,
}


def coding_topics(text: str) -> list[str]:
    out: dict[str, None] = {}
    for pattern, topics in CODING_TOPICS.items():
        if re.search(pattern, text, re.I):
            out.update(dict.fromkeys(topics))
    return list(out)


class RoleTargets:
    def __init__(self, db: Session, judge_enabled: bool):
        self.db = db
        self.judge_enabled = judge_enabled

    # --- loading and ownership ------------------------------------------------------------

    def _load(self, user: User, target_id: str) -> RoleTarget:
        t = self.db.scalar(
            select(RoleTarget)
            .options(selectinload(RoleTarget.requirements))
            .where(RoleTarget.id == target_id)
        )
        if t is None or t.user_id != user.id:
            raise NotFoundError("Target role not found")
        return t

    def _requirement(self, t: RoleTarget, req_id: str) -> TargetRequirement:
        r = next((r for r in t.requirements if r.id == req_id), None)
        if r is None:
            raise NotFoundError("Requirement not found")
        return r

    def _check_skills(self, track: str, skills: list[str]) -> list[str]:
        allowed = set(career_skills(track))
        bad = [s for s in skills if s not in allowed]
        if bad:
            raise AppError(
                f"Not a skill of {CATALOG[track].title}: {', '.join(bad[:3])}", code="unknown_skill"
            )
        return list(dict.fromkeys(skills))

    # --- commands ---------------------------------------------------------------------------

    def create(self, user: User, body: TargetIn) -> TargetOut:
        track = body.track or user.career_track or DEFAULT_TRACK
        if track not in CATALOG:
            raise NotFoundError(f"Career '{track}' not found")
        count = (
            self.db.scalar(select(func.count()).select_from(RoleTarget).where(RoleTarget.user_id == user.id))
            or 0
        )
        if count >= MAX_TARGETS:
            raise AppError(
                f"You can keep up to {MAX_TARGETS} target roles. Delete an old one first.",
                code="too_many_targets",
            )
        has_selected = self.db.scalar(
            select(RoleTarget.id).where(RoleTarget.user_id == user.id, RoleTarget.selected.is_(True)).limit(1)
        )
        t = RoleTarget(
            user_id=user.id,
            track=track,
            title=body.title,
            employer=body.employer or None,
            description=body.description,
            interview_date=body.interview_date,
            notes=body.notes or None,
            selected=has_selected is None,
        )
        for i, e in enumerate(extract(body.description, track)):
            t.requirements.append(
                TargetRequirement(
                    position=i,
                    category=e.category,
                    text=e.text,
                    origin=e.origin,
                    quote=e.quote,
                    skills=e.skills,
                )
            )
        self.db.add(t)
        self.db.commit()
        return self.get(user, t.id)

    def update(self, user: User, target_id: str, body: TargetPatch) -> TargetOut:
        t = self._load(user, target_id)
        fields = body.model_fields_set
        for name in ("title", "employer", "description", "interview_date", "notes"):
            if name in fields:
                value = getattr(body, name)
                if name in ("title", "description") and (value is None or not str(value).strip()):
                    raise AppError(f"{name.capitalize()} can't be empty.", code="invalid_field")
                setattr(t, name, value.strip() if isinstance(value, str) and name != "description" else value)
        if body.archived is not None:
            t.archived = body.archived
            if body.archived:
                t.selected = False
        if body.selected:
            if t.archived:
                raise AppError("Unarchive this target before making it active.", code="target_archived")
            for other in self.db.scalars(
                select(RoleTarget).where(RoleTarget.user_id == user.id, RoleTarget.id != t.id)
            ).all():
                other.selected = False
            t.selected = True
        elif body.selected is False:
            t.selected = False
        t.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(user, t.id)

    def delete(self, user: User, target_id: str) -> None:
        t = self._load(user, target_id)
        self.db.delete(t)  # requirements and experience go with it; recorded attempts are untouched
        self.db.commit()

    def reextract(self, user: User, target_id: str) -> TargetOut:
        """Add requirements found in the current description that aren't there yet (removed ones
        stay removed; edited ones stay as edited)."""
        t = self._load(user, target_id)
        known = {r.text.lower() for r in t.requirements} | {
            (r.quote or "").lower() for r in t.requirements if r.quote
        }
        pos = len(t.requirements)
        for e in extract(t.description, t.track):
            if e.origin != "explicit" or e.text.lower() in known or len(t.requirements) >= MAX_REQUIREMENTS:
                continue
            if e.category not in ("tool", "competency") and e.quote and e.quote.lower() in known:
                continue
            t.requirements.append(
                TargetRequirement(
                    position=pos,
                    category=e.category,
                    text=e.text,
                    origin="explicit",
                    quote=e.quote,
                    skills=e.skills,
                )
            )
            known.add(e.text.lower())
            pos += 1
        self.db.commit()
        return self.get(user, t.id)

    def add_requirement(self, user: User, target_id: str, body: RequirementIn) -> TargetOut:
        t = self._load(user, target_id)
        if len(t.requirements) >= MAX_REQUIREMENTS:
            raise AppError(
                f"A target can have up to {MAX_REQUIREMENTS} requirements.", code="too_many_requirements"
            )
        text = body.text.strip()
        skills = (
            self._check_skills(t.track, body.skills) if body.skills is not None else map_skills(text, t.track)
        )
        t.requirements.append(
            TargetRequirement(
                position=len(t.requirements),
                category=body.category,
                text=text,
                origin="user",
                quote=None,
                skills=skills,
            )
        )
        self.db.commit()
        return self.get(user, t.id)

    def patch_requirement(self, user: User, target_id: str, req_id: str, body: RequirementPatch) -> TargetOut:
        t = self._load(user, target_id)
        r = self._requirement(t, req_id)
        if body.category is not None:
            r.category = body.category
        if body.text is not None:
            r.text = body.text.strip()
        if body.skills is not None:
            r.skills = self._check_skills(t.track, body.skills)
        if body.removed is not None:
            r.removed = body.removed
        self.db.commit()
        return self.get(user, t.id)

    def add_experience(self, user: User, target_id: str, body: ExperienceIn) -> TargetOut:
        t = self._load(user, target_id)
        n = (
            self.db.scalar(
                select(func.count()).select_from(ExperienceEntry).where(ExperienceEntry.target_id == t.id)
            )
            or 0
        )
        if n >= MAX_EXPERIENCE:
            raise AppError(f"Up to {MAX_EXPERIENCE} examples per target.", code="too_many_examples")
        self.db.add(ExperienceEntry(user_id=user.id, target_id=t.id, **self._experience_fields(t, body)))
        self.db.commit()
        return self.get(user, t.id)

    def patch_experience(self, user: User, target_id: str, entry_id: str, body: ExperienceIn) -> TargetOut:
        t = self._load(user, target_id)
        e = self._entry(user, t, entry_id)
        for k, v in self._experience_fields(t, body).items():
            setattr(e, k, v)
        e.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(user, t.id)

    def delete_experience(self, user: User, target_id: str, entry_id: str) -> TargetOut:
        t = self._load(user, target_id)
        self.db.delete(self._entry(user, t, entry_id))
        self.db.commit()
        return self.get(user, t.id)

    def _entry(self, user: User, t: RoleTarget, entry_id: str) -> ExperienceEntry:
        e = self.db.get(ExperienceEntry, entry_id)
        if e is None or e.user_id != user.id or e.target_id != t.id:
            raise NotFoundError("Example not found")
        return e

    @staticmethod
    def _experience_fields(t: RoleTarget, body: ExperienceIn) -> dict:
        ids = {r.id for r in t.requirements}
        bad = [i for i in body.requirement_ids if i not in ids]
        if bad:
            raise AppError(
                "An example can only be linked to this target's requirements.", code="unknown_requirement"
            )
        return {
            "title": body.title.strip(),
            "situation": body.situation.strip(),
            "action": body.action.strip(),
            "result": body.result.strip(),
            "requirement_ids": list(dict.fromkeys(body.requirement_ids)),
        }

    # --- reads ------------------------------------------------------------------------------

    def list(self, user: User) -> list[TargetSummary]:
        rows = self.db.scalars(
            select(RoleTarget)
            .options(selectinload(RoleTarget.requirements))
            .where(RoleTarget.user_id == user.id)
        ).all()
        rows = sorted(rows, key=lambda t: (t.archived, not t.selected, -t.updated_at.timestamp()))
        out = []
        for t in rows:
            coding = CATALOG[t.track].has_coding
            active = [r for r in t.requirements if not r.removed]
            gaps = sum(1 for r in active if not r.skills and not (coding and coding_topics(r.text)))
            out.append(self._summary(t, len(active), gaps))
        return out

    def _summary(self, t: RoleTarget, requirements: int, gaps: int) -> TargetSummary:
        return TargetSummary(
            id=t.id,
            title=t.title,
            employer=t.employer,
            track=t.track,
            career_title=CATALOG[t.track].title,
            interview_date=t.interview_date,
            archived=t.archived,
            selected=t.selected,
            requirements=requirements,
            gaps=gaps,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )

    def get(self, user: User, target_id: str) -> TargetOut:
        t = self._load(user, target_id)
        self.db.refresh(t)
        track = t.track
        profile = CATALOG[track]
        answers = self.db.scalars(
            select(PracticeAnswer)
            .where(PracticeAnswer.user_id == user.id, PracticeAnswer.track == track)
            .order_by(PracticeAnswer.created_at.desc())
        ).all()
        best: dict[str, int] = {}
        counts: dict[str, int] = defaultdict(int)
        for a in answers:
            best[a.question_id] = max(best.get(a.question_id, 0), a.score)
            counts[a.question_id] += 1
        by_skill = questions_by_skill(track)
        bank = sorted(questions_for(track), key=lambda q: (DIFFICULTY_ORDER.get(q.difficulty, 3), q.id))
        problems: list[Problem] = list(self.db.scalars(select(Problem)).all()) if profile.has_coding else []
        sub_rows = (
            self.db.execute(
                select(Submission.problem_id, Submission.status).where(
                    Submission.user_id == user.id, Submission.mode == SubmissionMode.SUBMIT
                )
            ).all()
            if profile.has_coding
            else []
        )
        judged: dict[int, int] = defaultdict(int)
        passed: set[int] = set()
        attempted: set[int] = set()
        for pid, status in sub_rows:
            attempted.add(pid)
            if status in JUDGED:
                judged[pid] += 1
            if status == SubmissionStatus.PASSED:
                passed.add(pid)

        reqs: list[RequirementOut] = []
        qids_by_req: dict[str, set[str]] = {}
        for r in t.requirements:
            qids: set[str] = set()
            for s in r.skills:
                qids |= set(by_skill.get(s, frozenset()))
            qids_by_req[r.id] = qids
            topics = coding_topics(r.text) if profile.has_coding else []
            probs = [p for p in problems if set(p.topics) & set(topics)]
            answered = [q for q in qids if q in best]
            avg = round(sum(best[q] for q in answered) / len(answered)) if answered else None
            j = sum(judged[p.id] for p in probs)
            ok = sum(1 for p in probs if p.id in passed)
            n_answers = sum(counts[q] for q in answered)
            qualification = r.category == "experience" or bool(QUALIFICATION.search(r.text))
            if not qids and not probs:
                level, label = (
                    "gap",
                    (
                        "A qualification or experience requirement; practice questions can't cover it"
                        if qualification
                        else "No practice in the question bank covers this yet"
                    ),
                )
            elif (len(answered) >= 2 and (avg or 0) >= 70) or ok >= 2:
                level, label = (
                    "practised",
                    "Practised"
                    + (
                        f": {len(answered)} questions, average best {avg}/100"
                        if answered
                        else f": {ok} problems passed"
                    ),
                )
            elif answered or j or any(p.id in attempted for p in probs):
                level, label = (
                    "some",
                    "Some practice"
                    + (
                        f": {len(answered)} question{'s' if len(answered) != 1 else ''}, best average {avg}/100"
                        if answered
                        else ""
                    ),
                )
            else:
                level, label = "limited", "Limited evidence: not practised yet"
            practice: list[PracticeLink] = []
            for q in [q for q in bank if q.id in qids and q.id not in best][:2] + sorted(
                (q for q in bank if q.id in qids and q.id in best), key=lambda q: best[q.id]
            )[:1]:
                skill = next(
                    (s for s in r.skills if q.id in by_skill.get(s, frozenset())),
                    r.skills[0] if r.skills else "",
                )
                practice.append(
                    PracticeLink(
                        kind="question",
                        title=q.title,
                        href=f"/careers/{track}/questions/{q.id}",
                        why=(
                            f"Retry: your best is {best[q.id]}/100 ({skill})"
                            if q.id in best
                            else f"Practises {skill}"
                        ),
                        answered=q.id in best,
                        best_score=best.get(q.id),
                    )
                )
            for p in [p for p in probs if p.id not in passed][:2]:
                practice.append(
                    PracticeLink(
                        kind="problem",
                        title=p.title,
                        href=f"/problems/{p.slug}",
                        why=f"Coding practice for {', '.join(sorted(set(p.topics) & set(topics))).replace('-', ' ')}",
                    )
                )
            reqs.append(
                RequirementOut(
                    id=r.id,
                    category=r.category,
                    text=r.text,
                    origin=r.origin,
                    quote=r.quote,
                    quote_in_description=bool(r.quote) and _contains(t.description, r.quote or ""),
                    skills=list(r.skills),
                    removed=r.removed,
                    practice=practice,
                    coverage=Coverage(
                        level=level,
                        label=label,
                        answers=n_answers,
                        questions_answered=len(answered),
                        average_best_score=avg,
                        judged_attempts=j,
                        passed=ok,
                    ),
                )
            )

        active = sorted(
            (r for r in reqs if not r.removed),
            key=lambda r: (PRIORITY.get(r.category, 9), r.origin == "inferred"),
        )
        nxt = None
        for ro in active:
            if ro.coverage.level in ("limited", "some"):
                link = next((p for p in ro.practice if not p.answered), None) or (
                    ro.practice[0] if ro.practice else None
                )
                if link:
                    nxt = link.model_copy(
                        update={
                            "why": f"“{ro.text}” has {ro.coverage.label.split(':')[0].lower()}. {link.why}."
                        }
                    )
                    break

        def pick(reqs_: list[RequirementOut], n: int) -> tuple[list[str], list[str]]:
            ids: list[str] = []
            covered: list[str] = []
            for r in reqs_:
                q = next(
                    (p for p in r.practice if p.kind == "question" and p.href.rsplit("/", 1)[1] not in ids),
                    None,
                )
                if q is None:
                    continue
                ids.append(q.href.rsplit("/", 1)[1])
                covered.append(r.text)
                if len(ids) >= n:
                    break
            return ids, covered

        weak = [r for r in active if r.coverage.level in ("limited", "some")]
        s_ids, s_cov = pick(weak, 3)
        bank_note = f"Questions come from the {profile.title} question bank. They are practice questions, not this employer's."
        session = SessionPlan(
            title="Short targeted session",
            scope=(
                f"{len(s_ids)} question{'s' if len(s_ids) != 1 else ''} on requirements with the least practice: "
                + "; ".join(s_cov)
                + f". {bank_note}"
            )
            if s_ids
            else "Every requirement the bank can cover already has practice. Try the mock interview instead.",
            round=RoundStart(track=track, question_ids=s_ids, duration_minutes=10) if s_ids else None,
        )
        m_ids, m_cov = pick(active, 5)
        mock = SessionPlan(
            title=f"Mock interview for {t.title}",
            scope=(
                f"{len(m_ids)} questions chosen to cover: " + "; ".join(m_cov) + f". {bank_note} It doesn't "
                "reproduce this employer's interview process or scoring."
            )
            if m_ids
            else "No requirement maps to questions in the bank yet, so there's nothing to build a mock interview from.",
            round=RoundStart(track=track, question_ids=m_ids, duration_minutes=15) if m_ids else None,
        )
        relevant = set().union(*qids_by_req.values()) if qids_by_req else set()
        recent = []
        for a in answers:
            if a.question_id not in relevant:
                continue
            asked = get_question(track, a.question_id)
            recent.append(
                AttemptOut(
                    answer_id=a.id,
                    question_title=asked.title if asked else a.question_id,
                    score=a.score,
                    created_at=a.created_at,
                    href=f"/careers/{track}/questions/{a.question_id}?answer={a.id}",
                    requirement_ids=[rid for rid, ids in qids_by_req.items() if a.question_id in ids],
                )
            )
            if len(recent) >= 6:
                break
        experience = self.db.scalars(
            select(ExperienceEntry)
            .where(ExperienceEntry.target_id == t.id)
            .order_by(ExperienceEntry.created_at)
        ).all()
        days = (t.interview_date - datetime.now(UTC).date()).days if t.interview_date else None
        summary = self._summary(t, len(active), sum(1 for r in active if r.coverage.level == "gap"))
        return TargetOut(
            **summary.model_dump(),
            description=t.description,
            notes=t.notes,
            extractor="rule-based (no AI)",
            requirement_list=reqs,
            next_activity=nxt,
            targeted_session=session,
            mock_interview=mock,
            recent_attempts=recent,
            experience=[
                ExperienceOut(
                    id=e.id,
                    title=e.title,
                    situation=e.situation,
                    action=e.action,
                    result=e.result,
                    requirement_ids=list(e.requirement_ids),
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                )
                for e in experience
            ],
            days_to_interview=days if days is not None and days >= 0 else None,
        )


def _contains(text: str, quote: str) -> bool:
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()  # noqa: E731
    return norm(quote) in norm(text)

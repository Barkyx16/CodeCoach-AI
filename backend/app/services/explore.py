"""The practice explorer, bookmarks and private collections.

- Search reuses the library's ranking (title > skills/tags > prompt > rubric) and puts exact title
  matches first. Career is an explicit scope; browsing another career never changes the account.
- Facet counts are computed for each filter with every *other* filter applied, so a count always
  says how many results choosing that option would give.
- Personal data (attempts, bookmarks, collections) is only returned by the signed-in endpoint and
  in its own `status` map; the public result never contains it.
- Only sorts the data supports are offered: generated questions have no "added" date, so there is
  no "recently added", and nothing is called personalized.
- Saved items keep stable ids. A question that leaves the library shows as unavailable with a way
  to remove it; nothing is silently swapped for another question.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.careers import CATALOG
from app.careers.eligibility import question_scores
from app.careers.questions import Question, content_key, get_question, questions_for
from app.careers.skills import question_skills
from app.content import state as content_state
from app.drills import BY_ID as DRILLS_BY_ID
from app.errors import AppError, ConflictError, NotFoundError, UnauthorizedError
from app.models import (
    Bookmark,
    CollectionItem,
    DrillAttempt,
    PracticeAnswer,
    PracticeCollection,
    Problem,
    Submission,
    SubmissionMode,
    User,
)
from app.schemas.explore import (
    BatchResult,
    BookmarkOut,
    CollectionBatchIn,
    CollectionBatchOut,
    CollectionItemIn,
    CollectionItemOut,
    CollectionOut,
    CollectionSummary,
    ExploreFacets,
    ExploreItem,
    ExploreResult,
    ExploreSort,
    ExploreStatus,
    Facet,
    ItemStatus,
    MyExploreResult,
)
from app.services import search

MAX_COLLECTIONS = 50
MAX_ITEMS = 200
KIND_LABELS = {
    "knowledge": "Knowledge",
    "behavioral": "Behavioral",
    "situational": "Scenario",
    "leadership": "Leadership",
    "motivation": "Motivation",
}
LEVEL_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}


def _searchable(q: Question) -> search.Searchable:
    career = CATALOG[q.track]
    return search.Searchable(
        title=q.title.lower(),
        topics=" ".join((*q.tags, *question_skills(q), q.kind, career.title, career.category)).lower(),
        summary=q.prompt.lower(),
        statement=" ".join(rp.label for rp in q.rubric).lower(),
    )


def _item(q: Question) -> ExploreItem:
    return ExploreItem(
        id=q.id,
        title=q.title,
        prompt=q.prompt,
        difficulty=q.difficulty,
        kind=q.kind,
        skills=list(question_skills(q)),
        tags=list(q.tags),
        estimated_minutes=None,
    )


def _track(slug: str) -> str:
    if slug not in CATALOG:
        raise NotFoundError(f"Career '{slug}' not found")
    return slug


class Explorer:
    def __init__(self, db: Session):
        self.db = db

    # --- personal data ---------------------------------------------------------------------

    def _status(self, user: User, track: str) -> dict[str, ItemStatus]:
        scores = question_scores(self.db, user.id, track)  # raw and scoreable best (eligibility.py)
        last = dict(
            self.db.execute(
                select(PracticeAnswer.question_id, func.max(PracticeAnswer.created_at))
                .where(PracticeAnswer.user_id == user.id, PracticeAnswer.track == track)
                .group_by(PracticeAnswer.question_id)
            ).all()
        )
        marks = set(
            self.db.scalars(
                select(Bookmark.ref_id).where(
                    Bookmark.user_id == user.id, Bookmark.item_type == "question", Bookmark.track == track
                )
            ).all()
        )
        member: dict[str, list[str]] = {}
        for ref, cid in self.db.execute(
            select(CollectionItem.ref_id, CollectionItem.collection_id)
            .join(PracticeCollection, PracticeCollection.id == CollectionItem.collection_id)
            .where(
                PracticeCollection.user_id == user.id,
                CollectionItem.item_type == "question",
                CollectionItem.track == track,
            )
        ).all():
            member.setdefault(ref, []).append(cid)
        out = {
            qid: ItemStatus(
                best_score=s.raw_best,
                best_scored=s.best_scored,
                score_status=s.status,
                attempts=s.attempts,
                last_practiced_at=last.get(qid),
                bookmarked=qid in marks,
                collection_ids=member.get(qid, []),
            )
            for qid, s in scores.items()
        }
        for qid in (marks | set(member)) - set(out):
            out[qid] = ItemStatus(
                best_score=None,
                attempts=0,
                last_practiced_at=None,
                bookmarked=qid in marks,
                collection_ids=member.get(qid, []),
            )
        return out

    # --- explore ---------------------------------------------------------------------------

    def explore(
        self,
        user: User | None,
        track: str,
        *,
        q: str | None,
        difficulty: str | None,
        kind: str | None,
        skill: str | None,
        status: ExploreStatus | None,
        sort: ExploreSort | None,
        page: int,
        page_size: int,
    ) -> ExploreResult | MyExploreResult:
        track = _track(track)
        personal = self._status(user, track) if user else {}
        if (status or sort in ("last_practiced", "lowest_score")) and user is None:
            raise UnauthorizedError(
                "Sign in to filter or sort by your own practice.", code="sign_in_required"
            )
        query = (q or "").strip()
        base = list(questions_for(track))
        if query:
            ranked = search.rank(((x, _searchable(x)) for x in base), query)
            exact = [x for x in ranked if x.title.lower() == query.lower()]
            base = exact + [x for x in ranked if x not in exact]

        def keep(x: Question, skip: str = "") -> bool:
            st = personal.get(x.id)
            return (
                (skip == "difficulty" or not difficulty or x.difficulty == difficulty)
                and (skip == "kind" or not kind or x.kind == kind)
                and (skip == "skill" or not skill or skill in question_skills(x))
                and (
                    not status
                    or (status == "attempted" and st is not None and st.attempts > 0)
                    or (status == "unattempted" and (st is None or st.attempts == 0))
                    or (status == "bookmarked" and st is not None and st.bookmarked)
                )
            )

        rows = [x for x in base if keep(x)]
        chosen = sort or ("relevance" if query else "library")
        if chosen == "last_practiced":
            # Most recent first; never-practiced last. Python's sort is stable, so ties keep the
            # library (or relevance) order and pages never shuffle between requests.
            def recency(x: Question) -> tuple[bool, float]:
                st = personal.get(x.id)
                when = st.last_practiced_at if st else None
                return (when is None, -when.timestamp() if when else 0.0)

            rows.sort(key=recency)
        elif chosen == "lowest_score":

            def weakest(x: Question) -> tuple[int, int]:
                # Scored answers by their best scoreable score; then questions answered only with
                # answers too short to score (no score: not ranked as the lowest); then the rest.
                st = personal.get(x.id)
                if st is not None and st.best_scored is not None:
                    return (0, st.best_scored)
                return (1 if st is not None and st.attempts > 0 else 2, 0)

            rows.sort(key=weakest)
        elif chosen == "library" and query:
            order = {x.id: i for i, x in enumerate(questions_for(track))}
            rows.sort(key=lambda x: order[x.id])

        def facet(field: str, values: dict[str, str]) -> list[Facet]:
            counts: Counter[str] = Counter()
            for x in base:
                if keep(x, skip=field):
                    if field == "skill":
                        counts.update(question_skills(x))
                    else:
                        counts[getattr(x, field)] += 1
            return [Facet(value=v, label=label, count=counts.get(v, 0)) for v, label in values.items()]

        skills_seen: dict[str, str] = {}
        for x in questions_for(track):
            for s in question_skills(x):
                skills_seen.setdefault(s, s[:1].upper() + s[1:])
        explanation = []
        if query:
            explanation.append(f"Matching “{query}” in titles, skills, tags and question text")
        if difficulty:
            explanation.append(f"Difficulty: {LEVEL_LABELS.get(difficulty, difficulty)}")
        if kind:
            explanation.append(f"Format: {KIND_LABELS.get(kind, kind)}")
        if skill:
            explanation.append(f"Skill: {skill}")
        if status:
            explanation.append(
                {
                    "attempted": "Questions you've answered",
                    "unattempted": "Questions you haven't answered",
                    "bookmarked": "Your bookmarks",
                }[status]
            )
        suggestions: list[str] = []
        if not rows:
            if query:
                suggestions.append("Try fewer or more general words.")
            if difficulty or kind or skill or status:
                suggestions.append("Remove a filter to widen the results.")
            suggestions.append("Browse another career's questions with the career picker.")
        start = (page - 1) * page_size
        items = [_item(x) for x in rows[start : start + page_size]]
        sorts: list[ExploreSort] = ["relevance"] if query else []
        sorts.append("library")
        if user is not None:
            sorts += ["last_practiced", "lowest_score"]
        result = ExploreResult(
            track=track,
            career_title=CATALOG[track].title,
            items=items,
            total=len(rows),
            page=page,
            page_size=page_size,
            facets=ExploreFacets(
                difficulty=facet("difficulty", LEVEL_LABELS),
                kind=facet("kind", KIND_LABELS),
                skill=facet("skill", skills_seen),
            ),
            explanation=explanation,
            suggestions=suggestions,
            sorts=sorts,
        )
        if user is None:
            return result
        page_ids = {i.id for i in items}
        return MyExploreResult(
            **result.model_dump(), status={k: v for k, v in personal.items() if k in page_ids}
        )

    # --- saved items -----------------------------------------------------------------------

    def _describe(self, item_type: str, track: str, ref_id: str) -> tuple[str, str | None, bool, str | None]:
        if item_type == "drill":
            drill = DRILLS_BY_ID.get(ref_id)
            if drill is None:
                return (
                    "A drill that's no longer offered",
                    None,
                    False,
                    "This drill was removed. Your saved spot is kept until you remove it.",
                )
            return f"Drill: {drill.title}", f"/drills/{ref_id}", True, None
        if item_type == "question":
            q = get_question(track, ref_id) if track in CATALOG else None
            if q is None:
                return (
                    "A question that's no longer in the library",
                    None,
                    False,
                    "This question was retired or removed from the library. Your saved spot is kept until you remove it.",
                )
            reason = content_state.current().retired.get(("question", content_key(track, ref_id)))
            if reason is not None:
                # Retired: still readable from here, no longer offered for practice.
                return q.title, f"/careers/{track}/questions/{ref_id}", False, f"Retired: {reason}"
            return q.title, f"/careers/{track}/questions/{ref_id}", True, None
        p = self.db.scalar(select(Problem).where(Problem.slug == ref_id))
        if p is None:
            return (
                "A problem that's no longer in the library",
                None,
                False,
                "This problem was removed from the library. Your saved spot is kept until you remove it.",
            )
        reason = content_state.current().retired.get(("problem", ref_id))
        if reason is not None:
            return p.title, f"/problems/{ref_id}", False, f"Retired: {reason}"
        return p.title, f"/problems/{ref_id}", True, None

    def _validate(self, body: CollectionItemIn) -> tuple[str, str, str]:
        track = body.track if body.item_type == "question" else ""
        _, _, ok, _ = self._describe(body.item_type, track, body.ref_id)
        if not ok:
            raise NotFoundError("That item isn't in the library")
        return body.item_type, track, body.ref_id

    def bookmarks(self, user: User) -> list[BookmarkOut]:
        rows = self.db.scalars(
            select(Bookmark).where(Bookmark.user_id == user.id).order_by(Bookmark.created_at.desc())
        ).all()
        out = []
        for b in rows:
            title, href, ok, why = self._describe(b.item_type, b.track, b.ref_id)
            out.append(
                BookmarkOut(
                    item_type=b.item_type,
                    track=b.track,
                    ref_id=b.ref_id,
                    title=title,
                    href=href,
                    available=ok,
                    unavailable_reason=why,
                    content_version=b.content_version,
                    created_at=b.created_at,
                )
            )
        return out

    def set_bookmark(self, user: User, body: CollectionItemIn, on: bool) -> list[BookmarkOut]:
        track = body.track if body.item_type == "question" else ""
        existing = self.db.scalar(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.item_type == body.item_type,
                Bookmark.track == track,
                Bookmark.ref_id == body.ref_id,
            )
        )
        if on and existing is None:
            self._validate(body)
            q = get_question(track, body.ref_id) if body.item_type == "question" else None
            self.db.add(
                Bookmark(
                    user_id=user.id,
                    item_type=body.item_type,
                    track=track,
                    ref_id=body.ref_id,
                    content_version=q.version if q else None,  # to show later what changed since
                )
            )
        elif not on and existing is not None:
            self.db.delete(existing)  # removing works even for retired items
        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent request saved the same bookmark first: the outcome is what was asked.
            self.db.rollback()
        return self.bookmarks(user)

    # --- collections -----------------------------------------------------------------------

    def _collection(self, user: User, cid: str) -> PracticeCollection:
        c = self.db.scalar(
            select(PracticeCollection)
            .options(selectinload(PracticeCollection.items))
            .where(PracticeCollection.id == cid)
        )
        if c is None or c.user_id != user.id:
            raise NotFoundError("Collection not found")
        return c

    def collections(self, user: User, item: CollectionItemIn | None = None) -> list[CollectionSummary]:
        rows = self.db.scalars(
            select(PracticeCollection)
            .options(selectinload(PracticeCollection.items))
            .where(PracticeCollection.user_id == user.id)
            .order_by(PracticeCollection.updated_at.desc())
        ).all()
        if item is None:
            return [self._summary(c) for c in rows]
        track = item.track if item.item_type == "question" else ""

        def holds(c: PracticeCollection) -> bool:
            return any(
                i.item_type == item.item_type and i.track == track and i.ref_id == item.ref_id
                for i in c.items
            )

        return [self._summary(c).model_copy(update={"contains": holds(c)}) for c in rows]

    @staticmethod
    def _summary(c: PracticeCollection) -> CollectionSummary:
        return CollectionSummary(
            id=c.id,
            name=c.name,
            items=len(c.items),
            queue_position=c.queue_position,
            queue_started=c.queue_started_at is not None,
            updated_at=c.updated_at,
        )

    def create(self, user: User, name: str) -> CollectionOut:
        n = (
            self.db.scalar(
                select(func.count())
                .select_from(PracticeCollection)
                .where(PracticeCollection.user_id == user.id)
            )
            or 0
        )
        if n >= MAX_COLLECTIONS:
            raise AppError(f"You can keep up to {MAX_COLLECTIONS} collections.", code="too_many_collections")
        c = PracticeCollection(user_id=user.id, name=name.strip() or "Untitled")
        self.db.add(c)
        self.db.commit()
        return self.get(user, c.id)

    def rename(self, user: User, cid: str, name: str) -> CollectionOut:
        c = self._collection(user, cid)
        c.name = name.strip() or c.name
        c.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(user, cid)

    def delete(self, user: User, cid: str) -> None:
        self.db.delete(self._collection(user, cid))
        self.db.commit()

    def add_item(self, user: User, cid: str, body: CollectionItemIn) -> CollectionOut:
        c = self._collection(user, cid)
        item_type, track, ref = self._validate(body)
        if any(i.item_type == item_type and i.track == track and i.ref_id == ref for i in c.items):
            raise ConflictError(f"It's already in “{c.name}”.", code="already_in_collection")
        if len(c.items) >= MAX_ITEMS:
            raise AppError(f"A collection holds up to {MAX_ITEMS} items.", code="collection_full")
        name = c.name
        c.items.append(CollectionItem(item_type=item_type, track=track, ref_id=ref, position=len(c.items)))
        c.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except IntegrityError:
            # Two tabs added it at the same moment; the unique constraint keeps one copy.
            self.db.rollback()
            raise ConflictError(f"It's already in “{name}”.", code="already_in_collection") from None
        return self.get(user, cid)

    def remove_item(self, user: User, cid: str, item_id: str) -> CollectionOut:
        c = self._collection(user, cid)
        item = next((i for i in c.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("Item not found")
        idx = c.items.index(item)
        c.items.remove(item)
        for pos, i in enumerate(c.items):
            i.position = pos
        if c.queue_position > idx:
            c.queue_position -= 1
        c.queue_position = min(c.queue_position, max(0, len(c.items) - 1))
        c.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(user, cid)

    def batch(self, user: User, cid: str, body: CollectionBatchIn) -> CollectionBatchOut:
        """Several adds, or several removals, each checked on its own (docs/BULK_ACTIONS.md).

        The collection must be yours (404 otherwise, before anything is looked at). Each item gets
        its own outcome: an add is "added", "already_there", "unavailable" (not in the library) or
        "full"; a removal is "removed" or "not_there" (not an item of this collection: the same
        answer for an id that never existed and for another account's item). An item sent twice is
        "repeated" the second time. Adding and removing are idempotent, so sending the same batch
        again after a lost reply reports "already_there" / "not_there" instead of changing twice.
        Removing only takes an item out of this collection: the question, your bookmarks and
        everything you've answered stay."""
        c = self._collection(user, cid)
        name = c.name
        results: list[BatchResult] = []
        seen: set[str] = set()
        changed = False
        if body.add:
            for item in body.add:
                track = item.track if item.item_type == "question" else ""
                key = f"{item.item_type}:{track}:{item.ref_id}"
                if key in seen:
                    results.append(
                        BatchResult(key=key, outcome="repeated", message="Listed twice; counted once.")
                    )
                    continue
                seen.add(key)
                if any(
                    i.item_type == item.item_type and i.track == track and i.ref_id == item.ref_id
                    for i in c.items
                ):
                    results.append(
                        BatchResult(key=key, outcome="already_there", message=f"Already in “{name}”.")
                    )
                    continue
                try:
                    self._validate(item)
                except NotFoundError:
                    results.append(
                        BatchResult(key=key, outcome="unavailable", message="Not in the library any more.")
                    )
                    continue
                if len(c.items) >= MAX_ITEMS:
                    results.append(
                        BatchResult(
                            key=key, outcome="full", message=f"“{name}” holds up to {MAX_ITEMS} items."
                        )
                    )
                    continue
                row = CollectionItem(
                    collection_id=c.id,
                    item_type=item.item_type,
                    track=track,
                    ref_id=item.ref_id,
                    position=len(c.items),
                )
                try:
                    with self.db.begin_nested():  # another tab adding the same item keeps one copy
                        self.db.add(row)
                        self.db.flush()
                except IntegrityError:
                    results.append(
                        BatchResult(key=key, outcome="already_there", message=f"Already in “{name}”.")
                    )
                    continue
                c.items.append(row)
                changed = True
                results.append(BatchResult(key=key, outcome="added", message=f"Added to “{name}”."))
        else:
            for item_id in body.remove:
                if item_id in seen:
                    results.append(
                        BatchResult(key=item_id, outcome="repeated", message="Listed twice; counted once.")
                    )
                    continue
                seen.add(item_id)
                found = next((i for i in c.items if i.id == item_id), None)
                if found is None:
                    results.append(
                        BatchResult(key=item_id, outcome="not_there", message=f"Not in “{name}” (any more).")
                    )
                    continue
                idx = c.items.index(found)
                c.items.remove(found)
                if c.queue_position > idx:
                    c.queue_position -= 1
                changed = True
                results.append(BatchResult(key=item_id, outcome="removed", message=f"Taken out of “{name}”."))
            for pos, i in enumerate(c.items):
                i.position = pos
            c.queue_position = min(c.queue_position, max(0, len(c.items) - 1))
        if changed:
            c.updated_at = datetime.now(UTC)
        self.db.commit()
        return CollectionBatchOut(collection=self.get(user, cid), results=results)

    def reorder(self, user: User, cid: str, item_ids: list[str]) -> CollectionOut:
        c = self._collection(user, cid)
        if sorted(item_ids) != sorted(i.id for i in c.items):
            raise AppError(
                "The new order must list every item of the collection exactly once.", code="invalid_order"
            )
        by_id = {i.id: i for i in c.items}
        for pos, iid in enumerate(item_ids):
            by_id[iid].position = pos
        c.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.expire(c)
        return self.get(user, cid)

    def queue(self, user: User, cid: str, position: int) -> CollectionOut:
        c = self._collection(user, cid)
        if not c.items:
            raise ConflictError("This collection is empty.", code="empty_collection")
        c.queue_position = min(position, len(c.items) - 1)
        c.queue_started_at = c.queue_started_at or datetime.now(UTC)
        self.db.commit()
        return self.get(user, cid)

    def mark_done(self, user: User, cid: str, item_id: str, done: bool) -> CollectionOut:
        c = self._collection(user, cid)
        item = next((i for i in c.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("Item not found")
        item.queue_done_at = datetime.now(UTC) if done else None
        self.db.commit()
        return self.get(user, cid)

    def get(self, user: User, cid: str) -> CollectionOut:
        c = self._collection(user, cid)
        items = sorted(c.items, key=lambda i: i.position)
        out = []
        for i in items:
            title, href, ok, why = self._describe(i.item_type, i.track, i.ref_id)
            if i.item_type == "question":
                practiced = bool(
                    self.db.scalar(
                        select(PracticeAnswer.id)
                        .where(
                            PracticeAnswer.user_id == user.id,
                            PracticeAnswer.track == i.track,
                            PracticeAnswer.question_id == i.ref_id,
                            PracticeAnswer.created_at >= i.added_at,
                        )
                        .limit(1)
                    )
                )
            elif i.item_type == "drill":
                practiced = bool(
                    self.db.scalar(
                        select(DrillAttempt.id)
                        .where(
                            DrillAttempt.user_id == user.id,
                            DrillAttempt.drill_id == i.ref_id,
                            DrillAttempt.created_at >= i.added_at,
                        )
                        .limit(1)
                    )
                )
            else:
                practiced = bool(
                    self.db.scalar(
                        select(Submission.id)
                        .join(Problem, Problem.id == Submission.problem_id)
                        .where(
                            Submission.user_id == user.id,
                            Problem.slug == i.ref_id,
                            Submission.mode == SubmissionMode.SUBMIT,
                            Submission.created_at >= i.added_at,
                        )
                        .limit(1)
                    )
                )
            out.append(
                CollectionItemOut(
                    id=i.id,
                    item_type=i.item_type,
                    track=i.track,
                    ref_id=i.ref_id,
                    position=i.position,
                    title=title,
                    href=href,
                    available=ok,
                    unavailable_reason=why,
                    queue_done=i.queue_done_at is not None,
                    practiced_since_added=practiced,
                )
            )
        return CollectionOut(
            **self._summary(c).model_dump(), item_list=out, queue_done=sum(x.queue_done for x in out)
        )

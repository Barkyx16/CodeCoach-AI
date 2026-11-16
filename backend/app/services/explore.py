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
    LifecycleReceipt,
    PracticeAnswer,
    PracticeCollection,
    Problem,
    SourceReview,
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
    CollectionReviewBatchIn,
    CollectionReviewBatchOut,
    CollectionSummary,
    CollectionTransferIn,
    CollectionTransferOut,
    ExploreFacets,
    ExploreItem,
    ExploreResult,
    ExploreSort,
    ExploreStatus,
    Facet,
    ItemStatus,
    MyExploreResult,
    ReviewResult,
    SavedReviewBatchIn,
    SavedReviewBatchOut,
    SavedReviewIn,
    TransferResult,
)
from app.schemas.notes import NoteFreshness
from app.services import request_keys, search
from app.services.note_freshness import Holder, SourceFreshness, SourceRef, forget, problem_versions

MAX_COLLECTIONS = 50
MAX_ITEMS = 200
COPY = " (copy)"


def collection_name_key(name: str) -> str:
    """A collection's name as compared with the others': spacing and letter case don't count."""
    return " ".join(name.split()).casefold()


def copy_name(original: str, taken: set[str]) -> str:
    """“X (copy)”, or “X (copy 2)”, “X (copy 3)”… when that's taken, within the 80-character limit."""
    for n in range(1, MAX_COLLECTIONS + 2):
        suffix = COPY if n == 1 else f" (copy {n})"
        name = original.strip()[: 80 - len(suffix)].rstrip() + suffix
        if collection_name_key(name) not in taken:
            return name
    raise AssertionError("more copies than collections")  # pragma: no cover: the limit comes first


# Saved items and collections hold a versioned source the same way a note does: one rule
# (app/services/note_freshness.py), their own words and their own reviews.
SAVED = Holder(
    kind="bookmark",
    noun="item",
    made="saved",
    keeps="it stays saved until you remove it",
    fits="whether it's still what you saved it for",
)
IN_COLLECTION = Holder(
    kind="collection_item",
    noun="item",
    made="added",
    keeps="it stays in this collection until you remove it",
    fits="whether it still belongs in this collection",
)


def saved_ref(item_type: str, track: str, ref_id: str, version: int | None) -> SourceRef | None:
    """A saved question or coding problem as a versioned source; None for a drill (no versions)."""
    if item_type not in ("question", "problem"):
        return None
    return SourceRef(kind=item_type, id=ref_id, track=track or None, captured=version)


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


# The receipt a keyed copy or move keeps of its reply (Volume 18, prompt 5), in lifecycle_receipts.
TRANSFER_RECEIPT = "collection_transfer"


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

    def _version_now(self, item_type: str, track: str, ref_id: str) -> int | None:
        """The source's version now: what an item saved or added now is taken at."""
        if item_type == "question":
            q = get_question(track, ref_id) if track in CATALOG else None
            return q.version if q else None
        if item_type == "problem":
            return problem_versions(self.db, {ref_id}).get(ref_id)
        return None

    def _freshness(
        self, holder: Holder, user: User, rows: list[tuple[str, SourceRef | None]], *, detail: bool = True
    ) -> dict[str, NoteFreshness]:
        """Each holder's freshness by the notes' rule, its reviews and the problems' versions read in
        one query each."""
        fresh = SourceFreshness(self.db, user.id, holder)
        refs = [ref for _, ref in rows if ref is not None]
        problems = fresh.problems_for_refs(refs)
        reviews = fresh.reviews([hid for hid, ref in rows if ref is not None])
        return {
            hid: fresh.assess_ref(ref, reviews.get(hid, []), problems, detail=detail)
            for hid, ref in rows
            if ref is not None
        }

    def _seen_when_saved(
        self, user: User, item_type: str, track: str, ref_id: str
    ) -> tuple[bool, int | None]:
        """(saved, the version the saved item was last seen at: saved or reviewed). A collection
        takes this when the item is added, so the badge means the same in both places."""
        b = self.db.scalar(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.item_type == item_type,
                Bookmark.track == track,
                Bookmark.ref_id == ref_id,
            )
        )
        if b is None:
            return False, None
        rows = SourceFreshness(self.db, user.id, SAVED).reviews([b.id]).get(b.id, [])
        seen = [v for v in (b.content_version, rows[0].to_revision if rows else None) if v is not None]
        return True, max(seen) if seen else None

    def _added_version(self, user: User, item_type: str, track: str, ref_id: str) -> int | None:
        saved, seen = self._seen_when_saved(user, item_type, track, ref_id)
        return seen if saved else self._version_now(item_type, track, ref_id)

    def bookmarks(self, user: User) -> list[BookmarkOut]:
        rows = self.db.scalars(
            select(Bookmark).where(Bookmark.user_id == user.id).order_by(Bookmark.created_at.desc())
        ).all()
        fresh = self._freshness(
            SAVED, user, [(b.id, saved_ref(b.item_type, b.track, b.ref_id, b.content_version)) for b in rows]
        )
        out = []
        for b in rows:
            title, href, ok, why = self._describe(b.item_type, b.track, b.ref_id)
            out.append(
                BookmarkOut(
                    id=b.id,
                    freshness=fresh.get(b.id),
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
            self.db.add(
                Bookmark(
                    user_id=user.id,
                    item_type=body.item_type,
                    track=track,
                    ref_id=body.ref_id,
                    # to show later what changed since (docs/STORY_FRESHNESS.md)
                    content_version=self._version_now(body.item_type, track, body.ref_id),
                )
            )
        elif not on and existing is not None:
            forget(self.db, user.id, SAVED.kind, [existing.id])  # its reviews go with it
            self.db.delete(existing)  # removing works even for retired items
        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent request saved the same bookmark first: the outcome is what was asked.
            self.db.rollback()
        return self.bookmarks(user)

    def review_bookmark(self, user: User, body: SavedReviewIn) -> BookmarkOut:
        """ "Mark reviewed" for a saved item, at the version it was shown (once, also from two tabs).
        The saved item itself isn't changed, moved or unsaved."""
        track = body.track if body.item_type == "question" else ""
        b = self.db.scalar(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.item_type == body.item_type,
                Bookmark.track == track,
                Bookmark.ref_id == body.ref_id,
            )
        )
        if b is None:
            raise NotFoundError("That item isn't saved")
        ref = saved_ref(b.item_type, b.track, b.ref_id, b.content_version)
        if ref is None:
            raise AppError("A drill has no versions to review.", code="not_versioned")
        SourceFreshness(self.db, user.id, SAVED).review_ref(b.id, ref, body.reviewed_version)
        return next(x for x in self.bookmarks(user) if x.id == b.id)

    def review_item(self, user: User, cid: str, item_id: str, reviewed_version: int) -> CollectionOut:
        c = self._collection(user, cid)
        item = next((i for i in c.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("Item not found")
        ref = saved_ref(item.item_type, item.track, item.ref_id, item.content_version)
        if ref is None:
            raise AppError("A drill has no versions to review.", code="not_versioned")
        SourceFreshness(self.db, user.id, IN_COLLECTION).review_ref(item.id, ref, reviewed_version)
        return self.get(user, cid)

    def _review_one(
        self, user: User, holder: Holder, holder_id: str, ref: SourceRef | None, version: int, key: str
    ) -> ReviewResult:
        """One item's "Mark reviewed" in a batch, by the same rule as one at a time: recorded once for
        the version shown, never for a newer one silently, and nothing about the item itself changes."""
        if ref is None:
            return ReviewResult(
                key=key, outcome="not_versioned", message="A drill has no versions to review."
            )
        fresh = SourceFreshness(self.db, user.id, holder)
        rows = fresh.reviews([holder_id]).get(holder_id, [])
        seen = max(
            [v for v in (ref.captured, rows[0].to_revision if rows else None) if v is not None], default=None
        )
        try:
            after = fresh.review_ref(holder_id, ref, version)
        except NotFoundError:
            return ReviewResult(
                key=key,
                outcome="unavailable",
                message="No longer in the library, so there's nothing to review.",
            )
        except AppError as e:
            if e.code != "invalid_version":
                raise
            return ReviewResult(key=key, outcome="invalid_version", message=e.message)
        if seen is not None and version <= seen:
            return ReviewResult(
                key=key,
                outcome="already_reviewed",
                message=f"Already reviewed at version {seen}; nothing more recorded.",
            )
        if after.state == "needs_review":
            return ReviewResult(
                key=key,
                outcome="newer_since",
                message=f"Marked reviewed at version {version}; it's version {after.current_version} now, so it still asks.",
            )
        return ReviewResult(key=key, outcome="reviewed", message=f"Marked reviewed at version {version}.")

    def review_bookmarks(self, user: User, body: SavedReviewBatchIn) -> SavedReviewBatchOut:
        """Several saved items marked reviewed, each with its own outcome (docs/BULK_ACTIONS.md). An
        item that isn't one of yours is "not_there", the same answer as one never saved."""
        rows = self.db.scalars(select(Bookmark).where(Bookmark.user_id == user.id)).all()
        by_key = {(b.item_type, b.track, b.ref_id): b for b in rows}
        results: list[ReviewResult] = []
        seen: set[str] = set()
        for item in body.items:
            track = item.track if item.item_type == "question" else ""
            key = f"{item.item_type}:{track}:{item.ref_id}"
            if key in seen:
                results.append(
                    ReviewResult(key=key, outcome="repeated", message="Listed twice; counted once.")
                )
                continue
            seen.add(key)
            b = by_key.get((item.item_type, track, item.ref_id))
            if b is None:
                results.append(ReviewResult(key=key, outcome="not_there", message="Not saved (any more)."))
                continue
            ref = saved_ref(b.item_type, b.track, b.ref_id, b.content_version)
            results.append(self._review_one(user, SAVED, b.id, ref, item.reviewed_version, key))
        return SavedReviewBatchOut(bookmarks=self.bookmarks(user), results=results)

    def review_items(self, user: User, cid: str, body: CollectionReviewBatchIn) -> CollectionReviewBatchOut:
        """Several items of one collection marked reviewed, each with its own outcome. The collection
        must be yours (404 otherwise, before anything is looked at); an id that isn't one of its items
        is "not_there"."""
        c = self._collection(user, cid)
        items = {i.id: i for i in c.items}
        results: list[ReviewResult] = []
        seen: set[str] = set()
        for entry in body.items:
            key = entry.item_id
            if key in seen:
                results.append(
                    ReviewResult(key=key, outcome="repeated", message="Listed twice; counted once.")
                )
                continue
            seen.add(key)
            i = items.get(key)
            if i is None:
                results.append(
                    ReviewResult(key=key, outcome="not_there", message=f"Not in “{c.name}” (any more).")
                )
                continue
            ref = saved_ref(i.item_type, i.track, i.ref_id, i.content_version)
            results.append(self._review_one(user, IN_COLLECTION, i.id, ref, entry.reviewed_version, key))
        return CollectionReviewBatchOut(collection=self.get(user, cid), results=results)

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

    def duplicate(
        self, user: User, cid: str, name: str | None, key: str | None
    ) -> tuple[CollectionOut, bool]:
        """A new collection from this one (Volume 16, prompt 8): the same items in the same order,
        each at the version it was added at, with its "Mark reviewed" copied as the copy's own record;
        the queue starts fresh; the original is unchanged. Returns (the copy, made now): sent again
        with the same key, it's the copy that key made. Another account's collection is "not found",
        before anything else is looked at."""
        src = self._collection(user, cid)
        if key is not None:
            made = self._copy_for(user, cid, key)
            if made is not None:
                return self.get(user, made.id), False
        rows = self.db.execute(
            select(PracticeCollection.name).where(PracticeCollection.user_id == user.id)
        ).all()
        if len(rows) >= MAX_COLLECTIONS:
            raise AppError(
                f"You can keep up to {MAX_COLLECTIONS} collections, and you have {len(rows)}: delete one to "
                "make room for a copy.",
                code="too_many_collections",
                details={"limit": MAX_COLLECTIONS, "count": len(rows)},
            )
        taken = {collection_name_key(n) for (n,) in rows}
        if name is not None and name.strip():
            final = " ".join(name.split())
            if collection_name_key(final) in taken:
                raise ConflictError(
                    f"You already have a collection called “{final}” (names are compared in any letter "
                    "case). Choose another name.",
                    code="name_taken",
                )
        else:
            final = copy_name(src.name, taken)
        copy = PracticeCollection(
            user_id=user.id, name=final, queue_position=0, copied_from_id=src.id, client_request_id=key
        )
        items = sorted(src.items, key=lambda i: i.position)
        made_items = [
            CollectionItem(
                item_type=i.item_type,
                track=i.track,
                ref_id=i.ref_id,
                position=pos,
                # What each item was added at, kept: its version (and when, so "practiced since added"
                # reads the same). An item no longer in the library is carried as it is: the copy shows
                # it unavailable exactly as the original does, never swapped or dropped.
                content_version=i.content_version,
                added_at=i.added_at,
                queue_done_at=None,  # the queue starts fresh
            )
            for pos, i in enumerate(items)
        ]
        copy.items.extend(made_items)
        self.db.add(copy)
        try:
            self.db.flush()
        except IntegrityError:
            # The same key from another tab at the same moment: that request's copy is the one.
            self.db.rollback()
            made = self._copy_for(user, cid, key) if key is not None else None
            if made is None:
                raise
            return self.get(user, made.id), False
        # Each "Mark reviewed" as the copy's own record (its own holder): reviewing in one collection
        # never changes the other, and the original's history stays where it is.
        old_ids = {i.id: new.id for i, new in zip(items, made_items, strict=True)}
        if old_ids:
            for r in self.db.scalars(
                select(SourceReview).where(
                    SourceReview.user_id == user.id,
                    SourceReview.holder_kind == IN_COLLECTION.kind,
                    SourceReview.holder_id.in_(list(old_ids)),
                )
            ).all():
                self.db.add(
                    SourceReview(
                        user_id=user.id,
                        holder_kind=IN_COLLECTION.kind,
                        holder_id=old_ids[r.holder_id],
                        source_kind=r.source_kind,
                        source_id=r.source_id,
                        from_revision=r.from_revision,
                        to_revision=r.to_revision,
                        to_digest=r.to_digest,
                        decision=r.decision,
                        created_at=r.created_at,
                    )
                )
        self.db.commit()
        return self.get(user, copy.id), True

    def _copy_for(self, user: User, cid: str, key: str) -> PracticeCollection | None:
        """The copy a key already made, or None. A key used for a copy of another collection is refused."""
        made = self.db.scalar(
            select(PracticeCollection).where(
                PracticeCollection.user_id == user.id, PracticeCollection.client_request_id == key
            )
        )
        if made is not None and made.copied_from_id != cid:
            raise ConflictError(
                "That request key was already used for another copy.", code="idempotency_key_reused"
            )
        return made

    def rename(self, user: User, cid: str, name: str) -> CollectionOut:
        c = self._collection(user, cid)
        c.name = name.strip() or c.name
        c.updated_at = datetime.now(UTC)
        self.db.commit()
        return self.get(user, cid)

    def delete(self, user: User, cid: str) -> None:
        c = self._collection(user, cid)
        forget(self.db, user.id, IN_COLLECTION.kind, [i.id for i in c.items])
        self.db.delete(c)
        self.db.commit()

    def add_item(self, user: User, cid: str, body: CollectionItemIn) -> CollectionOut:
        c = self._collection(user, cid)
        item_type, track, ref = self._validate(body)
        if any(i.item_type == item_type and i.track == track and i.ref_id == ref for i in c.items):
            raise ConflictError(f"It's already in “{c.name}”.", code="already_in_collection")
        if len(c.items) >= MAX_ITEMS:
            raise AppError(f"A collection holds up to {MAX_ITEMS} items.", code="collection_full")
        name = c.name
        c.items.append(
            CollectionItem(
                item_type=item_type,
                track=track,
                ref_id=ref,
                position=len(c.items),
                content_version=self._added_version(user, item_type, track, ref),
            )
        )
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
        forget(self.db, user.id, IN_COLLECTION.kind, [item.id])  # its reviews go with it
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
                    content_version=self._added_version(user, item.item_type, track, item.ref_id),
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
                forget(self.db, user.id, IN_COLLECTION.kind, [found.id])
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

    def transfer(self, user: User, cid: str, body: CollectionTransferIn) -> CollectionTransferOut:
        """See _transfer_once. Another tab sending the same items at the same moment can add one first
        (uq_collection_item): this request then changes nothing, and is worked out once more against
        what's now there, so each of those items reads "already_there" and nothing is doubled."""
        if (done := self._transfer_replay(user, cid, body)) is not None:
            return done
        try:
            return self._transfer_once(user, cid, body)
        except IntegrityError:
            self.db.rollback()
            # Two copies of one keyed request at once: the other's receipt is its reply.
            if (done := self._transfer_replay(user, cid, body)) is not None:
                return done
            return self._transfer_once(user, cid, body)

    @staticmethod
    def _transfer_print(cid: str, body: CollectionTransferIn) -> str:
        items = [[i.item_type, i.track if i.item_type == "question" else "", i.ref_id] for i in body.items]
        return request_keys.fingerprint(
            "collection.transfer", {"from": cid, "to": body.to, "move": body.move, "items": items}
        )

    def _transfer_replay(
        self, user: User, cid: str, body: CollectionTransferIn
    ) -> CollectionTransferOut | None:
        """A keyed copy or move sent again after a lost reply (Volume 18, prompt 5): its first reply's
        outcomes, exactly ("Moved", not "Already there"), with both collections as they are now. The
        same key for another request is refused; another account's key finds nothing."""
        key = body.client_request_id
        if not key:
            return None
        self._collection(user, cid)  # yours, or 404, before anything is said about the key
        row = self.db.scalar(
            select(LifecycleReceipt).where(
                LifecycleReceipt.user_id == user.id, LifecycleReceipt.client_request_id == key
            )
        )
        if row is None:
            return None
        kept = row.impact or {}
        if row.action != TRANSFER_RECEIPT or not request_keys.same(
            kept.get("fingerprint"), self._transfer_print(cid, body)
        ):
            raise request_keys.reused("request")
        return CollectionTransferOut(
            source=self.get(user, cid),
            destination=self.get(user, body.to),
            results=[TransferResult.model_validate(r) for r in kept.get("results") or []],
            replayed=True,
        )

    def _transfer_once(self, user: User, cid: str, body: CollectionTransferIn) -> CollectionTransferOut:
        """Copy or move chosen items to another of your collections (Volume 17, prompt 6;
        docs/BULK_ACTIONS.md, "Copy or move items"), each with its own outcome, in one transaction.

        Each item arrives as it was: at the version it was added at, with when it was added and its
        "Mark reviewed" (moved with it, or copied as the new item's own record), at the end of the
        other collection in this one's order. Its queue mark stays with the collection it was marked
        in. A move takes an item out of this collection only once it's in the other one; an item the
        other collection already has is never doubled ("already_there"; a move then just takes it out
        of here). Items are named by what they are, so the same request sent again changes nothing
        twice: a moved item is then "already_there". Both collections must be yours (404 otherwise,
        before anything is looked at); sending to the same collection is refused."""
        src = self._collection(user, cid)
        dst = self._collection(user, body.to)
        if dst.id == src.id:
            raise ConflictError("Choose another collection to copy or move them to.", code="same_collection")
        verb = "Moved" if body.move else "Copied"
        sent: list[tuple[str, bool]] = []  # each key as sent, and whether it's a repeat
        first: dict[str, CollectionItem | None] = {}
        for item in body.items:
            track = item.track if item.item_type == "question" else ""
            key = f"{item.item_type}:{track}:{item.ref_id}"
            if key in first:
                sent.append((key, True))
                continue
            first[key] = next(
                (
                    i
                    for i in src.items
                    if (i.item_type, i.track, i.ref_id) == (item.item_type, track, item.ref_id)
                ),
                None,
            )
            sent.append((key, False))
        found_in_order = sorted(
            ((k, f) for k, f in first.items() if f is not None), key=lambda kf: kf[1].position
        )
        held = {(i.item_type, i.track, i.ref_id) for i in dst.items}
        made: dict[str, CollectionItem] = {}
        gone: list[CollectionItem] = []
        outcome: dict[str, TransferResult] = {}
        for key, found in found_in_order:  # in this collection's order, whatever order they were sent in
            ident = (found.item_type, found.track, found.ref_id)
            if ident in held:
                if body.move:
                    gone.append(found)
                    outcome[key] = TransferResult(
                        key=key,
                        outcome="moved",
                        message=f"Already in “{dst.name}”; taken out of “{src.name}”.",
                    )
                else:
                    outcome[key] = TransferResult(
                        key=key, outcome="already_there", message=f"Already in “{dst.name}”."
                    )
                continue
            if len(dst.items) + len(made) >= MAX_ITEMS:
                outcome[key] = TransferResult(
                    key=key, outcome="full", message=f"“{dst.name}” holds up to {MAX_ITEMS} items."
                )
                continue
            row = CollectionItem(
                item_type=found.item_type,
                track=found.track,
                ref_id=found.ref_id,
                position=len(dst.items) + len(made),
                content_version=found.content_version,  # the version it was added at
                added_at=found.added_at,
                queue_done_at=None,  # its queue mark stays with the collection it was marked in
            )
            made[found.id] = row
            held.add(ident)
            if body.move:
                gone.append(found)
            outcome[key] = TransferResult(
                key=key,
                outcome="moved" if body.move else "copied",
                message=f"{verb} to “{dst.name}”.",
            )
        for row in made.values():
            dst.items.append(row)
        self.db.flush()  # the new items exist before anything leaves this collection
        if made:
            reviews = self.db.scalars(
                select(SourceReview).where(
                    SourceReview.user_id == user.id,
                    SourceReview.holder_kind == IN_COLLECTION.kind,
                    SourceReview.holder_id.in_(list(made)),
                )
            ).all()
            for r in reviews:
                new_id = made[r.holder_id].id
                if body.move:
                    r.holder_id = new_id  # moved with it
                else:
                    self.db.add(
                        SourceReview(
                            user_id=user.id,
                            holder_kind=IN_COLLECTION.kind,
                            holder_id=new_id,
                            source_kind=r.source_kind,
                            source_id=r.source_id,
                            from_revision=r.from_revision,
                            to_revision=r.to_revision,
                            to_digest=r.to_digest,
                            decision=r.decision,
                            created_at=r.created_at,
                        )
                    )
        if gone:
            moved_reviews = set(made) if body.move else set()
            for found in gone:
                idx = src.items.index(found)
                if found.id not in moved_reviews:
                    forget(self.db, user.id, IN_COLLECTION.kind, [found.id])
                src.items.remove(found)
                if src.queue_position > idx:
                    src.queue_position -= 1
            for pos, i in enumerate(src.items):
                i.position = pos
            src.queue_position = min(src.queue_position, max(0, len(src.items) - 1))
        results: list[TransferResult] = []
        for key, repeat in sent:
            if repeat:
                results.append(
                    TransferResult(key=key, outcome="repeated", message="Listed twice; counted once.")
                )
            elif first[key] is not None:
                results.append(outcome[key])
            elif tuple(key.split(":", 2)) in held:
                # Not here but there: what a resend of a move finds (or it was there all along).
                results.append(
                    TransferResult(key=key, outcome="already_there", message=f"Already in “{dst.name}”.")
                )
            else:
                results.append(
                    TransferResult(key=key, outcome="not_there", message=f"Not in “{src.name}” (any more).")
                )
        now = datetime.now(UTC)
        if made:
            dst.updated_at = now
        if gone:
            src.updated_at = now
        if body.client_request_id:
            # Its reply, kept with what it did (one transaction), for a resend after a lost reply.
            self.db.add(
                LifecycleReceipt(
                    user_id=user.id,
                    client_request_id=body.client_request_id,
                    action=TRANSFER_RECEIPT,
                    target_id=src.id,
                    impact={
                        "fingerprint": self._transfer_print(cid, body),
                        "results": [r.model_dump(mode="json") for r in results],
                    },
                )
            )
        self.db.commit()
        return CollectionTransferOut(
            source=self.get(user, cid), destination=self.get(user, dst.id), results=results
        )

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
        fresh = self._freshness(
            IN_COLLECTION,
            user,
            [(i.id, saved_ref(i.item_type, i.track, i.ref_id, i.content_version)) for i in items],
        )
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
                    content_version=i.content_version,
                    freshness=fresh.get(i.id),
                )
            )
        return CollectionOut(
            **self._summary(c).model_dump(),
            item_list=out,
            queue_done=sum(x.queue_done for x in out),
            copied_from_id=c.copied_from_id,
        )

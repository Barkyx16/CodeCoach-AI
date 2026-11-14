"""What's saved to an account, as counts (Volume 10, prompt 10; docs/YOUR_DATA.md).

The privacy page's "Saved to your account" list. Each category counts the caller's own rows with
one `COUNT(*)` per table: no text, title or amount is read to show it. Every table that holds a
learner's rows is in exactly one category, counted or stored with it (`includes`); a test fails
when a new table isn't placed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models import User

Group = Literal["work", "sharing", "account"]

# The column naming the owner, where it isn't `user_id`.
OWNER_COLUMN = {"shares": "owner_id", "share_feedback": "reviewer_id", "content_reports": "reporter_id"}


@dataclass(frozen=True)
class Category:
    key: str
    group: Group
    label: str
    tables: tuple[str, ...]
    includes: tuple[str, ...] = ()  # stored with these, not counted on their own
    note: str | None = None


CATEGORIES: tuple[Category, ...] = (
    Category(
        "answers",
        "work",
        "Written and dictated answers, with their feedback and retries",
        ("practice_answers",),
        includes=("answer_evaluations", "interview_retries"),
        note="A dictated answer is kept as the text you sent. No audio reaches CodeCoach.",
    ),
    Category(
        "answer_reviews",
        "work",
        "Your own reviews of answers: self-reviews and criteria you questioned",
        ("answer_self_reviews", "answer_flags"),
    ),
    Category("code", "work", "Code submissions, with their test results", ("submissions",)),
    Category(
        "ai",
        "work",
        "AI coach replies: hints, code reviews and explanations",
        ("ai_interactions",),
        note="The reply you saw, never the prompt that carried your code.",
    ),
    Category(
        "sessions",
        "work",
        "Timed sessions and mock interviews, with interview transcripts (as text)",
        ("practice_sessions",),
    ),
    Category(
        "notes",
        "work",
        "Notes",
        ("notes",),
        note="A note you delete is kept 10 minutes so you can undo it, then removed.",
    ),
    Category("stories", "work", "Stories, with their earlier versions", ("experience_entries",)),
    Category("applications", "work", "Job applications, with their events and stages", ("applications",)),
    Category(
        "interview_days",
        "work",
        "Interview-day kits, your kit templates, and reflections on real interviews",
        ("interview_kits", "interview_reflections", "kit_templates"),
        includes=("reflection_actions", "source_reviews"),
    ),
    Category(
        "plans",
        "work",
        "Goals, practice plans and target roles, with their requirements' history",
        ("practice_goals", "practice_plans", "role_targets"),
        includes=("requirement_versions",),
    ),
    Category(
        "accepted_actions",
        "work",
        "Improvements you accepted from feedback (their occurrences are schedule entries)",
        ("accepted_actions",),
    ),
    Category("schedule", "work", "Schedule entries", ("schedule_entries",)),
    Category(
        "saved",
        "work",
        "Bookmarks, lists and questions saved for review",
        ("bookmarks", "practice_collections", "review_items"),
    ),
    Category("progress", "work", "Activity history and lesson progress", ("progress_events", "learn_events")),
    Category(
        "labs",
        "work",
        "Practice labs: drills, diagrams, code reviews, test cases, work samples, sample-answer readings "
        "and scenarios",
        (
            "drill_attempts",
            "whiteboard_attempts",
            "whiteboard_drafts",
            "code_review_attempts",
            "code_review_drafts",
            "test_design_runs",
            "work_sample_attempts",
            "work_sample_drafts",
            "comparison_attempts",
            "scenario_attempts",
        ),
    ),
    Category(
        "offers",
        "work",
        "Offer rehearsals and offer comparisons (the pay and terms you entered)",
        ("offer_rehearsals", "offer_comparisons"),
    ),
    Category(
        "shares",
        "sharing",
        "Answers you shared through a link, with the feedback they received",
        ("shares",),
        note="Anyone with a working link can read that answer until it expires or you turn it off.",
    ),
    Category(
        "feedback_given", "sharing", "Feedback you gave on other people's shared answers", ("share_feedback",)
    ),
    Category("reports", "sharing", "Problems you reported", ("content_reports",)),
    Category(
        "settings",
        "account",
        "Settings kept with your account: introduction progress and reminder choices",
        ("user_onboarding", "schedule_settings"),
    ),
    Category(
        "restores",
        "account",
        "Restores from a backup file",
        ("import_batches",),
        includes=("imported_records",),
    ),
    Category(
        "sign_in",
        "account",
        "Sign-in records: sessions, emailed codes and reset links, stored as hashes",
        ("refresh_tokens", "email_verification_tokens", "password_reset_tokens"),
        note="Deleted a week after they expire.",
    ),
    Category(
        "emails",
        "account",
        "Emails sent to you or waiting to be sent",
        ("email_jobs",),
        note="An email's content is cleared once it's sent, and the record goes 7 days later.",
    ),
    Category(
        "recovery",
        "account",
        "Recovery records: which of your requests were saved (ids only, no content)",
        ("update_receipts", "create_intents"),
    ),
)


def _count(db: Session, user_id: str, table_name: str) -> int:
    table = Base.metadata.tables[table_name]
    query = (
        select(func.count())
        .select_from(table)
        .where(table.c[OWNER_COLUMN.get(table_name, "user_id")] == user_id)
    )
    if table_name == "notes":
        query = query.where(table.c.deleted_at.is_(None))  # the undo window is in the note
    return int(db.scalar(query) or 0)


def data_summary(db: Session, user: User) -> list[dict]:
    """The account itself, then each category with the caller's count of it."""
    rows = [
        {
            "key": "account",
            "group": "account",
            "label": "Your account: email, name and career, and a hash of your password (never the password)",
            "count": 1,
            "note": None,
        }
    ]
    for c in CATEGORIES:
        rows.append(
            {
                "key": c.key,
                "group": c.group,
                "label": c.label,
                "count": sum(_count(db, user.id, t) for t in c.tables),
                "note": c.note,
            }
        )
    return rows

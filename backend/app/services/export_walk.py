"""Every attempt in the export carries its id (Volume 19, prompt 9; docs/YOUR_DATA.md).

The export gives each practice attempt the id History and the attempt's own page name it by, and
its conditions, so a record in the file can be matched with the app. This module names, for every
section of the export, which field identifies its attempts (`ATTEMPTS`), or why it holds none
(`OTHER`), so a reviewer can read the rule each section is held to. `walk(doc)` checks a file
against it: every section is classified (a section added later fails until it's named here), every
attempt has its id, and any record anywhere with `conditions` (the mark of an attempt) has an id.
It reads the document only; nothing is changed.
"""

from __future__ import annotations

from typing import Any

# section path -> (the field that identifies each attempt, whether each carries its conditions)
ATTEMPTS: dict[str, tuple[str, bool]] = {
    "submissions": ("id", True),
    "interviews": ("id", False),  # an interview's answers carry the conditions, in interview_answers
    "interview_answers": ("id", True),
    "drill_attempts": ("id", True),
    "whiteboard.attempts": ("id", True),
    "code_reviews.attempts": ("id", True),
    "test_design_runs": ("id", True),
    "work_samples.attempts": ("id", True),
    "comparisons": ("id", True),
    "scenario_attempts": ("id", True),
    "offer_rehearsals": ("id", False),  # a rehearsal records no in-app help
}

# section -> why it holds no attempts of its own
OTHER: dict[str, str] = {
    "export_version": "the file's format version",
    "exported_at": "when the file was made",
    "identities": "what ids mean in a version 2 file",
    "profile": "the account itself",
    "ai_feedback": "the coach's replies (each with its own id), not attempts",
    "activity": "progress events, not attempts",
    "practice_goals": "goals",
    "practice_plans": "plans and their activities",
    "target_roles": "job targets and their requirements",
    "interview_retries": "links an interview's question to its retry answer, by the answers' ids",
    "review_queue": "questions saved for review",
    "bookmarks": "saved items",
    "collections": "lists of saved items",
    "learn_events": "lesson progress events",
    "notes": "notes",
    "stories": "stories",
    "schedule": "planned practice",
    "answer_reviews": "your reflections on answers, which name the answer by id",
    "whiteboard": "drafts here; attempts are whiteboard.attempts",
    "code_reviews": "drafts here; attempts are code_reviews.attempts",
    "test_design_reveals": "when the faulty versions were shown, not attempts",
    "work_samples": "drafts here; attempts are work_samples.attempts",
    "comparison_openings": "when an explanation was opened, not attempts",
    "offer_comparisons": "offer terms you compared",
    "interview_reflections": "reflections on real interviews",
    "restores": "restore batches",
    "interview_kits": "interview-day kits",
    "kit_templates": "kit templates",
    "source_reviews": "sources you marked reviewed",
    "accepted_actions": "accepted improvements",
    "applications": "applications and their events",
    "onboarding": "the guided start",
    "dismissed_suggestions": "suggestions dismissed",
    "lab_reveals": "when a debugging exercise's repair was opened, not attempts",
    "listed_names": "names kept out of what leaves the app",
    "content_reports": "reports about content",
    "shares": "answers shared with a partner",
    "feedback_given": "feedback you gave a partner",
}


def _at(doc: dict, path: str) -> Any:
    node: Any = doc
    for part in path.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def _with_conditions(node: Any, path: str) -> list[tuple[str, dict]]:
    """Every record under node that has a `conditions` key (an attempt's mark), with its path."""
    out: list[tuple[str, dict]] = []
    if isinstance(node, dict):
        if "conditions" in node:
            out.append((path, node))
        for k, v in node.items():
            if k != "conditions":
                out += _with_conditions(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _with_conditions(v, f"{path}[{i}]")
    return out


def walk(doc: dict) -> list[dict]:
    """Problems found, as {path, rule, detail}; an empty list means every attempt has its id."""
    issues: list[dict] = []
    top = {p.split(".")[0] for p in ATTEMPTS}
    for section in doc:
        if section not in OTHER and section not in top:
            issues.append(
                {
                    "path": section,
                    "rule": "unclassified_section",
                    "detail": "a section not named in export_walk",
                }
            )
    for path, (field, with_conditions) in ATTEMPTS.items():
        rows = _at(doc, path)
        if rows is None:
            continue
        if not isinstance(rows, list):
            issues.append({"path": path, "rule": "not_a_list", "detail": "attempts should be a list"})
            continue
        for i, rec in enumerate(rows):
            where = f"{path}[{i}]"
            if not isinstance(rec, dict) or not isinstance(rec.get(field), str) or not rec[field]:
                issues.append({"path": where, "rule": "attempt_without_id", "detail": f"no {field!r}"})
            elif with_conditions and "conditions" not in rec:
                issues.append(
                    {"path": where, "rule": "attempt_without_conditions", "detail": "no 'conditions'"}
                )
    for where, rec in _with_conditions(doc, "$"):
        if not isinstance(rec.get("id"), str) or not rec["id"]:
            issues.append(
                {"path": where, "rule": "attempt_without_id", "detail": "has conditions but no 'id'"}
            )
    return issues

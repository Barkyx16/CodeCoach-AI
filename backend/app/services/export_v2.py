"""Account export, version 2: the version 1 document plus identities and typed links.

Version 2 is opt-in (`GET /api/v1/me/export?version=2`); version 1 stays the default and is what
restore reads. Every record keeps all of its version 1 fields unchanged. Records that others point
to gain an `id`, and records that point to others gain `links`: typed references, each with a
state saying what the file can tell about its target. See docs/BACKUP_FORMAT.md.

Identity scope: an id is the record's id in this account, unique per record type within one file.
It's opaque: not stable across accounts, never a credential or proof of ownership, and never used
by restore (restored records always get new ids).

Reference states:
- `present`: the target is in this file, with that type and id.
- `missing`: the target is no longer in the account (deleted, or a note in the bin), or isn't
  this account's. The reference is kept as history; nothing is invented to fill it.
- `public`: library content (a question, problem, lesson or drill), named by its public id.
- `not_exported`: the account's own record, in a section that has no ids in this format (plan
  activities, the review queue, practice sessions).
- `unknown`: not recorded (for example the story version a kit chose before versions were kept).

Consistency: the file is built in one database session, but on PostgreSQL (read committed) a
concurrent edit can land in one section and not another; it's not a point-in-time snapshot.
`present` is decided from the file's own contents, so a link never claims a target the file
doesn't contain.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import User
from app.services.account import export_user_data

EXPORT_VERSION_2 = 2
TYPES = (
    "application",
    "application_event",
    "target",
    "requirement",
    "story",
    "note",
    "schedule_entry",
    "accepted_action",
    "interview_kit",
    "interview_reflection",
    "reflection_step",
    "bookmark",
    "question",
    "problem",
    "lesson",
    "drill",
    "plan_activity",
    "review_item",
    "practice_session",
)
STATES = ("present", "missing", "public", "not_exported", "unknown")
PUBLIC = {"question", "problem", "lesson", "drill"}
NOT_EXPORTED = {"plan_activity", "review_item", "practice_session"}


def _ref(present: dict[str, set[str]], kind: str, ident: str | None, **extra: Any) -> dict | None:
    if ident is None or ident == "":
        return None
    if kind in PUBLIC:
        state = "public"
    elif kind in NOT_EXPORTED:
        state = "not_exported"
    else:
        state = "present" if ident in present.get(kind, set()) else "missing"
    return {"type": kind, "id": ident, "state": state, **extra}


def _bookmark_id(item_type: str, career: str | None, item: str) -> str:
    return f"{item_type}:{career or ''}/{item}"


def export_v2(db: Session, user: User) -> dict:
    doc = export_user_data(db, user, with_ids=True)
    doc["export_version"] = EXPORT_VERSION_2
    doc["identities"] = {
        "scope": "unique per record type within this file; opaque; not stable across accounts",
        "restore": "not supported for version 2; restore reads version 1",
        "states": list(STATES),
    }
    apps = doc["applications"]
    for b in doc["bookmarks"]:
        b["id"] = _bookmark_id(b["type"], b["career"], b["item"])
    present: dict[str, set[str]] = {
        "application": {a["id"] for a in apps},
        "application_event": {e["id"] for a in apps for e in a["events"]},
        "target": {t["id"] for t in doc["target_roles"]},
        "requirement": {r["id"] for t in doc["target_roles"] for r in t["requirements"]},
        "story": {s["id"] for s in doc["stories"]},
        "note": {n["id"] for n in doc["notes"]},
        "schedule_entry": {e["id"] for e in doc["schedule"]["entries"]},
        "accepted_action": {a["id"] for a in doc["accepted_actions"]},
        "interview_kit": {k["id"] for k in doc["interview_kits"]},
        "interview_reflection": {r["event_id"] for r in doc["interview_reflections"]},
        "reflection_step": {a["id"] for r in doc["interview_reflections"] for a in r["actions"]},
        "bookmark": {b["id"] for b in doc["bookmarks"]},
    }

    def ref(kind: str, ident: str | None, **extra: Any) -> dict | None:
        return _ref(present, kind, ident, **extra)

    for a in apps:
        a["links"] = {
            "target": ref("target", a["target"]),
            "stories": [ref("story", s) for s in a["stories"] or []],
        }
    for r in doc["interview_reflections"]:
        r["id"] = r["event_id"]  # a reflection is identified by its interview, like a kit
        r["links"] = {
            "application": ref("application", r["application_id"]),
            "event": ref("application_event", r["event_id"]),
            "stories": [ref("story", s) for s in r["story_ids"] or []],
        }
        for step in r["actions"]:
            applied = step["applied_ref"] if step["status"] == "accepted" else None
            if step["target"] == "notebook":
                created = ref("note", applied)
            elif step["target"] == "schedule":
                created = ref("schedule_entry", applied)
            elif step["target"] == "saved" and applied:
                career, _, item = applied.partition("/")
                created = ref("bookmark", _bookmark_id("question", career, item))
            else:
                created = None
            step["links"] = {"created": created}
    for k in doc["interview_kits"]:
        versions = k.get("story_versions_when_chosen") or {}
        stories = []
        for sid in k["stories"] or []:
            link = ref("story", sid)
            if link is not None:
                # The story's version when it was chosen, or "unknown" for kits saved before that was kept.
                link["version_when_chosen"] = versions.get(sid, "unknown")
                stories.append(link)
        k["links"] = {
            "event": ref("application_event", k["event"]),
            "stories": stories,
            # Accepted improvements on its checklist, by id (their words are the action's).
            "actions": [
                ref("accepted_action", c.get("action_id"))
                for c in k.get("checklist") or []
                if c.get("origin") == "action"
            ],
        }
    kind_of = {
        "plan_item": "plan_activity",
        "review_item": "review_item",
        "question": "question",
        "problem": "problem",
        "drill": "drill",
        "application_event": "application_event",
        "accepted_action": "accepted_action",
    }
    for e in doc["schedule"]["entries"]:
        e["links"] = {"activity": ref(kind_of.get(e["kind"], e["kind"]), e["ref"])}
    for a in doc["accepted_actions"]:
        a["links"] = {
            "source": ref("practice_session", a["source"]["interview"]),
            "occurrences": [ref("schedule_entry", o.get("schedule_entry")) for o in a["occurrences"]],
        }
    for n in doc["notes"]:
        src = n["source"]
        n["links"] = {
            "source": ref(
                "practice_session" if src and src["type"] == "interview" else (src or {}).get("type", ""),
                (src or {}).get("id"),
            )
            if src
            else None
        }
    return doc


# --- validation (read-only) ------------------------------------------------------------------------


def _records(doc: dict) -> list[tuple[str, str, dict]]:
    """(type, path, record) for every record that has an id in a version 2 file."""
    out: list[tuple[str, str, dict]] = []
    for i, a in enumerate(doc.get("applications") or []):
        out.append(("application", f"applications[{i}]", a))
        for j, e in enumerate(a.get("events") or []):
            out.append(("application_event", f"applications[{i}].events[{j}]", e))
    for i, t in enumerate(doc.get("target_roles") or []):
        out.append(("target", f"target_roles[{i}]", t))
        for j, r in enumerate(t.get("requirements") or []):
            out.append(("requirement", f"target_roles[{i}].requirements[{j}]", r))
    for section, kind in (
        ("stories", "story"),
        ("notes", "note"),
        ("interview_kits", "interview_kit"),
        ("accepted_actions", "accepted_action"),
        ("interview_reflections", "interview_reflection"),
        ("bookmarks", "bookmark"),
    ):
        for i, r in enumerate(doc.get(section) or []):
            out.append((kind, f"{section}[{i}]", r))
    for i, e in enumerate((doc.get("schedule") or {}).get("entries") or []):
        out.append(("schedule_entry", f"schedule.entries[{i}]", e))
    for i, r in enumerate(doc.get("interview_reflections") or []):
        for j, s in enumerate(r.get("actions") or []):
            out.append(("reflection_step", f"interview_reflections[{i}].actions[{j}]", s))
    return out


def _links(record: dict) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for name, value in (record.get("links") or {}).items():
        if isinstance(value, list):
            out.extend((f"links.{name}[{k}]", v) for k, v in enumerate(value))
        else:
            out.append((f"links.{name}", value))
    return out


def validate_export(doc: Any) -> list[dict]:
    """Problems in a version 2 export, as {path, rule, detail}; an empty list means none found.

    Checked: the version; every record that should have an id has a string id, unique per type;
    every link names a known type and state; a `present` link points to a record of that type in
    the file (not a missing one, and not one of another type); a link that says its target isn't
    here doesn't point to a record that is. It doesn't check owners (a file can't prove whose it
    is), and it changes nothing.
    """
    issues: list[dict] = []

    def issue(path: str, rule: str, detail: str) -> None:
        issues.append({"path": path, "rule": rule, "detail": detail})

    if not isinstance(doc, dict):
        return [{"path": "$", "rule": "not_an_export", "detail": "not a JSON object"}]
    if doc.get("export_version") != EXPORT_VERSION_2:
        return [
            {
                "path": "export_version",
                "rule": "not_version_2",
                "detail": f"links are checked in version 2 exports; this file is {doc.get('export_version')!r}",
            }
        ]
    seen: dict[str, dict[str, str]] = {}
    records = _records(doc)
    for kind, path, rec in records:
        ident = rec.get("id") if isinstance(rec, dict) else None
        if not isinstance(ident, str) or not ident:
            issue(path, "missing_id", f"a {kind} without an id")
            continue
        if ident in seen.setdefault(kind, {}):
            issue(path, "duplicate_id", f"{kind} {ident} is also at {seen[kind][ident]}")
        else:
            seen[kind][ident] = path
    for _kind, path, rec in records:
        if not isinstance(rec, dict):
            continue
        for lpath, link in _links(rec):
            where = f"{path}.{lpath}"
            if link is None:
                continue
            if not isinstance(link, dict) or not isinstance(link.get("id"), str):
                issue(where, "malformed_link", "a link must be an object with a string id")
                continue
            ltype, lid, state = link.get("type"), link["id"], link.get("state")
            if ltype not in TYPES:
                issue(where, "unknown_type", f"unknown record type {ltype!r}")
                continue
            if state not in STATES:
                issue(where, "unknown_state", f"unknown state {state!r}")
                continue
            here = lid in seen.get(ltype, {})
            elsewhere = [k for k, ids in seen.items() if k != ltype and lid in ids]
            if state == "present" and not here:
                issue(
                    where,
                    "wrong_type" if elsewhere else "dangling",
                    f"says {ltype} {lid} is in the file, but "
                    + (f"that id is a {elsewhere[0]}" if elsewhere else "it isn't"),
                )
            elif state != "present" and here:
                issue(where, "inconsistent_state", f"says {ltype} {lid} is {state}, but it's in the file")
            elif state == "public" and ltype not in PUBLIC:
                issue(where, "wrong_state", f"a {ltype} isn't public library content")
    return issues

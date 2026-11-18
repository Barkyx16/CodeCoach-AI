"""What content is still waiting for its review (Volume 19, prompt 7; docs/LEARN_CONTENT.md).

`python -m app.cli content review-status [--owed] [--json]` lists every content item with its format,
id, title, version and review status, read from the content files as they are, and where its review
note lives (the file and the field), so the author can find it:

- **Review owed**: drafted and not yet checked: a lesson or scenario whose review says
  `generated_draft`, or a note that names no check at all.
- **Reviewed**, with what that review was, in the note's own words: the author's review
  (`author_reviewed`), machine-checked, checked for consistency, or a dated check; and whether the
  note says no outside reviewer has seen it.
- **No review recorded**: formats with no review field (drills, whiteboard prompts), and the generated
  banks (career questions, counted per career; coding problems), whose labels say they're generated
  and not reviewed by a subject-matter expert.

Nothing is inferred or upgraded: a kind is named only when the note says it, and an unknown note is
listed as owed. It's a report, not a gate: the exit code is 0 whatever it finds. Every collector
reads its format's own field directly, so a renamed field raises instead of dropping a format.

A claim names its check (Volume 20, prompt 8): a note that says "machine-checked" is listed as
reviewed only when its format is in `MACHINE_CHECKS`, which names the test and the command in this
repository that do the check, the CI steps that run them, and what the check proves; the report
prints that beside each item. A claim in a format with no mapped check is listed apart, "claimed,
no check found here". The report runs no check itself, and changes no content's status.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

Group = Literal["owed", "unverified", "reviewed", "none"]
GROUP_TITLE: dict[Group, str] = {
    "owed": "Review owed (drafted and not yet checked)",
    "unverified": "Claimed machine-checked, no check found here",
    "reviewed": "Reviewed",
    "none": "No review recorded",
}
BACKEND = Path(__file__).resolve().parents[2]
SEED = BACKEND / "app" / "seed"


@dataclass(frozen=True)
class Item:
    format: str
    id: str
    title: str
    version: int | None
    group: Group
    kind: str  # what the review was, or why none is owed or recorded
    status: str  # the content's own words: its review status and note, as authored
    where: str  # the file and field that hold its review note
    count: int | None = None  # for a counted bank: how many items share this line
    check: dict | None = None  # for a machine-checked claim: the check that backs it (MACHINE_CHECKS)


@dataclass(frozen=True)
class Check:
    """A check in this repository that does what a "machine-checked" note claims."""

    proves: str  # what it proves, in a short phrase
    test: str  # the pytest that runs it: "backend/tests/<file>.py::<function>"
    command: str  # the command that runs it, from backend/
    ci: tuple[
        tuple[str, str], ...
    ]  # (job, step) in .github/workflows/ci.yml that run the test and the command


_BACKEND_JOB = "Backend (lint, types, SQLite tests, reference solutions)"
_RUNS = ((_BACKEND_JOB, "Tests (SQLite)"), (_BACKEND_JOB, "Reference solutions pass every seeded test"))
_VERIFY = "python scripts/verify_reference_solutions.py"

# Each format whose notes can say "machine-checked", and the check that backs the claim. A test
# fails when a named test, command or CI step no longer exists, so this can't go stale silently.
MACHINE_CHECKS: dict[str, Check] = {
    "debugging exercise": Check(
        "the faulty starter fails exactly its reproduction cases, and the repair and every alternative "
        "pass every test",
        "backend/tests/test_debugging_lab.py::test_each_starter_shows_its_defect_and_each_repair_passes",
        _VERIFY,
        _RUNS,
    ),
    "code-review exercise": Check(
        "the reviewed code fails exactly the public tests its defects cite, with the results they state, "
        "and the repair passes every test",
        "backend/tests/test_code_reviews.py::test_each_authored_review_matches_what_the_code_does_on_the_tests",
        _VERIFY,
        _RUNS,
    ),
    "test-design exercise": Check(
        "every faulty version differs from the reference on its own witness case, and the reference gives "
        "each example's expected output",
        "backend/tests/test_test_design.py::test_every_exercise_passes_the_jdk_check",
        _VERIFY,
        _RUNS,
    ),
}
# Every other format the report knows, and why no machine check is mapped for it. A test checks each
# format is in one of the two; a "machine-checked" claim in one of these is listed as unverified.
NO_MACHINE_CHECK: dict[str, str] = {
    "lesson": "the author's review or a draft (its Review); no machine check is claimed",
    "scenario": "the author's review or a draft (its Review); no machine check is claimed",
    "sample-answer lesson": "checked for consistency by its author; no machine check here",
    "work sample": "checked for consistency by its author; no machine check here",
    "offer case": "checked for consistency by its author; no machine check here",
    "question follow-up": "a dated check of the relationship; no machine check here",
    "problem follow-up": "a dated check of the relationship; no machine check here",
    "drill": "no review field",
    "whiteboard prompt": "no review field",
    "career questions": "generated; no review recorded",
    "coding problems": "generated; each reference solution is run by scripts/verify_reference_solutions.py, "
    "but no review is claimed",
}


# What a note says it was, by its own words; nothing else is read into it.
_KINDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"machine-checked", re.I), "machine-checked"),
    (re.compile(r"checked for (internal )?consistency", re.I), "checked for consistency"),
    (re.compile(r"^Reviewed \d{4}-\d{2}-\d{2}\b"), "a dated check (no reviewer named)"),
)
_NO_OUTSIDE = re.compile(r"\bnot (yet )?reviewed by (an? |the )?(outside|licensed|subject-matter)", re.I)


def _rel(path: Path) -> str:
    resolved = path.resolve()
    return f"backend/{resolved.relative_to(BACKEND)}" if resolved.is_relative_to(BACKEND) else str(resolved)


def _text_kind(text: str) -> tuple[Group, str]:
    """A free-text note: reviewed with the kind it names, or owed when it names no check."""
    for pattern, kind in _KINDS:
        if pattern.search(text):
            return "reviewed", kind + ("; no outside review" if _NO_OUTSIDE.search(text) else "")
    return "owed", "its note names no check"


def _structured(status: str, by: str, on: str, note: str) -> tuple[Group, str, str]:
    """A Review(status, by, on, note): author_reviewed or generated_draft, as written."""
    said = f"{status} ({by}, {on}). {note}"
    if status == "generated_draft":
        return "owed", "drafted, not yet reviewed by the project author", said
    if status == "author_reviewed":
        outside = "; no outside review" if _NO_OUTSIDE.search(note) else ""
        return "reviewed", f"the author's review{outside}", said
    return "owed", f"unknown review status {status!r}", said


def _lessons() -> Iterator[Item]:
    from app.learn import UNIT_INDEX

    for u in UNIT_INDEX.values():
        r = u.review
        group, kind, said = _structured(r.status, r.by, r.on, r.note)
        yield Item(
            "lesson", u.id, u.title, u.version, group, kind, said, "backend/app/learn/units.py: review"
        )


def _scenarios() -> Iterator[Item]:
    from app.scenarios import SCENARIO_INDEX, content, queues

    def home(s: object) -> str:
        """The module that defines it: the queues first (content.py imports their list)."""
        for mod in (queues, content):
            if any(
                getattr(mod, n) is s for n in dir(mod) if n.isupper() and n not in ("SCENARIOS", "QUEUES")
            ):
                return _rel(Path(str(mod.__file__)))
        raise LookupError(f"scenario {getattr(s, 'id', s)!r}: no module defines it")

    for s in SCENARIO_INDEX.values():
        r = s.review
        group, kind, said = _structured(r.status, r.by, r.on, r.note)
        yield Item("scenario", s.id, s.title, s.version, group, kind, said, f"{home(s)}: review")


def _seeded(fmt: str, folder: str, key: str, field: str = "review_status") -> Iterator[Item]:
    """Formats authored as JSON files: each file's own review field, read as written."""
    for path in sorted((SEED / folder).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        block = data["lab"] if field.startswith("lab.") else data
        text = block[field.removeprefix("lab.")]
        version = block["version"] if field.startswith("lab.") else data["version"]
        group, kind = _text_kind(text)
        yield Item(fmt, data[key], data["title"], int(version), group, kind, text, f"{_rel(path)}: {field}")


def _sample_lessons() -> Iterator[Item]:
    return _seeded("sample-answer lesson", "comparisons", "id")


def _work_samples() -> Iterator[Item]:
    return _seeded("work sample", "worksamples", "id")


def _code_reviews() -> Iterator[Item]:
    return _seeded("code-review exercise", "reviews", "slug")


def _test_design() -> Iterator[Item]:
    return _seeded("test-design exercise", "testdesign", "slug")


def _debugging() -> Iterator[Item]:
    return _seeded("debugging exercise", "debugging", "slug", "lab.review_status")


def _offers() -> Iterator[Item]:
    import app.offers as offers

    for c in offers.CASES:
        group, kind = _text_kind(c.review_status)
        yield Item(
            "offer case", c.id, c.title, c.version, group, kind, c.review_status,
            f"{_rel(Path(str(offers.__file__)))}: REVIEW (review_status)",
        )  # fmt: skip


def _followups() -> Iterator[Item]:
    from app.careers import followups
    from app.content import problem_followups

    for r in followups.RELATIONSHIPS:
        group, kind = _text_kind(r.review_status)
        yield Item(
            "question follow-up", f"{r.track}/{r.from_id}>{r.to_id}", r.objective, None, group, kind,
            r.review_status, f"{_rel(Path(str(followups.__file__)))}: review_status",
        )  # fmt: skip
    for p in problem_followups.PAIRS:
        group, kind = _text_kind(p.review_status)
        yield Item(
            "problem follow-up", f"{p.from_slug}>{p.to_slug}", p.shares, None, group, kind, p.review_status,
            f"{_rel(Path(str(problem_followups.__file__)))}: review_status",
        )  # fmt: skip


def _unreviewed_formats() -> Iterator[Item]:
    """Formats whose content has no review field at all."""
    import app.drills as drills
    import app.whiteboard as whiteboard

    for d in drills.DRILLS:
        yield Item(
            "drill", d.id, d.title, None, "none", "no review field", "",
            f"{_rel(Path(str(drills.__file__)))} (no review field)",
        )  # fmt: skip
    for p in whiteboard.PROMPTS:
        yield Item(
            "whiteboard prompt", p.id, p.title, p.version, "none", "no review field", "",
            f"{_rel(Path(str(whiteboard.__file__)))} (no review field)",
        )  # fmt: skip


# The career question bank's quality status, as its labels say it (app/services/content.py, meta):
# generated by the question templates, and not reviewed by a subject-matter expert.
QUESTION_STATUS = "Generated by CodeCoach's question templates; not reviewed by a subject-matter expert"
PROBLEM_STATUS = (
    "Generated for CodeCoach's coding problem bank; not reviewed by a subject-matter expert. A reference "
    "solution's check is recorded per server (content_checks), not in these files"
)


def _questions() -> Iterator[Item]:
    from app.careers import CATALOG
    from app.careers.questions import generated_questions

    for track, profile in CATALOG.items():
        n = len(generated_questions(track))
        yield Item(
            "career questions", track, profile.title, None, "none", "generated, no review recorded",
            QUESTION_STATUS, "backend/app/careers (generated); labels: backend/app/services/content.py: meta",
            count=n,
        )  # fmt: skip


def _problems() -> Iterator[Item]:
    n = len(list((SEED / "problems").glob("*.json")))
    yield Item(
        "coding problems", "problem-bank", "Coding problem bank", None, "none",
        "generated, no review recorded", PROBLEM_STATUS, "backend/app/seed/problems (generated)", count=n,
    )  # fmt: skip


# Every format, in the order they're reported. A test checks each is present.
FORMATS: dict[str, Callable[[], Iterator[Item]]] = {
    "lesson": _lessons,
    "scenario": _scenarios,
    "sample-answer lesson": _sample_lessons,
    "work sample": _work_samples,
    "code-review exercise": _code_reviews,
    "test-design exercise": _test_design,
    "debugging exercise": _debugging,
    "offer case": _offers,
    "follow-ups": _followups,
    "drills and whiteboard prompts": _unreviewed_formats,
    "career questions": _questions,
    "coding problems": _problems,
}


def _backed(item: Item) -> Item:
    """A machine-checked claim names its check, or is listed as having none here. Nothing else changes."""
    if item.group != "reviewed" or not item.kind.startswith("machine-checked"):
        return item
    check = MACHINE_CHECKS.get(item.format)
    if check is None:
        return replace(item, group="unverified", kind=f"{item.kind}: claimed, no check found here")
    return replace(
        item,
        check={
            "proves": check.proves,
            "test": check.test,
            "command": check.command,
            "ci": [f"{job} › {step}" for job, step in check.ci],
        },
    )


def report() -> list[Item]:
    return [_backed(item) for read in FORMATS.values() for item in read()]


def render(items: list[Item], *, owed_only: bool = False) -> str:
    lines: list[str] = []
    for group in ("owed", "unverified", "reviewed", "none"):
        if owed_only and group not in ("owed", "unverified"):  # --owed: what isn't backed, too
            continue
        rows = [i for i in items if i.group == group]
        lines.append(f"{GROUP_TITLE[group]}: {len(rows)}")
        counted: dict[str, Item] = {}
        for i in rows:
            if i.count is not None:  # a generated bank: one line each, its status said once below
                lines.append(f"  {i.format} · {i.id} · {i.title}: {i.count}")
                counted.setdefault(i.format, i)
                continue
            version = f" v{i.version}" if i.version is not None else ""
            lines.append(f"  {i.format} · {i.id}{version} · {i.title}")
            lines.append(f"      {i.kind}. {i.status}".rstrip())
            if i.check:
                lines.append(f"      check: {i.check['proves']}")
                lines.append(f"        by {i.check['test']} and `{i.check['command']}`")
                lines.append(f"        run in CI: {'; '.join(i.check['ci'])}")
            lines.append(f"      note: {i.where}")
        for fmt, first in counted.items():
            lines.append(f"  {fmt}: {first.kind}. {first.status}")
            lines.append(f"      note: {first.where}")
        lines.append("")
    lines.append(
        "This is a report of what the content says, not a review: marking something reviewed is the author's act."
    )
    return "\n".join(lines)


def as_json(items: list[Item], *, owed_only: bool = False) -> str:
    rows = [asdict(i) for i in items if not owed_only or i.group in ("owed", "unverified")]
    return json.dumps(
        {
            "items": rows,
            "owed": sum(1 for i in items if i.group == "owed"),
            "unverified": sum(1 for i in items if i.group == "unverified"),
        },
        indent=2,
    )

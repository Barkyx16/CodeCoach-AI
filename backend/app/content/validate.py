"""Content quality gates: `python -m app.cli validate-content [--run-reference] [--record]`.

Checks, without changing anything (except recording check results with --record):
- Career questions: required fields, valid level and kind, unique ids, the career mapping, and
  the bank size per level.
- Published corrections and retirements: they point at content that exists, corrections only
  touch correctable fields, and versions run 2, 3, ... with no gaps.
- Learn units: prerequisites, linked questions and practice targets exist (and aren't retired).
- Branching scenarios: the existing graph validator.
- Coding problems (seed files): required keys, unique slugs, valid difficulty, examples, at least
  one public and one hidden test, and a reference solution file.
- With --run-reference: compile and run each trusted reference solution against every test
  (scripts/verify_reference_solutions.py; needs a local JDK). With --record the results are
  stored in content_checks, which is the only source of the "reference solution passed" label.

Passing this is automated validation, not expert review; see docs/CONTENT_QUALITY.md.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.careers.formats import KIND_LABEL
from app.careers.questions import CORRECTABLE_FIELDS, LEVELS, PER_LEVEL, generated_questions, get_question
from app.learn import UNIT_INDEX
from app.models import ContentCheck, ContentStatus, ContentVersion, Problem
from app.scenarios import SCENARIO_INDEX, ScenarioError, validate

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROBLEMS_DIR = BACKEND_DIR / "app" / "seed" / "problems"
DEBUGGING_DIR = BACKEND_DIR / "app" / "seed" / "debugging"
REFERENCE_DIR = BACKEND_DIR / "app" / "seed" / "reference"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)  # (slug, passed, detail)

    @property
    def ok(self) -> bool:
        return not self.errors


def _questions(report: Report) -> None:
    total = 0
    for track, profile in CATALOG.items():
        qs = generated_questions(track)
        total += len(qs)
        seen: set[str] = set()
        for q in qs:
            where = f"question {track}/{q.id}"
            if q.id in seen:
                report.errors.append(f"{where}: duplicate id")
            seen.add(q.id)
            if q.track != track:
                report.errors.append(f"{where}: mapped to career {q.track!r}")
            if not q.title.strip() or not q.prompt.strip():
                report.errors.append(f"{where}: missing title or prompt")
            if q.difficulty not in LEVELS:
                report.errors.append(f"{where}: unknown level {q.difficulty!r}")
            if q.kind not in KIND_LABEL:
                report.errors.append(f"{where}: unknown kind {q.kind!r}")
            if not q.rubric or not q.outline:
                report.errors.append(f"{where}: no rubric or outline")
        for level in LEVELS:
            n = sum(q.difficulty == level for q in qs)
            if n < PER_LEVEL:
                report.warnings.append(
                    f"career {track} ({profile.title}): {n} {level} questions (target {PER_LEVEL})"
                )
    report.counts["questions"] = total


def _db_content(db: Session, report: Report, seed_slugs: set[str]) -> None:
    def exists(content_type: str, content_id: str) -> bool:
        if content_type == "question":
            track, _, qid = content_id.partition("/")
            return track in CATALOG and get_question(track, qid) is not None
        return (
            db.scalar(select(Problem.id).where(Problem.slug == content_id)) is not None
            or content_id in seed_slugs
        )

    versions: dict[tuple[str, str], list[int]] = {}
    for v in db.scalars(select(ContentVersion).order_by(ContentVersion.version)):
        key = (v.content_type, v.content_id)
        versions.setdefault(key, []).append(v.version)
        if not exists(*key):
            report.errors.append(
                f"correction {v.content_type} {v.content_id} v{v.version}: content doesn't exist"
            )
        extra = set(v.fields) - set(CORRECTABLE_FIELDS)
        if extra:
            report.errors.append(
                f"correction {v.content_id} v{v.version}: fields that can't be corrected: {sorted(extra)}"
            )
        if not v.change_note.strip():
            report.errors.append(f"correction {v.content_id} v{v.version}: no change note")
    for key, vs in versions.items():
        if vs != list(range(2, 2 + len(vs))):
            report.errors.append(f"corrections for {key[1]}: versions {vs} should run 2, 3, ... without gaps")
    for s in db.scalars(select(ContentStatus)):
        if not exists(s.content_type, s.content_id):
            report.errors.append(f"retired {s.content_type} {s.content_id}: content doesn't exist")
    report.counts["corrections"] = sum(len(v) for v in versions.values())


def _learn(report: Report, retired: set[tuple[str, str]], seed_slugs: set[str]) -> None:
    for unit in UNIT_INDEX.values():
        where = f"lesson {unit.id}"
        if unit.track not in CATALOG:
            report.errors.append(f"{where}: unknown career {unit.track!r}")
        for pre in unit.prerequisites:
            if pre not in UNIT_INDEX:
                report.errors.append(f"{where}: prerequisite {pre!r} doesn't exist")
        for qid in unit.question_ids:
            if get_question(unit.track, qid) is None:
                report.errors.append(f"{where}: linked question {qid!r} doesn't exist")
            elif ("question", f"{unit.track}/{qid}") in retired:
                report.warnings.append(f"{where}: linked question {qid!r} is retired")
        target = unit.practice
        if target.kind == "question" and get_question(unit.track, target.ref_id) is None:
            report.errors.append(f"{where}: practice question {target.ref_id!r} doesn't exist")
        if target.kind == "problem" and target.ref_id not in seed_slugs:
            report.errors.append(f"{where}: practice problem {target.ref_id!r} doesn't exist")
    report.counts["lessons"] = len(UNIT_INDEX)


def _scenarios(report: Report) -> None:
    for scenario in SCENARIO_INDEX.values():
        try:
            validate(scenario)
        except ScenarioError as exc:
            report.errors.append(f"scenario {scenario.id}: {exc}")
        if scenario.track not in CATALOG:
            report.errors.append(f"scenario {scenario.id}: unknown career {scenario.track!r}")
    report.counts["scenarios"] = len(SCENARIO_INDEX)


def _problems(report: Report) -> dict[str, dict]:
    seeds: dict[str, dict] = {}
    for path in sorted(PROBLEMS_DIR.glob("*.json")):
        where = f"problem file {path.name}"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            report.errors.append(f"{where}: invalid JSON ({exc})")
            continue
        missing = [
            k
            for k in (
                "slug",
                "title",
                "difficulty",
                "statement",
                "signature",
                "starter_code",
                "tests",
                "examples",
            )
            if not data.get(k)
        ]
        if missing:
            report.errors.append(f"{where}: missing {missing}")
            continue
        slug = data["slug"]
        if slug in seeds:
            report.errors.append(f"{where}: duplicate slug {slug!r}")
        seeds[slug] = {**data, "_path": path}
        if data["difficulty"] not in ("easy", "medium", "hard"):
            report.errors.append(f"problem {slug}: unknown difficulty {data['difficulty']!r}")
        sig = data["signature"]
        if (
            not isinstance(sig, dict)
            or not sig.get("method")
            or "params" not in sig
            or not sig.get("returns")
        ):
            report.errors.append(f"problem {slug}: signature needs method, params and returns")
        visibilities = {t.get("visibility") for t in data["tests"]}
        if not {"public", "hidden"} <= visibilities:
            report.errors.append(f"problem {slug}: needs at least one public and one hidden test")
        if any("input" not in t or "expected_output" not in t for t in data["tests"]):
            report.errors.append(f"problem {slug}: a test is missing its input or expected output")
        if not (REFERENCE_DIR / f"{slug}.java").exists():
            report.errors.append(f"problem {slug}: no reference solution")
    report.counts["problems"] = len(seeds)
    return seeds


_LAB_TEXT = ("intended_behavior", "follow_up", "review_status")
_DEFECT_TEXT = ("summary", "explanation", "why_missed")


def _debugging(report: Report, problems: dict[str, dict]) -> dict[str, dict]:
    """Debugging exercises (app/seed/debugging): a problem file plus "kind": "debug" and a "lab"
    block. Running the starter and the repairs is the reference check's job (run_reference)."""
    seeds: dict[str, dict] = {}
    for path in sorted(DEBUGGING_DIR.glob("*.json")):
        where = f"debugging file {path.name}"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            report.errors.append(f"{where}: invalid JSON ({exc})")
            continue
        slug = str(data.get("slug", ""))
        if not slug.startswith("debug-"):
            report.errors.append(f"{where}: a debugging exercise's slug starts with 'debug-'")
            continue
        if slug in problems or slug in seeds:
            report.errors.append(f"{where}: duplicate slug {slug!r}")
            continue
        if data.get("kind") != "debug":
            report.errors.append(f"debugging {slug}: kind must be 'debug'")
        tests = data.get("tests") or []
        if not {"public", "hidden"} <= {t.get("visibility") for t in tests}:
            report.errors.append(f"debugging {slug}: needs at least one public and one hidden test")
        if len(data.get("hints") or []) < 2:
            report.errors.append(f"debugging {slug}: needs at least two staged hints")
        lab = data.get("lab") or {}
        if not isinstance(lab.get("version"), int) or lab["version"] < 1:
            report.errors.append(f"debugging {slug}: lab.version must be a positive whole number")
        missing = [k for k in _LAB_TEXT if not str(lab.get(k, "")).strip()]
        missing += [
            f"defect.{k}" for k in _DEFECT_TEXT if not str((lab.get("defect") or {}).get(k, "")).strip()
        ]
        if missing:
            report.errors.append(f"debugging {slug}: lab is missing {missing}")
        repro = lab.get("reproduction") or []
        public = {i for i, t in enumerate(tests) if t.get("visibility") == "public"}
        if not repro or not set(repro) <= public:
            report.errors.append(f"debugging {slug}: lab.reproduction must list public test positions")
        if not (REFERENCE_DIR / f"{slug}.java").exists():
            report.errors.append(f"debugging {slug}: no reference repair")
        seeds[slug] = {**data, "_path": path}
    report.counts["debugging exercises"] = len(seeds)
    return seeds


def _load_reference_checker():
    spec = importlib.util.spec_from_file_location(
        "verify_reference", BACKEND_DIR / "scripts" / "verify_reference_solutions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check_problem, module.check_debug_exercise


def run(db: Session | None, *, run_reference: bool = False, record: bool = False) -> Report:
    report = Report()
    _questions(report)
    seeds = _problems(report)
    seeds |= _debugging(report, seeds)
    retired: set[tuple[str, str]] = set()
    if db is not None:
        _db_content(db, report, set(seeds))
        retired = {(s.content_type, s.content_id) for s in db.scalars(select(ContentStatus))}
        for slug in db.scalars(select(Problem.slug)):
            if slug not in seeds:
                report.warnings.append(f"problem {slug}: in the database but not in the seed files")
    _learn(report, retired, set(seeds))
    _scenarios(report)

    if run_reference:
        if shutil.which("javac") is None or shutil.which("java") is None:
            report.warnings.append("reference solutions not run: no local JDK (javac/java) found")
        else:
            check, check_debug = _load_reference_checker()
            for slug in seeds:
                failures = (check_debug if seeds[slug].get("kind") == "debug" else check)(
                    seeds[slug]["_path"]
                )
                report.checks.append((slug, not failures, "\n".join(failures)[:2000]))
                if failures:
                    report.errors.append(f"problem {slug}: reference solution failed ({len(failures)} tests)")
            if record and db is not None:
                _record(db, report, seeds)
    return report


def _record(db: Session, report: Report, seeds: dict[str, dict]) -> None:
    now = datetime.now(UTC)
    for slug, passed, detail in report.checks:
        version = max((int(t.get("version", 1)) for t in seeds[slug]["tests"]), default=1)
        row = db.scalar(
            select(ContentCheck).where(
                ContentCheck.content_type == "problem",
                ContentCheck.content_id == slug,
                ContentCheck.check == "reference_solution",
            )
        )
        if row is None:
            row = ContentCheck(content_type="problem", content_id=slug, check="reference_solution")
            db.add(row)
        row.content_version, row.passed, row.detail, row.checked_at = version, passed, detail or None, now
    db.commit()

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
import re
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
REVIEWS_DIR = BACKEND_DIR / "app" / "seed" / "reviews"
TEST_DESIGN_DIR = BACKEND_DIR / "app" / "seed" / "testdesign"


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


_REVIEW_TEXT = ("title", "context", "code", "debrief", "review_status")
_FINDING_TEXT = ("id", "title", "explanation", "consequence", "repair")


def _span(value: object, n: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, int) for v in value)
        and 1 <= value[0] <= value[1] <= n
    )


def _reviews(report: Report, problems: dict[str, dict]) -> dict[str, dict]:
    """Code-review exercises (app/seed/reviews; docs/CODE_REVIEW_PRACTICE.md). Running the code
    and the repairs against the problem's tests is the reference check's job."""
    seeds: dict[str, dict] = {}
    for path in sorted(REVIEWS_DIR.glob("*.json")):
        where = f"review file {path.name}"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            report.errors.append(f"{where}: invalid JSON ({exc})")
            continue
        slug = str(data.get("slug", ""))
        if not slug.startswith("review-"):
            report.errors.append(f"{where}: a review exercise's slug starts with 'review-'")
            continue
        if slug in seeds:
            report.errors.append(f"{where}: duplicate slug {slug!r}")
            continue
        here = f"review {slug}"
        if not isinstance(data.get("version"), int) or data["version"] < 1:
            report.errors.append(f"{here}: version must be a positive whole number")
        missing = [k for k in _REVIEW_TEXT if not str(data.get(k) or "").strip()]
        if missing:
            report.errors.append(f"{here}: missing {missing}")
        problem = problems.get(str(data.get("problem")))
        if problem is None:
            report.errors.append(f"{here}: no coding problem {data.get('problem')!r}")
            continue
        public = [t for t in problem.get("tests", []) if t.get("visibility") == "public"]
        n = len(str(data.get("code") or "").splitlines())
        findings = data.get("findings") or []
        if not findings:
            report.errors.append(f"{here}: needs at least one authored finding")
        ids: set[str] = set()
        for f in findings:
            fid = str(f.get("id", "?"))
            at = f"{here} finding {fid}"
            if fid in ids:
                report.errors.append(f"{at}: duplicate id")
            ids.add(fid)
            gaps = [k for k in _FINDING_TEXT if not str(f.get(k) or "").strip()]
            if gaps:
                report.errors.append(f"{at}: missing {gaps}")
            if f.get("kind") not in ("defect", "observation"):
                report.errors.append(f"{at}: kind must be 'defect' or 'observation'")
            spans = [f.get("lines")] + list(f.get("related_lines") or [])
            if not all(_span(s, n) for s in spans):
                report.errors.append(f"{at}: lines must be [first, last] within the code's {n} lines")
            evidence = f.get("evidence") or []
            if f.get("kind") == "defect":
                if not evidence:
                    report.errors.append(f"{at}: a defect needs evidence from a public test")
                for e in evidence:
                    pos = e.get("public_test")
                    if not isinstance(pos, int) or not 1 <= pos <= len(public) or "actual" not in e:
                        report.errors.append(
                            f"{at}: evidence must name a public test (1 to {len(public)}) and the actual result"
                        )
            elif f.get("kind") == "observation":
                if evidence:
                    report.errors.append(
                        f"{at}: an observation has no failing test; label it a defect or drop the evidence"
                    )
                if not str(f.get("why_preference") or "").strip():
                    report.errors.append(f"{at}: an observation says why it's a preference, not a defect")
        defects = [f for f in findings if f.get("kind") == "defect"]
        if defects and not str(data.get("repaired_code") or "").strip():
            report.errors.append(f"{here}: an exercise with a defect needs repaired_code")
        seeds[slug] = {**data, "_path": path, "_defects": len(defects)}
    if seeds and all(s["_defects"] for s in seeds.values()):
        report.errors.append(
            "reviews: at least one exercise must have no defect (a correct implementation to review)"
        )
    report.counts["review exercises"] = len(seeds)
    return seeds


_TD_TEXT = ("title", "summary", "spec", "review_status")
_VARIANT_TEXT = ("id", "title", "defect", "gap")


def _code_shape(code: object) -> str | None:
    """The reference and each faulty version become one class each in a shared file."""
    text = str(code or "")
    if len(re.findall(r"\bclass\s+Solution\b", text)) != 1:
        return "needs exactly one `class Solution`"
    if re.search(r"^\s*(import|package)\b|\bpublic\s+class\b", text, re.M):
        return "can't use import, package or a public class (it shares a file with the others)"
    return None


def _test_design(report: Report) -> None:
    """Test-design exercises (app/seed/testdesign; docs/TEST_DESIGN.md). Running them is the
    reference check's job; this checks the shape, so a broken fixture is refused before a learner
    sees it."""
    from app.testdesign import case_errors, parse, supported_signature

    seen: set[str] = set()
    for path in sorted(TEST_DESIGN_DIR.glob("*.json")):
        where = f"test design file {path.name}"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            report.errors.append(f"{where}: invalid JSON ({exc})")
            continue
        slug = str(data.get("slug", ""))
        if not slug.startswith("tests-"):
            report.errors.append(f"{where}: a test design exercise's slug starts with 'tests-'")
            continue
        if slug in seen:
            report.errors.append(f"{where}: duplicate slug {slug!r}")
            continue
        seen.add(slug)
        here = f"test design {slug}"
        if not isinstance(data.get("version"), int) or data["version"] < 1:
            report.errors.append(f"{here}: version must be a positive whole number")
        missing = [k for k in _TD_TEXT if not str(data.get(k) or "").strip()]
        if missing:
            report.errors.append(f"{here}: missing {missing}")
        if not supported_signature(data.get("signature") or {}):
            report.errors.append(
                f"{here}: the one supported shape is int[] then up to two int, returning int or boolean"
            )
            continue
        lim = data.get("limits") or {}
        if not all(
            isinstance(lim.get(k), int) for k in ("max_cases", "max_length", "min_value", "max_value")
        ) or not (
            1 <= lim["max_cases"] <= 20
            and 1 <= lim["max_length"] <= 50
            and lim["min_value"] < lim["max_value"]
        ):
            report.errors.append(
                f"{here}: limits must be whole numbers: max_cases 1-20, max_length 1-50, min_value < max_value"
            )
            continue
        if problem := _code_shape(data.get("reference")):
            report.errors.append(f"{here}: the reference {problem}")
        variants = data.get("variants") or []
        if len(variants) < 2:
            report.errors.append(f"{here}: needs at least two faulty versions")
        ids = [str(v.get("id")) for v in variants]
        if len(set(ids)) != len(ids):
            report.errors.append(f"{here}: faulty version ids must be unique")
        try:
            ex = parse(data)
        except (KeyError, TypeError, ValueError) as exc:
            report.errors.append(f"{here}: malformed ({exc.__class__.__name__}: {exc})")
            continue
        dummy = True if ex.returns == "boolean" else 0
        for i, e in enumerate(ex.examples, 1):
            if errs := case_errors(ex, e.get("input"), e.get("expected")):
                report.errors.append(f"{here}: example {i}: {errs[0]}")
        if not ex.examples:
            report.errors.append(f"{here}: needs at least one example")
        for v in variants:
            at = f"{here} faulty version {v.get('id', '?')}"
            gaps = [k for k in _VARIANT_TEXT if not str(v.get(k) or "").strip()]
            if gaps:
                report.errors.append(f"{at}: missing {gaps}")
            if problem := _code_shape(v.get("code")):
                report.errors.append(f"{at}: {problem}")
            if errs := case_errors(ex, v.get("witness"), dummy):
                report.errors.append(f"{at}: witness: {errs[0]}")
    report.counts["test design exercises"] = len(seen)


def _load_reference_checker():
    spec = importlib.util.spec_from_file_location(
        "verify_reference", BACKEND_DIR / "scripts" / "verify_reference_solutions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        module.check_problem,
        module.check_debug_exercise,
        module.check_review_exercise,
        module.check_test_design_exercise,
    )


def run(db: Session | None, *, run_reference: bool = False, record: bool = False) -> Report:
    report = Report()
    _questions(report)
    seeds = _problems(report)
    seeds |= _debugging(report, seeds)
    reviews = _reviews(report, seeds)
    _test_design(report)
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
            check, check_debug, check_review, check_design = _load_reference_checker()
            for slug, review in reviews.items():
                if failures := check_review(review["_path"]):
                    report.errors.append(f"review {slug}: " + "; ".join(failures)[:2000])
            for path in sorted(TEST_DESIGN_DIR.glob("*.json")):
                if failures := check_design(path):
                    report.errors.append(f"test design {path.stem}: " + "; ".join(failures)[:2000])
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

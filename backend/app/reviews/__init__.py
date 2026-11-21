"""Code-review practice (Volume 10, prompt 3; docs/CODE_REVIEW_PRACTICE.md).

The learner reviews someone else's code: a short, synthetic snippet written for an existing coding
problem. Each exercise (app/seed/reviews/*.json) carries an authored review: defects, each shown by
a public test of that problem (the evidence names the test and what the code returns for it), and
observations, labelled as preferences with the reason they aren't defects. At least one exercise
has no defect at all. scripts/verify_reference_solutions.py runs every snippet and repair against
the problem's tests with a real JDK, so the evidence can't drift from the code.

An exercise is versioned; an attempt keeps a snapshot of the code and the authored review it was
compared with (`Exercise.snapshot`), so a later correction never rewrites an old attempt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"
REVIEWS_DIR = SEED_DIR / "reviews"
PROBLEMS_DIR = SEED_DIR / "problems"
KINDS = ("defect", "observation")


def problem_seed(slug: str, directory: Path = PROBLEMS_DIR) -> dict[str, Any] | None:
    """The coding problem's seed file (`NNN-<slug>.json`), or None."""
    for path in directory.glob(f"*-{slug}.json"):
        data = json.loads(path.read_text())
        if data.get("slug") == slug:
            return data
    return None


def public_tests(problem: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in problem.get("tests", []) if t.get("visibility") == "public"]


@dataclass(frozen=True)
class Evidence:
    public_test: int  # 1-based position among the problem's public tests
    input: dict[str, Any]
    expected: Any
    actual: Any  # what the reviewed code returns for it (checked with a real JDK)


@dataclass(frozen=True)
class Reference:
    id: str
    kind: str  # defect | observation
    lines: tuple[int, int]
    related_lines: tuple[tuple[int, int], ...]
    title: str
    explanation: str
    consequence: str
    repair: str
    why_preference: str | None
    evidence: tuple[Evidence, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "lines": list(self.lines),
            "related_lines": [list(s) for s in self.related_lines],
            "title": self.title,
            "explanation": self.explanation,
            "consequence": self.consequence,
            "repair": self.repair,
            "why_preference": self.why_preference,
            "evidence": [
                {"public_test": e.public_test, "input": e.input, "expected": e.expected, "actual": e.actual}
                for e in self.evidence
            ],
        }


@dataclass(frozen=True)
class Exercise:
    slug: str
    version: int
    title: str
    problem: str
    context: str
    code: str
    findings: tuple[Reference, ...]
    repaired_code: str | None
    debrief: str
    review_status: str

    @property
    def lines(self) -> list[str]:
        return self.code.splitlines()

    def snapshot(self, problem_title: str, statement: str) -> dict[str, Any]:
        """Everything an attempt is compared with, frozen with it."""
        return {
            "version": self.version,
            "title": self.title,
            "problem": self.problem,
            "problem_title": problem_title,
            "statement": statement,
            "context": self.context,
            "code": self.code,
            "reference": [f.as_dict() for f in self.findings],
            "repaired_code": self.repaired_code,
            "debrief": self.debrief,
        }


def _pair(value: list[int]) -> tuple[int, int]:
    return int(value[0]), int(value[1])


def parse(data: dict[str, Any], problems_dir: Path = PROBLEMS_DIR) -> Exercise:
    """Build an exercise from its seed file. Raises on malformed content; app/content/validate.py
    reports the same problems one by one."""
    problem = problem_seed(data["problem"], problems_dir)
    if problem is None:
        raise ValueError(f"review {data.get('slug')}: no coding problem {data['problem']!r}")
    public = public_tests(problem)
    findings = []
    for f in data["findings"]:
        evidence = []
        for e in f.get("evidence", []):
            test = public[int(e["public_test"]) - 1]
            evidence.append(
                Evidence(int(e["public_test"]), test["input"], test["expected_output"], e["actual"])
            )
        findings.append(
            Reference(
                id=f["id"],
                kind=f["kind"],
                lines=_pair(f["lines"]),
                related_lines=tuple(_pair(s) for s in f.get("related_lines", [])),
                title=f["title"],
                explanation=f["explanation"],
                consequence=f["consequence"],
                repair=f["repair"],
                why_preference=f.get("why_preference"),
                evidence=tuple(evidence),
            )
        )
    return Exercise(
        slug=data["slug"],
        version=int(data["version"]),
        title=data["title"],
        problem=data["problem"],
        context=data["context"],
        code=data["code"],
        findings=tuple(findings),
        repaired_code=data.get("repaired_code"),
        debrief=data["debrief"],
        review_status=data["review_status"],
    )


def load(directory: Path = REVIEWS_DIR) -> tuple[Exercise, ...]:
    return tuple(parse(json.loads(p.read_text())) for p in sorted(directory.glob("*.json")))


EXERCISES = load()
BY_SLUG = {e.slug: e for e in EXERCISES}

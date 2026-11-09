"""Load the curated problem library from app/seed/problems/*.json into the database.

Idempotent: problems are upserted by slug. When a problem's test cases change, they are
replaced and their version number is bumped, so stored results can be traced to the test
set they were judged against.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Difficulty, Problem, TestCase, TestVisibility

logger = logging.getLogger("codecoach.seed")
SEED_DIR = Path(__file__).resolve().parents[1] / "seed" / "problems"
# Debugging exercises (Volume 10, prompt 2): the same format with "kind": "debug" and a "lab" block;
# the faulty code is the starter, the repair is reference/<slug>.java (docs/DEBUGGING_LAB.md).
DEBUGGING_DIR = Path(__file__).resolve().parents[1] / "seed" / "debugging"
REFERENCE_DIR = Path(__file__).resolve().parents[1] / "seed" / "reference"

_PROBLEM_FIELDS = (
    "title",
    "summary",
    "statement",
    "constraints",
    "examples",
    "starter_code",
    "signature",
    "hints",
    "expected_complexity",
    "topics",
)


def load_seed_files(seed_dir: Path = SEED_DIR) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(seed_dir.glob("*.json"))]


def _tests_signature(tests: list) -> list:
    return [(t["input"], t["expected_output"], str(t["visibility"])) for t in tests]


def seed_problems(session: Session, seed_dir: Path = SEED_DIR, debugging_dir: Path | None = None) -> int:
    count = 0
    if debugging_dir is None and seed_dir == SEED_DIR:
        debugging_dir = DEBUGGING_DIR
    files = load_seed_files(seed_dir) + (load_seed_files(debugging_dir) if debugging_dir else [])
    for data in files:
        problem = session.scalar(select(Problem).where(Problem.slug == data["slug"]))
        if problem is None:
            problem = Problem(slug=data["slug"])
            session.add(problem)
        for field in _PROBLEM_FIELDS:
            setattr(problem, field, data[field])
        problem.difficulty = Difficulty(data["difficulty"])
        problem.order_index = data["order"]
        problem.kind = data.get("kind", "problem")
        problem.lab = (
            {
                **data["lab"],
                "reference_repair": (REFERENCE_DIR / f"{data['slug']}.java").read_text(encoding="utf-8"),
            }
            if problem.kind == "debug"
            else None
        )

        existing = [
            {"input": t.input, "expected_output": t.expected_output, "visibility": t.visibility.value}
            for t in problem.test_cases
        ]
        if _tests_signature(existing) != _tests_signature(data["tests"]):
            version = (max((t.version for t in problem.test_cases), default=0)) + 1
            problem.test_cases.clear()
            for position, t in enumerate(data["tests"]):
                problem.test_cases.append(
                    TestCase(
                        position=position,
                        input=t["input"],
                        expected_output=t["expected_output"],
                        visibility=TestVisibility(t["visibility"]),
                        version=version,
                    )
                )
        count += 1
    session.commit()
    logger.info("seeded problems", extra={"count": count})
    return count

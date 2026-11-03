"""Career-answer evaluation: the written-answer coach against hand-labelled answers.

Each case is one synthetic answer to one question at a pinned version, with a human label for
every rubric point (evals/career_*.json). The grader under test is any function with the
signature of `app.careers.grading.grade`; by default the real one.

Every case produces named checks, so a failure says what went wrong on which answer:

  schema               the feedback has the stored shape (score 0-100, a known rating that matches
                       the score, one result per rubric point, a known evidence level)
  points               the grader's covered/not covered agrees with the label, per point (points
                       the labeller marked uncertain are reported but not counted)
  evidence             every quote shown as evidence is the learner's own words, shows the point it
                       is quoted for, and is never text the case forbids (an instruction to the grader)
  insufficient         an answer too short to judge gets no score shown and no praise
  actionable           every point the grader says is missing comes with advice, and the summary
                       names one to start with
  rating               the rating is within the bounds the labeller set (when set)
  notes                the structure notes the labeller expected are there (the "we"/"I" and
                       numbers notes)
  injection            text addressed to the grader neither adds a covered point nor raises the
                       rating, compared with the same answer without it
  stable               the same answer graded twice, or with different spacing, gets the same result
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.careers.grading import Feedback
from app.careers.questions import Question, get_question

EVAL_DIR = Path(__file__).resolve().parent
RATINGS = ["Needs work", "Developing", "Good", "Strong"]
PRAISE = ("You covered everything", "Solid.")
NOTE_KEYS = {"we": "“we”", "numbers": "No numbers", "length": "words:"}

Grader = Callable[[Question, str], Feedback]


def load(name: str) -> dict:
    return json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))


def _rating_for(score: int) -> str:
    return (
        "Strong" if score >= 85 else "Good" if score >= 65 else "Developing" if score >= 40 else "Needs work"
    )


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _evidence_problems(fb: Feedback, q: Question, answer: str, forbidden: list[str]) -> list[str]:
    problems = []
    flat = _norm(answer)
    patterns = {r.label: r.patterns for r in q.rubric}
    for p in fb.points:
        if not p.covered:
            if p.evidence:
                problems.append(f"{p.label}: evidence quoted for a point marked missing")
            continue
        if not p.evidence:
            problems.append(f"{p.label}: marked covered with no quote")
            continue
        quote = _norm(p.evidence)
        truncated = quote.endswith("…")
        body = quote[:-1].rstrip() if truncated else quote
        if body not in flat:
            problems.append(f"{p.label}: quote is not the learner's words: {p.evidence[:60]!r}")
            continue
        padded = " " + body + " "
        if not any(re.search(pat, padded, flags=re.IGNORECASE) for pat in patterns[p.label]):
            problems.append(
                f"{p.label}: the quote doesn't show the point"
                + (" (cut before the part that does)" if truncated else "")
                + f": {p.evidence[:60]!r}"
            )
        for bad in forbidden:
            if bad.lower() in quote.lower():
                problems.append(f"{p.label}: quotes forbidden text {bad!r}")
    return problems


def evaluate_case(case: dict, track: str, grader: Grader) -> dict:
    """All checks for one case. Never raises: a grader crash is a failed case, not a lost run."""
    out: dict = {"id": case["id"], "question_id": case["question_id"], "tags": case["tags"], "checks": {}}
    q = get_question(track, case["question_id"], case["question_version"])
    if q is None or q.version != case["question_version"]:
        out["error"] = f"question {case['question_id']} v{case['question_version']} not found"
        return out
    labels: dict[str, bool] = case["labels"]["points"]
    if sorted(r.label for r in q.rubric) != sorted(labels):
        # The rubric changed under the labels: the case must be relabelled, not scored.
        out["error"] = "the question's rubric points no longer match the labelled points; relabel this case"
        return out
    try:
        fb = grader(q, case["answer"])
    except Exception as exc:  # noqa: BLE001 - recorded per case
        out["error"] = f"grader raised {type(exc).__name__}: {exc}"
        return out
    checks = out["checks"]
    out["observed"] = {
        "score": fb.score,
        "rating": fb.rating,
        "evidence_level": fb.evidence_level,
        "covered": sorted(p.label for p in fb.points if p.covered),
    }

    # schema
    problems = []
    if not (isinstance(fb.score, int) and 0 <= fb.score <= 100):
        problems.append(f"score {fb.score!r} out of range")
    if fb.rating not in RATINGS or (isinstance(fb.score, int) and fb.rating != _rating_for(fb.score)):
        problems.append(f"rating {fb.rating!r} doesn't match score {fb.score!r}")
    if [p.label for p in fb.points] != [r.label for r in q.rubric]:
        problems.append("points don't match the rubric")
    if fb.evidence_level not in ("sufficient", "insufficient"):
        problems.append(f"unknown evidence level {fb.evidence_level!r}")
    checks["schema"] = _check(problems)

    # points
    uncertain = set(case["labels"]["uncertain"])
    predicted = {p.label: p.covered for p in fb.points}
    point_rows = []
    for label, expected in labels.items():
        point_rows.append(
            {
                "label": label,
                "expected": expected,
                "predicted": predicted.get(label),
                "uncertain": label in uncertain,
            }
        )
    out["points"] = point_rows
    wrong = [
        f"{r['label']}: labelled {'covered' if r['expected'] else 'missing'}, grader said "
        f"{'covered' if r['predicted'] else 'missing'}"
        for r in point_rows
        if not r["uncertain"] and r["predicted"] != r["expected"]
    ]
    checks["points"] = _check(wrong)

    # evidence
    checks["evidence"] = _check(_evidence_problems(fb, q, case["answer"], case.get("forbidden_evidence", [])))

    # insufficient evidence
    exp_level = case["expected"]["evidence_level"]
    problems = []
    if fb.evidence_level != exp_level:
        problems.append(f"evidence level {fb.evidence_level}, expected {exp_level}")
    if exp_level == "insufficient":
        if fb.score > 35:
            problems.append(f"score {fb.score} shown for an answer too short to judge (cap is 35)")
        if fb.rating in ("Good", "Strong"):
            problems.append(f"rated {fb.rating} although too short to judge")
        if fb.summary.startswith(PRAISE):
            problems.append(f"praises a too-short answer: {fb.summary!r}")
    checks["insufficient"] = _check(problems)

    # actionable
    missed = [p for p in fb.points if not p.covered]
    problems = [f"{p.label}: missing with no advice" for p in missed if not p.advice.strip()]
    if missed and fb.evidence_level == "sufficient" and missed[0].label.lower() not in fb.summary.lower():
        problems.append("the summary doesn't say which missing point to start with")
    checks["actionable"] = _check(problems)

    # rating bounds
    exp = case["expected"]
    if "rating_at_least" in exp or "rating_at_most" in exp:
        r = RATINGS.index(fb.rating) if fb.rating in RATINGS else -1
        problems = []
        if "rating_at_least" in exp and r < RATINGS.index(exp["rating_at_least"]):
            problems.append(f"rated {fb.rating}, expected at least {exp['rating_at_least']}")
        if "rating_at_most" in exp and r > RATINGS.index(exp["rating_at_most"]):
            problems.append(f"rated {fb.rating}, expected at most {exp['rating_at_most']}")
        checks["rating"] = _check(problems)

    # notes
    if exp.get("notes"):
        notes = " ".join(fb.notes)
        checks["notes"] = _check([f"no {k!r} note" for k in exp["notes"] if NOTE_KEYS[k] not in notes])

    # injection
    if case.get("injection"):
        without = case["answer"].replace(case["injection"], "")
        base = grader(q, without)
        problems = []
        gained = sorted(
            {p.label for p in fb.points if p.covered} - {p.label for p in base.points if p.covered}
        )
        if gained:
            problems.append(f"the injected text added covered points: {gained}")
        if RATINGS.index(fb.rating) > RATINGS.index(base.rating):
            problems.append(f"the injected text raised the rating from {base.rating} to {fb.rating}")
        if base.evidence_level == "insufficient" and fb.evidence_level == "sufficient":
            problems.append("the injected text turned a too-short answer into a scored one")
        checks["injection"] = _check(problems)

    # stability
    again = grader(q, case["answer"])
    respaced = grader(q, "  " + case["answer"].replace(". ", ".\n\n").replace(", ", ",  ") + "\n")
    problems = []
    if again != fb:
        problems.append("a second grading of the same answer differs")
    if (respaced.score, [p.covered for p in respaced.points]) != (fb.score, [p.covered for p in fb.points]):
        problems.append(f"different spacing changes the result ({fb.score} vs {respaced.score})")
    checks["stable"] = _check(problems)
    return out


def _check(problems: list[str]) -> dict:
    return {"passed": not problems, "problems": problems}


def evaluate_set(dataset: dict, grader: Grader) -> dict:
    cases = [evaluate_case(c, dataset["track"], grader) for c in dataset["cases"]]
    errors = [c for c in cases if "error" in c]
    scored = [c for c in cases if "error" not in c]
    tp = fp = fn = tn = 0
    uncertain_rows = []
    for c in scored:
        for r in c["points"]:
            if r["uncertain"]:
                uncertain_rows.append({"case": c["id"], **r})
                continue
            tp += r["expected"] and r["predicted"]
            fp += (not r["expected"]) and r["predicted"]
            fn += r["expected"] and not r["predicted"]
            tn += (not r["expected"]) and not r["predicted"]
    names = [
        "schema",
        "points",
        "evidence",
        "insufficient",
        "actionable",
        "rating",
        "notes",
        "injection",
        "stable",
    ]
    dims = {}
    for name in names:
        applicable = [c for c in scored if name in c["checks"]]
        failed = [c["id"] for c in applicable if not c["checks"][name]["passed"]]
        dims[name] = {"cases": len(applicable), "passed": len(applicable) - len(failed), "failed": failed}
    by_tag: dict[str, Counter] = {}
    for c in scored:
        for t in c["tags"]:
            by_tag.setdefault(t, Counter())
            by_tag[t]["cases"] += 1
            by_tag[t]["all_checks_passed"] += all(ch["passed"] for ch in c["checks"].values())
    return {
        "dataset": dataset["id"],
        "dataset_version": dataset["version"],
        "split": dataset["split"],
        "track": dataset["track"],
        "cases_planned": len(dataset["cases"]),
        "cases_scored": len(scored),
        "case_errors": [{"id": c["id"], "error": c["error"]} for c in errors],
        "point_agreement": {
            "points": tp + fp + fn + tn,
            "precision": _r(tp / (tp + fp)) if tp + fp else None,
            "recall": _r(tp / (tp + fn)) if tp + fn else None,
            "accuracy": _r((tp + tn) / (tp + fp + fn + tn)) if tp + fp + fn + tn else None,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "uncertain_points_not_counted": len(uncertain_rows),
            "uncertain_agreement": sum(r["expected"] == r["predicted"] for r in uncertain_rows),
        },
        "dimensions": dims,
        "by_tag": {t: dict(v) for t, v in sorted(by_tag.items())},
        "cases": cases,
    }


def _r(x: float) -> float:
    return round(x, 3)

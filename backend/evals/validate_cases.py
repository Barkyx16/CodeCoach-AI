"""Check a career-answer case file against the evaluation protocol (evals/protocol.json).

    python -m evals.validate_cases evals/career_families_dev.json

Prints counts and the ids of cases that break a rule, never answer text, so it can be run on a
sealed set. Exit status 1 when anything is wrong.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.careers.questions import get_question, questions_for

EVAL_DIR = Path(__file__).resolve().parent
RATINGS = ["Needs work", "Developing", "Good", "Strong"]
REVIEW_STATES = {"unreviewed", "reviewed", "partly reviewed"}
PAIRED = {"dictated", "paraphrase", "meaning_changed"}
NEEDS_BOUNDS = {"keyword_list", "contradiction", "meaning_changed", "grader_directed"}
DATASET_FIELDS = (
    "id",
    "version",
    "split",
    "track",
    "domain",
    "provenance",
    "labeling",
    "labeler",
    "review_status",
    "cases",
)


def protocol() -> dict:
    return json.loads((EVAL_DIR / "protocol.json").read_text(encoding="utf-8"))


def rule_questions(track: str, index: int) -> set[str]:
    by_cell: dict[tuple[str, str], list[str]] = defaultdict(list)
    for q in questions_for(track):
        by_cell[(q.difficulty, q.kind)].append(q.id)
    return {sorted(ids)[index] for ids in by_cell.values() if len(ids) > index}


RULE_INDEX = {
    "career-rn-dev": 0,
    "career-rn-holdout": 1,
    "career-rn-families-dev": 2,
    "career-rn-sealed": 3,
    "career-rn-contradiction-pairs": 0,
}


def edits(a: str, b: str) -> int:
    """How many separate places two answers differ in, word by word (a minimal pair has one)."""
    ops = difflib.SequenceMatcher(a=a.split(), b=b.split(), autojunk=False).get_opcodes()
    return sum(tag != "equal" for tag, *_ in ops)


def _pair_problems(c: dict, by_id: dict, plan: dict) -> list[str]:
    """protocol.json minimal_pairs: one edit from its pair, and contradiction labels that say which
    two statements disagree and which points they undermine."""
    cid, v = c.get("id", "?"), c.get("variant")
    errors = []
    if v != "typed":
        pair = by_id.get(c.get("pair_of"))
        if pair is None or pair.get("family") != c.get("family"):
            errors.append(f"{cid}: pair_of must name a case of the same family")
        elif not c.get("change") or edits(pair.get("answer", ""), c.get("answer", "")) != 1:
            errors.append(f"{cid}: must differ from {pair['id']} by exactly one edit, described in `change`")
        elif v == "grader_directed" and pair.get("variant") != "contradiction":
            errors.append(f"{cid}: grader_directed is paired with a contradiction variant")
    if not isinstance(c.get("contradiction"), bool):
        errors.append(f"{cid}: needs `contradiction` (true or false)")
        return errors
    should = {"contradiction": True, "self_correction": False, "contradiction_control": False, "typed": False}
    if v in should and c["contradiction"] != should[v]:
        errors.append(f"{cid}: a {v} case is labelled contradiction={should[v]}")
    points = c.get("labels", {}).get("points", {})
    if c["contradiction"]:
        cp = c.get("contradicted_points") or []
        if not cp or not set(cp) <= set(points) or any(points.get(x) for x in cp):
            errors.append(f"{cid}: a contradiction needs contradicted_points, each labelled not covered")
        quotes = c.get("conflict") or []
        if len(quotes) != 2 or any(not q or q not in c.get("answer", "") for q in quotes):
            errors.append(f"{cid}: `conflict` must quote the two statements, exactly as in the answer")
        if not ({"rating_at_least", "rating_at_most"} & set(c.get("expected", {}))):
            errors.append(f"{cid}: a contradiction needs a rating bound")
    elif c.get("contradicted_points") or c.get("conflict"):
        errors.append(f"{cid}: contradicted_points / conflict on an answer labelled not contradictory")
    return errors


def validate(data: dict) -> tuple[list[str], dict]:
    p = protocol()
    pairs = data.get("design") == "minimal_pairs"
    plan_spec = p["minimal_pairs"] if pairs else None
    variant_names = plan_spec["variants"] if plan_spec else p["variants"]
    kinds_of = {**p["kinds"], **plan_spec["kinds"]} if plan_spec else p["kinds"]
    errors: list[str] = []
    for f in DATASET_FIELDS:
        if f not in data:
            errors.append(f"dataset: missing field {f!r}")
    status = str(data.get("review_status", ""))
    if status.split(":")[0].strip() not in REVIEW_STATES:
        errors.append(f"dataset: review_status must start with one of {sorted(REVIEW_STATES)}")
    if any(w in status.lower() for w in ("validated", "expert", "clinician")) and not data.get("reviews"):
        errors.append("dataset: claims validation or expert review without review records")
    cases = data.get("cases", [])
    track = data.get("track", "registered-nurse")
    allowed_q = rule_questions(track, RULE_INDEX[data["id"]]) if data.get("id") in RULE_INDEX else None
    ids = Counter(c.get("id") for c in cases)
    errors += [f"{i}: duplicate id" for i, n in ids.items() if n > 1]
    by_id = {c.get("id"): c for c in cases}
    variants = Counter()
    families: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        cid = c.get("id", "?")
        v = c.get("variant")
        variants[v] += 1
        families[c.get("family", "?")].append(c)
        if v not in variant_names:
            errors.append(f"{cid}: unknown variant {v!r}")
            continue
        if pairs:
            errors += _pair_problems(c, by_id, plan_spec)
        kinds = kinds_of.get(v)
        if kinds and c.get("kind") not in kinds:
            errors.append(f"{cid}: {v} needs a kind from {kinds}")
        if allowed_q is not None and c.get("question_id") not in allowed_q:
            errors.append(
                f"{cid}: question {c.get('question_id')} is not one the selection rule picks for this set"
            )
        q = get_question(track, c.get("question_id", ""), c.get("question_version"))
        if q is None:
            errors.append(f"{cid}: question not found at that version")
            continue
        labels = c.get("labels", {})
        points = labels.get("points", {})
        if sorted(points) != sorted(r.label for r in q.rubric):
            errors.append(f"{cid}: labels must name exactly the question's rubric points")
        if not set(labels.get("uncertain", [])) <= set(points):
            errors.append(f"{cid}: uncertain names a point that isn't labelled")
        answer = c.get("answer", "")
        injection = c.get("injection")
        if v == "grader_directed":
            if not injection or injection not in answer:
                errors.append(f"{cid}: grader_directed needs `injection`, an exact substring of the answer")
            if not c.get("forbidden_evidence"):
                errors.append(f"{cid}: grader_directed needs forbidden_evidence")
        words = len(answer.replace(injection, " ").split()) if injection else len(answer.split())
        expected = c.get("expected", {})
        level = "insufficient" if words < 40 else "sufficient"
        if expected.get("evidence_level") != level:
            errors.append(f"{cid}: evidence_level must be {level!r} ({words} words without injected text)")
        for key in ("rating_at_least", "rating_at_most"):
            if key in expected and expected[key] not in RATINGS:
                errors.append(f"{cid}: {key} must be one of {RATINGS}")
        if v in NEEDS_BOUNDS and not ({"rating_at_least", "rating_at_most"} & set(expected)):
            errors.append(f"{cid}: {v} needs a rating bound")
        if v == "contradiction":
            cp = c.get("contradicted_points") or []
            if not cp or not set(cp) <= set(points) or any(points.get(x) for x in cp):
                errors.append(f"{cid}: contradiction needs contradicted_points, each labelled not covered")
        if v in PAIRED and not pairs:
            pair = by_id.get(c.get("pair_of"))
            if pair is None or pair.get("variant") != "typed" or pair.get("family") != c.get("family"):
                errors.append(f"{cid}: {v} needs pair_of = the typed answer of the same family")
            elif v in ("dictated", "paraphrase") and pair.get("labels", {}).get("points") != points:
                errors.append(f"{cid}: a meaning-preserving {v} must have its typed pair's point labels")
        if v == "keyword_list" and words < 40:
            errors.append(f"{cid}: keyword_list must have at least 40 words")
    # The family plan, per question (a minimal-pairs set has its own design instead).
    plan = p["family_plan_per_question"]
    per_question: dict[str, list[list[str]]] = defaultdict(list)
    for fam in families.values():
        per_question[fam[0].get("question_id", "?")].append(sorted(x.get("variant") for x in fam))
    for qid, fams in per_question.items():
        for name, wanted in plan.items() if not pairs else ():
            if sorted(wanted) not in fams:
                errors.append(f"question {qid}: no family with exactly the variants of plan {name} {wanted}")
        if pairs and not any([x for x in f if x == "typed"] == ["typed"] for f in fams):
            errors.append(f"question {qid}: every family needs exactly one base answer (variant typed)")
    summary = {
        "cases": len(cases),
        "questions": len(per_question),
        "families": len(families),
        "variants": dict(sorted(variants.items(), key=lambda kv: str(kv[0]))),
        "uncertain_points": sum(len(c.get("labels", {}).get("uncertain", [])) for c in cases),
    }
    return errors, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file")
    args = parser.parse_args()
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    errors, summary = validate(data)
    print(json.dumps(summary, indent=1))
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} problem(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

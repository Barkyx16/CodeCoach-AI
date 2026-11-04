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

from app.careers.grading import Feedback, _normalize
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
        truncated = quote.startswith("…") or quote.endswith("…")
        body = quote.strip("…").strip()  # an ellipsis marks where a long sentence was cut
        if body not in flat:
            problems.append(f"{p.label}: quote is not the learner's words: {p.evidence[:60]!r}")
            continue
        span = getattr(p, "span", None)  # rubric v3 records where the quote is; older rubrics don't
        if span is not None and _norm(answer[span[0] : span[1]]) != body:
            problems.append(f"{p.label}: the recorded position doesn't hold the quoted text")
        # Read the quote the way the rubric reads the answer (apostrophes and filler sounds out).
        padded = " " + _normalize(body).text + " "
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
        "left_out_text": any(n.startswith("Left out") for n in fb.notes),
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


# --- protocol metrics (evals/protocol.json "metrics") ------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval for k successes out of n (None when n is 0)."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": _r(k / n) if n else None, "ci95": wilson(k, n)}


def protocol_metrics(dataset: dict, result: dict) -> dict:
    """The protocol's metrics for one graded set: each with numerator, denominator and interval."""
    cases = {c["id"]: c for c in dataset["cases"]}
    graded = {c["id"]: c for c in result["cases"] if "error" not in c}
    a = result["point_agreement"]
    out: dict = {
        "item_precision": rate(a["tp"], a["tp"] + a["fp"]),
        "item_recall": rate(a["tp"], a["tp"] + a["fn"]),
        "unsupported_credit_rate": rate(a["fp"], a["fp"] + a["tn"]),
        "rating_within_bounds": rate(
            result["dimensions"]["rating"]["passed"], result["dimensions"]["rating"]["cases"]
        ),
    }

    def of(variant: str) -> list[tuple[dict, dict]]:
        return [(cases[i], g) for i, g in graded.items() if cases[i].get("variant") == variant]

    kw = of("keyword_list")
    out["keyword_false_award"] = rate(
        sum(g["observed"]["rating"] in ("Good", "Strong") for _, g in kw), len(kw)
    )
    contradicted = [
        (c, g, label) for c, g in of("contradiction") for label in c.get("contradicted_points", [])
    ]
    out["contradiction_full_credit"] = rate(
        sum(label in g["observed"]["covered"] for _, g, label in contradicted), len(contradicted)
    )
    att = of("grader_directed")
    out["attack_credit"] = rate(
        sum(
            not (g["checks"].get("injection", {}).get("passed", True) and g["checks"]["evidence"]["passed"])
            for _, g in att
        ),
        len(att),
    )
    benign = of("benign_control")
    out["benign_false_exclusion"] = rate(sum(g["observed"]["left_out_text"] for _, g in benign), len(benign))
    same = changed = removed = awarded = 0
    for c, g in [*of("dictated"), *of("paraphrase"), *of("meaning_changed")]:
        pair = graded.get(c.get("pair_of"))
        if pair is None:
            continue
        if c["variant"] == "meaning_changed":
            typed_labels = cases[c["pair_of"]]["labels"]["points"]
            gone = [lab for lab, v in typed_labels.items() if v and not c["labels"]["points"].get(lab)]
            removed += len(gone)
            awarded += sum(lab in g["observed"]["covered"] for lab in gone)
            continue
        if c["variant"] != "dictated":
            continue
        for lab in c["labels"]["points"]:
            same += (lab in g["observed"]["covered"]) == (lab in pair["observed"]["covered"])
            changed += 1
    out["dictated_parity"] = rate(same, changed)
    out["meaning_changed_false_award"] = rate(awarded, removed)
    per_variant: dict[str, dict] = {}
    for c, g in ((cases[i], g) for i, g in graded.items()):
        v = c.get("variant") or (c.get("tags") or ["?"])[0]
        row = per_variant.setdefault(v, {"cases": 0, "tp": 0, "fp": 0, "fn": 0})
        row["cases"] += 1
        for r in g["points"]:
            if r["uncertain"]:
                continue
            row["tp"] += r["expected"] and r["predicted"]
            row["fp"] += (not r["expected"]) and r["predicted"]
            row["fn"] += r["expected"] and not r["predicted"]
    out["per_variant"] = {
        v: {
            "cases": r["cases"],
            "precision": rate(r["tp"], r["tp"] + r["fp"]),
            "recall": rate(r["tp"], r["tp"] + r["fn"]),
        }
        for v, r in sorted(per_variant.items())
    }
    return out


def evaluate_regression(grader: Grader) -> list[dict]:
    """Each known defect (evals/regression.json) against the cases that show it, in their own sets."""
    spec = json.loads((EVAL_DIR / "regression.json").read_text(encoding="utf-8"))
    names = {
        "career-rn-dev": "career_dev.json",
        "career-rn-holdout": "career_holdout.json",
        "career-rn-families-dev": "career_families_dev.json",
    }
    sets = {k: load(v) for k, v in names.items()}
    out = []
    for d in spec["defects"]:
        rows = []
        for ref in d["cases"]:
            set_id, case_id = ref.split("/")
            data = sets[set_id]
            case = next(c for c in data["cases"] if c["id"] == case_id)
            r = evaluate_case(case, data["track"], grader)
            sig = d["signal"]
            if "error" in r:
                shows = True
            elif sig["check"] == "typed_parity":
                q = get_question(data["track"], case["question_id"], case["question_version"])
                shows = [p.covered for p in grader(q, case["answer"]).points] != [
                    p.covered for p in grader(q, sig["typed"]).points
                ]
            elif sig["check"] == "pair_parity":
                q = get_question(data["track"], case["question_id"], case["question_version"])
                typed = next(c for c in data["cases"] if c["id"] == case["pair_of"])
                a = {p.label: p.covered for p in grader(q, case["answer"]).points}
                b = {p.label: p.covered for p in grader(q, typed["answer"]).points}
                shows = any(a[label] != b[label] for label in sig.get("points", a))
            elif sig["check"] == "transform_parity":
                from evals import dictation

                q = get_question(data["track"], case["question_id"], case["question_version"])
                transformed = getattr(dictation, sig["transform"])(case["answer"])
                shows = [p.covered for p in grader(q, case["answer"]).points] != [
                    p.covered for p in grader(q, transformed).points
                ]
            elif "point" in sig:
                row = next(x for x in r["points"] if x["label"] == sig["point"])
                shows = row["predicted"] != row["expected"]
            else:
                shows = not r["checks"].get(sig["check"], {"passed": True})["passed"]
            rows.append({"case": ref, "shows_defect": shows})
        out.append(
            {
                "id": d["id"],
                "status_recorded": d["status"],
                "cases": rows,
                "still_shows": any(r["shows_defect"] for r in rows),
            }
        )
    return out

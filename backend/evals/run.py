"""AI coach evaluation suite (blueprint §06): measure before claiming accuracy.

    python -m evals.run                      # offline coach (default, free, deterministic)
    AI_PROVIDER=anthropic ANTHROPIC_API_KEY=… python -m evals.run --provider anthropic

What it measures
----------------
Code review, on evals/review_set.json (hand-labelled samples; the verdict labels are verified
by running every sample through the real judge in tests/test_eval_labels.py):
  - issue detection, per category and micro-averaged: precision, recall, F1
  - false-alarm rate: share of CLEAN samples where the reviewer reported a medium/high issue
  - complexity accuracy: the reviewer's Big-O vs. the labelled Big-O
  - schema validity: every response parses as a CodeReview
Hints, for every problem:
  - level-1 spoiler rate: nudges that contain a give-away term (evals/hint_terms.json)
  - level-2 relevance: concept hints that mention the key idea
  - code leak rate: level 1–2 hints that contain Java code

Results go to evals/results/<provider>.json and .md. The numbers describe THIS labelled set
only. They are not general accuracy claims.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.db.seed import load_seed_files  # noqa: E402
from app.schemas.ai import CodeReview, HintContent  # noqa: E402
from app.services.ai.base import CoachProvider, HintContext, ProblemContext, ReviewContext  # noqa: E402
from app.services.ai.interviewer_offline import normalize_big_o  # noqa: E402
from app.services.ai.offline import OfflineCoach  # noqa: E402
from app.services.ai.service import build_provider, sanitize_code  # noqa: E402
from app.services.ai.static_analysis import analyze  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CATEGORIES = ["correctness", "edge-case", "complexity", "readability", "style"]
_CODE_LIKE = re.compile(r"(;\s*$|;\s*\n|\{\s*\n|\breturn\s+\w+\s*;|\bpublic\s+\w+)", re.M)


def problem_contexts() -> dict[str, ProblemContext]:
    out = {}
    for p in load_seed_files():
        out[p["slug"]] = ProblemContext(
            slug=p["slug"],
            title=p["title"],
            statement=p["statement"],
            constraints=p["constraints"],
            signature=p["signature"],
            starter_code=p["starter_code"],
            expected_time=p["expected_complexity"].get("time"),
            expected_space=p["expected_complexity"].get("space"),
            curated_hints=p["hints"],
        )
    return out


@dataclass
class ReviewScores:
    tp: Counter = field(default_factory=Counter)
    fp: Counter = field(default_factory=Counter)
    fn: Counter = field(default_factory=Counter)
    clean_samples: int = 0
    clean_false_alarms: int = 0
    complexity_hits: int = 0
    schema_valid: int = 0
    total: int = 0
    misses: list[dict] = field(default_factory=list)


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": _r(p), "recall": _r(r), "f1": _r(f), "tp": tp, "fp": fp, "fn": fn}


def _r(x: float | None) -> float | None:
    return round(x, 3) if x is not None else None


def evaluate_reviews(
    provider: CoachProvider, samples: list[dict], problems: dict[str, ProblemContext]
) -> dict:
    s = ReviewScores()
    for sample in samples:
        problem = problems[sample["problem"]]
        code = sanitize_code(sample["code"], 12_000)
        ctx = ReviewContext(
            problem=problem,
            code=code,
            judge_status=None,
            analysis=analyze(
                code,
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=problem.expected_time,
                constraints=problem.constraints,
            ),
        )
        result = provider.review(ctx)
        s.total += 1
        try:
            review = CodeReview.model_validate(result.content.model_dump())
            s.schema_valid += 1
        except Exception:  # noqa: BLE001 - counted as a schema failure
            continue
        predicted = {i.category for i in review.issues}
        expected = set(sample["categories"])
        for c in CATEGORIES:
            if c in predicted and c in expected:
                s.tp[c] += 1
            elif c in predicted:
                s.fp[c] += 1
            elif c in expected:
                s.fn[c] += 1
        if not expected:
            s.clean_samples += 1
            if any(i.severity in ("medium", "high") for i in review.issues):
                s.clean_false_alarms += 1
        if normalize_big_o(review.complexity.time.strip("O()")) == normalize_big_o(
            sample["time"].strip("O()")
        ):
            s.complexity_hits += 1
        if predicted != expected:
            s.misses.append(
                {
                    "id": sample["id"],
                    "expected": sorted(expected),
                    "predicted": sorted(predicted),
                    "time_expected": sample["time"],
                    "time_predicted": review.complexity.time,
                }
            )
    per_category = {c: _prf(s.tp[c], s.fp[c], s.fn[c]) for c in CATEGORIES}
    micro = _prf(sum(s.tp.values()), sum(s.fp.values()), sum(s.fn.values()))
    return {
        "samples": s.total,
        "schema_validity": _r(s.schema_valid / s.total),
        "issue_detection_micro": micro,
        "issue_detection_by_category": per_category,
        "clean_samples": s.clean_samples,
        "false_alarm_rate_on_clean_code": _r(s.clean_false_alarms / s.clean_samples)
        if s.clean_samples
        else None,
        "complexity_accuracy": _r(s.complexity_hits / s.total),
        "disagreements": s.misses,
    }


def _mentions(text: str, term: str) -> bool:
    """Whole-word match, so the variable name "mid" doesn't match the word "middle"."""
    return re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text) is not None


def evaluate_hints(provider: CoachProvider, problems: dict[str, ProblemContext], terms: dict) -> dict:
    spoilers, relevant, code_leaks, checked = [], 0, [], 0
    for slug, problem in problems.items():
        t = terms[slug]
        starter = problem.starter_code
        for level in (1, 2):
            ctx = HintContext(problem=problem, code=starter, level=level, analysis=analyze(starter))
            hint: HintContent = provider.hint(ctx).content
            text = hint.hint.lower()
            checked += 1
            if level == 1 and any(_mentions(text, term) for term in t["level1_spoilers"]):
                spoilers.append(slug)
            if level == 2 and any(_mentions(text, term) for term in t["level2_concepts"]):
                relevant += 1
            if _CODE_LIKE.search(hint.hint):
                code_leaks.append(f"{slug}:L{level}")
    n = len(problems)
    return {
        "problems": n,
        "level1_spoiler_rate": _r(len(spoilers) / n),
        "level1_spoilers": spoilers,
        "level2_relevance": _r(relevant / n),
        "code_leak_rate_levels_1_2": _r(len(code_leaks) / checked),
        "code_leaks": code_leaks,
    }


def run(provider_name: str = "offline") -> dict:
    samples = json.loads((EVAL_DIR / "review_set.json").read_text())["samples"]
    holdout = json.loads((EVAL_DIR / "holdout_set.json").read_text())["samples"]
    medium = json.loads((EVAL_DIR / "medium_set.json").read_text())["samples"]
    terms = json.loads((EVAL_DIR / "hint_terms.json").read_text())
    problems = problem_contexts()
    if provider_name == "offline":
        provider: CoachProvider = OfflineCoach()
    else:
        provider = build_provider(Settings())  # reads AI_PROVIDER / ANTHROPIC_API_KEY from the environment
        if provider.name != provider_name:
            raise SystemExit(f"Provider {provider_name!r} is not configured (got {provider.name!r}).")
    start = time.perf_counter()
    report = {
        "provider": provider.name,
        "model": provider.model,
        "evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        # review_set.json was used while improving the offline rules; holdout_set.json was written
        # afterwards and never used to change them, so it's the honest generalisation number.
        "review": evaluate_reviews(provider, samples, problems),
        "review_holdout": evaluate_reviews(provider, holdout, problems),
        # medium_set.json covers the medium problems added in session 5; also held out.
        "review_medium": evaluate_reviews(provider, medium, problems),
        "hints": evaluate_hints(provider, problems, terms),
    }
    report["duration_s"] = round(time.perf_counter() - start, 2)
    return report


def to_markdown(r: dict) -> str:
    rv, h, ho = r["review"], r["hints"], r.get("review_holdout")
    lines = [
        f"# Coach evaluation: `{r['provider']}` ({r['model']})",
        "",
        f"Run {r['evaluated_at']} over {rv['samples']} labelled review samples and {h['problems']} problems. "
        "These numbers describe this labelled set only.",
        "",
        "## Tuning set",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Schema validity | {rv['schema_validity']:.0%} |",
        f"| Issue detection (micro) precision / recall / F1 | {_pct(rv['issue_detection_micro']['precision'])} / {_pct(rv['issue_detection_micro']['recall'])} / {_pct(rv['issue_detection_micro']['f1'])} |",
        f"| False alarms on clean code (medium/high issue on a clean sample) | {_pct(rv['false_alarm_rate_on_clean_code'])} of {rv['clean_samples']} |",
        f"| Complexity (Big-O) accuracy | {_pct(rv['complexity_accuracy'])} |",
        f"| Level-1 hint spoiler rate | {_pct(h['level1_spoiler_rate'])} |",
        f"| Level-2 hint relevance | {_pct(h['level2_relevance'])} |",
        f"| Code in level 1–2 hints | {_pct(h['code_leak_rate_levels_1_2'])} |",
        "",
        *(_holdout_section(ho) if ho else []),
        *(
            _holdout_section(r["review_medium"], title="Medium held-out set (newer problems)")
            if r.get("review_medium")
            else []
        ),
        "## Issue detection by category (tuning set)",
        "",
        "| Category | Precision | Recall | F1 | TP | FP | FN |",
        "|---|---|---|---|---|---|---|",
    ]
    for c, m in rv["issue_detection_by_category"].items():
        lines.append(
            f"| {c} | {_pct(m['precision'])} | {_pct(m['recall'])} | {_pct(m['f1'])} | {m['tp']} | {m['fp']} | {m['fn']} |"
        )
    lines += [
        "",
        "## Disagreements with the labels",
        "",
        "| Sample | Expected | Reviewer said | Big-O expected → reported |",
        "|---|---|---|---|",
    ]
    for d in rv["disagreements"]:
        lines.append(
            f"| `{d['id']}` | {', '.join(d['expected']) or '—'} | {', '.join(d['predicted']) or '—'} | "
            f"{d['time_expected']} → {d['time_predicted']} |"
        )
    return "\n".join(lines) + "\n"


def _holdout_section(ho: dict, title: str = "Held-out set (generalisation)") -> list[str]:
    m = ho["issue_detection_micro"]
    rows = [
        f"## {title}",
        "",
        f"{ho['samples']} samples written after the rules were frozen; never used to tune them.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Issue detection (micro) precision / recall / F1 | {_pct(m['precision'])} / {_pct(m['recall'])} / {_pct(m['f1'])} |",
        f"| False alarms on clean code | {_pct(ho['false_alarm_rate_on_clean_code'])} of {ho['clean_samples']} |",
        f"| Complexity (Big-O) accuracy | {_pct(ho['complexity_accuracy'])} |",
        "",
        "| Sample | Expected | Reviewer said | Big-O expected → reported |",
        "|---|---|---|---|",
    ]
    for d in ho["disagreements"]:
        rows.append(
            f"| `{d['id']}` | {', '.join(d['expected']) or '—'} | {', '.join(d['predicted']) or '—'} | "
            f"{d['time_expected']} → {d['time_predicted']} |"
        )
    return rows + [""]


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", default="offline", choices=["offline", "anthropic"])
    args = parser.parse_args()
    report = run(args.provider)
    out = EVAL_DIR / "results"
    out.mkdir(exist_ok=True)
    (out / f"{report['provider']}.json").write_text(json.dumps(report, indent=2) + "\n")
    md = to_markdown(report)
    (out / f"{report['provider']}.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()

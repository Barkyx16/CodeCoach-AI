"""Freeze a scoring candidate before a measurement, and check later that nothing it depends on moved.

    python -m evals.freeze write --label candidate-rubric-v9     # evals/results/freeze-<date>-<label>.json
    python -m evals.freeze check evals/results/freeze-<...>.json  # exit 1 if anything it froze changed

A freeze names the commit and tree, the rubric and coach prompt versions with the request
fingerprint, the protocol version, a hash of every file that decides a career score or a request
to Claude, every dataset's hash, the dependency files, and the metrics and release rule declared
before the measurement (copied from evals/protocol.json). Writing one refuses a tree with
uncommitted changes outside evaluation outputs, so the record always describes a commit.
A freeze is not a measurement: it says what will be measured, and with what.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from evals import meta

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
RESULTS = BACKEND / "evals" / "results"
# Everything that decides a career answer's score and feedback, or what is asked of Claude.
SCORING = (
    "backend/app/careers/grading.py",
    "backend/app/careers/questions.py",
    "backend/app/careers/contradictions.py",
    "backend/app/careers/evidence.py",
    "backend/app/careers/profiles.py",
    "backend/app/services/ai/anthropic_provider.py",
    "backend/evals/protocol.json",
)
DEPENDENCIES = ("backend/requirements.txt", "backend/requirements-dev.txt", "frontend/package-lock.json")
# Metrics declared before the measurement, each with what its denominator counts.
DECLARED = {
    "item_precision": "rubric points the coach credited (non-uncertain labels)",
    "item_recall": "rubric points labelled covered (non-uncertain)",
    "unsupported_credit_rate": "rubric points labelled missing",
    "contradiction_detection_precision": "contradictions the coach reported",
    "contradiction_detection_recall": "answers labelled contradictory",
    "contradiction_full_credit": "contradicted points in contradiction answers",
    "meaning_changed_false_award": "points labelled covered on a typed answer and missing on its meaning-changed version",
    "keyword_false_award": "keyword_list answers (incl. the question's guidance copied or reported back)",
    "benign_false_exclusion": "benign control answers",
    "attack_credit": "grader-directed answers",
    "contradiction_collateral": "covered points a reported contradiction isn't about",
    "quote_validity": "quotes shown as evidence",
    "quote_relevance": "quotes shown as evidence",
    "dictated_parity": "point decisions of dictated answers, against their typed pairs",
    "rating_within_bounds": "answers with a rating bound",
}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _dirty() -> list[str]:
    lines = _git("status", "--porcelain", "--untracked-files=no").splitlines()
    return [x for x in lines if "evals/results/" not in x and "evals/reviews/" not in x]


def record(label: str) -> dict:
    from app.careers.grading import RUBRIC_VERSION
    from app.services.ai.anthropic_provider import PROMPT_VERSION

    if _dirty():
        raise SystemExit("uncommitted changes: commit them first, so the freeze names what it froze")
    protocol = json.loads((BACKEND / "evals" / "protocol.json").read_text(encoding="utf-8"))
    return {
        "label": label,
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "candidate_commit": _git("rev-parse", "HEAD"),
        "tree": _git("rev-parse", "HEAD^{tree}"),
        "rubric_version": RUBRIC_VERSION,
        "coach_prompt_version": PROMPT_VERSION,
        "coach_request_fingerprint": meta.request_fingerprint(),
        "protocol_version": protocol["protocol_version"],
        "scoring_files": {f: _sha(f) for f in SCORING},
        "datasets": {d["id"]: d["sha256_actual"] for d in meta.datasets()},
        "dependencies": {f: _sha(f) for f in DEPENDENCIES},
        "python": platform.python_version(),
        "declared_metrics": DECLARED,
        "release_rule": protocol["release"],
        "rule": (
            "No change to scoring, rubric, prompts, protocol or datasets after this point before the "
            "measurement it was frozen for; if any changes, `python -m evals.freeze check` fails and the "
            "measurement must be planned again on a new frozen candidate."
        ),
    }


def check(rec: dict) -> list[str]:
    """What changed since the freeze (empty when nothing it froze moved)."""
    from app.careers.grading import RUBRIC_VERSION
    from app.services.ai.anthropic_provider import PROMPT_VERSION

    problems = []
    if rec["rubric_version"] != RUBRIC_VERSION:
        problems.append(f"rubric {RUBRIC_VERSION}, frozen {rec['rubric_version']}")
    if rec["coach_prompt_version"] != PROMPT_VERSION:
        problems.append(f"coach prompt {PROMPT_VERSION}, frozen {rec['coach_prompt_version']}")
    if meta.request_fingerprint() != rec["coach_request_fingerprint"]:
        problems.append("the request fingerprint changed (prompts, request settings or output schemas)")
    for f, h in rec["scoring_files"].items():
        if _sha(f) != h:
            problems.append(f"{f} changed")
    now = {d["id"]: d["sha256_actual"] for d in meta.datasets()}
    for d, h in rec["datasets"].items():
        if now.get(d) != h:
            problems.append(f"dataset {d} changed")
    problems += [f"dataset {d} added after the freeze" for d in now.keys() - rec["datasets"].keys()]
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--label", required=True)
    c = sub.add_parser("check")
    c.add_argument("record", type=Path)
    a = parser.parse_args()
    if a.cmd == "write":
        rec = record(a.label)
        path = RESULTS / f"freeze-{rec['frozen_at'][:10]}-{a.label}.json"
        path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}: {rec['candidate_commit'][:12]}, rubric {rec['rubric_version']}")
        return
    problems = check(json.loads(a.record.read_text(encoding="utf-8")))
    for p in problems:
        print(f"moved: {p}")
    print("frozen candidate unchanged" if not problems else f"{len(problems)} change(s) since the freeze")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

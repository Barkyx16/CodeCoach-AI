"""Release gates: a small set of checks a coach change must pass, each with its reason.

A gate either passes, fails with the cases and checks that failed, or is "not run" when its
section isn't in the report. Gates on held-out sets name the case and check but not the answer
text, so the held-out set isn't turned into a set to tune against by reading it.

`compare` puts a baseline and a candidate report side by side. They must have run on the same
datasets (same content hashes); everything else that differs (commit, rubric, prompt, provider,
model, configuration) is listed as a changed condition. A check that passed in the baseline and
fails in the candidate is a regression, case by case.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from evals.meta import REPORT_SCHEMA


@dataclass(frozen=True)
class Gate:
    id: str
    why: str
    check: Callable[[dict], list[str] | None]  # failures; None when the section wasn't run


def _gated() -> set[str]:
    from evals.meta import EVAL_DIR

    protocol = json.loads((EVAL_DIR / "protocol.json").read_text(encoding="utf-8"))
    return set(protocol["gated_career_sets"]["sets"])


def _career_sets(report: dict) -> dict[str, dict]:
    """The career sets the per-case gates apply to (protocol.json: gated_career_sets). A
    development set written to expose weaknesses is reported, not gated, until a fix covers it."""
    gated = _gated()
    return {k: v for k, v in (report.get("career") or {}).items() if k in gated}


def _career_dimension(name: str) -> Callable[[dict], list[str] | None]:
    def check(report: dict) -> list[str] | None:
        sets = _career_sets(report)
        if not sets:
            return None
        failures = []
        for set_id, s in sets.items():
            for case in s["cases"]:
                c = case.get("checks", {}).get(name)
                if c and not c["passed"]:
                    if s["split"] == "holdout":
                        failures.append(
                            f"{set_id} / {case['id']}: {name} failed (held-out: details in the JSON report)"
                        )
                    else:
                        failures.append(f"{set_id} / {case['id']}: " + "; ".join(c["problems"]))
        return failures

    return check


# Variants whose answers must never be reported as contradicting themselves (rubric v5).
NOT_CONTRADICTIONS = ("self_correction", "benign_control", "contradiction_control")


def _gated_families(report: dict, which: tuple[str, ...]) -> list[str] | None:
    """Development families a brief has fixed (protocol.json gated_career_sets.families): a
    keyword_list answer is awarded no point; a self-correction or control is not reported as a
    contradiction."""
    from evals.meta import EVAL_DIR

    families = json.loads((EVAL_DIR / "protocol.json").read_text(encoding="utf-8"))["gated_career_sets"].get(
        "families", {}
    )
    families = {k: [v for v in vs if v in which] for k, vs in families.items()}
    sets = report.get("career") or {}
    if not any(k in sets and families[k] for k in families):
        return None
    out = []
    for set_id, variants in families.items():
        for case in sets.get(set_id, {}).get("cases", []):
            tags, observed = case.get("tags", []), case.get("observed", {})
            if "keyword_list" in variants and "keyword_list" in tags and observed.get("covered"):
                out.append(
                    f"{set_id} / {case['id']}: a keyword list was awarded {', '.join(observed['covered'])}"
                )
            gated = [v for v in variants if v in NOT_CONTRADICTIONS and v in tags]
            if gated and any(c["status"] == "conflict" for c in observed.get("conflicts", [])):
                out.append(
                    f"{set_id} / {case['id']}: a {gated[0]} answer was reported as contradicting itself"
                )
    return out


def _career_complete(report: dict) -> list[str] | None:
    sets = _career_sets(report)
    if not sets:
        return None
    out = []
    for set_id, s in sets.items():
        out += [f"{set_id} / {e['id']}: {e['error']}" for e in s["case_errors"]]
        if s["cases_scored"] != s["cases_planned"]:
            out.append(f"{set_id}: scored {s['cases_scored']} of {s['cases_planned']} cases")
    return out


def _career_agreement(report: dict) -> list[str] | None:
    s = _career_sets(report).get("career-rn-dev")
    if s is None:
        return None
    a = s["point_agreement"]
    out = []
    if a["precision"] is None or a["precision"] < 0.75:
        out.append(
            f"precision {a['precision']} < 0.75 (points marked covered that the labels say are missing: {a['fp']})"
        )
    if a["recall"] is None or a["recall"] < 0.92:
        out.append(f"recall {a['recall']} < 0.92 (covered points the grader missed: {a['fn']})")
    return out


def _metric(
    section: str, path: tuple[str, ...], op: str, bound: float, what: str
) -> Callable[[dict], list[str] | None]:
    def check(report: dict) -> list[str] | None:
        value = report.get(section)
        if value is None:
            return None
        for key in path:
            value = value[key]
        ok = value is not None and (value >= bound if op == ">=" else value <= bound)
        return [] if ok else [f"{what} is {value}, needs {op} {bound}"]

    return check


def _contract(name: str) -> Callable[[dict], list[str] | None]:
    def check(report: dict) -> list[str] | None:
        c = report.get("contracts")
        return None if c is None else list(c["checks"][name]["failures"])

    return check


def _data_overlap(report: dict) -> list[str] | None:
    d = report.get("data_checks")
    if d is None:
        return None
    out = [f"no review recorded for {p}" for p in d["unreviewed_pairs"]]
    out += [f"{set_id}: {e}" for set_id, errors in d["validation"].items() for e in errors]
    return out


def _regression(report: dict) -> list[str] | None:
    rows = report.get("regression")
    if rows is None:
        return None
    out = []
    for d in rows:
        if d["status_recorded"] == "fixed" and d["still_shows"]:
            out.append(
                f"{d['id']}: recorded fixed but shows again on "
                + ", ".join(c["case"] for c in d["cases"] if c["shows_defect"])
            )
        if d["status_recorded"] == "open" and not d["still_shows"]:
            out.append(
                f"{d['id']}: no longer shows; record it as fixed (with the commit) in evals/regression.json"
            )
    return out


def _faults(report: dict) -> list[str] | None:
    f = report.get("faults")
    if f is None:
        return None
    return [f"{r['scenario']} during {r['action']}: {r['problem']}" for r in f["failed"]]


def _integrity(report: dict) -> list[str] | None:
    meta = report.get("meta")
    if meta is None:
        return None
    out = []
    if meta.get("report_schema") != REPORT_SCHEMA:
        out.append(f"report schema {meta.get('report_schema')}, this code reads {REPORT_SCHEMA}")
    if not report.get("complete"):
        out.append("partial run: " + "; ".join(report.get("incomplete_reasons") or ["unknown"]))
    out += [
        f"{d['file']}: content differs from the manifest"
        for d in meta["datasets"]
        if not d["matches_manifest"]
    ]
    out += report.get("version_problems", [])
    return out


GATES: list[Gate] = [
    Gate(
        "report.integrity",
        "Only a complete run on the recorded datasets and prompt version is a result.",
        _integrity,
    ),
    Gate(
        "coding.schema",
        "The review UI needs every response to parse.",
        _metric("review", ("schema_validity",), ">=", 1.0, "review schema validity"),
    ),
    Gate(
        "coding.precision",
        "Reported issues that aren't real teach the wrong thing; floor just under the measured tuning-set level.",
        _metric(
            "review", ("issue_detection_micro", "precision"), ">=", 0.95, "review precision (tuning set)"
        ),
    ),
    Gate(
        "coding.recall",
        "Floor just under the measured tuning-set level, so a rule change can't silently stop finding issues.",
        _metric("review", ("issue_detection_micro", "recall"), ">=", 0.55, "review recall (tuning set)"),
    ),
    Gate(
        "coding.false_alarms",
        "Clean code reported as broken is the most discouraging mistake.",
        _metric(
            "review",
            ("false_alarm_rate_on_clean_code",),
            "<=",
            0.10,
            "false alarms on clean code (tuning set)",
        ),
    ),
    Gate(
        "coding.big_o",
        "Complexity feedback is a core interview skill.",
        _metric("review", ("complexity_accuracy",), ">=", 0.90, "Big-O accuracy (tuning set)"),
    ),
    Gate(
        "hints.no_spoilers",
        "A level-1 nudge must not name the answer.",
        _metric("hints", ("level1_spoiler_rate",), "<=", 0.0, "level-1 spoiler rate"),
    ),
    Gate(
        "hints.no_code",
        "Hints below level 3 must not contain code.",
        _metric("hints", ("code_leak_rate_levels_1_2",), "<=", 0.0, "code in level 1-2 hints"),
    ),
    Gate(
        "career.complete",
        "Every labelled answer must be graded; a skipped case hides a failure.",
        _career_complete,
    ),
    Gate(
        "career.schema", "Feedback must have the shape the app stores and shows.", _career_dimension("schema")
    ),
    Gate(
        "career.evidence",
        "A quote that isn't the learner's words, or doesn't show the point, makes feedback look grounded when it isn't.",
        _career_dimension("evidence"),
    ),
    Gate(
        "career.insufficient",
        "Answers too short to judge get no score and no praise (the product rule since rubric v1).",
        _career_dimension("insufficient"),
    ),
    Gate(
        "career.injection",
        "Text addressed to the grader must not earn credit.",
        _career_dimension("injection"),
    ),
    Gate(
        "career.stable",
        "The built-in coach promises the same result for the same answer; re-evaluation relies on it.",
        _career_dimension("stable"),
    ),
    Gate(
        "career.actionable",
        "Every missing point needs advice, and the summary must say where to start.",
        _career_dimension("actionable"),
    ),
    Gate(
        "career.agreement",
        "Floor at the agreement rubric v1 measured on the development set (precision 0.753, recall 0.935): no change may agree less with the labels.",
        _career_agreement,
    ),
    Gate(
        "contract.framing",
        "Learner text must reach Claude as data inside tags, under a rule not to follow it.",
        _contract("framing"),
    ),
    Gate("contract.ladder", "Hints must not carry deeper levels than the one unlocked.", _contract("ladder")),
    Gate("contract.hidden_tests", "Hidden test inputs must never reach a prompt.", _contract("hidden_tests")),
    Gate(
        "contract.secrets",
        "Keys and passwords in learner code must be redacted before they leave the server.",
        _contract("secrets"),
    ),
    Gate(
        "contract.bounded", "Every request asks for a known schema with a token limit.", _contract("bounded")
    ),
    Gate(
        "career.keyword_lists",
        "A list of terms, headings or the question's guidance said back names a point without showing it (rubric v4).",
        lambda report: _gated_families(report, ("keyword_list",)),
    ),
    Gate(
        "career.contradiction_controls",
        "A self-correction, quoted speech, a hypothetical or an ordinary negation is not a contradiction; "
        "reporting one takes credit away for nothing (rubric v5).",
        lambda report: _gated_families(report, NOT_CONTRADICTIONS),
    ),
    Gate(
        "data.integrity",
        "Every case file follows the protocol, and no answer is close to one in another split without a recorded review.",
        _data_overlap,
    ),
    Gate(
        "data.regression_status",
        "A fixed defect must not come back, and a defect that no longer shows must be recorded as fixed.",
        _regression,
    ),
    Gate(
        "contract.reference_leak",
        "The evaluation's reference text never reaches the model it evaluates.",
        _contract("reference_leak"),
    ),
    Gate(
        "provider.fallback",
        "When Claude fails in any way, the learner gets the offline coach, not an error.",
        _faults,
    ),
]


def evaluate_gates(report: dict) -> list[dict]:
    out = []
    for g in GATES:
        failures = g.check(report)
        out.append(
            {
                "id": g.id,
                "why": g.why,
                "status": "not run" if failures is None else ("passed" if not failures else "failed"),
                "failures": failures or [],
            }
        )
    return out


# --- comparing two reports --------------------------------------------------------------------

CONDITIONS = (
    "commit",
    "uncommitted_changes",
    "rubric_version",
    "prompt_version",
    "prompt_fingerprint",
    "provider",
    "model",
    "config",
)


def compare(baseline: dict, candidate: dict) -> dict:
    b_meta, c_meta = baseline["meta"], candidate["meta"]
    b_data = {d["id"]: d["sha256_actual"] for d in b_meta["datasets"]}
    c_data = {d["id"]: d["sha256_actual"] for d in c_meta["datasets"]}
    changed_data = sorted(k for k in b_data.keys() & c_data.keys() if b_data[k] != c_data[k])
    result: dict = {
        "baseline_run": b_meta["run_id"],
        "candidate_run": c_meta["run_id"],
        "comparable": not changed_data,
        "changed_datasets": changed_data,
        "changed_conditions": {
            k: {"baseline": b_meta.get(k), "candidate": c_meta.get(k)}
            for k in CONDITIONS
            if b_meta.get(k) != c_meta.get(k)
        },
        "fixed": [],
        "regressed": [],
        "metrics": {},
    }
    if changed_data:
        return result
    for set_id in sorted(_career_sets(baseline).keys() & _career_sets(candidate).keys()):
        b_cases = {c["id"]: c for c in baseline["career"][set_id]["cases"]}
        for c in candidate["career"][set_id]["cases"]:
            b = b_cases.get(c["id"])
            if b is None:
                continue
            for name in sorted(set(b.get("checks", {})) | set(c.get("checks", {}))):
                was = b.get("checks", {}).get(name, {}).get("passed")
                now = c.get("checks", {}).get(name, {}).get("passed")
                if was is True and now is False:
                    result["regressed"].append(f"{set_id} / {c['id']}: {name}")
                elif was is False and now is True:
                    result["fixed"].append(f"{set_id} / {c['id']}: {name}")
            if "error" in c and "error" not in b:
                result["regressed"].append(f"{set_id} / {c['id']}: now fails to grade ({c['error']})")
        bs, cs = baseline["career"][set_id], candidate["career"][set_id]
        result["metrics"][set_id] = {
            "precision": [bs["point_agreement"]["precision"], cs["point_agreement"]["precision"]],
            "recall": [bs["point_agreement"]["recall"], cs["point_agreement"]["recall"]],
            **{
                f"{d} passed": [bs["dimensions"][d]["passed"], cs["dimensions"][d]["passed"]]
                for d in bs["dimensions"]
                if bs["dimensions"][d]["cases"]
            },
        }
    for section in ("review", "review_holdout", "review_medium"):
        if baseline.get(section) and candidate.get(section):
            bm, cm = baseline[section]["issue_detection_micro"], candidate[section]["issue_detection_micro"]
            result["metrics"][section] = {
                "precision": [bm["precision"], cm["precision"]],
                "recall": [bm["recall"], cm["recall"]],
                "false_alarms": [
                    baseline[section]["false_alarm_rate_on_clean_code"],
                    candidate[section]["false_alarm_rate_on_clean_code"],
                ],
                "big_o": [
                    baseline[section]["complexity_accuracy"],
                    candidate[section]["complexity_accuracy"],
                ],
            }
    if baseline.get("faults") and candidate.get("faults"):
        result["metrics"]["provider fallback"] = {
            "passed": [baseline["faults"]["passed"], candidate["faults"]["passed"]],
            "of": candidate["faults"]["checks"],
        }
        b_ok = {(r["scenario"], r["action"]) for r in baseline["faults"]["rows"] if r["passed"]}
        for r in candidate["faults"]["rows"]:
            key = (r["scenario"], r["action"])
            if key in b_ok and not r["passed"]:
                result["regressed"].append(f"provider fallback: {r['scenario']} during {r['action']}")
            elif key not in b_ok and r["passed"]:
                result["fixed"].append(f"provider fallback: {r['scenario']} during {r['action']}")
    if baseline.get("contracts") and candidate.get("contracts"):
        for name, c in candidate["contracts"]["checks"].items():
            was = baseline["contracts"]["checks"].get(name, {}).get("passed")
            if was and not c["passed"]:
                result["regressed"].append(f"contract: {name}")
            elif was is False and c["passed"]:
                result["fixed"].append(f"contract: {name}")
    return result

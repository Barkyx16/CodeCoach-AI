"""The "CI summary" check: one conclusion for the exact event and SHA (Volume 8, prompt 10;
docs/CI.md). It reads every job's result and the lanes the change needed, writes a table to the
run's summary page, and fails closed:

- the change couldn't be classified (the `changes` job didn't succeed): fail;
- a required job didn't succeed (failed, cancelled, or skipped): fail;
- a job that ran and failed fails the summary even if the change didn't need it;
- a job this script expects is missing from the run: fail (it can't be dropped silently).

A documentation-only change passes with the code jobs not run, and says so: documentation
validation, not code evidence for this SHA.

    NEEDS='${{ toJSON(needs) }}' python scripts/ci_summary.py
"""

from __future__ import annotations

import json
import os
import sys

# job id -> the lane that makes it required ("always": every run).
JOBS = {
    "security": "always",
    "backend": "backend",
    "backend-pg": "backend",
    "frontend": "frontend",
    "e2e": "e2e",
    "runner": "runner",
    "sandbox": "sandbox",
    "docker": "docker",
}


def evaluate(needs: dict) -> tuple[bool, list[tuple[str, str, str, str]], str]:
    """(passed, rows of (job, required, result, verdict), headline)."""
    changes = needs.get("changes") or {}
    if changes.get("result") != "success":
        return (
            False,
            [("changes", "yes", changes.get("result", "missing"), "FAIL")],
            "the change couldn't be classified: no evidence",
        )
    try:
        lanes = json.loads((changes.get("outputs") or {}).get("lanes") or "")
    except json.JSONDecodeError:
        return (
            False,
            [("changes", "yes", "no lanes", "FAIL")],
            "the classification gave no lanes: no evidence",
        )
    rows, passed = [], True
    for job, lane in JOBS.items():
        required = lane == "always" or bool(lanes.get(lane))
        result = (needs.get(job) or {}).get("result", "missing")
        if result == "success":
            verdict = "ok"
        elif result == "skipped" and not required:
            verdict = "not required for this change"
        else:
            verdict = "FAIL"
            passed = False
        rows.append((job, "yes" if required else "no", result, verdict))
    if lanes.get("docs_only"):
        headline = (
            "documentation-only change: the code jobs didn't run on this SHA. This is documentation "
            "validation (secret scan, dependency audit), not code evidence"
        )
    elif lanes.get("full"):
        headline = "every lane required"
    else:
        headline = "lanes required: " + ", ".join(
            k for k in ("backend", "frontend", "e2e", "runner", "sandbox", "docker") if lanes.get(k)
        )
    return passed, rows, headline


def main() -> int:
    needs = json.loads(os.environ.get("NEEDS") or "{}")
    passed, rows, headline = evaluate(needs)
    sha = os.environ.get("GITHUB_SHA", "?")
    event = os.environ.get("GITHUB_EVENT_NAME", "?")
    lines = [
        f"### CI summary: {'passed' if passed else 'FAILED'}",
        f"{event} · `{sha[:12]}` · {headline}",
        "",
        "| Job | Required | Result | Verdict |",
        "|---|---|---|---|",
        *(f"| {job} | {req} | {res} | {verdict} |" for job, req, res, verdict in rows),
    ]
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

"""What a set of cases demonstrates, from the outputs the sandbox actually produced.

Every statement here is read off the run: the reference's output for each input, and each
variant's. A variant is "told apart" by a case when, on that input, it returns something different
from the reference (or throws where the reference doesn't). The learner's expected output only
decides whether a case counts: if it disagrees with the reference, the case is shown as
disagreeing with the specification and counts against nothing. Results that didn't arrive are
"not finished", never guessed. Coverage is over these authored variants only.
"""

from __future__ import annotations

from typing import Any

from app.services.judge.harness import outputs_match
from app.testdesign import LABEL_TEXT, Exercise, same_input, variant_key

REPORT_VERSION = 1
COVERAGE_NOTE = (
    "This counts only the {n} faulty versions written for this exercise. It says nothing about every "
    "possible defect, or about any hidden tests in the problem bank."
)


def unique_inputs(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[int], list[int | None]]:
    """(inputs to run, each case's position in them, each case's earlier duplicate or None)."""
    unique: list[dict[str, Any]] = []
    position: list[int] = []
    duplicate_of: list[int | None] = []
    for i, case in enumerate(cases):
        earlier = next((j for j in range(i) if same_input(cases[j]["input"], case["input"])), None)
        duplicate_of.append(earlier)
        if earlier is None:
            unique.append(case["input"])
            position.append(len(unique) - 1)
        else:
            position.append(position[earlier])
    return unique, position, duplicate_of


def _outcome(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {"kind": "missing"}
    if row.get("ok"):
        return {"kind": "value", "value": row.get("output")}
    return {"kind": "exception", "exception": str(row.get("exception") or "an exception")}


def _differs(a: dict[str, Any], b: dict[str, Any]) -> bool | None:
    if "missing" in (a["kind"], b["kind"]):
        return None
    if a["kind"] != b["kind"]:
        return True
    if a["kind"] == "value":
        return not outputs_match(a["value"], b["value"])
    return a["exception"] != b["exception"]


def _shown(o: dict[str, Any]) -> str:
    if o["kind"] == "value":
        v = o["value"]
        return "true" if v is True else "false" if v is False else str(v)
    if o["kind"] == "exception":
        return f"throws {o['exception']}"
    return "no result"


def report(ex: Exercise, cases: list[dict[str, Any]], outputs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    unique, position, duplicate_of = unique_inputs(cases)
    n_unique = len(unique)
    keys = [variant_key(k) for k in range(len(ex.variants))]
    caught: dict[str, list[int]] = {key: [] for key in keys}
    unsure: set[str] = set()  # versions with a result that never arrived
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    disagreeing = redundant = unfinished = 0
    for i, case in enumerate(cases):
        u = position[i]
        ref = _outcome(outputs.get(u))
        variants = [_outcome(outputs.get((k + 1) * n_unique + u)) for k in range(len(ex.variants))]
        row: dict[str, Any] = {
            "case": i + 1,
            "label": case.get("label"),
            "reference_output": _shown(ref),
            "status": "counted",
            "distinguishes": [],
            "new": [],
            "notes": [],
        }
        earlier = duplicate_of[i]
        if earlier is not None:
            row["status"] = "duplicate"
            row["notes"].append(
                f"Same input as case {earlier + 1}: it can't show anything that case doesn't, so it isn't counted again."
            )
            redundant += 1
        elif ref["kind"] == "missing":
            row["status"] = "not_finished"
            row["notes"].append(
                "No result arrived for this case (the run stopped early). Nothing was guessed."
            )
            unfinished += 1
        elif ref["kind"] == "exception":
            row["status"] = "reference_failed"
            row["notes"].append(
                f"The reference implementation {_shown(ref)} on this input, so the case can't be checked."
            )
        elif not outputs_match(case["expected"], ref["value"]):
            row["status"] = "disagrees"
            disagreeing += 1
            row["notes"].append(
                f"The specification's reference returns {_shown(ref)} here, not {_shown({'kind': 'value', 'value': case['expected']})}. "
                "A case with a wrong expected output isn't evidence against any version, so it isn't counted. "
                "Check the specification and fix the expected output."
            )
        else:
            tells = [key for key, o in zip(keys, variants, strict=True) if _differs(ref, o) is True]
            unknown = [key for key, o in zip(keys, variants, strict=True) if _differs(ref, o) is None]
            unsure.update(unknown)
            new = [v for v in tells if v not in seen]
            seen.update(tells)
            for v in tells:
                caught[v].append(i + 1)
            row["distinguishes"], row["new"] = tells, new
            if new:
                row["notes"].append(
                    f"Tells apart {len(new)} faulty version{'s' if len(new) != 1 else ''} that no earlier case did."
                )
            elif tells:
                row["notes"].append("Tells apart only versions an earlier case already did.")
                redundant += 1
            else:
                row["notes"].append(
                    "Every faulty version gives the same answer as the reference here, so this case doesn't "
                    "separate any of them."
                )
                redundant += 1
            if unknown:
                row["notes"].append(
                    f"{len(unknown)} version{'s' if len(unknown) != 1 else ''} didn't finish on this input, so "
                    "whether it tells them apart isn't known."
                )
        if case.get("label"):
            row["label_text"] = LABEL_TEXT.get(case["label"], case["label"])
        rows.append(row)

    total = len(ex.variants)
    found = sum(1 for ids in caught.values() if ids)
    summary = [
        f"Your cases tell {found} of the {total} authored faulty versions apart from the reference.",
        COVERAGE_NOTE.format(n=total),
    ]
    if disagreeing:
        summary.append(
            f"{disagreeing} case{'s' if disagreeing != 1 else ''} had an expected output that disagrees with the "
            "specification, so they weren't counted."
        )
    if redundant:
        summary.append(
            f"{redundant} case{'s' if redundant != 1 else ''} added nothing new among these versions. More cases "
            "aren't better testing; different ones are."
        )
    if unfinished or unsure:
        summary.append("Some results didn't arrive, so they're marked as unknown; nothing was guessed.")
    # One gap to investigate: a version no case told apart, among those whose every result arrived
    # (one with a missing result might have been told apart; it isn't offered as a gap).
    missed = [
        (key, v) for key, v in zip(keys, ex.variants, strict=True) if not caught[key] and key not in unsure
    ]
    gap = {"variant": missed[0][0], "hint": missed[0][1].gap} if missed and not unfinished else None
    return {
        "report_version": REPORT_VERSION,
        "cases": rows,
        # Versions are named by letter only: their ids would give the defects away. A caught version's
        # defect is named; a missed one stays hidden until the learner asks (the variants route).
        "variants": [
            {"key": key, "caught_by": caught[key], "title": v.title if caught[key] else None}
            for key, v in zip(keys, ex.variants, strict=True)
        ],
        "caught": found,
        "total": total,
        "summary": summary,
        "gap": gap,
    }

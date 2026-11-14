"""How a learner's selections compare with the authored explanation (docs/COMPARE_ANSWERS.md).

Fixed rules on the snapshot the attempt was made against. For each excerpt the learner marked:
- marked a strength, and the explanation lists it as a strength: "matches" (with the criterion);
- marked a strength, and the explanation lists it as a gap (or the reverse): "differs", with the
  explanation's reason to compare with theirs; they're invited to weigh both, not told they're wrong;
- the explanation doesn't single it out: "not covered": their reason may still hold.
The learner's reason is shown back next to the explanation's; the rules don't grade its wording.

A choice of answer (only offered in lessons with a preferred answer) is compared with that view and
explained; in a tradeoff lesson there's nothing to match. Nothing is scored, and choosing the
longer or more confident answer isn't rewarded: only the reasons tied to excerpts are discussed.
"""

from __future__ import annotations

from typing import Any

RULES_VERSION = 1


def _authored(snapshot: dict[str, Any]) -> dict[tuple[str, str], list[tuple[str, dict[str, Any]]]]:
    """(sample, sentence) -> [("strength" | "gap", the authored entry)]."""
    found: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    for sample_id, notes in snapshot["explanation"]["samples"].items():
        for kind, key in (("strength", "strengths"), ("gap", "gaps")):
            for entry in notes.get(key, []):
                for sentence in entry["sentences"]:
                    found.setdefault((sample_id, sentence), []).append((kind, entry))
    return found


def evaluate(
    snapshot: dict[str, Any], selections: list[dict[str, Any]], choice: str | None
) -> dict[str, Any]:
    authored = _authored(snapshot)
    labels = {r["id"]: r["label"] for r in snapshot["rubric"]}
    out = []
    for sel in selections:
        notes = authored.get((sel["sample"], sel["sentence"]), [])
        same = [entry for kind, entry in notes if kind == sel["kind"]]
        other = [entry for kind, entry in notes if kind != sel["kind"]]
        if same:
            status = "matches"
            note = f"The explanation also reads this as a {sel['kind']} ({labels.get(same[0]['criterion'], same[0]['criterion'])})."
            why = same[0]["why"]
        elif other:
            status = "differs"
            other_kind = "gap" if sel["kind"] == "strength" else "strength"
            note = (
                f"The explanation reads this as a {other_kind} ({labels.get(other[0]['criterion'], other[0]['criterion'])}). "
                "Compare its reason with yours; both can have a point."
            )
            why = other[0]["why"]
        else:
            status = "not_covered"
            note = "The explanation doesn't single this out. Your reason may still hold."
            why = None
        out.append({**sel, "status": status, "note": note, "explanation_why": why})

    preferred = snapshot["explanation"].get("preferred")
    if snapshot["kind"] == "tradeoff":
        choice_note = "This lesson has no single best answer: both have strengths. What matters is the reasons you gave."
    elif choice is None:
        choice_note = "You didn't choose an answer; the explanation's view is below, with its reasons."
    elif choice == preferred:
        choice_note = f"You chose Answer {choice}, as the explanation does. Check that your reasons match its reasons, not just its choice."
    else:
        choice_note = (
            f"You chose Answer {choice}; the explanation prefers Answer {preferred}. Its reasons are below. "
            "If yours rest on excerpts it doesn't weigh, they may still be worth keeping."
        )
    counts = {k: sum(1 for s in out if s["status"] == k) for k in ("matches", "differs", "not_covered")}
    return {
        "rules_version": RULES_VERSION,
        "selections": out,
        "counts": counts,
        "choice": choice,
        "choice_note": choice_note,
        "method": "Fixed rules, not AI: each excerpt you marked is compared with the authored explanation for this "
        "version of the samples. Your reasons are shown next to its reasons; they aren't graded.",
    }

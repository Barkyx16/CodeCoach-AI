"""Reviewed follow-up questions (Volume 12, prompt 4; docs/FOLLOW_UPS.md).

A small, authored relationship: after repeated practice on question A, question B asks for the same
objective in a different situation, so the learner can see whether an improvement carries over.
Each relationship names what A and B share and how B differs, and records who reviewed it and
how. The content gate (app/content/validate.py) checks every one: both questions exist in the bank,
the relationship is reviewed, and it stays in one career unless it says otherwise.

Nothing here is generated: when no reviewed relationship exists, nothing is offered.
"""

from __future__ import annotations

from dataclasses import dataclass

# Offered after this many answers to the question that were long enough to score: the same two
# tries the question page already compares (docs/OVERNIGHT_LOG.md, LX08).
THRESHOLD = 2


@dataclass(frozen=True)
class FollowUp:
    track: str
    from_id: str
    to_id: str
    objective: str  # what A and B share
    difference: str  # how B differs, in the learner's words
    review_status: str  # who reviewed it, when and against what
    to_track: str | None = None  # another career only when stated here, never inferred

    @property
    def target_track(self) -> str:
        return self.to_track or self.track


_REVIEWED = (
    "Reviewed 2026-11-14 against both questions' prompts and rubric points in the bank: the same "
    "rubric points, a different situation."
)

RELATIONSHIPS: tuple[FollowUp, ...] = (
    FollowUp(
        track="registered-nurse",
        from_id="e-tool-mistake-0",
        to_id="e-tool-mistake-1",
        objective="Catching a mistake with the equipment you use, and preventing a repeat",
        difference="Same checking habit, different equipment: IV pumps instead of electronic health records",
        review_status=_REVIEWED,
    ),
    FollowUp(
        track="registered-nurse",
        from_id="e-inform-0",
        to_id="e-inform-2",
        objective="Keeping people informed through a normal day",
        difference="Same communication habit, a different audience: patients' families instead of patients",
        review_status=_REVIEWED,
    ),
    FollowUp(
        track="registered-nurse",
        from_id="e-accuracy-0",
        to_id="e-accuracy-1",
        objective="Checking your own work",
        difference="Same self-checking habit, a different task: medication administration instead of patient assessment",
        review_status=_REVIEWED,
    ),
    FollowUp(
        track="customer-service-representative",
        from_id="e-tool-mistake-0",
        to_id="e-tool-mistake-1",
        objective="Catching a mistake with the tools you use, and preventing a repeat",
        difference="Same checking habit, a different tool: a CRM system instead of help desk software",
        review_status=_REVIEWED,
    ),
    FollowUp(
        track="customer-service-representative",
        from_id="e-inform-0",
        to_id="e-inform-1",
        objective="Keeping people informed through a normal day",
        difference="Same communication habit, a different audience: team leads instead of customers",
        review_status=_REVIEWED,
    ),
)


def follow_ups_from(
    track: str, question_id: str, relationships: tuple[FollowUp, ...] = RELATIONSHIPS
) -> list[FollowUp]:
    return [r for r in relationships if r.track == track and r.from_id == question_id]


def follow_ups_to(
    track: str, question_id: str, relationships: tuple[FollowUp, ...] = RELATIONSHIPS
) -> list[FollowUp]:
    return [r for r in relationships if r.target_track == track and r.to_id == question_id]


def problems(relationships: tuple[FollowUp, ...], exists) -> list[str]:
    """What the content gate refuses. `exists(track, question_id)` says whether the bank has it."""
    out = []
    seen = set()
    for r in relationships:
        where = f"follow-up {r.track}/{r.from_id} -> {r.target_track}/{r.to_id}"
        if (r.track, r.from_id, r.target_track, r.to_id) in seen:
            out.append(f"{where}: listed twice")
        seen.add((r.track, r.from_id, r.target_track, r.to_id))
        if not r.review_status.strip():
            out.append(f"{where}: not reviewed")
        if not r.objective.strip() or not r.difference.strip():
            out.append(f"{where}: no shared objective or no stated difference")
        if not exists(r.track, r.from_id):
            out.append(f"{where}: question {r.from_id!r} isn't in the {r.track} bank")
        if not exists(r.target_track, r.to_id):
            out.append(f"{where}: question {r.to_id!r} isn't in the {r.target_track} bank")
        if r.to_track == r.track:
            out.append(f"{where}: to_track repeats the career; leave it out")
        if (r.track, r.from_id) == (r.target_track, r.to_id):
            out.append(f"{where}: a question can't follow up itself")
    return out

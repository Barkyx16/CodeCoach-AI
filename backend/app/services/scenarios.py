"""Running branching scenarios on the server.

The attempt's current node lives in the database and every step is checked against the authored
graph: the client says which node it's answering and what it chose, never where to go next. A
repeated request for a step that was already recorded returns the attempt unchanged; a request
for any other node is refused. Each recorded step keeps a snapshot of the text and the authored
feedback, so a debrief still reads correctly after the scenario is revised or retired.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.careers import CATALOG
from app.errors import AppError, ConflictError, NotFoundError
from app.models import ScenarioAttempt, User
from app.scenarios import SCENARIO_INDEX, Node, Scenario, check_written, get_scenario, scenarios_for
from app.schemas.learn import ReferenceOut, ReviewOut
from app.schemas.scenarios import (
    Alternative,
    CareerCount,
    Debrief,
    DecisionOut,
    NodeView,
    OptionOut,
    ScenarioAttemptOut,
    ScenarioAttemptSummary,
    ScenarioCatalog,
    ScenarioDetail,
    ScenarioSummary,
    StartIn,
    StepIn,
    StepOut,
    WrittenOut,
)

FEEDBACK_SOURCE = "All feedback here is the scenario's authored decision rules and rubric points. No AI commentary was generated."
DISCLAIMER = (
    "Outcomes are simulated consequences of a fictional case. They don't predict what would happen at work or how "
    "an employer would judge you."
)


def _now() -> datetime:
    return datetime.now(UTC)


def _find(scenario_id: str) -> Scenario:
    s = get_scenario(scenario_id)
    if s is None:
        raise NotFoundError("Scenario not found")
    return s


def _longest_decisions(s: Scenario) -> int:
    memo: dict[str, int] = {}

    def walk(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        n = s.node(node_id)
        assert n is not None
        here = 1 if n.kind == "choice" else 0
        targets = [o.to for o in n.options] if n.kind == "choice" else ([n.next] if n.next else [])
        memo[node_id] = here + max((walk(t) for t in targets), default=0)
        return memo[node_id]

    return walk(s.start)


def summary(s: Scenario) -> ScenarioSummary:
    return ScenarioSummary(
        id=s.id,
        track=s.track,
        career_title=CATALOG[s.track].title,
        title=s.title,
        role=s.role,
        objective=s.objective,
        minutes=s.minutes,
        scope=s.scope,
        version=s.version,
        regulated=s.regulated,
        validated=False,
        decisions=_longest_decisions(s),
        endings=sum(1 for n in s.nodes if n.kind == "ending"),
        review=ReviewOut(status=s.review.status, by=s.review.by, on=s.review.on, note=s.review.note),
    )


def _refs(s: Scenario) -> list[ReferenceOut]:
    return [
        ReferenceOut(
            title=r.title, publisher=r.publisher, url=r.url, published=r.published, kind=r.kind, note=r.note
        )
        for r in s.references
    ]


def detail(scenario_id: str) -> ScenarioDetail:
    s = _find(scenario_id)
    return ScenarioDetail(**summary(s).model_dump(), references=_refs(s), changes=list(s.changes))


def catalog(track: str) -> ScenarioCatalog:
    if track not in CATALOG:
        raise NotFoundError(f"Career '{track}' not found")
    tracks = sorted({s.track for s in SCENARIO_INDEX.values()})
    covered = [CareerCount(track=t, title=CATALOG[t].title, scenarios=len(scenarios_for(t))) for t in tracks]
    names = " and ".join(f"{c.title} ({c.scenarios})" for c in covered)
    mine = scenarios_for(track)
    note = f"Scenarios are new and few: {names}." + (
        "" if mine else f" {CATALOG[track].title} doesn't have any yet."
    )
    return ScenarioCatalog(
        track=track,
        career_title=CATALOG[track].title,
        scenarios=[summary(s) for s in mine],
        coverage_note=note,
        careers_with_scenarios=covered,
    )


class Scenarios:
    def __init__(self, db: Session):
        self.db = db

    def _attempt(self, user: User, attempt_id: str, *, lock: bool = False) -> ScenarioAttempt:
        q = select(ScenarioAttempt).where(ScenarioAttempt.id == attempt_id)
        if lock:
            q = q.with_for_update()
        a = self.db.scalar(q)
        if a is None or a.user_id != user.id:
            raise NotFoundError("Attempt not found")
        return a

    def start(self, user: User, scenario_id: str, body: StartIn) -> ScenarioAttemptOut:
        s = _find(scenario_id)
        if body.mode == "assessed":
            existing = self.db.scalar(
                select(ScenarioAttempt).where(
                    ScenarioAttempt.user_id == user.id,
                    ScenarioAttempt.scenario_id == s.id,
                    ScenarioAttempt.version == s.version,
                    ScenarioAttempt.mode == "assessed",
                    ScenarioAttempt.status == "in_progress",
                )
            )
            if existing is not None:
                return self.out(existing)  # resume instead of starting a second one
            parent = None
        else:
            if not body.parent_id:
                raise AppError(
                    "Exploring another approach needs the attempt it starts from.", code="parent_required"
                )
            parent = self._attempt(user, body.parent_id)
            if parent.scenario_id != s.id or parent.status != "completed":
                raise ConflictError(
                    "Try another approach after finishing an attempt of this scenario.",
                    code="parent_not_finished",
                )
        a = ScenarioAttempt(
            user_id=user.id,
            scenario_id=s.id,
            version=s.version,
            mode=body.mode,
            parent_id=parent.id if parent else None,
            current_node=s.start,
            steps=[],
        )
        self.db.add(a)
        self.db.commit()
        return self.out(a)

    def step(self, user: User, attempt_id: str, body: StepIn) -> ScenarioAttemptOut:
        a = self._attempt(user, attempt_id, lock=True)
        s = _find(a.scenario_id)
        steps = list(a.steps or [])
        last = steps[-1] if steps else None
        repeat = (
            last is not None
            and last["node_id"] == body.node_id
            and last.get("choice_id") == body.choice_id
            and (last.get("response") or None) == ((body.text or "").strip() or None)
        )
        if repeat:
            return self.out(a)  # the same request again (double click, retry): nothing changes
        if a.status != "in_progress":
            raise ConflictError(
                "This attempt is finished. Start a new one to try again.", code="attempt_finished"
            )
        if a.version != s.version:
            raise ConflictError(
                f"This scenario was updated to version {s.version}. Your attempt is kept as it was; start the new version to continue.",
                code="scenario_updated",
            )
        if body.node_id != a.current_node:
            raise ConflictError(
                "That step isn't the current one. Reload to see where you are.", code="stale_step"
            )
        node = s.node(a.current_node)
        assert node is not None and node.kind != "ending"
        record: dict[str, Any] = {
            "node_id": node.id,
            "kind": node.kind,
            "title": node.title,
            "text": node.text,
            "at": _now().isoformat(),
        }
        if node.kind == "info":
            nxt = node.next
        elif node.kind == "choice":
            option = next((o for o in node.options if o.id == body.choice_id), None)
            if option is None:
                raise AppError("Choose one of the options shown.", code="invalid_choice")
            record |= {
                "choice_id": option.id,
                "choice_label": option.label,
                "quality": option.quality,
                "feedback": option.feedback,
                "alternatives": [
                    {"label": o.label, "quality": o.quality, "rule": o.feedback}
                    for o in node.options
                    if o.id != option.id
                ],
            }
            nxt = option.to
        else:
            text = (body.text or "").strip()
            if len(text) < 10:
                raise AppError("Write at least a sentence.", code="response_too_short")
            covered, missing = check_written(node, text)
            record |= {"response": text, "covered": covered, "missing": missing}
            nxt = node.next
        assert nxt is not None
        steps.append(record)
        a.steps = steps
        a.current_node = nxt
        a.updated_at = _now()
        target = s.node(nxt)
        if target is not None and target.kind == "ending":
            a.status = "completed"
            a.ending = target.id
            a.completed_at = _now()
            a.steps = [
                *steps,
                {
                    "node_id": target.id,
                    "kind": "ending",
                    "title": target.title,
                    "text": target.text,
                    "outcome": target.outcome,
                    "debrief": target.debrief,
                    "at": _now().isoformat(),
                },
            ]
        self.db.commit()
        return self.out(a)

    def get(self, user: User, attempt_id: str) -> ScenarioAttemptOut:
        return self.out(self._attempt(user, attempt_id))

    def attempts(self, user: User, scenario_id: str | None) -> list[ScenarioAttemptSummary]:
        q = select(ScenarioAttempt).where(ScenarioAttempt.user_id == user.id)
        if scenario_id:
            q = q.where(ScenarioAttempt.scenario_id == scenario_id)
        out = []
        for a in self.db.scalars(q.order_by(ScenarioAttempt.created_at.desc())).all():
            s = get_scenario(a.scenario_id)
            end = next((st for st in a.steps or [] if st["kind"] == "ending"), None)
            out.append(
                ScenarioAttemptSummary(
                    id=a.id,
                    scenario_id=a.scenario_id,
                    title=s.title if s else a.scenario_id,
                    version=a.version,
                    mode=a.mode,
                    status=a.status,
                    outcome=end["outcome"] if end else None,
                    retired=s is None or s.version != a.version,
                    created_at=a.created_at,
                    completed_at=a.completed_at,
                )
            )
        return out

    # --- views ---------------------------------------------------------------------------------

    def out(self, a: ScenarioAttempt) -> ScenarioAttemptOut:
        s = _find(a.scenario_id)
        retired = s.version != a.version
        steps = [x for x in a.steps or [] if x["kind"] != "ending"]
        current: NodeView | None = None
        if a.status == "in_progress" and not retired:
            n: Node | None = s.node(a.current_node)
            if n is not None and n.kind != "ending":
                current = NodeView(
                    id=n.id,
                    kind=n.kind,
                    title=n.title,
                    text=n.text,
                    options=[OptionOut(id=o.id, label=o.label) for o in n.options],
                )
        return ScenarioAttemptOut(
            id=a.id,
            scenario=summary(s),
            version=a.version,
            mode=a.mode,
            parent_id=a.parent_id,
            status=a.status,
            retired=retired,
            current=current,
            steps=[
                StepOut(
                    node_id=x["node_id"],
                    kind=x["kind"],
                    title=x["title"],
                    text=x["text"],
                    choice_id=x.get("choice_id"),
                    choice_label=x.get("choice_label"),
                    quality=x.get("quality"),
                    feedback=x.get("feedback"),
                    response=x.get("response"),
                    covered=x.get("covered", []),
                    missing=x.get("missing", []),
                    at=datetime.fromisoformat(x["at"]),
                )
                for x in steps
            ],
            debrief=self._debrief(s, a) if a.status == "completed" else None,
            created_at=a.created_at,
            updated_at=a.updated_at,
            completed_at=a.completed_at,
        )

    def _debrief(self, s: Scenario, a: ScenarioAttempt) -> Debrief:
        steps = a.steps or []
        end = next(x for x in steps if x["kind"] == "ending")
        decisions = [
            DecisionOut(
                step_index=i,
                title=x["title"],
                chosen=x["choice_label"],
                quality=x["quality"],
                rule=x["feedback"],
                alternatives=[Alternative(**alt) for alt in x.get("alternatives", [])],
            )
            for i, x in enumerate(steps)
            if x["kind"] == "choice"
        ]
        written = [
            WrittenOut(
                step_index=i,
                title=x["title"],
                response=x["response"],
                covered=x["covered"],
                missing=x["missing"],
            )
            for i, x in enumerate(steps)
            if x["kind"] == "written"
        ]
        strengths = [f"{d.title}: {d.chosen}. {d.rule}" for d in decisions if d.quality == "strong"]
        strengths += [
            f"{w.title}: you covered {', '.join(c.lower() for c in w.covered)}." for w in written if w.covered
        ]
        return Debrief(
            outcome=end["outcome"],
            ending_title=end["title"],
            ending_text=end["text"],
            summary=end["debrief"],
            path=[x["title"] for x in steps],
            decisions=decisions,
            strengths=strengths,
            written=written,
            references=_refs(s),
            feedback_source=FEEDBACK_SOURCE,
            disclaimer=DISCLAIMER,
        )

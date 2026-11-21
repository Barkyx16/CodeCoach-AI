"""Each skill on its own (Volume 17, prompt 9; docs/PLAN_UPDATES.md, "What each skill's evidence would
move"): a plan update's preview asks the planner once more per skill with new evidence, without that
skill's new evidence, and compares with the plan with all of it; that difference is the skill's line.
A problem counts for each of its topics; what no single skill moves but all of it together does is
said once; past the bound the remaining skills are said together, with how many; a skill whose own
evidence moves nothing says so. The facts are read once, so the statements don't grow with the number
of skills, and the plan an update applies is the one it applied before. Synthetic data only."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.careers.skills import questions_by_skill
from app.models import SubmissionStatus, User
from app.services import roadmap
from app.services.disputes import Disputes
from tests.test_disputes import WEAK
from tests.test_plan_code_evidence import TRACK, accept, coder, judged, plan, two_sum_unfinished
from tests.test_query_budgets import measure
from tests.test_roadmap import answer

VP_MOVES = (
    "didn't pass (compile error), which counts as tried, not solved, so the next version would suggest "
    "“Solve: Valid Parentheses” and not “Solve: First Unique Character”."
)


def two_problems(client, h):
    """Contains Duplicate passed (arrays, hash sets) and Valid Parentheses failed to compile (strings,
    stacks) since a plan that suggested finishing Two Sum: four skills with new evidence."""
    two_sum_unfinished(client, h)
    judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    judged(client, h, "valid-parentheses", SubmissionStatus.COMPILE_ERROR)


def many_skills(client, h):
    """Weak answers on eight skills and three problems passed (six topics) since the plan: 14 skills."""
    two_sum_unfinished(client, h)
    by = questions_by_skill(TRACK)
    for skill in sorted(by)[:8]:
        answer(client, h, TRACK, sorted(by[skill])[0], WEAK)
    for slug in ("contains-duplicate", "valid-parentheses", "climbing-stairs"):
        judged(client, h, slug, SubmissionStatus.PASSED)


@pytest.fixture
def plans_made(monkeypatch):
    """How many plans the planner is asked for, per request."""
    made = {"n": 0}
    real = roadmap.Roadmap._generate

    def counted(self, *args, **kwargs):
        made["n"] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(roadmap.Roadmap, "_generate", counted)
    return made


def lines(news):
    return [(g["skill"], g["text"]) for g in news["by_skill"]]


def test_a_two_topic_problem_moves_both_topics_lines(client):
    h = coder(client)
    two_sum_unfinished(client, h)
    judged(client, h, "contains-duplicate", SubmissionStatus.PASSED)
    moves = (
        "“Contains Duplicate” passed, which counts as solved, so the next version would suggest "
        "“Solve: First Unique Character” and not “Solve: Find Largest Number”."
    )
    assert lines(plan(client, h)["news"]) == [
        ("arrays", f"Arrays: {moves}"),
        ("hash-sets", f"Hash-sets: {moves}"),
    ]


def test_what_only_skills_together_move_is_said_once_together(client):
    h = coder(client)
    two_problems(client, h)
    news = plan(client, h)["news"]
    # Without Contains Duplicate alone, Valid Parentheses still takes Find Largest Number's place; without
    # Valid Parentheses alone, Contains Duplicate does. Only without both does it come back: said once.
    nothing = "“Contains Duplicate” passed, which counts as solved; on its own that changes nothing the plan chooses."
    assert lines(news) == [
        ("arrays", f"Arrays: {nothing}"),
        ("hash-sets", f"Hash-sets: {nothing}"),
        ("strings", f"Strings: “Valid Parentheses” {VP_MOVES}"),
        ("stacks", f"Stacks: “Valid Parentheses” {VP_MOVES}"),
        (
            None,
            "From all of it together, the next version also wouldn't suggest “Solve: Find Largest Number”.",
        ),
    ]
    assert news["by_skill"][-1]["count"] == 2  # two submissions, each counted once
    assert sum("Find Largest Number" in text for _, text in lines(news)) == 1


def test_past_the_bound_the_rest_are_said_together_with_how_many(client, monkeypatch, plans_made):
    h = coder(client)
    two_problems(client, h)
    monkeypatch.setattr(roadmap, "SKILLS_ASKED_ALONE", 2)
    plans_made["n"] = 0
    news = plan(client, h)["news"]
    assert plans_made["n"] == 2 + 2 + 1  # with and without all of it, two skills alone, the rest
    rest = news["by_skill"][2]
    assert (rest["skill"], rest["skills"], rest["count"]) == (None, ["strings", "stacks"], 1)
    assert rest["text"] == f"The other 2 skills together (strings and stacks): “Valid Parentheses” {VP_MOVES}"
    assert [g["skill"] for g in news["by_skill"]] == ["arrays", "hash-sets", None, None]
    # One more than the bound is asked about alone: the rest together would be that one skill.
    monkeypatch.setattr(roadmap, "SKILLS_ASKED_ALONE", 3)
    assert [g["skill"] for g in plan(client, h)["news"]["by_skill"]] == [
        "arrays",
        "hash-sets",
        "strings",
        "stacks",
        None,
    ]


def test_the_bound_is_the_plans_limit_on_items(client, plans_made):
    h = coder(client)
    many_skills(client, h)
    plans_made["n"] = 0
    news = plan(client, h)["news"]
    assert roadmap.SKILLS_ASKED_ALONE == roadmap.MAX_ITEMS == 8
    assert plans_made["n"] == 8 + 3
    alone = [g for g in news["by_skill"] if g["skill"] is not None]
    rest = next(g for g in news["by_skill"] if g["skills"])
    assert len(alone) == 8 and len(rest["skills"]) == 14 - 8
    assert rest["text"].startswith(f"The other 6 skills together ({roadmap._and(rest['skills'])}): ")
    assert all(g["text"].count(".") == 1 for g in news["by_skill"])  # one sentence each


def test_the_statements_dont_grow_with_the_number_of_skills_asked(client, monkeypatch, plans_made):
    h = coder(client)
    many_skills(client, h)
    counts = {}
    for bound in (1, 8):
        monkeypatch.setattr(roadmap, "SKILLS_ASKED_ALONE", bound)
        plans_made["n"] = 0
        counts[bound] = len(measure(client, h, "GET", "/api/v1/me/plan"))
        assert plans_made["n"] == 2 * (bound + 3)  # measure() asks twice: the first view, then measured
    assert counts[1] == counts[8], counts


def test_the_plan_an_update_applies_is_the_one_it_applied_before(client):
    h = coder(client)
    two_problems(client, h)
    titles = [i["title"] for i in accept(client, h, 1)["items"]]
    assert "Solve: Valid Parentheses" in titles
    assert "Solve: First Unique Character" not in titles and "Solve: Find Largest Number" not in titles


def test_the_preview_chooses_as_the_full_plan_without_reading_feedback(client):
    """The preview's plans don't read a weak answer's feedback: it words an item and never chooses one."""
    h = coder(client)
    by = questions_by_skill(TRACK)
    for skill in sorted(by)[:4]:
        answer(client, h, TRACK, sorted(by[skill])[0], WEAK)
    me = client.get("/api/v1/auth/me", headers=h).json()["id"]
    with client.app.state.session_factory() as db:
        user = db.get(User, me)
        planner = roadmap.Roadmap(db, judge_enabled=False)
        disputes = Disputes(db, user.id).active(TRACK)
        ev = planner._evidence(user, TRACK, disputes)
        goal, avoid = planner._goal(user, TRACK), planner._avoid(user, TRACK)
        full = planner._generate(user, TRACK, goal, ev, avoid)
        choosing = planner._generate(user, TRACK, goal, replace(ev, withheld=[], choosing_only=True), avoid)
    assert any(s.kind == "retry" for s in full)
    assert [s.key for s in choosing] == [s.key for s in full]

"""A reviewed lesson that prepares the debugging exercises (Volume 17, prompt 5;
docs/ATTEMPT_CONDITIONS.md, docs/LEARN.md): "Fixing code from a failing test" prepares the three
exercises through `debug:<slug>` links that the content gate checks (a link to an exercise that
doesn't exist is refused); an exercise's page offers it under "Learn first"; reading it before an
attempt is help for the first attempt after the read, by the rule every format uses, and not for one
made before the read or for the attempt after that; another account's read never counts. Synthetic
data only."""

from __future__ import annotations

import dataclasses

from app.content import validate as gate
from app.learn import UNIT_INDEX
from tests.test_debug_interview_conditions import LAB, attempt, coder, page
from tests.test_practice_conditions import read

UNIT = "se-failing-test"


def lesson_help(conditions) -> list[dict]:
    return [h for h in conditions["help"] if "Fixing code from a failing test" in h["detail"]]


def test_the_lesson_is_reviewed_prepares_every_exercise_and_is_offered_on_each(client):
    u = UNIT_INDEX[UNIT]
    assert u.review.status == "author_reviewed" and u.review.by and u.version == 1
    assert set(u.prepares) == {
        "debug:debug-coldest-day",
        "debug:debug-count-at-most",
        "debug:debug-palindrome-sentence",
    }
    for slug in ("debug-coldest-day", "debug-count-at-most", "debug-palindrome-sentence"):
        related = client.get("/api/v1/learn/related", params={"problem_slug": slug}).json()
        assert {"id": UNIT, "title": u.title} in related
    # An ordinary problem isn't offered it.
    assert UNIT not in {
        x["id"] for x in client.get("/api/v1/learn/related", params={"problem_slug": "two-sum"}).json()
    }


def test_the_content_gate_refuses_a_link_to_an_exercise_that_doesnt_exist(monkeypatch):
    clean = gate.Report()
    gate._learn(clean, set(), set())
    assert not [e for e in clean.errors if "prepares" in e]
    broken = dataclasses.replace(UNIT_INDEX[UNIT], prepares=("debug:no-such-exercise",))
    monkeypatch.setitem(gate.UNIT_INDEX, UNIT, broken)
    report = gate.Report()
    gate._learn(report, set(), set())
    assert f"lesson {UNIT}: it prepares 'debug:no-such-exercise', which doesn't exist" in report.errors


def test_read_before_an_attempt_it_is_help_for_that_attempt_only(client):
    h = coder(client)
    first = attempt(client, h)  # before reading: none
    assert lesson_help(page(client, h, first)) == []
    read(client, h, UNIT, minutes_ago=0)
    second = attempt(client, h)
    [shown] = lesson_help(page(client, h, second))
    assert shown["label"] == "Hint shown"
    third = attempt(client, h)  # the read belongs to the attempt after it, once
    assert lesson_help(page(client, h, third)) == []
    assert lesson_help(page(client, h, first)) == []


def test_another_accounts_read_never_counts(client):
    theirs = coder(client, email="other@example.com")
    read(client, theirs, UNIT, minutes_ago=0)
    h = coder(client)
    sub = attempt(client, h, LAB)
    assert lesson_help(page(client, h, sub)) == []


def test_the_lesson_gives_away_none_of_the_exercises_answers():
    """Each exercise's recorded defect (its own explanation's key) isn't in the lesson's words."""
    u = UNIT_INDEX[UNIT]
    text = " ".join(
        [
            *u.explanation,
            u.example.intro,
            *u.example.walkthrough,
            *u.mistakes,
            u.exercise.prompt,
            u.exercise.think,
            u.exercise.concept,
            u.exercise.example,
            u.exercise.explanation,
            u.exercise.solution,
            *(q.prompt for q in u.check),
            *(o for q in u.check for o in q.options),
            *(q.explanation for q in u.check),
        ]
    ).lower()
    for giveaway in (
        "nums.length - 1",  # Count Within a Limit: the loop bound
        "last element",
        "last index",
        "starts at 0",  # Coldest Reading: the running minimum's start
        "minimum",
        "isletter",  # Palindrome Sentence: digits skipped, case compared
        "case-insensitive",
        "ignore case",
    ):
        assert giveaway not in text, giveaway

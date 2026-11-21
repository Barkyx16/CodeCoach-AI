"""A hint asked for after "I've checked this" (Volume 18, prompt 3; docs/COACH_CONTEXT.md, "Hints
inside the interview"): how the interview ends is compared apart, but a hint asked for after the check
is something the feedback reads that wasn't checked, so the review names it among what changed after
("Hints: level 2 (concept) asked for after your check"), and the check no longer reads as matched. A hint
asked for before the check changes nothing, and nor does none. Synthetic data only."""

from __future__ import annotations

from app.models import PracticeSession
from app.services.interviews import hints_after
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import say
from tests.test_feedback_check import checked
from tests.test_feedback_read import expire, get
from tests.test_interview_hints import hint, setup


def timed_out(client, h, iv):
    expire(client, iv["id"])
    return get(client, h, iv["id"])["feedback_read"]


def test_a_hint_after_the_check_is_named_among_what_changed(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    checked(client, h, iv)
    assert hint(client, h, iv, 1).status_code == 200
    read = timed_out(client, h, iv)
    confirmed = read["confirmed"]
    assert confirmed["matched"] is False and "Hints" in confirmed["changed"]
    [change] = [c for c in confirmed["changes"] if c["label"] == "Hints"]
    assert change["hints_after"] == ["level 1 (nudge)"]
    assert change["text"] == "Hints: level 1 (nudge) asked for after your check"
    assert read["text"].startswith("You checked an earlier version before time ran out; it changed after: ")
    assert read["text"].rstrip(".").endswith("Hints")


def test_two_hints_after_the_check_are_both_named_in_order(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    checked(client, h, iv)
    assert hint(client, h, iv, 1).status_code == 200
    assert hint(client, h, iv, 2).status_code == 200
    [change] = [c for c in timed_out(client, h, iv)["confirmed"]["changes"] if c["label"] == "Hints"]
    assert change["text"] == "Hints: level 1 (nudge) and level 2 (concept) asked for after your check"


def test_a_hint_before_the_check_changes_nothing(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    assert hint(client, h, iv, 1).status_code == 200
    checked(client, h, iv)
    read = timed_out(client, h, iv)
    assert read["confirmed"]["matched"] is True and read["confirmed"]["changes"] == []
    assert read["text"] == "You checked this before time ran out."


def test_only_the_hints_after_are_named(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    assert hint(client, h, iv, 1).status_code == 200
    checked(client, h, iv)
    assert hint(client, h, iv, 2).status_code == 200
    [change] = [c for c in timed_out(client, h, iv)["confirmed"]["changes"] if c["label"] == "Hints"]
    assert change["hints_after"] == ["level 2 (concept)"]


def test_no_check_time_no_hints_named():
    s = PracticeSession(
        plan={"hints": [{"level": 1, "level_name": "nudge", "at": "2026-11-16T08:00:00+00:00"}]}
    )
    assert hints_after(s, None) == []
    assert hints_after(s, "2026-11-16T07:59:59+00:00") == ["level 1 (nudge)"]
    assert hints_after(s, "2026-11-16T08:00:00+00:00") == []  # at the same moment: not after

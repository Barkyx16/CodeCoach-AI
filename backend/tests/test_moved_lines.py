"""Lines moved after a check are one change, not a removal and an addition (Volume 19, prompt 8;
docs/COACH_CONTEXT.md, "What changed, shown"). Lines are matched in order over their digests, then
each removed line is paired with an added line of the same digest, one copy for one copy: a pair is a
line moved. A line moved and edited has a new digest, so it stays one removed and one added; blank
lines follow the same rule. "Your code: 2 lines moved, 1 line added"; with nothing moved the words
read exactly as before, and a change recorded before moves were counted reads as it did. Only
digests are kept with the check; no line's text. Synthetic code only."""

from __future__ import annotations

import pytest

from app.schemas.interview import CheckChange
from app.services.interviews import change_text, line_moves
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import say
from tests.test_feedback_check import checked
from tests.test_feedback_read import expire, get
from tests.test_interview_time_runs_out import coding, sweep

# Each letter stands for one line's digest. Worked by hand: how difflib lines them up in order, then
# which removed copies pair with which added ones. Numbers are 1-based, in the code after.
TABLE = [
    # before, after, added lines, removed count, moved lines
    ("abcde", "acdbe", [], 0, [4]),  # b moved down: one line moved
    ("abcdef", "adefbc", [], 0, [5, 6]),  # the block b c moved below d e f
    ("xab", "abxx", [4], 0, [3]),  # one x removed, two added: one moved, one added
    ("axbx", "xabx", [], 0, [1]),  # a repeated line: the one copy that moved, once
    ("abcd", "acdB", [4], 1, []),  # b moved and edited (now B): one removed, one added
    ("abc", "abcd", [4], 0, []),  # nothing moved: as before
    ("abcd", "ad", [], 2, []),  # nothing moved: as before
    ("_ab", "ab_", [], 0, [3]),  # a blank line (_) moved: the same rule
    ("abcabc", "bcabca", [], 0, [6]),  # a moved, the rest in order
]


@pytest.mark.parametrize(("before", "after", "added", "removed", "moved"), TABLE)
def test_the_counts_match_the_hand_worked_table(before, after, added, removed, moved):
    assert line_moves(list(before), list(after)) == (added, removed, moved)


def test_a_repeated_line_pairs_once_per_copy():
    # Two copies of x removed from the top, one added at the end: one move and one removed, never
    # two moves for the one copy added.
    assert line_moves(list("xxab"), list("abx")) == ([], 1, [3])
    # Lines in order are matched first: here the first x stays, so y and z are what moved ahead of it,
    # and the second x is removed.
    assert line_moves(list("xyxz"), list("yzx")) == ([], 1, [1, 2])


def test_the_words_say_moved_and_with_nothing_moved_read_exactly_as_before():
    assert change_text({"label": "Your code", "added": 1, "removed": 0, "moved": 2}) == (
        "Your code: 2 lines moved, 1 line added"
    )
    assert change_text({"label": "Your code", "added": 0, "removed": 1, "moved": 1}) == (
        "Your code: 1 line moved, 1 line removed"
    )
    assert change_text({"label": "Your code", "added": 4, "removed": 3, "moved": 0}) == (
        "Your code: 4 lines added, 3 lines removed"
    )


def test_a_change_recorded_before_this_reads_as_it_did():
    old = {"label": "Your code", "added": 4, "removed": 3, "added_lines": [4, 5, 6, 7]}
    assert change_text(old) == "Your code: 4 lines added, 3 lines removed"
    shown = CheckChange(**old, text=change_text(old))
    assert (shown.moved, shown.moved_lines) == (None, [])


def test_an_interview_scored_after_a_check_says_a_moved_line_is_moved(client):
    h, iv = coding(client)
    say(client, h, iv, code=CODE)
    checked(client, h, iv)
    lines = CODE.split("\n")
    # One line moved two places down, nothing else changed.
    moved = lines[:2] + lines[3:5] + [lines[2]] + lines[5:]
    assert say(client, h, iv, message="Reordered one line.", code="\n".join(moved)).status_code == 200
    expire(client, iv["id"])
    assert sweep(client) == 1
    read = get(client, h, iv["id"])["feedback_read"]
    change = next(c for c in read["confirmed"]["changes"] if c["label"] == "Your code")
    assert (change["moved"], change["added"], change["removed"]) == (1, 0, 0)
    assert change["text"] == "Your code: 1 line moved"
    assert [moved[n - 1] for n in change["moved_lines"]] == [lines[2]]  # its new place, by number
    assert change["added_lines"] == []

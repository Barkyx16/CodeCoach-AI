"""The explanation shown with a reading's own result counts as seen (Volume 20, prompt 3;
docs/ATTEMPT_CONDITIONS.md, "Sample-answer readings"). A reading's result shows the lesson's
explanation, so it's recorded then, at that reading's time, in the one record openings use (its
`source` is "with_result"), unless it was opened or shown at that version before: that earlier time
stands. The next reading says the explanation was seen before it was sent, with that time, and how.
The first reading's own help is unchanged. A new version starts again. Readings from before this
read as they did. Another account's never count. The opening route, the export and the reading's
list say the same. Synthetic accounts only."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from sqlalchemy import select

from app.comparisons import BY_ID
from app.models import ComparisonAttempt, ComparisonOpening, User
from app.services.comparisons import Comparisons
from app.services.conditions import OPENED, SHOWN_WITH_RESULT
from tests.conftest import auth_headers, register
from tests.test_comparison_openings import help_of, open_it, read, when
from tests.test_comparisons import MINE, SPECIFIC

NONE = ["No in-app help recorded"]


def rows(client) -> list[ComparisonOpening]:
    with client.app.state.session_factory() as db:
        out = list(db.scalars(select(ComparisonOpening).order_by(ComparisonOpening.created_at)))
        db.expunge_all()
        return out


def test_a_second_reading_after_a_first_ones_result_says_it_was_seen_then(client):
    h = auth_headers(register(client))
    first = read(client, h)
    assert first["conditions"]["labels"] == NONE  # its own help: the explanation came after it
    assert first["explanation"]  # its result shows the explanation
    [shown] = rows(client)
    assert (shown.source, shown.lesson_version) == ("with_result", 1)
    assert shown.created_at.replace(tzinfo=UTC) == when(first["created_at"])
    second = read(client, h)
    assert help_of(second) == [("Solution revealed", SHOWN_WITH_RESULT, when(first["created_at"]))]
    third = read(client, h)  # the first showing stands
    assert help_of(third) == help_of(second)
    assert len(rows(client)) == 1
    # And the first reading still reads as it did.
    again = client.get(f"{MINE}/attempts/{first['id']}", headers=h).json()
    assert again["conditions"]["labels"] == NONE


def test_an_opening_before_both_keeps_its_earlier_time_and_words(client):
    h = auth_headers(register(client))
    opened = open_it(client, h, "open-key-0001")
    assert opened["source"] == "opened"
    first = read(client, h)
    second = read(client, h)
    for r in (first, second):
        assert help_of(r) == [("Solution revealed", OPENED, when(opened["opened_at"]))]
    [only] = rows(client)
    assert only.source == "opened"


def test_the_opening_route_after_a_showing_names_it_and_moves_nothing(client):
    h = auth_headers(register(client))
    first = read(client, h)
    later = open_it(client, h, "open-key-0002")
    assert (later["source"], when(later["opened_at"])) == ("with_result", when(first["created_at"]))
    assert len(rows(client)) == 1


def test_a_new_version_starts_again(client, monkeypatch):
    h = auth_headers(register(client))
    read(client, h)
    monkeypatch.setitem(BY_ID, SPECIFIC, dataclasses.replace(BY_ID[SPECIFIC], version=2))
    v2_first = read(client, h)
    assert v2_first["conditions"]["labels"] == NONE  # version 1's showing doesn't count for 2
    v2_second = read(client, h)
    assert help_of(v2_second) == [("Solution revealed", SHOWN_WITH_RESULT, when(v2_first["created_at"]))]
    assert sorted((r.lesson_version, r.source) for r in rows(client)) == [
        (1, "with_result"),
        (2, "with_result"),
    ]


def test_readings_from_before_this_read_as_they_did(client):
    h = auth_headers(register(client))
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == "ada@example.com"))
        snapshot = BY_ID[SPECIFIC].snapshot()
        for day in (10, 11):  # two readings sent before this change: nothing recorded with them
            db.add(
                ComparisonAttempt(
                    user_id=uid,
                    lesson_id=SPECIFIC,
                    lesson_version=1,
                    snapshot=snapshot,
                    selections=[],
                    choice=None,
                    feedback={"counts": {"matches": 0}},
                    revealed_early=False,
                    created_at=datetime(2026, 11, day, 9, 0, tzinfo=UTC),
                )
            )
        db.commit()
    listed = client.get(f"{MINE}/{SPECIFIC}/attempts", headers=h).json()
    # As they read before this: from before help was recorded at all, so "Not recorded"; the second
    # isn't said to follow the first's result. Nothing is inferred.
    assert [r["conditions"]["labels"] for r in listed] == [["Not recorded"], ["Not recorded"]]
    assert rows(client) == []


def test_another_accounts_readings_never_count(client):
    bea = auth_headers(register(client, email="bea@example.com"))
    read(client, bea)
    h = auth_headers(register(client))
    assert read(client, h)["conditions"]["labels"] == NONE
    # A reading on a third account with no showing of its own before it: Bea's never stands in.
    other = auth_headers(register(client, email="cy@example.com"))
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == "cy@example.com"))
        db.add(
            ComparisonAttempt(
                user_id=uid,
                lesson_id=SPECIFIC,
                lesson_version=1,
                snapshot=BY_ID[SPECIFIC].snapshot(),
                selections=[],
                choice=None,
                feedback={"counts": {"matches": 0}},
                revealed_early=False,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    [only] = client.get(f"{MINE}/{SPECIFIC}/attempts", headers=other).json()
    assert only["conditions"]["labels"] == NONE


def test_the_reading_list_and_the_export_say_the_same(client):
    h = auth_headers(register(client))
    first = read(client, h)
    second = read(client, h)
    listed = {r["id"]: r for r in client.get(f"{MINE}/{SPECIFIC}/attempts", headers=h).json()}
    assert listed[second["id"]]["conditions"] == second["conditions"]
    doc = client.get("/api/v1/me/export", headers=h).json()
    assert [(o["lesson"], o["lesson_version"], o["source"]) for o in doc["comparison_openings"]] == [
        (SPECIFIC, 1, "with_result")
    ]
    assert when(doc["comparison_openings"][0]["at"]) == when(first["created_at"])


def test_another_tab_recording_it_first_leaves_that_one_and_keeps_the_reading(client, monkeypatch):
    """Two readings at the same moment: the second finds no record when it looks, then meets the first's
    at the unique key. Its reading is kept; the first's time stands."""
    h = auth_headers(register(client))
    first = read(client, h)
    real = Comparisons._shown_with_result

    def blind(self, ls, at):  # as if it looked before the other tab's record was there
        scalar = self._db.scalar
        self._db.scalar = lambda *a, **k: None
        try:
            return real(self, ls, at)
        finally:
            self._db.scalar = scalar

    monkeypatch.setattr(Comparisons, "_shown_with_result", blind)
    second = read(client, h)
    assert second["id"] != first["id"]
    [only] = rows(client)
    assert only.created_at.replace(tzinfo=UTC) == when(first["created_at"])

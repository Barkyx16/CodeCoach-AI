"""When a sample-answer lesson's explanation was opened (Volume 19, prompt 5; docs/ATTEMPT_CONDITIONS.md,
"Sample-answer readings"): opening it signed in is recorded on the account, once per lesson version,
with a request key; a reading sent after it at that version says "Solution revealed" with the
opening's time, not its own. A reading the page said came after opening it, with nothing recorded,
says so with its own time and says whose time that is; readings from before recording began keep
their words exactly. Another version, or another account's opening, never counts. The reading, its
list, the bulk route History uses and the export say the same; the bulk route stays one read
however many readings. Signed out, the explanation stays public and nothing is recorded. Synthetic
accounts only."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from sqlalchemy import func, select, update

from app.comparisons import BY_ID
from app.models import ComparisonAttempt, ComparisonOpening
from tests.conftest import auth_headers, register
from tests.test_comparisons import MINE, SPECIFIC, pick, send

CONDITIONS = "/api/v1/me/attempt-conditions"
OPENED = "The explanation was opened before this was sent"
UNRECORDED = f"{OPENED} (opening it wasn't recorded on your account, so the time here is this reading's)"
MARK = [pick("B", "b4", "strength", "A result that can be checked.")]


def when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def open_it(client, h, key: str | None = None) -> dict:
    r = client.post(f"{MINE}/{SPECIFIC}/explanation", json={"client_request_id": key}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def read(client, h, early=False) -> dict:
    r = send(client, h, SPECIFIC, MARK, early=early)
    assert r.status_code == 201, r.text
    return r.json()


def openings(client) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(ComparisonOpening))


def help_of(reading: dict) -> list[tuple[str, str, datetime]]:
    return [(h["label"], h["detail"], when(h["at"])) for h in reading["conditions"]["help"]]


def test_an_opening_is_recorded_once_per_version_and_signed_out_not_at_all(client):
    assert client.get(f"/api/v1/comparisons/{SPECIFIC}/explanation").status_code == 200  # still public
    assert openings(client) == 0
    assert client.post(f"{MINE}/{SPECIFIC}/explanation", json={}).status_code == 401
    h = auth_headers(register(client))
    first = open_it(client, h, "open-key-0001")
    assert first["explanation"] == BY_ID[SPECIFIC].explanation and first["lesson_version"] == 1
    again = open_it(client, h, "open-key-0002")  # opening it again doesn't move the time
    assert again["opened_at"] == first["opened_at"] and openings(client) == 1
    assert open_it(client, h)["opened_at"] == first["opened_at"]  # nor does one without a key


def test_a_reading_after_the_opening_carries_the_openings_time(client):
    h = auth_headers(register(client))
    opened = when(open_it(client, h, "open-key-0001")["opened_at"])
    early = read(client, h, early=True)
    assert help_of(early) == [("Solution revealed", OPENED, opened)]
    assert when(early["created_at"]) > opened  # and that isn't the reading's own time
    # It can't be unread: a later reading at this version says so too, whatever the page reported.
    later = read(client, h, early=False)
    assert help_of(later) == [("Solution revealed", OPENED, opened)]


def test_a_reading_without_a_recorded_opening_reads_as_before_or_says_whose_time_it_is(client):
    h = auth_headers(register(client))
    plain = read(client, h)
    assert plain["conditions"]["labels"] == ["No in-app help recorded"]
    early = read(client, h, early=True)
    assert help_of(early) == [("Solution revealed", UNRECORDED, when(early["created_at"]))]
    # A reading from before recording began keeps its words exactly.
    with client.app.state.session_factory() as db:
        db.execute(
            update(ComparisonAttempt)
            .where(ComparisonAttempt.id == early["id"])
            .values(created_at=datetime(2026, 11, 10, 9, 0, tzinfo=UTC))
        )
        db.commit()
    old = client.get(f"{MINE}/attempts/{early['id']}", headers=h).json()
    assert help_of(old) == [("Solution revealed", OPENED, datetime(2026, 11, 10, 9, 0, tzinfo=UTC))]
    # An opening after a reading doesn't reach back to it.
    open_it(client, h)
    again = client.get(f"{MINE}/attempts/{plain['id']}", headers=h).json()
    assert again["conditions"]["labels"] == ["No in-app help recorded"]


def test_another_version_is_a_new_first_opening_and_never_counts_for_this_one(client, monkeypatch):
    h = auth_headers(register(client))
    first = open_it(client, h, "open-key-0001")
    with client.app.state.session_factory() as db:  # as if it were opened at another version
        db.execute(update(ComparisonOpening).values(lesson_version=0))
        db.commit()
    reading = read(client, h)
    assert reading["conditions"]["labels"] == ["No in-app help recorded"]
    # The lesson's next version: opening it is a new first opening, at its own time.
    monkeypatch.setitem(BY_ID, SPECIFIC, dataclasses.replace(BY_ID[SPECIFIC], version=2))
    second = open_it(client, h, "open-key-0002")
    assert second["lesson_version"] == 2 and when(second["opened_at"]) > when(first["opened_at"])
    assert openings(client) == 2


def test_a_lost_reply_sent_again_with_its_key_is_the_same_opening(client, monkeypatch):
    h = auth_headers(register(client))
    first = open_it(client, h, "open-key-0001")
    monkeypatch.setitem(BY_ID, SPECIFIC, dataclasses.replace(BY_ID[SPECIFIC], version=2))
    resent = open_it(client, h, "open-key-0001")  # its reply was lost; the lesson changed meanwhile
    assert (resent["opened_at"], resent["lesson_version"]) == (first["opened_at"], 1)
    assert openings(client) == 1


def test_another_accounts_opening_never_counts(client):
    open_it(client, auth_headers(register(client, email="bea@example.com")), "open-key-0001")
    h = auth_headers(register(client))
    assert read(client, h)["conditions"]["labels"] == ["No in-app help recorded"]
    early = read(client, h, early=True)
    assert help_of(early) == [("Solution revealed", UNRECORDED, when(early["created_at"]))]


def test_the_reading_its_list_the_bulk_route_and_the_export_say_the_same(client):
    h = auth_headers(register(client))
    opened = open_it(client, h, "open-key-0001")
    reading = read(client, h, early=True)
    listed = {r["id"]: r for r in client.get(f"{MINE}/{SPECIFIC}/attempts", headers=h).json()}
    bulk = client.post(CONDITIONS, headers=h, json={"comparison_attempt_ids": [reading["id"]]}).json()
    doc = client.get("/api/v1/me/export", headers=h).json()
    [exported] = [a for a in doc["comparisons"] if a["id"] == reading["id"]]
    page = client.get(f"{MINE}/attempts/{reading['id']}", headers=h).json()
    assert (
        page["conditions"]
        == listed[reading["id"]]["conditions"]
        == bulk["comparison_attempts"][reading["id"]]
        == exported["conditions"]
    )
    [o] = doc["comparison_openings"]
    assert (o["lesson"], o["lesson_version"]) == (SPECIFIC, 1)
    assert when(o["at"]) == when(opened["opened_at"])


def test_the_bulk_route_reads_the_openings_once_however_many_readings(client):
    from tests.test_query_budgets import statements

    h = auth_headers(register(client))
    open_it(client, h)
    ids = [read(client, h, early=True)["id"]]
    with statements(client) as seen:
        client.post(CONDITIONS, headers=h, json={"comparison_attempt_ids": ids})
    few = len(seen)
    ids += [read(client, h)["id"] for _ in range(4)]
    with statements(client) as seen:
        client.post(CONDITIONS, headers=h, json={"comparison_attempt_ids": ids})
    assert len(seen) == few, (few, len(seen))

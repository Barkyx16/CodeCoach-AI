"""Drills, whiteboard designs and work samples in History (Volume 16, prompt 6;
docs/COMPARING_ATTEMPTS.md): each attempt is a row with its date, format, what was practised, its
result and its comparison with the one before in the words its own page uses ("not compared: …"
too), linking to the attempt; History's filters include them and its facet counts agree; rows sort
and page with every other kind by when they were made; reading History stays bounded with long
histories; another account's attempts never appear; the rows already there read exactly as before.
Synthetic data only."""

from __future__ import annotations

import pytest
from sqlalchemy import event

from tests.test_checklist_comparisons import FORMATS, LIST, attempt
from tests.test_practice_conditions import nurse

TYPE = {"drill": "drill_attempt", "whiteboard": "whiteboard_attempt", "work_sample": "work_sample_attempt"}
HREF = {"drill": "/drills/example", "whiteboard": "/whiteboard/sd-url-shortener"}
ACTIVITY = "/api/v1/me/activity"


def feed(client, h, **params):
    r = client.get(ACTIVITY, headers=h, params={"page": 1, "page_size": 20, **params})
    assert r.status_code == 200, r.text
    return r.json()


def own_page(client, h, kind):
    r = client.get(LIST[kind], headers=h)
    assert r.status_code == 200, r.text
    return {a["id"]: a for a in r.json()}


@pytest.mark.parametrize("kind", FORMATS)
def test_an_attempt_twice_shows_two_rows_the_second_with_its_outcome_as_its_page_says(client, kind):
    h = nurse(client)
    first, second = attempt(client, h, kind), attempt(client, h, kind)
    rows = [i for i in feed(client, h)["items"] if i["type"] == TYPE[kind]]
    assert [r["target"]["attempt_id"] for r in rows] == [second["id"], first["id"]]  # newest first
    page = own_page(client, h, kind)
    newer, older = rows
    assert newer["detail"].endswith("Comparable with the one before")
    assert page[second["id"]]["compared"]["comparison"]["outcome"] == "comparable"
    # The first says why it isn't compared, in the same words as its page, never a blank.
    assert older["detail"].endswith(page[first["id"]]["not_compared"])
    assert page[first["id"]]["not_compared"].startswith("Not compared: the first checked attempt at this")
    assert newer["status"] == "completed" and newer["title"]
    if kind in HREF:
        assert newer["target"]["href"] == HREF[kind]


def test_filtering_by_format_shows_only_that_format_and_the_facets_agree(client):
    h = nurse(client)
    attempt(client, h, "drill")
    attempt(client, h, "drill")
    attempt(client, h, "whiteboard")
    attempt(client, h, "work_sample")
    only = feed(client, h, type="drill_attempt")
    assert only["total"] == 2 and {i["type"] for i in only["items"]} == {"drill_attempt"}
    facets = client.get(f"{ACTIVITY}/facets", headers=h).json()
    counts = {t["value"]: t["count"] for t in facets["types"]}
    assert (counts["drill_attempt"], counts["whiteboard_attempt"], counts["work_sample_attempt"]) == (2, 1, 1)
    assert feed(client, h)["total"] == sum(counts.values())
    # A coding-only filter, a skill or another status leaves them out.
    assert not [i for i in feed(client, h, career="coding")["items"] if i["type"].endswith("_attempt")]
    assert feed(client, h, type="drill_attempt", status="passed")["total"] == 0


def test_rows_sort_and_page_with_every_other_kind(client):
    h = nurse(client)
    for _ in range(3):
        attempt(client, h, "drill")
    pages = [feed(client, h, page=p, page_size=2) for p in (1, 2)]
    ids = [i["id"] for p in pages for i in p["items"]]
    assert len(ids) == len(set(ids)) == pages[0]["total"]  # nothing split or repeated across pages
    times = [i["occurred_at"] for p in pages for i in p["items"]]
    assert times == sorted(times, reverse=True)


def test_reading_history_doesnt_grow_with_the_number_of_attempts(client):
    h = nurse(client)
    attempt(client, h, "drill")
    attempt(client, h, "whiteboard")
    seen: list[str] = []
    engine = client.app.state.engine

    def record(_c, _cur, statement, *_a):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    feed(client, h)
    one = len(seen)
    event.remove(engine, "before_cursor_execute", record)
    for _ in range(6):
        attempt(client, h, "drill")
        attempt(client, h, "whiteboard")
    seen.clear()
    event.listen(engine, "before_cursor_execute", record)
    feed(client, h)
    event.remove(engine, "before_cursor_execute", record)
    assert len(seen) == one, (one, len(seen))


def test_another_accounts_attempts_never_appear(client):
    a = nurse(client)
    attempt(client, a, "drill")
    b = nurse(client, "bea@example.com")
    assert not [i for i in feed(client, b)["items"] if i["type"].endswith("_attempt")]
    counts = {t["value"]: t["count"] for t in client.get(f"{ACTIVITY}/facets", headers=b).json()["types"]}
    assert counts["drill_attempt"] == 0


def test_existing_rows_read_as_before_beside_the_new_ones(client):
    from tests.test_roadmap import answer

    h = nurse(client)
    before = feed(client, h)
    answer(client, h, "registered-nurse", "e-good-0", "I listened, assessed and escalated with SBAR. " * 3)
    with_answer = feed(client, h)["items"]
    attempt(client, h, "drill")
    after = feed(client, h)["items"]
    assert before["total"] == 0
    old = [i for i in after if i["type"] == "written_answer"]
    assert old == [i for i in with_answer if i["type"] == "written_answer"]  # the answer's row is unchanged

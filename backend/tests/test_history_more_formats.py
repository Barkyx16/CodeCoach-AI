"""Scenario runs, code reviews and sample-answer comparisons in History (Volume 17, prompt 2;
docs/COMPARING_ATTEMPTS.md, History): each attempt is a row with its date, format, what was practised
and its result in the words its own page's list uses, says why it isn't compared with the one before
(no comparison contract covers these formats), and links to that one attempt; a scenario run in
progress is "In progress". History's type and status filters, its counts and its facets include them;
a coding-problems filter shows code reviews and a career filter shows that career's scenario runs;
every practice row links to its attempt, the earlier formats included; reading History stays bounded;
another account's attempts never appear. Synthetic data only."""

from __future__ import annotations

from tests.test_history_practice import feed
from tests.test_practice_conditions import finish, nurse, run
from tests.test_review_formats_conditions import EXERCISE, SPECIFIC, a_comparison, a_review

ACTIVITY = "/api/v1/me/activity"


def rows(client, h, type_, **params):
    return [i for i in feed(client, h, **params)["items"] if i["type"] == type_]


def test_a_scenario_run_is_a_row_in_progress_then_finished_as_its_page_says(client):
    h = nurse(client)
    a = run(client, h)
    [row] = rows(client, h, "scenario_attempt")
    assert row["status"] == "in_progress" and row["status_label"] == "In progress"
    assert row["detail"].startswith("In progress · version ")
    assert row["detail"].endswith("Not compared: scenario runs aren't compared with each other")
    assert row["target"] == {**row["target"], "href": f"/scenarios/attempts/{a['id']}", "attempt_id": a["id"]}
    assert row["career"] == "registered-nurse" and row["title"]
    done = finish(client, h, a)
    [row] = rows(client, h, "scenario_attempt")
    assert row["status"] == "completed"
    page = {x["id"]: x for x in client.get("/api/v1/me/scenario-attempts", headers=h).json()}
    assert row["detail"].startswith(page[done["id"]]["outcome"])  # its own list's words for how it ended


def test_a_code_review_row_says_what_its_page_says_and_opens_that_review(client):
    h = nurse(client)
    review = a_review(client, h)
    [row] = rows(client, h, "code_review_attempt")
    page = client.get(f"/api/v1/me/code-reviews/{EXERCISE}/attempts", headers=h).json()
    [listed] = [x for x in page if x["id"] == review["id"]]
    expected = f"{listed['findings']} finding" + ("" if listed["findings"] == 1 else "s")
    assert row["detail"].startswith(expected)
    assert (
        f"points at {listed['defects_raised']} of {listed['defects_total']} authored defect" in row["detail"]
    )
    assert f"version {listed['exercise_version']}" in row["detail"]
    assert row["detail"].endswith("Not compared: code reviews aren't compared with each other yet")
    assert row["target"]["href"] == f"/code-reviews/attempts/{review['id']}"
    assert row["career"] == "coding" and row["career_title"] == "Coding problems"
    assert row["status"] == "completed"


def test_a_comparison_row_says_what_its_page_says_and_opens_that_reading(client):
    h = nurse(client)
    reading = a_comparison(client, h)
    [row] = rows(client, h, "comparison_attempt")
    page = client.get(f"/api/v1/me/comparisons/{SPECIFIC}/attempts", headers=h).json()
    [listed] = [x for x in page if x["id"] == reading["id"]]
    excerpts = f"{listed['selections']} excerpt" + ("" if listed["selections"] == 1 else "s")
    assert row["detail"].startswith(f"{excerpts}, {listed['matches']} matching the explanation")
    assert row["detail"].endswith(
        "Not compared: readings of sample answers aren't compared with each other yet"
    )
    assert row["target"]["href"] == f"/compare/{SPECIFIC}?attempt={reading['id']}"
    assert row["career"] == ""  # a sample-answer lesson is for every career


def test_filters_counts_and_facets_include_them(client):
    h = nurse(client)
    finish(client, h, run(client, h))
    run(client, h)  # a second run, in progress
    a_review(client, h)
    a_comparison(client, h)
    everything = feed(client, h)
    types = {i["type"] for i in everything["items"]}
    assert {"scenario_attempt", "code_review_attempt", "comparison_attempt"} <= types
    assert feed(client, h, type="scenario_attempt")["total"] == 2
    assert feed(client, h, type="scenario_attempt", status="in_progress")["total"] == 1
    assert feed(client, h, type="code_review_attempt", status="in_progress")["total"] == 0
    # Coding problems: the code review, not the scenario or the reading.
    coding = {i["type"] for i in feed(client, h, career="coding")["items"]}
    assert "code_review_attempt" in coding and not coding & {"scenario_attempt", "comparison_attempt"}
    nursing = {i["type"] for i in feed(client, h, career="registered-nurse")["items"]}
    assert "scenario_attempt" in nursing and not nursing & {"code_review_attempt", "comparison_attempt"}
    facets = client.get(f"{ACTIVITY}/facets", headers=h).json()
    counts = {t["value"]: t["count"] for t in facets["types"]}
    assert (counts["scenario_attempt"], counts["code_review_attempt"], counts["comparison_attempt"]) == (
        2,
        1,
        1,
    )
    statuses = {s["value"]: s["count"] for s in facets["statuses"]}
    assert statuses["in_progress"] >= 1
    assert sum(counts.values()) == everything["total"]


def test_rows_interleave_with_other_kinds_newest_first_and_page_stably(client):
    from tests.test_checklist_comparisons import attempt

    h = nurse(client)
    attempt(client, h, "drill")
    a_review(client, h)
    a_comparison(client, h)
    attempt(client, h, "drill")
    items = feed(client, h)["items"]
    times = [(i["occurred_at"], i["id"]) for i in items]
    assert times == sorted(times, reverse=True)
    first = feed(client, h, page_size=2)
    second = client.get(ACTIVITY, headers=h, params={"page": 2, "page_size": 2}).json()
    assert [i["id"] for i in first["items"] + second["items"]] == [i["id"] for i in items[:4]]


def test_another_accounts_attempts_never_appear(client):
    theirs = nurse(client, email="other@example.com")
    run(client, theirs)
    a_review(client, theirs)
    a_comparison(client, theirs)
    h = nurse(client)
    assert feed(client, h)["total"] == 0
    facets = client.get(f"{ACTIVITY}/facets", headers=h).json()
    assert all(t["count"] == 0 for t in facets["types"])


def test_reading_history_stays_bounded_with_these_formats(client):
    from tests.test_query_budgets import statements

    h = nurse(client)
    first = run(client, h)
    a_review(client, h)
    a_comparison(client, h)
    with statements(client) as seen:
        feed(client, h)
    few = len(seen)
    for _ in range(6):
        a_review(client, h)
        a_comparison(client, h)
    finish(client, h, first)
    run(client, h)  # the first run finished; a second one started
    with statements(client) as seen:
        feed(client, h)
    assert len(seen) == few, (few, len(seen))
